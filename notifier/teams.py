# notifier/teams.py
import requests
import json
from datetime import datetime
from src.logger import get_logger, log_success, log_error, log_info

logger = get_logger()

class TeamsNotifier:
    def __init__(self, webhook_url: str = None, webhook_urls: list = None):
        self.webhook_url = webhook_url
        self.webhook_urls = webhook_urls or ([webhook_url] if webhook_url else [])
        self.session = requests.Session()
        self.session.timeout = 15

    def _create_adaptive_card(self, message: str, severity: str = "information") -> dict:
        """Create Microsoft Teams Adaptive Card for better formatting"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color scheme based on severity
        color_map = {
            "information": "Good",
            "warning": "Warning", 
            "error": "Attention",
            "success": "Good"
        }
        
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": "SentinelOne Monitor Alert",
            "themeColor": "00FF41" if severity == "success" else "FF6B35" if severity == "error" else "FFD23F",
            "sections": [
                {
                    "activityTitle": "🛡️ SentinelOne Monitor",
                    "activitySubtitle": f"Alert - {timestamp}",
                    "activityImage": "https://cdn-icons-png.flaticon.com/512/2092/2092063.png",
                    "facts": [
                        {
                            "name": "Timestamp",
                            "value": timestamp
                        },
                        {
                            "name": "Severity", 
                            "value": severity.upper()
                        }
                    ],
                    "text": message
                }
            ]
        }
        
        return card

    def _create_simple_payload(self, message: str) -> dict:
        """Create simple text payload as fallback"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"🛡️ **SentinelOne Monitor**\n\n📅 {timestamp}\n\n{message}"
        
        return {"text": formatted_message}

    def send(self, message: str, severity: str = "information", use_adaptive_card: bool = True) -> bool:
        """Send message to Microsoft Teams with enhanced formatting"""
        if not self.webhook_urls:
            log_error("TeamsNotifier: no webhook URLs configured")
            return False

        success_count = 0
        total_webhooks = len(self.webhook_urls)
        
        for webhook_url in self.webhook_urls:
            if not webhook_url:
                continue
                
            try:
                # Try adaptive card first, fallback to simple text
                if use_adaptive_card:
                    payload = self._create_adaptive_card(message, severity)
                else:
                    payload = self._create_simple_payload(message)
                
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'SentinelOne-Monitor/2.0'
                }
                
                resp = self.session.post(webhook_url, json=payload, headers=headers)
                
                if resp.status_code in (200, 201, 202):
                    success_count += 1
                    log_success(f"Teams message sent to webhook")
                elif resp.status_code == 400 and use_adaptive_card:
                    # Retry with simple payload if adaptive card fails
                    log_info("Teams adaptive card failed, retrying with simple format")
                    simple_payload = self._create_simple_payload(message)
                    retry_resp = self.session.post(webhook_url, json=simple_payload, headers=headers)
                    
                    if retry_resp.status_code in (200, 201, 202):
                        success_count += 1
                        log_success(f"Teams message sent with simple format")
                    else:
                        log_error(f"Teams API error (retry): {retry_resp.status_code} - {retry_resp.text}")
                else:
                    log_error(f"Teams API error: {resp.status_code} - {resp.text}")
                    
            except requests.exceptions.Timeout:
                log_error(f"Teams webhook timeout")
            except requests.exceptions.RequestException as e:
                log_error(f"Teams network error: {e}")
            except Exception as e:
                log_error(f"Teams unexpected error: {e}")

        if success_count == total_webhooks:
            log_success(f"Teams notification sent to all {total_webhooks} webhooks")
            return True
        elif success_count > 0:
            log_info(f"Teams notification sent to {success_count}/{total_webhooks} webhooks")
            return True
        else:
            log_error("Teams notification failed for all webhooks")
            return False

    def test_connection(self) -> dict:
        """Test Teams webhook connection"""
        if not self.webhook_urls:
            return {"success": False, "error": "No webhook URLs configured"}
        
        test_message = "🧪 Connection test from SentinelOne Monitor"
        
        try:
            # Test with first webhook
            webhook_url = self.webhook_urls[0]
            payload = self._create_simple_payload(test_message)
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'SentinelOne-Monitor/2.0'
            }
            
            resp = self.session.post(webhook_url, json=payload, headers=headers)
            
            if resp.status_code in (200, 201, 202):
                return {
                    "success": True,
                    "message": "Teams webhook connection successful"
                }
            else:
                return {
                    "success": False,
                    "error": f"Webhook error: {resp.status_code}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_alert(self, title: str, message: str, severity: str = "warning") -> bool:
        """Send formatted alert to Teams"""
        alert_message = f"**{title}**\n\n{message}"
        return self.send(alert_message, severity, use_adaptive_card=True)
