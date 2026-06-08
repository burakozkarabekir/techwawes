"""
Teknik gosterge hesaplari (saf fonksiyonlar, sadece fiyat DataFrame'i alir).

yfinance OHLCV DataFrame'i bekler: Open, High, Low, Close, Volume kolonlari.
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float | None:
    """Wilder RSI(14). Son degeri doner."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period).mean()
    rs = gain / loss.replace(0, pd.NA)
    val = 100 - (100 / (1 + rs))
    last = val.iloc[-1]
    return round(float(last), 1) if pd.notna(last) else None


def atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """Average True Range(14). Mutlak fiyat birimi cinsinden son deger."""
    if len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    val = tr.ewm(alpha=1 / period, min_periods=period).mean().iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def sma(close: pd.Series, period: int) -> float | None:
    if len(close) < period:
        return None
    val = close.rolling(period).mean().iloc[-1]
    return round(float(val), 2) if pd.notna(val) else None


def pct_return(close: pd.Series, days: int) -> float | None:
    """Son `days` islem gunu icindeki yuzde getiri."""
    if len(close) <= days:
        return None
    now, then = close.iloc[-1], close.iloc[-1 - days]
    if pd.isna(now) or pd.isna(then) or then == 0:
        return None
    return round(float((now / then - 1) * 100), 2)


def position_52w(close: pd.Series) -> float | None:
    """Fiyatin 52 haftalik aralikta nerede oldugu (0=dip, 100=tepe)."""
    window = close.tail(252)
    lo, hi = window.min(), window.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return None
    return round(float((close.iloc[-1] - lo) / (hi - lo) * 100), 1)


def swing_levels(df: pd.DataFrame, lookback: int = 60) -> tuple[float | None, float | None]:
    """Yakin destek (son dip) ve direnc (son tepe). (destek, direnc)."""
    window = df.tail(lookback)
    if window.empty:
        return None, None
    return round(float(window["Low"].min()), 2), round(float(window["High"].max()), 2)


def snapshot(df: pd.DataFrame) -> dict:
    """Bir hissenin tum teknik gostergelerini tek sozlukte toplar."""
    close = df["Close"].dropna()
    if close.empty:
        return {}
    price = round(float(close.iloc[-1]), 2)
    ma50, ma200 = sma(close, 50), sma(close, 200)
    sup, res = swing_levels(df)
    return {
        "price": price,
        "rsi": rsi(close),
        "atr": atr(df),
        "ma50": ma50,
        "ma200": ma200,
        "mom_1m": pct_return(close, 21),
        "mom_3m": pct_return(close, 63),
        "pos_52w": position_52w(close),
        "support": sup,
        "resistance": res,
        "above_ma50": (ma50 is not None and price > ma50),
        "above_ma200": (ma200 is not None and price > ma200),
        "golden": (ma50 is not None and ma200 is not None and ma50 > ma200),  # MA50>MA200
    }
