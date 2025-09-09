# src/sentinel_api.py
import requests
import json
import os
import time
from datetime import datetime
from src.logger import log_info, log_error, log_debug, log_success
from src.config import load_config
from src.backup import append_events

class SentinelAPI:
    def __init__(self, config: dict):
        self.config = config or load_config()
        self.base_url = self.config.get("sentinelone", {}).get("base_url")
        self.api_token = self.config.get("sentinelone", {}).get("api_token")
        self.event_dir = os.path.join("storage", "events")

        if not os.path.exists(self.event_dir):
            os.makedirs(self.event_dir, exist_ok=True)
            log_debug(f"Event directory created: {self.event_dir}")

        if not self.base_url or not self.api_token:
            log_error("Base URL atau API Token SentinelOne belum dikonfigurasi.")
            raise ValueError("Config SentinelOne tidak lengkap.")

        testing_api = f"{self.base_url}/web/api/v2.1/agents"
        headers = self._headers()
        try:
            response = requests.get(testing_api, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                total_agents = data.get("pagination", {}).get("totalItems", 0)
                log_success(f"SentinelOne API terkoneksi. Agents ditemukan: {total_agents}")
            else:
                log_error(f"Gagal koneksi ke SentinelOne. Status: {response.status_code} | {response.text}")
                raise ConnectionError(f"Gagal koneksi ke SentinelOne. Status: {response.status_code}")
        except Exception as e:
            log_error(f"Exception saat koneksi SentinelOne: {str(e)}")
            raise ConnectionError(f"Exception saat koneksi SentinelOne: {str(e)}")

    def _headers(self):
        return {
            "Authorization": f"ApiToken {self.api_token}",
            "Content-Type": "application/json"
        }

    def _store_data(self, data_type, data):
        """Simpan raw json ke folder storage/events"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{data_type}_{timestamp}.json"
        filepath = os.path.join(self.event_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log_info(f"Data {data_type} disimpan ke {filepath}")
        except Exception as e:
            log_error(f"Gagal menyimpan data {data_type}: {str(e)}")
        return filepath

    def get_detection(self, limit=50):
        """
        Get detections/alerts (cloud-detection/alerts)
        Returns parsed JSON or None
        """
        url = f"{self.base_url}/web/api/v2.1/cloud-detection/alerts?limit={limit}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=20)
            response.raise_for_status()
            data = response.json()
            # store raw
            fp = self._store_data("detections", data)
            # append events for daily archive
            try:
                items = data.get("data", [])
                if items:
                    append_events(items)
            except Exception as e:
                log_error(f"append_events failed: {e}")

            log_success(f"Berhasil mendapatkan {len(data.get('data', []))} deteksi(s).")
            # trigger notifications per item (simple)
            self._notify_items(data.get("data", []), fp)
            return data
        except requests.RequestException as e:
            log_error(f"Gagal mendapatkan deteksi: {e}")
            return None
        except Exception as e:
            log_error(f"Exception in get_detection: {e}")
            return None

    def _notify_items(self, items, filepath):
        """Send notifications to channels based on routing config. Best-effort, quick summary."""
        if not items:
            return
        cfg = load_config()
        routing = cfg.get("routing", {}).get("severity_to_channels", {})
        channels_cfg = cfg.get("channels", {})

        # we'll send a single summary for now (could be per-item)
        try:
            # Example simple aggregation: count by classification/severity if available
            summary_lines = [f"Found {len(items)} new detection(s). Saved: {filepath}"]
            # pick top 3 items for detail
            for it in items[:3]:
                name = (it.get("threatInfo") or {}).get("threatName") or it.get("id") or "N/A"
                site = (it.get("agentRealtimeInfo") or it.get("agentDetectionInfo") or {}).get("agentComputerName") or it.get("agentName") or "unknown"
                summary_lines.append(f"- {name} on {site}")
            summary = "\n".join(summary_lines)

            # Telegram
            tg = channels_cfg.get("telegram", {})
            if tg.get("enabled") and tg.get("bot_token") and tg.get("chat_id"):
                from notifier.telegram import TelegramNotifier
                tn = TelegramNotifier(token=tg.get("bot_token"), chat_id=tg.get("chat_id"))
                tn.send(summary)

            # Teams
            tm = channels_cfg.get("teams", {})
            if tm.get("enabled") and tm.get("webhook_url"):
                from notifier.teams import TeamsNotifier
                t2 = TeamsNotifier(tm.get("webhook_url"))
                t2.send(summary)

            # WhatsApp (optional)
            wa = channels_cfg.get("whatsapp", {})
            if wa.get("enabled"):
                bridge = wa.get("bridge", {})
                notify_to = wa.get("notify_number")
                if notify_to:
                    from src.whatsapp import WhatsAppBridge
                    wb = WhatsAppBridge(bridge.get("base_url"))
                    wb.send_message(notify_to, summary, session=bridge.get("session_name"))
        except Exception as e:
            log_error(f"Notification dispatch error: {e}")

    def start_polling(self, interval=60):
        """
        Start polling according to given interval in seconds. This blocks until interrupted.
        """
        log_info(f"Starting polling every {interval} seconds...")
        try:
            while True:
                try:
                    self.get_detection(limit=50)
                except Exception as e:
                    log_error(f"Polling cycle error: {e}")
                time.sleep(interval)
        except KeyboardInterrupt:
            log_info("Polling stopped by user.")
        except Exception as e:
            log_error(f"Polling worker exception: {e}")
            time.sleep(interval)