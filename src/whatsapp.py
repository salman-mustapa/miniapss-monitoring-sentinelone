import requests
from src.logger import get_logger

logger = get_logger()

class WhatsAppBridge:
    def __init__(self, base_url: str, default_session: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.default_session = default_session

    def _get(self, path: str, params=None):
        try:
            url = f"{self.base_url}{path}"
            r = requests.get(url, params=params, timeout=15)
            return r.json()
        except Exception as e:
            logger.error(f"WA GET {path} error: {e}")
            return {"success": False, "error": str(e)}

    def _post(self, path: str, data=None):
        try:
            url = f"{self.base_url}{path}"
            r = requests.post(url, json=data or {}, timeout=15)
            return r.json()
        except Exception as e:
            logger.error(f"WA POST {path} error: {e}")
            return {"success": False, "error": str(e)}

    # sessions
    def list_sessions(self):
        """List all WhatsApp sessions with status information"""
        try:
            response = self._get("/api/sessions")
            # Enhance session data with status indicators
            if isinstance(response, dict) and 'sessions' in response:
                for session in response['sessions']:
                    if 'status' not in session:
                        session['status'] = 'unknown'
                    # Add connection timestamp if available
                    if 'connected_at' not in session and session.get('status') == 'connected':
                        session['connected_at'] = 'unknown'
            return response
        except Exception as e:
            return {"success": False, "error": str(e), "sessions": []}

    def connect_session(self, session=None):
        """Connect/create a WhatsApp session with enhanced error handling"""
        try:
            response = self._post("/api/connect", {"session": session or self.default_session})
            if isinstance(response, dict):
                # Add session name to response for tracking
                response['session_name'] = session or self.default_session
            return response
        except Exception as e:
            return {
                "success": False, 
                "error": str(e), 
                "session_name": session or self.default_session
            }

    # QR
    def get_qr(self, session=None):
        """Get QR code for WhatsApp session with enhanced error handling"""
        try:
            response = self._get("/api/qr", {"session": session or self.default_session})
            if isinstance(response, dict):
                response['session_name'] = session or self.default_session
            return response
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "session_name": session or self.default_session
            }

    # groups
    def list_groups(self, session=None):
        return self._get("/api/groups", {"session": session or self.default_session})

    def fetch_groups(self, session=None):
        return self._get("/api/fetch-groups", {"session": session or self.default_session})

    # message
    def send_message(self, number_or_group, message, session=None):
        """Send WhatsApp message with enhanced error handling and validation"""
        try:
            if not number_or_group or not message:
                return {
                    "success": False,
                    "error": "Number/group and message are required",
                    "session_name": session or self.default_session
                }
            
            # Use JSON format as per the API example
            data = {
                "number": number_or_group,
                "message": message,
                "session": session or self.default_session
            }
            
            try:
                url = f"{self.base_url}/api/kirim-pesan"
                r = requests.post(url, json=data, timeout=15)
                response = r.json()
            except Exception as e:
                logger.error(f"WA POST /api/kirim-pesan error: {e}")
                return {"success": False, "error": str(e)}
            
            if isinstance(response, dict):
                response['session_name'] = session or self.default_session
                response['recipient'] = number_or_group
            
            return response
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "session_name": session or self.default_session,
                "recipient": number_or_group
            }

    # logs
    def list_logs(self, session=None):
        """Get logs for a session"""
        try:
            params = {"session": session or self.default_session}
            url = f"{self.base_url}/api/logs"
            r = requests.get(url, params=params, timeout=15)
            response = r.json()
            
            if isinstance(response, dict):
                response['session_name'] = session or self.default_session
            
            return response
        except Exception as e:
            logger.error(f"WA GET /api/logs error: {e}")
            return {"success": False, "error": str(e)}

    def get_logs(self, target, session=None):
        """Get logs for a specific target (phone number) in a session"""
        try:
            params = {"session": session or self.default_session}
            url = f"{self.base_url}/api/logs/{target}"
            r = requests.get(url, params=params, timeout=15)
            response = r.json()
            
            if isinstance(response, dict):
                response['session_name'] = session or self.default_session
                response['target'] = target
            
            return response
        except Exception as e:
            logger.error(f"WA GET /api/logs/{target} error: {e}")
            return {"success": False, "error": str(e)}