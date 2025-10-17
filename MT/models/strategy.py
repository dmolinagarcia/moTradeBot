# -*- coding: utf-8 -*-
from django.db import models

from .strategyOperation import StrategyOperation
from .strategyState import StrategyState
from .lib.moTradeError import MoTradeError
from .lib.helpers import D as _D
from .lib.helpers import to_roll_date as _to_roll_date
from .lib.helpers import compute_atr_wilder as _compute_atr_wilder
from .lib.api     import get_position, get_indicator, buy_order

from django.utils import timezone
from decimal import Decimal

import requests
import json
import time
import logging
import threading
import sys
from datetime import datetime, timedelta
import traceback
import logging

logger = logging.getLogger("MT.models")

# ──────────────────────────────────────────────────────────────────────────────
# Parámetros mejorados de gestión (seguros por defecteo)
# ──────────────────────────────────────────────────────────────────────────────
# TODO. Esto deben ser opciones!
ATR_MULT_SL = Decimal("2.0")        # Stop inicial: 2xATR
ATR_MULT_TSL = Decimal("2.5")       # Trailing: 2.5xATR desde el extremo
TP1_R_MULT = Decimal("1.0")         # (lógico) Toma parcial en 1R (marcado por flag)
BREAKEVEN_R = Decimal("0.7")        # Mover a BE a partir de 0.7R
MAX_BARS_IN_TRADE = 240             # Time-stop en nº de velas
ADX_MIN_DEFAULT = Decimal("0")      # Conserva tu filtro existente via limitOpen
VOL_MIN_PCT = Decimal("2.0")        # Volatilidad mínima (ATR% del precio) para operar
RISK_PCT = Decimal("0.0150")        # Riesgo por operación (0.75% del equity)

