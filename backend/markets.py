"""
Piyasa kayit defteri (multi-market).

Uygulama bastan tek-piyasaydi (S&P 500 / ABD). Bu modul piyasa kavramini
soyutlar: her piyasanin bir EVRENI (sembol + sektor tablosu), para birimi,
breadth kapanis saati ve ornek sembolu vardir. Boylece breadth.py / sectors.py /
app.py "market" parametresiyle hem ABD hem BIST icin calisir.

ABD evreni dinamik (S&P 500, Wikipedia'dan; breadth.get_sp500_table).
BIST evreni burada elle tutulan likit/bilinen ~100 hisseden olusur (Yahoo `.IS`
sembolleri). Birkac sembol gecersiz olsa bile breadth/sektor kodu NaN kolonlari
zaten atar; bu yuzden liste "yeterince iyi" olmasi kafidir.
"""
from __future__ import annotations

import pandas as pd

# ----------------------------------------------------------------------------- BIST evreni
# (bare_symbol, sektor). Yahoo'da `.IS` ile sorgulanir (get_bist_table ekler).
# Sektorler GICS yerine BIST'e uygun, sade Turkce etiketler.
_BIST: list[tuple[str, str]] = [
    # --- Bankacilik ---
    ("AKBNK", "Bankacilik"), ("GARAN", "Bankacilik"), ("YKBNK", "Bankacilik"),
    ("ISCTR", "Bankacilik"), ("VAKBN", "Bankacilik"), ("HALKB", "Bankacilik"),
    ("TSKB", "Bankacilik"), ("ALBRK", "Bankacilik"), ("SKBNK", "Bankacilik"),
    # --- Holding ---
    ("KCHOL", "Holding"), ("SAHOL", "Holding"), ("AGHOL", "Holding"),
    ("ENKAI", "Holding"), ("ALARK", "Holding"), ("TKFEN", "Holding"),
    ("GLYHO", "Holding"), ("DOHOL", "Holding"), ("IHLAS", "Holding"),
    ("GSDHO", "Holding"),
    # --- Otomotiv & Yan Sanayi ---
    ("FROTO", "Otomotiv"), ("TOASO", "Otomotiv"), ("DOAS", "Otomotiv"),
    ("OTKAR", "Otomotiv"), ("KARSN", "Otomotiv"), ("TTRAK", "Otomotiv"),
    ("EGEEN", "Otomotiv"), ("BFREN", "Otomotiv"), ("PARSN", "Otomotiv"),
    # --- Beyaz Esya / Dayanikli Tuketim ---
    ("ARCLK", "Dayanikli Tuketim"), ("VESTL", "Dayanikli Tuketim"),
    ("VESBE", "Dayanikli Tuketim"), ("KLMSN", "Dayanikli Tuketim"),
    # --- Demir-Celik / Metal ---
    ("EREGL", "Demir-Celik"), ("KRDMD", "Demir-Celik"), ("CEMTS", "Demir-Celik"),
    ("BURCE", "Demir-Celik"), ("IZMDC", "Demir-Celik"),
    # --- Cimento ---
    ("AKCNS", "Cimento"), ("CIMSA", "Cimento"), ("OYAKC", "Cimento"),
    ("BUCIM", "Cimento"), ("NUHCM", "Cimento"), ("GOLTS", "Cimento"),
    ("KONYA", "Cimento"),
    # --- Enerji & Elektrik ---
    ("AKSEN", "Enerji"), ("ZOREN", "Enerji"), ("ODAS", "Enerji"),
    ("ENJSA", "Enerji"), ("AYGAZ", "Enerji"), ("GWIND", "Enerji"),
    ("BIOEN", "Enerji"), ("AKFYE", "Enerji"), ("ALFAS", "Enerji"),
    ("ASTOR", "Enerji"),
    # --- Petrokimya / Kimya ---
    ("TUPRS", "Petrokimya-Kimya"), ("PETKM", "Petrokimya-Kimya"),
    ("SASA", "Petrokimya-Kimya"), ("GUBRF", "Petrokimya-Kimya"),
    ("BAGFS", "Petrokimya-Kimya"), ("HEKTS", "Petrokimya-Kimya"),
    ("ALKIM", "Petrokimya-Kimya"), ("BRISA", "Petrokimya-Kimya"),
    ("GOODY", "Petrokimya-Kimya"),
    # --- Perakende ---
    ("BIMAS", "Perakende"), ("MGROS", "Perakende"), ("SOKM", "Perakende"),
    ("BIZIM", "Perakende"), ("MAVI", "Perakende"), ("CRFSA", "Perakende"),
    ("VAKKO", "Perakende"),
    # --- Gida-Icecek ---
    ("ULKER", "Gida-Icecek"), ("CCOLA", "Gida-Icecek"), ("AEFES", "Gida-Icecek"),
    ("TATGD", "Gida-Icecek"), ("TUKAS", "Gida-Icecek"), ("PNSUT", "Gida-Icecek"),
    ("BANVT", "Gida-Icecek"), ("KNFRT", "Gida-Icecek"), ("PETUN", "Gida-Icecek"),
    # --- Telekom & Teknoloji ---
    ("TCELL", "Telekom-Teknoloji"), ("TTKOM", "Telekom-Teknoloji"),
    ("ASELS", "Telekom-Teknoloji"), ("LOGO", "Telekom-Teknoloji"),
    ("ARENA", "Telekom-Teknoloji"), ("INDES", "Telekom-Teknoloji"),
    ("KAREL", "Telekom-Teknoloji"), ("NETAS", "Telekom-Teknoloji"),
    ("ALCTL", "Telekom-Teknoloji"), ("KFEIN", "Telekom-Teknoloji"),
    ("SMART", "Telekom-Teknoloji"), ("FONET", "Telekom-Teknoloji"),
    ("ARDYZ", "Telekom-Teknoloji"),
    # --- Ulastirma (Havayolu) ---
    ("THYAO", "Ulastirma"), ("PGSUS", "Ulastirma"), ("TAVHL", "Ulastirma"),
    ("CLEBI", "Ulastirma"),
    # --- GYO (Gayrimenkul) ---
    ("EKGYO", "GYO"), ("ISGYO", "GYO"), ("TRGYO", "GYO"), ("KLGYO", "GYO"),
    ("OZKGY", "GYO"), ("RYGYO", "GYO"), ("VKGYO", "GYO"), ("AKFGY", "GYO"),
    # --- Cam ---
    ("SISE", "Cam"),
    # --- Madencilik ---
    ("PRKME", "Madencilik"),
    # --- Sigorta ---
    ("ANSGR", "Sigorta"), ("AKGRT", "Sigorta"), ("TURSG", "Sigorta"),
    ("AGESA", "Sigorta"), ("ANHYT", "Sigorta"), ("RAYSG", "Sigorta"),
    # --- Saglik-Ilac ---
    ("MPARK", "Saglik-Ilac"), ("LKMNH", "Saglik-Ilac"), ("DEVA", "Saglik-Ilac"),
    ("SELEC", "Saglik-Ilac"), ("ECILC", "Saglik-Ilac"),
]

