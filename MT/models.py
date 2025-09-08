# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from django.db.models import Max, Min
# DISABLE WEBPUSH from webpush import send_user_notification, send_group_notification
# DISABLE TELEGRAM import telegram
from django.conf import settings

import pytz
import requests
import json
import time
import logging
import threading
import sys
from datetime import datetime, timedelta
import traceback
from decimal import Decimal

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Gestión de excepciones
# ──────────────────────────────────────────────────────────────────────────────

class MoTradeError(Exception):
    """Excepción unificada con código de error y mensaje."""

    def __init__(self, code: int, message: str, *args):
        super().__init__(message, *args)
        self.code = code
        self.message = message

    def __str__(self):
        return f"[{self.code}] {self.message}"


# ──────────────────────────────────────────────────────────────────────────────
# Parámetros mejorados de gestión (seguros por defecteo)
# ──────────────────────────────────────────────────────────────────────────────
ATR_MULT_SL = Decimal("2.0")       # Stop inicial: 2xATR
ATR_MULT_TSL = Decimal("2.5")      # Trailing: 2.5xATR desde el extremo
TP1_R_MULT = Decimal("1.0")        # (lógico) Toma parcial en 1R (marcado por flag)
BREAKEVEN_R = Decimal("0.7")       # Mover a BE a partir de 0.7R
MAX_BARS_IN_TRADE = 240            # Time-stop en nº de velas
ADX_MIN_DEFAULT = Decimal("0")     # Conserva tu filtro existente via limitOpen
VOL_MIN_PCT = Decimal("0.30")      # Volatilidad mínima (ATR% del precio) para operar

# ──────────────────────────────────────────────────────────────────────────────
# Funciones Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _D(x):
    return Decimal(str(x)) if x is not None else None

def _to_roll_date(dttm, offset_minutes=0):
    """Convierte un datetime a fecha (UTC) aplicando un 'rollover' por minutos (p.ej. sesión)."""
    if dttm is None:
        return None
    # Asegura zona
    if timezone.is_naive(dttm):
        dttm = timezone.make_aware(dttm, timezone.utc)
    dttm_utc = dttm.astimezone(timezone.utc) + timedelta(minutes=offset_minutes)
    return dttm_utc.date()

def _compute_atr_wilder(candles, period=14):
    """
    Modifica in-place la lista de velas (orden ascendente), añadiendo 'atr' por barra.
    candles: [{'open':..., 'high':..., 'low':..., 'close':..., 'time': 'YYYY-mm-ddT00:00:00Z'}, ...]
    """
    n = len(candles)
    if n == 0:
        return candles
    # True Range por barra
    trs = []
    prev_close = None
    for i in range(n):
        h, l, c = float(candles[i]["high"]), float(candles[i]["low"]), float(candles[i]["close"])
        if prev_close is None:
            tr = h - l
        else:
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    # RMA de Wilder
    atr = [None] * n
    if n >= period:
        atr[period-1] = sum(trs[:period]) / period
        for i in range(period, n):
            atr[i] = (atr[i-1] * (period - 1) + trs[i]) / period
    # Asigna
    for i in range(n):
        candles[i]["atr"] = float(atr[i]) if atr[i] is not None else None
    return candles

# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY
# ──────────────────────────────────────────────────────────────────────────────
class Strategy(models.Model):

    # ── MÉTODOS DE ESTADO / UI ────────────────────────────────────────────────
    def status(self):
        statusUtility = "<u><b>" + self.utility + str(self.cryptoTimeframeADX or '|1d') + str(self.cryptoTimeframeDI or '|1d') + "</b></u> \n"
        if self.accion == "VENDER":
            statusOperation = "VENDER"
        elif self.accion == "COMPRAR":
            statusOperation = "COMPRAR"
        else:
            statusOperation = ""
        profit = self.currentProfit if self.currentProfit is not None else 0
        return statusUtility + " " + statusOperation + " " + f'{profit:3.2f}' + "%"

    # ── INTERFAZ CON EL SERVICIO LOCAL (sin cambios funcionales) ─────────────
    def get_position(self, position_id):
        if self.operIDclose is None:
            operIDclose = 0
        else:
            operIDclose = self.operIDclose

        data = {
            'order_id': position_id,
            'order_id_close': operIDclose,
            'instrument_id_bingx': self.operSymbolBingx
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            'http://127.0.0.1:5000/get_position',
            headers=headers,
            data=json.dumps(data))

        try:
            salida = (response.json())
        except Exception:
            logger.error(' -- ' + str(self.operSymbolBingx))
            logger.error('Error en get_position al leer el response.json()')
            logger.error(response.text)

        return response.json()[0], response.json()[1]

    def buy_order(self, instrument_type, instrument_id, instrument_id_bingx, side,
        amount, leverage, type, limit_price=None, stop_lose_kind=None,
        stop_lose_value=None, use_trail_stop=None):

        data = {
            'instrument_type': instrument_type,
            'instrument_id': instrument_id,
            'instrument_id_bingx': instrument_id_bingx,
            'side': side,
            'amount': amount,
            'leverage': leverage,
            'type': type,
            'limit_price': limit_price,
            'stop_lose_kind': stop_lose_kind,
            'stop_lose_value': stop_lose_value,
            'use_trail_stop': use_trail_stop,
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            'http://127.0.0.1:5000/buy_order',
            headers=headers,
            data=json.dumps(data))

        return response.json()[0], response.json()[1]

    def close_position(self, order_id):
        data = {
            'order_id': order_id,
            'instrument_id_bingx': self.operSymbolBingx
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            'http://127.0.0.1:5000/close_position',
            headers=headers,
            data=json.dumps(data))

        # no probado, con BINGX devuelvo el ID de orden de cierre
        return response.json()[0], response.json()[1]

    def cancel_order(self, order_id):
        data = '{"order_id": ' + str(order_id) + ' }'
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            'http://127.0.0.1:5000/cancel_order',
            headers=headers,
            data=data)
        return response.json()

    # ── Obtener velas de los datos locales ───────────────────────────────────
    def get_candle(self, limit=200, timeframe="1d", with_atr=False, atr_period=14, session_offset_minutes=0):
        """
        Genera velas desde StrategyState (muestras 10m) SIN llamar a ningún endpoint externo.

        Parámetros:
          - limit: nº de velas a devolver (por defecto 200)
          - timeframe: sólo "1d" está soportado aquí
          - with_atr: si True, añade clave 'atr' en cada vela (Wilder)
          - atr_period: periodo del ATR
          - session_offset_minutes: desplaza el rollover diario (0 = UTC puro)

        Devuelve:
          Lista de velas en orden ASC:
          [{"time":"YYYY-mm-ddT00:00:00Z","open":..,"high":..,"low":..,"close":.., "atr":..?}, ...]
        """
        if timeframe.lower() != "1d":
            # Puedes ampliar a 1h/4h si lo necesitas; por ahora forzamos 1d
            timeframe = "1d"

        # Para tener margen para ATR, lee días extra
        days_needed = int(limit) + int(atr_period) + 5
        start_dt = timezone.now() - timedelta(days=days_needed)

        # Lee tus muestras (cada 10 min) de ESTA estrategia
        qs = (StrategyState.objects
              .filter(strategy=self, timestamp__gte=start_dt)
              .exclude(currentRate__isnull=True)
              .order_by('timestamp')
              .values('timestamp', 'currentRate'))

        # Agregación diaria
        daily_map = {}   # key: date  → dict con o/h/l/c
        for row in qs.iterator():
            ts = row['timestamp']
            px = float(row['currentRate'])
            dkey = _to_roll_date(ts, offset_minutes=session_offset_minutes)
            if dkey is None:
                continue
            if dkey not in daily_map:
                daily_map[dkey] = {'open': px, 'high': px, 'low': px, 'close': px}
            else:
                rec = daily_map[dkey]
                # open es el primero del día (no cambia)
                rec['high'] = max(rec['high'], px)
                rec['low']  = min(rec['low'], px)
                rec['close'] = px  # último del día

        # Ordena por fecha ASC y forma velas
        days_sorted = sorted(daily_map.keys())
        candles = [{
            "time": f"{d.isoformat()}T00:00:00Z",
            "open": float(daily_map[d]['open']),
            "high": float(daily_map[d]['high']),
            "low":  float(daily_map[d]['low']),
            "close":float(daily_map[d]['close']),
        } for d in days_sorted]

        # Limita al nº solicitado
        if len(candles) > limit:
            candles = candles[-limit:]

        # ATR opcional
        if with_atr:
            _compute_atr_wilder(candles, period=atr_period)

        return candles

    # ── MODELO DE DATOS ──────────────────────────────────────────────────────
    utility = models.CharField(max_length=16, null=True)
    nextUpdate = models.DateTimeField(
        auto_now=False, auto_now_add=False, null=True, default=timezone.now)
    rateSymbol = models.CharField(max_length=16, null=True)
    operSymbol = models.CharField(max_length=16, null=True)
    operSymbolBingx = models.CharField(max_length=16, null=True)
    tickSymbol = models.CharField(max_length=32, null=True)
    operID = models.IntegerField(null=True, blank=True)
    operIDclose = models.IntegerField(null=True, blank=True)
    currentProfit = models.FloatField(null=True, blank=True)
    accion = models.CharField(max_length=10, null=True, blank=True)

    class StrategyStates(models.IntegerChoices):
        HOLD = 0
        PREOPER = 1
        OPER = 2
        COOLDOWN = 3

    estado = models.IntegerField(
        choices=StrategyStates.choices, null=True, default=0)
    ema = models.FloatField(null=True, blank=True)
    ema20 = models.FloatField(null=True, blank=True)
    ema100 = models.FloatField(null=True, blank=True)
    adx = models.FloatField(null=True, blank=True)
    plusDI = models.FloatField(null=True, blank=True)
    minusDI = models.FloatField(null=True, blank=True)
    diffDI = models.FloatField(null=True, blank=True)
    currentRate = models.FloatField(null=True, blank=True)
    maxCurrentRate = models.FloatField(null=True, blank=True)
    stopLoss = models.FloatField(null=True)
    stopLossCurrent = models.FloatField(null=True, blank=True)
    takeProfitCurrent = models.FloatField(null=True, blank=True)
    sleep = models.IntegerField(null=True)
    cooldownUntil = models.DateTimeField(
        auto_now=False, auto_now_add=False, null=True, default=timezone.now)
    amount = models.IntegerField(null=True)
    beneficioTotal = models.FloatField(null=True, default=0, blank=True)
    limitOpen = models.IntegerField(null=True)
    limitClose = models.IntegerField(null=True)
    adxClose = models.IntegerField(null=True, default=0)
    limitBuy = models.IntegerField(null=True)
    limitSell = models.IntegerField(null=True)
    cryptoTimeframeADX = models.CharField(max_length=4, null=True, blank=True)
    cryptoTimeframeDI = models.CharField(max_length=4, null=True, blank=True)
    isRunning = models.BooleanField(default=False)
    protectedTrade = models.BooleanField(default=False)
    placedPrice = models.FloatField(null=True, blank=True)
    bet = models.IntegerField(null=True, default=0)
    comments = models.TextField(null=True, blank=True)
    recommendMA = models.FloatField(default=0, null=True, blank=True)
    recommendMA240 = models.FloatField(default=0, null=True, blank=True)
    inError = models.BooleanField(default=False)
    leverage = models.IntegerField(default=4)

    # NUEVOS CAMPOS (opcionales)
    atr = models.FloatField(null=True, blank=True)  # ATR para sizing/SL
    bars_in_trade = models.IntegerField(null=True, blank=True, default=0)
    partial_done = models.BooleanField(default=False)

    # Campos nuevos no usados. Futura ampliacion
    last_trade_day = models.DateField(null=True, blank=True)
    day_pnl = models.DecimalField(default=Decimal("0"), max_digits=9, decimal_places=2)

    def __str__(self):
        return (self.utility + str(self.cryptoTimeframeADX or '|1d') +
                str(self.cryptoTimeframeDI or '|1d'))

    # ── MODIFICADORES ────────────────────────────────────────────────────────
    def clear(self):
        self.beneficioTotal = 0
        self.isRunning = True
        self.operID = 0
        self.estado = 3
        self.accion = "COOLDOWN"
        self.maxCurrentRate = 0
        self.nextUpdate = timezone.now()
        self.bet = 0
        self.comments = ""
        self.save()
        self.getOperations().delete()
        StrategyState.objects.filter(strategy=self).delete()

    def toggleIsRunning(self):
        if self.isRunning:
            self.isRunning = False
        else:
            self.isRunning = True
            self.estado = 3
        self.save()

    def unlock(self):
        if self.estado == 3:
            self.estado = 0
            self.accion = "WAIT"
            self.save()

    def setAmount(self, amount):
        self.amount = amount
        self.save()

    # ── GETS ─────────────────────────────────────────────────────────────────
    def getHistory(self):
        history = StrategyState.objects.filter(strategy=self).order_by('timestamp')
        return history

    def getOperations(self):
        return StrategyOperation.objects.filter(strategy=self)

    def getComments(self):
        return self.comments

    # ── Operation ────────────────────────────────────────────────────────────
    # ── UPDATE: Añadimos calculo del ATR a partir de las velas ───────────────
    def update(self):
        cryptoDataraw = ('{"symbols":{"tickers":["' + self.tickSymbol + '"],"query":{"types":[]}},"columns":['
            + '"ADX' + str(self.cryptoTimeframeADX or '') + '",'
            + '"ADX+DI' + str(self.cryptoTimeframeDI or '') + '",'
            + '"ADX-DI' + str(self.cryptoTimeframeDI or '') + '",'
            + '"EMA10' + str(self.cryptoTimeframeADX or '') + '",'
            + '"EMA20' + str(self.cryptoTimeframeADX or '') + '",'
            + '"EMA100' + str(self.cryptoTimeframeADX or '') + '",'
            + '"Recommend.MA' + str(self.cryptoTimeframeADX or '') + '",'
            + '"Recommend.MA|240"'
            + ']}')

        headers = {
            'authority': 'scanner.tradingview.com',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
            'content-type': 'application/x-www-form-urlencoded',
            'accept': '*/*',
            'origin': 'https://www.tradingview.com',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://www.tradingview.com/',
            'accept-language': 'en,es;q=0.9',
            'cookie': '_ga=GA1.2.526459883.1610099096; __gads=ID=8f36aef99159e559:T=1610100101:S=ALNI_Mars83GB1m6Wd227WWiChIcow2RpQ; sessionid=8pzntqn1e9y9p347mq5y54mo5yvb8zqq; tv_ecuid=41f8c020-6882-40d1-a729-c638b361d4b3; _sp_id.cf1a=18259830-0041-4e5d-bbec-2f481ebd9b76.1610099095.44.1613162553.1612699115.1f98354c-1841-47fc-ab5d-d7113cfa5090; _sp_ses.cf1a=*; _gid=GA1.2.1715043600.1613162554; _gat_gtag_UA_24278967_1=1',
        }

        response = requests.post(
            'https://scanner.tradingview.com/crypto/scan', 
            headers=headers, 
            data=cryptoDataraw)

        if response.json()['totalCount'] == 0:
            raise MoTradeError(3, "MOT-00003: No data from TradingView for " + self.rateSymbol)

        try:
            d = response.json()['data'][0]['d']
            self.adx = d[0]
            self.plusDI = d[1]
            self.minusDI = d[2]
            self.ema = d[3]
            self.ema20 = d[4]
            self.ema100 = d[5]
            self.diffDI = self.plusDI - self.minusDI
            self.recommendMA = d[6]
            self.recommendMA240 = d[7]

            # --- ATR desde tus propias muestras (StrategyState) ---
            try:
                candles = self.get_candle(limit=200, timeframe=self.cryptoTimeframeADX or "1d",
                                          with_atr=True, atr_period=14, session_offset_minutes=0)
                if candles and candles[-1].get("atr") is not None:
                    self.atr = float(candles[-1]["atr"])
                else:
                    self.atr = None
            except Exception as e:
                logger.warning("No se pudo calcular ATR desde StrategyState: %s", e)
                self.atr = None

        except Exception as e:
            logger.error("Error al leer datos de tradingview: %s", e)
            logger.error(response.content)
            raise e

        data = {
            'instrument_id_bingx': self.operSymbolBingx
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(
            'http://127.0.0.1:5000/get_price',
            headers=headers,
            data=json.dumps(data))
	
        resp_json = response.json()

        #resp = requests.get('https://api.binance.com/api/v1/ticker/price?symbol='+self.rateSymbol)
        #resp_json = resp.json()
        if float(resp_json['price']) > -1:
            self.currentRate = float(resp_json['price'])
        else:
            logger.error("No se ha podido obtener el precio de " + str(self.rateSymbol))
        self.save()

    # ── LÓGICA PRINCIPAL ─────────────────────────────────────────────────────
    def operation(self, isMarketOpen):
        logger.debug("Entering operation for " + str(self.rateSymbol))

        try:
            # Sanity Checks
            # Comprobaciones de que todo es correcto. Si no, cancelamos llamada a operation

            if self.estado == 2 and self.operID == 0:
            ## Operacion en curso, pero no tenemos OPERID
                # logger.error("MOT-00001: Open operation without operID at " + self.rateSymbol)
                # self.inError = True
                # self.save()
                # return
                raise MoTradeError(1, "MOT-00001: Open operation without operID at " + self.rateSymbol)

            if self.estado == 2 and self.bet == 0:
            ## Operacion en curso, pero no se ha cargado BET
                # logger.error ("MOT-00002: Bet can't be zero with an open operation at " + self.rateSymbol)
                # self.inError=True
                # self.save()
                # return
                raise MoTradeError(2, "MOT-00002: Bet can't be zero with an open operation at " + self.rateSymbol)

            if self.cooldownUntil is None:
                self.cooldownUntil = timezone.now()

            # Refresca datos
            self.update()
            self.nextUpdate = timezone.now() + timedelta(seconds=self.sleep)

            if self.isRunning:
                logger.debug("Symbol is running so we evaluate")
                estadoNext = self.estado
                cierre=False

                # ── PROTECTED TRADE: conserva tu lógica anterior (mínimo cambio) ──
                if self.protectedTrade:
                    logger.debug("Symbol is in protected trading mode")
                    ## Inicio proceso protected Trade
                    if self.estado == 0:
                        ## Estado HOLD. 
                        self.maxCurrentRate = 0
                        self.accion = "WAIT"
                        ## Abrimos si el ADX está por encima del mínimo limitOpen

                        if self.adx > self.limitOpen :
                            if self.diffDI > self.limitBuy :
                                check = self.comprar()
                                if check:
                                    estadoNext = 2
                                    self.currentProfit = 0
                                    self.bet = self.amount
                                    self.maxCurrentRate = self.currentRate
                            if self.diffDI < self.limitSell :
                                check = self.vender()
                                if check:
                                    estadoNext = 2
                                    self.currentProfit = 0
                                    self.bet = self.amount
                                    self.maxCurrentRate = self.currentRate
                    if self.estado == 2:
                        check, position = self.get_position(self.operID)
                        if check:
                            # La orden se ha ejecutado
                            self.currentProfit = round((position['position']['currentProfit'] / (self.bet or 1)) * 100, 2)
                            if position['position']['sell_amount'] == 0 or position['position']['buy_amount'] == 0:
                                # Y la orden sigue abierta
                                if position['orders'][0]['side'] == "sell":
                                    self.accion = "VENDER"
                                    if self.currentRate < self.maxCurrentRate :
                                        self.maxCurrentRate = self.currentRate
                                else:
                                    self.accion = "COMPRAR"
                                    if self.currentRate > self.maxCurrentRate :
                                        self.maxCurrentRate = self.currentRate
                            else:
                                # Y la orden se ha cerrado
                                estadoNext = 0
                                self.sleep = 60
                                self.placedPrice = 0
                                self.accion = "CERRAR"
                                beneficio = position['position']['sell_amount'] - position['position']['buy_amount']
                                profit = beneficio * 100 / self.bet
                                self.beneficioTotal = self.beneficioTotal + beneficio
                                Noperation = StrategyOperation.objects.filter(operID__exact=self.operID)
                                Noperation[0].close(float(beneficio),
                                                    float(position['position']['buy_amount']),
                                                    float(position['position']['sell_amount']),
                                                    "AUTO",
                                                    0,            ## Cuanto hace que esto no funciona?
                                                    profit)
                                self.operID = 0
                                self.bet = 0
                        else:
                            check = self.cancel_order(self.operID)
                            if check:
                                estadoNext = 0
                                self.sleep = 60
                                self.accion = "WAIT"
                                StrategyOperation.objects.filter(operID=self.operID).delete()
                                self.operID = 0
                ## Fin de protected trade 
                
                # ── MODO NORMAL: lógica mejorada (ATR, sizing, trailing, time-stop) ──
                else:
                    logger.debug("Symbol is in normal operation mode")
                    if self.estado == 0:  # HOLD
                        logger.debug ("Symbol is in HOLD status")
                        self.currentProfit = None
                        self.maxCurrentRate = 0
                        self.accion = "WAIT"

                        # Filtros de entrada
                        ## Primero hay que entrar por el limitOpen. ADX debe ser superior
                        ## en caso contrario no entramos
                        
                        if self.adx > self.limitOpen:
                            # Señal direccional junto a TV Recommend
                            side = None
                            if (self.diffDI > self.limitBuy) and self.checkRecommend() and isMarketOpen:
                                side = "long"
                            if (self.diffDI < self.limitSell) and self.checkRecommend() and isMarketOpen:
                                side = "short"

                        ## Despues, el diffDI debe superar el limitBuy o el limitSell
                        ## self.checkRecommend tiene en cuenta la recomendacion general de TV
                        ## isMarketOpen comprueba si el nasdaq esta abierto
                            ## Busca limitar ante bajo volumen

                            if (self.diffDI > self.limitBuy) : 
                                if self.checkRecommend() and isMarketOpen :
                                    check=self.comprar()
                                    if check :
                                        self.maxCurrentRate=self.currentRate
                                        self.accion="COMPRAR"
                                        self.currentProfit=0
                                        estadoNext=2
                                        self.bet=self.amount
                                        self.adxClose=self.limitClose
                            if (self.diffDI < self.limitSell) : 
                                if self.checkRecommend() and isMarketOpen :
                                    check=self.vender()
                                    if check:
                                        self.maxCurrentRate = self.currentRate
                                        self.accion = "VENDER"
                                        self.currentProfit = 0
                                        estadoNext = 2
                                        self.bet=self.amount
                                        self.adxClose=self.limitClose
   
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    if self.estado == 2:  # OPER
                        logger.debug("Symbol is in operation status")
                    # Estamos en OPERACION NOT PROTECTED
                        # Setup INICIAL
                        force=False
                        reason=" "
    
                        # Si no se ha fijado el SLCurrent y el TPCurrent, hacerlo ahora
                        if self.stopLossCurrent is None :
                            self.stopLossCurrent = self.stopLoss
                            self.takeProfitCurrent = self.stopLoss + 50
    
                        # Obtener estado de posicion
                        check,position=self.get_position(self.operID)
                        if check :
                            # if position['position']['close_at'] > 0 :
                            # para IQoption, close_at is not None, pero nunca mas lo usaremos.
                            if position['position']['currentProfit'] == -9999 :
                            # Esta fealdad la puedo sustituir por el retorno isPositionOpen
                                ## la posicion está cerrada
                                reason=reason+"notOpen "
                                self.cooldownUntil=timezone.now()+timedelta(days=2)
                                self.operIDclose=position['position']['orderIDClose']
                                cierre=True
                                force=True
                            else :
                                self.currentProfit=round((position['position']['currentProfit']/self.bet)*100 ,2)
    
                        # Tenemos el currentProfit y los SL y TP, pero primero calculamos si hay que cerrar, antes de ejecutar
    
                        if (self.adx*0.85) > self.adxClose :
                            self.adxClose=self.adx*0.85
                        if self.limitClose==0:
                            self.adxClose=0
                        if self.adx<self.adxClose :
                            cierre=True
                            reason=reason+"limitClose "
                        if self.accion == "VENDER" :
                            if self.currentRate < self.maxCurrentRate :
                                self.maxCurrentRate = self.currentRate
                            if self.diffDI > self.limitSell*0.85 :
                                cierre=True
                                reason=reason+"limitSell "
                            ### Ante un stopLoss, esperamos 48 periodos                            
                            ### If we are below stopLoss and checkRecommend Fails. Close!
                            if ( self.currentProfit < self.stopLossCurrent ) and not self.checkRecommend() :
                                cierre=True
                                reason=reason+"stopLoss "
                                self.cooldownUntil=timezone.now()+timedelta(days=1)
                            if (self.currentProfit > self.takeProfitCurrent) and not self.checkRecommend() :
                                # Si excedemos el takeProfit, pero el check recommend es TRUE no entramos
                                # Asumimos que seguimos subiendo
                                # Si lo alcanzamos y el checkRecommend es FALSE, cazamos, ya que asuimos que bajara
                                # Nota 20/11/2024 - Creo que nunca vamos a entrar aqui
                                cierre=True
                                reason=reason+"takeProfit "
                                self.cooldownUntil=timezone.now()+timedelta(days=1)
    
                        else :
                            if self.currentRate > self.maxCurrentRate :
                                self.maxCurrentRate = self.currentRate
                            if self.diffDI < self.limitBuy*0.85 :
                                cierre=True
                                reason=reason+"limitBuy "
                            ### Ante un stopLoss, esperamos 48 periodos                            
                            if self.currentProfit < self.stopLossCurrent and not self.checkRecommend():
                                cierre=True
                                reason=reason+"stopLoss "
                                self.cooldownUntil=timezone.now()+timedelta(days=1)
                            if (self.currentProfit > self.takeProfitCurrent) and not self.checkRecommend() :
                                # Si excedemos el takeProfit, pero el check recommend es TRUE no entramos
                                # Asumimos que seguimos subiendo
                                # Si lo alcanzamos y el checkRecommend es FALSE, cazamos, ya que asuimos que bajara
                                # Nota 20/11/2024 - Creo que nunca vamos a entrar aqui                                cierre=True
                                reason=reason+"takeProfit "
                                self.cooldownUntil=timezone.now()+timedelta(days=1)
    
                        # Now we update SLc and TPc
                        if ( self.currentProfit + self.stopLoss > self.stopLossCurrent ) :
                            # if Current Profit plus stopLoss (Which is always negative!) is higher that current stopLoss, 
                            # this is a regular trailing stoploss. We ser stopLoss at current profit minus stopLoss 
                            self.stopLossCurrent = self.currentProfit + self.stopLoss
    
                        if (self.stopLossCurrent < 1) and (self.currentProfit > 15):
                            # If profit reaches 15, set stopLoss to 0 to prevent Losses
                            self.stopLossCurrent=0
      
                        if (self.stopLossCurrent < self.currentProfit) :
                        #IF SL is below currentProfit
                            # Stop Loss "Hugging"
                            # TODO
                            # I am searching for the perfect balance. I am being toooooo aggresive.
                            # 20/11/2024 changed from 0.01 to 0.008
                            self.stopLossCurrent = self.stopLossCurrent + ((self.currentProfit - self.stopLossCurrent)*0.002)

                        # TODO
                        # Replace stopLoss in the bot with the BINGX stopLoss
                        # I need a new property, stopLossOrderID
                        # if stopLossorderID is not -1
                        # cancel orderId stopLossOrderID
                        # set new stopLossOrder (I have to calculate the price)!
    
                        # Finalmente, siempre, takeProfitCurrent
                        self.takeProfitCurrent = self.stopLossCurrent + 40
    
                        if cierre :
                            check=self.cerrar(reason,force)
                            if check:
                                # payload = {"head": self.__str__(), "body": "Cerrar"}
                                #send_group_notification(group_name="notificame", payload=payload, ttl=100000)	
                                #telegram_settings = settings.TELEGRAM
                                #bot = telegram.Bot(token=telegram_settings['bot_token'])
                                #bot.send_message(chat_id="@%s" % telegram_settings['channel_name'],
                                #    text=self.__str__()+" Cerrar", parse_mode=telegram.ParseMode.HTML)
                                self.accion = "CERRAR"
                                estadoNext = 3
                                self.bet = 0
                                self.stopLossCurrent = None
                                self.takeProfitCurrent = None
                                self.currentProfit = None
                                self.adxClose = self.limitClose or 0

                # ── COOLDOWN ──────────────────────────────────────────────────
                if self.estado == 3:
                    logger.debug("Symbol is in cooldown mode")
                    self.currentProfit = None
                    ## Si el ADX esta por debajo del OPEN, salimos del cooldown
                    ## Si el limitOpen es 0, no hay cooldown y salimos
                    if self.adx < self.limitOpen or self.limitOpen==0 :
                        estadoNext = 0
                        self.accion = "WAIT"
                    else:
                        estadoNext = 3
                        self.accion = "COOLDOWN"
                    ## Si el cooldownUntil está en el futuro, esperamos
                    if self.cooldownUntil < timezone.now():
                        estadoNext = 0
                        self.accion = "WAIT"
                    else:
                        estadoNext = 3
                        self.accion = "COOLDOWN"

                self.estado = estadoNext

            # Log y persistencia final
            self.log()
            self.inError = False
            self.save()

        except MoTradeError as e:
            logger.error("Excepcion conocida (%s) en %s: %s", e.code, self.rateSymbol, e.message)
            self.inError = True
            self.save()                

        except Exception as e:
            self.inError = True
            self.save()
            logger.exception("MOT-99999: Excepcion no controlada en " + self.rateSymbol)

    # ── CIERRE MANUAL (Llamada desde la consola) ───────────────
    def manualClose(self, reason):
    # Used when closed is called from the web console
        self.cooldownUntil = timezone.now() + timedelta(days=1)
            # Cooldown de 48 periodos. Igual que cierre por stoploss

        force = False
        check = self.cerrar(reason, force)
        if check:
            #payload = {"head": self.__str__(), "body": "Cerrar"}
            #send_group_notification(group_name="notificame", payload=payload, ttl=100000)      
            #telegram_settings = settings.TELEGRAM
            #bot = telegram.Bot(token=telegram_settings['bot_token'])
            #bot.send_message(chat_id="@%s" % telegram_settings['channel_name'],
            #    text=self.__str__()+" Cerrar", parse_mode=telegram.ParseMode.HTML)
            self.accion = "CERRAR"
            estadoNext = 3
            self.bet = 0
            self.adxClose = self.limitClose
            self.estado = estadoNext
            self.stopLossCurrent = None
            self.takeProfitCurrent = None
            self.log()
            self.save()

    # ── LOG DE ESTADO ───────────────────────────────────────────────────────
    def log(self):
        StrategyState(strategy=self,
            operID=self.operID,
            accion=self.accion,
            estado=self.estado,
            ema=self.ema,
            ema20=self.ema20,
            ema100=self.ema100,
            adx=self.adx,
            plusDI=self.plusDI,
            minusDI=self.minusDI,
            diffDI=self.diffDI,
            currentRate=self.currentRate,
            currentProfit=self.currentProfit,
            maxCurrentRate=self.maxCurrentRate,
            stopLoss=self.stopLoss,
            sleep=self.sleep,
            amount=self.amount,
            beneficioTotal=self.beneficioTotal,
            limitOpen=self.limitOpen,
            limitClose=self.limitClose,
            limitBuy=self.limitBuy,
            limitSell=self.limitSell,
            cryptoTimeframeADX=self.cryptoTimeframeADX,
            cryptoTimeframeDI=self.cryptoTimeframeDI,
            recommendMA=self.recommendMA,
            recommendMA240=self.recommendMA240,
            isRunning=self.isRunning,
            stopLossCurrent=self.stopLossCurrent,
            atr=self.atr).save()

    # ── ÓRDENES DE ENTRADA (conserva interfaz; añade flag protected) ─────────
    def comprar(self):
        if self.protectedTrade :
            check, order_id = self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                instrument_id_bingx=self.operSymbolBingx,
                side="buy",
                amount=self.amount,
                leverage=self.leverage,
                # type="limit", limit_price=self.ema,
                type="market",
                stop_lose_kind="percent", stop_lose_value=self.stopLoss,
                use_trail_stop=True)
            self.placedPrice = self.ema
        else:
            check, order_id = self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                instrument_id_bingx=self.operSymbolBingx,
                side="buy",
                amount=self.amount,
                leverage=self.leverage,
                type="market")
        if check:
            self.operID = order_id
            self.placedPrice = self.currentRate
            Noperation = StrategyOperation(strategy=self, operID=order_id, type="buy")
            Noperation.save()
        self.save()
        return check

    def vender(self):
        if self.protectedTrade:
            check, order_id = self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                instrument_id_bingx=self.operSymbolBingx,
                side="sell",
                amount=self.amount,
                leverage=self.leverage,
                # type="limit", limit_price=self.ema,
                type="market",
                stop_lose_kind="percent", stop_lose_value=self.stopLoss,
                use_trail_stop=True)
            self.placedPrice = self.ema
        else:
            check, order_id = self.buy_order(
                instrument_type="crypto",
                instrument_id=self.operSymbol,
                instrument_id_bingx=self.operSymbolBingx,
                side="sell",
                amount=self.amount,
                leverage=self.leverage,
                type="market")
        if check:
            self.operID = order_id
            self.placedPrice = self.currentRate
            Noperation = StrategyOperation(strategy=self, operID=order_id, type="sell")
            Noperation.save()
        self.save()
        return check

    # ── CIERRE Y CONTABILIDAD ───────────────────────────────────────────────
    def cerrar(self, reasonClose, forceClose):
        checkClose, orderIDClose = self.close_position(self.operID)
        if checkClose or forceClose:
            time.sleep(1)
            self.placedPrice = 0
            if not forceClose:
                self.operIDclose = orderIDClose
            check, position = self.get_position(self.operID)
            beneficio = position['position']['sell_amount'] - position['position']['buy_amount']
            self.beneficioTotal = (self.beneficioTotal or 0) + beneficio
            profit = beneficio*100/self.bet
            Noperation = StrategyOperation.objects.filter(operID__exact=self.operID)
            Noperation[0].close(float(beneficio),
                                float(position['position']['buy_amount']),
                                float(position['position']['sell_amount']),
                                reasonClose,
                                orderIDClose,
                                profit)

            # Update max margin accordingly
            adminUser = User.objects.filter(username='admin')
            for user in adminUser:
                adminId = user.id
                adminProfile = Profile.objects.filter(user=adminId)
                for profile in adminProfile:
                    maxBalance = profile.configMaxBet
                    profile.configMaxBet = (float)(maxBalance) + beneficio
                    profile.save()

        self.operID = 0
        self.operIDclose = 0
        self.bet = 0
        self.save()
        return checkClose or forceClose

    # ── FILTRO MACRO ─────────────────────────────────────────────────────────
    def checkRecommend(self):
        resultado = False
        recomendacionTV = self.recommendMA + self.recommendMA240
        ## Resultado por defecto False
        ## recomendacionTV es la suma de recommendMA y recommendMA240
        ## La suma debe ser mayor a 1, en la direccion adecuada
        ## Es decir, como no puede superar 1, al menos deben estar en la misma direccion!

        if (self.diffDI is not None) and (self.limitBuy is not None) and (self.diffDI > self.limitBuy):
            # Comprar
            if recomendacionTV > 1.5:
                resultado = True

        if (self.diffDI is not None) and (self.limitSell is not None) and (self.diffDI < self.limitSell):
            # Vender
            if recomendacionTV < -1.5:
                resultado = True

        return resultado


# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY STATE 
# ──────────────────────────────────────────────────────────────────────────────
class StrategyState(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    operID = models.IntegerField(null=True)
    accion = models.CharField(max_length=10, null=True)

    class StrategyStateStates(models.IntegerChoices):
        HOLD = 0
        PREOPER = 1
        OPER = 2
        PRECIERRE = 3

    estado = models.IntegerField(choices=StrategyStateStates.choices, null=True)
    ema = models.FloatField(null=True)
    ema20 = models.FloatField(null=True)
    ema100 = models.FloatField(null=True)
    adx = models.FloatField(null=True)
    plusDI = models.FloatField(null=True)
    minusDI = models.FloatField(null=True)
    diffDI = models.FloatField(null=True)
    currentRate = models.FloatField(null=True)
    currentProfit = models.FloatField(null=True)
    maxCurrentRate = models.FloatField(null=True)
    stopLoss = models.FloatField(null=True)
    sleep = models.IntegerField(null=True)
    amount = models.IntegerField(null=True)
    beneficioTotal = models.FloatField(null=True)
    limitOpen = models.IntegerField(null=True)
    limitClose = models.IntegerField(null=True)
    limitBuy = models.IntegerField(null=True)
    limitSell = models.IntegerField(null=True)
    cryptoTimeframeADX = models.CharField(max_length=4, null=True)
    cryptoTimeframeDI = models.CharField(max_length=4, null=True)
    isRunning = models.BooleanField(null=True)
    recommendMA = models.FloatField(default=0, null=True, blank=True)
    recommendMA240 = models.FloatField(default=0, null=True, blank=True)
    stopLossCurrent = models.FloatField(null=True, blank=True)
    atr = models.FloatField(null=True, blank=True) # ATR actual
    
    def __str__(self):
        return str(self.strategy.utility + ":" + str(self.timestamp))


# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY OPERATION 
# ──────────────────────────────────────────────────────────────────────────────
class StrategyOperation(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    operID = models.IntegerField()
    type = models.CharField(max_length=4)
    timestampOpen = models.DateTimeField(auto_now=False, auto_now_add=True)
    timestampClose = models.DateTimeField(auto_now=False, auto_now_add=False, null=True, blank=True)
    beneficio = models.FloatField(null=True, blank=True)
    buyAmount = models.FloatField(null=True)
    sellAmount = models.FloatField(null=True, blank=True)
    reasonClose = models.CharField(max_length=128, null=True, blank=True)
    operIDClose = models.IntegerField(null=True)
    profit = models.FloatField(null=True, blank=True)

    def __str__(self):
        return str(self.strategy.utility + ":" + str(self.operID))

    def close(self, beneficio, buyAmount, sellAmount, reasonClose, operIDClose, profit):
        self.timestampClose = timezone.now()
        self.beneficio = beneficio
        self.buyAmount = buyAmount
        self.sellAmount = sellAmount
        self.reasonClose = reasonClose
        self.operIDClose = operIDClose
        self.profit = profit
        self.save()

    def getHistory(self):
        history = self.strategy.getHistory()
        startTS = self.strategy.getHistory().exclude(timestamp__gt=self.timestampOpen).order_by('-timestamp')[:20].aggregate(Min('timestamp'))['timestamp__min']

        if startTS:
            history = history.filter(timestamp__gt=startTS)

        if self.timestampClose:
            endTS = self.strategy.getHistory().filter(timestamp__gte=self.timestampClose).order_by('timestamp')[:20].aggregate(Max('timestamp'))['timestamp__max']
            history = history.exclude(timestamp__gt=endTS)

        return history

    def getStrategy(self):
        return self.strategy

    def deleteOperation(self):
        # Clear History
        history = self.strategy.getHistory()
        history = history.filter(timestamp__gte=self.timestampOpen)
        if self.timestampClose:
            history = history.exclude(timestamp__gt=self.timestampClose)

        for entry in history:
            entry.accion = "WAIT"
            entry.currentProfit = 0
            entry.save()

        if self.beneficio:
            self.strategy.beneficioTotal = (self.strategy.beneficioTotal or 0) - self.beneficio
            self.strategy.save()

        # Update Strategy beneficioTotal
        
        # Self.delete
# ──────────────────────────────────────────────────────────────────────────────
# USER PROFILE 
# ──────────────────────────────────────────────────────────────────────────────
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    timezoneChoices = [(x, x) for x in pytz.common_timezones]
    timezone = models.CharField(
        max_length=100,
        choices=timezoneChoices,
    )
    configMaxBet = models.DecimalField(default=0, max_digits=14, decimal_places=2)
    configProcessEnabled = models.BooleanField(default=False)
    configTest = models.BooleanField(default=False)

    configGlobalTPEnabled = models.BooleanField(default=True)
    configGlobalTPThreshold = models.DecimalField(default=0, max_digits=5, decimal_places=2)
    configGlobalTPSleepdown = models.IntegerField(default=100)
    configGlobalTPWakeUp = models.DateTimeField(auto_now=False, auto_now_add=False, null=True)

    configLegacyGraph = models.BooleanField(default=True)

    def __str__(self):
        return (self.user.username)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()