# ──────────────────────────────────────────────────────────────────────────────
# STRATEGY
# ──────────────────────────────────────────────────────────────────────────────
class Strategy(models.Model):

    # ── MÉTODOS DE ESTADO / UI ────────────────────────────────────────────────
    def status(self):
        statusUtility = (
            "<u><b>"
            + self.utility
            + str(self.cryptoTimeframeADX or "|1d")
            + str(self.cryptoTimeframeDI or "|1d")
            + "</b></u> \n"
        )
        if self.accion == "VENDER":
            statusOperation = "VENDER"
        elif self.accion == "COMPRAR":
            statusOperation = "COMPRAR"
        else:
            statusOperation = ""
        profit = self.currentProfit if self.currentProfit is not None else 0
        return statusUtility + " " + statusOperation + " " + f"{profit:3.2f}" + "%"

    # ── INTERFAZ CON EL SERVICIO LOCAL (sin cambios funcionales) ─────────────

    def close_position(self, order_id):
        data = {"order_id": order_id, "instrument_id_bingx": self.operSymbolBingx}

        headers = {"Content-Type": "application/json"}
        response = requests.post(
            "http://127.0.0.1:5000/close_position", headers=headers, data=json.dumps(data)
        )

        # no probado, con BINGX devuelvo el ID de orden de cierre
        return response.json()[0], response.json()[1]

    def cancel_order(self, order_id):
        data = '{"order_id": ' + str(order_id) + " }"
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            "http://127.0.0.1:5000/cancel_order", headers=headers, data=data
        )
        return response.json()

    # ── Obtener velas de los datos locales ───────────────────────────────────
    def get_candle(
        self,
        limit=200,
        timeframe="1d",
        with_atr=False,
        atr_period=14,
        session_offset_minutes=0,
    ):
        """
        Genera velas desde StrategyState (muestras 10m) SIN llamar a ningún endpoint
        externo.

        Parámetros:
          - limit: nº de velas a devolver (por defecto 200)
          - timeframe: sólo "1d" está soportado aquí
          - with_atr: si True, añade clave 'atr' en cada vela (Wilder)
          - atr_period: periodo del ATR
          - session_offset_minutes: desplaza el rollover diario (0 = UTC puro)

        Devuelve:
          Lista de velas en orden ASC:
          [{"time":"YYYY-mm-ddT00:00:00Z","open":..,"high":..,"low":..,"close":..,
            "atr":..?}, ...]
        """

        if timeframe.lower() != "1d":
            # Puedes ampliar a 1h/4h si lo necesitas; por ahora forzamos 1d
            timeframe = "1d"

        # Para tener margen para ATR, lee días extra
        days_needed = int(limit) + int(atr_period) + 5
        start_dt = timezone.now() - timedelta(days=days_needed)

        # Lee tus muestras (cada 10 min) de ESTA estrategia
        qs = (
            StrategyState.objects.filter(strategy=self, timestamp__gte=start_dt)
            .exclude(currentRate__isnull=True)
            .order_by("timestamp")
            .values("timestamp", "currentRate")
        )

        # Agregación diaria
        daily_map = {}  # key: date  → dict con o/h/l/c
        for row in qs.iterator():
            ts = row["timestamp"]
            px = float(row["currentRate"])
            dkey = _to_roll_date(ts, offset_minutes=session_offset_minutes)
            if dkey is None:
                continue
            if dkey not in daily_map:
                daily_map[dkey] = {"open": px, "high": px, "low": px, "close": px}
            else:
                rec = daily_map[dkey]
                # open es el primero del día (no cambia)
                rec["high"] = max(rec["high"], px)
                rec["low"] = min(rec["low"], px)
                rec["close"] = px  # último del día

        # Ordena por fecha ASC y forma velas
        days_sorted = sorted(daily_map.keys())
        candles = [
            {
                "time": f"{d.isoformat()}T00:00:00Z",
                "open": float(daily_map[d]["open"]),
                "high": float(daily_map[d]["high"]),
                "low": float(daily_map[d]["low"]),
                "close": float(daily_map[d]["close"]),
            }
            for d in days_sorted
        ]

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
        auto_now=False, auto_now_add=False, null=True, default=timezone.now
    )
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

    estado = models.IntegerField(choices=StrategyStates.choices, null=True, default=0)
    ema = models.FloatField(null=True, blank=True)
    ema20 = models.FloatField(null=True, blank=True)
    ema100 = models.FloatField(null=True, blank=True)
    adx = models.FloatField(null=True, blank=True)
    plusDI = models.FloatField(null=True, blank=True)
    minusDI = models.FloatField(null=True, blank=True)
    currentRate = models.FloatField(null=True, blank=True)
    maxCurrentRate = models.FloatField(null=True, blank=True)
    stopLoss = models.FloatField(null=True)
    stopLossCurrent = models.FloatField(null=True, blank=True)
    takeProfitCurrent = models.FloatField(null=True, blank=True)
    sleep = models.IntegerField(null=True)
    cooldownUntil = models.DateTimeField(
        auto_now=False, auto_now_add=False, null=True, default=timezone.now
    )
    amount = models.IntegerField(null=True)
    beneficioTotal = models.FloatField(null=True, default=0, blank=True)
    limitOpen = models.IntegerField(null=True)
    limitClose = models.IntegerField(null=True)
    adxClose = models.IntegerField(null=True, default=0)
    limitBuy = models.IntegerField(null=False, default=15)
    limitSell = models.IntegerField(null=False, default=-25)
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
        return (
            self.utility
            + str(self.cryptoTimeframeADX or "|1d")
            + str(self.cryptoTimeframeDI or "|1d")
        )

    # ── MODIFICADORES ────────────────────────────────────────────────────────
    def clear(self):
        self.beneficioTotal = 0
        self.takeProfitCurrent = None
        self.stopLossCurrent = None
        self.currentProfit = None
        self.isRunning = True
        self.operID = 0
        self.estado = 3
        self.accion = "COOLDOWN"
        self.maxCurrentRate = 0
        self.nextUpdate = timezone.now()
        self.bet = 0
        self.comments = ""
        self.cooldownUntil = timezone.now()
        self.save()
        self.getOperations().delete()
        # Clear status from operations
        for state in StrategyState.objects.filter(strategy=self):
            state.clear()
        # Mantenemos histórico,

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
        return StrategyState.objects.filter(strategy=self).order_by("timestamp")

    def getOperations(self):
        return StrategyOperation.objects.filter(strategy=self)

    def getComments(self):
        return self.comments

    # ── Operation ────────────────────────────────────────────────────────────
    def update(self):

        total_count, indicators = get_indicator(self.tickSymbol, 
                                                self.cryptoTimeframeDI, 
                                                self.cryptoTimeframeADX )

        if total_count == 0:
            raise MoTradeError(3, "MOT-00201: No data from TradingView for " + self.rateSymbol)

        try:
            self.adx = indicators[0]
            self.plusDI = indicators[1]
            self.minusDI = indicators[2]
            self.ema = indicators[3]
            self.ema20 = indicators[4]
            self.ema100 = indicators[5]
            self.recommendMA = indicators[6]
            self.recommendMA240 = indicators[7]

            # --- ATR desde tus propias muestras (StrategyState) ---
            try:
                candles = self.get_candle(
                    limit=200,
                    timeframe=self.cryptoTimeframeADX or "1d",
                    with_atr=True,
                    atr_period=14,
                    session_offset_minutes=0,
                )

                if not candles or candles[-1].get("atr") is None:
                    logger.warning(
                        str(self.rateSymbol)
                        + ": No se pudo calcular ATR desde StrategyState "
                        + "(ultima ATR=None)."
                    )
                    self.atr = (self.currentRate or 0) * 0.05
                else:
                    self.atr = float(candles[-1]["atr"])

            except Exception as e:
                logger.warning(
                    str(self.rateSymbol) + ": No se pudo calcular ATR desde StrategyState: %s",
                    e,
                )
                # valor por defecto si no se puede calcular ATR
                self.atr = self.currentRate * 0.05

        except Exception as e:
            logger.error(
                str(self.rateSymbol) + ": Error al leer datos de tradingview: %s", e
            )
            logger.error(response.content)
            raise e

        data = {"instrument_id_bingx": self.operSymbolBingx}
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            "http://127.0.0.1:5000/get_price", headers=headers, data=json.dumps(data)
        )

        resp_json = response.json()

        if float(resp_json["price"]) > -1:
            self.currentRate = float(resp_json["price"])
        else:
            logger.error(str(self.rateSymbol) + ": No se ha podido obtener el precio")

        self.nextUpdate = timezone.now() + timedelta(seconds=self.sleep)
        self.save()

    # ── LÓGICA PRINCIPAL ─────────────────────────────────────────────────────
    def operation(self, isMarketOpen):
        logger.debug(str(self.rateSymbol) + ": Entering operation")

        try:
            # Sanity Checks

            if self.estado == 2 and self.operID == 0:
                raise MoTradeError(
                    1, "MOT-00101: Open operation without operID at " + self.rateSymbol
                )

            if self.estado == 2 and self.bet == 0:
                raise MoTradeError(
                    2, "MOT-00102: Bet can't be zero with an open operation at "
                    + self.rateSymbol
                )

            if self.protectedTrade:
                raise MoTradeError(
                    2, "MOT-00103: Protected Trade not implemented in API! For "
                    + self.rateSymbol
                )

            if self.cooldownUntil is None:
                self.cooldownUntil = timezone.now()

            self.update()

            if self.isRunning:
                logger.debug(str(self.rateSymbol) + ":   Symbol is running so we evaluate")
                estadoNext = self.estado

                # ── PROTECTED TRADE: conserva tu lógica anterior (mínimo cambio) ──
                if self.protectedTrade:
                    logger.debug(
                        str(self.rateSymbol) + ":     Symbol is in protected trading mode"
                    )
                    ## Inicio proceso protected Trade
                    if self.estado == 0:
                        ## Estado HOLD.
                        self.maxCurrentRate = 0
                        self.accion = "WAIT"
                        ## Abrimos si el ADX está por encima del mínimo limitOpen

                        if self.adx > self.limitOpen:
                            if ( self.plusDI - self.minusDI ) > self.limitBuy:
                                check = self.placeOrder("buy")
                                if check:
                                    estadoNext = 2
                                    self.currentProfit = 0
                                    self.bet = self.amount
                                    self.maxCurrentRate = self.currentRate
                            if ( self.plusDI - self.minusDI ) < self.limitSell:
                                check = self.placeOrder("sell")
                                if check:
                                    estadoNext = 2
                                    self.currentProfit = 0
                                    self.bet = self.amount
                                    self.maxCurrentRate = self.currentRate
                    if self.estado == 2:
                        check, position = get_position(self.operID, 
                                                       self.operIDclose, 
                                                       self.operSymbolBingx)
                        if check:
                            # La orden se ha ejecutado
                            self.currentProfit = round(
                                (position["position"]["currentProfit"] / (self.bet or 1))
                                * 100,
                                2,
                            )
                            if (
                                position["position"]["sell_amount"] == 0
                                or position["position"]["buy_amount"] == 0
                            ):
                                # Y la orden sigue abierta
                                if position["orders"][0]["side"] == "sell":
                                    self.accion = "VENDER"
                                    if self.currentRate < self.maxCurrentRate:
                                        self.maxCurrentRate = self.currentRate
                                else:
                                    self.accion = "COMPRAR"
                                    if self.currentRate > self.maxCurrentRate:
                                        self.maxCurrentRate = self.currentRate
                            else:
                                # Y la orden se ha cerrado
                                estadoNext = 0
                                self.sleep = 60
                                self.placedPrice = 0
                                self.accion = "CERRAR"
                                beneficio = (
                                    position["position"]["sell_amount"]
                                    - position["position"]["buy_amount"]
                                )
                                profit = beneficio * 100 / self.bet
                                self.beneficioTotal = self.beneficioTotal + beneficio
                                Noperation = StrategyOperation.objects.filter(
                                    operID__exact=self.operID
                                )
                                Noperation[0].close(
                                    float(beneficio),
                                    float(position["position"]["buy_amount"]),
                                    float(position["position"]["sell_amount"]),
                                    "AUTO",
                                    0,  ## Cuanto hace que esto no funciona?
                                    profit,
                                )
                                self.operID = 0
                                self.bet = 0
                        else:
                            check = self.cancel_order(self.operID)
                            if check:
                                estadoNext = 0
                                self.sleep = 60
                                self.accion = "WAIT"
                                StrategyOperation.objects.filter(
                                    operID=self.operID
                                ).delete()
                                self.operID = 0
                ## Fin de protected trade

                # ── MODO NORMAL: lógica mejorada (ATR, sizing, trailing, time-stop) ──
                else:
                    logger.debug(
                        str(self.rateSymbol) + ":     Symbol is in normal operation mode"
                    )
                    if self.estado == 0:  # HOLD
                        logger.debug(
                            str(self.rateSymbol)
                            + ":       Symbol is in HOLD status. Evaluate entry "
                            + "conditions... "
                        )
                        self.currentProfit = None
                        self.maxCurrentRate = 0
                        self.accion = "WAIT"

                        # Filtros de entrada
                        ## Primero hay que entrar por el limitOpen. ADX debe ser superior
                        ## en caso contrario no entramos

                        if self.adx > self.limitOpen:
                            logger.debug(
                                str(self.rateSymbol)
                                + ":         - ADX > limitOpen (%s > %s)",
                                self.adx,
                                self.limitOpen,
                            )
                            # Señal direccional junto a TV Recommend
                            ## Despues, el diffDI debe superar el limitBuy o el limitSell
                            ## self.checkRecommend tiene en cuenta la recomendacion general
                            ## de TV
                            ## isMarketOpen comprueba si el nasdaq esta abierto
                            ## Busca limitar ante bajo volumen

                            side = None
                            if (
                                (( self.plusDI - self.minusDI ) > self.limitBuy)
                                and self.checkRecommend()
                                and isMarketOpen
                            ):
                                side = "buy"
                            if (
                                (( self.plusDI - self.minusDI ) < self.limitSell)
                                and self.checkRecommend()
                                and isMarketOpen
                            ):
                                side = "sell"
                            logger.debug(
                                str(self.rateSymbol) + ":         - Side evaluated to %s",
                                side,
                            )
                            logger.debug(
                                str(self.rateSymbol)
                                + ":          > diffDI=%s, limitBuy=%s, limitSell=%s, "
                                + "Recommend=%s, MarketOpen=%s",
                                self.plusDI - self.minusDI,
                                self.limitBuy,
                                self.limitSell,
                                self.checkRecommend(),
                                isMarketOpen,
                            )

                            # Volatilidad mínima (ATR% del precio)
                            vol_ok = False
                            if self.atr and self.currentRate:
                                atr_pct = _D(self.atr) * Decimal("100") / _D(self.currentRate)
                                vol_ok = atr_pct >= VOL_MIN_PCT
                            logger.debug(
                                str(self.rateSymbol)
                                + ":         - Volatility ok is %s (atr_pct=%s, min=%s)",
                                vol_ok,
                                atr_pct if self.atr else None,
                                VOL_MIN_PCT,
                            )

                            if side and vol_ok:
                                # --- Sizing por riesgo (amount en MONEDA / NO en unidades) ---
                                equity = Decimal("10000")
                                try:
                                    from django.contrib.auth.models import User

                                    adminUser = User.objects.filter(
                                        username="admin"
                                    ).first()
                                    if adminUser:
                                        equity = Decimal(
                                            str(adminUser.profile.configMaxBet)
                                        )
                                except Exception:
                                    pass
                                logger.debug(
                                    str(self.rateSymbol)
                                    + ":             - Equity for sizing: %s",
                                    equity,
                                )

                                logger.debug(
                                    str(self.rateSymbol)
                                    + ":             - Entering amount calculation..."
                                )
                                # Distancia de stop por ATR (en precio)
                                amount_calc = 0
                                if self.atr and self.currentRate and self.atr > 0:
                                    atr_d = _D(self.atr)
                                    entry = _D(self.currentRate)
                                    stop_dist = ATR_MULT_SL * atr_d
                                    logger.debug(
                                        str(self.rateSymbol)
                                        + ":               - ATR=%s, entry=%s, stop_dist=%s",
                                        atr_d,
                                        entry,
                                        stop_dist,
                                    )

                                    if stop_dist > 0 and entry and entry > 0:
                                        risk_amount = equity * RISK_PCT
                                        logger.debug(
                                            str(self.rateSymbol)
                                            + ":               - - Risk amount per trade: "
                                            + "%s (%.2f%% of equity)",
                                            risk_amount,
                                            RISK_PCT * 100,
                                        )

                                        # NOCIONAL que hace que la pérdida ~ risk_amount
                                        # si el precio recorre stop_dist
                                        # amount_notional = units * entry
                                        #                   = (risk_amount/stop_dist) * entry
                                        amount_notional = (
                                            (risk_amount * entry)
                                            / stop_dist
                                            / Decimal(str(self.leverage or 1))
                                        )
                                        logger.debug(
                                            str(self.rateSymbol)
                                            + ":               - - Calculated notional "
                                            + "amount: %s",
                                            amount_notional,
                                        )

                                        # Redondeo a entero para mantener compatibilidad
                                        # con IntegerField
                                        amount_calc = int(max(amount_notional, 0))
                                else:
                                    # Fallback: sin ATR válido usamos el amount ya
                                    # configurado
                                    amount_calc = int(self.amount or 0)
                                logger.debug(
                                    str(self.rateSymbol)
                                    + ":               - Calculated amount for entry: %s",
                                    amount_calc,
                                )

                                if amount_calc > 0:
                                    # IMPORTANTE: fija amount/bet ANTES de enviar la orden
                                    # (buy_order usa self.amount)
                                    self.amount = amount_calc

                                    # Abrimos con orden de mercado
                                    check = self.placeOrder(side)

                                    if check:
                                        self.bet = amount_calc
                                        self.maxCurrentRate = self.currentRate
                                        self.accion = (
                                            "COMPRAR" if side == "buy" else "VENDER"
                                        )
                                        self.currentProfit = 0
                                        estadoNext = 2
                                        self.adxClose = self.limitClose

                                        # SL/TP iniciales en % usando ATR
                                        entry = _D(self.currentRate)
                                        if self.atr and entry and entry > 0:
                                            stop_init = ATR_MULT_SL * _D(self.atr)
                                            # >>> Cambios: SL/TP por PRECIO <<<
                                            if self.accion == "COMPRAR":
                                                sl_price = entry - stop_init
                                                tp_price = entry + ( stop_init * Decimal("2")  )
                                            else:
                                                sl_price = entry + stop_init
                                                tp_price = entry - ( stop_init * Decimal("2")  )
                                            self.stopLossCurrent = float(sl_price)
                                            self.takeProfitCurrent = float(tp_price)
                                            # conservar valor inicial (no usado en
                                            # comparaciones)
                                            self.stopLoss = self.stopLossCurrent
                                        logger.debug(
                                            str(self.rateSymbol)
                                            + ":               - Entry order placed "
                                            + "successfully, operID=%s",
                                            self.operID,
                                        )
                                        logger.debug(
                                            str(self.rateSymbol)
                                            + ":               - Amount=%s, SL=%.6f, "
                                            + "TP=%.6f",
                                            self.amount,
                                            self.stopLossCurrent or 0,
                                            self.takeProfitCurrent or 0,
                                        )
                        else:
                            logger.debug(
                                str(self.rateSymbol)
                                + ":           - ADX <= limitOpen (%s <= %s), no entry",
                                self.adx,
                                self.limitOpen,
                            )

                    if self.estado == 2:  # OPER
                        logger.debug(
                            str(self.rateSymbol)
                            + ":       Symbol is in operation status (normal mode)"
                        )
                        # Estamos en OPERACION NOT PROTECTED
                        # Setup INICIAL
                        force = False
                        reason = []

                        # Obtener estado de posicion
                        check, position = get_position(self.operID, 
                                                       self.operIDclose, 
                                                       self.operSymbolBingx)
                        if check:
                            # if position['position']['close_at'] > 0 :
                            # para IQoption, close_at is not None, pero nunca mas lo
                            # usaremos.
                            if position["position"]["currentProfit"] == -9999:
                                # Esta fealdad la puedo sustituir por el retorno
                                # isPositionOpen
                                ## la posicion está cerrada
                                reason.append("notOpen")
                                self.cooldownUntil = timezone.now() + timedelta(days=2)
                                self.operIDclose = position["position"]["orderIDClose"]
                                force = True
                            else:
                                self.currentProfit = round(
                                    (position["position"]["currentProfit"] / self.bet)
                                    * 100,
                                    2,
                                )

                        # Tenemos el currentProfit y los SL y TP, pero primero calculamos
                        # si hay que cerrar, antes de ejecutar
                        # Trailing por ADX/DI (tus reglas) + ATR (mejora)
                        # Ajuste dinámico ADXClose
                        if (self.adx * 0.85) > self.adxClose:
                            self.adxClose = self.adx * 0.85
                        if self.limitClose == 0:
                            self.adxClose = 0

                        # Señal de cierre por ADX débil
                        if self.adx < self.adxClose:
                            reason.append("limitClose")

                        # Actualiza extremos y trailing en precio con ATR
                        if self.accion == "VENDER":
                            if self.currentRate < self.maxCurrentRate:
                                self.maxCurrentRate = self.currentRate
                            # Reversión de momentum en short
                            if (self.plusDI - self.minusDI) > self.limitSell * 0.85:
                                reason.append("limitSell")
                        else:
                            if self.currentRate > self.maxCurrentRate:
                                self.maxCurrentRate = self.currentRate
                            # Reversión de momentum en long
                            if (self.plusDI - self.minusDI) < self.limitBuy * 0.85:
                                reason.append("limitBuy")

                        # BE y trailing por ATR en % (si tenemos ATR)
                        # Ajustes de SL y TP de GPT
                        # Pero, si force=True.... se ha cerrado y todo esto falla. Saltarlo!
                        if not force:

                            logger.debug(
                                str(self.rateSymbol)
                                + ":         - Adjusting SL/TP dynamically with ATR..."
                            )
    
                            # Mi stop init es 2x ATR. Es mucho!
                            stop_init = ATR_MULT_SL * _D(self.atr)
    
                            r_unity = (
                                stop_init / _D(self.placedPrice) * _D(self.leverage)
                            )  # riesgo en unidad (1R = riesgo inicial)
    
                            pnl_r_est = (
                                _D(self.currentRate - self.placedPrice) / stop_init
                                if self.accion == "COMPRAR"
                                else ((_D(self.placedPrice) - _D(self.currentRate)) / stop_init)
                            )
                            logger.debug(str(self.rateSymbol) + ":         - Values used in calculation")
                            logger.debug(str(self.rateSymbol) + ":           > stop_init %s", stop_init)
                            logger.debug(
                                str(self.rateSymbol) + ":           > r_unity (es un pct) (%.2f%%)",
                                r_unity * 100,
                            )
                            logger.debug(
                                str(self.rateSymbol) + ":           > pnl_r_est %s", pnl_r_est
                            )
    
                            # --- Break-even unificado (no retrocede SL) ---
                            if pnl_r_est >= BREAKEVEN_R and (self.stopLossCurrent is not None):
                                entry_price = float(self.placedPrice)
                                # dir = +1 para long (COMPRAR), -1 para short (VENDER)
                                dir_ = 1 if self.accion == "COMPRAR" else -1
    
                                # ¿Mover a BE mejora la protección?
                                # Long: mover si SL < entry_price
                                # Short: mover si SL > entry_price
                                should_move_to_be = (
                                    (dir_ == 1 and self.stopLossCurrent < entry_price) or
                                    (dir_ == -1 and self.stopLossCurrent > entry_price)
                                )
    
                                if should_move_to_be:
                                    logger.debug(
                                        "%s: - - BREAKEVEN reached at %.2f%%, moving SL to entry (0%%)",
                                        str(self.rateSymbol),
                                        self.currentProfit,
                                    )
                                    # >>> Cambios: mover SL al PRECIO de entrada (sin retroceder) <<<
                                    self.stopLossCurrent = entry_price
    
                            # Trailing tipo Chandelier (en PRECIO)
                            extreme = _D(
                                self.maxCurrentRate
                                if self.maxCurrentRate is not None
                                else self.currentRate
                            )
                            if self.accion == "COMPRAR":
                                new_stop_price = extreme - stop_init
                                # >>> Actualización en PRECIO (solo hacia arriba)
                                if (self.stopLossCurrent is None) or (
                                    new_stop_price > _D(self.stopLossCurrent)
                                ):
                                    self.stopLossCurrent = float(new_stop_price)
                            else:
                                new_stop_price = extreme + stop_init
                                # >>> Actualización en PRECIO (solo hacia abajo)
                                if (self.stopLossCurrent is None) or (
                                    new_stop_price < _D(self.stopLossCurrent)
                                ):
                                    self.stopLossCurrent = float(new_stop_price)
    
    
                            # >>> TP por PRECIO (2R respecto a entrada; ratchet solo a favor)
                            base_tp = (
                                _D(self.placedPrice) + (stop_init * Decimal("2"))
                                if self.accion == "COMPRAR"
                                else _D(self.placedPrice) - (stop_init * Decimal("2"))
                            )
                            if self.takeProfitCurrent is None:
                                self.takeProfitCurrent = float(base_tp)
                            else:
                                if self.accion == "COMPRAR":
                                    if base_tp > _D(self.takeProfitCurrent):
                                        self.takeProfitCurrent = float(base_tp)
                                else:
                                    if base_tp < _D(self.takeProfitCurrent):
                                        self.takeProfitCurrent = float(base_tp)
    
                            # Reglas de SL/TP gobernadas por recomendación (como tenías)
                            if not self.checkRecommend():
                                # Solo si no es recomendable seguir, evaluamos SL/TP
                                if self.accion == "COMPRAR":
                                    if (
                                        self.stopLossCurrent is not None
                                        and self.currentRate <= self.stopLossCurrent
                                    ):
                                        reason.append("stopLoss")
                                        self.cooldownUntil = (
                                            timezone.now() + timedelta(days=1)
                                        )
                                    if (
                                        self.takeProfitCurrent is not None
                                        and self.currentRate >= self.takeProfitCurrent
                                    ):
                                        reason.append("takeProfit")
                                        self.cooldownUntil = (
                                            timezone.now() + timedelta(days=1)
                                        )
                                else:
                                    if (
                                        self.stopLossCurrent is not None
                                        and self.currentRate >= self.stopLossCurrent
                                    ):
                                        reason.append("stopLoss")
                                        self.cooldownUntil = (
                                            timezone.now() + timedelta(days=1)
                                        )
                                    if (
                                        self.takeProfitCurrent is not None
                                        and self.currentRate <= self.takeProfitCurrent
                                    ):
                                        reason.append("takeProfit")
                                        self.cooldownUntil = (
                                            timezone.now() + timedelta(days=1)
                                        )
    
    #                       if (self.stopLossCurrent is not None):
    #                           ### SL Hugging. Deactivated for same reasons as above
    #                           #IF SL is below currentProfit
    #                           # Stop Loss "Hugging"
    #                           # >>> Desactivado en términos de profit%; mantenemos comentarios
    #                           self.stopLossCurrent = self.stopLossCurrent + 
    #                               ((self.currentProfit - self.stopLossCurrent)*0.002)
    #                           pass
    
    #                           # Time-stop condicional por falta de progreso + BE forzado
    #                           try:
    #                               # Parámetros (ajusta si quieres)
    #                               N_DAYS_STAGNATION = 3                            # nº de velas diarias a esperar
    #                               R_BAND = Decimal("0.3")                          # banda [-0.3R, +0.3R]
    #                               R_BE_THRESH = Decimal("0.7")                     # BE si no se alcanzó +0.7R
    #                               ADX_STAGNATION_MAX = _D(self.limitOpen or 0)     # umbral ADX para "falta de tendencia"
    #
    #                                op = StrategyOperation.objects.filter(strategy=self, operID=self.operID).first()
    #                                if op and self.placedPrice and self.atr:
    #                                    entry = _D(self.placedPrice)
    #                                    atr_d = _D(self.atr)
    #                                    lev   = Decimal(str(self.leverage or 1))
    #                                    stop_init = ATR_MULT_SL * atr_d  # distancia stop en precio (k*ATR)
    #
    #                                    if entry and entry > 0 and stop_init and stop_init > 0:
    #                                        # Días en la operación (por vela diaria real)
    #                                        open_day  = _to_roll_date(op.timestampOpen)
    #                                        today_day = _to_roll_date(timezone.now())
    #                                        days_in_trade = (today_day - open_day).days + 1
    #                                        # Guarda para UI si quieres ver días reales en vez de ticks
    #                                        self.bars_in_trade = days_in_trade
    #
    #                                        # 1R expresado en % sobre el "bet" (margen): R%_bet = (stop_init / entry) * Decimal("100") * lev
    #                                        R_pct_on_bet = (stop_init / entry) * Decimal("100") * lev
    #
    #                                        # PnL actual en R
    #                                        pnl_R = None
    #                                        if R_pct_on_bet > 0 and self.currentProfit is not None:
    #                                            pnl_R = _D(self.currentProfit) / R_pct_on_bet
    #
    #                                        # Máximo R alcanzado usando el extremo registrado
    #                                        side = "short" if self.accion == "VENDER" else "long"
    #                                        extreme_price = _D(self.maxCurrentRate or self.currentRate or self.placedPrice)
    #                                        if side == "long":
    #                                            delta_ext = max(Decimal("0"), (extreme_price - entry))
    #                                        else:
    #                                            delta_ext = max(Decimal("0"), (entry - extreme_price))
    #                                        max_R = (delta_ext / stop_init) * lev  # R sobre bet
    #
    #                                        if days_in_trade >= N_DAYS_STAGNATION:
    #                                            # (a) Cierre por falta de progreso: |pnl_R| <= 0.3R y ADX bajo
    #                                            adx_ok = (self.adx is not None) and (_D(self.adx) < (ADX_STAGNATION_MAX or Decimal("0")))
    #                                            if (pnl_R is not None) and (-R_BAND <= pnl_R <= R_BAND) and adx_ok:
    #                                                reason.append("timeStopNoProgress")
    #
    #                                            # (b) BE forzado: si no alcanzó +0.7R en N días, sube SL a BE
    #                                            if (max_R is not None) and (max_R < R_BE_THRESH):
    #                                                if (self.stopLossCurrent is None) or (self.stopLossCurrent < 0.0):
    #                                                    self.stopLossCurrent = 0.0  # breakeven
    #                                                    # (opcional) marca el motivo para auditoría
    #                                                    # reason.append("forceBE")
    #                            except Exception:
    #                                # No rompas la operativa si algo falla en este bloque auxiliar
    #                                pass

                        # Ejecuta cierre si hay razones
                        if len(reason) > 0:
                            check = self.cerrar(" ".join(reason), force)
                            if check:
                                # payload = {"head": self.__str__(), "body": "Cerrar"}
                                #send_group_notification(group_name="notificame",
                                #    payload=payload, ttl=100000)
                                #telegram_settings = settings.TELEGRAM
                                #bot = telegram.Bot(token=telegram_settings['bot_token'])
                                #bot.send_message(chat_id="@%s" %
                                #    telegram_settings['channel_name'],
                                #    text=self.__str__()+" Cerrar",
                                #    parse_mode=telegram.ParseMode.HTML)
                                self.accion = "CERRAR"
                                estadoNext = 3
                                self.bet = 0
                                self.stopLossCurrent = None
                                self.takeProfitCurrent = None
                                self.currentProfit = None
                                self.adxClose = self.limitClose or 0

                # ── COOLDOWN ──────────────────────────────────────────────────
                if self.estado == 3:
                    logger.debug(str(self.rateSymbol) + ": Symbol is in cooldown mode")
                    self.currentProfit = None
                    ## Si el ADX esta por debajo del OPEN, salimos del cooldown
                    ## Si el limitOpen es 0, no hay cooldown y salimos
                    if self.adx < self.limitOpen or self.limitOpen == 0:
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
            logger.error(
                str(self.rateSymbol)
                + ": Excepcion conocida (%s) en %s: %s",
                e.code,
                self.rateSymbol,
                e.message,
            )
            self.inError = True
            self.save()

        except Exception as e:
            self.inError = True
            self.save()
            logger.exception(
                str(self.rateSymbol) + ": MOT-99999: Excepcion no controlada en "
                + self.rateSymbol
            )

    # ── CIERRE MANUAL (Llamada desde la consola) ───────────────
    def manualClose(self, reason):
        # Used when closed is called from the web console
        self.cooldownUntil = timezone.now() + timedelta(days=1)
        # Cooldown de 48 periodos. Igual que cierre por stoploss

        force = False
        check = self.cerrar(reason, force)
        if check:
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
        StrategyState(
            strategy=self,
            operID=self.operID,
            accion=self.accion,
            estado=self.estado,
            ema=self.ema,
            ema20=self.ema20,
            ema100=self.ema100,
            adx=self.adx,
            plusDI=self.plusDI,
            minusDI=self.minusDI,
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
            takeProfitCurrent=self.takeProfitCurrent,
            atr=self.atr,
        ).save()

    # ── Order placement ──────────────────────────────────────────────────────

    def placeOrder(self, side):
        """
        Calls internal API to place order 
        side: "buy" | "sell"
        """

        logger.debug(side)

        # Common parameters for protected / unprotected
        params = {
            "instrument_type": "crypto",
            "instrument_id": self.operSymbol,
            "instrument_id_bingx": self.operSymbolBingx,
            "side": side,              
            "amount": self.amount,
            "leverage": self.leverage,
            "type": "market",
        }

        # Protected trade (trail + SL %) aditional parmeters
        if self.protectedTrade:
            params.update({
                "stop_lose_kind": "percent",
                "stop_lose_value": self.stopLoss,
                "use_trail_stop": True,
            })
            price_to_save = self.ema
        else:
            price_to_save = self.currentRate

        check, order_id = buy_order(**params)

        if check:
            self.operID = order_id
            self.placedPrice = price_to_save
            StrategyOperation(strategy=self, operID=order_id, type=side).save()

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
                check, position = get_position(self.operID, 
                                               self.operIDclose, 
                                               self.operSymbolBingx)
                sell_amount= position["position"]["sell_amount"]
                buy_amount= position["position"]["buy_amount"]  
                beneficio = (sell_amount - buy_amount)  
            else:
                beneficio = -self.bet  # pérdida total forzada
                sell_amount = 0
                buy_amount = 0
            self.beneficioTotal = (self.beneficioTotal or 0) + beneficio
            profit = beneficio * 100 / self.bet
            Noperation = StrategyOperation.objects.filter(operID__exact=self.operID)
            Noperation[0].close(
                float(beneficio),
                float(position["position"]["buy_amount"]),
                float(position["position"]["sell_amount"]),
                reasonClose,
                orderIDClose,
                profit,
            )

            # Update max margin accordingly
            from django.contrib.auth.models import User
            from .profile import Profile  # ajusta el import según tu estructura

            adminUser = User.objects.filter(username="admin")
            for user in adminUser:
                adminId = user.id
                adminProfile = Profile.objects.filter(user=adminId)
                for profile in adminProfile:
                    maxBalance = profile.configMaxBet
                    profile.configMaxBet = float(maxBalance) + beneficio
                    profile.save()

        self.operID = 0
        self.operIDclose = 0
        self.bet = 0
        self.save()
        return checkClose or forceClose

    # ── FILTRO MACRO ─────────────────────────────────────────────────────────
    def checkRecommend(self):
        recommendTV = self.recommendMA + self.recommendMA240

        # side:  1 if plusDI > minusDI, LONG
        #       -1 if minusDI > plusDI, SHORT 
        #        0 if they match
        
        side = 1 if self.plusDI > self.minusDI else (-1 if self.minusDI > self.plusDI else 0)
        if side == 0:
            return False  # sin dirección

        return (recommendTV * side) > 1.5