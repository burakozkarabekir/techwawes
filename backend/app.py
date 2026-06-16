"""
Finansal Analist - web sunucusu (FastAPI). Public-ready.

Cok piyasali: ABD (S&P 500) ve BIST (Borsa Istanbul). Endpoint'ler ?market=us|bist
parametresi alir (varsayilan us).

Genel (herkese acik, salt-okunur):
  GET /                        -> dashboard (HTML)
  GET /api/markets             -> mevcut piyasalar (frontend secici)
  GET /api/breadth?market=     -> kayitli piyasa gucu gecmisi (DB'den)
  GET /api/sectors?market=     -> sektor siralamasi (piyasa basina 30 dk cache)
  GET /api/company/{sym}       -> sirket analizi (BIST sembolu ciplak yazilabilir)
  GET /api/status              -> piyasa basina son guncelleme / saglik

Korumali (sadece ADMIN_TOKEN ile, X-Admin-Token header):
  POST /api/refresh?market=    -> ilgili piyasayi yeniden tara, DB'yi guncelle

Veri otomatik yenilenir: baslangicta her piyasa isitilir + zamanlayici her piyasayi
kendi kapanis saatinde, sektorleri 6 saatte bir tazeler. Ziyaretci canli tarama
tetikleyemez (rate-limit korumasi).

Calistir (lokal):  uvicorn backend.app:app --port 8000
Calistir (host):   uvicorn backend.app:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import breadth, company, events, fundamentals, markets, news, rs, scanner, sectors

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend" / "dashboard.html"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

_STATE = {"last_breadth_refresh": None, "last_sectors_refresh": None, "warming": False}
_scheduler = BackgroundScheduler(timezone="UTC")


# ----------------------------------------------------------------------------- veri yenileme
def _refresh_breadth(market: str) -> None:
    try:
        breadth.run(period="3mo", market=market)
        _STATE["last_breadth_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"[zamanlayici] breadth yenilendi ({market}).")
    except Exception as exc:  # noqa: BLE001
        print(f"[zamanlayici] breadth hatasi ({market}): {exc}")


def _refresh_sectors() -> None:
    for market in markets.MARKETS:
        try:
            sectors.invalidate(market)  # cache'i bayatlat, yeniden hesapla
            sectors.rank_sectors(market=market)
            print(f"[zamanlayici] sektorler yenilendi ({market}).")
        except Exception as exc:  # noqa: BLE001
            print(f"[zamanlayici] sektor hatasi ({market}): {exc}")
    _STATE["last_sectors_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _warm() -> None:
    """Baslangicta veriyi arka planda isitir. Breadth bos/bayatsa yeniden hesaplar."""
    _STATE["warming"] = True
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        for market in markets.MARKETS:
            history = breadth.load_history(market=market)
            if not history or history[-1]["date"] < today:
                _refresh_breadth(market)
            else:
                _STATE["last_breadth_refresh"] = "DB'den (guncel)"
        _refresh_sectors()
    finally:
        _STATE["warming"] = False


# ----------------------------------------------------------------------------- yasam dongusu
@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm, daemon=True).start()
    # Her piyasa kendi kapanis saatinde breadth tarar; sektorler 6 saatte bir.
    for mkt, meta in markets.MARKETS.items():
        cron = meta["breadth_cron"]
        _scheduler.add_job(
            _refresh_breadth, "cron", args=[mkt],
            hour=cron["hour"], minute=cron["minute"], id=f"breadth-{mkt}",
        )
    _scheduler.add_job(_refresh_sectors, "interval", hours=6, id="sectors")
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="Finansal Analist", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ----------------------------------------------------------------------------- genel uclar
@app.get("/")
def dashboard():
    return FileResponse(FRONTEND)


@app.get("/api/markets")
def api_markets():
    """Mevcut piyasalar (frontend secici icin)."""
    return JSONResponse({
        "default": markets.DEFAULT_MARKET,
        "markets": [
            {"id": mid, "label": m["label"], "evren": m["evren_label"],
             "currency": m["currency"], "ornek": m["ornek"]}
            for mid, m in markets.MARKETS.items()
        ],
    })


@app.get("/api/status")
def api_status():
    out = {}
    for mkt in markets.MARKETS:
        history = breadth.load_history(market=mkt)
        out[mkt] = {
            "breadth_days": len(history),
            "last_breadth_date": history[-1]["date"] if history else None,
        }
    return JSONResponse({
        "ok": True,
        "warming": _STATE["warming"],
        "markets": out,
        "last_breadth_refresh": _STATE["last_breadth_refresh"],
        "last_sectors_refresh": _STATE["last_sectors_refresh"],
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


@app.get("/api/breadth")
def api_breadth(market: str = "us"):
    market = markets.normalize_market(market)
    history = breadth.load_history(market=market)
    latest = history[-1] if history else None
    yorum = breadth.signal(latest["ratio_5d"]) if latest else "Veri hazirlaniyor…"
    return JSONResponse({"market": market, "history": history, "latest": latest, "yorum": yorum})


@app.get("/api/sectors")
def api_sectors(market: str = "us"):
    market = markets.normalize_market(market)
    try:
        return JSONResponse({"ok": True, "market": market, "sectors": sectors.rank_sectors(market=market)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/company/{symbol}")
def api_company(symbol: str):
    try:
        result = company.analyze_cached(symbol)
        code = 200 if result.get("ok") else 404
        return JSONResponse(result, status_code=code)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc), "symbol": symbol}, status_code=500)


@app.get("/api/health/{symbol}")
def api_health(symbol: str, quarterly: bool = False):
    """Asama 2 - Temel Saglik Skoru (8 kriter + kirmizi bayrak)."""
    try:
        cfg = {"use_quarterly": True} if quarterly else None
        result = fundamentals.analyze_health(symbol, cfg)
        code = 200 if result.get("ok") else 404
        return JSONResponse(result, status_code=code)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc), "symbol": symbol}, status_code=500)


@app.get("/api/news/{symbol}")
def api_news(symbol: str):
    """Asama 3 - tekillesti rilmis, tarihe gore sirali haber akisi."""
    try:
        return JSONResponse({"ok": True, "symbol": symbol, "news": news.feed(symbol)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc), "symbol": symbol}, status_code=500)


@app.get("/api/scan")
def api_scan(market: str = "us"):
    """Asama 4 - birikim + golden/death cross taramasi (piyasa basina 30 dk cache)."""
    market = markets.normalize_market(market)
    try:
        return JSONResponse({"ok": True, **scanner.scan(market=market)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/rs")
def api_rs(market: str = "us"):
    """Asama 6 - RS Rating tablosu (1-99 yuzdelik)."""
    market = markets.normalize_market(market)
    try:
        return JSONResponse({"ok": True, **rs.rs_table(market=market)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/rs/topdown")
def api_topdown(market: str = "us"):
    """Asama 6 - top-down guc tarayici (en guclu sektor -> en guclu hisse)."""
    market = markets.normalize_market(market)
    try:
        return JSONResponse({"ok": True, **rs.top_down(market=market)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/ratio/{symbol}")
def api_ratio(symbol: str, market: str = "us", benchmark: str = ""):
    """Asama 6 - oran grafigi (hisse / benchmark)."""
    market = markets.normalize_market(market)
    try:
        result = rs.ratio_chart(symbol, benchmark or None, market=market)
        return JSONResponse(result, status_code=200 if result.get("ok") else 404)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc), "symbol": symbol}, status_code=500)


@app.get("/api/compare")
def api_compare(symbols: str = ""):
    """Asama 6 - 2+ hisseyi temel + teknik metriklerle yan yana getirir."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()][:6]
    if len(syms) < 2:
        return JSONResponse({"ok": False, "error": "en az 2 sembol verin (virgulle)"}, status_code=400)
    rows = []
    for s in syms:
        a = company.analyze_cached(s)
        if not a.get("ok"):
            rows.append({"symbol": s, "ok": False, "error": a.get("error")})
            continue
        t, f = a.get("teknik", {}), a.get("temel", {})
        rows.append({
            "ok": True, "symbol": a["symbol"], "name": a.get("name"),
            "stance": a.get("stance"), "score": a.get("score"),
            "price": t.get("price"), "rsi": t.get("rsi"), "mom_3m": t.get("mom_3m"),
            "pos_52w": t.get("pos_52w"), "pe": f.get("trailing_pe"), "peg": f.get("peg"),
            "pb": f.get("pb"), "roe": f.get("roe"), "margin": f.get("profit_margin"),
            "target_upside": f.get("target_upside"), "currency": f.get("currency"),
        })
    return JSONResponse({"ok": True, "rows": rows})


@app.get("/api/chart/{symbol}")
def api_chart(symbol: str, period: str = "1y"):
    """Asama 5 - fiyat serisi + iceriden islem / geri alim isaretleri."""
    try:
        result = events.chart(symbol, period=period)
        return JSONResponse(result, status_code=200 if result.get("ok") else 404)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc), "symbol": symbol}, status_code=500)


# ----------------------------------------------------------------------------- korumali uc
@app.post("/api/refresh")
def api_refresh(request: Request, period: str = "3mo", market: str = "us", x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        return JSONResponse({"ok": False, "error": "yetkisiz (X-Admin-Token gerekli)"}, status_code=401)
    market = markets.normalize_market(market)
    try:
        summary = breadth.run(period=period, market=market)
        _STATE["last_breadth_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return JSONResponse({"ok": True, "summary": summary})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
