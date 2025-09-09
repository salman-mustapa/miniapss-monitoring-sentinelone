#!/usr/bin/env python3
# setup_config.py
"""setup_config.py
Proses sederhana untuk membuat config/config.json berdasarkan inputan user.
Test koneksi akan langsung di tampilkan (by Telegram/Team, Or other).
"""

import os
import json
import stat
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))    
CONFIG_DIR = os.path.join(BASE_DIR, 'config')        
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')    

def prompt(prompt_text, default=None, hide=False):
    if default:
        prompt_text = f"{prompt_text} [{default}]: "
    else:
        prompt_text = f"{prompt_text}: "
    if hide:
        import getpass
        return getpass.getpass(prompt_text) or default
    return input(prompt_text) or default

def connect_telegram(bot_token, chat_id):
    if not bot_token or not chat_id:
        return False, 'missing token or chat_id'
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": "SentinelOne Monitor setup test message from salman"},  timeout=10)
        if r.status_code == 200:
            return True, 'connection success'
        return False, f'status {r.status_code} -  {r.text}'
    except Exception as e:
        return False, str(e)

def connect_teams(webhook_url):
    if not webhook_url:
        return False, 'missing webhook_url'
    try:
        r = requests.post(webhook_url, json={"text": "SentinelOne Monitor setup message from salman"}, timeout=10)
        if r.status_code in (200, 201, 202):
            return True, 'connection success'
        return False, f'status {r.status_code} - {r.text}'
    except Exception as e:
        return False, str(e)

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def save_config(cfg):
    ensure_dir(CONFIG_DIR)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    print('\nConfig berhasil disimpan ke: ', CONFIG_PATH)

# 👇 ini fungsi baru, isinya refactor dari __main__
def run_setup():
    print('=== MiniApps SentinelOne Monitoring - Setup Config ===')
    
    cfg = {}

    print('\n-- Config SentinelOne --')
    base_url = prompt('SentinelOne Base URL (example: https://apne1-1101-nfr.sentinelone.net', 'https://')
    api_token = prompt('SentinelOne API TOKEN (untuk simpan data ke local)', hide=False)
    webhook_secret = prompt('Webhook shared secret (for verifiying webhook signature)', '')

    print('\n-- Polling --')
    interval = int(prompt('Polling interval in seconds', '60'))

    print('\n-- Channels (Telegram) --')
    use_telegram = prompt('Enable Telegram? (y/n)', 'n')
    telegram_cfg = {"enabled": False, "bot_token": "", "chat_id": ""}
    if use_telegram.lower().startswith('y'):
        telegram_cfg['enabled'] = True
        telegram_cfg['bot_token'] = prompt('Telegram bot token', hide=True)
        telegram_cfg['chat_id'] = prompt('Telegram chat id (group or user)')
        ok, msg = connect_telegram(telegram_cfg['bot_token'], telegram_cfg['chat_id'])
        print('Telegram test →', ok, msg)

    print('\n-- Channels (Teams) --')
    use_teams = prompt('Enable Teams? (y/n)', 'n')
    teams_cfg = {"enabled": False, "webhook_url":""}
    if use_teams.lower().startswith('y'):
        teams_cfg['enabled'] = True
        teams_cfg['webhook_url'] = prompt('Teams incoming webhook URL')
        ok, msg = connect_teams(teams_cfg['webhook_url'])
        print('Teams test →', ok, msg)

    print('\n-- Whatsapp (bridge) --')
    use_wa = prompt('Kamu ingin menggunakan local whatsapp? (y/n)', 'n')
    wa_cfg = {"enabled": False, "driver": "bridge", "bridge": {"base_url":"http://localhost:3001", "session_name": "default"}}
    if use_wa.lower().startswith('y'):
        wa_cfg['enabled'] = True
        wa_cfg['bridge']['base_url'] = prompt('Wa bridge base URL', wa_cfg['bridge']['base_url'])
        wa_cfg['bridge']['session_name'] = prompt('Wa bridge session_name', wa_cfg['bridge']['session_name'])
        print('Note: Wa bridge test will be done in later steps')
    
    print('\n-- Web Dashboard --')
    web_cfg = {
        "host": prompt("Web server host", "https://wa-gateway.salmanmustapa.my.id"),
        "port": int(prompt("Web server port", "80")),
        "api_key": prompt("Web API key", "change-me-local-key")
    }

    print('\n-- AI (Optional) --')
    use_ai = prompt('Enable AI (OpenAI) for summary & mitigation (y/n)? ','n')
    ai_cfg = {"enabled": False, "provider": "openai", "openai_api_key": "", "model": "gpt-4o-mini", "sanitize_before_ai": True}
    if use_ai.lower().startswith('y'):
        ai_cfg['enabled'] = True
        ai_cfg['open_api_key'] = prompt('OpenAI Api key (will be stored locally)', hide=True)
        ai_cfg['model'] = prompt('OpenI model', ai_cfg['model'])

    http_cfg = {"host": "127.0.0.1", "port": 5000, "api_key": prompt('HTTP APi key for dashboard (change this!)', 'change-me-local-key')}

    cfg = {
        "sentinelone": {"base_url": base_url, "api_token": api_token, "webhook_secret": webhook_secret, "site_ids": []},
        "polling": {"enabled": True, "interval_seconds": interval, "last_success_ts": None},
        "archive": {"path": "storage/events", "enabled": True},
        "routing": {"severity_to_channels": {"CRITICAL": ["telegram", "whatsapp", "teams"], "HIGH": ["telegram", "whatsapp", "teams"], "MEDIUM": ["telegram"], "LOW": []}},
        "channels": {"telegram": telegram_cfg, "teams": teams_cfg, "whatsapp": wa_cfg},
        "web": web_cfg,
        "ai": ai_cfg,
        "http": http_cfg
    }

    save_config(cfg)
    
    print('\n*** IMPORTANT ***')
    print(' - config/config.json is in .gitignore. Do not commit it.')
    print(' - Keep your API keys and tokens secure. jika ingin share, pertimbangkan encrypt file anda')

if __name__ == '__main__':
    run_setup()
