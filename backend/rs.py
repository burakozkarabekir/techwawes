"""
Asama 6 - Karsilastirma, Oran Grafigi ve RS (Relative Strength) Rating.

  1. RS Rating (IBD tarzi 1-99 yuzdelik): bir evrendeki hisseleri agirlikli getiriye
     gore puanlar; 99 = en guclu %1.
  2. Oran grafigi (ratio chart): hisse / benchmark (orn. NVDA/^GSPC). Oran yukseliyorsa
     hisse benchmark'tan GUCLU, dusuyorsa zayif.
  3. Top-down guc tarayici: en guclu sektor -> o sektordeki en guclu hisse.

Agirlikli getiri ve yuzdelik siralama SAF fonksiyonlardir -> birim test edilebilir.
"""
from __future__ import annotations

import sys
import time

import pandas as pd
import yfinance as yf

from . import markets

_CACHE: dict[str, dict] = {}
_TTL = 1800

# IBD benzeri agirliklar: son ceyrek 2x, sonraki ceyrekler 1x (3/6/9/12 ay ~ 63/126/189/252 gun)
_WEIGHTS = [(63, 2.0), (126, 1.0), (189, 1.0), (252, 1.0)]


# ----------------------------------------------------------------------------- saf hesaplar
def weighted_return(close: pd.Series) -> float | None:
    """IBD tarzi agirlikli getiri ham skoru. Yeterli veri yoksa None."""
    close = close.dropna()
    if len(close) < 64:  # en az ~3 ay
        return None
    last = close.iloc[-1]
    total_w = 0.0
    acc = 0.0
    for days, w in _WEIGHTS:
        if len(close) > days:
            then = close.iloc[-1 - days]
            if then and not pd.isna(then) and then != 0:
                acc += w * (last / then - 1.0)
                total_w += w
    if total_w == 0:
        return None
    return float(acc / total_w * 100)


def percentile_ranks(raw: dict[str, float]) -> dict[str, int]:
    """Ham skorlari 1-99 yuzdelik RS Rating'e cevirir (yuksek skor = yuksek rating)."""
    items = [(k, v) for k, v in raw.items() if v is not None]
    n = len(items)
    if n == 0:
        return {}
    if n == 1:
        return {items[0][0]: 99}
    ordered = sorted(items, key=lambda kv: kv[1])  # dusukten yukseye
    out: dict[str, int] = {}
    for i, (sym, _) in enumerate(ordered):
        pct = i / (n - 1)  # 0..1
        out[sym] = int(round(1 + pct * 98))  # 1..99
    return out


# ----------------------------------------------------------------------------- evren RS tablosu
def _download_closes(symbols: list[str], period: str = "1y") -> pd.DataFrame:
    data = yf.download(symbols, period=period, interval="1d", auto_adjust=True,
                       progress=False, threads=True)
    if data.empty:
        return pd.DataFrame()
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]]
    return close.dropna(how="all")


def rs_table(market: str = "us", period: str = "1y") -> dict:
    """Evrendeki tum hisseler icin RS Rating tablosu (cache'li)."""
    market = markets.normalize_market(market)
    now = time.time()
    cached = _CACHE.get(market)
    if cached and now - cached["ts"] < _TTL:
        return cached["data"]

    table = markets.get_table(market)
    symbols = table["symbol"].tolist()
    sector_of = dict(zip(table["symbol"], table["sector"]))
    print(f"[bilgi] RS: {len(symbols)} hisse indiriliyor ({market})...", file=sys.stderr)
    closes = _download_closes(symbols, period=period)

    raw: dict[str, float] = {}
    for sym in closes.columns:
        r = weighted_return(closes[sym])
        if r is not None:
            raw[sym] = r
    ratings = percentile_ranks(raw)

    rows = [{
        "symbol": sym,
        "sector": sector_of.get(sym),
        "rs": ratings[sym],
        "raw": round(raw[sym], 1),
    } for sym in ratings]
    rows.sort(key=lambda x: x["rs"], reverse=True)

    out = {"market": market, "rows": rows, "evren": len(symbols)}
    _CACHE[market] = {"ts": now, "data": out}
    return out


