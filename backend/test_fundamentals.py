"""
Asama 2 birim testleri - Temel Saglik Skoru saf hesaplama mantigi.

Bagimsiz calisir (pytest gerekmez):  python -m backend.test_fundamentals
Sentetik tablolarla skorlamayi ve teknik trend yardimcilarini dogrular; ag erisimi yok.
"""
from __future__ import annotations

import pandas as pd

from . import fundamentals as F


# ----------------------------------------------------------------------------- mini test runner
_passed = 0
_failed = 0


def check(name: str, cond: bool):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✓ {name}")
    else:
        _failed += 1
        print(f"  ✗ {name}  <-- BASARISIZ")


def _dates(n: int):
    # eski -> yeni ceyreklik tarihler (kolon olarak)
    return list(pd.date_range("2024-03-31", periods=n, freq="QE"))


def _df(rows: dict[str, list[float]], n: int) -> pd.DataFrame:
    cols = _dates(n)
    return pd.DataFrame({c: [rows[r][i] for r in rows] for i, c in enumerate(cols)},
                        index=list(rows.keys()))


# ----------------------------------------------------------------------------- saf yardimcilar
def test_trend_up():
    check("trend_up artan seri", F.trend_up(pd.Series([1, 2, 3, 4])) is True)
    check("trend_up azalan seri", F.trend_up(pd.Series([4, 3, 2, 1])) is False)
    check("trend_up dalgali ama net artis", F.trend_up(pd.Series([1, 3, 2, 5])) is True)
    check("trend_up tek eleman", F.trend_up(pd.Series([5.0])) is False)


def test_is_stable():
    check("is_stable duz seri", F.is_stable(pd.Series([100, 101, 99, 100])) is True)
    check("is_stable sert dusus", F.is_stable(pd.Series([100, 100, 100, 40])) is False)
    check("is_stable cok oynak", F.is_stable(pd.Series([10, 100, 5, 120])) is False)


def test_not_decreasing():
    check("not_decreasing yatay", F.not_decreasing(pd.Series([0.3, 0.31, 0.30, 0.32])) is True)
    check("not_decreasing dusen", F.not_decreasing(pd.Series([0.4, 0.3, 0.2, 0.1])) is False)


def test_ratio_series():
    ni = pd.Series([10, 12, 15], index=_dates(3))
    eq = pd.Series([100, 100, 100], index=_dates(3))
    roe = F._roe_series(ni, eq)
    check("ROE serisi yuzde", abs(roe.iloc[-1] - 15.0) < 1e-6)

    ebitda = pd.Series([20, 30], index=_dates(2))
    rev = pd.Series([100, 100], index=_dates(2))
    m = F._margin_series(ebitda, rev)
    check("FAVOK marji orani", abs(m.iloc[-1] - 0.30) < 1e-6)

    cogs = pd.Series([50, 80], index=_dates(2))
    inv = pd.Series([25, 20], index=_dates(2))
    t = F._turnover_series(cogs, inv)
    check("stok devir artan (2.0->4.0)", t.iloc[0] == 2.0 and t.iloc[-1] == 4.0)


# ----------------------------------------------------------------------------- skor karti
def _healthy_stmts(n=4):
    inc = _df({
        "Operating Income": [100, 110, 125, 140],
        "Total Revenue":    [1000, 1010, 1030, 1050],
        "Net Income":       [80, 90, 100, 110],
        "EBITDA":           [200, 215, 235, 260],
        "Cost Of Revenue":  [600, 620, 660, 700],
        "Diluted EPS":      [1.0, 1.1, 1.25, 1.4],
    }, n)
    bal = _df({
        "Stockholders Equity": [500, 510, 520, 530],
        "Current Assets":      [300, 305, 310, 315],
        "Current Liabilities": [180, 182, 185, 188],
        "Inventory":           [120, 110, 100, 95],
    }, n)
    cf = _df({
        "Operating Cash Flow": [90, 95, 105, 120],
        "Net Common Stock Issuance": [0, 0, 0, 0],
        "Repayment Of Debt": [0, 0, 0, -10],
        "Capital Expenditure": [-40, -42, -45, -50],
    }, n)
    return {"income_q": inc, "balance_q": bal, "cashflow_q": cf,
            "income": inc, "balance": bal, "cashflow": cf}


