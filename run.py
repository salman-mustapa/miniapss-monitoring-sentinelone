# run.py
import argparse
from src.main import start_app
import setup_config  # we'll call setup_config.run_setup()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mini App SentinelOne Monitor")
    parser.add_argument("--setup", action="store_true", help="Run setup configuration")
    args = parser.parse_args()

    if args.setup:
        # setup_config.run_setup() will be provided in setup_config.py
        if hasattr(setup_config, "run_setup"):
            setup_config.run_setup()
        else:
            print("setup not available (setup_config.run_setup missing).")
    else:
        start_app()
