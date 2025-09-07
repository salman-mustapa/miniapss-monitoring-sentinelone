# src/sentinel_api.py
import requests
import json
import os
import time
from datetime import datetime
from src.logger import log_info, log_error, log_debug, log_success
from src.config import load_config


class SentinelAPI:
    def __init__(self, config):
        self.base_url = config.get("sentinelone", {}).get("base_url")
        self.api_token = config.get("sentinelone", {}).get("api_token")
        self.event_dir = "storage/events"

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

    def get_detection(self, limit=10):
        """
        Mendapatkan deteksi terbaru dari SentinelOne.
        """
        url = f"{self.base_url}/web/api/v2.1/cloud-detection/alerts?limit={limit}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=15)
            response.raise_for_status()
            data = response.json()

            # simpan raw data ke file
            self._store_data("detections", data)

            log_success(f"Berhasil mendapatkan {len(data.get('data', []))} deteksi(s).")
            return data
        except requests.RequestException as e:
            log_info(f"Gagal mendapatkan deteksi: {str(e)}")
            return None
        except Exception as e:
            log_error(f"Exception: {str(e)}")

    def _store_data(self, data_type, data):
        """Simpan raw json ke folder storage/events"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{data_type}_{timestamp}.json"
        filepath = os.path.join(self.event_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log_info(f"Data {data_type} disimpan ke {filepath}")
        except Exception as e:
            log_error(f"Gagal menyimpan data {data_type}: {str(e)}")

    def start_polling(self, interval=60):
        """
        Mulai polling deteksi setiap interval detik.
        """
        log_info(f"Memulai polling deteksi setiap {interval} detik... (CTRL+C untuk berhenti)")

        try:
            while True:
                self.get_detection(limit=10)
                time.sleep(interval)
        except KeyboardInterrupt:
            log_info("Polling dihentikan oleh user.")
        except Exception as e:
            log_error(f"Error saat polling: {str(e)}")
            time.sleep(interval)
