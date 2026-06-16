"""
Asama 2 - Temel Saglik Skoru (skor karti + akilli uyari).

Bir hisse icin 8 kriteri gercek finansal tablolardan (gelir/bilanco/nakit, ceyreklik)
hesaplar; her birini gecti/kaldi + ham deger + kisa aciklama olarak doner; toplam
skoru ozetler (orn. 6/8). Ek olarak nakit akis tablosundan "kirmizi bayrak" tarar:
sermaye artirimindan gelen nakit operasyona degil borc odemeye gitmis OLABILIR.

Hesaplama mantigi SAF fonksiyonlardir (pandas Series/DataFrame alir) -> birim test
edilebilir (test_fundamentals.py). analyze_health(symbol) bunlari marketdata ile besler.

Kriterler:
  1 Esas faaliyet kari (Operating Income)   -> duzenli artis
  2 Ciro istikrari (Total Revenue)          -> istikrarli, sert dusus yok
  3 ROE (Net Income / Stockholders Equity)  -> esik uzeri + istikrarli
  4 Cari oran (Current Assets/Liabilities)  -> 1.5-2.0 bandi
  5 FAVOK marji (EBITDA / Revenue)          -> azalmiyor
  6 Operasyonel nakit akisi                 -> pozitif
  7 Stok devir hizi (COGS / Inventory)      -> artan
  8 EPS (Diluted EPS)                       -> artis trendi
"""
from __future__ import annotations

import sys

import pandas as pd

from . import marketdata

# ----------------------------------------------------------------------------- config
DEFAULT_CONFIG: dict = {
    "periods": 4,                    # son N donem dikkate alinir
    "use_quarterly": False,          # yillik (False, varsayilan; mevsimsellikten arinik)
                                     # vs ceyreklik (True; daha guncel ama mevsimsel)
    "current_ratio_band": (1.5, 2.0),
    "roe_min_pct": 15.0,             # sektor ort. yoksa kullanilan proxy esik (%)
    "trend_min_up_frac": 0.5,        # "artis" icin pozitif adim orani esigi
    "stable_max_cv": 0.30,           # ciro istikrari: degisim katsayisi tavani
    "stable_max_drop": 0.20,         # tek donemde izin verilen max dusus (%20)
    "margin_tolerance": 0.02,        # FAVOK marji "azalmiyor" toleransi (2 puan)
    # kirmizi bayrak esikleri (son donem)
    "flag_issuance_min": 0.0,        # net hisse ihraci > 0 (sermaye girisi)
    "flag_debt_repay_ratio": 0.5,    # borc odemesi, ihrac nakdinin >= %50'si
}


# ----------------------------------------------------------------------------- saf yardimcilar
def _last_n(s: pd.Series, n: int) -> pd.Series:
    return s.tail(n) if len(s) > n else s


def trend_up(s: pd.Series, min_up_frac: float = 0.5) -> bool:
    """Seri "duzenli artis" trendinde mi: son >= ilk VE pozitif adim orani esigi gecsin."""
    s = s.dropna()
    if len(s) < 2:
        return False
    diffs = s.diff().dropna()
    up_frac = (diffs > 0).sum() / len(diffs)
    return bool(s.iloc[-1] > s.iloc[0] and up_frac >= min_up_frac)


def is_stable(s: pd.Series, max_cv: float = 0.30, max_drop: float = 0.20) -> bool:
    """Seri istikrarli mi: degisim katsayisi dusuk VE tek donem sert dususu yok."""
    s = s.dropna()
    if len(s) < 2:
        return False
    mean = s.mean()
    if mean == 0:
        return False
    cv = s.std(ddof=0) / abs(mean)
    # donemler arasi en kotu dusus orani
    prev = s.shift(1)
    drops = ((prev - s) / prev.abs()).dropna()  # pozitif = dusus
    worst_drop = drops.max() if len(drops) else 0.0
    return bool(cv <= max_cv and worst_drop <= max_drop)


