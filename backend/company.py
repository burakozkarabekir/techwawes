"""
Modul 4 - Sirket analizi + uc modlu senaryo (gercekci / iyimser / karamsar)
Modul 3 - Hareketli stop-loss / kar-al noktalari (ATR tabanli, duruma gore ayarli)

Felsefe: "su fiyattan al" demez. Sektoru yazar, sirketin teknik + temel + bilanco
ozetini cikarir, son haberleri listeler ve uc senaryo ("cunku ...") ciker.
Stop/hedef teknik (ATR + destek/direnc) hesaplanir; haber/temel sinyali stance'i
(siki/gevsek) ayarlar.

Veri kaynagi: yfinance .info (temel), .news (haber), .history (teknik).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import yfinance as yf

from . import indicators, markets

# Sembol basina analiz onbellegi (public'te tekrar eden istekleri Yahoo'ya tasimaz)
_ANALYSIS_CACHE: dict[str, tuple[float, dict]] = {}
_ANALYSIS_TTL = 1800  # 30 dk


# ----------------------------------------------------------------------------- veri toplama
def _fundamentals(info: dict) -> dict:
    """info sozlugunden temel/bilanco ozetini cikarir (bilanco okumadan)."""
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    target = info.get("targetMeanPrice")
    upside = round((target / price - 1) * 100, 1) if (target and price) else None
    return {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "name": info.get("shortName") or info.get("longName"),
        "currency": info.get("currency"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": _r(info.get("trailingPE")),
        "forward_pe": _r(info.get("forwardPE")),
        "peg": _r(info.get("pegRatio")),
        "pb": _r(info.get("priceToBook")),
        "profit_margin": _pct(info.get("profitMargins")),
        "revenue_growth": _pct(info.get("revenueGrowth")),
        "earnings_growth": _pct(info.get("earningsGrowth")),
        "roe": _pct(info.get("returnOnEquity")),
        "debt_to_equity": _r(info.get("debtToEquity")),
        "recommendation": info.get("recommendationKey"),
        "target_price": _r(target),
        "target_upside": upside,
        "fwd_better": (info.get("forwardPE") and info.get("trailingPE")
                       and info["forwardPE"] < info["trailingPE"]),  # kazanc buyuyor sinyali
    }


def _news(ticker: yf.Ticker, limit: int = 5) -> list[dict]:
    """Son haberleri sade listeye cevirir (baslik, ozet, tarih, kaynak, link)."""
    out = []
    try:
        raw = ticker.news or []
    except Exception:  # noqa: BLE001
        raw = []
    for item in raw[:limit]:
        c = item.get("content", item) if isinstance(item, dict) else {}
        url = ""
        for k in ("canonicalUrl", "clickThroughUrl"):
            if isinstance(c.get(k), dict) and c[k].get("url"):
                url = c[k]["url"]
                break
        provider = c.get("provider", {})
        out.append({
            "title": c.get("title", ""),
            "summary": (c.get("summary") or "")[:240],
            "date": (c.get("pubDate") or "")[:10],
            "source": provider.get("displayName", "") if isinstance(provider, dict) else "",
            "url": url,
        })
    return out


# ----------------------------------------------------------------------------- skor + senaryo
def _score(tech: dict, fund: dict) -> tuple[int, list[str], list[str]]:
    """Teknik+temel sinyalleri -100..+100 skora toplar. (skor, artilar, eksiler)."""
    score = 0
    pos: list[str] = []
    neg: list[str] = []

    def add(cond, pts, pos_msg=None, neg_msg=None):
        nonlocal score
        if cond:
            score += pts
            if pos_msg:
                pos.append(pos_msg)
        else:
            if neg_msg:
                neg.append(neg_msg)

    # --- Teknik ---
    if tech.get("above_ma200") is not None:
        add(tech["above_ma200"], 15,
            "fiyat 200 gunluk ortalamanin uzerinde (uzun vade yukari trend)",
            "fiyat 200 gunluk ortalamanin altinda (uzun vade zayif)")
    if tech.get("golden") is not None:
        add(tech["golden"], 10,
            "MA50 > MA200 (golden cross dizilimi)",
            "MA50 < MA200 (death cross dizilimi)")
    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 8; pos.append(f"RSI {rsi} (asiri satim - tepki potansiyeli)")
        elif rsi > 70:
            score -= 8; neg.append(f"RSI {rsi} (asiri alim - geri cekilme riski)")
    m3 = tech.get("mom_3m")
    if m3 is not None:
        add(m3 > 0, 8, f"3 aylik momentum +%{m3}", f"3 aylik momentum %{m3}")
    p52 = tech.get("pos_52w")
    if p52 is not None and p52 > 90:
        neg.append(f"52h aralikta tepeye yakin (%{p52})")

    # --- Temel ---
    peg = fund.get("peg")
    if peg is not None:
        if peg < 1:
            score += 12; pos.append(f"PEG {peg} (<1, buyumeye gore ucuz)")
        elif peg > 2.5:
            score -= 10; neg.append(f"PEG {peg} (>2.5, pahali)")
    if fund.get("fwd_better"):
        score += 8; pos.append("ileri F/K < cari F/K (kazanc buyumesi bekleniyor)")
    eg = fund.get("earnings_growth")
    if eg is not None:
        add(eg > 10, 8, f"kazanc buyumesi +%{eg}", f"kazanc buyumesi %{eg}")
    rg = fund.get("revenue_growth")
    if rg is not None:
        add(rg > 8, 6, f"ciro buyumesi +%{rg}", None)
    roe = fund.get("roe")
    if roe is not None and roe > 15:
        score += 6; pos.append(f"ozkaynak karliligi (ROE) %{roe} (yuksek)")
    de = fund.get("debt_to_equity")
    if de is not None and de > 150:
        score -= 6; neg.append(f"borc/ozkaynak {de} (yuksek kaldirac)")
    up = fund.get("target_upside")
    if up is not None:
        if up > 10:
            score += 8; pos.append(f"analist hedefi %{up} yukarida")
        elif up < -5:
            score -= 8; neg.append(f"analist hedefi %{abs(up)} asagida (fiyat hedefi astı)")

    return max(-100, min(100, score)), pos, neg


def _stance(score: int) -> str:
    if score >= 35:
        return "Pozitif"
    if score >= 10:
        return "Hafif pozitif"
    if score > -10:
        return "Notr"
    if score > -35:
        return "Hafif negatif"
    return "Negatif"


def scenarios(tech: dict, fund: dict, score: int, pos: list[str], neg: list[str]) -> dict:
    """Uc modlu senaryo metni uretir. Her biri gercek verilerle 'cunku ...' der."""
    price = tech.get("price")
    res = tech.get("resistance")
    sup = tech.get("support")
    target = fund.get("target_price")

    pos_txt = "; ".join(pos[:4]) if pos else "belirgin olumlu sinyal sinirli"
    neg_txt = "; ".join(neg[:4]) if neg else "belirgin olumsuz sinyal sinirli"

    gercekci = (
        f"Genel durus: {_stance(score)} (skor {score:+d}). "
        f"Olumlu taraf: {pos_txt}. Riskler: {neg_txt}. "
        f"Fiyat {price}; yakin destek {sup}, yakin direnc {res}. "
        + (f"Analist ortalama hedefi {target}. " if target else "")
        + "Karar: trend ve temel teyit ederse kademeli; teyit yoksa beklemek mantikli."
    )

    atr = tech.get("atr")
    # Ikincil hedef: analist hedefi fiyatin uzerindeyse onu kullan; degilse direncten
    # ATR kadar oteye projekte et (direncle ayni cikmasin).
    if target and price and target > (res or price):
        up_target = target
    elif res and atr:
        up_target = round(res + 3 * atr, 2)
    elif price:
        up_target = round(price * 1.10, 2)
    else:
        up_target = None
    iyimser = (
        "IYIMSER senaryo: "
        + (f"Eger {pos[0]}, " if pos else "Eger pozitif katalizor gelir ve ")
        + (f"ek olarak {pos[1]}, " if len(pos) > 1 else "")
        + "ivme korunursa fiyat "
        + (f"once {res} direncini, ardindan {up_target} bolgesini deneyebilir. " if (res and up_target) else "yukari yonlu hareket edebilir. ")
        + "Tetik: direncin hacimle kirilmasi ve sektorun guclu kalmasi."
    )

    down_stop = sup if sup else (round(price * 0.92, 2) if price else None)
    karamsar = (
        "KARAMSAR senaryo: "
        + (f"Eger {neg[0]}" if neg else "Eger olumsuz haber/zayif bilanco gelirse")
        + (f" ve ayrica {neg[1]}, " if len(neg) > 1 else ", ")
        + "satis baskisi artarsa "
        + (f"{down_stop} destegi kirilabilir; altinda dususun hizlanma riski var. " if down_stop else "geri cekilme derinlesebilir. ")
        + "Tetik: destegin kapanista kirilmasi veya sektor genelinde zayiflama."
    )

    return {"gercekci": gercekci, "iyimser": iyimser, "karamsar": karamsar}


# ----------------------------------------------------------------------------- Modul 3: stop/hedef
def levels(tech: dict, score: int) -> dict:
    """ATR tabanli hareketli stop-loss + kar-al. Duruma gore carpan ayarlanir.

    Pozitif duruс -> trail'i gevset (kosmaya birak). Negatif duruс -> sikilastir.
    """
    price = tech.get("price")
    atr = tech.get("atr")
    sup = tech.get("support")
    res = tech.get("resistance")
    if not price or not atr:
        return {"uygun": False, "neden": "ATR/fiyat yok"}

    # stance carpani: pozitifte daha genis trailing, negatifte daha sıkı
    if score >= 35:
        mult, mode = 3.0, "gevsek (trend takibi)"
    elif score >= 10:
        mult, mode = 2.5, "normal"
    elif score > -10:
        mult, mode = 2.0, "normal"
    else:
        mult, mode = 1.5, "siki (sermaye koruma)"

    trail_stop = round(price - mult * atr, 2)
    # destek varsa ve trailing stop'tan yukaridaysa, destegin biraz altini kullan (mantikli stop)
    if sup and sup < price:
        struct_stop = round(sup - 0.5 * atr, 2)
        stop = max(trail_stop, struct_stop) if struct_stop < price else trail_stop
    else:
        stop = trail_stop

    risk = round(price - stop, 2)
    take1 = round(price + 2 * risk, 2)  # 2R
    take2 = round(price + 3 * risk, 2)  # 3R
    # direnc hedefi varsa goster
    rr_note = ""
    if res and res > price:
        rr_to_res = round((res - price) / risk, 1) if risk else None
        rr_note = f"Direnc {res} = {rr_to_res}R uzaklikta."

    return {
        "uygun": True,
        "price": price,
        "atr": atr,
        "stop": stop,
        "stop_mode": mode,
        "stop_mult": mult,
        "risk_per_share": risk,
        "take_profit_2r": take1,
        "take_profit_3r": take2,
        "stop_pct": round((stop / price - 1) * 100, 1),
        "not": (
            f"Hareketli stop {price} fiyatta {mult}xATR ({mode}) ile {stop}. "
            f"Fiyat yukseldikce stop yukari tasinir, asla asagi cekilmez. "
            f"Hedefler 2R={take1}, 3R={take2}. {rr_note}"
        ),
    }


# ----------------------------------------------------------------------------- ust seviye API
def normalize_symbol(symbol: str) -> str:
    """Kullanici sembolunu Yahoo formatina cevirir.

    BIST hisseleri Yahoo'da `.IS` ister (THYAO -> THYAO.IS). Kullanici cipla yazarsa
    ve sembol bilinen BIST evrenindeyse `.IS` eklenir. Zaten suffix varsa dokunulmaz.
    """
    s = symbol.upper().strip()
    if "." not in s and s in markets.BIST_BARE_SET:
        return s + markets.BIST_SUFFIX
    return s


def analyze(symbol: str) -> dict:
    """Bir hisse icin tam analiz: teknik + temel + haber + 3 senaryo + stop/hedef."""
    symbol = normalize_symbol(symbol)
    t = yf.Ticker(symbol)
    try:
        hist = t.history(period="1y", interval="1d", auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"fiyat verisi alinamadi: {exc}", "symbol": symbol}
    if hist.empty:
        return {"ok": False, "error": "fiyat verisi bos (sembol gecersiz olabilir)", "symbol": symbol}

    tech = indicators.snapshot(hist)
    try:
        info = t.info or {}
    except Exception:  # noqa: BLE001
        info = {}
    fund = _fundamentals(info)
    if not tech.get("price") and fund.get("market_cap"):
        tech["price"] = info.get("currentPrice")

    score, pos, neg = _score(tech, fund)
    return {
        "ok": True,
        "symbol": symbol,
        "name": fund.get("name") or symbol,
        "sector": fund.get("sector"),
        "industry": fund.get("industry"),
        "stance": _stance(score),
        "score": score,
        "teknik": tech,
        "temel": fund,
        "artilar": pos,
        "eksiler": neg,
        "haberler": _news(t),
        "senaryolar": scenarios(tech, fund, score, pos, neg),
        "stop_hedef": levels(tech, score),
        "guncelleme": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def analyze_cached(symbol: str) -> dict:
    """analyze() etrafinda TTL'li onbellek. Public endpoint bunu kullanir."""
    symbol = normalize_symbol(symbol)
    now = time.time()
    hit = _ANALYSIS_CACHE.get(symbol)
    if hit and now - hit[0] < _ANALYSIS_TTL:
        return hit[1]
    result = analyze(symbol)
    if result.get("ok"):
        _ANALYSIS_CACHE[symbol] = (now, result)
    return result


