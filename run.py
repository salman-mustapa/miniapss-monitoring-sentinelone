# run.py
import argparse
from src.main import start_app
import setup_config
from src.config import load_config
from src.sentinel_api import SentinelAPI
from src.logger import log_info

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python Monitor (SentinelOne)")
    parser.add_argument("--setup", action="store_true", help="Run setup configuration")
    parser.add_argument("--web", action="store_true", help="Run web dashboard (http)")
    parser.add_argument("--polling", action="store_true", help="Run SentinelOne polling loop")
    parser.add_argument("--backup", action="store_true", help="Run backup (archive) loop")
    args = parser.parse_args()

    if args.setup:
        # call the setup wizard (interactive)
        if hasattr(setup_config, "run_setup"):
            setup_config.run_setup()
        else:
            print("setup not available (setup_config.run_setup missing).")
    elif args.web:
        # start web dashboard (reads config for host/port)
        start_app()
    elif args.polling:
        cfg = load_config()
        if not cfg:
            print("Config not found — run `python run.py --setup` first to create config/config.json")
        else:
            api = SentinelAPI(cfg)
            interval = cfg.get("polling", {}).get("interval_seconds", 60)
            api.start_polling(interval=interval)
    elif args.backup:
        print("Backup runner: currently run your own scheduler. See README for recommended cron/systemd timer.")
        # Could add a backup worker here if you want (simple loop); omitted for safety.
    else:
        print("Use --setup, --web, --polling, or --backup. Example: python run.py --web")
