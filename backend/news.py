"""
Asama 3 - Haber agregasyonu.

Secili ticker icin haberleri tek akista toplar: kaynak + tarih + link + kisa ozet.
Basliga/URL'ye gore tekilles tirir, tarihe gore (yeni->eski) siralar. Onbellekli.

NOT: X (Twitter) dedikodu kosesi bu surumde KAPSAM DISI (kullanici karari: atla).
Ileride eklenecekse ayri bir 'rumors(symbol)' fonksiyonu + 'dogrulanmamis' etiketiyle
buraya takilabilir.
"""
from __future__ import annotations

import sys
import time

from . import marketdata

_CACHE: dict[str, tuple[float, list]] = {}
_TTL = 900  # 15 dk


def _extract(item: dict) -> dict:
    c = item.get("content", item) if isinstance(item, dict) else {}
    url = ""
    for k in ("canonicalUrl", "clickThroughUrl"):
        v = c.get(k)
        if isinstance(v, dict) and v.get("url"):
            url = v["url"]
            break
    provider = c.get("provider", {})
    return {
        "title": (c.get("title") or "").strip(),
        "summary": (c.get("summary") or c.get("description") or "")[:280],
        "date": (c.get("pubDate") or c.get("displayTime") or "")[:10],
        "source": provider.get("displayName", "") if isinstance(provider, dict) else "",
        "url": url,
    }


def feed(symbol: str, limit: int = 20) -> list[dict]:
    """Tekillesti rilmis, tarihe gore sirali haber akisi."""
    sym = marketdata.normalize_symbol(symbol)
    now = time.time()
    hit = _CACHE.get(sym)
    if hit and now - hit[0] < _TTL:
        return hit[1][:limit]

    try:
        raw = marketdata._ticker(sym).news or []
    except Exception:  # noqa: BLE001
        raw = []

    seen: set[str] = set()
    out: list[dict] = []
    for item in raw:
        n = _extract(item)
        if not n["title"]:
            continue
        key = (n["url"] or n["title"]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)

    # tarihe gore yeni->eski (bos tarih en sona)
    out.sort(key=lambda n: n["date"] or "0000-00-00", reverse=True)
    _CACHE[sym] = (now, out)
    return out[:limit]


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    for n in feed(sym):
        print(f"[{n['date']}] {n['title']}  · {n['source']}")
