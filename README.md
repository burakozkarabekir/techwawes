# Finansal Analist

Kural tabanlı, sektör → şirket → haber → senaryo mantığıyla çalışan finansal analiz aracı.
Sana "şu fiyattan al/sat" demez; piyasanın gücünü ölçer, sektör/şirket görünümü çıkarır, senaryo yazar.

**İki piyasa:** 🇺🇸 ABD (S&P 500) ve 🇹🇷 BIST (Borsa İstanbul ~117 likit hisse). Dashboard'ın
üstündeki seçiciyle geçiş yapılır; tüm modüller (Piyasa Gücü, Sektörler, Şirket Analizi) her
iki piyasada da çalışır. BIST sembolü çıplak yazılabilir (`THYAO` → `THYAO.IS`).

## Yol haritası (modüller)

| # | Modül | Durum |
|---|-------|-------|
| 1 | **Piyasa Gücü (Market Breadth)** — S&P 500 + BIST'i her kapanışta tara: ≥%4 yükselen/düşen + 5g/10g ort. | ✅ Çalışıyor |
| 2 | Portföy & sıkı mal takibi | Planlı |
| 3 | **Haber + temel takibinden hareketli stop-loss / kâr-al** (ATR tabanlı) | ✅ Çalışıyor |
| 4 | **Sektör görünümü → şirket seçimi anlatısı** (3 modlu senaryo) | ✅ Çalışıyor |
| 5 | "Alttan ucuz mal bul" tarama motoru (AI/sektör) | Planlı |

## Modül 1 — Piyasa Gücü

Her kapanışta S&P 500'ün **500 hissesini** tarar ve üretir:
1. ≥ +%4 değer kazanan hisse sayısı
2. ≥ −%4 değer kaybeden hisse sayısı
3. 5 günlük ortalama = ort(↑%4, 5g) / ort(↓%4, 5g)
4. 10 günlük ortalama = ort(↑%4, 10g) / ort(↓%4, 10g)

> Oran > 1 → alıcılar önde, geniş tabanlı yükseliş. Oran < 1 → satıcılar önde.
> Geçmiş tek seferde çekildiği için 5/10 günlük ortalamalar gün beklemeden hemen hesaplanır.

Veri kaynağı: **yfinance** (ücretsiz, API anahtarı yok). Geçmiş `backend/breadth.db` (SQLite) içinde saklanır.

## Modül 4 — Sektör görünümü & Modül 3 — Stop/Hedef

"Amele gibi bilanço okuma" yerine: sektörü yazar, şirketin teknik + temel + bilanço özetini
çıkarır, son haberleri listeler, **3 modlu senaryo** (gerçekçi/iyimser/karamsar) yazar.
Sana "şu fiyattan al" demez — "X sektörü güçlü çünkü…, Y şirketi şu yüzden öne çıkıyor" der.

- **Sektör sıralaması:** S&P 500 GICS sektörleri 3 ay / 1 ay momentuma göre sıralanır + her sektörün liderleri.
- **Şirket analizi:** teknik (RSI, ATR, MA50/200, momentum, 52h konum, destek/direnç) + temel (F/K, ileri F/K, PEG, marj, büyüme, ROE, borç/özkaynak, analist hedefi) + son haberler → skor → 3 senaryo.
- **Stop/Hedef (Modül 3):** ATR tabanlı **hareketli** stop-loss; duruşa göre çarpan ayarlanır (pozitifte 3×ATR "koşmaya bırak", negatifte 1.5×ATR "sermaye koru"). Hedefler 2R/3R + direnç uzaklığı.

```bash
python -m backend.sectors            # ABD sektör sıralaması (terminal)
python -m backend.sectors bist       # BIST sektör sıralaması
python -m backend.company NVDA       # tam şirket analizi + senaryo + stop/hedef
python -m backend.company THYAO      # BIST: çıplak sembol .IS'e çevrilir
```

