# src/webapp.py
from fastapi import FastAPI, Request
from datetime import datetime
import os, json

from src.logger import get_logger, log_info, log_error, log_success
from notifier.telegram import TelegramNotifier
from src.config import load_config

logger = get_logger()

def create_app():
    app = FastAPI()
    # load config (must exist)
    cfg = load_config()

    # support both config styles:
    # 1) top-level bot_token/chat_id (older example)
    # 2) channels.telegram.bot_token / chat_id (setup_config.py style)
    tg_conf = cfg.get("channels", {}).get("telegram", {}) or {
        "bot_token": cfg.get("bot_token"),
        "chat_id": cfg.get("chat_id")
    }

    telegram_notifier = TelegramNotifier(
        token=tg_conf.get("bot_token"),
        chat_id=tg_conf.get("chat_id")
    )

    @app.post("/send/alert")
    async def send_alert(request: Request):
        try:
            data = await request.json()

            # save raw alert to storage/alerts/<YYYY-MM-DD>/alert_<ts>.json
            dirpath = os.path.join("storage", "alerts", datetime.utcnow().strftime("%Y-%m-%d"))
            os.makedirs(dirpath, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(dirpath, f"alert_{ts}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log_info(f"Alert saved to {filepath}")

            # build simple message (safe for many payloads)
            threat_name = (data.get("threatInfo") or {}).get("threatName") or data.get("threat") or "N/A"
            agent_name = (data.get("agentRealtimeInfo") or {}).get("agentComputerName") or (data.get("agentDetectionInfo") or {}).get("agentComputerName") or "Unknown"
            message = f"🚨 <b>SentinelOne Alert</b>\nAgent: {agent_name}\nThreat: {threat_name}\nSaved: {filepath}"

            sent = telegram_notifier.send(message)
            if sent:
                log_success(f"Alert notification sent for file {filepath}")
                return {"status": "ok", "file": filepath}
            else:
                log_error("Failed to send alert notification")
                return {"status": "error", "message": "Failed to send notification"}, 500

        except Exception as e:
            logger.exception("Exception in /send/alert")
            return {"status": "error", "message": str(e)}

    return app
