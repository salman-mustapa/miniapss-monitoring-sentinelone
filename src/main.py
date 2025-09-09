# src/main.py
import uvicorn
from src.webapp import app
from src.logger import init_logging
from src.config import load_config

def start_app():
    # init logging early
    init_logging()

    cfg = load_config()
    cfg_web = cfg.get("web") or cfg.get("http") or {}
    host = cfg_web.get("host", "0.0.0.0")
    port = int(cfg_web.get("port", 5000))

    uvicorn.run(app, host=host, port=port)
