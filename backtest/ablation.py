#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ablaciones de la lógica del bot
-------------------------------

Cambia una regla de Strategy.operation() cada vez y mide el efecto frente al bot
actual (con el filtro de régimen de BTC), con el simulador de replay.py sobre la
reconstrucción horaria del bot de research.py (indicadores sobre la vela diaria y
de 4h en curso, como TradingView; ATR de las velas del propio bot).

Marco: capital fijo, riesgo constante por operación, comisiones, deslizamiento,
funding real de Binance y liquidación del margen aislado. Las reglas se eligen
sólo con el periodo de selección (hasta IS_END) y se comprueban en evaluación.

    python3 backtest/marketdata.py --extended --hourly     # histórico (ver --vision)
    python3 backtest/ablation.py                           # una regla cada vez (GROUPS)
    python3 backtest/ablation.py --group trailing          # sólo un grupo
    python3 backtest/ablation.py --combo                   # la propuesta, regla a regla
    python3 backtest/ablation.py --neighbors               # vecinos de la propuesta
    python3 backtest/ablation.py --combo --universe extended   # monedas no usadas al elegir
    python3 backtest/ablation.py --combo --m15             # 7 activas, ciclos de 15 min
    python3 backtest/ablation.py --combo --slippage 0.0015 # sensibilidad a costes

La propuesta (PROPUESTA) acumula las reglas que mejoran el Sharpe del periodo de
selección: sólo largos, stop y trailing a 4 ATR con el tamaño actual, SL sin
condicionar a checkRecommend() y sin volatilidad mínima.

