#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exploración de stop loss / take profit del bot
----------------------------------------------

Reconstruye el bot sobre BTC, ETH y SOL con el filtro de régimen de BTC y recorre
una rejilla de niveles de SL y TP y de reglas de cierre, con el simulador de
replay.py:

  - SL y TP en múltiplos de R, siendo R el stop actual (ATR_MULT_SL = 2 ATR). El
    SL también fija el trailing, el break-even y el tamaño (riesgo constante), como
    haría el código si se cambia ATR_MULT_SL; el TP es relativo al mismo R.
  - TP "condicionado": sólo si checkRecommend() es False (código actual).
    "forzado": el bot cierra en el primer ciclo con el precio más allá del TP.
    "orden": orden TP en el exchange, se ejecuta al nivel en cuanto se toca.

Un ciclo por vela de 15 min (velas de Binance, marketdata.py --m15), al precio de
cierre: la caché de precios de BINGX.py se refrescaba cada ~20 min (5 min desde 2026-09-30), así que el bot
no ve los extremos intermedios. Como en vivo, el ATR sale de velas diarias hechas
con esas muestras y DI/ADX/Recommend.MA de la vela diaria (y 4h) en curso.

Los parámetros se eligen con 2020-2022 y se validan con 2023 en adelante.

    python3 backtest/marketdata.py --m15 BTC,ETH,SOL
    python3 backtest/sltp.py
    python3 backtest/sltp.py --symbols XRP,DOGE,BNB,ADA   # otros símbolos del bot
