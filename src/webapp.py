# src/webapp.py
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import requests, os, json, mimetypes
from datetime import datetime

from src.config import load_config, save_config
from src.logger import get_logger, log_info, log_error, log_success

logger = get_logger()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# mount static if exists (css/js)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# small helper: require auth (session kept simple in memory)
SESSION = {"auth": False}
def get_pin():
    try:
        cfg = load_config()
    except Exception:
        return "tOOr12345*"
    pin = cfg.get("web", {}).get("pin") or cfg.get("http", {}).get("api_key")
    return str(pin) if pin else "tOOr12345*"

def require_auth_redirect():
    if not SESSION.get("auth"):
        return RedirectResponse("/login", status_code=303)
    return None

# Utility: safe load config
def safe_load_cfg():
    try:
        return load_config()
    except Exception as e:
        logger.error(f"Config load error: {e}")
        # return minimal default skeleton to avoid crashes
        return {
            "channels": {"whatsapp": {"bridge": {"base_url": "", "session_name": "default"}}},
            "sentinelone": {},
            "polling": {"interval_seconds": 60},
            "web": {"pin": ""},
        }

# ---------------- UI routes ----------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    # quick summary for dashboard
    channels = cfg.get("channels", {})
    polling = cfg.get("polling", {})
    return templates.TemplateResponse("index.html", {"request": request, "config": cfg, "channels": channels, "polling": polling})

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(pin: str = Form(...)):
    if str(pin) == get_pin():
        SESSION["auth"] = True
        log_info("User logged in via web UI")
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login", status_code=303)

@app.get("/logout")
async def logout():
    SESSION["auth"] = False
    log_info("User logged out")
    return RedirectResponse("/login", status_code=303)

# ------------- config page (all channels) -------------
@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    return templates.TemplateResponse("config.html", {"request": request, "config": cfg})

@app.post("/config")
async def update_config(
    sentinel_base_url: Optional[str] = Form(None),
    sentinel_api_token: Optional[str] = Form(None),
    telegram_enabled: Optional[str] = Form(None),
    telegram_token: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    teams_enabled: Optional[str] = Form(None),
    teams_webhook: Optional[str] = Form(None),
    wa_enabled: Optional[str] = Form(None),
    wa_base_url: Optional[str] = Form(None),
    wa_session_name: Optional[str] = Form(None),
    polling_interval: Optional[int] = Form(None),
    web_pin: Optional[str] = Form(None)
):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    cfg.setdefault("sentinelone", {})
    cfg.setdefault("channels", {})
    cfg.setdefault("polling", {})
    cfg.setdefault("web", {})

    if sentinel_base_url:
        cfg["sentinelone"]["base_url"] = sentinel_base_url.strip()
    if sentinel_api_token:
        cfg["sentinelone"]["api_token"] = sentinel_api_token.strip()

    # Telegram
    cfg["channels"].setdefault("telegram", {})
    cfg["channels"]["telegram"]["enabled"] = bool(telegram_enabled)
    if telegram_token:
        cfg["channels"]["telegram"]["bot_token"] = telegram_token.strip()
    if telegram_chat_id:
        cfg["channels"]["telegram"]["chat_id"] = telegram_chat_id.strip()

    # Teams
    cfg["channels"].setdefault("teams", {})
    cfg["channels"]["teams"]["enabled"] = bool(teams_enabled)
    if teams_webhook:
        cfg["channels"]["teams"]["webhook_url"] = teams_webhook.strip()

    # WhatsApp bridge
    cfg["channels"].setdefault("whatsapp", {}).setdefault("bridge", {})
    cfg["channels"]["whatsapp"]["enabled"] = bool(wa_enabled)
    if wa_base_url:
        cfg["channels"]["whatsapp"]["bridge"]["base_url"] = wa_base_url.strip()
    if wa_session_name:
        cfg["channels"]["whatsapp"]["bridge"]["session_name"] = wa_session_name.strip()

    if polling_interval:
        try:
            cfg["polling"]["interval_seconds"] = int(polling_interval)
        except Exception:
            pass

    if web_pin:
        cfg["web"]["pin"] = str(web_pin).strip()

    save_config(cfg)
    log_info("Config updated via web")
    return RedirectResponse("/config", status_code=303)