BIST_SUFFIX = ".IS"
# Yahoo sembollerinin .IS olmadan kume hali (company.py sembol normalizasyonu icin)
BIST_BARE_SET: set[str] = {sym for sym, _ in _BIST}


def get_bist_table() -> pd.DataFrame:
    """BIST evrenini Yahoo `.IS` sembolu + sektor olarak doner (breadth tablosu formatinda)."""
    return pd.DataFrame(
        {
            "symbol": [sym + BIST_SUFFIX for sym, _ in _BIST],
            "sector": [sec for _, sec in _BIST],
        }
    )


# ----------------------------------------------------------------------------- piyasa kayit defteri
# table_fn lazy import edilir (breadth -> markets dongusel import olmasin diye).
def _us_table() -> pd.DataFrame:
    from . import breadth
    return breadth.get_sp500_table()


MARKETS: dict[str, dict] = {
    "us": {
        "label": "ABD (S&P 500)",
        "evren_label": "S&P 500",
        "currency": "USD",
        "table_fn": _us_table,
        "ornek": "AAPL",
        "benchmark": "^GSPC",        # S&P 500 endeksi (oran grafigi / RS referansi)
        "benchmark_label": "S&P 500",
        # ABD kapanis ~20:00 UTC; 22:30'da guvenli yenile
        "breadth_cron": {"hour": 22, "minute": 30},
    },
    "bist": {
        "label": "BIST (Borsa Istanbul)",
        "evren_label": "BIST ~100",
        "currency": "TRY",
        "table_fn": get_bist_table,
        "ornek": "THYAO",
        "benchmark": "XU100.IS",     # BIST 100 endeksi
        "benchmark_label": "BIST 100",
        # BIST kapanis 18:00 TR = 15:00 UTC; 16:00 UTC'de guvenli yenile
        "breadth_cron": {"hour": 16, "minute": 0},
    },
}

DEFAULT_MARKET = "us"


def normalize_market(market: str | None) -> str:
    """Gecersiz/eksik piyasa adini varsayilana cevirir."""
    m = (market or "").strip().lower()
    return m if m in MARKETS else DEFAULT_MARKET


def get_table(market: str) -> pd.DataFrame:
    """Piyasanin evren tablosunu (symbol, sector) doner."""
    return MARKETS[normalize_market(market)]["table_fn"]()
