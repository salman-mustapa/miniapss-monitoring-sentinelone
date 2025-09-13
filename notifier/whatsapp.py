# notifier/whatsapp.py
import requests
import json
from datetime import datetime
from src.logger import get_logger, log_success, log_error, log_info

logger = get_logger()

class WhatsAppNotifier:
    def __init__(self, base_url: str, session_name: str = "gateway", recipients: list = None):
        self.base_url = base_url.rstrip("/")
        self.session_name = session_name
        self.recipients = recipients or []
        self.session = requests.Session()
        self.session.timeout = 20

    def _format_message(self, message: str) -> str:
        """Format message for WhatsApp with emojis and timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        formatted = f"🛡️ *SentinelOne Monitor*\n"
        formatted += f"📅 {timestamp}\n"
        formatted += f"{'='*30}\n\n"
        formatted += f"{message}\n\n"
        formatted += f"🔐 _Automated Security Alert_"
        
        return formatted

    def send(self, message: str) -> bool:
        """Send WhatsApp message to all configured recipients"""
        if not self.recipients:
            log_error("WhatsAppNotifier: no recipients configured")
            return False

        if not self.base_url:
            log_error("WhatsAppNotifier: no gateway URL configured")
            return False

        success_count = 0
        total_recipients = len(self.recipients)
        formatted_message = self._format_message(message)

        for recipient in self.recipients:
            try:
                result = self.send_message(recipient, formatted_message)
                
                if result.get('success', False):
                    success_count += 1
                    log_success(f"WhatsApp message sent to {recipient}")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    log_error(f"WhatsApp send failed to {recipient}: {error_msg}")
                    
            except Exception as e:
                log_error(f"WhatsApp error for {recipient}: {e}")

        if success_count == total_recipients:
            log_success(f"WhatsApp notification sent to all {total_recipients} recipients")
            return True
        elif success_count > 0:
            log_info(f"WhatsApp notification sent to {success_count}/{total_recipients} recipients")
            return True
        else:
            log_error("WhatsApp notification failed for all recipients")
            return False

    def send_message(self, number_or_group: str, message: str) -> dict:
        """Send message to specific WhatsApp number or group"""
        try:
            url = f"{self.base_url}/api/kirim-pesan"
            payload = {
                "number": number_or_group,
                "message": message,
                "session": self.session_name
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'SentinelOne-Monitor/2.0'
            }
            
            response = self.session.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                result['recipient'] = number_or_group
                result['session_name'] = self.session_name
                return result
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "recipient": number_or_group,
                    "session_name": self.session_name
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout",
                "recipient": number_or_group,
                "session_name": self.session_name
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "recipient": number_or_group,
                "session_name": self.session_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "recipient": number_or_group,
                "session_name": self.session_name
            }

    def test_connection(self) -> dict:
        """Test WhatsApp gateway connection"""
        try:
            url = f"{self.base_url}/api/sessions"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "sessions": data.get('sessions', []),
                    "message": "Gateway connection successful"
                }
            else:
                return {
                    "success": False,
                    "error": f"Gateway error: {response.status_code}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}


class WhatsAppBridge:
    """Enhanced WhatsApp Bridge for gateway management"""
    
    def __init__(self, base_url: str, default_session: str = "gateway"):
        self.base_url = base_url.rstrip("/")
        self.default_session = default_session
        self.session = requests.Session()
        self.session.timeout = 20

    def _make_request(self, method: str, path: str, params: dict = None, data: dict = None) -> dict:
        """Make HTTP request with error handling"""
        try:
            url = f"{self.base_url}{path}"
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'SentinelOne-Monitor/2.0'
            }
            
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def list_sessions(self) -> dict:
        """List all WhatsApp sessions"""
        result = self._make_request('GET', '/api/sessions')
        
        # Enhance session data
        if result.get('success') and 'sessions' in result:
            for session in result['sessions']:
                if 'status' not in session:
                    session['status'] = 'unknown'
                if 'health' not in session:
                    session['health'] = 'good' if session.get('status') == 'connected' else 'warning'
        
        return result

    def connect_session(self, session: str = None) -> dict:
        """Connect/create WhatsApp session"""
        session_name = session or self.default_session
        data = {"session": session_name}
        result = self._make_request('POST', '/api/connect', data=data)
        result['session_name'] = session_name
        return result

    def get_qr(self, session: str = None) -> dict:
        """Get QR code for session"""
        session_name = session or self.default_session
        params = {"session": session_name}
        result = self._make_request('GET', '/api/qr', params=params)
        result['session_name'] = session_name
        return result

    def list_groups(self, session: str = None) -> dict:
        """List WhatsApp groups for session"""
        session_name = session or self.default_session
        params = {"session": session_name}
        return self._make_request('GET', '/api/groups', params=params)

    def fetch_groups(self, session: str = None) -> dict:
        """Fetch/refresh WhatsApp groups for session"""
        session_name = session or self.default_session
        params = {"session": session_name}
        return self._make_request('GET', '/api/fetch-groups', params=params)

    def get_logs(self, session: str = None, target: str = None) -> dict:
        """Get logs for session or specific target"""
        session_name = session or self.default_session
        
        if target:
            path = f"/api/logs/{target}"
        else:
            path = "/api/logs"
            
        params = {"session": session_name}
        result = self._make_request('GET', path, params=params)
        result['session_name'] = session_name
        
        if target:
            result['target'] = target
            
        return result

    def send_message(self, number_or_group: str, message: str, session: str = None) -> dict:
        """Send WhatsApp message"""
        session_name = session or self.default_session
        data = {
            "number": number_or_group,
            "message": message,
            "session": session_name
        }
        
        result = self._make_request('POST', '/api/kirim-pesan', data=data)
        result['recipient'] = number_or_group
        result['session_name'] = session_name
        return result