# ----------------------------------------------------------------------------- yardimcilar
def _r(v, nd: int = 2):
    try:
        return round(float(v), nd) if v is not None else None
    except (TypeError, ValueError):
        return None


def _pct(v, nd: int = 1):
    """Orani yuzdeye cevirir (0.27 -> 27.0)."""
    try:
        return round(float(v) * 100, nd) if v is not None else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    a = analyze(sym)
    if not a.get("ok"):
        print("HATA:", a.get("error")); sys.exit(1)
    print(f"\n=== {a['name']} ({a['symbol']}) — {a['sector']} / {a['industry']} ===")
    print(f"Durus: {a['stance']} (skor {a['score']:+d})")
    print(f"\nTeknik: fiyat={a['teknik']['price']} RSI={a['teknik']['rsi']} "
          f"MA50={a['teknik']['ma50']} MA200={a['teknik']['ma200']} "
          f"1a={a['teknik']['mom_1m']}% 3a={a['teknik']['mom_3m']}% 52h_poz={a['teknik']['pos_52w']}")
    print(f"Temel: F/K={a['temel']['trailing_pe']} ileriF/K={a['temel']['forward_pe']} "
          f"PEG={a['temel']['peg']} marj={a['temel']['profit_margin']}% "
          f"ciroBuyume={a['temel']['revenue_growth']}% hedef={a['temel']['target_price']} (%{a['temel']['target_upside']})")
    print("\nArtilar:", "; ".join(a["artilar"]) or "-")
    print("Eksiler:", "; ".join(a["eksiler"]) or "-")
    print("\n--- SENARYOLAR ---")
    for k, v in a["senaryolar"].items():
        print(f"\n[{k.upper()}]\n{v}")
    print("\n--- STOP / HEDEF (Modul 3) ---")
    print(a["stop_hedef"].get("not") or a["stop_hedef"].get("neden"))
    print("\n--- SON HABERLER ---")
    for n in a["haberler"]:
        print(f"  • [{n['date']}] {n['title']} ({n['source']})")
