"""
Finansal Analist - web sunucusu (FastAPI). Public-ready.

Genel (herkese acik, salt-okunur):
  GET /                   -> dashboard (HTML)
  GET /api/breadth        -> kayitli piyasa gucu gecmisi (DB'den)
  GET /api/sectors        -> sektor siralamasi (30 dk cache)
  GET /api/company/{sym}  -> sirket analizi (sembol basina 30 dk cache)
  GET /api/status         -> son guncelleme zamani / saglik

Korumali (sadece ADMIN_TOKEN ile, X-Admin-Token header):
  POST /api/refresh       -> S&P 500'u yeniden tara, DB'yi guncelle

Veri otomatik yenilenir: baslangicta isitilir + zamanlayici gunluk breadth /
saatlik sektor tazeler. Ziyaretci canli tarama tetikleyemez (rate-limit korumasi).

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

from . import breadth, company, sectors

ROOT = Path(__file__).parent.parent
FRONTEND = ROOT / "frontend" / "dashboard.html"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

_STATE = {"last_breadth_refresh": None, "last_sectors_refresh": None, "warming": False}
_scheduler = BackgroundScheduler(timezone="UTC")


# ----------------------------------------------------------------------------- veri yenileme
def _refresh_breadth() -> None:
    try:
        breadth.run(period="3mo")
        _STATE["last_breadth_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print("[zamanlayici] breadth yenilendi.")
    except Exception as exc:  # noqa: BLE001
        print(f"[zamanlayici] breadth hatasi: {exc}")


def _refresh_sectors() -> None:
    try:
        sectors._CACHE["data"] = None  # cache'i bayatlat, yeniden hesapla
        sectors.rank_sectors()
        _STATE["last_sectors_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print("[zamanlayici] sektorler yenilendi.")
    except Exception as exc:  # noqa: BLE001
        print(f"[zamanlayici] sektor hatasi: {exc}")


def _warm() -> None:
    """Baslangicta veriyi arka planda isitir. Breadth bos/bayatsa yeniden hesaplar."""
    _STATE["warming"] = True
    try:
        history = breadth.load_history()
        today = datetime.now(timezone.utc).date().isoformat()
        if not history or history[-1]["date"] < today:
            _refresh_breadth()
        else:
            _STATE["last_breadth_refresh"] = "DB'den (guncel)"
        _refresh_sectors()
    finally:
        _STATE["warming"] = False


# ----------------------------------------------------------------------------- yasam dongusu
@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm, daemon=True).start()
    # Gunluk breadth (ABD kapanis ~20:00 UTC, 22:30'da guvenli), 6 saatte bir sektor
    _scheduler.add_job(_refresh_breadth, "cron", hour=22, minute=30, id="breadth")
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


@app.get("/api/status")
def api_status():
    history = breadth.load_history()
    return JSONResponse({
        "ok": True,
        "warming": _STATE["warming"],
        "breadth_days": len(history),
        "last_breadth_date": history[-1]["date"] if history else None,
        "last_breadth_refresh": _STATE["last_breadth_refresh"],
        "last_sectors_refresh": _STATE["last_sectors_refresh"],
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


@app.get("/api/breadth")
def api_breadth():
    history = breadth.load_history()
    latest = history[-1] if history else None
    yorum = breadth.signal(latest["ratio_5d"]) if latest else "Veri hazirlaniyor…"
    return JSONResponse({"history": history, "latest": latest, "yorum": yorum})


@app.get("/api/sectors")
def api_sectors():
    try:
        return JSONResponse({"ok": True, "sectors": sectors.rank_sectors()})
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


# ----------------------------------------------------------------------------- korumali uc
@app.post("/api/refresh")
def api_refresh(request: Request, period: str = "3mo", x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        return JSONResponse({"ok": False, "error": "yetkisiz (X-Admin-Token gerekli)"}, status_code=401)
    try:
        summary = breadth.run(period=period)
        _STATE["last_breadth_refresh"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return JSONResponse({"ok": True, "summary": summary})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
