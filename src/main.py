import uvicorn
from src.webapp import create_app
from src.logger import init_logging
from src.config import load_config

def start_app():
    #Load config
    config = load_config()

    #inisialisasi logging
    init_logging()

    # start webapp (http server)
    app = create_app()

    uvicorn.run(app, host="0.0.0.0", port=config.get("port", 8000))