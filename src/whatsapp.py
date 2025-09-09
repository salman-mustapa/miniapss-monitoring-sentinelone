# src/whatsapp.py
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
from src.config import load_config
from src.logger import log_info, log_error

class WhatsAppBridge:
    def __init__(self, base_url: Optional[str] = None):
        cfg = load_config()
        wa_cfg = cfg.get("channels", {}).get("whatsapp", {}).get("bridge", {}).get("base_url", {})
        self.base_url = (wa_cfg.get("base_url") or base_url  or "https://wa-gateway.salmanmustapa.my.id").rstrip("/")
        # default endpoints from your node gateway
        self.endpoints = {
            "sessions": "/api/sessions",
            "qr": "/api/qr",
            "groups": "/api/groups",
            "fetch_groups": "/api/fetch-groups",
            "connect": "/api/connect",
            "send": "/api/kirim-pesan",
            "logs": "/api/logs"
        }

    def _url(self, key: str, params: Dict[str, Any] = None) -> str:
        p = ""
        if params:
            # append query string manually only for simple cases
            from urllib.parse import urlencode
            p = "?" + urlencode(params)
        return self.base_url + self.endpoints.get(key, "") + p

    def list_sessions(self) -> Dict[str, Any]:
        try:
            r = requests.get(self._url("sessions"), timeout=10)
            return r.json()
        except Exception as e:
            log_error(f"WA list_sessions error: {e}")
            return {"success": False, "error": str(e)}

    def get_qr(self, session: str = None) -> Dict[str, Any]:
        try:
            params = {"session": session} if session else {}
            r = requests.get(self._url("qr", params=params), timeout=10)
            return r.json()
        except Exception as e:
            log_error(f"WA get_qr error: {e}")
            return {"success": False, "error": str(e)}

    def list_groups(self, session: str = None) -> Dict[str, Any]:
        try:
            params = {"session": session} if session else {}
            r = requests.get(self._url("groups", params=params), timeout=15)
            return r.json()
        except Exception as e:
            log_error(f"WA list_groups error: {e}")
            return {"success": False, "error": str(e)}

    def fetch_groups(self, session: str = None) -> Dict[str, Any]:
        try:
            params = {"session": session} if session else {}
            r = requests.get(self._url("fetch_groups", params=params), timeout=30)
            return r.json()
        except Exception as e:
            log_error(f"WA fetch_groups error: {e}")
            return {"success": False, "error": str(e)}

    def connect_session(self, session: str = "default") -> Dict[str, Any]:
        try:
            payload = {"session": session}
            r = requests.post(self.base_url + self.endpoints["connect"], json=payload, timeout=10)
            return r.json()
        except Exception as e:
            log_error(f"WA connect_session error: {e}")
            return {"success": False, "error": str(e)}

    def send_message(self, number_or_group: str, message: str, session: str = None) -> Dict[str, Any]:
        try:
            payload = {"number": number_or_group, "message": message, "session": session}
            r = requests.post(self.base_url + self.endpoints["send"], json=payload, timeout=15)
            return r.json()
        except Exception as e:
            log_error(f"WA send_message error: {e}")
            return {"success": False, "error": str(e)}