# ------------- WhatsApp proxy helpers -------------
def wa_call(path: str, method: str = "GET", data: dict = None):
    """
    Call external WA-gateway base_url from config.
    path should include leading slash, e.g. '/sessions' or '/kirim-pesan'
    """
    cfg = safe_load_cfg()
    wa_cfg = cfg.get("channels", {}).get("whatsapp", {}).get("bridge", {})
    base = wa_cfg.get("base_url") or ""
    if not base:
        return {"success": False, "error": "WhatsApp base_url not configured"}
    url = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
    try:
        if method.upper() == "GET":
            r = requests.get(url, timeout=15)
        else:
            r = requests.post(url, json=data or {}, timeout=30)
        try:
            return r.json()
        except Exception:
            return {"success": False, "status": r.status_code, "text": r.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ------------- WhatsApp UI & API proxy endpoints -------------
@app.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    wa_conf = cfg.get("channels", {}).get("whatsapp", {}).get("bridge", {})
    return templates.TemplateResponse("whatsapp.html", {"request": request, "wa": wa_conf or {}})

@app.get("/api/whatsapp/sessions")
async def list_sessions():
    r = require_auth_redirect()
    if r:
        return r
    return JSONResponse(wa_call("/sessions"))

@app.post("/api/whatsapp/connect")
async def connect_session(session: str = Form(...)):
    r = require_auth_redirect()
    if r:
        return r
    return JSONResponse(wa_call("/connect", method="POST", data={"session": session}))

@app.get("/api/whatsapp/qr")
async def get_qr(session: Optional[str] = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    # pass session as query if provided
    url = "/qr"
    if session:
        url = f"/qr?session={session}"
    return JSONResponse(wa_call(url))

@app.get("/api/whatsapp/groups")
async def list_groups(session: Optional[str] = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    url = "/groups"
    if session:
        url = f"/groups?session={session}"
    return JSONResponse(wa_call(url))

@app.get("/api/whatsapp/fetch-groups")
async def fetch_groups(session: Optional[str] = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    url = "/fetch-groups"
    if session:
        url = f"/fetch-groups?session={session}"
    return JSONResponse(wa_call(url))

@app.post("/api/whatsapp/send")
async def send_message(number: str = Form(...), message: str = Form(...), session: Optional[str] = Form(None)):
    r = require_auth_redirect()
    if r:
        return r
    payload = {"number": number, "message": message}
    if session:
        payload["session"] = session
    return JSONResponse(wa_call("/kirim-pesan", method="POST", data=payload))

@app.get("/api/whatsapp/logs")
async def wa_logs():
    r = require_auth_redirect()
    if r:
        return r
    return JSONResponse(wa_call("/logs"))

# ------------- backups & logs viewer -------------
@app.get("/backups")
async def list_backups():
    r = require_auth_redirect()
    if r:
        return r
    files = []
    base = os.path.join("storage", "events")
    if os.path.isdir(base):
        for root, _, filenames in os.walk(base):
            for fn in filenames:
                if fn.startswith("."):
                    continue
                full = os.path.join(root, fn)
                mtime = os.path.getmtime(full)
                files.append({"path": full, "name": os.path.relpath(full, start="storage"), "mtime": mtime})
    files = sorted(files, key=lambda x: x["mtime"], reverse=True)
    return JSONResponse({"success": True, "files": files})

@app.get("/backups/download")
async def download_backup(path: str = Query(...)):
    r = require_auth_redirect()
    if r:
        return r
    safe_root = os.path.abspath("storage")
    requested = os.path.abspath(path)
    if not requested.startswith(safe_root):
        return JSONResponse({"success": False, "error": "invalid path"}, status_code=400)
    if not os.path.exists(requested):
        return JSONResponse({"success": False, "error": "file not found"}, status_code=404)
    mime, _ = mimetypes.guess_type(requested)
    return FileResponse(requested, media_type=mime or "application/octet-stream", filename=os.path.basename(requested))

@app.get("/logs")
async def list_logs():
    r = require_auth_redirect()
    if r:
        return r
    log_dir = "logs"
    files = []
    if os.path.isdir(log_dir):
        for fn in sorted(os.listdir(log_dir), reverse=True):
            full = os.path.join(log_dir, fn)
            if os.path.isfile(full):
                files.append({"name": fn, "path": full, "size": os.path.getsize(full)})
    return JSONResponse({"success": True, "files": files})

@app.get("/logs/download")
async def download_log(path: str = Query(...)):
    r = require_auth_redirect()
    if r:
        return r
    safe_root = os.path.abspath("logs")
    requested = os.path.abspath(path)
    if not requested.startswith(safe_root):
        return JSONResponse({"success": False, "error": "invalid path"}, status_code=400)
    if not os.path.exists(requested):
        return JSONResponse({"success": False, "error": "file not found"}, status_code=404)
    mime, _ = mimetypes.guess_type(requested)
    return FileResponse(requested, media_type=mime or "text/plain", filename=os.path.basename(requested))

# ------------- sentinel alert receiver -------------
@app.post("/send/alert")
async def receive_alert(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        log_error(f"Invalid JSON payload for /send/alert: {e}")
        return JSONResponse({"status": "error", "message": "invalid json"}, status_code=400)

    # save raw alert
    try:
        now = datetime.utcnow()
        dirpath = os.path.join("storage", "alerts", now.strftime("%Y-%m-%d"))
        os.makedirs(dirpath, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(dirpath, f"alert_{ts}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_info(f"Saved incoming alert to {filepath}")
    except Exception as e:
        log_error(f"Failed saving alert: {e}")

    # dispatch notifier (best-effort)
    try:
        cfg = safe_load_cfg()
        threat = (data.get("threatInfo") or {}).get("threatName") or data.get("threat") or "N/A"
        agent = (data.get("agentRealtimeInfo") or {}).get("agentComputerName") or (data.get("agentDetectionInfo") or {}).get("agentComputerName") or "Unknown"
        summary = f"🚨 SentinelOne Alert\nAgent: {agent}\nThreat: {threat}\nFile: {filepath}"

        # Telegram
        tg = cfg.get("channels", {}).get("telegram", {})
        if tg.get("enabled") and tg.get("bot_token") and tg.get("chat_id"):
            from notifier.telegram import TelegramNotifier
            tn = TelegramNotifier(token=tg.get("bot_token"), chat_id=tg.get("chat_id"))
            tn.send(summary)

        # Teams
        teams = cfg.get("channels", {}).get("teams", {})
        if teams.get("enabled") and teams.get("webhook_url"):
            from notifier.teams import TeamsNotifier
            tn2 = TeamsNotifier(teams.get("webhook_url"))
            tn2.send(summary)

        # WhatsApp via bridge
        wa = cfg.get("channels", {}).get("whatsapp", {})
        if wa.get("enabled"):
            wa_bridge = wa.get("bridge", {})
            wa_base = wa_bridge.get("base_url")
            wa_session = wa_bridge.get("session_name")
            notify_to = wa.get("notify_number")
            if wa_base and wa_session and notify_to:
                # use WA Bridge proxy
                wa_call("/kirim-pesan", method="POST", data={"number": notify_to, "message": summary, "session": wa_session})
        log_success("Alert notification dispatched (best-effort)")
    except Exception as e:
        log_error(f"Notifier dispatch error: {e}")

    return JSONResponse({"status": "ok", "file": filepath})
