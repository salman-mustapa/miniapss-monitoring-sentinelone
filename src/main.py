# src/main.py
import uvicorn
from src.webapp import app
from src.logger import init_logging
from src.config import load_config

def start_app():
    # init logging early
    init_logging()

    cfg = load_config()
    http_cfg = cfg.get("http") or cfg.get("web") or {}
    host = http_cfg.get("host", "0.0.0.0")
    port = int(http_cfg.get("port", 5000))

    uvicorn.run(app, host=host, port=port)