"""

import argparse
import math
import os
import pickle
import random
import statistics
from collections import defaultdict
from dataclasses import replace
from multiprocessing import Pool

import indicators as ind
import replay as rp
import research as R

SYMBOLS = ("BTC", "ETH", "SOL")
# Zona elegida con BTC, ETH y SOL, para contrastarla con otros símbolos
ZONE = [(sl, tp, rule) for sl in (1.25, 1.5) for tp in (1.5, 2.0) for rule in ("forzado", "orden")]
PERIODS = (("selección 2020-2022", "2020-01-01", "2022-12-31"),
           ("validación 2023-2026", "2023-01-01", None))
SL_R = (0.5, 0.75, 1.0, 1.25, 1.5)
TP_R = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, None)
TP_RULES = ("condicionado", "forzado", "orden")
EQUITY = 30000
BASE = replace(rp.ACTUAL, btc_regime=True)
COSTS = rp.Costs(slippage=0.0005, funding_8h=0.0, liq_frac=1e9, fill="logged")
COSTS_FIELDS = {}
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
DB = os.path.join(HERE, "..", "db.sqlite3")
STEP = 15 * 60 * 1000


def variant(sl, tp, rule, sl_forced=False, same_size=False):
    """SL y TP en múltiplos del R actual (2 ATR)."""
    return replace(BASE, atr_mult_sl=rp.ACTUAL.atr_mult_sl * sl, tp_r=tp / sl if tp else None,
                   tp_gated=rule == "condicionado", tp_order=rule == "orden",
                   sl_gated=not sl_forced,
                   sizing_sl=rp.ACTUAL.atr_mult_sl if same_size else None)


def name(sl, tp, rule, sl_forced=False, same_size=False):
    return (f"SL {sl:g}R TP {f'{tp:g}R' if tp else '-':>4} TP {rule}"
            + (" +SL forz." if sl_forced else "") + (" tam.actual" if same_size else ""))


# ──────────────────────────────────────────────────────────────────────────────
# Datos: ciclos del bot cada 15 min
# ──────────────────────────────────────────────────────────────────────────────
def bot_rows(s, limits, btc_up):
    """
    Formato de filas de replay.py con el régimen de BTC del día anterior (14) y el
    máximo y mínimo de la vela de 15 min (15, 16) para las órdenes TP.
    """
    bars = R.read_rows(f"{s.symbol}_15m.csv")
    t4, _, _, c4, v4 = s.bars_4h()
    idx4 = {t: k for k, t in enumerate(t4)}
    dmi_d, rating_d, rating_4h = ind.PartialDMI(s.h, s.l, s.c), ind.PartialRating(s.c, s.v), \
        ind.PartialRating(c4, v4)
    # ATR del bot: velas diarias hechas con sus propias muestras de precio
    bh, bl, bc, bidx = [], [], [], {}
    for r in bars:
        d = int(r[0]) // R.DAY_MS * R.DAY_MS
        if d not in bidx:
            bidx[d] = len(bc)
            bh.append(r[4]), bl.append(r[4]), bc.append(r[4])
        k = bidx[d]
        bh[k], bl[k], bc[k] = max(bh[k], r[4]), min(bl[k], r[4]), r[4]
    atr_bot = ind.PartialDMI(bh, bl, bc)
    lb, ls = limits[s.name]
    four = 4 * 3600 * 1000
    rows, day, block = [], None, None
    for t, _, h, l, c, v in bars:
        t = int(t)
        d = t // R.DAY_MS * R.DAY_MS
        if d != day:
            day, hp, lp, vp, chp, clp = d, h, l, 0.0, c, c
            k, kb = s.index.get(d - R.DAY_MS), bidx.get(d - R.DAY_MS)
            up = btc_up.get(d - R.DAY_MS)
            regime = 0 if up is None else (1 if up else -1)
        if t // four * four != block:
            block, v4p = t // four * four, 0.0
            k4 = idx4.get(block - four)
        hp, lp, vp, v4p = max(hp, h), min(lp, l), vp + v, v4p + v
        chp, clp = max(chp, c), min(clp, c)
        if k is None or kb is None or k4 is None:
            continue
        x, xb = dmi_d.at(k, hp, lp, c), atr_bot.at(kb, chp, clp, c)
        rd, r4 = rating_d.at(k, c, vp), rating_4h.at(k4, c, v4p)
        if None in (x, xb, rd, r4):
            continue
        rows.append(((t + STEP) / 1000, c, x[2], x[0], x[1], rd, r4, xb[3], 0, 0, lb, ls, 1, 0,
                     regime, h, l))
    return rows


def load(symbols=SYMBOLS):
    os.makedirs(CACHE, exist_ok=True)
    limits, levs = R.bot_limits(DB), R.bot_leverages(DB)
    assert limits and levs, f"sin parámetros del bot: falta {DB}"
    data, btc_up = {}, None
    for n in symbols:
        path = os.path.join(CACHE, f"sltp_15m_{n}.pkl")
        if not os.path.exists(path):
            if btc_up is None:
                btc = R.Series("BTC", R.CORE["BTC"])
                btc_up = {t: c > m for t, c, m in zip(btc.t, btc.c, ind.sma(btc.c, 200))
                          if m is not None}
            s = R.Series(n, R.CORE[n])
            with open(path, "wb") as f:
                pickle.dump({"rows": bot_rows(s, limits, btc_up), "t": s.t, "c": s.c,
                             "funding": dict(s.funding)}, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(path, "rb") as f:
            data[n] = pickle.load(f)
        data[n]["lev"] = levs[n]
    return data


# ──────────────────────────────────────────────────────────────────────────────
# Simulación y métricas
# ──────────────────────────────────────────────────────────────────────────────
DATA = None


def simulate(params):
    """Operaciones y P&L acumulado diario (con el funding real) de los tres símbolos."""
    trades, daily = [], defaultdict(float)
    for sym, d in DATA.items():
        tr, curve = rp.simulate(d["rows"], sym, d["lev"], params, replace(COSTS, **COSTS_FIELDS),
                                EQUITY)
        index = {t: i for i, t in enumerate(d["t"])}
        funding = defaultdict(float)
        for t in tr:
            units = t.bet * d["lev"] / t.entry
            paid = 0.0
            for day in range(int(t.t_open * 1000) // R.DAY_MS * R.DAY_MS,
                             int(t.t_close * 1000) // R.DAY_MS * R.DAY_MS, R.DAY_MS):
                i = index.get(day)
                if i is not None:
                    f = t.side * units * d["c"][i] * d["funding"].get(day, 0.0)
                    funding[day] += f
                    paid += f
            t.pnl -= paid
        pnl_at = {}
        for hour, value in curve:
            pnl_at[hour * 3600 * 1000 // R.DAY_MS * R.DAY_MS] = value
        pnl, acc = 0.0, 0.0
        for day in range(min(pnl_at), max(pnl_at) + 1, R.DAY_MS):
            pnl = pnl_at.get(day, pnl)
            acc += funding.get(day, 0.0)
            daily[day] += pnl - acc
        trades += tr
    return trades, [(day, daily[day]) for day in sorted(daily)]


def in_period(t_close, start, end):
    return R.day_ms(start) / 1000 <= t_close < (R.day_ms(end) / 1000 + 86400 if end else float("inf"))


def period_stats(trades, curve, start, end):
    a, b = R.day_ms(start), R.day_ms(end) if end else float("inf")
    pts = [v for day, v in curve if a <= day <= b]
    rets = [(y - x) / EQUITY for x, y in zip(pts, pts[1:])]
    sd = statistics.pstdev(rets)
    peak, dd = pts[0], 0.0
    for v in pts:
        peak = max(peak, v)
        dd = max(dd, peak - v)
    sel = [t.pnl for t in trades if in_period(t.t_close, start, end)]
    wins, losses = sum(x for x in sel if x > 0), -sum(x for x in sel if x <= 0)
    return {"pnl": pts[-1] - pts[0], "sharpe": statistics.mean(rets) / sd * math.sqrt(365) if sd else 0.0,
            "dd": dd, "sd": sd, "n": len(sel), "win": sum(x > 0 for x in sel) / len(sel) if sel else 0.0,
            "pf": wins / losses if losses else float("inf")}


def evaluate(item):
    label, params = item
    trades, curve = simulate(params)
    by_sym = {sym: [sum(t.pnl for t in trades if t.sym == sym and in_period(t.t_close, a, b))
                    for _, a, b in PERIODS] for sym in DATA}
    reasons = defaultdict(lambda: [0, 0.0])
    for t in trades:
        if in_period(t.t_close, *PERIODS[1][1:]):
            r = reasons[t.reason.split()[0]]
            r[0] += 1
            r[1] += t.pnl
    monthly, yearly, last = defaultdict(float), defaultdict(float), 0.0
    for day, v in curve:
        if day >= R.day_ms(PERIODS[1][1]):
            monthly[R.fmt_day(day)[:7]] += v - last
        yearly[R.fmt_day(day)[:4]] += v - last
        last = v
    return label, [period_stats(trades, curve, a, b) for _, a, b in PERIODS], by_sym, \
        dict(reasons), dict(monthly), dict(yearly)


# ──────────────────────────────────────────────────────────────────────────────
# Informe
# ──────────────────────────────────────────────────────────────────────────────
def cell(st):
    return (f"{st['pnl']:+8,.0f} {st['sharpe']:6.2f} {st['dd']:7,.0f} "
            f"{st['n']:4d} {st['win']:5.0%} {st['pf']:5.2f}")


def table(results, labels, title):
    print(f"\n{title}")
    width = max(len(n) for n in labels) + 1
    print(f"  {'':{width}} " + "   ".join(f"{p:^42}" for p, _, _ in PERIODS))
    print(f"  {'variante':{width}} " + "   ".join(
        f"{'P&L':>8} {'Sharpe':>6} {'maxDD':>7} {'ops':>4} {'acier':>5} {'PF':>5}" for _ in PERIODS))
    for label in labels:
        print(f"  {label:{width}} " + "   ".join(cell(s) for s in results[label][1]))


def grid(results, rule, key, period, fmt):
    print(f"\n  TP {rule} · {key} en {PERIODS[period][0]} (filas SL, columnas TP)")
    print("  " + f"{'':8}" + "".join(f"{('TP ' + f'{tp:g}R') if tp else 'sin TP':>10}" for tp in TP_R))
    for sl in SL_R:
        vals = [results[name(sl, tp, rule)][1][period][key] for tp in TP_R]
        print("  " + f"SL {sl:<5g}" + "".join(f"{fmt(v):>10}" for v in vals))


def scale(results, base, label):
    """Factor de tamaño que iguala la volatilidad diaria a la de base en selección."""
    return results[base][1][0]["sd"] / results[label][1][0]["sd"]


def bootstrap(results, base, labels, same_risk=False):
    rng = random.Random(1)
    print(f"\n  Diferencia de P&L en validación frente a «{base}» (IC 90% remuestreando meses)"
          + (", a igual volatilidad que la base en selección:" if same_risk else ":"))
    for label in labels:
        k = scale(results, base, label) if same_risk else 1.0
        a, b = results[base][4], results[label][4]
        diffs = [k * b.get(m, 0.0) - a.get(m, 0.0) for m in sorted(set(a) | set(b))]
        sims = sorted(sum(rng.choice(diffs) for _ in diffs) for _ in range(5000))
        print(f"  {label:36} {sum(diffs):+8,.0f}  IC90% [{sims[250]:+7,.0f}, {sims[4749]:+7,.0f}]  "
              f"meses mejor/peor {sum(d > 1 for d in diffs)}/{sum(d < -1 for d in diffs)}"
              + (f"  (tamaño ×{k:.2f}, maxDD validación {k * results[label][1][1]['dd']:,.0f})"
                 if same_risk else ""))


def smoothed(results, rule):
    """Sharpe de selección promediado con los vecinos de la rejilla (SL±1, TP±1)."""
    out = {}
    for i, sl in enumerate(SL_R):
        for j, tp in enumerate(TP_R):
            vals = [results[name(SL_R[a], TP_R[b], rule)][1][0]["sharpe"]
                    for a in range(max(i - 1, 0), min(i + 2, len(SL_R)))
                    for b in range(max(j - 1, 0), min(j + 2, len(TP_R)))]
            out[name(sl, tp, rule)] = statistics.mean(vals)
    return out


def yearly(results, labels):
    years = sorted({y for label in labels for y in results[label][5]})
    width = max(len(n) for n in labels) + 1
    print(f"\n  P&L por año (sin escalar)")
    print(f"  {'variante':{width}}" + "".join(f"{y:>8}" for y in years))
    for label in labels:
        print(f"  {label:{width}}" + "".join(f"{results[label][5].get(y, 0.0):+8,.0f}" for y in years))


def main():
    global DATA
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--slippage", type=float, default=COSTS.slippage, help="por lado")
    ap.add_argument("--every", type=int, default=1,
                    help="el bot decide cada N velas de 15 min (sensibilidad al muestreo)")
    args = ap.parse_args()

    DATA = load(args.symbols.split(","))
    if args.every > 1:
        for d in DATA.values():
            rows, merged = d["rows"], []
            for i in range(args.every - 1, len(rows), args.every):
                group = rows[i - args.every + 1:i + 1]
                merged.append(rows[i][:15] + (max(r[15] for r in group), min(r[16] for r in group)))
            d["rows"] = merged
    COSTS_FIELDS["slippage"] = args.slippage
    variants = {}
    for sl in SL_R:
        for tp in TP_R:
            for rule in TP_RULES:
                variants[name(sl, tp, rule)] = variant(sl, tp, rule)
            for rule in ("condicionado", "forzado"):
                variants[name(sl, tp, rule, sl_forced=True)] = variant(sl, tp, rule, sl_forced=True)
    for sl, tp in ((0.5, 1.0), (0.75, 1.5), (1.25, 2.5), (1.5, 3.0)):
        for rule in TP_RULES:
            variants[name(sl, tp, rule, same_size=True)] = variant(sl, tp, rule, same_size=True)

    with Pool(args.procs) as pool:
        results = {r[0]: r for r in pool.imap_unordered(evaluate, variants.items())}

    print(f"{', '.join(DATA)} con filtro de régimen de BTC | ciclos de {15 * args.every} min | slippage "
          f"{args.slippage:.2%} | capital fijo "
          f"{EQUITY:,} | riesgo {rp.ACTUAL.risk_pct:.1%} por operación | apalancamiento "
          + ", ".join(f"{s} {d['lev']}x" for s, d in DATA.items())
          + " | datos desde " + ", ".join(f"{s} {rp.fmt(d['rows'][0][0], '%Y-%m-%d')}"
                                         for s, d in DATA.items()))

    actual = name(1.0, 2.0, "condicionado")
    asked = [actual, name(1.0, 2.0, "forzado"), name(1.0, 2.0, "orden"),
             name(0.75, 1.5, "condicionado"), name(0.75, 1.5, "forzado"), name(0.75, 1.5, "orden"),
             name(0.75, 1.5, "forzado", same_size=True)]
    table(results, asked, "Lo pedido: bot actual, TP forzado y SL 0.75R / TP 1.5R")
    bootstrap(results, actual, asked[1:])

    zone = [name(*z) for z in ZONE]
    table(results, [actual] + zone, "Zona elegida con BTC, ETH y SOL (SL 1.25-1.5R, TP 1.5-2R)")
    bootstrap(results, actual, zone, same_risk=True)

    for rule in TP_RULES:
        grid(results, rule, "sharpe", 0, lambda v: f"{v:.2f}")
        grid(results, rule, "sharpe", 1, lambda v: f"{v:.2f}")
        grid(results, rule, "pnl", 1, lambda v: f"{v:+,.0f}")

    # El tamaño no cambia el Sharpe: se ordenan sólo las variantes de riesgo constante
    ranked = sorted((n for n in results if "tam.actual" not in n),
                    key=lambda n: results[n][1][0]["sharpe"], reverse=True)
    table(results, ranked[:15], "Las 15 mejores por Sharpe en selección (2020-2022)")
    by_val = sorted(ranked, key=lambda n: results[n][1][1]["sharpe"], reverse=True)
    pos_sel = {n: i + 1 for i, n in enumerate(ranked)}
    pos_val = {n: i + 1 for i, n in enumerate(by_val)}
    print(f"\n  Correlación de rangos selección→validación (Spearman): "
          f"{statistics.correlation([pos_sel[n] for n in ranked], [pos_val[n] for n in ranked]):+.2f}"
          f" sobre {len(ranked)} variantes")
    print(f"  Bot actual: puesto {pos_sel[actual]} en selección, {pos_val[actual]} en validación")
    table(results, by_val[:10], "Referencia: las 10 mejores en validación (no se pueden elegir así)")

    smooth = {}
    for rule in TP_RULES:
        smooth.update(smoothed(results, rule))
    by_smooth = sorted(smooth, key=smooth.get, reverse=True)
    print("\nSelección robusta: Sharpe de 2020-2022 promediado con los vecinos de la rejilla")
    for n in by_smooth[:8]:
        st = results[n][1]
        print(f"  {n:36} vecindario {smooth[n]:.2f} | propio {st[0]['sharpe']:.2f} → validación "
              f"{st[1]['sharpe']:.2f}")
    print(f"  Bot actual: vecindario {smooth[actual]:.2f}, puesto {by_smooth.index(actual) + 1} "
          f"de {len(by_smooth)}")

    chosen = by_smooth[0]
    print(f"\nElegida en selección: {chosen}")
    key = [name(1.0, 2.0, "forzado"), name(0.75, 1.5, "forzado"), chosen, ranked[0]]
    table(results, [actual] + key, "Candidatas frente al bot actual")
    bootstrap(results, actual, key, same_risk=True)
    yearly(results, [actual] + key)
    print("\n  P&L por símbolo (selección / validación):")
    for label in [actual] + key:
        by = results[label][2]
        print(f"  {label:36} " + "  ".join(f"{s} {v[0]:+7,.0f} / {v[1]:+7,.0f}" for s, v in by.items()))
    print("\n  Motivos de cierre en validación (ops / P&L):")
    for label in [actual, name(1.0, 2.0, "orden")] + key:
        rs = results[label][3]
        print(f"  {label:36} " + "  ".join(f"{r} {v[0]} / {v[1]:+,.0f}" for r, v in sorted(rs.items())))


if __name__ == "__main__":
    main()
