"""
Piyasa Gucu (Market Breadth) motoru.

Bir hisse grubunu (varsayilan: S&P 500) her gun kapanista tarar ve sunlari uretir:
  1. %4 ve uzeri DEGER KAZANAN hisse sayisi          (up4)
  2. %4 ve uzeri DEGER KAYBEDEN hisse sayisi          (down4)
  3. 5 gunluk ortalama  = ort(up4, 5g) / ort(down4, 5g)   (ratio_5d)
  4. 10 gunluk ortalama = ort(up4, 10g) / ort(down4, 10g) (ratio_10d)

Veri kaynagi: yfinance (ucretsiz, API anahtari gerekmez).
Gecmis SQLite'ta saklanir; her calistirmada eksik gunler tamamlanir.

Kullanim:
    python breadth.py            # S&P 500'u tara, DB'yi guncelle, ozet bas
    python breadth.py --period 6mo
"""
from __future__ import annotations

import argparse
import io
import sqlite3
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

from . import markets

DB_PATH = Path(__file__).parent / "breadth.db"
THRESHOLD = 4.0  # yuzde esigi

# Wikipedia erisilemezse devreye giren yedek liste (kismi ornek; tam liste online cekilir)
_FALLBACK_SP500 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "BRK-B", "AVGO",
    "JPM", "LLY", "V", "UNH", "XOM", "MA", "JNJ", "PG", "HD", "COST",
    "ABBV", "MRK", "CVX", "ADBE", "PEP", "KO", "WMT", "CRM", "BAC", "NFLX",
    "AMD", "ACN", "MCD", "CSCO", "LIN", "TMO", "ABT", "DHR", "INTC", "WFC",
    "QCOM", "TXN", "DIS", "VZ", "PM", "INTU", "CAT", "AMGN", "IBM", "GE",
]


