import pandas as pd


def smma(series, period):
    """Compute Smoothed Moving Average (SMMA).

    SMMA uses: SMMA[0] = SMA(first period)
    SMMA[i] = (SMMA[i-1]*(period-1) + price[i]) / period
    """
    vals = list(series)
    if len(vals) < period:
        return pd.Series([None]*len(vals))

    smma_values = [None] * len(vals)
    sma = sum(vals[:period]) / period
    smma_values[period-1] = sma
    prev = sma
    for i in range(period, len(vals)):
        cur = (prev * (period - 1) + vals[i]) / period
        smma_values[i] = cur
        prev = cur

    return pd.Series(smma_values, index=series.index)


def detect_crossovers(short, long):
    """Return indices where short crosses long. Returns list of tuples (idx, type) where type is 'buy' or 'sell'."""
    cross = []
    prev_diff = None
    for i in range(len(short)):
        s = short.iat[i]
        l = long.iat[i]
        if s is None or l is None:
            prev_diff = None
            continue
        diff = s - l
        if prev_diff is None:
            prev_diff = diff
            continue
        if prev_diff <= 0 and diff > 0:
            cross.append((i, 'buy'))
        elif prev_diff >= 0 and diff < 0:
            cross.append((i, 'sell'))
        prev_diff = diff
    return cross
