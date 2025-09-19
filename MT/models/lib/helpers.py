# -*- coding: utf-8 -*-

from decimal import Decimal
from django.utils import timezone

# ──────────────────────────────────────────────────────────────────────────────
# Funciones Helpers
# ──────────────────────────────────────────────────────────────────────────────

def D(x):
    return Decimal(str(x)) if x is not None else None

def to_roll_date(dttm, offset_minutes=0):
    """Convierte un datetime a fecha (UTC) aplicando un 'rollover' por minutos (p.ej. sesión)."""
    if dttm is None:
        return None
    # Asegura zona
    if timezone.is_naive(dttm):
        dttm = timezone.make_aware(dttm, timezone.utc)
    dttm_utc = dttm.astimezone(timezone.utc) + timedelta(minutes=offset_minutes)
    return dttm_utc.date()

def compute_atr_wilder(candles, period=14):
    """
    Añade 'atr' in-place a la lista de velas (orden ascendente).
    Fast-start: si n < period, usa la media simple de TR disponibles para cada barra.
    A partir de 'period-1' usa la RMA de Wilder estándar.
    """
    n = len(candles)
    if n == 0:
        return candles

    # True Range por barra
    trs = []
    prev_close = None
    for i in range(n):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        c = float(candles[i]["close"])
        if prev_close is None:
            tr = h - l
        else:
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c

    atr = [None] * n

    if n < period:
        # FAST-START: para cada i, ATR = media simple de TR[0..i]
        running_sum = 0.0
        for i in range(n):
            running_sum += trs[i]
            atr[i] = running_sum / (i + 1)
    else:
        # Wilder "clásico"
        first = sum(trs[:period]) / period
        atr[period - 1] = first
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + trs[i]) / period

    # Asigna a las velas
    for i in range(n):
        candles[i]["atr"] = float(atr[i]) if atr[i] is not None else None

    return candles        
