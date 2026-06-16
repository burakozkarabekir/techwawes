"""
Asama 4 - Sektorel tarama motoru.

Iki sinyal uretir ve bir "tarama sonuclari" tablosunda toplar:
  1. BIRIKIM (accumulation): fiyat yatay seyrederken hacmi belirgin artan hisseler
     (sessiz toplama isareti).
  2. GOLDEN / DEATH CROSS: 50 gunluk MA'nin 200 gunluk MA'yi yukari (golden) ya da
     asagi (death) kesmesi son birkac gunde gerceklestiyse sinyal.

Sinyal fonksiyonlari SAF (tek hisse OHLCV DataFrame'i alir) -> birim test edilebilir.
scan(market) tum evreni tek batch indirir, sinyalleri toplar; piyasa basina cache.
"""
from __future__ import annotations

import sys
import time

import pandas as pd
import yfinance as yf

from . import markets

_CACHE: dict[str, dict] = {}   # {market: {"ts":.., "data":..}}
_TTL = 1800  # 30 dk


# ----------------------------------------------------------------------------- saf sinyaller
def accumulation_signal(
    df: pd.DataFrame,
    flat_window: int = 25,
    max_range_pct: float = 10.0,
    min_vol_ratio: float = 1.3,
) -> dict | None:
    """Fiyat yatay + hacim artan mi? Oyleyse sinyal sozlugu, degilse None.

    - "yatay": son flat_window gunde (en yuksek-en dusuk)/ortalama <= max_range_pct%
    - "hacim artan": son yarinin ort. hacmi, onceki yarinin ort. hacminin
      >= min_vol_ratio kati.
    """
    if df is None or df.empty or "Close" not in df or "Volume" not in df:
        return None
    close = df["Close"].dropna()
    vol = df["Volume"].dropna()
    if len(close) < flat_window or len(vol) < flat_window:
        return None

    c = close.tail(flat_window)
    rng_pct = (c.max() - c.min()) / c.mean() * 100 if c.mean() else 999
    if rng_pct > max_range_pct:
        return None

    half = flat_window // 2
    v = vol.tail(flat_window)
    prior = v.iloc[:half].mean()
    recent = v.iloc[half:].mean()
    if not prior or pd.isna(prior) or prior == 0:
        return None
    vol_ratio = recent / prior
    if vol_ratio < min_vol_ratio:
        return None

    return {
        "signal": "birikim",
        "price": round(float(close.iloc[-1]), 2),
        "range_pct": round(float(rng_pct), 1),
        "vol_ratio": round(float(vol_ratio), 2),
        "detail": f"Fiyat son {flat_window} gun ~%{rng_pct:.1f} bantta yatay; "
                  f"hacim {vol_ratio:.2f}x artti (sessiz toplama olasi).",
    }


def cross_signal(df: pd.DataFrame, lookback: int = 10) -> dict | None:
    """Son `lookback` gunde MA50/MA200 golden/death cross olduysa sinyal doner."""
    if df is None or df.empty or "Close" not in df:
        return None
    close = df["Close"].dropna()
    if len(close) < 200 + lookback:
        return None
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    diff = (ma50 - ma200).dropna()
    if len(diff) < lookback + 1:
        return None

    recent = diff.tail(lookback + 1)
    sign = recent.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    # son lookback gun icinde isaret degisimi ara
    for i in range(1, len(sign)):
        if sign.iloc[i - 1] <= 0 and sign.iloc[i] > 0:
            kind, label = "golden", "Golden Cross (MA50 MA200'u yukari kesti)"
            break
        if sign.iloc[i - 1] >= 0 and sign.iloc[i] < 0:
            kind, label = "death", "Death Cross (MA50 MA200'u asagi kesti)"
            break
    else:
        return None

    when = recent.index[i]
    return {
        "signal": kind,
        "date": str(getattr(when, "date", lambda: when)())[:10],
        "price": round(float(close.iloc[-1]), 2),
        "ma50": round(float(ma50.iloc[-1]), 2),
        "ma200": round(float(ma200.iloc[-1]), 2),
        "detail": label,
    }


# ----------------------------------------------------------------------------- evren taramasi
def _download(symbols: list[str], period: str = "1y") -> pd.DataFrame:
    return yf.download(symbols, period=period, interval="1d", auto_adjust=True,
                       progress=False, threads=True, group_by="column")


def _slice(data: pd.DataFrame, sym: str) -> pd.DataFrame:
    """Batch indirmeden tek hissenin OHLCV'sini cikarir."""
    if isinstance(data.columns, pd.MultiIndex):
        try:
            return pd.DataFrame({
                "Close": data["Close"][sym],
                "Volume": data["Volume"][sym],
            }).dropna(how="all")
        except KeyError:
            return pd.DataFrame()
    # tek sembol
    return data[["Close", "Volume"]] if "Close" in data else pd.DataFrame()


def scan(market: str = "us", period: str = "1y") -> dict:
    """Piyasa evrenini tarar; birikim + cross sinyallerini toplar. Cache'li."""
    market = markets.normalize_market(market)
    now = time.time()
    cached = _CACHE.get(market)
    if cached and now - cached["ts"] < _TTL:
        return cached["data"]

    table = markets.get_table(market)
    symbols = table["symbol"].tolist()
    sector_of = dict(zip(table["symbol"], table["sector"]))
    print(f"[bilgi] tarama: {len(symbols)} hisse indiriliyor ({market})...", file=sys.stderr)
    data = _download(symbols, period=period)

    accumulation: list[dict] = []
    crosses: list[dict] = []
    for sym in symbols:
        d = _slice(data, sym)
        if d.empty:
            continue
        acc = accumulation_signal(d)
        if acc:
            accumulation.append({"symbol": sym, "sector": sector_of.get(sym), **acc})
        cr = cross_signal(d)
        if cr:
            crosses.append({"symbol": sym, "sector": sector_of.get(sym), **cr})

    accumulation.sort(key=lambda x: x["vol_ratio"], reverse=True)
    crosses.sort(key=lambda x: (x["signal"] != "golden", x["date"]), reverse=False)
    out = {
        "market": market,
        "accumulation": accumulation,
        "crosses": crosses,
        "evren": len(symbols),
    }
    _CACHE[market] = {"ts": now, "data": out}
    return out


def invalidate(market: str | None = None) -> None:
    if market is None:
        _CACHE.clear()
    else:
        _CACHE.pop(markets.normalize_market(market), None)


if __name__ == "__main__":
    mkt = sys.argv[1] if len(sys.argv) > 1 else "us"
    r = scan(market=mkt)
    print(f"\n=== TARAMA ({mkt}) — {r['evren']} hisse ===")
    print(f"\nBIRIKIM ({len(r['accumulation'])}):")
    for a in r["accumulation"][:15]:
        print(f"  {a['symbol']:10} {a['sector']:18} hacim {a['vol_ratio']}x · bant %{a['range_pct']}")
    print(f"\nCROSS ({len(r['crosses'])}):")
    for c in r["crosses"][:15]:
        print(f"  {c['symbol']:10} {c['signal']:7} {c['date']} · {c['sector']}")
