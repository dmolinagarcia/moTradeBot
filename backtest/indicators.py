# -*- coding: utf-8 -*-
"""
Indicadores técnicos en Python puro (listas), alineados con la serie de entrada:
cada función devuelve una lista del mismo tamaño con None mientras no hay datos
suficientes. Las fórmulas siguen a TradingView (ta.rma, ta.dmi, ta.atr...) para
que los valores sean comparables con los que el bot lee del scanner.
"""

import math


def sma(xs, n):
    out, acc = [None] * len(xs), 0.0
    for i, x in enumerate(xs):
        acc += x
        if i >= n:
            acc -= xs[i - n]
        if i >= n - 1:
            out[i] = acc / n
    return out


def _smooth(xs, n, alpha):
    """Media exponencial sembrada con la media simple de los n primeros valores."""
    out, prev, count, acc = [None] * len(xs), None, 0, 0.0
    for i, x in enumerate(xs):
        if x is None:
            continue
        if prev is None:
            count += 1
            acc += x
            if count == n:
                prev = acc / n
                out[i] = prev
            continue
        prev = alpha * x + (1 - alpha) * prev
        out[i] = prev
    return out


def ema(xs, n):
    return _smooth(xs, n, 2.0 / (n + 1))


def rma(xs, n):
    """Media de Wilder (ta.rma)."""
    return _smooth(xs, n, 1.0 / n)


def wma(xs, n):
    out = [None] * len(xs)
    den = n * (n + 1) / 2
    for i in range(n - 1, len(xs)):
        window = xs[i - n + 1:i + 1]
        if None in window:
            continue
        out[i] = sum(w * x for w, x in zip(range(1, n + 1), window)) / den
    return out


