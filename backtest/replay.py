#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest por replay de StrategyState
------------------------------------

Reproduce ciclo a ciclo la lógica de Strategy.operation() (modo normal) con los
mismos datos que vio el bot en cada ciclo y que quedaron registrados en
MT_strategystate: precio, ADX, DI+/DI-, Recommend.MA de TradingView y ATR.

No llama a ninguna API ni necesita Django: abre la base de datos en modo sólo
lectura, así que puede usarse con una copia de la BD de producción.

    python backtest/replay.py --db db.sqlite3 --validate   # contrasta con operaciones reales
    python backtest/replay.py --db db.sqlite3 --detail     # compara variantes
    python backtest/replay.py --db db.sqlite3 --grid       # sensibilidad del trailing

Todas las variantes se dimensionan con el mismo capital fijo (--equity) para que
sean comparables. Limitaciones:
  - El precio registrado es el de la caché de BINGX.py (se refresca cada ~20 min),
    pero las órdenes reales se ejecutan al precio del momento. Por defecto se
    ejecutan al siguiente refresco (--fill next), que es lo que mejor reproduce
    el P&L de las operaciones reales; conviene comprobar que las conclusiones se
    mantienen con --fill logged.
  - La financiación (funding) se aproxima con una tasa fija que se cobra siempre.
  - Sólo modo normal: protectedTrade no está soportado por la API.
