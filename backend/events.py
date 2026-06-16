"""
Asama 5 - Grafik verisi + geri alim / iceriden islem isaretleme.

Fiyat serisini (kapanis + MA50/MA200 + hacim) ve grafigin uzerine konacak
isaretleri doner:
  - Iceriden alim-satim (Yahoo insider_transactions; cogunlukla ABD/SEC Form 4).
  - Hisse geri alim (buyback): yfinance'te kesin tarih yok; yillik nakit akistaki
    'Repurchase Of Capital Stock' kalemleri donem sonu isareti olarak verilir.

BIST'te Yahoo iceriden islem dondurmez -> 'veri yok' notu ile bos liste; mimari
ileride KAP kaynagi takilacak sekilde hazir (kullanici karari: Asama 5 sona birakildi,
BIST olaylari icin KAP scraping su an kapsam disi).
"""
from __future__ import annotations

import sys

import pandas as pd

from . import marketdata, markets


# ----------------------------------------------------------------------------- isaretler
def insider_markers(symbol: str, limit: int = 60) -> list[dict]:
    """Iceriden islemleri grafik isareti formatina cevirir (al/sat ayrimi)."""
    sym = marketdata.normalize_symbol(symbol)
    df = marketdata.insider(sym)
    if df is None or df.empty:
        return []
    out: list[dict] = []
    for _, r in df.iterrows():
        txn = str(r.get("Transaction", "") or "")
        text = str(r.get("Text", "") or "")
        blob = (txn + " " + text).lower()
        if "sale" in blob or "sell" in blob:
            kind = "sat"
        elif "purchase" in blob or "buy" in blob:
            kind = "al"
        else:
            kind = "diger"  # grant/award/gift vb.
        date = r.get("Start Date")
        try:
            date = str(pd.to_datetime(date).date())
        except Exception:  # noqa: BLE001
            date = str(date)[:10]
        out.append({
            "date": date,
            "type": kind,
            "shares": _num(r.get("Shares")),
            "value": _num(r.get("Value")),
            "insider": str(r.get("Insider", "") or ""),
            "position": str(r.get("Position", "") or ""),
            "text": text[:120],
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:limit]


def buyback_markers(symbol: str) -> list[dict]:
    """Yillik nakit akistan hisse geri alim kalemlerini donem sonu isareti yapar."""
    sym = marketdata.normalize_symbol(symbol)
    cf = marketdata.statements(sym).get("cashflow", pd.DataFrame())
    s = marketdata.row_series(cf, "Repurchase Of Capital Stock", "Common Stock Payments")
    out = []
    for date, val in s.items():
        amt = abs(float(val)) if not pd.isna(val) else 0.0
        if amt <= 0:
            continue
        try:
            d = str(pd.to_datetime(date).date())
        except Exception:  # noqa: BLE001
            d = str(date)[:10]
        out.append({"date": d, "amount": amt,
                    "text": f"Yillik geri alim ~{amt:,.0f}"})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


# ----------------------------------------------------------------------------- grafik verisi
def chart(symbol: str, period: str = "1y") -> dict:
    """Fiyat serisi (kapanis + MA50/200 + hacim) + isaretler. Asama 5 ana ucu."""
    sym = marketdata.normalize_symbol(symbol)
    df = marketdata.ohlcv(sym, period=period)
    if df is None or df.empty or "Close" not in df:
        return {"ok": False, "symbol": sym, "error": "fiyat verisi yok"}

    close = df["Close"].dropna()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    vol = df["Volume"] if "Volume" in df else pd.Series(index=close.index, dtype="float64")

    dates = [str(getattr(d, "date", lambda: d)())[:10] for d in close.index]
    is_bist = sym.endswith(markets.BIST_SUFFIX)
    ins = insider_markers(sym)
    note = None
    if is_bist and not ins:
        note = "BIST iceriden islem verisi Yahoo'da yok (KAP'ta). Bu bolum ileride KAP kaynagina baglanacak."

    return {
        "ok": True,
        "symbol": sym,
        "currency": marketdata.info(sym).get("currency"),
        "dates": dates,
        "close": [round(float(v), 2) for v in close.values],
        "ma50": [None if pd.isna(v) else round(float(v), 2) for v in ma50.values],
        "ma200": [None if pd.isna(v) else round(float(v), 2) for v in ma200.values],
        "volume": [None if pd.isna(v) else float(v) for v in vol.reindex(close.index).values],
        "insider": ins,
        "buyback": buyback_markers(sym),
        "note": note,
    }


def _num(v):
    try:
        return None if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    c = chart(sym)
    if not c.get("ok"):
        print("HATA:", c.get("error")); sys.exit(1)
    print(f"{c['symbol']} — {len(c['dates'])} gun fiyat, "
          f"{len(c['insider'])} iceriden islem, {len(c['buyback'])} geri alim isareti")
    if c.get("note"):
        print("NOT:", c["note"])
    for m in c["insider"][:5]:
        print(f"  [{m['date']}] {m['type'].upper():5} {m['insider']} ({m['position']}) "
              f"{m['shares']} adet / {m['value']}")