API: `GET /api/sectors?market=us|bist`, `GET /api/company/{SEMBOL}` · Dashboard'da "Sektörler" ve "Şirket Analizi" sekmeleri (üstteki ABD/BIST seçicisi tüm sekmeleri yönetir).

## TechWawes 6-Aşama Analiz Modülleri (yeni)

Birleşik veri katmanı üzerine kurulu, hem ABD hem BIST'te çalışan ileri analiz seti.
Hesaplama mantığı (skor, teknik sinyaller, RS) **birim testlidir**
(`python -m backend.test_fundamentals` · `python -m backend.test_signals` → 45 test).

| Aşama | Ne yapar | Endpoint | Veri notu |
|-------|----------|----------|-----------|
| 1 · Veri katmanı | `marketdata.py` — tek servis: OHLCV, finansal tablolar, kurumsal olaylar; TTL cache | — | yfinance |
| 2 · Temel Sağlık Skoru | 8 kriter (esas faaliyet kârı, ciro istikrarı, ROE, cari oran, FAVÖK marjı, op. nakit, stok devir, EPS) geçti/kaldı + **kırmızı bayrak** (sermaye artırımı→borç ödeme) | `/api/health/{sym}` | Yıllık tablolar (ABD+BIST) |
| 3 · Haber akışı | Tekilleştirilmiş, tarihe sıralı haber | `/api/news/{sym}` | X/Twitter dedikodu **kapsam dışı** (karar) |
| 4 · Sektörel tarama | **Birikim** (fiyat yatay+hacim artan) + **golden/death cross** | `/api/scan?market=` | OHLCV |
| 5 · Grafik + işaretler | Fiyat/MA50/MA200 + **içeriden işlem** & **geri alım** işaretleri (hover detay) | `/api/chart/{sym}` | İçeriden işlem ABD'de var; **BIST'te yok** ("veri yok" rozeti, ileride KAP) |
| 6 · Karşılaştırma & RS | **RS Rating 1–99**, oran grafiği (hisse/benchmark), karşılaştırma, **top-down** (en güçlü sektör→hisse) | `/api/rs`, `/api/rs/topdown`, `/api/ratio/{sym}`, `/api/compare?symbols=` | OHLCV |

> Dürüstlük kuralı: yfinance'te karşılığı olmayan metrikler (BIST içeriden işlem/sermaye
> artırımı/geri alım tarihleri, X dedikoduları) **uydurulmaz**, "veri yok" olarak işaretlenir.

Tarama ve RS ağır (tüm evreni indirir); piyasa başına 30 dk cache'lenir, ilk istekte hesaplanır.

```bash
python -m backend.fundamentals AAPL      # temel sağlık skoru
python -m backend.scanner bist           # birikim + cross taraması
python -m backend.rs us                  # top-down güç seçimi
python -m backend.events NVDA            # içeriden işlem / geri alım işaretleri
```

## Kurulum & çalıştırma

```bash
cd finansal-analist
./run.sh                      # venv kurar, bağımlılıkları yükler, sunucuyu açar
# tarayıcı: http://127.0.0.1:8000  → "Şimdi Tara" butonu
```

Sadece terminalde (web olmadan) çalıştırmak için:

```bash
source .venv/bin/activate
python -m backend.breadth --period 6mo               # ABD (S&P 500)
python -m backend.breadth --market bist --period 6mo # BIST
```

## Günlük otomasyon

Web sunucusu açıkken zaten her piyasa kendi kapanış saatinde otomatik taranır (BIST 16:00 UTC,
ABD 22:30 UTC). Sunucusuz, salt-cron ile çalıştırmak için:

```cron
# BIST kapanışı (18:00 TSİ ≈ 15:00 UTC) sonrası
30 18 * * 1-5  cd /Users/bozkarabekir/finansal-analist && .venv/bin/python -m backend.breadth --market bist >> breadth.log 2>&1
# ABD kapanışı sonrası
30 23 * * 1-5  cd /Users/bozkarabekir/finansal-analist && .venv/bin/python -m backend.breadth --market us >> breadth.log 2>&1
```