"""

import argparse
import os
import pickle
import random
import sqlite3
import statistics
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

EPOCH = datetime(1970, 1, 1)
HOUR = 3600.0
DAY = 86400.0


# ──────────────────────────────────────────────────────────────────────────────
# Parámetros de la lógica (valores por defecto = código actual de strategy.py)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Params:
    atr_mult_sl: float = 2.0      # ATR_MULT_SL: stop inicial y trailing
    breakeven_r: float = 0.7      # BREAKEVEN_R
    tp_r: float = 2.0             # TP en múltiplos de R (None = sin TP)
    sl_gated: bool = True         # SL sólo se evalúa si checkRecommend() es False
    tp_gated: bool = True         # TP sólo se evalúa si checkRecommend() es False
    hard_sl_always: bool = False  # el stop inicial se evalúa siempre, aunque el SL esté condicionado
    trail_steps: tuple = ()       # ((R alcanzado, múltiplo de ATR del trailing), ...)
    di_exit: bool = True          # cierre por reversión de DI (limitBuy / limitSell)
    btc_regime: bool = False      # largos sólo con BTC > SMA200 y cortos sólo por debajo
                                  # (requiere filas con el régimen en la posición 14)
    vol_min_pct: float = 2.0      # VOL_MIN_PCT
    risk_pct: float = 0.015       # RISK_PCT
    cooldown_days: float = 1.0    # cooldown tras stopLoss / takeProfit


@dataclass(frozen=True)
class Costs:
    taker: float = 0.0005         # comisión taker de BingX por lado
    slippage: float = 0.0         # deslizamiento por lado sobre el precio registrado
    funding_8h: float = 0.0001    # coste de financiación cada 8h sobre el nocional
    liq_frac: float = 0.9         # pérdida (fracción del margen) que provoca liquidación
    fill: str = "next"            # precio de ejecución: "next" = siguiente refresco de la
                                  # caché tras la decisión (el que mejor casa con las
                                  # operaciones reales); "logged" = precio registrado


ACTUAL = Params()
PROPUESTA = replace(ACTUAL, sl_gated=False, tp_r=None,
                    trail_steps=((1.0, 1.5), (2.0, 1.0)))

VARIANTS = {
    "actual": ACTUAL,
    "sl_siempre": replace(ACTUAL, sl_gated=False),
    "sl_tp_siempre": replace(ACTUAL, sl_gated=False, tp_gated=False),
    "trailing_1R_2R": PROPUESTA,
}

# Sensibilidad de la propuesta: si sólo mejora con un ajuste concreto, es ruido
GRID = {
    "actual": ACTUAL,
    "1R>1.5 2R>1.0": PROPUESTA,
    "1R>1.5": replace(PROPUESTA, trail_steps=((1.0, 1.5),)),
    "1R>1.0": replace(PROPUESTA, trail_steps=((1.0, 1.0),)),
    "0.5R>1.5 1.5R>1.0": replace(PROPUESTA, trail_steps=((0.5, 1.5), (1.5, 1.0))),
    "1.5R>1.5 3R>1.0": replace(PROPUESTA, trail_steps=((1.5, 1.5), (3.0, 1.0))),
    "1R>1.5 2R>0.75": replace(PROPUESTA, trail_steps=((1.0, 1.5), (2.0, 0.75))),
    "1R>1.5 2R>1.0 +TP cond.": replace(PROPUESTA, tp_r=2.0, tp_gated=True),
}

# Ablaciones informativas (no forman parte de la propuesta)
EXTRA = {
    "stop_inicial_siempre": replace(ACTUAL, hard_sl_always=True),
    "sin_salida_DI": replace(ACTUAL, di_exit=False),
    "trailing_sin_DI": replace(PROPUESTA, di_exit=False),
}

ALL_VARIANTS = {**VARIANTS, **GRID, **EXTRA}


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
COLUMNS = ("timestamp", "currentRate", "adx", "plusDI", "minusDI", "recommendMA",
           "recommendMA240", "atr", "limitOpen", "limitClose", "limitBuy",
           "limitSell", "isRunning", "operID")


def connect(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def to_epoch(ts):
    # Django guarda en SQLite texto UTC sin zona horaria
    return (datetime.fromisoformat(ts[:26]) - EPOCH).total_seconds()


def fmt(epoch, f="%Y-%m-%d %H:%M"):
    return (EPOCH + timedelta(seconds=epoch)).strftime(f)


def load_strategies(con):
    return con.execute(
        "select id, utility, leverage, isRunning from MT_strategy order by id"
    ).fetchall()


def load_rows(con, strategy_id, cache_dir=None):
    """Ciclos registrados de una estrategia, en orden temporal."""
    path = cache_dir and os.path.join(cache_dir, f"state_{strategy_id}.pkl")
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    rows = []
    query = ("select " + ",".join(COLUMNS) + " from MT_strategystate"
             " where strategy_id=? order by timestamp")
    for r in con.execute(query, (strategy_id,)):
        # En vivo un ciclo sin estos datos acaba en excepción (inError)
        if None in r[:12]:
            continue
        rows.append((to_epoch(r[0]),) + r[1:13] + (r[13] or 0,))
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(rows, f, protocol=pickle.HIGHEST_PROTOCOL)
    return rows


def fill_prices(rows, c):
    """Precio al que se ejecutaría una orden decidida en cada ciclo."""
    prices = [r[1] for r in rows]
    if c.fill == "next":
        # El precio registrado sale de la caché de BINGX.py: la orden real se
        # ejecuta después, más cerca del siguiente refresco que del registrado.
        for i in range(len(rows) - 2, -1, -1):
            if rows[i + 1][1] == rows[i][1]:
                prices[i] = prices[i + 1]
            else:
                prices[i] = rows[i + 1][1]
    return prices


# ──────────────────────────────────────────────────────────────────────────────
# Simulación
# ──────────────────────────────────────────────────────────────────────────────
class Position:
    __slots__ = ("side", "entry", "fill", "units", "bet", "sl", "hard_sl", "tp",
                 "extreme", "adx_close", "t_open", "mfe", "mae")


@dataclass
class Trade:
    sym: str
    side: int
    t_open: float
    t_close: float
    entry: float
    exit: float
    bet: float
    pnl: float
    reason: str
    mfe: float  # máximo beneficio no realizado, % sobre el margen
    mae: float  # máxima pérdida no realizada, % sobre el margen


def simulate(rows, sym, lev, p, c, equity, respect_running=False):
    """Replay de Strategy.operation() en modo normal. Devuelve (trades, curva horaria)."""
    trades, curve = [], []
    fills = fill_prices(rows, c)
    estado, pos = 0, None
    cooldown_until = float("-inf")
    realized, last_hour = 0.0, None

    def close(t, fpx, reason, pnl=None):
        nonlocal realized
        exit_fill = fpx * (1 - pos.side * c.slippage)
        if pnl is None:
            gross = pos.units * (exit_fill - pos.fill) * pos.side
            fees = c.taker * pos.units * (pos.fill + exit_fill)
            funding = c.funding_8h * pos.units * pos.fill * (t - pos.t_open) / (8 * HOUR)
            pnl = gross - fees - funding
        realized += pnl
        trades.append(Trade(sym, pos.side, pos.t_open, t, pos.fill, exit_fill, pos.bet,
                            pnl, reason, pos.mfe, pos.mae))

    for i, (t, px, adx, pdi, mdi, rma, rma240, atr, lo, lc, lb, ls, running, _, *extra) in enumerate(rows):
        if respect_running and not running:
            continue
        diff = pdi - mdi
        # checkRecommend(): dirección según los DI, no según la posición abierta
        d = 1 if pdi > mdi else (-1 if mdi > pdi else 0)
        rec = d != 0 and (rma + rma240) * d > 1.5
        nxt = estado

        if estado == 0:  # HOLD
            if adx > lo:
                side = 0
                if diff > lb and rec:
                    side = 1
                if diff < ls and rec:
                    side = -1
                if p.btc_regime and side * (extra[0] if extra else 0) <= 0:
                    side = 0
                if side and atr and px and atr * 100.0 / px >= p.vol_min_pct:
                    stop_dist = p.atr_mult_sl * atr
                    amount = int(max(equity * p.risk_pct * px / stop_dist / lev, 0))
                    if amount > 0:
                        pos = Position()
                        pos.side, pos.entry, pos.bet, pos.t_open = side, px, amount, t
                        pos.fill = fills[i] * (1 + side * c.slippage)
                        pos.units = amount * lev / pos.fill
                        pos.sl = pos.hard_sl = px - side * stop_dist
                        pos.tp = px + side * stop_dist * p.tp_r if p.tp_r else None
                        pos.extreme = px
                        pos.adx_close = lc
                        pos.mfe = pos.mae = 0.0
                        nxt = 2

        elif estado == 2:  # OPER
            upnl = pos.units * (px - pos.fill) * pos.side
            pct = upnl * 100.0 / pos.bet
            if pct > pos.mfe:
                pos.mfe = pct
            if pct < pos.mae:
                pos.mae = pct
            if upnl <= -c.liq_frac * pos.bet:
                # Liquidación: en vivo se detecta como notOpen (cooldown de 2 días)
                close(t, fills[i], "liquidation", pnl=-pos.bet)
                cooldown_until = t + 2 * DAY
                pos, nxt = None, 3
            else:
                reasons = []
                if adx * 0.85 > pos.adx_close:
                    pos.adx_close = adx * 0.85
                if lc == 0:
                    pos.adx_close = 0
                if adx < pos.adx_close:
                    reasons.append("limitClose")
                if pos.side == -1:
                    if px < pos.extreme:
                        pos.extreme = px
                    if p.di_exit and diff > ls * 0.85:
                        reasons.append("limitSell")
                else:
                    if px > pos.extreme:
                        pos.extreme = px
                    if p.di_exit and diff < lb * 0.85:
                        reasons.append("limitBuy")

                stop_init = p.atr_mult_sl * atr
                if stop_init > 0:
                    side, entry = pos.side, pos.entry
                    # Break-even (no retrocede el SL)
                    if ((px - entry) * side / stop_init >= p.breakeven_r
                            and (pos.sl - entry) * side < 0):
                        pos.sl = entry
                    # Trailing tipo Chandelier desde el extremo
                    dist = stop_init
                    max_r = (pos.extreme - entry) * side / stop_init
                    for r_min, mult in p.trail_steps:
                        if max_r >= r_min:
                            dist = mult * atr
                    new_sl = pos.extreme - side * dist
                    if (new_sl - pos.sl) * side > 0:
                        pos.sl = new_sl
                    # TP en múltiplos de R desde la entrada; sólo se aleja
                    if p.tp_r:
                        base_tp = entry + side * stop_init * p.tp_r
                        if pos.tp is None or (base_tp - pos.tp) * side > 0:
                            pos.tp = base_tp
                    if (((not p.sl_gated or not rec) and (px - pos.sl) * side <= 0)
                            or (p.hard_sl_always and (px - pos.hard_sl) * side <= 0)):
                        reasons.append("stopLoss")
                        cooldown_until = t + p.cooldown_days * DAY
                    if (pos.tp is not None and (not p.tp_gated or not rec)
                            and (px - pos.tp) * side >= 0):
                        reasons.append("takeProfit")
                        cooldown_until = t + p.cooldown_days * DAY

                if reasons:
                    close(t, fills[i], " ".join(reasons))
                    pos, nxt = None, 3

        elif estado == 3:  # COOLDOWN
            nxt = 0 if cooldown_until < t else 3

        estado = nxt

        hour = int(t // HOUR)
        if hour != last_hour:
            upnl = pos.units * (px - pos.fill) * pos.side if pos else 0.0
            curve.append((hour, realized + upnl))
            last_hour = hour

    if pos is not None:
        close(rows[-1][0], fills[-1], "abierta")
    return trades, curve


# ──────────────────────────────────────────────────────────────────────────────
# Métricas
# ──────────────────────────────────────────────────────────────────────────────
def combine(curves):
    """Suma curvas horarias de varias estrategias arrastrando el último valor."""
    curves = [cv for cv in curves if cv]
    if not curves:
        return []
    start = min(cv[0][0] for cv in curves)
    end = max(cv[-1][0] for cv in curves)
    idx, last, out = [0] * len(curves), [0.0] * len(curves), []
    for hour in range(start, end + 1):
        for k, cv in enumerate(curves):
            while idx[k] < len(cv) and cv[idx[k]][0] <= hour:
                last[k] = cv[idx[k]][1]
                idx[k] += 1
        out.append((hour, sum(last)))
    return out


def max_drawdown(curve, equity):
    peak, dd, dd_pct = 0.0, 0.0, 0.0
    for _, value in curve:
        peak = max(peak, value)
        dd = max(dd, peak - value)
        dd_pct = max(dd_pct, (peak - value) * 100.0 / (equity + peak))
    return dd, dd_pct


def summarize(trades, curve, equity, risk_amount):
    pnls = [t.pnl for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
    dd, dd_pct = max_drawdown(curve, equity)
    return {
        "n": len(pnls),
        "win": 100.0 * len(wins) / len(pnls) if pnls else 0.0,
        "pnl": sum(pnls),
        "ret": 100.0 * sum(pnls) / equity,
        "pf": sum(wins) / -sum(losses) if sum(losses) < 0 else float("inf"),
        "avg_win": statistics.mean(wins) if wins else 0.0,
        "avg_loss": statistics.mean(losses) if losses else 0.0,
        "exp_r": sum(pnls) / len(pnls) / risk_amount if pnls else 0.0,
        "dd": dd,
        "dd_pct": dd_pct,
        "liq": sum(1 for t in trades if t.reason == "liquidation"),
    }


def print_table(header, rows, widths):
    line = "  ".join(f"{h:>{w}}" if i else f"{h:<{w}}" for i, (h, w) in enumerate(zip(header, widths)))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(f"{v:>{w}}" if i else f"{v:<{w}}" for i, (v, w) in enumerate(zip(row, widths))))
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Comparación de variantes
# ──────────────────────────────────────────────────────────────────────────────
def compare(con, strategies, variants, costs, args):
    risk_amount = args.equity * ACTUAL.risk_pct
    trades = {name: [] for name in variants}
    curves = {name: [] for name in variants}
    for sid, sym, lev, _ in strategies:
        rows = load_rows(con, sid, args.cache)
        for name, p in variants.items():
            tr, cv = simulate(rows, sym, lev, p, costs, args.equity, args.respect_running)
            trades[name] += tr
            curves[name].append(cv)
    if not any(trades.values()):
        print("Sin operaciones simuladas.")
        return

    all_trades = [t for tr in trades.values() for t in tr]
    t0 = min(t.t_open for t in all_trades)
    t1 = max(t.t_close for t in all_trades)
    print(f"Periodo {fmt(t0, '%Y-%m-%d')} → {fmt(t1, '%Y-%m-%d')} | "
          f"{len(strategies)} estrategias | capital {args.equity:,.0f} | "
          f"riesgo/operación {risk_amount:,.0f} | comisión {costs.taker:.3%} | "
          f"slippage {costs.slippage:.3%} | funding {costs.funding_8h:.3%}/8h\n")

    stats = {name: summarize(trades[name], combine(curves[name]), args.equity, risk_amount)
             for name in variants}
    width = max(len(n) for n in variants) + 2
    print_table(
        ["variante", "ops", "acierto", "P&L", "rent.", "PF", "gan.media", "pérd.media",
         "E[R]", "maxDD", "liq."],
        [[name, s["n"], f"{s['win']:.0f}%", f"{s['pnl']:,.0f}", f"{s['ret']:+.1f}%",
          f"{s['pf']:.2f}", f"{s['avg_win']:,.0f}", f"{s['avg_loss']:,.0f}",
          f"{s['exp_r']:+.2f}", f"{s['dd']:,.0f} ({s['dd_pct']:.0f}%)", s["liq"]]
         for name, s in stats.items()],
        [width, 5, 7, 9, 7, 5, 9, 10, 6, 13, 4])

    # Motivos de cierre
    print("Motivo de cierre (ops / P&L):")
    reasons = sorted({t.reason.split()[0] for t in all_trades})
    print_table(
        ["variante"] + reasons,
        [[name] + [
            (lambda sel: f"{len(sel)} / {sum(t.pnl for t in sel):,.0f}" if sel else "-")(
                [t for t in trades[name] if t.reason.split()[0] == r])
            for r in reasons] for name in variants],
        [width] + [max(len(r), 14) for r in reasons])

    names = list(variants)
    if args.detail:
        # Estabilidad: por mitades del periodo, por mes y por estrategia
        mid = t0 + (t1 - t0) / 2
        halves = [("1ª mitad", lambda t: t.t_close < mid), ("2ª mitad", lambda t: t.t_close >= mid)]
        print(f"P&L por mitades (corte {fmt(mid, '%Y-%m-%d')}):")
        print_table(["periodo"] + names,
                    [[label] + [f"{sum(t.pnl for t in trades[n] if cond(t)):,.0f}" for n in names]
                     for label, cond in halves],
                    [10] + [max(len(n), 9) for n in names])

        months = sorted({fmt(t.t_close, "%Y-%m") for t in all_trades})
        print("P&L por mes de cierre:")
        print_table(["mes"] + names,
                    [[m] + [f"{sum(t.pnl for t in trades[n] if fmt(t.t_close, '%Y-%m') == m):,.0f}"
                            for n in names] for m in months],
                    [8] + [max(len(n), 9) for n in names])

        print("P&L por estrategia:")
        syms = [s[1] for s in strategies]
        print_table(["símbolo"] + names,
                    [[sym] + [f"{sum(t.pnl for t in trades[n] if t.sym == sym):,.0f}" for n in names]
                     for sym in syms],
                    [8] + [max(len(n), 9) for n in names])
        base = names[0]
        for n in names[1:]:
            better = sum(1 for sym in syms
                         if sum(t.pnl for t in trades[n] if t.sym == sym)
                         > sum(t.pnl for t in trades[base] if t.sym == sym) + 1)
            worse = sum(1 for sym in syms
                        if sum(t.pnl for t in trades[n] if t.sym == sym)
                        < sum(t.pnl for t in trades[base] if t.sym == sym) - 1)
            print(f"  {n}: mejora en {better} estrategias, empeora en {worse} (frente a {base})")
        print()

        # Robustez: ¿la diferencia con la primera variante se distingue del ruido?
        # Remuestreo por meses (los símbolos de un mismo mes están correlacionados).
        rng = random.Random(1)
        print(f"Robustez frente a {base} (IC 90% por remuestreo de meses, 5000 réplicas):")
        by_month = {n: defaultdict(float) for n in names}
        for n in names:
            for t in trades[n]:
                by_month[n][fmt(t.t_close, "%Y-%m")] += t.pnl
        for n in names:
            best = sorted(trades[n], key=lambda t: t.pnl, reverse=True)
            top = ", ".join(f"{t.sym} {fmt(t.t_open, '%Y-%m-%d')} {t.pnl:,.0f}" for t in best[:3])
            line = (f"  {n}: sin su mejor operación {sum(t.pnl for t in best[1:]):,.0f}; "
                    f"mejores: {top}")
            if n != base:
                diffs = [by_month[n][m] - by_month[base][m] for m in months]
                sims = sorted(sum(rng.choice(diffs) for _ in diffs) for _ in range(5000))
                line += (f"\n    diferencia {sum(diffs):+,.0f}, IC90% [{sims[250]:+,.0f}, "
                         f"{sims[4749]:+,.0f}], meses mejor/peor {sum(d > 1 for d in diffs)}/"
                         f"{sum(d < -1 for d in diffs)}")
            print(line)
        print()


# ──────────────────────────────────────────────────────────────────────────────
# Validación frente a las operaciones reales
# ──────────────────────────────────────────────────────────────────────────────
def validate(con, strategies, costs, args):
    ops = defaultdict(list)
    for row in con.execute(
            "select strategy_id, type, timestampOpen, timestampClose, beneficio, profit,"
            " reasonClose from MT_strategyoperation order by timestampOpen"):
        ops[row[0]].append(row)

    pnl_err, lev_check = [], []
    real_total = matched = same_reason = sim_in_period = 0
    close_diff = []
    unmatched = []
    first_real = min((to_epoch(o[2]) for lst in ops.values() for o in lst), default=0)

    for sid, sym, lev, _ in strategies:
        rows = load_rows(con, sid, args.cache)
        if not rows:
            continue
        ts = [r[0] for r in rows]
        fills = fill_prices(rows, costs)

        # 1) Modelo de P&L: precio de ejecución al abrir/cerrar + comisiones
        for _, typ, t_open, t_close, ben, prof, reason in ops[sid]:
            if not t_close or not prof or (reason or "").startswith("notOpen"):
                continue
            i, j = bisect_left(ts, to_epoch(t_open)), bisect_left(ts, to_epoch(t_close))
            if j >= len(rows):
                continue
            entry, exit_ = fills[i], fills[j]
            side = 1 if typ == "buy" else -1
            bet = ben * 100.0 / prof
            units = bet * lev / entry
            model = units * (exit_ - entry) * side - costs.taker * units * (entry + exit_)
            pnl_err.append((model - ben) * 100.0 / bet)
            move = (exit_ - entry) * side * 100.0 / entry
            if abs(move) > 1:
                lev_check.append((sym, lev, prof / move))

        # 2) Lógica de decisión: la variante actual respetando isRunning
        sim, _ = simulate(rows, sym, lev, ACTUAL, costs, args.equity, respect_running=True)
        sim_in_period += sum(1 for t in sim if t.t_open >= first_real)
        used = set()
        for _, typ, t_open, t_close, ben, prof, reason in ops[sid]:
            real_total += 1
            side = 1 if typ == "buy" else -1
            to = to_epoch(t_open)
            cands = [(abs(t.t_open - to), k) for k, t in enumerate(sim)
                     if k not in used and t.side == side and abs(t.t_open - to) <= HOUR]
            if not cands:
                unmatched.append((sym, typ, t_open[:16], (reason or "abierta").strip()))
                continue
            _, k = min(cands)
            used.add(k)
            matched += 1
            if t_close and sim[k].reason != "abierta":
                close_diff.append(abs(sim[k].t_close - to_epoch(t_close)) / HOUR)
                if (reason or "").split()[0] == sim[k].reason.split()[0]:
                    same_reason += 1

    print("1) Modelo de P&L frente a operaciones reales cerradas (sin notOpen)")
    if pnl_err:
        q = statistics.quantiles(pnl_err, n=10)
        print(f"   {len(pnl_err)} operaciones. Error del modelo (puntos % sobre el margen): "
              f"mediana {statistics.median(pnl_err):+.2f}, media {statistics.mean(pnl_err):+.2f}, "
              f"p10 {q[0]:+.2f}, p90 {q[-1]:+.2f}")
        by_sym = defaultdict(list)
        for sym, lev, implied in lev_check:
            by_sym[(sym, lev)].append(implied)
        print("   Apalancamiento configurado vs implícito (beneficio % / movimiento %):")
        print("   " + ", ".join(f"{s} {l}x→{statistics.median(v):.1f}x"
                               for (s, l), v in sorted(by_sym.items())))
    print()
    print("2) Lógica de decisión: operaciones reales reproducidas por el simulador")
    print(f"   Reales: {real_total}. Con entrada simulada del mismo lado a ±1h: {matched} "
          f"({100.0 * matched / max(real_total, 1):.0f}%)")
    print(f"   Simuladas desde la primera operación real: {sim_in_period}")
    if close_diff:
        print(f"   En las emparejadas y cerradas: mismo motivo de cierre {same_reason}/{len(close_diff)}, "
              f"diferencia mediana en la hora de cierre {statistics.median(close_diff):.1f} h")
    if unmatched:
        print("   Sin emparejar: " + "; ".join(" ".join(u) for u in unmatched))
    print()


# ──────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="db.sqlite3", help="copia de la BD (se abre en sólo lectura)")
    ap.add_argument("--equity", type=float, default=30000, help="capital fijo para dimensionar")
    ap.add_argument("--variants", help="variantes separadas por comas (por defecto todas)")
    ap.add_argument("--grid", action="store_true", help="sensibilidad del trailing escalonado")
    ap.add_argument("--validate", action="store_true", help="contrastar con operaciones reales")
    ap.add_argument("--only-running", action="store_true", help="sólo estrategias activas hoy")
    ap.add_argument("--respect-running", action="store_true",
                    help="operar sólo en los ciclos con isRunning=1")
    ap.add_argument("--exclude", default="SHIB", help="símbolos excluidos (SHIB: precio congelado)")
    ap.add_argument("--detail", action="store_true", help="desglose por mitades, mes y estrategia")
    ap.add_argument("--taker", type=float, default=Costs.taker)
    ap.add_argument("--slippage", type=float, default=Costs.slippage)
    ap.add_argument("--funding", type=float, default=Costs.funding_8h)
    ap.add_argument("--fill", choices=("next", "logged"), default=Costs.fill,
                    help="precio de ejecución (ver Costs.fill)")
    ap.add_argument("--cache", help="directorio para cachear los datos leídos de la BD")
    args = ap.parse_args()

    con = connect(args.db)
    excluded = {s.strip() for s in args.exclude.split(",") if s.strip()}
    strategies = [s for s in load_strategies(con) if s[1] not in excluded]
    if args.only_running:
        strategies = [s for s in strategies if s[3]]
    costs = Costs(taker=args.taker, slippage=args.slippage, funding_8h=args.funding,
                  fill=args.fill)

    if args.validate:
        validate(con, strategies, costs, args)
        return
    variants = GRID if args.grid else VARIANTS
    if args.variants:
        variants = {n: ALL_VARIANTS[n] for n in args.variants.split(",")}
    compare(con, strategies, variants, costs, args)


if __name__ == "__main__":
    main()
