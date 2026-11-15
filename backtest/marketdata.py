#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Histórico de mercado para investigar estrategias
------------------------------------------------

Descarga y cachea velas y tasas de funding de los futuros perpetuos USDT-M de
Binance (API pública, sin clave). BingX cotiza prácticamente al mismo precio,
pero su API pública ofrece mucho menos historia.

    python backtest/marketdata.py                  # descarga/actualiza backtest/data
    python backtest/marketdata.py --extended       # añade el universo ampliado
    python backtest/marketdata.py --m15 BTC,ETH,SOL  # velas de 15 min (sltp.py)
    python backtest/marketdata.py --vision ...     # desde el archivo público

Los ficheros se actualizan de forma incremental: sólo se piden las velas nuevas.

La API responde 451 desde algunas regiones (p. ej. servidores en EE. UU.). Con
--vision se descargan los mismos datos de data.binance.vision, el archivo público
de Binance (un zip por mes, y uno por día para el mes en curso; el funding del
mes en curso no está publicado y se toma como cero).
"""

import argparse
import csv
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "https://fapi.binance.com"
VISION = "https://data.binance.vision/data/futures/um"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
START = "2019-09-01"
INTERVAL_MS = {"1d": 86_400_000, "4h": 14_400_000, "1h": 3_600_000, "15m": 900_000}

# Símbolos del bot → contrato de Binance
CORE = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "TRX": "TRXUSDT", "XRP": "XRPUSDT",
    "WLD": "WLDUSDT", "DOGE": "DOGEUSDT", "SOL": "SOLUSDT", "BCH": "BCHUSDT",
    "AVAX": "AVAXUSDT", "ALGO": "ALGOUSDT", "SHIB": "1000SHIBUSDT", "NEAR": "NEARUSDT",
    "FIL": "FILUSDT", "AAVE": "AAVEUSDT", "XLM": "XLMUSDT", "EGLD": "EGLDUSDT",
    "HBAR": "HBARUSDT", "BNB": "BNBUSDT", "RUNE": "RUNEUSDT", "ETC": "ETCUSDT",
    "OP": "OPUSDT", "QNT": "QNTUSDT", "IOTA": "IOTAUSDT", "ADA": "ADAUSDT",
}

# Resto de símbolos que el bot ha operado alguna vez (db.sqlite3.source), para
# comprobar que las conclusiones no dependen de la selección actual
EXTENDED = {
    "LTC": "LTCUSDT", "LINK": "LINKUSDT", "EOS": "EOSUSDT", "DOT": "DOTUSDT",
    "AXS": "AXSUSDT", "SAND": "SANDUSDT", "UNI": "UNIUSDT", "MANA": "MANAUSDT",
    "APE": "APEUSDT", "FLOW": "FLOWUSDT", "MINA": "MINAUSDT", "JASMY": "JASMYUSDT",
    "FET": "FETUSDT", "ASTR": "ASTRUSDT", "STX": "STXUSDT", "TIA": "TIAUSDT",
    "PYTH": "PYTHUSDT", "SUPER": "SUPERUSDT", "OMG": "OMGUSDT", "MATIC": "MATICUSDT",
    "FTM": "FTMUSDT", "BNX": "BNXUSDT", "HIFI": "HIFIUSDT", "AGLD": "AGLDUSDT",
    "BAKE": "BAKEUSDT", "ETHW": "ETHWUSDT",
}


def to_ms(day):
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def get(path, params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 400:  # símbolo inexistente o deslistado
                return None
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(2 * (attempt + 1))


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [tuple(float(x) for x in row) for row in csv.reader(f)]


def write_csv(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp, path)


def update_klines(symbol, interval):
    """Velas cerradas: (apertura ms, open, high, low, close, volumen en USDT)."""
    path = os.path.join(DATA_DIR, f"{symbol}_{interval}.csv")
    rows = read_csv(path)
    start = int(rows[-1][0]) + INTERVAL_MS[interval] if rows else to_ms(START)
    now = int(time.time() * 1000)
    while start < now:
        batch = get("/fapi/v1/klines",
                    {"symbol": symbol, "interval": interval, "startTime": start, "limit": 1500})
        if batch is None:
            return None
        closed = [k for k in batch if int(k[6]) < now]
        rows += [(int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7]))
                 for k in closed]
        if len(batch) < 1500 or len(closed) < len(batch):
            break
        start = int(batch[-1][0]) + INTERVAL_MS[interval]
        time.sleep(0.3)
    write_csv(path, rows)
    return rows


def update_funding(symbol):
    """Tasas de funding: (hora ms, tasa). Positiva: los largos pagan a los cortos."""
    path = os.path.join(DATA_DIR, f"{symbol}_funding.csv")
    rows = read_csv(path)
    start = int(rows[-1][0]) + 1 if rows else to_ms(START)
    while True:
        batch = get("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": start, "limit": 1000})
        if not batch:
            break
        rows += [(int(f["fundingTime"]), float(f["fundingRate"])) for f in batch]
        if len(batch) < 1000:
            break
        start = int(batch[-1]["fundingTime"]) + 1
        time.sleep(0.3)
    write_csv(path, rows)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Archivo público (data.binance.vision)
# ──────────────────────────────────────────────────────────────────────────────
def vision_rows(path):
    """Filas del CSV de un zip del archivo, o [] si no existe."""
    for attempt in range(5):
        try:
            with urllib.request.urlopen(f"{VISION}/{path}", timeout=60) as response:
                data = response.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                text = z.read(z.namelist()[0]).decode()
            # Los ficheros recientes llevan cabecera
            return [r for r in csv.reader(io.StringIO(text)) if r and r[0][:1].isdigit()]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError, zipfile.BadZipFile, ConnectionError):
            if attempt == 4:
                raise
        time.sleep(2 * (attempt + 1))


def vision_periods(start_ms):
    """Meses completos desde start_ms y días del mes en curso: ([YYYY-MM], [YYYY-MM-DD])."""
    today = datetime.now(timezone.utc).date()
    d = datetime.fromtimestamp(start_ms / 1000, timezone.utc).date().replace(day=1)
    months = []
    while (d.year, d.month) < (today.year, today.month):
        months.append(d.strftime("%Y-%m"))
        d = (d + timedelta(days=32)).replace(day=1)
    days = [today.replace(day=k).isoformat() for k in range(1, today.day)]
    # El zip mensual tarda unos días en publicarse: el mes anterior también por días
    if months:
        prev = datetime.strptime(months[-1], "%Y-%m").date()
        while prev.month == int(months[-1][5:]):
            days.append(prev.isoformat())
            prev += timedelta(days=1)
    return months, sorted(days)


def vision_klines(symbol, interval, pool):
    path = os.path.join(DATA_DIR, f"{symbol}_{interval}.csv")
    rows = {int(r[0]): r for r in read_csv(path)}
    start = max(rows) + INTERVAL_MS[interval] if rows else to_ms(START)
    months, days = vision_periods(start)
    files = [f"monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{m}.zip" for m in months]
    got = list(pool.map(vision_rows, files))
    missing = {m for m, g in zip(months, got) if not g}
    files = [f"daily/klines/{symbol}/{interval}/{symbol}-{interval}-{d}.zip"
             for d in days if d[:7] in missing or d[:7] not in months]
    got += list(pool.map(vision_rows, files))
    for batch in got:
        for k in batch:
            t = int(k[0])
            rows[t] = (t, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7]))
    out = [rows[t] for t in sorted(rows)]
    if out:
        write_csv(path, out)
    return out


def vision_funding(symbol, pool):
    path = os.path.join(DATA_DIR, f"{symbol}_funding.csv")
    rows = {int(r[0]): r for r in read_csv(path)}
    months, _ = vision_periods(max(rows) + 1 if rows else to_ms(START))
    files = [f"monthly/fundingRate/{symbol}/{symbol}-fundingRate-{m}.zip" for m in months]
    for batch in pool.map(vision_rows, files):
        for f in batch:
            rows[int(f[0])] = (int(f[0]), float(f[2]))
    out = [rows[t] for t in sorted(rows)]
    write_csv(path, out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extended", action="store_true", help="incluir el universo ampliado")
    ap.add_argument("--hourly", action="store_true", help="velas de 1h del universo principal")
    ap.add_argument("--m15", help="sólo velas de 15 min de estos símbolos (separados por comas)")
    ap.add_argument("--vision", action="store_true",
                    help="descargar de data.binance.vision (si la API está bloqueada por región)")
    args = ap.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)
    global update_klines, update_funding
    if args.vision:
        pool = ThreadPoolExecutor(16)
        update_klines = lambda symbol, interval: vision_klines(symbol, interval, pool)
        update_funding = lambda symbol: vision_funding(symbol, pool)
    if args.m15:
        for name in args.m15.split(","):
            rows = update_klines(CORE[name], "15m")
            print(f"{name:6} {CORE[name]:14} {len(rows)} velas de 15 min")
        return
    universe = {**CORE, **(EXTENDED if args.extended else {})}
    for name, symbol in universe.items():
        daily = update_klines(symbol, "1d")
        if not daily:
            print(f"{name:6} {symbol:14} no disponible en Binance")
            continue
        update_klines(symbol, "4h")
        if args.hourly and name in CORE:
            update_klines(symbol, "1h")
        funding = update_funding(symbol)
        first = datetime.fromtimestamp(daily[0][0] / 1000, timezone.utc).date() if daily else "-"
        last = datetime.fromtimestamp(daily[-1][0] / 1000, timezone.utc).date() if daily else "-"
        print(f"{name:6} {symbol:14} {len(daily):5} días ({first} → {last}), {len(funding)} fundings")


if __name__ == "__main__":
    main()
