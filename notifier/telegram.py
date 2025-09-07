# notifier/telegram.py
import requests
from src.logger import get_logger

logger = get_logger()

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        # fixed URL (api.telegram.org)
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logger.error("TelegramNotifier: missing token or chat_id")
            return False
        try:
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            resp = requests.post(self.base_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram message sent")
                return True
            else:
                logger.error(f"Telegram API error: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.exception(f"Error sending Telegram message: {e}")
            return False
