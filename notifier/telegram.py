# notifier/telegram.py
import requests
import json
from datetime import datetime
from src.logger import get_logger, log_success, log_error, log_info

logger = get_logger()

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str = None, chat_ids: list = None):
        self.token = token
        self.chat_id = chat_id
        self.chat_ids = chat_ids or ([chat_id] if chat_id else [])
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.session = requests.Session()
        self.session.timeout = 15

    def _format_message(self, message: str, format_type: str = "markdown") -> str:
        """Format message for better display"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if format_type == "markdown":
            formatted = f"🛡️ *SentinelOne Monitor*\n"
            formatted += f"📅 `{timestamp}`\n\n"
            formatted += f"{message}"
        else:
            formatted = f"🛡️ SentinelOne Monitor\n"
            formatted += f"📅 {timestamp}\n\n"
            formatted += f"{message}"
        
        return formatted

    def send(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram with enhanced formatting and error handling"""
        if not self.token:
            log_error("TelegramNotifier: missing bot token")
            return False
        
        if not self.chat_ids:
            log_error("TelegramNotifier: no chat IDs configured")
            return False

        success_count = 0
        total_chats = len(self.chat_ids)
        
        formatted_message = self._format_message(message, "markdown" if parse_mode == "Markdown" else "html")
        
        for chat_id in self.chat_ids:
            try:
                payload = {
                    "chat_id": chat_id,
                    "text": formatted_message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
                
                url = f"{self.base_url}/sendMessage"
                resp = self.session.post(url, json=payload)
                
                if resp.status_code == 200:
                    success_count += 1
                    log_success(f"Telegram message sent to chat {chat_id}")
                else:
                    error_data = resp.json() if resp.content else {}
                    error_desc = error_data.get('description', resp.text)
                    log_error(f"Telegram API error for chat {chat_id}: {resp.status_code} - {error_desc}")
                    
            except requests.exceptions.Timeout:
                log_error(f"Telegram timeout for chat {chat_id}")
            except requests.exceptions.RequestException as e:
                log_error(f"Telegram network error for chat {chat_id}: {e}")
            except Exception as e:
                log_error(f"Telegram unexpected error for chat {chat_id}: {e}")

        success_rate = success_count / total_chats if total_chats > 0 else 0
        
        if success_count == total_chats:
            log_success(f"Telegram notification sent to all {total_chats} chats")
            return True
        elif success_count > 0:
            log_info(f"Telegram notification sent to {success_count}/{total_chats} chats")
            return True
        else:
            log_error("Telegram notification failed for all chats")
            return False

    def test_connection(self) -> dict:
        """Test Telegram bot connection"""
        if not self.token:
            return {"success": False, "error": "No bot token configured"}
        
        try:
            url = f"{self.base_url}/getMe"
            resp = self.session.get(url)
            
            if resp.status_code == 200:
                bot_info = resp.json()
                return {
                    "success": True,
                    "bot_info": bot_info.get('result', {}),
                    "message": "Bot connection successful"
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {resp.status_code}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_chat_info(self, chat_id: str) -> dict:
        """Get information about a chat"""
        try:
            url = f"{self.base_url}/getChat"
            resp = self.session.get(url, params={"chat_id": chat_id})
            
            if resp.status_code == 200:
                return {"success": True, "chat_info": resp.json().get('result', {})}
            else:
                return {"success": False, "error": f"API error: {resp.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