def hma(xs, n):
    half, root = wma(xs, n // 2), wma(xs, n)
    diff = [2 * a - b if a is not None and b is not None else None for a, b in zip(half, root)]
    return wma(diff, int(math.sqrt(n)))


def vwma(closes, volumes, n):
    pv = sma([c * v for c, v in zip(closes, volumes)], n)
    vv = sma(volumes, n)
    return [a / b if a is not None and b else None for a, b in zip(pv, vv)]


def true_range(h, l, c):
    return [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
                            for i in range(1, len(c))]


def atr(h, l, c, n=14):
    return rma(true_range(h, l, c), n)


def dmi(h, l, c, n=14):
    """(DI+, DI-, ADX) de Wilder, como ta.dmi de TradingView."""
    plus_dm, minus_dm = [0.0], [0.0]
    for i in range(1, len(c)):
        up, down = h[i] - h[i - 1], l[i - 1] - l[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    tr = rma(true_range(h, l, c), n)
    sp, sm = rma(plus_dm, n), rma(minus_dm, n)
    pdi = [100 * p / t if p is not None and t else None for p, t in zip(sp, tr)]
    mdi = [100 * m / t if m is not None and t else None for m, t in zip(sm, tr)]
    dx = [100 * abs(p - m) / (p + m) if p is not None and m is not None and p + m else
          (0.0 if p is not None and m is not None else None) for p, m in zip(pdi, mdi)]
    return pdi, mdi, rma(dx, n)


def rolling_max(xs, n):
    return [max(xs[i - n + 1:i + 1]) if i >= n - 1 else None for i in range(len(xs))]


def rolling_min(xs, n):
    return [min(xs[i - n + 1:i + 1]) if i >= n - 1 else None for i in range(len(xs))]


def rsi(c, n=14):
    gains = [0.0] + [max(c[i] - c[i - 1], 0.0) for i in range(1, len(c))]
    losses = [0.0] + [max(c[i - 1] - c[i], 0.0) for i in range(1, len(c))]
    g, lo = rma(gains, n), rma(losses, n)
    return [None if a is None or b is None else (100.0 if b == 0 else 100 - 100 / (1 + a / b))
            for a, b in zip(g, lo)]


class PartialDMI:
    """
    DI+/DI-/ADX y ATR de Wilder con la vela siguiente a k aún en curso, como los
    calcula TradingView en tiempo real. Con la vela completa coincide con dmi()/atr().
    """

    def __init__(self, h, l, c, n=14):
        self.h, self.l, self.c, self.n = h, l, c, n
        plus_dm, minus_dm = [0.0], [0.0]
        for i in range(1, len(c)):
            up, down = h[i] - h[i - 1], l[i - 1] - l[i]
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
        self.tr, self.pdm, self.mdm = rma(true_range(h, l, c), n), rma(plus_dm, n), rma(minus_dm, n)
        self.adx = dmi(h, l, c, n)[2]

    def at(self, k, hp, lp, cp):
        """(DI+, DI-, ADX, ATR) si la vela k+1 va por máximo hp, mínimo lp y cierre cp."""
        n = self.n
        if k < 1 or k >= len(self.c) or self.adx[k] is None:
            return None
        tr = max(hp - lp, abs(hp - self.c[k]), abs(lp - self.c[k]))
        up, down = hp - self.h[k], self.l[k] - lp
        trs = (self.tr[k] * (n - 1) + tr) / n
        ps = (self.pdm[k] * (n - 1) + (up if up > down and up > 0 else 0.0)) / n
        ms = (self.mdm[k] * (n - 1) + (down if down > up and down > 0 else 0.0)) / n
        if not trs:
            return None
        pdi, mdi = 100 * ps / trs, 100 * ms / trs
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0
        return pdi, mdi, (self.adx[k] * (n - 1) + dx) / n, trs


class PartialRating:
    """ma_rating() con la vela siguiente a k aún en curso (cierre cp, volumen vp)."""

    LENGTHS = (10, 20, 30, 50, 100, 200)

    def __init__(self, c, v):
        self.c = c
        self.sum_c, self.sum_cv, self.sum_v = [0.0], [0.0], [0.0]
        for x, y in zip(c, v):
            self.sum_c.append(self.sum_c[-1] + x)
            self.sum_cv.append(self.sum_cv[-1] + x * y)
            self.sum_v.append(self.sum_v[-1] + y)
        self.ema = {n: ema(c, n) for n in self.LENGTHS}
        w4, w9 = wma(c, 4), wma(c, 9)
        self.hull_raw = [2 * a - b if a is not None and b is not None else None for a, b in zip(w4, w9)]

    def at(self, k, cp, vp):
        if k < 200 or k >= len(self.c):
            return None
        votes = 0
        for n in self.LENGTHS:
            sma_n = (self.sum_c[k + 1] - self.sum_c[k + 2 - n] + cp) / n
            e = self.ema[n][k]
            ema_n = e + 2.0 / (n + 1) * (cp - e)
            votes += (sma_n < cp) - (sma_n > cp) + (ema_n < cp) - (ema_n > cp)
        den = self.sum_v[k + 1] - self.sum_v[k - 18] + vp
        if den:
            vw = (self.sum_cv[k + 1] - self.sum_cv[k - 18] + cp * vp) / den
            votes += (vw < cp) - (vw > cp)
        c = self.c
        w4 = (c[k - 2] + 2 * c[k - 1] + 3 * c[k] + 4 * cp) / 10
        w9 = (sum((j + 1) * c[k - 7 + j] for j in range(8)) + 9 * cp) / 45
        a, b = self.hull_raw[k - 1], self.hull_raw[k]
        if a is not None and b is not None:
            hull = (a + 2 * b + 3 * (2 * w4 - w9)) / 6
            votes += (hull < cp) - (hull > cp)
        return votes / 15


def ma_rating(h, l, c, v):
    """
    Aproximación de "Recommend.MA" de TradingView: media de los votos de 15 medias
    (+1 si la media está por debajo del precio, -1 si está por encima). Ichimoku
    se cuenta como neutral, que es lo más habitual con sus reglas.
    """
    lines = [sma(c, n) for n in (10, 20, 30, 50, 100, 200)]
    lines += [ema(c, n) for n in (10, 20, 30, 50, 100, 200)]
    lines += [vwma(c, v, 20), hma(c, 9)]
    out = [None] * len(c)
    for i in range(len(c)):
        votes = [1 if m[i] < c[i] else (-1 if m[i] > c[i] else 0) for m in lines if m[i] is not None]
        if len(votes) < len(lines):
            continue
        out[i] = sum(votes) / (len(votes) + 1)  # +1: Ichimoku neutral
    return out
