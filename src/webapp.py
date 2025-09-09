# src/webapp.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from src.config import load_config, save_config
from src.logger import get_logger, log_info, log_error, log_success

import os, json

logger = get_logger()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# serve static (optional)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# session-like simple auth
SESSION = {"auth": False}


def get_pin():
    cfg = load_config()
    # pin stored at config["web"]["pin"] OR config["http"]["api_key"] fallback
    pin = cfg.get("web", {}).get("pin")
    if not pin:
        pin = cfg.get("http", {}).get("api_key") or cfg.get("web", {}).get("api_key")
    return str(pin) if pin else "1234"


def require_auth_redirect():
    # helper to use inside handlers — returns RedirectResponse if not authed else None
    if not SESSION.get("auth"):
        return RedirectResponse("/login", status_code=303)
    return None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # allow public view but require auth for config actions; if you want / to require auth, uncomment below
    r = require_auth_redirect()
    if r:
        return r
    cfg = load_config()
    return templates.TemplateResponse("index.html", {"request": request, "config": cfg})


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(pin: str = Form(...)):
    if str(pin) == get_pin():
        SESSION["auth"] = True
        log_info("User logged into web dashboard")
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/logout")
async def logout():
    SESSION["auth"] = False
    log_info("User logged out from web dashboard")
    return RedirectResponse("/login", status_code=303)


# Config Editor
@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = load_config()
    return templates.TemplateResponse("config.html", {"request": request, "config": cfg or {}})


@app.post("/config")
async def update_config(
    request: Request,
    # fields to edit — we'll only update if provided (partial update)
    sentinel_base_url: str = Form(None),
    sentinel_api_token: str = Form(None),
    wa_base_url: str = Form(None),
    wa_session_name: str = Form(None),
    polling_interval: int = Form(None),
    web_pin: str = Form(None)
):
    r = require_auth_redirect()
    if r:
        return r

    cfg = load_config()
    # ensure structure
    cfg.setdefault("sentinelone", {})
    cfg.setdefault("channels", {}).setdefault("whatsapp", {}).setdefault("bridge", {})
    cfg.setdefault("polling", {})
    cfg.setdefault("web", {})
    cfg.setdefault("http", {})

    if sentinel_base_url:
        cfg["sentinelone"]["base_url"] = sentinel_base_url.strip()
    if sentinel_api_token:
        cfg["sentinelone"]["api_token"] = sentinel_api_token.strip()

    if wa_base_url:
        cfg["channels"]["whatsapp"]["bridge"]["base_url"] = wa_base_url.strip()
    if wa_session_name:
        cfg["channels"]["whatsapp"]["bridge"]["session_name"] = wa_session_name.strip()

    if polling_interval:
        cfg["polling"]["interval_seconds"] = int(polling_interval)

    if web_pin:
        cfg["web"]["pin"] = str(web_pin).strip()

    save_config(cfg)
    log_info("Config updated via web")
    return RedirectResponse("/config", status_code=303)


# WhatsApp management page
@app.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = load_config()
    wa = cfg.get("channels", {}).get("whatsapp", {})
    return templates.TemplateResponse("whatsapp.html", {"request": request, "wa": wa})


@app.post("/whatsapp")
async def update_whatsapp(base_url: str = Form(None), session_name: str = Form(None)):
    r = require_auth_redirect()
    if r:
        return r
    cfg = load_config()
    cfg.setdefault("channels", {}).setdefault("whatsapp", {}).setdefault("bridge", {})
    if base_url:
        cfg["channels"]["whatsapp"]["bridge"]["base_url"] = base_url.strip()
    if session_name:
        cfg["channels"]["whatsapp"]["bridge"]["session_name"] = session_name.strip()
    save_config(cfg)
    log_info("WhatsApp config updated via web")
    return RedirectResponse("/whatsapp", status_code=303)


# endpoint to receive sentinelone webhook alert
@app.post("/send/alert")
async def receive_alert(request: Request):
    """
    SentinelOne will POST alerts here (webhook).
    We save raw JSON to storage/alerts/<date>/alert_<ts>.json
    and then trigger notifier(s) (telegram currently).
    """
    try:
        data = await request.json()
    except Exception as e:
        log_error(f"Invalid JSON payload for /send/alert: {e}")
        return {"status": "error", "message": "invalid json"}, 400

    # save raw alert
    try:
        now = __import__("datetime").datetime.utcnow()
        dirpath = os.path.join("storage", "alerts", now.strftime("%Y-%m-%d"))
        os.makedirs(dirpath, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(dirpath, f"alert_{ts}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_info(f"Saved incoming alert to {filepath}")
    except Exception as e:
        log_error(f"Failed saving alert: {e}")

    # send minimal notification via configured telegram (best-effort)
    try:
        from notifier.telegram import TelegramNotifier
        cfg = load_config()
        tg = cfg.get("channels", {}).get("telegram", {}) or {}
        token = tg.get("bot_token")
        chat_id = tg.get("chat_id")
        if token and chat_id:
            tn = TelegramNotifier(token=token, chat_id=chat_id)
            # craft short message
            threat = (data.get("threatInfo") or {}).get("threatName") or data.get("threat") or "N/A"
            agent = (data.get("agentRealtimeInfo") or {}).get("agentComputerName") or (data.get("agentDetectionInfo") or {}).get("agentComputerName") or "Unknown"
            msg = f"🚨 SentinelOne Alert\nAgent: {agent}\nThreat: {threat}\nSaved: {filepath}"
            tn.send(msg)
            log_success("Telegram alert sent")
    except Exception as e:
        log_error(f"Notifier error: {e}")

    return {"status": "ok", "file": filepath}
