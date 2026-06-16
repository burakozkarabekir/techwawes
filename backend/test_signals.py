"""
Asama 4 + 6 birim testleri - tarama sinyalleri ve RS hesaplari (saf).

Bagimsiz calisir:  python -m backend.test_signals
"""
from __future__ import annotations

import pandas as pd

from . import rs
from . import scanner as S

_passed = _failed = 0


def check(name: str, cond: bool):
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  ✓ {name}")
    else:
        _failed += 1; print(f"  ✗ {name}  <-- BASARISIZ")


def _ohlcv(closes: list[float], vols: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"Close": closes, "Volume": vols}, index=idx)


# ----------------------------------------------------------------------------- accumulation
def test_accumulation():
    # fiyat yatay (100 +-1), hacim ikinci yari ~2x
    closes = [100 + (i % 3 - 1) for i in range(30)]      # ~99-101 dar bant
    vols = [1000] * 15 + [2200] * 15                      # ikinci yari 2.2x
    sig = S.accumulation_signal(_ohlcv(closes, vols), flat_window=30)
    check("birikim: yatay+hacim artan tetiklendi", sig is not None and sig["signal"] == "birikim")
    check("birikim: vol_ratio ~2.2", sig and abs(sig["vol_ratio"] - 2.2) < 0.1)

    # hacim artmiyor -> sinyal yok
    flat_vol = S.accumulation_signal(_ohlcv(closes, [1000] * 30), flat_window=30)
    check("birikim: hacim sabit -> sinyal yok", flat_vol is None)

    # fiyat genis bantta -> sinyal yok
    trend = S.accumulation_signal(_ohlcv(list(range(70, 100)), [1000] * 15 + [3000] * 15), flat_window=30)
    check("birikim: fiyat trendde -> sinyal yok", trend is None)


# ----------------------------------------------------------------------------- cross
def test_cross():
    # 210 gun duz 100, son 6 gun 200 -> MA50 MA200'u yukari keser (golden)
    g = _ohlcv([100] * 210 + [200] * 6, [1000] * 216)
    sig = S.cross_signal(g, lookback=10)
    check("golden cross tetiklendi", sig is not None and sig["signal"] == "golden")

    # tam tersi -> death
    d = _ohlcv([200] * 210 + [100] * 6, [1000] * 216)
    sigd = S.cross_signal(d, lookback=10)
    check("death cross tetiklendi", sigd is not None and sigd["signal"] == "death")

    # tamamen duz -> cross yok
    flat = S.cross_signal(_ohlcv([100] * 260, [1000] * 260), lookback=10)
    check("duz seri -> cross yok", flat is None)

    # yetersiz veri -> None
    short = S.cross_signal(_ohlcv([100] * 50, [1000] * 50))
    check("kisa seri -> None", short is None)


# ----------------------------------------------------------------------------- RS
def test_weighted_return():
    up = pd.Series(range(100, 360))      # surekli artan
    down = pd.Series(range(360, 100, -1))
    check("agirlikli getiri artan -> pozitif", rs.weighted_return(up) > 0)
    check("agirlikli getiri dusen -> negatif", rs.weighted_return(down) < 0)
    check("kisa seri -> None", rs.weighted_return(pd.Series([1, 2, 3])) is None)


def test_percentile():
    raw = {"A": -5.0, "B": 0.0, "C": 5.0, "D": 10.0, "E": 20.0}
    r = rs.percentile_ranks(raw)
    check("en guclu 99", r["E"] == 99)
    check("en zayif 1", r["A"] == 1)
    check("orta deger ortada", 40 <= r["C"] <= 60)
    check("tek eleman -> 99", rs.percentile_ranks({"X": 3.0}) == {"X": 99})
    check("bos -> bos", rs.percentile_ranks({}) == {})


def main():
    print("== Asama 4+6 birim testleri ==")
    for fn in [test_accumulation, test_cross, test_weighted_return, test_percentile]:
        print(f"\n[{fn.__name__}]")
        fn()
    print(f"\n== Sonuc: {_passed} gecti, {_failed} kaldi ==")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
