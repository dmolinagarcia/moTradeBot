#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigación de estrategias sobre velas diarias
------------------------------------------------

Motor de cartera común para comparar estrategias de forma justa: mismo capital,
dimensionamiento por riesgo (ATR), comisiones, deslizamiento, funding real de
Binance y límite de exposición total. Las señales se calculan al cierre diario y
se ejecutan en la apertura siguiente; los stops se evalúan dentro del día con el
máximo/mínimo de la vela.

Para no sobreajustar, los parámetros se eligen sólo con el periodo de selección
(hasta IS_END) y se evalúan en el periodo posterior, que la selección no ha visto.

    python backtest/marketdata.py                 # primero: descargar el histórico
    python backtest/research.py                   # compara las familias de estrategias
    python backtest/research.py --universe extended
    python backtest/research.py --validate-bot    # réplica diaria del bot vs replay.py
"""

import argparse
import csv
import math
import os
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import indicators as ind
from marketdata import CORE, DATA_DIR, EXTENDED

DAY_MS = 86_400_000
START = "2020-04-01"    # a partir de aquí todos los indicadores tienen historia suficiente
IS_END = "2023-12-31"   # fin del periodo de selección de parámetros


def day_ms(day):
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def fmt_day(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────────────────────────
# Datos
# ──────────────────────────────────────────────────────────────────────────────
def read_rows(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [tuple(float(x) for x in row) for row in csv.reader(f)]


class Series:
    """Velas diarias de un símbolo, funding diario e indicadores cacheados."""

    def __init__(self, name, symbol):
        self.name, self.symbol = name, symbol
        rows = read_rows(f"{symbol}_1d.csv")
        # Contratos retirados: tras la retirada quedan velas planas sin volumen
        dead = [r[2] == r[3] or r[5] < 1000 for r in rows]
        cut, dead_after = len(rows), 0
        for k in range(len(rows) - 1, -1, -1):
            dead_after += dead[k]
            if dead[k] and dead_after >= 0.98 * (len(rows) - k):
                cut = k
        rows = rows[:cut]
        self.t = [int(r[0]) for r in rows]
        self.o, self.h, self.l, self.c, self.v = ([r[k] for r in rows] for k in range(1, 6))
        self.index = {t: i for i, t in enumerate(self.t)}
        self.funding = defaultdict(float)
        for when, rate in read_rows(f"{symbol}_funding.csv"):
            self.funding[int(when) // DAY_MS * DAY_MS] += rate
        self.ind = {"atr": ind.atr(self.h, self.l, self.c, 14), "adv": ind.sma(self.v, 30)}

    def cached(self, key, fn):
        if key not in self.ind:
            self.ind[key] = fn()
        return self.ind[key]

    def bars_4h(self):
        rows = read_rows(f"{self.symbol}_4h.csv")
        return [int(r[0]) for r in rows], [r[2] for r in rows], [r[3] for r in rows], \
            [r[4] for r in rows], [r[5] for r in rows]


def load_universe(which):
    names = {"core": CORE, "extended": EXTENDED, "all": {**CORE, **EXTENDED}}[which]
    series = [Series(n, s) for n, s in names.items()]
    return [s for s in series if len(s.t) > 60]


# ──────────────────────────────────────────────────────────────────────────────
# Estrategias
# ──────────────────────────────────────────────────────────────────────────────
class Strategy:
    family = ""
    name = ""
    stop = 2.0          # stop inicial en ATR (None: sin stop intradía)
    trail = None        # trailing tipo Chandelier en ATR desde el extremo
    long_only = False
    regime = None       # filtro BTC: largos sólo si BTC > SMA(regime), cortos sólo si está debajo
    every = 1           # evaluar señales cada N días (los stops, siempre)
    reset_after_stop = True  # tras un stop, no reentrar hasta que la señal se reinicie

    def label(self, base):
        extra = (" L" if self.long_only else " LS") + (f" btc{self.regime}" if self.regime else "")
        return base + extra

    def prepare_universe(self, series):
        if self.regime:
            btc = next((s for s in series if s.name == "BTC"), None) or Series("BTC", CORE["BTC"])
            ma = ind.sma(btc.c, self.regime)
            self.btc_up = {t: (c > m if m is not None else None) for t, c, m in zip(btc.t, btc.c, ma)}

    def prepare(self, s):
        pass

    def allowed(self, side, day):
        if self.long_only and side < 0:
            return False
        if self.regime:
            up = self.btc_up.get(day)
            if up is None or (side > 0) != up:
                return False
        return True

    def entry(self, s, i):
        return 0

    def exit(self, s, i, pos):
        return False

    def on_entry(self, s, i, pos, atr):
        pos.extreme = pos.entry
        pos.stop = pos.entry - pos.side * self.stop * atr if self.stop else None

    def on_close(self, s, i, pos):
        if pos.side > 0:
            pos.extreme = max(pos.extreme, s.h[i])
        else:
            pos.extreme = min(pos.extreme, s.l[i])
        a = s.ind["atr"][i]
        if self.trail and a:
            new = pos.extreme - pos.side * self.trail * a
            if pos.stop is None or (new - pos.stop) * pos.side > 0:
                pos.stop = new

    def intraday(self, s, i, pos):
        """Niveles a vigilar durante la vela: [("stop"|"tp", precio), ...]."""
        return [("stop", pos.stop)] if pos.stop is not None else []

    def on_exit(self, s, i, pos, reason):
        pass


class BotActual(Strategy):
    """Réplica diaria de la lógica actual del bot (Strategy.operation, modo normal)."""
    family = "bot"
    stop = None
    reset_after_stop = False  # el bot sólo aplica un día de cooldown

    def __init__(self, limits):
        self.limits = limits
        self.name = "bot_actual"

    def prepare(self, s):
        p, m, _ = s.cached("dmi", lambda: ind.dmi(s.h, s.l, s.c, 14))
        s.ind["pdi"], s.ind["mdi"] = p, m
        s.cached("rating_d", lambda: ind.ma_rating(s.h, s.l, s.c, s.v))

        def rating_4h():
            t4, h4, l4, c4, v4 = s.bars_4h()
            r4 = ind.ma_rating(h4, l4, c4, v4)
            pos = {t: k for k, t in enumerate(t4)}
            last = 20 * 3600 * 1000  # vela de 4h que cierra con el día
            return [r4[pos[t + last]] if t + last in pos else None for t in s.t]
        s.cached("rating_4h", rating_4h)
        s.cool = -1

    def rec(self, s, i):
        p, m = s.ind["pdi"][i], s.ind["mdi"][i]
        rd, r4 = s.ind["rating_d"][i], s.ind["rating_4h"][i]
        if None in (p, m, rd, r4):
            return False
        d = 1 if p > m else (-1 if m > p else 0)
        return d != 0 and (rd + r4) * d > 1.5

    def entry(self, s, i):
        p, m, a = s.ind["pdi"][i], s.ind["mdi"][i], s.ind["atr"][i]
        if i <= s.cool or p is None or m is None or not a or a * 100 / s.c[i] < 2.0:
            return 0
        lb, ls = self.limits.get(s.name, (5, -25))
        if p - m > lb and self.rec(s, i):
            return 1
        if p - m < ls and self.rec(s, i):
            return -1
        return 0

    def on_entry(self, s, i, pos, atr):
        pos.extreme = pos.entry
        pos.state = [pos.entry - pos.side * 2 * atr, pos.entry + pos.side * 4 * atr]  # SL, TP

    def on_close(self, s, i, pos):
        a = s.ind["atr"][i]
        if pos.side > 0:
            pos.extreme = max(pos.extreme, s.h[i])
        else:
            pos.extreme = min(pos.extreme, s.l[i])
        if not a:
            return
        stop_init, sl, tp = 2 * a, pos.state[0], pos.state[1]
        if (s.c[i] - pos.entry) * pos.side / stop_init >= 0.7 and (sl - pos.entry) * pos.side < 0:
            sl = pos.entry                                        # break-even
        new = pos.extreme - pos.side * stop_init                  # Chandelier 2 ATR
        if (new - sl) * pos.side > 0:
            sl = new
        base_tp = pos.entry + pos.side * 2 * stop_init            # TP 2R, sólo se aleja
        if (base_tp - tp) * pos.side > 0:
            tp = base_tp
        pos.state = [sl, tp]

    def intraday(self, s, i, pos):
        # SL y TP sólo cuentan cuando TradingView deja de recomendar la operación
        return [] if self.rec(s, i - 1) else [("stop", pos.state[0]), ("tp", pos.state[1])]

    def exit(self, s, i, pos):
        lb, ls = self.limits.get(s.name, (5, -25))
        diff = s.ind["pdi"][i] - s.ind["mdi"][i]
        return diff < lb * 0.85 if pos.side > 0 else diff > ls * 0.85

    def on_exit(self, s, i, pos, reason):
        if reason in ("stop", "tp"):
            s.cool = i  # cooldown de un día


class Donchian(Strategy):
    """Ruptura de canal: entra al superar el máximo de n_in días, sale al perder el mínimo de n_out."""
    family = "donchian"

    def __init__(self, n_in, n_out, long_only=False, regime=None, stop=2.0, trail=None):
        self.n_in, self.n_out, self.long_only, self.regime = n_in, n_out, long_only, regime
        self.stop, self.trail = stop, trail
        self.name = self.label(f"donchian {n_in}/{n_out}" + (f" tr{trail}" if trail else ""))

    def prepare(self, s):
        for n in (self.n_in, self.n_out):
            s.cached(f"hh{n}", lambda n=n: ind.rolling_max(s.h, n))
            s.cached(f"ll{n}", lambda n=n: ind.rolling_min(s.l, n))

    def entry(self, s, i):
        hh, ll = s.ind[f"hh{self.n_in}"][i - 1], s.ind[f"ll{self.n_in}"][i - 1]
        if hh is None:
            return 0
        return 1 if s.c[i] > hh else (-1 if s.c[i] < ll else 0)

    def exit(self, s, i, pos):
        if pos.side > 0:
            return s.c[i] < s.ind[f"ll{self.n_out}"][i - 1]
        return s.c[i] > s.ind[f"hh{self.n_out}"][i - 1]


class EmaCross(Strategy):
    """Cruce de medias exponenciales; sale con el cruce contrario (stop sólo de emergencia)."""
    family = "ema"
    reset_after_stop = False

    def __init__(self, fast, slow, long_only=False, regime=None, stop=None):
        self.fast, self.slow, self.long_only, self.regime = fast, slow, long_only, regime
        self.stop = stop
        self.name = self.label(f"ema {fast}/{slow}" + (f" sl{stop:g}" if stop else ""))

    def prepare(self, s):
        for n in (self.fast, self.slow):
            s.cached(f"ema{n}", lambda n=n: ind.ema(s.c, n))

    def entry(self, s, i):
        f, sl = s.ind[f"ema{self.fast}"][i], s.ind[f"ema{self.slow}"][i]
        if f is None or sl is None:
            return 0
        return 1 if f > sl else (-1 if f < sl else 0)

    def exit(self, s, i, pos):
        return self.entry(s, i) != pos.side


class TSMom(Strategy):
    """Momentum temporal: posición en el sentido del rendimiento de los últimos L días."""
    family = "tsmom"
    every = 7
    reset_after_stop = False

    def __init__(self, lookback, long_only=False, regime=None, stop=None):
        self.lookback, self.long_only, self.regime, self.stop = lookback, long_only, regime, stop
        self.name = self.label(f"tsmom {lookback}d" + (f" sl{stop:g}" if stop else ""))

    def entry(self, s, i):
        if i < self.lookback:
            return 0
        r = s.c[i] / s.c[i - self.lookback] - 1
        return 1 if r > 0 else (-1 if r < 0 else 0)

    def exit(self, s, i, pos):
        return self.entry(s, i) != pos.side


class XSMom(Strategy):
    """Momentum transversal: cada semana, largo en las top_k monedas con mejor rendimiento."""
    family = "xsmom"
    every = 7
    long_only = True
    reset_after_stop = False

    def __init__(self, lookback, top_k, regime=None, stop=None):
        # lookback: días, o una tupla de días para puntuar con la media de sus rendimientos
        self.lookbacks = lookback if isinstance(lookback, tuple) else (lookback,)
        self.top_k, self.regime, self.stop = top_k, regime, stop
        days = "+".join(str(n) for n in self.lookbacks)
        self.name = self.label(f"xsmom {days}d top{top_k}" + (f" sl{stop:g}" if stop else ""))
        self.key = "rank" + days

    def prepare_universe(self, series):
        super().prepare_universe(series)
        by_day = defaultdict(list)
        longest = max(self.lookbacks)
        for s in series:
            if self.key in s.ind:
                continue
            s.ind[self.key] = [None] * len(s.t)
            for i in range(longest, len(s.t)):
                score = statistics.mean(s.c[i] / s.c[i - n] - 1 for n in self.lookbacks)
                by_day[s.t[i]].append((score, s, i))
        for rows in by_day.values():
            rows.sort(key=lambda r: r[0], reverse=True)
            for rank, (score, s, i) in enumerate(rows, 1):
                s.ind[self.key][i] = (rank, score)

    def entry(self, s, i):
        r = s.ind[self.key][i]
        return 1 if r and r[0] <= self.top_k and r[1] > 0 else 0

    def exit(self, s, i, pos):
        return self.entry(s, i) != 1


class RsiDip(Strategy):
    """Reversión a la media en tendencia: compra RSI bajo por encima de la SMA200."""
    family = "rsi"
    long_only = True

    def __init__(self, low, exit_level, max_days=10, regime=None):
        self.low, self.exit_level, self.max_days, self.regime = low, exit_level, max_days, regime
        self.name = self.label(f"rsi<{low} >{exit_level}")

    def prepare(self, s):
        s.cached("rsi14", lambda: ind.rsi(s.c, 14))
        s.cached("sma200", lambda: ind.sma(s.c, 200))

    def entry(self, s, i):
        r, m = s.ind["rsi14"][i], s.ind["sma200"][i]
        return 1 if r is not None and m is not None and s.c[i] > m and r < self.low else 0

    def exit(self, s, i, pos):
        return s.ind["rsi14"][i] > self.exit_level or i - pos.i_entry >= self.max_days


# ──────────────────────────────────────────────────────────────────────────────
# Motor de cartera
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Config:
    equity: float = 30000.0
    risk_pct: float = 0.01        # pérdida si el precio recorre unit_atr ATR en contra
    unit_atr: float = 2.0
    pos_cap: float = 1.0          # nocional máximo por posición (× capital)
    gross_cap: float = 3.0        # nocional total máximo (× capital)
    taker: float = 0.0005
    slippage: float = 0.0005
    stop_penetration: float = 0.25  # fracción del recorrido más allá del stop que se pierde
    funding: bool = True
    compound: bool = True
    leverage: float = 3.0         # margen aislado: liquidación si el precio recorre ~1/leverage en
                                  # contra; la exposición total tampoco puede superar el apalancamiento
    maintenance: float = 0.005    # margen de mantenimiento (fracción del nocional)


class Pos:
    __slots__ = ("sym", "side", "units", "entry", "i_entry", "t_entry", "stop", "extreme",
                 "state", "fees", "funding")


@dataclass
class Trade:
    sym: str
    side: int
    t_open: int
    t_close: int
    notional: float
    pnl: float        # neto de comisiones y funding
    fees: float
    funding: float
    reason: str


class Result:
    def __init__(self, strategy, curve, trades, exposure):
        self.strategy, self.curve, self.trades, self.exposure = strategy, curve, trades, exposure


def run(strategy, series, cfg, start=START, end=None):
    by_name = {s.name: s for s in series}
    strategy.prepare_universe(series)
    for s in series:
        strategy.prepare(s)
    first, last = day_ms(start), day_ms(end) if end else max(s.t[-1] for s in series)
    gross_cap = min(cfg.gross_cap, cfg.leverage) if cfg.leverage else cfg.gross_cap

    balance = cfg.equity
    positions, pending, blocked = {}, {}, {}
    curve, trades, exposure = [], [], []
    last_close = {}

    def close(pos, raw_px, reason, day):
        nonlocal balance
        px = raw_px * (1 - pos.side * cfg.slippage)
        fee = cfg.taker * pos.units * px
        gross = pos.side * pos.units * (px - pos.entry)
        balance += gross - fee
        trades.append(Trade(pos.sym, pos.side, pos.t_entry, day, pos.units * pos.entry,
                            gross - fee - pos.fees - pos.funding, pos.fees + fee, pos.funding, reason))
        del positions[pos.sym]

    for day in range(first, last + 1, DAY_MS):
        equity_prev = curve[-1][1] if curve else cfg.equity
        base = equity_prev if cfg.compound else cfg.equity

        # 1) Apertura: salidas pendientes, después entradas por orden de liquidez
        entries = []
        for sym, (action, side) in pending.items():
            s = by_name[sym]
            i = s.index.get(day)
            if i is None:
                continue
            if action in ("exit", "flip") and sym in positions:
                close(positions[sym], s.o[i], "signal", day)
            if action in ("enter", "flip"):
                entries.append((s.ind["adv"][i - 1] or 0, sym, side))
        pending = {}
        gross = sum(p.units * last_close.get(p.sym, p.entry) for p in positions.values())
        for _, sym, side in sorted(entries, reverse=True):
            s = by_name[sym]
            i = s.index[day]
            a = s.ind["atr"][i - 1]
            if not a:
                continue
            px = s.o[i] * (1 + side * cfg.slippage)
            wanted = base * cfg.risk_pct / (cfg.unit_atr * a) * px
            notional = min(wanted, cfg.pos_cap * base, gross_cap * base - gross)
            if notional < 0.25 * wanted:
                continue
            pos = Pos()
            pos.sym, pos.side, pos.units, pos.entry = sym, side, notional / px, px
            pos.i_entry, pos.t_entry, pos.funding = i, day, 0.0
            pos.fees = cfg.taker * notional
            balance -= pos.fees
            strategy.on_entry(s, i, pos, a)
            positions[sym] = pos
            gross += notional

        # 2) Durante la vela: stops, take profits y liquidaciones
        for sym, pos in list(positions.items()):
            s = by_name[sym]
            i = s.index.get(day)
            if i is None:
                if day > s.t[-1]:  # deslistado: se cierra al último precio
                    close(pos, s.c[-1], "delist", day)
                continue
            levels = strategy.intraday(s, i, pos)
            if cfg.leverage:
                # La liquidación va detrás de cualquier stop: sólo actúa si el stop no existe
                # o si el precio lo atraviesa hasta el precio de liquidación
                liq = pos.entry * (1 - pos.side * (1 / cfg.leverage - cfg.maintenance))
                levels = levels + [("liquidation", liq)]
            for kind, level in levels:
                o, h, l = s.o[i], s.h[i], s.l[i]
                if kind == "liquidation":
                    if (o - level) * pos.side <= 0 or (l if pos.side > 0 else h) * pos.side <= level * pos.side:
                        close(pos, level, kind, day)
                        strategy.on_exit(s, i, pos, kind)
                        break
                    continue
                if kind == "stop":
                    if (o - level) * pos.side <= 0:
                        fill = o
                    elif pos.side > 0 and l <= level:
                        fill = level - cfg.stop_penetration * (level - l)
                    elif pos.side < 0 and h >= level:
                        fill = level + cfg.stop_penetration * (h - level)
                    else:
                        continue
                    if cfg.leverage:  # la pérdida no puede superar el margen
                        fill = max(fill, liq) if pos.side > 0 else min(fill, liq)
                else:
                    if (o - level) * pos.side >= 0:
                        fill = o
                    elif (pos.side > 0 and h >= level) or (pos.side < 0 and l <= level):
                        fill = level
                    else:
                        continue
                close(pos, fill, kind, day)
                strategy.on_exit(s, i, pos, kind)
                if kind == "stop" and strategy.reset_after_stop:
                    blocked[sym] = pos.side
                break

        # 3) Cierre: funding, valoración y señales para la apertura siguiente
        unreal = gross_now = 0.0
        for sym, pos in positions.items():
            s = by_name[sym]
            i = s.index.get(day)
            c = s.c[i] if i is not None else last_close.get(sym, pos.entry)
            last_close[sym] = c
            if cfg.funding and i is not None:
                f = pos.side * pos.units * c * s.funding.get(day, 0.0)
                balance -= f
                pos.funding += f
            unreal += pos.side * pos.units * (c - pos.entry)
            gross_now += pos.units * c
        equity = balance + unreal
        curve.append((day, equity))
        exposure.append(gross_now / equity if equity > 0 else 0.0)
        if equity <= 0:
            break

        for s in series:
            i = s.index.get(day)
            if i is None or i < 1:
                continue
            last_close[s.name] = s.c[i]
            pos = positions.get(s.name)
            if pos:
                strategy.on_close(s, i, pos)
            if strategy.every > 1 and (day // DAY_MS) % strategy.every:
                continue
            sig = strategy.entry(s, i)
            if pos:
                if sig == -pos.side and strategy.allowed(sig, day):
                    pending[s.name] = ("flip", sig)
                elif strategy.exit(s, i, pos):
                    pending[s.name] = ("exit", 0)
                    strategy.on_exit(s, i, pos, "signal")
            else:
                b = blocked.get(s.name)
                if b is not None:
                    if sig == b:
                        continue
                    del blocked[s.name]
                if sig and strategy.allowed(sig, day):
                    pending[s.name] = ("enter", sig)

    return Result(strategy, curve, trades, exposure)


# ──────────────────────────────────────────────────────────────────────────────
# Métricas
# ──────────────────────────────────────────────────────────────────────────────
def stats(curve, start=None, end=None):
    lo = day_ms(start) if start else curve[0][0]
    hi = day_ms(end) if end else curve[-1][0]
    pts = [(d, e) for d, e in curve if lo <= d <= hi]
    if len(pts) < 30:
        return None
    rets = [pts[k][1] / pts[k - 1][1] - 1 for k in range(1, len(pts)) if pts[k - 1][1] > 0]
    years = (pts[-1][0] - pts[0][0]) / DAY_MS / 365.25
    total = pts[-1][1] / pts[0][1]
    peak, dd = pts[0][1], 0.0
    for _, e in pts:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    sd = statistics.pstdev(rets)
    cagr = total ** (1 / years) - 1 if total > 0 else -1.0
    return {
        "cagr": cagr,
        "sharpe": statistics.mean(rets) / sd * math.sqrt(365) if sd else 0.0,
        "maxdd": dd,
        "calmar": cagr / dd if dd else 0.0,
        "total": total - 1,
    }


def trade_stats(trades, start=None, end=None):
    lo = day_ms(start) if start else 0
    hi = day_ms(end) if end else 1 << 62
    sel = [t for t in trades if lo <= t.t_close <= hi]
    wins = [t.pnl for t in sel if t.pnl > 0]
    losses = [t.pnl for t in sel if t.pnl <= 0]
    return {
        "n": len(sel),
        "win": len(wins) / len(sel) if sel else 0.0,
        "pf": sum(wins) / -sum(losses) if sum(losses) < 0 else float("inf"),
        "days": statistics.mean((t.t_close - t.t_open) / DAY_MS for t in sel) if sel else 0.0,
        "fees": sum(t.fees for t in sel),
        "funding": sum(t.funding for t in sel),
    }


def buy_and_hold(series, names, start=START, end=None):
    """Curva de comprar y mantener (sin costes) a partes iguales, rebalanceo diario."""
    first, last = day_ms(start), day_ms(end) if end else max(s.t[-1] for s in series)
    pool = [s for s in series if s.name in names]
    equity, curve = 30000.0, []
    for day in range(first, last + 1, DAY_MS):
        rets = []
        for s in pool:
            i = s.index.get(day)
            if i is not None and i > 0:
                rets.append(s.c[i] / s.c[i - 1] - 1)
        equity *= 1 + (statistics.mean(rets) if rets else 0.0)
        curve.append((day, equity))
    return curve


# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de estrategias
# ──────────────────────────────────────────────────────────────────────────────
def bot_limits(db="db.sqlite3"):
    """limitBuy/limitSell actuales de cada estrategia del bot (si hay BD)."""
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    return {u: (lb, ls) for u, lb, ls in
            con.execute("select utility, limitBuy, limitSell from MT_strategy")}


def catalog():
    out = [BotActual(bot_limits())]
    for lo in (False, True):
        for rg in (None, 200):
            for n_in, n_out in ((20, 10), (55, 20), (100, 50)):
                out.append(Donchian(n_in, n_out, long_only=lo, regime=rg))
            for fast, slow in ((10, 50), (20, 100), (50, 200)):
                out.append(EmaCross(fast, slow, long_only=lo, regime=rg))
            for lb in (30, 90, 180):
                out.append(TSMom(lb, long_only=lo, regime=rg))
    for rg in (None, 200):
        for lb in (30, 90):
            for k in (3, 6):
                out.append(XSMom(lb, k, regime=rg))
        for low, ex in ((30, 50), (35, 60)):
            out.append(RsiDip(low, ex, regime=rg))
    return out


def neighborhood():
    """Parámetros cercanos a las finalistas: si sólo funciona un valor exacto, es ruido."""
    out = []
    for lb in (14, 21, 30, 45, 60):
        out.append(TSMom(lb, long_only=True, regime=200))
        out.append(TSMom(lb, long_only=False))
    for fast, slow in ((5, 20), (10, 30), (10, 50), (15, 60), (20, 60), (20, 100)):
        out.append(EmaCross(fast, slow, long_only=True, regime=200))
    for n_in, n_out in ((10, 5), (15, 7), (20, 10), (30, 15), (40, 20)):
        out.append(Donchian(n_in, n_out, long_only=True, regime=200))
    for lb in (14, 21, 30, 45, 60, (14, 21, 30)):
        for k in (2, 3, 4, 6):
            out.append(XSMom(lb, k, regime=200))
    # Con stop de emergencia (en vivo sería una orden stop en el exchange)
    out += [EmaCross(10, 50, long_only=True, regime=200, stop=4), TSMom(30, long_only=True, regime=200, stop=4),
            TSMom(30, stop=4), XSMom(30, 3, regime=200, stop=4), XSMom(30, 6, regime=200, stop=4)]
    return out


def find(names):
    pool = {s.name: s for s in catalog() + neighborhood()}
    return [pool[n.strip()] for n in names.split(",")]


# Operaciones del replay minuto a minuto de la lógica actual (replay.py), mismo periodo
REPLAY_ACTUAL = {"23 estrategias": 23137, "7 activas": 7748}
ACTIVE = {"BTC", "ETH", "XRP", "DOGE", "SOL", "BNB", "ADA"}


def robust(strategies, series_core):
    """Misma estrategia bajo supuestos distintos: el resultado no debería depender de uno."""
    scenarios = [
        ("base (aislado 3x)", Config(), "core"),
        ("aislado 2x", Config(leverage=2.0), "core"),
        ("aislado 1x", Config(leverage=1.0), "core"),
        ("sin liquidación", Config(leverage=None), "core"),
        ("deslizamiento 0,15%", Config(slippage=0.0015), "core"),
        ("riesgo 0,5%, exposición 1,5x", Config(risk_pct=0.005, gross_cap=1.5), "core"),
        ("otras monedas (ampliado)", Config(), "extended"),
        ("todas las monedas", Config(), "all"),
    ]
    universes = {"core": series_core}
    for strat in strategies:
        print(f"{strat.name}")
        for label, cfg, uni in scenarios:
            if uni not in universes:
                universes[uni] = load_universe(uni)
            res = run(strat, universes[uni], cfg)
            liq = sum(1 for t in res.trades if t.reason == "liquidation")
            print(f"  {label:30} selección {fmt_stats(stats(res.curve, end=IS_END))} │ "
                  f"evaluación {fmt_stats(stats(res.curve, start=IS_END))} │ liquidaciones {liq}")
        print()


def window(strategies, series, start):
    """Mismo periodo y supuestos que replay.py: capital fijo de 30.000 y 1,5% de riesgo."""
    cfg = Config(risk_pct=0.015, gross_cap=100, pos_cap=100, compound=False, leverage=None)
    pools = {"23 estrategias": [s for s in series if s.name != "SHIB"],
             "7 activas": [s for s in series if s.name in ACTIVE]}
    print(f"Desde {start}, capital fijo {cfg.equity:,.0f}, riesgo {cfg.risk_pct:.1%} "
          f"(bot actual en replay: " + ", ".join(f"{k} {v:+,}" for k, v in REPLAY_ACTUAL.items()) + ")")
    for strat in strategies:
        cells = []
        for label, pool in pools.items():
            res = run(strat, pool, cfg, start=start)
            peak, dd = cfg.equity, 0.0
            for _, e in res.curve:
                peak = max(peak, e)
                dd = max(dd, peak - e)
            cells.append(f"{label} {res.curve[-1][1] - cfg.equity:+8,.0f} (maxDD {dd:,.0f}, "
                         f"{len(res.trades)} ops)")
        print(f"  {strat.name:30} " + " │ ".join(cells))


def bot_hourly_rows(s, limits, btc_up=None):
    """
    Ciclos horarios con los datos que vería el bot: DI/ADX y Recommend.MA sobre la
    vela diaria (y de 4h) aún en curso, y el ATR de sus propias velas muestreadas.
    Mismo formato que las filas de replay.py, para reutilizar su simulador; con
    btc_up añade el régimen de BTC del día anterior (+1 / -1) en la posición 14.
    """
    hourly = read_rows(f"{s.symbol}_1h.csv")
    if not hourly:
        return []
    t4, _, _, c4, v4 = s.bars_4h()
    idx4 = {t: k for k, t in enumerate(t4)}
    dmi_d, rating_d, rating_4h = ind.PartialDMI(s.h, s.l, s.c), ind.PartialRating(s.c, s.v), \
        ind.PartialRating(c4, v4)
    # El bot calcula el ATR con velas diarias hechas con sus muestras de precio
    bh, bl, bc, bidx = [], [], [], {}
    for r in hourly:
        d = int(r[0]) // DAY_MS * DAY_MS
        if d not in bidx:
            bidx[d] = len(bc)
            bh.append(r[4]), bl.append(r[4]), bc.append(r[4])
        k = bidx[d]
        bh[k], bl[k], bc[k] = max(bh[k], r[4]), min(bl[k], r[4]), r[4]
    atr_bot = ind.PartialDMI(bh, bl, bc)
    lb, ls = limits.get(s.name, (5, -25))
    four = 4 * 3600 * 1000
    rows, day, block = [], None, None
    for t, _, h, l, c, v in hourly:
        t = int(t)
        d = t // DAY_MS * DAY_MS
        if d != day:
            day, hp, lp, vp, chp, clp = d, h, l, 0.0, c, c
            k, kb = s.index.get(d - DAY_MS), bidx.get(d - DAY_MS)
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
        row = ((t + 3600 * 1000) / 1000, c, x[2], x[0], x[1], rd, r4, xb[3], 0, 0, lb, ls, 1, 0)
        if btc_up is not None:
            up = btc_up.get(d - DAY_MS)
            row += (0 if up is None else (1 if up else -1),)
        rows.append(row)
    return rows


def bot_leverages(db="db.sqlite3"):
    if not os.path.exists(db):
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    return dict(con.execute("select utility, leverage from MT_strategy"))


def bot_hourly(series, candidates):
    """El bot actual, hora a hora durante 6,5 años, frente a las candidatas en el mismo marco."""
    import replay as rp
    from dataclasses import replace
    limits, levs = bot_limits(), bot_leverages()
    btc = next(s for s in series if s.name == "BTC")
    btc_up = {t: c > m for t, c, m in zip(btc.t, btc.c, ind.sma(btc.c, 200)) if m is not None}
    variants = [("bot actual (horario)", rp.ACTUAL),
                ("bot + filtro BTC (horario)", replace(rp.ACTUAL, btc_regime=True))]
    costs = rp.Costs(slippage=0.0005, funding_8h=0.0, liq_frac=1e9, fill="logged")
    cfg = Config(risk_pct=0.015, gross_cap=100, pos_cap=100, compound=False, leverage=None)
    pools = {"23 estrategias": [s for s in series if s.name != "SHIB"],
             "7 activas": [s for s in series if s.name in ACTIVE]}
    periods = [("selección", START, IS_END), ("evaluación", "2024-01-01", None),
               ("último año", "2025-09-15", None)]
    days = range(day_ms(START), max(s.t[-1] for s in series) + 1, DAY_MS)
    last_year = day_ms("2025-09-15") / 1000

    # P&L acumulado diario de cada estrategia del bot, con el funding real descontado
    bot_pnl, bot_ops, bot_ops_year = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for s in pools["23 estrategias"]:
        lev = levs.get(s.name, 4)
        rows = bot_hourly_rows(s, limits, btc_up)
        for vname, params in variants:
            trades, curve = rp.simulate(rows, s.name, lev, params, costs, cfg.equity)
            pnl_at = {hour * 3600 * 1000 // DAY_MS * DAY_MS: value for hour, value in curve}
            funding = defaultdict(float)
            for t in trades:
                units = t.bet * lev / t.entry
                for d in range(int(t.t_open * 1000) // DAY_MS * DAY_MS,
                               int(t.t_close * 1000) // DAY_MS * DAY_MS, DAY_MS):
                    i = s.index.get(d)
                    if i is not None:
                        funding[d] += t.side * units * s.c[i] * s.funding.get(d, 0.0)
            pnl, acc_f, series_pnl = 0.0, 0.0, []
            for d in days:
                pnl = pnl_at.get(d, pnl)
                acc_f += funding.get(d, 0.0)
                series_pnl.append(pnl - acc_f)
            bot_pnl[vname][s.name], bot_ops[vname][s.name] = series_pnl, len(trades)
            bot_ops_year[vname][s.name] = sum(1 for t in trades if t.t_open >= last_year)

    print("Marco de replay.py: capital fijo 30.000, riesgo 1,5% por posición, sin límite de exposición")
    for label, pool in pools.items():
        names = [s.name for s in pool]
        first = variants[0][0]
        print(f"\n{label}: replay minuto a minuto del último año {REPLAY_ACTUAL[label]:+,}; "
              f"réplica horaria {sum(bot_ops_year[first][n] for n in names)} operaciones en ese año")
        results = []
        for vname, _ in variants:
            curve = [(d, cfg.equity + sum(bot_pnl[vname][n][j] for n in names)) for j, d in enumerate(days)]
            results.append((vname, curve, sum(bot_ops[vname][n] for n in names)))
        for strat in candidates:
            res = run(strat, pool, cfg)
            results.append((strat.name, res.curve, len(res.trades)))
        print(f"  {'estrategia':30} " + " │ ".join(f"{p:^27}" for p, _, _ in periods) + " │ ops")
        for name, curve, n in results:
            cells = []
            for _, a, b in periods:
                pts = [(d, e) for d, e in curve if day_ms(a) <= d <= (day_ms(b) if b else days[-1])]
                pnl = pts[-1][1] - pts[0][1]
                rets = [(pts[j][1] - pts[j - 1][1]) / cfg.equity for j in range(1, len(pts))]
                sd = statistics.pstdev(rets)
                sh = statistics.mean(rets) / sd * math.sqrt(365) if sd else 0.0
                peak, dd = pts[0][1], 0.0
                for _, e in pts:
                    peak = max(peak, e)
                    dd = max(dd, peak - e)
                cells.append(f"{pnl:+9,.0f} Sh {sh:4.2f} DD {dd:6,.0f}")
            print(f"  {name:30} " + " │ ".join(cells) + f" │ {n}")


def pct(x):
    return f"{x * 100:+.0f}%" if x is not None else "-"


def fmt_stats(st):
    if not st:
        return f"{'-':>6} {'-':>6} {'-':>6}"
    return f"{pct(st['cagr']):>6} {st['sharpe']:6.2f} {pct(-st['maxdd']):>6}"


def sharpe(st):
    return st["sharpe"] if st else -9.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--universe", choices=("core", "extended", "all"), default="core")
    ap.add_argument("--risk", type=float, default=Config.risk_pct)
    ap.add_argument("--gross-cap", type=float, default=Config.gross_cap)
    ap.add_argument("--slippage", type=float, default=Config.slippage)
    ap.add_argument("--leverage", type=float, default=Config.leverage,
                    help="apalancamiento del margen aislado (0: sin modelo de liquidación)")
    ap.add_argument("--only", help="sólo estrategias cuyo nombre contenga este texto")
    ap.add_argument("--neighborhood", action="store_true", help="parámetros cercanos a las finalistas")
    ap.add_argument("--robust", help="estrategias (nombres separados por comas) a someter a escenarios")
    ap.add_argument("--window", help="fecha inicial: comparar --robust con el bot en replay.py")
    ap.add_argument("--bot-hourly", action="store_true",
                    help="bot actual hora a hora (velas de 1h) frente a --robust, marco de replay.py")
    ap.add_argument("--validate-bot", action="store_true",
                    help="réplica del bot en el periodo de replay.py, con sus mismos supuestos")
    args = ap.parse_args()

    series = load_universe(args.universe)
    print(f"Universo {args.universe}: {len(series)} símbolos | selección {START} → {IS_END} | "
          f"evaluación {IS_END} → {fmt_day(max(s.t[-1] for s in series))}\n")

    if args.validate_bot:
        cfg = Config(risk_pct=0.015, gross_cap=100, pos_cap=100, compound=False)
        names = {"BTC", "ETH", "XRP", "DOGE", "SOL", "BNB", "ADA"}
        for label, pool in (("23 estrategias", [s for s in series if s.name != "SHIB"]),
                            ("7 activas", [s for s in series if s.name in names])):
            res = run(BotActual(bot_limits()), pool, cfg, start="2025-09-15")
            ts = trade_stats(res.trades)
            print(f"bot_actual diario, {label}: P&L {res.curve[-1][1] - cfg.equity:+,.0f}, "
                  f"{ts['n']} operaciones, acierto {ts['win']:.0%}, PF {ts['pf']:.2f}")
        return

    if args.bot_hourly:
        bot_hourly(series, find(args.robust) if args.robust else [])
        return
    if args.window:
        window(find(args.robust) + [BotActual(bot_limits())], series, args.window)
        return
    if args.robust:
        robust(find(args.robust), series)
        return

    cfg = Config(risk_pct=args.risk, gross_cap=args.gross_cap, slippage=args.slippage,
                 leverage=args.leverage or None)
    strategies = neighborhood() if args.neighborhood else catalog()
    strategies = [s for s in strategies if not args.only or args.only in s.name]
    results = []
    for strat in strategies:
        res = run(strat, series, cfg)
        res.is_ = stats(res.curve, end=IS_END)
        res.oos = stats(res.curve, start=IS_END)
        res.ts = trade_stats(res.trades)
        results.append(res)

    # Referencias sin costes
    bench = [("BTC comprar y mantener", buy_and_hold(series, {"BTC"})),
             ("Universo comprar y mantener", buy_and_hold(series, {s.name for s in series}))]

    header = (f"{'estrategia':30} {'CAGR':>6} {'Sharpe':>6} {'MaxDD':>6} │ {'CAGR':>6} "
              f"{'Sharpe':>6} {'MaxDD':>6} │ {'ops/año':>7} {'expos.':>6}")
    print(f"{'':30} {'── selección ──':^22} │ {'── evaluación ──':^22} │")
    print(header)
    print("─" * len(header))
    years = (results[0].curve[-1][0] - results[0].curve[0][0]) / DAY_MS / 365.25
    family = None
    for res in sorted(results, key=lambda r: (r.strategy.family, -sharpe(r.is_))):
        if res.strategy.family != family:
            family = res.strategy.family
            print(f"[{family}]")
        print(f"{res.strategy.name:30} {fmt_stats(res.is_)} │ {fmt_stats(res.oos)} │ "
              f"{res.ts['n'] / years:7.0f} {statistics.mean(res.exposure):6.2f}")
    for label, curve in bench:
        print(f"{label:30} {fmt_stats(stats(curve, end=IS_END))} │ "
              f"{fmt_stats(stats(curve, start=IS_END))} │")
    print()

    # Mejor de cada familia según el periodo de selección, y cómo le fue después
    print("Mejor configuración de cada familia en selección → resultado en evaluación")
    by_family = defaultdict(list)
    for res in results:
        by_family[res.strategy.family].append(res)
    picks = []
    for fam, group in by_family.items():
        best = max(group, key=lambda r: sharpe(r.is_))
        picks.append(best)
        print(f"  {fam:9} {best.strategy.name:30} Sharpe {sharpe(best.is_):.2f} → "
              f"{sharpe(best.oos):.2f} ({fmt_stats(best.oos).split()[0]} CAGR); mediana de la "
              f"familia en evaluación {statistics.median(sharpe(r.oos) for r in group):.2f}")
    print()

    # Rentabilidad por año de las elegidas
    yrs = sorted({fmt_day(d)[:4] for d, _ in picks[0].curve})
    print("Rentabilidad anual:")
    print(f"  {'':30} " + " ".join(f"{y:>6}" for y in yrs))
    for res in picks:
        row = []
        for y in yrs:
            st = stats(res.curve, f"{y}-01-01", f"{y}-12-31")
            row.append(pct(st["total"]) if st else "-")
        print(f"  {res.strategy.name:30} " + " ".join(f"{x:>6}" for x in row))
    for label, curve in bench:
        row = []
        for y in yrs:
            st = stats(curve, f"{y}-01-01", f"{y}-12-31")
            row.append(pct(st["total"]) if st else "-")
        print(f"  {label:30} " + " ".join(f"{x:>6}" for x in row))


if __name__ == "__main__":
    main()