Los límites DI y el apalancamiento de cada símbolo salen de --db (por defecto
db.sqlite3 y, si no existe, db.sqlite3.source); sin dato, limitBuy/limitSell 5/-5
y apalancamiento 4.
"""

import argparse
import heapq
import math
import os
import pickle
import random
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import replace
from multiprocessing import Pool

import indicators as ind
import replay as rp
import research as R

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
EQUITY = 30000
IS_END = "2023-12-31"
ACTIVE = ("BTC", "ETH", "XRP", "DOGE", "SOL", "BNB", "ADA")
COSTS = rp.Costs(slippage=0.0005, funding_8h=0.0, liq_frac=0.9, fill="logged")
BASE = replace(rp.ACTUAL, btc_regime=True)   # el bot desde la 0.1.18


def v(**changes):
    return replace(BASE, **changes)


# Columnas de régimen que load() añade a cada fila (posición en los extras de replay.py)
REGIMES = {"btc200": 0, "btc100": 3, "btc50": 4, "propia200": 5, "btc200+propia200": 6,
           "btc50>200": 7}

# Una regla cada vez. Cada entrada: nombre → (Params, opciones). Opciones: cap = máximo de
# posiciones a la vez; lev = apalancamiento (en lugar del de cada estrategia); order =
# semilla para barajar la prioridad de los símbolos cuando el máximo se alcanza
GROUPS = {
    "stops": {
        "SL siempre (sin condicionar)": (v(sl_gated=False), {}),
        "stop inicial siempre": (v(hard_sl_always=True), {}),
        "TP forzado": (v(tp_gated=False), {}),
        "SL y TP siempre": (v(sl_gated=False, tp_gated=False), {}),
        "sin TP": (v(tp_r=None), {}),
        "TP 3R condicionado": (v(tp_r=3.0), {}),
        "sin break-even": (v(breakeven_r=1e9), {}),
        "break-even a 1R": (v(breakeven_r=1.0), {}),
        "stop 1.5 ATR (mismo tamaño)": (v(atr_mult_sl=1.5, sizing_sl=2.0, tp_r=2.0 * 2 / 1.5), {}),
        "stop 3 ATR (mismo tamaño)": (v(atr_mult_sl=3.0, sizing_sl=2.0, tp_r=2.0 * 2 / 3), {}),
        "stop 4 ATR (mismo tamaño)": (v(atr_mult_sl=4.0, sizing_sl=2.0, tp_r=1.0), {}),
        "trailing 1R>1.5 2R>1.0, SL siempre, sin TP": (
            v(sl_gated=False, tp_r=None, trail_steps=((1.0, 1.5), (2.0, 1.0))), {}),
        "cooldown SL/TP 0 d": (v(cooldown_days=0.0), {}),
        "cooldown SL/TP 3 d": (v(cooldown_days=3.0), {}),
    },
    "salida": {
        "salida DI ×0.5": (v(di_exit_mult=0.5), {}),
        "salida DI en el cruce (×0)": (v(di_exit_mult=0.0), {}),
        "salida DI ×-1 (señal contraria)": (v(di_exit_mult=-1.0), {}),
        "sin salida DI": (v(di_exit=False), {}),
        "salida DI sólo al cierre diario": (v(daily_exit=True), {}),
        "cooldown DI 6 h": (v(cooldown_di_days=0.25), {}),
        "cooldown DI 1 d": (v(cooldown_di_days=1.0), {}),
        "cooldown DI 2 d": (v(cooldown_di_days=2.0), {}),
        "time-stop 5 d sin ganar": (v(max_days=5), {}),
        "time-stop 10 d sin ganar": (v(max_days=10), {}),
    },
    "entrada": {
        "entrada sólo al cierre diario": (v(daily_entry=True), {}),
        "entrada y salida al cierre diario": (v(daily_entry=True, daily_exit=True), {}),
        "ADX > 15": (v(adx_min=15), {}),
        "ADX > 20": (v(adx_min=20), {}),
        "ADX > 25": (v(adx_min=25), {}),
        "ADX > 30": (v(adx_min=30), {}),
        "recommend > 1.0": (v(rec_min=1.0), {}),
        "recommend > 1.2": (v(rec_min=1.2), {}),
        "recommend > 1.7": (v(rec_min=1.7), {}),
        "recommend > 1.85": (v(rec_min=1.85), {}),
        "sin volatilidad mínima": (v(vol_min_pct=0.0), {}),
        "volatilidad mínima 3%": (v(vol_min_pct=3.0), {}),
        "volatilidad mínima 4%": (v(vol_min_pct=4.0), {}),
        "sólo largos": (v(long_only=True), {}),
        "sin filtro BTC": (v(btc_regime=False), {}),
    },
    "recommend": {
        **{f"recommend > {x} (entrada y SL/TP)": (v(rec_min=x), {}) for x in (0.0, 0.5, 0.8, 1.0, 1.2)},
        **{f"recommend > {x} sólo entrada": (v(rec_min=x, rec_gate=1.5), {}) for x in (0.0, 0.5, 1.0)},
        **{f"recommend > {x} sólo SL/TP": (v(rec_gate=x), {}) for x in (0.0, 0.5, 1.0)},
        "recommend > 1.0, SL siempre": (v(rec_min=1.0, sl_gated=False), {}),
        "recommend > 1.0, SL y TP siempre": (v(rec_min=1.0, sl_gated=False, tp_gated=False), {}),
    },
    "trailing": {
        **{f"inicial 2 ATR, trailing {x} ATR": (v(trail_mult=x), {}) for x in (3.0, 4.0, 6.0)},
        **{f"inicial {x} ATR, trailing 2 ATR (mismo tamaño)": (v(atr_mult_sl=x, trail_mult=2.0, sizing_sl=2.0, tp_r=4 / x), {})
           for x in (3.0, 4.0)},
        **{f"stop {x} ATR (mismo tamaño)": (v(atr_mult_sl=x, sizing_sl=2.0, tp_r=4 / x), {}) for x in (3.0, 4.0, 5.0, 6.0, 8.0)},
        **{f"stop {x} ATR, sin TP (mismo tamaño)": (v(atr_mult_sl=x, sizing_sl=2.0, tp_r=None), {}) for x in (3.0, 4.0, 6.0)},
        **{f"stop {x} ATR, 2x (mismo tamaño)": (v(atr_mult_sl=x, sizing_sl=2.0, tp_r=4 / x), {"lev": 2}) for x in (2.0, 4.0, 6.0)},
        "stop 4 ATR, tamaño a 4 ATR": (v(atr_mult_sl=4.0, tp_r=1.0), {}),
    },
    "regimen": {
        **{f"régimen {name}": (v(regime_idx=idx), {}) for name, idx in REGIMES.items() if idx},
        **{f"sólo largos, régimen {name}": (v(regime_idx=idx, long_only=True), {}) for name, idx in REGIMES.items()},
        "sólo largos, sin régimen": (v(btc_regime=False, long_only=True), {}),
    },
    "limites": {
        f"limitBuy/Sell {lb}/{ls}": (v(limits=(lb, ls)), {})
        for lb, ls in ((1, -1), (5, -5), (5, -25), (10, -10), (15, -15), (15, -25), (20, -20),
                       (25, -25), (30, -30))
    },
    "cartera": {
        **{f"máximo {n} posiciones": (BASE, {"cap": n}) for n in (3, 4, 5, 6, 8, 12)},
        **{f"máximo 5 posiciones, orden al azar {k}": (BASE, {"cap": 5, "order": k}) for k in (1, 2, 3)},
        **{f"apalancamiento {x}x": (BASE, {"lev": x}) for x in (2, 3, 5)},
    },
}


# Reglas que mejoran en selección, acumuladas una a una
L = v(long_only=True)
WIDE = replace(L, atr_mult_sl=4.0, sizing_sl=2.0)   # stop y trailing a 4 ATR, tamaño actual; TP a 2R = 8 ATR
PROPUESTA = replace(WIDE, sl_gated=False, vol_min_pct=0.0)
COMBOS = {
    "1) sólo largos": (L, {}),
    "2) + stop y trailing a 4 ATR (TP a 8 ATR)": (WIDE, {}),
    "3) + SL sin condicionar": (replace(WIDE, sl_gated=False), {}),
    "4) + sin volatilidad mínima = PROPUESTA": (PROPUESTA, {}),
    "PROPUESTA, mitad de tamaño (dimensionada a 4 ATR)": (replace(PROPUESTA, sizing_sl=None), {}),
    "PROPUESTA sin TP": (replace(PROPUESTA, tp_r=None), {}),
    "PROPUESTA con cortos": (replace(PROPUESTA, long_only=False), {}),
    "PROPUESTA con cortos a mitad de tamaño": (replace(PROPUESTA, long_only=False, short_risk=0.5), {}),
    "PROPUESTA, apalancamiento 2x": (PROPUESTA, {"lev": 2}),
    "PROPUESTA, apalancamiento 3x": (PROPUESTA, {"lev": 3}),
    "PROPUESTA 3x, margen total ≤ 100%": (PROPUESTA, {"lev": 3, "margin": 1.0}),
    "bot actual, límites 5/-25": (v(limits=(5, -25)), {}),
    "PROPUESTA, límites 5/-25": (replace(PROPUESTA, limits=(5, -25)), {}),
}

# Vecinos de la propuesta: si sólo funciona un valor exacto, es ruido
NEIGHBORS = {
    "PROPUESTA": (PROPUESTA, {}),
    "stop 3 ATR": (replace(PROPUESTA, atr_mult_sl=3.0), {}),
    "stop 5 ATR": (replace(PROPUESTA, atr_mult_sl=5.0), {}),
    "stop 6 ATR": (replace(PROPUESTA, atr_mult_sl=6.0), {}),
    "inicial 2 ATR, trailing 4 ATR": (replace(PROPUESTA, atr_mult_sl=2.0, trail_mult=4.0), {}),
    "TP a 4 ATR": (replace(PROPUESTA, tp_r=1.0), {}),
    "TP a 12 ATR": (replace(PROPUESTA, tp_r=3.0), {}),
    "sin TP": (replace(PROPUESTA, tp_r=None), {}),
    "TP forzado": (replace(PROPUESTA, tp_gated=False), {}),
    "volatilidad mínima 2%": (replace(PROPUESTA, vol_min_pct=2.0), {}),
    "SL condicionado (como hoy)": (replace(PROPUESTA, sl_gated=True), {}),
    "sin break-even": (replace(PROPUESTA, breakeven_r=1e9), {}),
    "recommend > 1.0": (replace(PROPUESTA, rec_min=1.0), {}),
    "recommend > 1.7": (replace(PROPUESTA, rec_min=1.7), {}),
    "sin salida DI": (replace(PROPUESTA, di_exit=False), {}),
    "salida DI en el cruce (×0)": (replace(PROPUESTA, di_exit_mult=0.0), {}),
    "cooldown DI 1 d": (replace(PROPUESTA, cooldown_di_days=1.0), {}),
    "cooldown SL 0 d": (replace(PROPUESTA, cooldown_days=0.0), {}),
    "cooldown SL 3 d": (replace(PROPUESTA, cooldown_days=3.0), {}),
    "limitBuy 5": (replace(PROPUESTA, limits=(5, -25)), {}),
    "limitBuy 10": (replace(PROPUESTA, limits=(10, -25)), {}),
    "limitBuy 15": (replace(PROPUESTA, limits=(15, -25)), {}),
    "limitBuy 25": (replace(PROPUESTA, limits=(25, -25)), {}),
    "ADX > 20": (replace(PROPUESTA, adx_min=20), {}),
    "con cortos": (replace(PROPUESTA, long_only=False), {}),
    "sin filtro BTC": (replace(PROPUESTA, btc_regime=False), {}),
    "régimen BTC > SMA100": (replace(PROPUESTA, regime_idx=REGIMES["btc100"]), {}),
    "máximo 5 posiciones": (PROPUESTA, {"cap": 5}),
    "máximo 8 posiciones": (PROPUESTA, {"cap": 8}),
    "máximo 12 posiciones": (PROPUESTA, {"cap": 12}),
}


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
def bot_config(db):
    for path in (db, os.path.join(HERE, "..", "db.sqlite3"), os.path.join(HERE, "..", "db.sqlite3.source")):
        if path and os.path.exists(path):
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            rows = con.execute("select utility, limitBuy, limitSell, leverage from MT_strategy").fetchall()
            return {u: (lb, ls) for u, lb, ls, _ in rows}, {u: lev for u, _, _, lev in rows}, path
    return {}, {}, None


def load(names, db=None, m15=False):
    """Ciclos del bot por símbolo: {nombre: {rows, t, c, funding, lev}}."""
    os.makedirs(CACHE, exist_ok=True)
    limits, levs, path = bot_config(db)
    tag = "15m" if m15 else "1h"
    data, btc_up = {}, None
    for n in names:
        lim = limits.get(n, (5, -5))
        file = os.path.join(CACHE, f"ablation_{tag}_{n}_{lim[0]}_{lim[1]}.pkl")
        if not os.path.exists(file):
            if btc_up is None:
                btc = R.Series("BTC", R.CORE["BTC"])
                btc_up = {t: c > m for t, c, m in zip(btc.t, btc.c, ind.sma(btc.c, 200))
                          if m is not None}
            s = R.Series(n, {**R.CORE, **R.EXTENDED}[n])
            if m15:
                import sltp
                rows = sltp.bot_rows(s, {n: lim}, btc_up)
            else:
                rows = R.bot_hourly_rows(s, {n: lim}, btc_up)
            with open(file, "wb") as f:
                pickle.dump({"rows": rows, "t": s.t, "c": s.c, "funding": dict(s.funding)}, f,
                            protocol=pickle.HIGHEST_PROTOCOL)
        with open(file, "rb") as f:
            data[n] = pickle.load(f)
        data[n]["lev"] = levs.get(n, 4)
    data = {n: d for n, d in data.items() if d["rows"]}
    add_regimes(data, 900 if m15 else 3600)
    return data, path


def add_regimes(data, step):
    """Añade a cada fila las columnas de REGIMES (+1 / -1 / 0 con el cierre del día anterior)."""
    def sign(t, c, ref):
        return {day: (1 if x > m else -1) for day, x, m in zip(t, c, ref) if m is not None}

    btc = R.Series("BTC", R.CORE["BTC"])
    sma = {k: ind.sma(btc.c, k) for k in (50, 100, 200)}
    btc200, btc100, btc50 = (sign(btc.t, btc.c, sma[k]) for k in (200, 100, 50))
    cross = sign(btc.t, sma[50], sma[200])
    for d in data.values():
        own = sign(d["t"], d["c"], ind.sma(d["c"], 200))
        out = []
        for row in d["rows"]:
            day = int((row[0] - step) // 86400) * R.DAY_MS - R.DAY_MS
            a, b = btc200.get(day, 0), own.get(day, 0)
            out.append(row[:15] + (row[15:17] if len(row) > 15 else (None, None))
                       + (btc100.get(day, 0), btc50.get(day, 0), b, a if a == b else 0,
                          cross.get(day, 0)))
        d["rows"] = out


# ──────────────────────────────────────────────────────────────────────────────
# Simulación
# ──────────────────────────────────────────────────────────────────────────────
DATA = None


def simulate(params, names, cap=None, margin=None, lev=None, order=None):
    """
    Operaciones y P&L diario acumulado por símbolo (con el funding real). Con cap
    (máximo de posiciones) o margin (margen total máximo, en veces el capital) las
    estrategias se intercalan en el tiempo y la apertura que no cabe se descarta.
    """
    results = {}
    levs = {n: lev or DATA[n]["lev"] for n in names}
    if cap is None and margin is None:
        for n in names:
            results[n] = rp.simulate(DATA[n]["rows"], n, levs[n], params, COSTS, EQUITY)
    else:
        bets, count = {}, [0, 0.0]  # nº de posiciones abiertas y margen total

        def gate(sym, side, t, amount):
            return ((cap is None or count[0] < cap)
                    and (margin is None or count[1] + amount <= margin * EQUITY))

        # A igual hora, el bot procesa las estrategias en orden (aquí, el de la lista)
        priority = list(names)
        if order is not None:
            random.Random(order).shuffle(priority)
        its, heap = {}, []
        for k, n in enumerate(priority):
            d = DATA[n]
            its[n] = rp.simulate_iter(d["rows"], n, levs[n], params, COSTS, EQUITY, gate=gate)
            heap.append((d["rows"][0][0], k, n, 0))
        heapq.heapify(heap)
        while heap:
            _, k, n, i = heapq.heappop(heap)
            try:
                _, bet = next(its[n])
            except StopIteration as done:
                results[n] = done.value
                continue
            before = bets.get(n, 0)
            count[0] += (1 if bet else 0) - (1 if before else 0)
            count[1] += bet - before
            bets[n] = bet
            rows = DATA[n]["rows"]
            # Tras la última fila queda un next() pendiente que devuelve el resultado
            heapq.heappush(heap, (rows[i + 1][0] if i + 1 < len(rows) else float("inf"), k, n, i + 1))

    trades, daily = [], {}
    for n in names:
        d = DATA[n]
        tr, curve = results[n]
        index = {t: i for i, t in enumerate(d["t"])}
        funding = defaultdict(float)
        for t in tr:
            t.notional = t.bet * levs[n]
            units = t.notional / t.entry
            paid = 0.0
            for day in range(int(t.t_open * 1000) // R.DAY_MS * R.DAY_MS,
                             int(t.t_close * 1000) // R.DAY_MS * R.DAY_MS, R.DAY_MS):
                i = index.get(day)
                if i is not None:
                    f = t.side * units * d["c"][i] * d["funding"].get(day, 0.0)
                    funding[day] += f
                    paid += f
            t.pnl -= paid
        pnl_at = {hour * 3600 * 1000 // R.DAY_MS * R.DAY_MS: value for hour, value in curve}
        pnl, acc, series = 0.0, 0.0, {}
        for day in range(min(pnl_at), max(pnl_at) + 1, R.DAY_MS):
            pnl = pnl_at.get(day, pnl)
            acc += funding.get(day, 0.0)
            series[day] = pnl - acc
        daily[n] = series
        trades += tr
    return trades, daily


def portfolio_curve(daily, names):
    """Suma el P&L acumulado de varios símbolos arrastrando el último valor."""
    days = sorted({day for n in names for day in daily[n]})
    last, out = {n: 0.0 for n in names}, []
    for day in days:
        for n in names:
            if day in daily[n]:
                last[n] = daily[n][day]
        out.append((day, sum(last.values())))
    return out


def stats(trades, curve, names, start, end):
    a, b = R.day_ms(start) if start else curve[0][0], R.day_ms(end) if end else curve[-1][0]
    pts = [x for day, x in curve if a <= day <= b]
    rets = [(y - x) / EQUITY for x, y in zip(pts, pts[1:])]
    sd = statistics.pstdev(rets)
    peak, dd = pts[0], 0.0
    for x in pts:
        peak = max(peak, x)
        dd = max(dd, peak - x)
    sel = [t for t in trades if t.sym in names and a / 1000 <= t.t_close < b / 1000 + 86400]
    wins = sum(t.pnl for t in sel if t.pnl > 0)
    losses = -sum(t.pnl for t in sel if t.pnl <= 0)
    monthly, prev = defaultdict(float), None
    for day, x in curve:
        if a <= day <= b:
            if prev is not None:
                monthly[R.fmt_day(day)[:7]] += x - prev
            prev = x
    events = sorted([(t.t_open, 1, t.notional) for t in sel] + [(t.t_close, -1, -t.notional) for t in sel])
    count = gross = max_count = max_gross = 0
    for _, k, x in events:
        count, gross = count + k, gross + x
        max_count, max_gross = max(max_count, count), max(max_gross, gross)
    return {"max_pos": max_count, "max_gross": max_gross / EQUITY,
            "pnl": pts[-1] - pts[0], "sharpe": statistics.mean(rets) / sd * math.sqrt(365) if sd else 0.0,
            "dd": dd, "sd": sd, "n": len(sel),
            "win": sum(t.pnl > 0 for t in sel) / len(sel) if sel else 0.0,
            "pf": wins / losses if losses else float("inf"),
            "liq": sum(t.reason == "liquidation" for t in sel),
            "days": statistics.mean((t.t_close - t.t_open) / 86400 for t in sel) if sel else 0.0,
            "fees": sum(COSTS.taker * t.notional * 2 for t in sel),
            "monthly": dict(monthly)}


def evaluate(item):
    label, params, opts, pools = item
    out = {}
    names_all = list(dict.fromkeys(n for names in pools.values() for n in names))
    shared = None if "cap" in opts or "margin" in opts else simulate(params, names_all, **opts)
    for pool, names in pools.items():
        trades, daily = shared or simulate(params, names, **opts)
        curve = portfolio_curve(daily, names)
        out[pool] = [stats(trades, curve, set(names), None, IS_END),
                     stats(trades, curve, set(names), "2024-01-01", None)]
        if pool == next(iter(pools)):
            reasons = defaultdict(lambda: [0, 0.0])
            for t in trades:
                if t.sym in names:
                    r = reasons[t.reason.split()[0]]
                    r[0] += 1
                    r[1] += t.pnl
            out["_reasons"] = dict(reasons)
            out["_by_sym"] = {n: [sum(t.pnl for t in trades if t.sym == n and (t.t_close * 1000 <= R.day_ms(IS_END)) == first)
                                  for first in (True, False)] for n in names}
    return label, out


# ──────────────────────────────────────────────────────────────────────────────
# Informe
# ──────────────────────────────────────────────────────────────────────────────
def cell(st):
    return (f"{st['pnl']:+9,.0f} {st['sharpe']:5.2f} {st['dd']:7,.0f} {st['n']:5d} {st['pf']:5.2f}")


def table(results, labels, pool, title):
    width = max(len(n) for n in labels) + 1
    print(f"\n{title}")
    print(f"  {'':{width}} {'selección (hasta 2023)':^35}   {'evaluación (2024 →)':^35}")
    head = f"{'P&L':>9} {'Shrp':>5} {'maxDD':>7} {'ops':>5} {'PF':>5}"
    print(f"  {'variante':{width}} {head}   {head}  liq  días  comis.  máx.pos  máx.expos.")
    for label in labels:
        a, b = results[label][pool]
        print(f"  {label:{width}} {cell(a)}   {cell(b)}  {a['liq'] + b['liq']:3d} {b['days']:5.1f} "
              f"{a['fees'] + b['fees']:7,.0f}  {max(a['max_pos'], b['max_pos']):7d}  "
              f"{max(a['max_gross'], b['max_gross']):9.1f}x")


def bootstrap(results, base, labels, pool):
    """¿La diferencia en evaluación se distingue del ruido? Remuestreo de meses."""
    rng = random.Random(1)
    print(f"\n  Diferencia de P&L en evaluación frente a «{base}» a igual volatilidad "
          f"(IC 90% remuestreando meses) · {pool}")
    a = results[base][pool][1]
    for label in labels:
        b = results[label][pool][1]
        k = a["sd"] / b["sd"] if b["sd"] else 1.0
        diffs = [k * b["monthly"].get(m, 0.0) - a["monthly"].get(m, 0.0)
                 for m in sorted(set(a["monthly"]) | set(b["monthly"]))]
        sims = sorted(sum(rng.choice(diffs) for _ in diffs) for _ in range(5000))
        print(f"  {label:44} {sum(diffs):+8,.0f}  IC90% [{sims[250]:+8,.0f}, {sims[4749]:+8,.0f}]  "
              f"meses mejor/peor {sum(d > 1 for d in diffs)}/{sum(d < -1 for d in diffs)}  (tamaño ×{k:.2f})")


def run(variants, pools, procs):
    items = [(label, params, opts, pools) for label, (params, opts) in variants.items()]
    with Pool(procs) as pool:
        return dict(pool.imap_unordered(evaluate, items))


def main():
    global DATA, COSTS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="BD del bot de la que leer límites DI y apalancamiento")
    ap.add_argument("--group", help="sólo este grupo: " + ", ".join(GROUPS))
    ap.add_argument("--combo", action="store_true", help="la propuesta, regla a regla (COMBOS)")
    ap.add_argument("--neighbors", action="store_true", help="vecinos de la propuesta (NEIGHBORS)")
    ap.add_argument("--m15", action="store_true", help="7 activas con ciclos de 15 min")
    ap.add_argument("--universe", choices=("core", "extended"), default="core")
    ap.add_argument("--slippage", type=float, default=COSTS.slippage)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    args = ap.parse_args()

    COSTS = replace(COSTS, slippage=args.slippage)
    if args.m15:
        names = list(ACTIVE)
    else:
        names = [n for n in (R.CORE if args.universe == "core" else R.EXTENDED) if n != "SHIB"]
    DATA, db = load(names, args.db, args.m15)
    names = [n for n in names if n in DATA]
    pools = {f"{len(names)} símbolos": names}
    active = [n for n in ACTIVE if n in DATA]
    if active and len(active) < len(names):
        pools[f"{len(active)} activas"] = active
    first = min(d["rows"][0][0] for d in DATA.values())
    print(f"{len(names)} símbolos ({args.universe}), ciclos de {'15 min' if args.m15 else '1 h'} desde "
          f"{rp.fmt(first, '%Y-%m-%d')} | capital fijo {EQUITY:,} | riesgo {BASE.risk_pct:.1%} | "
          f"slippage {COSTS.slippage:.2%} | parámetros del bot: {os.path.basename(db) if db else 'por defecto'}")

    base = "bot actual (filtro BTC)"
    if args.combo or args.neighbors:
        variants = {base: (BASE, {}), **(COMBOS if args.combo else NEIGHBORS)}
        results = run(variants, pools, args.procs)
        for pool in pools:
            table(results, list(variants), pool, f"Combinaciones · {pool}")
            bootstrap(results, base, [n for n in variants if n != base], pool)
        pool = next(iter(pools))
        years = sorted({m[:4] for r in results.values() for st in r[pool] for m in st["monthly"]})
        width = max(len(n) for n in variants) + 1
        print(f"\n  P&L por año · {pool}\n  {'':{width}}" + "".join(f"{y:>9}" for y in years))
        for label in variants:
            by = defaultdict(float)
            for st in results[label][pool]:
                for m, x in st["monthly"].items():
                    by[m[:4]] += x
            print(f"  {label:{width}}" + "".join(f"{by[y]:+9,.0f}" for y in years))
        if args.neighbors:
            return
        print("\n  Motivos de cierre, todo el periodo (ops / P&L):")
        for label in variants:
            print(f"  {label:44} " + "  ".join(
                f"{r} {n} / {pnl:+,.0f}" for r, (n, pnl) in sorted(results[label]["_reasons"].items())))
        print("\n  P&L por símbolo (selección / evaluación):")
        for label in variants:
            by = results[label]["_by_sym"]
            print(f"  {label}")
            print("    " + "  ".join(f"{s} {a:+,.0f}/{b:+,.0f}" for s, (a, b) in by.items()))
        return

    groups = {args.group: GROUPS[args.group]} if args.group else GROUPS
    variants = {base: (BASE, {})}
    for g in groups.values():
        variants.update(g)
    results = run(variants, pools, args.procs)
    for pool in pools:
        for gname, g in groups.items():
            table(results, [base] + list(g), pool, f"[{gname}] · {pool}")
    pool = next(iter(pools))
    print("\n  Motivos de cierre del bot actual (ops / P&L): " + "  ".join(
        f"{r} {n} / {pnl:+,.0f}" for r, (n, pnl) in sorted(results[base]["_reasons"].items())))


if __name__ == "__main__":
    main()
