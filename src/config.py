# src/config.py
import json
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "config.json"


def load_config() -> Dict[str, Any]:
    """
    Load config.json safely.
    If file doesn't exist, return empty dict (web will allow editing & saving).
    """
    try:
        if not CONFIG_PATH.exists():
            # no config yet — return empty dict and let caller decide to run setup
            print(f"[WARNING] config not found at {CONFIG_PATH}. Create it with `python run.py --setup` or via web /config.")
            return {}
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read config: {e}")
        return {}


def save_config(data: Dict[str, Any]) -> None:
    """
    Save config.json atomically (overwrite).
    """
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[SUCCESS] Config saved to {CONFIG_PATH}")
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        raise
