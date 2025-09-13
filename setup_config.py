#!/usr/bin/env python3
"""
setup_config.py
Setup konfigurasi untuk SentinelOne Monitor.
Jika config/config.json sudah ada → otomatis load sebagai default,
user bisa langsung tekan Enter untuk pakai nilai lama.
"""

import os, json, stat, requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

def prompt(text, default=None, hide=False):
    """Helper prompt with default value"""
    if default:
        text = f"{text} [{default}]: "
    else:
        text = f"{text}: "
    if hide:
        import getpass
        return getpass.getpass(text) or default
    return input(text) or default

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def save_config(cfg):
    ensure_dir(CONFIG_DIR)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    print(f"\n✅ Config disimpan ke {CONFIG_PATH}")

def load_existing():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def run_setup():
    print("=== SentinelOne Monitor - Setup Config ===")

    existing = load_existing()
    cfg = {}

    # --- SentinelOne
    print("\n-- SentinelOne --")
    s1 = existing.get("sentinelone", {})
    base_url = prompt("Base URL SentinelOne", s1.get("base_url", "https://"))
    api_token = prompt("API Token SentinelOne", s1.get("api_token", ""))
    webhook_secret = prompt("Webhook Secret", s1.get("webhook_secret", ""))

    # --- Polling
    print("\n-- Polling --")
    poll = existing.get("polling", {})
    interval = int(prompt("Polling interval (detik)", poll.get("interval_seconds", 60)))

    # --- PIN Web
    print("\n-- Web Security --")
    web_cfg = existing.get("web", {})
    pin_code = prompt("PIN untuk akses dashboard", web_cfg.get("pin", "1234"))

    # --- Notification Channels (Multi-channel support)
    print("\n-- Notification Channels --")
    
    # WhatsApp
    print("\n-- WhatsApp --")
    wa = existing.get("whatsapp", {})
    wa_base_url = prompt("WhatsApp Gateway Base URL", wa.get("base_url", "http://localhost:5013"))
    wa_session = prompt("WhatsApp Session Name", wa.get("session_name", "default"))
    
    # Telegram
    print("\n-- Telegram --")
    tg = existing.get("channels", {}).get("telegram", {})
    tg_bot_token = prompt("Telegram Bot Token", tg.get("bot_token", ""))
    
    # Teams
    print("\n-- Teams --")
    teams = existing.get("channels", {}).get("teams", {})
    teams_webhook = prompt("Teams Webhook URL", teams.get("webhook_url", ""))

    # --- Save config
    cfg = {
        "sentinelone": {"base_url": base_url, "api_token": api_token, "webhook_secret": webhook_secret, "site_ids": []},
        "polling": {"enabled": True, "interval_seconds": interval, "last_success_ts": None},
        "archive": {"path": "storage/events", "enabled": True},
        "whatsapp": {"base_url": wa_base_url, "session_name": wa_session},
        "channels": {
            "telegram": {"bot_token": tg_bot_token, "chats": [], "template": ""},
            "teams": {"webhooks": [teams_webhook] if teams_webhook else [], "template": ""},
            "whatsapp": {"session_name": wa_session, "recipients": [], "template": ""}
        },
        "web": {"host": web_cfg.get("host", "0.0.0.0"), "port": web_cfg.get("port", 8899), "api_key": web_cfg.get("api_key", "change-me"), "pin": pin_code}
    }

    save_config(cfg)
    print("✨ Setup selesai!")

if __name__ == "__main__":
    run_setup()