def test_score_card_healthy():
    card = F.score_card(_healthy_stmts())
    # Cari oran ~1.67 -> bandda; ROE = 110/530 ~%20.7 -> gecer; cogu kriter olumlu
    by = {c["key"]: c["passed"] for c in card["criteria"]}
    check("saglikli: esas faaliyet kari gecti", by["operating_income"] is True)
    check("saglikli: ciro istikrari gecti", by["revenue_stability"] is True)
    check("saglikli: ROE gecti", by["roe"] is True)
    check("saglikli: cari oran bandda gecti", by["current_ratio"] is True)
    check("saglikli: op nakit pozitif gecti", by["operating_cash_flow"] is True)
    check("saglikli: stok devir artan gecti", by["inventory_turnover"] is True)
    check("saglikli: EPS artan gecti", by["eps_growth"] is True)
    check("saglikli: toplam >= 7/8", card["passed"] >= 7)
    check("saglikli: kirmizi bayrak yok", card["red_flag"]["flag"] is False)


def test_score_card_weak():
    s = _healthy_stmts()
    # ciroyu coku, op nakdi negatif yap, EPS dusur
    s["income_q"].loc["Total Revenue"] = [1000, 1010, 1030, 600]
    s["income_q"].loc["Diluted EPS"] = [1.4, 1.2, 1.0, 0.5]
    s["cashflow_q"].loc["Operating Cash Flow"] = [90, -10, -30, -50]
    card = F.score_card(s)
    by = {c["key"]: c["passed"] for c in card["criteria"]}
    check("zayif: ciro istikrari kaldi", by["revenue_stability"] is False)
    check("zayif: op nakit kaldi", by["operating_cash_flow"] is False)
    check("zayif: EPS kaldi", by["eps_growth"] is False)


def test_red_flag():
    # Sermaye artirimi 1000, borc odeme 800, op nakit negatif, capex cuzi -> bayrak
    cf = _df({
        "Net Common Stock Issuance": [0, 0, 0, 1000],
        "Repayment Of Debt": [0, 0, 0, -800],
        "Operating Cash Flow": [10, 5, -20, -50],
        "Capital Expenditure": [-5, -5, -5, -10],
    }, 4)
    rf = F.red_flag(cf)
    check("kirmizi bayrak tetiklendi", rf["flag"] is True)
    check("kirmizi bayrak kalemleri var", rf["kalemler"]["sermaye_artirimi"] == 1000)

    # Sermaye artirimi var ama borc odeme yok, op nakit guclu -> bayrak yok
    cf2 = _df({
        "Net Common Stock Issuance": [0, 0, 0, 1000],
        "Repayment Of Debt": [0, 0, 0, 0],
        "Operating Cash Flow": [200, 220, 250, 300],
        "Capital Expenditure": [-300, -320, -350, -400],
    }, 4)
    check("saglikli kullanim: bayrak yok", F.red_flag(cf2)["flag"] is False)


def test_missing_data():
    card = F.score_card({"income_q": pd.DataFrame(), "balance_q": pd.DataFrame(), "cashflow_q": pd.DataFrame()})
    check("bos tablo: evaluated=0", card["evaluated"] == 0)
    check("bos tablo: skor 'veri yok'", card["skor"] == "veri yok")


def main():
    print("== Asama 2 birim testleri ==")
    for fn in [test_trend_up, test_is_stable, test_not_decreasing, test_ratio_series,
               test_score_card_healthy, test_score_card_weak, test_red_flag, test_missing_data]:
        print(f"\n[{fn.__name__}]")
        fn()
    print(f"\n== Sonuc: {_passed} gecti, {_failed} kaldi ==")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
