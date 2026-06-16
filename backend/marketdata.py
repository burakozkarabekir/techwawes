"""
Asama 1 - Birlesik piyasa veri servisi (marketDataService).

Tum yfinance erisimini TEK yerde toplar ve TTL'li onbellege alir (rate-limit dostu).
Yeni moduller (fundamentals, news, scanner, rs, events) Yahoo'ya dogrudan degil
bu servisten gecer; boylece veri saglayicisi degisse bile tek dosya degisir.

Yetenekler:
  ohlcv(sym, period, interval)  -> fiyat/hacim gecmisi (DataFrame)
  info(sym)                     -> ozet sozluk (.info)
  statements(sym)               -> finansal tablolar (gelir/bilanco/nakit, yillik+ceyreklik)
  actions(sym)                  -> temettu + split
  insider(sym)                  -> iceriden islemler (cogunlukla ABD; BIST'te bos)
  normalize_symbol(sym)         -> BIST ciplak sembolu .IS'e cevirir

Tablo satirlarini cekmek icin row_series() yardimcisi: istenen satiri eski->yeni
sirali bir pandas Series olarak doner (hesaplama modulleri bununla calisir).
"""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

from . import markets

# Onbellek: {anahtar: (zaman, deger)}. Tur bazinda farkli TTL.
_CACHE: dict[str, tuple[float, object]] = {}
TTL_PRICE = 900       # 15 dk  (fiyat sik degisir)
TTL_INFO = 1800       # 30 dk
TTL_STATEMENTS = 21600  # 6 saat (tablolar ceyrekte bir degisir)
TTL_EVENTS = 21600    # 6 saat


def _cached(key: str, ttl: int, producer):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = producer()
    _CACHE[key] = (now, val)
    return val


def invalidate(symbol: str | None = None) -> None:
    """Onbellegi bayatlatir. symbol=None -> tum onbellek."""
    if symbol is None:
        _CACHE.clear()
        return
    sym = normalize_symbol(symbol)
    for k in [k for k in _CACHE if k.endswith("|" + sym)]:
        _CACHE.pop(k, None)


# ----------------------------------------------------------------------------- sembol
def normalize_symbol(symbol: str) -> str:
    """Kullanici sembolunu Yahoo formatina cevirir.

    BIST hisseleri Yahoo'da `.IS` ister (THYAO -> THYAO.IS). Sembol cipla yazilmis
    ve bilinen BIST evrenindeyse `.IS` eklenir; zaten suffix varsa dokunulmaz.
    """
    s = (symbol or "").upper().strip()
    if "." not in s and s in markets.BIST_BARE_SET:
        return s + markets.BIST_SUFFIX
    return s


def _ticker(sym: str) -> yf.Ticker:
    return yf.Ticker(sym)


# ----------------------------------------------------------------------------- fiyat
def ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """OHLCV fiyat/hacim gecmisi. Onbellekli."""
    sym = normalize_symbol(symbol)
    key = f"ohlcv:{period}:{interval}|{sym}"

    def _produce():
        try:
            df = _ticker(sym).history(period=period, interval=interval, auto_adjust=True)
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
        return df if df is not None else pd.DataFrame()

    return _cached(key, TTL_PRICE, _produce)


def info(symbol: str) -> dict:
    """Ozet bilgi sozlugu (.info). Onbellekli."""
    sym = normalize_symbol(symbol)

    def _produce():
        try:
            return _ticker(sym).info or {}
        except Exception:  # noqa: BLE001
            return {}

    return _cached(f"info|{sym}", TTL_INFO, _produce)


# ----------------------------------------------------------------------------- finansal tablolar
def statements(symbol: str) -> dict[str, pd.DataFrame]:
    """Gelir/bilanco/nakit tablolarini (yillik + ceyreklik) tek sozlukte doner.

    Anahtarlar: income, income_q, balance, balance_q, cashflow, cashflow_q.
    Her biri yfinance formatinda DataFrame (index=kalem, kolon=donem, yeni->eski).
    """
    sym = normalize_symbol(symbol)

    def _produce():
        t = _ticker(sym)
        out: dict[str, pd.DataFrame] = {}
        pairs = [
            ("income", "income_stmt"), ("income_q", "quarterly_income_stmt"),
            ("balance", "balance_sheet"), ("balance_q", "quarterly_balance_sheet"),
            ("cashflow", "cashflow"), ("cashflow_q", "quarterly_cashflow"),
        ]
        for key, attr in pairs:
            try:
                df = getattr(t, attr)
                out[key] = df if df is not None else pd.DataFrame()
            except Exception:  # noqa: BLE001
                out[key] = pd.DataFrame()
        return out

    return _cached(f"stmts|{sym}", TTL_STATEMENTS, _produce)


def actions(symbol: str) -> pd.DataFrame:
    """Temettu + bolunme (split) gecmisi."""
    sym = normalize_symbol(symbol)

    def _produce():
        try:
            return _ticker(sym).actions
        except Exception:  # noqa: BLE001
            return pd.DataFrame()

    return _cached(f"actions|{sym}", TTL_EVENTS, _produce)


def insider(symbol: str) -> pd.DataFrame:
    """Iceriden islemler (Yahoo). Cogunlukla ABD; BIST'te genelde bos doner."""
    sym = normalize_symbol(symbol)

    def _produce():
        try:
            df = _ticker(sym).insider_transactions
            return df if df is not None else pd.DataFrame()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()

    return _cached(f"insider|{sym}", TTL_EVENTS, _produce)


# ----------------------------------------------------------------------------- tablo yardimcisi
def row_series(df: pd.DataFrame, *names: str) -> pd.Series:
    """Tablodan ilk eslesn satiri ESKI->YENI sirali Series olarak doner.

    yfinance kolonlari yeni->eski siralidir; burada tarihe gore artan siralanir.
    Birden cok ad verilebilir (ilk bulunan kullanilir). Bulunmazsa bos Series.
    """
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    for name in names:
        if name in df.index:
            s = df.loc[name]
            # Ayni ad birden cok satira denk gelirse ilkini al
            if isinstance(s, pd.DataFrame):
                s = s.iloc[0]
            s = pd.to_numeric(s, errors="coerce")
            try:
                s = s.sort_index()  # tarih artan
            except Exception:  # noqa: BLE001
                pass
            return s.dropna()
    return pd.Series(dtype="float64")
