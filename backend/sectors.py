"""
Modul 4 - Sektor gorunumu.

S&P 500'u GICS sektorlerine gore gruplar; her sektorun momentumunu (1 ay / 3 ay
ortalama getiri) ve genislik orani (yukselen hisse %%) olcer; sektorleri siralar.
Boylece "hangi sektor guclu / zayif" sorusuna bilanco okumadan cevap verir.

Veri tek seferde yf.download ile cekilir (hizli). Sonuc kisa sure cache'lenir.
"""
from __future__ import annotations

import sys
import time

import pandas as pd
import yfinance as yf

from . import breadth

_CACHE: dict = {"ts": 0.0, "data": None}
_TTL = 1800  # 30 dk


def _download_closes(symbols: list[str], period: str = "6mo") -> pd.DataFrame:
    data = yf.download(symbols, period=period, interval="1d", auto_adjust=True, progress=False, threads=True)
    if data.empty:
        raise RuntimeError("yfinance bos veri dondu.")
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]]
    return close.dropna(how="all")


def _ret(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    now, then = close.iloc[-1], close.iloc[-1 - days]
    if pd.isna(now) or pd.isna(then) or then == 0:
        return None
    return float(now / then - 1) * 100


def rank_sectors(period: str = "6mo") -> list[dict]:
    """Her sektor icin 1a/3a ortalama getiri + yukselen oranini hesaplar, siralar."""
    now = time.time()
    if _CACHE["data"] is not None and now - _CACHE["ts"] < _TTL:
        return _CACHE["data"]

    table = breadth.get_sp500_table()
    symbols = table["symbol"].tolist()
    sector_of = dict(zip(table["symbol"], table["sector"]))

    print(f"[bilgi] {len(symbols)} hisse sektor analizi icin indiriliyor...", file=sys.stderr)
    closes = _download_closes(symbols, period=period)

    rows = []
    for sym in closes.columns:
        s = closes[sym].dropna()
        if len(s) < 22:
            continue
        rows.append({
            "symbol": sym,
            "sector": sector_of.get(sym, "Bilinmiyor"),
            "mom_1m": _ret(s, 21),
            "mom_3m": _ret(s, 63),
        })
    df = pd.DataFrame(rows)

    out = []
    for sector, g in df.groupby("sector"):
        m1 = g["mom_1m"].dropna()
        m3 = g["mom_3m"].dropna()
        out.append({
            "sector": sector,
            "adet": int(len(g)),
            "mom_1m": round(float(m1.mean()), 2) if len(m1) else None,
            "mom_3m": round(float(m3.mean()), 2) if len(m3) else None,
            "yukselen_oran": round(float((m1 > 0).mean() * 100), 1) if len(m1) else None,
            "lider": _top(g, "mom_1m", 3),
            "geride": _top(g, "mom_1m", 3, asc=True),
        })

    out.sort(key=lambda x: (x["mom_3m"] is not None, x["mom_3m"] or -999), reverse=True)
    for i, row in enumerate(out, 1):
        row["sira"] = i
        row["yorum"] = _sector_comment(row)

    _CACHE.update(ts=now, data=out)
    return out


def _top(g: pd.DataFrame, col: str, n: int, asc: bool = False) -> list[dict]:
    gg = g.dropna(subset=[col]).sort_values(col, ascending=asc).head(n)
    return [{"symbol": r.symbol, "mom_1m": round(float(r.mom_1m), 1)} for r in gg.itertuples()]


def _sector_comment(row: dict) -> str:
    m3, m1 = row["mom_3m"], row["mom_1m"]
    if m3 is None:
        return "Yetersiz veri"
    if m3 > 8 and (m1 or 0) > 0:
        return "Guclu - 3 ayda lider, ivme devam ediyor"
    if m3 > 0 and (m1 or 0) > 0:
        return "Pozitif - trend yukari"
    if m3 > 0 and (m1 or 0) <= 0:
        return "Yoruluyor - 3 ay artida ama son ay zayif"
    if m3 <= 0 and (m1 or 0) > 0:
        return "Dipten donus denemesi - 3 ay ekside, son ay topluyor"
    return "Zayif - hem 3 ay hem son ay negatif"


def _n(v) -> str:
    return "-" if v is None else f"{v:.1f}"


if __name__ == "__main__":
    data = rank_sectors()
    print(f"\n{'SIRA':<5}{'SEKTOR':<26}{'3A %':>8}{'1A %':>8}{'YUKS%':>8}  YORUM")
    print("-" * 90)
    for r in data:
        print(f"{r['sira']:<5}{r['sector'][:25]:<26}{_n(r['mom_3m']):>8}{_n(r['mom_1m']):>8}{_n(r['yukselen_oran']):>8}  {r['yorum']}")
