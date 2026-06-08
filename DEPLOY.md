# Yayına Alma (Deploy) + GoDaddy Domain Bağlama

Hedef: uygulamayı ücretsiz bir Python host'una (Render) koymak, sonra GoDaddy'deki
alan adını oraya yönlendirmek. Sonuç: `analiz.SENINDOMAININ.com` siteyi açar.

> **Neden GoDaddy'de çalışmıyor?** GoDaddy paylaşımlı hosting Python/FastAPI çalıştırmaz.
> Domain GoDaddy'de kalır; uygulama Render'da çalışır; DNS ile ikisini bağlarız. Standart yöntem.

---

## Adım 1 — Kodu GitHub'a koy

```bash
cd ~/finansal-analist
git init && git add -A && git commit -m "Finansal Analist v1"
# GitHub'da bos bir repo ac (orn: finansal-analist), sonra:
git remote add origin https://github.com/KULLANICI/finansal-analist.git
git branch -M main
git push -u origin main
```

## Adım 2 — Render'a deploy

1. https://render.com → ücretsiz hesap (GitHub ile giriş yapabilirsin).
2. **New → Web Service** → GitHub repo'nu seç.
3. Render `render.yaml` + `Dockerfile`'ı otomatik okur. Onayla.
4. **Environment** bölümünde `ADMIN_TOKEN` değişkenine güçlü bir parola gir
   (ör. `openssl rand -hex 16` çıktısı). Bu, `/api/refresh`'i korur.
5. **Create Web Service.** İlk derleme ~3-5 dk. Bitince URL verir:
   `https://finansal-analist.onrender.com` → çalıştığını gör.

> Ücretsiz katman 15 dk hareketsizlikte uyur; ilk ziyaretçide ~30 sn'de uyanır.
> Kesintisiz istersen Render'da **Starter (7$/ay)** planına geçersin.

## Adım 3 — techwawes.com'u Render'a bağla (GoDaddy DNS)

> **Durum:** techwawes.com GoDaddy'de yönetiliyor, şu an GitHub Pages IP'lerini
> (`185.199.108–111.153`) gösteriyor. Pages kapatıldı → bu eski kayıtları silip
> Render'a yönlendireceğiz.

1. **Render** → servisin → **Settings → Custom Domains → Add Custom Domain** →
   `techwawes.com` ekle (ve istersen `www.techwawes.com`). Render sana **tam değerleri**
   gösterir: apex için bir **A kaydı IP**'si, www için bir **CNAME** hedefi.

2. **GoDaddy** → **My Products → DNS (techwawes.com)** → şu **eski kayıtları SİL:**
   - 4 adet **A** kaydı: `@ → 185.199.108.153 / .109 / .110 / .111` (GitHub Pages)
   - **CNAME** `www → burakozkarabekir.github.io`

3. **Yeni kayıtları EKLE** (Render'ın gösterdiği değerlerle):
   | Type | Name | Value | TTL |
   |------|------|-------|-----|
   | A | `@` | *(Render'ın verdiği IP)* | 600 |
   | CNAME | `www` | *(Render'ın verdiği hedef, ör. techwawes.onrender.com)* | 600 |

4. Kaydet. Yayılma 10 dk – 1 saat. Render SSL'i otomatik kurar → `https://techwawes.com`.

> **Alternatif (daha kolay):** apex yerine sadece `analiz.techwawes.com` kullan →
> tek **CNAME** `analiz → techwawes.onrender.com` yeter, A kayıtlarıyla uğraşmazsın.
> Ama techwawes.com kökünü istiyorsan yukarıdaki adımlar.

### Eski siteyi geri istersen
Eski TechWawes sitesi `eski-techwawes-yedek` dalında duruyor:
`git checkout eski-techwawes-yedek` veya GitHub'da o dala bak.

---

## Güncelleme nasıl çalışıyor?

- **Otomatik:** uygulama açılışta veriyi ısıtır; her gün 22:30 UTC breadth, 6 saatte bir
  sektörleri tazeler (kod içi zamanlayıcı). Ziyaretçi tarama tetikleyemez.
- **Manuel (admin):** `curl -X POST -H "X-Admin-Token: SENIN_TOKEN" https://.../api/refresh`
- **Kod güncelleme:** GitHub'a `git push` → Render otomatik yeniden deploy eder.

## Maliyet özeti

| Kalem | Ücret |
|-------|-------|
| Render Free | 0 (uyur/uyanır) |
| Render Starter (kesintisiz) | ~7 $/ay |
| GoDaddy domain | zaten var |
| Veri (yfinance) | ücretsiz |