def get_sp500_table() -> pd.DataFrame:
    """S&P 500 tablosunu (Symbol + GICS Sector) Wikipedia'dan ceker.

    macOS Python'da urllib SSL sertifika hatasi verdigi icin once curl_cffi
    (yfinance ile gelir, TLS/sertifikayi dogru yonetir) denenir; o da olmazsa urllib.
    yfinance nokta yerine tire kullanir (BRK.B -> BRK-B). Basarisizsa yedek doner.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def _parse(html: bytes) -> pd.DataFrame:
        table = pd.read_html(io.BytesIO(html))[0]
        out = pd.DataFrame(
            {
                "symbol": table["Symbol"].astype(str).str.replace(".", "-", regex=False),
                "sector": table["GICS Sector"].astype(str),
            }
        )
        return out

    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(url, impersonate="chrome", timeout=20)
        df = _parse(resp.content)
        if len(df) > 400:
            return df
    except Exception as exc:  # noqa: BLE001
        print(f"[uyari] curl_cffi ile liste cekilemedi ({exc}); urllib deneniyor.", file=sys.stderr)

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        df = _parse(urlopen(req, timeout=20).read())
        if len(df) > 400:
            return df
    except Exception as exc:  # noqa: BLE001
        print(f"[uyari] S&P 500 listesi cekilemedi ({exc}); yedek liste kullaniliyor.", file=sys.stderr)

    return pd.DataFrame({"symbol": _FALLBACK_SP500, "sector": "Bilinmiyor"})


def get_sp500_tickers() -> list[str]:
    """Sadece sembol listesini doner (geriye uyumluluk)."""
    return get_sp500_table()["symbol"].tolist()


def compute_breadth(tickers: list[str], period: str = "3mo") -> pd.DataFrame:
    """Tum hisselerin gunluk %% degisimini hesaplar; gun bazinda up4/down4 sayar.

    Donen DataFrame index'i tarih; kolonlar: up4, down4, total, ratio,
    up4_5d, down4_5d, ratio_5d, up4_10d, down4_10d, ratio_10d.
    """
    print(f"[bilgi] {len(tickers)} hisse indiriliyor (period={period})...", file=sys.stderr)
    data = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data.empty:
        raise RuntimeError("yfinance bos veri dondu. Internet/erisim sorununu kontrol et.")

    # Coklu hisse -> kolonlar MultiIndex ("Close", ticker). Tek hisse -> duz kolon.
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]]
    close = close.dropna(how="all")

    # Gunluk yuzde degisim (her hisse icin), yuzde cinsinden
    pct = close.pct_change() * 100.0

    up4 = (pct >= THRESHOLD).sum(axis=1)
    down4 = (pct <= -THRESHOLD).sum(axis=1)
    total = pct.notna().sum(axis=1)  # o gun verisi olan hisse sayisi

    df = pd.DataFrame({"up4": up4, "down4": down4, "total": total})
    df = df.iloc[1:]  # ilk gun pct_change NaN -> at

    df["ratio"] = df["up4"] / df["down4"].replace(0, pd.NA)

    for w, tag in ((5, "5d"), (10, "10d")):
        u = df["up4"].rolling(w).mean()
        d = df["down4"].rolling(w).mean()
        df[f"up4_{tag}"] = u.round(2)
        df[f"down4_{tag}"] = d.round(2)
        df[f"ratio_{tag}"] = (u / d.replace(0, pd.NA)).round(3)

    df.index = pd.to_datetime(df.index).date
    df.index.name = "date"
    return df


_NEW_SCHEMA = """
    CREATE TABLE IF NOT EXISTS breadth (
        date TEXT NOT NULL,
        market TEXT NOT NULL DEFAULT 'us',
        up4 INTEGER, down4 INTEGER, total INTEGER, ratio REAL,
        up4_5d REAL, down4_5d REAL, ratio_5d REAL,
        up4_10d REAL, down4_10d REAL, ratio_10d REAL,
        PRIMARY KEY (date, market)
    )
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Tabloyu olusturur; eski (market kolonsuz) semayi gocurur. Idempotent.

    v1 sema: PRIMARY KEY(date) — tek piyasa (ABD). Cok-piyasa icin (date, market)
    bilesik anahtara gecilir; eski satirlar market='us' ile tasinir. Gocum ayni
    transaction'da commit edilir (yarim kalmis gocum birakmaz).
    """
    conn.execute(_NEW_SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(breadth)")}
    migrated = False

    if "market" not in cols:
        # Eski v1 tablo: market kolonu yok. Gecici tabloya tasi, yeni semayi kur.
        conn.execute("ALTER TABLE breadth RENAME TO breadth_legacy")
        conn.execute(_NEW_SCHEMA)
        migrated = True

    # Legacy tablo varsa (taze gocum ya da onceden yarim kalmis gocum) veriyi tasi.
    has_legacy = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='breadth_legacy'"
    ).fetchone()
    if has_legacy:
        conn.execute(
            """
            INSERT OR IGNORE INTO breadth
                (date, market, up4, down4, total, ratio,
                 up4_5d, down4_5d, ratio_5d, up4_10d, down4_10d, ratio_10d)
            SELECT date, 'us', up4, down4, total, ratio,
                   up4_5d, down4_5d, ratio_5d, up4_10d, down4_10d, ratio_10d
            FROM breadth_legacy
            """
        )
        conn.execute("DROP TABLE breadth_legacy")
        migrated = True

    if migrated:
        conn.commit()


def save_history(df: pd.DataFrame, market: str = "us", db_path: Path = DB_PATH) -> None:
    """Gecmisi SQLite'a yazar (UPSERT). Ayni gun+piyasa tekrar calistirilirsa guncellenir."""
    market = markets.normalize_market(market)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        rows = [
            (
                str(d), market, int(r.up4), int(r.down4), int(r.total),
                _f(r.ratio), _f(r.up4_5d), _f(r.down4_5d), _f(r.ratio_5d),
                _f(r.up4_10d), _f(r.down4_10d), _f(r.ratio_10d),
            )
            for d, r in df.iterrows()
        ]
        conn.executemany(
            """
            INSERT INTO breadth VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(date, market) DO UPDATE SET
                up4=excluded.up4, down4=excluded.down4, total=excluded.total, ratio=excluded.ratio,
                up4_5d=excluded.up4_5d, down4_5d=excluded.down4_5d, ratio_5d=excluded.ratio_5d,
                up4_10d=excluded.up4_10d, down4_10d=excluded.down4_10d, ratio_10d=excluded.ratio_10d
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def load_history(market: str = "us", db_path: Path = DB_PATH) -> list[dict]:
    """Bir piyasanin kayitli gecmisini tarih sirali liste olarak doner (dashboard icin)."""
    if not db_path.exists():
        return []
    market = markets.normalize_market(market)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            "SELECT * FROM breadth WHERE market = ? ORDER BY date ASC", (market,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _f(v) -> float | None:
    """NaN/NA -> None (SQLite ve JSON icin)."""
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:  # noqa: BLE001
        return None


def signal(ratio_5d: float | None) -> str:
    """5 gunluk orana gore kaba piyasa gucu yorumu (kural tabanli)."""
    if ratio_5d is None:
        return "Yetersiz veri (5 gun birikmeli)"
    if ratio_5d >= 2.0:
        return "GUCLU ALICILI - genis tabanli yukselis"
    if ratio_5d >= 1.2:
        return "Pozitif - alicilar onde"
    if ratio_5d >= 0.8:
        return "Notr - dengeli / kararsiz"
    if ratio_5d >= 0.5:
        return "Negatif - saticilar onde"
    return "GUCLU SATICILI - genis tabanli dusus"


def run(period: str = "3mo", market: str = "us") -> dict:
    market = markets.normalize_market(market)
    tickers = markets.get_table(market)["symbol"].tolist()
    df = compute_breadth(tickers, period=period)
    save_history(df, market=market)
    last = df.iloc[-1]
    summary = {
        "date": str(df.index[-1]),
        "market": market,
        "evren": len(tickers),
        "veri_olan": int(last.total),
        "up4": int(last.up4),
        "down4": int(last.down4),
        "ratio": _f(last.ratio),
        "ratio_5d": _f(last.ratio_5d),
        "ratio_10d": _f(last.ratio_10d),
        "yorum": signal(_f(last.ratio_5d)),
    }
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Piyasa Gucu (Market Breadth) tarayici")
    ap.add_argument("--period", default="3mo", help="yfinance period (orn: 1mo, 3mo, 6mo, 1y)")
    ap.add_argument("--market", default="us", choices=list(markets.MARKETS), help="piyasa: us | bist")
    args = ap.parse_args()

    s = run(period=args.period, market=args.market)
    evren_label = markets.MARKETS[s["market"]]["evren_label"]
    print("\n" + "=" * 48)
    print(f"  PIYASA GUCU ({evren_label})  -  {s['date']}")
    print("=" * 48)
    print(f"  Evren ({evren_label})          : {s['evren']} hisse")
    print(f"  O gun verisi olan        : {s['veri_olan']} hisse")
    print(f"  >= +%4 yukselen          : {s['up4']}")
    print(f"  <= -%4 dusen             : {s['down4']}")
    print(f"  Gunluk oran (up/down)    : {s['ratio']}")
    print(f"  5 gunluk ortalama oran   : {s['ratio_5d']}")
    print(f"  10 gunluk ortalama oran  : {s['ratio_10d']}")
    print(f"  Yorum                    : {s['yorum']}")
    print("=" * 48 + "\n")