def not_decreasing(s: pd.Series, tol: float = 0.0) -> bool:
    """Seri azalmiyor mu (yatay/artan): son deger ilk degerin (1-tol) kati uzerinde
    VE genel egim negatif degil."""
    s = s.dropna()
    if len(s) < 2:
        return False
    if s.iloc[-1] < s.iloc[0] * (1 - tol):
        return False
    # basit egim isareti
    x = range(len(s))
    slope = pd.Series(list(x)).corr(pd.Series(s.values))
    return bool(pd.isna(slope) or slope >= -0.1)


def _crit(key: str, label: str, passed: bool | None, raw, detail: str) -> dict:
    return {"key": key, "label": label, "passed": passed, "raw": raw, "detail": detail}


def _fmt(v, nd: int = 2) -> str:
    try:
        return "-" if v is None or pd.isna(v) else f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return "-"


# ----------------------------------------------------------------------------- skor karti (saf)
def score_card(stmts: dict[str, pd.DataFrame], config: dict | None = None) -> dict:
    """Tablolardan 8 kriterli saglik kartini uretir. SAF: ag erisimi yok.

    stmts: marketdata.statements() ciktisi (income_q, balance_q, cashflow_q ...).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    n = cfg["periods"]
    q = cfg["use_quarterly"]
    inc = stmts.get("income_q" if q else "income", pd.DataFrame())
    bal = stmts.get("balance_q" if q else "balance", pd.DataFrame())
    cf = stmts.get("cashflow_q" if q else "cashflow", pd.DataFrame())

    rs = marketdata.row_series
    crits: list[dict] = []

    # 1 - Esas faaliyet kari (Operating Income) duzenli artis
    op = _last_n(rs(inc, "Operating Income", "Total Operating Income As Reported"), n)
    crits.append(_crit(
        "operating_income", "Esas faaliyet kari artisi",
        trend_up(op, cfg["trend_min_up_frac"]) if len(op) >= 2 else None,
        _fmt(op.iloc[-1]) if len(op) else None,
        f"Son {len(op)} donem esas faaliyet kari trendi" if len(op) else "veri yok",
    ))

    # 2 - Ciro istikrari (Total Revenue)
    rev = _last_n(rs(inc, "Total Revenue", "Operating Revenue"), n)
    crits.append(_crit(
        "revenue_stability", "Ciro istikrari",
        is_stable(rev, cfg["stable_max_cv"], cfg["stable_max_drop"]) if len(rev) >= 2 else None,
        _fmt(rev.iloc[-1]) if len(rev) else None,
        "Ciro istikrarli, sert dusus yok" if len(rev) else "veri yok",
    ))

    # 3 - ROE = Net Income / Stockholders Equity (esik uzeri + istikrarli)
    ni = _last_n(rs(inc, "Net Income", "Net Income Common Stockholders"), n)
    eq = _last_n(rs(bal, "Stockholders Equity", "Common Stock Equity"), n)
    roe_series = _roe_series(ni, eq)
    roe_last = roe_series.iloc[-1] if len(roe_series) else None
    roe_pass = None
    if len(roe_series):
        roe_pass = bool(roe_last is not None and roe_last >= cfg["roe_min_pct"]
                        and is_stable(roe_series, max_cv=0.6, max_drop=0.5))
    crits.append(_crit(
        "roe", f"ROE >= %{cfg['roe_min_pct']:.0f} (proxy) ve istikrarli",
        roe_pass, f"%{_fmt(roe_last, 1)}" if roe_last is not None else None,
        "Sektor ort. cekilemedigi icin sabit esik proxy olarak kullanildi" if len(roe_series) else "veri yok",
    ))

    # 4 - Cari oran (Current Assets / Current Liabilities) 1.5-2.0
    ca = rs(bal, "Current Assets")
    cl = rs(bal, "Current Liabilities")
    cur = _div_last(ca, cl)
    lo, hi = cfg["current_ratio_band"]
    crits.append(_crit(
        "current_ratio", f"Cari oran {lo}-{hi} bandi",
        (lo <= cur <= hi) if cur is not None else None,
        _fmt(cur) if cur is not None else None,
        f"Cari oran (donen varlik/kisa vade borc); ideal {lo}-{hi}" if cur is not None else "veri yok",
    ))

    # 5 - FAVOK marji (EBITDA / Revenue) azalmiyor
    ebitda = _last_n(rs(inc, "EBITDA", "Normalized EBITDA"), n)
    rev_for_m = _last_n(rs(inc, "Total Revenue", "Operating Revenue"), n)
    margin = _margin_series(ebitda, rev_for_m)
    crits.append(_crit(
        "ebitda_margin", "FAVOK marji azalmiyor",
        not_decreasing(margin, cfg["margin_tolerance"]) if len(margin) >= 2 else None,
        f"%{_fmt(margin.iloc[-1]*100, 1)}" if len(margin) else None,
        "FAVOK marji yatay veya artan" if len(margin) else "veri yok",
    ))

    # 6 - Operasyonel nakit akisi pozitif (son donem)
    ocf = _last_n(rs(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"), n)
    ocf_last = ocf.iloc[-1] if len(ocf) else None
    crits.append(_crit(
        "operating_cash_flow", "Operasyonel nakit akisi pozitif",
        bool(ocf_last is not None and ocf_last > 0) if len(ocf) else None,
        _fmt(ocf_last) if ocf_last is not None else None,
        "Esas faaliyetten pozitif nakit" if len(ocf) else "veri yok",
    ))

    # 7 - Stok devir hizi (COGS / Inventory) artan
    cogs = _last_n(rs(inc, "Cost Of Revenue", "Reconciled Cost Of Revenue"), n)
    invy = _last_n(rs(bal, "Inventory"), n)
    turn = _turnover_series(cogs, invy)
    crits.append(_crit(
        "inventory_turnover", "Stok devir hizi artan",
        trend_up(turn, cfg["trend_min_up_frac"]) if len(turn) >= 2 else None,
        _fmt(turn.iloc[-1]) if len(turn) else None,
        "Stok devir hizi (SMM/stok) artan trend" if len(turn) else "veri yok (stok kalemi olmayabilir)",
    ))

    # 8 - EPS (Diluted EPS) artis trendi
    eps = _last_n(rs(inc, "Diluted EPS", "Basic EPS"), n)
    crits.append(_crit(
        "eps_growth", "Hisse basina kar (EPS) artisi",
        trend_up(eps, cfg["trend_min_up_frac"]) if len(eps) >= 2 else None,
        _fmt(eps.iloc[-1]) if len(eps) else None,
        f"Son {len(eps)} donem EPS trendi" if len(eps) else "veri yok",
    ))

    passed = sum(1 for c in crits if c["passed"] is True)
    evaluated = sum(1 for c in crits if c["passed"] is not None)
    return {
        "criteria": crits,
        "passed": passed,
        "evaluated": evaluated,
        "total": len(crits),
        "skor": f"{passed}/{evaluated}" if evaluated else "veri yok",
        "ozet": _summary(passed, evaluated),
        "red_flag": red_flag(cf, cfg),
    }


def _summary(passed: int, evaluated: int) -> str:
    if not evaluated:
        return "Finansal tablo verisi cekilemedi"
    r = passed / evaluated
    if r >= 0.75:
        return "Saglikli - cogu kriter olumlu"
    if r >= 0.5:
        return "Orta - karisik tablo"
    return "Zayif - kriterlerin cogu olumsuz"


# ----------------------------------------------------------------------------- kirmizi bayrak (saf)
def red_flag(cf: pd.DataFrame, config: dict | None = None) -> dict:
    """Nakit akistan 'sermaye artirimi -> borc odeme' kalibini arar.

    Mantik: son donemde net hisse ihracindan (sermaye artirimi) belirgin nakit girisi +
    ayni donemde borc odemesi bu nakdin onemli kismi kadar + operasyonel/yatirim nakit
    kullaniminin zayif olmasi -> 'olasi' bayrak. Kesin degildir; dayanilan kalemler gosterilir.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    rs = marketdata.row_series
    issuance = rs(cf, "Net Common Stock Issuance", "Common Stock Issuance")
    repay = rs(cf, "Repayment Of Debt", "Long Term Debt Payments")
    ocf = rs(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    capex = rs(cf, "Capital Expenditure", "Purchase Of PPE")

    if not len(issuance):
        return {"flag": False, "reason": "Sermaye artirimi (hisse ihraci) kalemi yok"}

    iss = float(issuance.iloc[-1])
    rep = abs(float(repay.iloc[-1])) if len(repay) else 0.0
    op = float(ocf.iloc[-1]) if len(ocf) else 0.0
    cx = abs(float(capex.iloc[-1])) if len(capex) else 0.0

    raised = iss > cfg["flag_issuance_min"] and iss > 0
    repaid_big = raised and rep >= cfg["flag_debt_repay_ratio"] * iss
    weak_use = op <= 0 or cx < 0.25 * iss  # operasyon zayif ya da yatirim cuzi

    flag = bool(raised and repaid_big and weak_use)
    return {
        "flag": flag,
        "reason": (
            "Son donemde sermaye artirimindan gelen nakit, operasyon/yatirima degil "
            "agirlikli BORC ODEMESINE gitmis OLABILIR (kesin degil)."
            if flag else
            "Bu kalip icin belirgin sinyal yok"
        ),
        "kalemler": {
            "sermaye_artirimi": iss,
            "borc_odeme": rep,
            "operasyonel_nakit": op,
            "yatirim_capex": cx,
        },
    }


# ----------------------------------------------------------------------------- oran serileri (saf)
def _align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    idx = a.index.intersection(b.index)
    return a.reindex(idx).sort_index(), b.reindex(idx).sort_index()


def _roe_series(ni: pd.Series, eq: pd.Series) -> pd.Series:
    a, b = _align(ni, eq)
    if not len(a):
        return pd.Series(dtype="float64")
    return (a / b.replace(0, pd.NA) * 100).dropna()


def _margin_series(ebitda: pd.Series, rev: pd.Series) -> pd.Series:
    a, b = _align(ebitda, rev)
    if not len(a):
        return pd.Series(dtype="float64")
    return (a / b.replace(0, pd.NA)).dropna()


def _turnover_series(cogs: pd.Series, inv: pd.Series) -> pd.Series:
    a, b = _align(cogs, inv)
    if not len(a):
        return pd.Series(dtype="float64")
    return (a.abs() / b.replace(0, pd.NA)).dropna()


def _div_last(num: pd.Series, den: pd.Series) -> float | None:
    a, b = _align(num, den)
    if not len(a) or b.iloc[-1] == 0 or pd.isna(b.iloc[-1]):
        return None
    return round(float(a.iloc[-1] / b.iloc[-1]), 2)


# ----------------------------------------------------------------------------- ust seviye
def analyze_health(symbol: str, config: dict | None = None) -> dict:
    """Sembol icin saglik kartini marketdata'dan besleyerek uretir."""
    sym = marketdata.normalize_symbol(symbol)
    stmts = marketdata.statements(sym)
    if all(df is None or df.empty for df in stmts.values()):
        return {"ok": False, "symbol": sym, "error": "finansal tablo verisi yok"}
    card = score_card(stmts, config)
    inf = marketdata.info(sym)
    return {
        "ok": True,
        "symbol": sym,
        "name": inf.get("shortName") or inf.get("longName") or sym,
        "currency": inf.get("financialCurrency") or inf.get("currency"),
        "donem_tipi": "ceyreklik" if {**DEFAULT_CONFIG, **(config or {})}["use_quarterly"] else "yillik",
        **card,
    }


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    a = analyze_health(sym)
    if not a.get("ok"):
        print("HATA:", a.get("error")); sys.exit(1)
    print(f"\n=== {a['name']} ({a['symbol']}) — Temel Saglik {a['skor']} — {a['ozet']} ===")
    for c in a["criteria"]:
        mark = "✓" if c["passed"] else ("✗" if c["passed"] is False else "?")
        print(f"  [{mark}] {c['label']:42} ham={c['raw']}  ({c['detail']})")
    rf = a["red_flag"]
    print("\n  KIRMIZI BAYRAK:", "⚠ " + rf["reason"] if rf["flag"] else "yok — " + rf["reason"])
