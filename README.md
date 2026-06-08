# Finansal Analist

Kural tabanlı, sektör → şirket → haber → senaryo mantığıyla çalışan finansal analiz aracı.
Sana "şu fiyattan al/sat" demez; piyasanın gücünü ölçer, sektör/şirket görünümü çıkarır, senaryo yazar.

## Yol haritası (modüller)

| # | Modül | Durum |
|---|-------|-------|
| 1 | **Piyasa Gücü (Market Breadth)** — S&P 500'ü her kapanışta tara: ≥%4 yükselen/düşen + 5g/10g ort. | ✅ Çalışıyor |
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
python -m backend.sectors            # sektör sıralaması (terminal)
python -m backend.company NVDA       # tam şirket analizi + senaryo + stop/hedef
```

API: `GET /api/sectors`, `GET /api/company/{SEMBOL}` · Dashboard'da "Sektörler" ve "Şirket Analizi" sekmeleri.

## Kurulum & çalıştırma

```bash
cd finansal-analist
./run.sh                      # venv kurar, bağımlılıkları yükler, sunucuyu açar
# tarayıcı: http://127.0.0.1:8000  → "Şimdi Tara" butonu
```

Sadece terminalde (web olmadan) çalıştırmak için:

```bash
source .venv/bin/activate
python -m backend.breadth --period 6mo
```

## Günlük otomasyon

Her akşam piyasa kapanışından sonra (örn. TSİ 23:30) otomatik taramak için cron:

```cron
30 23 * * 1-5  cd /Users/bozkarabekir/finansal-analist && .venv/bin/python -m backend.breadth >> breadth.log 2>&1
```