def top_down(market: str = "us") -> dict:
    """En guclu sektor -> o sektorun en guclu hissesi (RS Rating ile)."""
    table = rs_table(market)
    rows = table["rows"]
    if not rows:
        return {"market": markets.normalize_market(market), "ranking": [], "pick": None}

    by_sector: dict[str, list[dict]] = {}
    for r in rows:
        by_sector.setdefault(r["sector"], []).append(r)

    ranking = []
    for sector, members in by_sector.items():
        avg = sum(m["rs"] for m in members) / len(members)
        leader = max(members, key=lambda m: m["rs"])
        ranking.append({
            "sector": sector,
            "avg_rs": round(avg, 1),
            "lider": {"symbol": leader["symbol"], "rs": leader["rs"]},
            "adet": len(members),
        })
    ranking.sort(key=lambda x: x["avg_rs"], reverse=True)

    pick = None
    if ranking:
        top_sector = ranking[0]
        pick = {
            "sector": top_sector["sector"],
            "symbol": top_sector["lider"]["symbol"],
            "rs": top_sector["lider"]["rs"],
            "aciklama": f"En guclu sektor '{top_sector['sector']}' (ort. RS {top_sector['avg_rs']}); "
                        f"icindeki en guclu hisse {top_sector['lider']['symbol']} (RS {top_sector['lider']['rs']}).",
        }
    return {"market": table["market"], "ranking": ranking, "pick": pick}


# ----------------------------------------------------------------------------- oran grafigi
def ratio_chart(symbol: str, benchmark: str | None = None, market: str = "us",
                period: str = "1y") -> dict:
    """Hisse/benchmark oranini zaman serisi olarak doner + yorum (guclu/zayif)."""
    from . import marketdata
    market = markets.normalize_market(market)
    sym = marketdata.normalize_symbol(symbol)
    bench = benchmark or markets.MARKETS[market]["benchmark"]

    closes = _download_closes([sym, bench], period=period)
    if closes.empty or sym not in closes.columns or bench not in closes.columns:
        return {"ok": False, "error": "veri cekilemedi", "symbol": sym, "benchmark": bench}
    a = closes[sym].dropna()
    b = closes[bench].dropna()
    idx = a.index.intersection(b.index)
    a, b = a.reindex(idx), b.reindex(idx)
    ratio = (a / b.replace(0, pd.NA)).dropna()
    if len(ratio) < 2:
        return {"ok": False, "error": "yetersiz ortak veri", "symbol": sym, "benchmark": bench}

    # normalize: baslangic = 100 (gorsel kolaylik)
    norm = ratio / ratio.iloc[0] * 100
    chg = float(norm.iloc[-1] - 100)
    trend = "guclu" if chg > 1 else ("zayif" if chg < -1 else "notr")
    yorum = {
        "guclu": f"{sym}, {bench}'a karsi son donemde GUCLU (oran +%{chg:.1f}).",
        "zayif": f"{sym}, {bench}'a karsi son donemde ZAYIF (oran %{chg:.1f}).",
        "notr": f"{sym} ile {bench} basa bas (oran ~%{chg:.1f}).",
    }[trend]
    return {
        "ok": True, "symbol": sym, "benchmark": bench, "market": market,
        "dates": [str(getattr(d, "date", lambda: d)())[:10] for d in norm.index],
        "ratio": [round(float(v), 2) for v in norm.values],
        "change_pct": round(chg, 1), "trend": trend, "yorum": yorum,
    }


def invalidate(market: str | None = None) -> None:
    if market is None:
        _CACHE.clear()
    else:
        _CACHE.pop(markets.normalize_market(market), None)


if __name__ == "__main__":
    mkt = sys.argv[1] if len(sys.argv) > 1 else "us"
    td = top_down(mkt)
    print(f"\n=== TOP-DOWN GUC ({mkt}) ===")
    for r in td["ranking"][:8]:
        print(f"  {r['sector']:20} ort.RS {r['avg_rs']:5}  lider {r['lider']['symbol']} (RS {r['lider']['rs']})")
    if td["pick"]:
        print("\n  SECIM:", td["pick"]["aciklama"])
