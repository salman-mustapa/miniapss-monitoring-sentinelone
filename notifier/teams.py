# notifier/teams.py
import requests
from src.logger import get_logger

logger = get_logger()

class TeamsNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str) -> bool:
        if not self.webhook_url:
            logger.error("TeamsNotifier: missing webhook_url")
            return False
        try:
            payload = {"text": message}
            r = requests.post(self.webhook_url, json=payload, timeout=10)
            if r.status_code in (200, 201, 202):
                logger.info("Teams message sent")
                return True
            else:
                logger.error(f"Teams API error: {r.status_code} {r.text}")
                return False
        except Exception as e:
            logger.exception(f"Teams send error: {e}")
            return False
