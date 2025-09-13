# src/webapp.py
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
import requests, os, json, mimetypes
from datetime import datetime

from src.config import load_config, save_config
from src.logger import get_logger, log_info, log_error, log_success
from src.whatsapp import WhatsAppBridge
from notifier.whatsapp import WhatsAppBridge as WhatsAppGateway, WhatsAppNotifier
from notifier.telegram import TelegramNotifier
from notifier.teams import TeamsNotifier

logger = get_logger()
app = FastAPI(title="SentinelOne Monitor v2.0", description="Advanced Security Monitoring System")
templates = Jinja2Templates(directory="templates")

# mount static if exists (css/js)
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse("static/favicon.ico")

# small helper: require auth (session kept simple in memory)
SESSION = {"auth": False}
def get_pin():
    try:
        cfg = load_config()
    except Exception:
        return "tOOr12345*"
    pin = cfg.get("web", {}).get("pin")
    return str(pin) if pin else "tOOr12345*"

def require_auth_redirect():
    if not SESSION.get("auth"):
        return RedirectResponse("/login", status_code=303)
    return None

# Utility: safe load config
def safe_load_cfg():
    try:
        return load_config()
    except Exception as e:
        logger.error(f"Config load error: {e}")
        # return minimal default skeleton to avoid crashes
        return {
            "channels": {"whatsapp": {"bridge": {"base_url": "", "session_name": "default"}}},
            "sentinelone": {},
            "polling": {"interval_seconds": 60},
            "web": {"pin": ""},
        }

# ---------------- UI routes ----------------
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    return templates.TemplateResponse("index.html", {"request": request, "config": cfg})

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(pin: str = Form(...)):
    if str(pin) == get_pin():
        SESSION["auth"] = True
        log_info("User logged in via web UI")
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login", status_code=303)

@app.get("/logout")
async def logout():
    SESSION["auth"] = False
    log_info("User logged out")
    return RedirectResponse("/login", status_code=303)

# ------------- config page (redirect to main dashboard) -------------
@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    return RedirectResponse("/", status_code=303)

@app.post("/config")
async def save_config_form(request: Request, 
                          sentinel_base_url: str = Form(""),
                          sentinel_api_token: str = Form(""),
                          web_pin: str = Form("")):
    """Save config from form"""
    try:
        cfg = safe_load_cfg()
        
        # Update SentinelOne config
        if "sentinelone" not in cfg:
            cfg["sentinelone"] = {}
        cfg["sentinelone"]["base_url"] = sentinel_base_url
        cfg["sentinelone"]["api_token"] = sentinel_api_token
        
        # Update web config
        if "web" not in cfg:
            cfg["web"] = {}
        cfg["web"]["pin"] = web_pin
        
        save_config(cfg)
        log_success("Configuration saved successfully")
        return RedirectResponse(url="/config?saved=1", status_code=303)
    except Exception as e:
        log_error(f"Failed to save config: {e}")
        return RedirectResponse(url="/config?error=1", status_code=303)

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """Notifications settings page - redirect to main dashboard"""
    r = require_auth_redirect()
    if r:
        return r
    return RedirectResponse("/", status_code=303)

@app.post("/api/notifications")
async def save_notifications(request: Request):
    """Save notification settings"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        cfg = load_config()
        
        # Update config with new notification settings
        if "channels" in data:
            cfg["channels"] = cfg.get("channels", {})
            cfg["channels"].update(data["channels"])
            
            # Also update notifications section for backward compatibility
            cfg["notifications"] = cfg.get("notifications", {})
            
            # Map channels to notifications format
            for channel_type, channel_config in data["channels"].items():
                if channel_type == "whatsapp":
                    cfg["notifications"]["whatsapp"] = {
                        "enabled": channel_config.get("enabled", False),
                        "session": channel_config.get("session_name", "default"),
                        "recipients": channel_config.get("recipients", []),
                        "template": channel_config.get("template", "")
                    }
                elif channel_type == "telegram":
                    cfg["notifications"]["telegram"] = {
                        "enabled": channel_config.get("enabled", False),
                        "chats": channel_config.get("chats", []),
                        "template": channel_config.get("template", "")
                    }
                elif channel_type == "teams":
                    cfg["notifications"]["teams"] = {
                        "enabled": channel_config.get("enabled", False),
                        "webhooks": channel_config.get("webhooks", []),
                        "template": channel_config.get("template", "")
                    }
        
        save_config(cfg)
        log_success("Notification settings saved")
        return JSONResponse({"success": True})
    except Exception as e:
        log_error(f"Failed to save notification settings: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/test-notifications")
async def test_notifications(request: Request):
    """Test all notification channels"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        cfg = safe_load_cfg()
        results = {"success": [], "errors": []}
        
        # Test message
        test_message = "🧪 Test notification from SentinelOne Monitor\n\nThis is a test to verify your notification channels are working correctly."
        
        # Test WhatsApp
        wa_settings = cfg.get("notifications", {}).get("whatsapp", {})
        if wa_settings.get("enabled"):
            session = wa_settings.get("session", "default")
            recipients = wa_settings.get("recipients", [])
            
            for recipient in recipients:
                try:
                    wb = get_whatsapp_bridge()
                    wb.session = session
                    wb.send_message(recipient, test_message)
                    results["success"].append(f"WhatsApp: {recipient}")
                    log_success(f"Test WA message sent to {recipient}")
                except Exception as e:
                    error_msg = f"WhatsApp {recipient}: {str(e)}"
                    results["errors"].append(error_msg)
                    log_error(f"Test WA failed for {recipient}: {e}")
        
        # Test Telegram
        tg_settings = cfg.get("notifications", {}).get("telegram", {})
        tg_legacy = cfg.get("channels", {}).get("telegram", {})
        
        if (tg_settings.get("enabled") or tg_legacy.get("enabled")) and tg_legacy.get("bot_token"):
            chat_id = tg_settings.get("chat_id") or tg_legacy.get("chat_id")
            if chat_id:
                try:
                    from notifier.telegram import TelegramNotifier
                    tn = TelegramNotifier(token=tg_legacy.get("bot_token"), chat_id=chat_id)
                    tn.send(test_message)
                    results["success"].append(f"Telegram: {chat_id}")
                    log_success(f"Test Telegram message sent to {chat_id}")
                except Exception as e:
                    error_msg = f"Telegram {chat_id}: {str(e)}"
                    results["errors"].append(error_msg)
                    log_error(f"Test Telegram failed: {e}")
        
        # Test Teams
        teams_settings = cfg.get("notifications", {}).get("teams", {})
        teams_legacy = cfg.get("channels", {}).get("teams", {})
        
        if (teams_settings.get("enabled") or teams_legacy.get("enabled")):
            webhook_url = teams_settings.get("webhook_url") or teams_legacy.get("webhook_url")
            if webhook_url:
                try:
                    from notifier.teams import TeamsNotifier
                    tn2 = TeamsNotifier(webhook_url)
                    tn2.send(test_message)
                    results["success"].append("Teams: Webhook")
                    log_success("Test Teams message sent")
                except Exception as e:
                    error_msg = f"Teams: {str(e)}"
                    results["errors"].append(error_msg)
                    log_error(f"Test Teams failed: {e}")
        
        return JSONResponse({"success": True, "results": results})
    except Exception as e:
        log_error(f"Test notifications error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/storage/all")
async def get_all_storage(request: Request, limit: int = 100, search: Optional[str] = None):
    """Get all files from storage directory organized by folders"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        import glob
        from pathlib import Path
        
        folders = {}
        storage_path = "storage"
        
        if os.path.exists(storage_path):
            # Get all items in storage directory
            for item in os.listdir(storage_path):
                item_path = os.path.join(storage_path, item)
                
                # Skip .gitkeep files
                if item == '.gitkeep':
                    continue
                    
                if os.path.isdir(item_path):
                    folder_files = []
                    
                    # Get all files in this folder recursively
                    try:
                        for root, dirs, files in os.walk(item_path):
                            for file in files:
                                if file == '.gitkeep':
                                    continue
                                    
                                filepath = os.path.join(root, file)
                                try:
                                    stat = os.stat(filepath)
                                    filename = os.path.basename(filepath)
                                    
                                    # Apply search filter
                                    if search and search.lower() not in filename.lower():
                                        continue
                                    
                                    folder_files.append({
                                        "name": filename,
                                        "path": filepath.replace("\\", "/"),
                                        "size": stat.st_size,
                                        "modified": stat.st_mtime
                                    })
                                except (OSError, IOError) as e:
                                    log_error(f"Error reading file {filepath}: {e}")
                                    continue
                    except Exception as e:
                        log_error(f"Error walking directory {item_path}: {e}")
                        continue
                    
                    # Always include folder even if empty, but show count
                    folders[item] = folder_files
                elif os.path.isfile(item_path):
                    # Handle files directly in storage root
                    try:
                        stat = os.stat(item_path)
                        filename = os.path.basename(item_path)
                        
                        if search and search.lower() not in filename.lower():
                            continue
                            
                        if 'root_files' not in folders:
                            folders['root_files'] = []
                        
                        folders['root_files'].append({
                            "name": filename,
                            "path": item_path.replace("\\", "/"),
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
                    except (OSError, IOError) as e:
                        log_error(f"Error reading root file {item_path}: {e}")
                        continue
        
        return JSONResponse({
            "success": True,
            "folders": folders
        })
    except Exception as e:
        log_error(f"Failed to get storage files: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/backups")
async def get_backups(request: Request, limit: int = 20, offset: int = 0, search: Optional[str] = None, type: Optional[str] = None):
    """Get backup files"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        import glob
        from pathlib import Path
        
        files = []
        storage_dirs = ["storage/events", "storage/alerts"]
        
        for storage_dir in storage_dirs:
            if os.path.exists(storage_dir):
                pattern = os.path.join(storage_dir, "**", "*")
                for filepath in glob.glob(pattern, recursive=True):
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        filename = os.path.basename(filepath)
                        
                        # Apply search filter
                        if search and search.lower() not in filename.lower():
                            continue
                        
                        # Apply type filter
                        if type and type not in filepath:
                            continue
                        
                        files.append({
                            "name": filename,
                            "path": filepath.replace("\\", "/"),
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        # Apply pagination
        total = len(files)
        files = files[offset:offset + limit]
        
        return JSONResponse({
            "success": True,
            "files": files,
            "total": total,
            "offset": offset,
            "limit": limit
        })
    except Exception as e:
        log_error(f"Failed to get backups: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/management", response_class=HTMLResponse)
async def management_page(request: Request):
    """Management page - redirect to main dashboard"""
    r = require_auth_redirect()
    if r:
        return r
    return RedirectResponse("/", status_code=303)

@app.get("/api/processes")
async def get_processes(request: Request):
    """Get running processes"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        try:
            import psutil
        except ImportError:
            return JSONResponse({"error": "psutil not installed"}, status_code=500)
        processes = {}
        
        # Check for polling processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'run.py --polling' in cmdline:
                    processes['polling'] = {
                        'pid': proc.info['pid'],
                        'status': 'running',
                        'started': proc.info['create_time']
                    }
                elif 'run.py --backup' in cmdline:
                    processes['backup'] = {
                        'pid': proc.info['pid'],
                        'status': 'running',
                        'started': proc.info['create_time']
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return JSONResponse({"success": True, "processes": processes})
    except Exception as e:
        log_error(f"Failed to get processes: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/processes/start")
async def start_process(request: Request):
    """Start a background process"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import subprocess
        import sys
        
        data = await request.json()
        process_type = data.get('type')
        
        if process_type == 'polling':
            interval = data.get('interval', 60)
            
            # Update config with new interval
            cfg = safe_load_cfg()
            if 'polling' not in cfg:
                cfg['polling'] = {}
            cfg['polling']['interval_seconds'] = interval
            save_config(cfg)
            
            # Start polling process
            cmd = [sys.executable, 'run.py', '--polling']
            subprocess.Popen(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            log_success(f"Started polling process with {interval}s interval")
            
        elif process_type == 'backup':
            frequency = data.get('frequency', 'daily')
            
            # Update config with backup frequency
            cfg = safe_load_cfg()
            if 'backup' not in cfg:
                cfg['backup'] = {}
            cfg['backup']['frequency'] = frequency
            save_config(cfg)
            
            # Start backup process
            cmd = [sys.executable, 'run.py', '--backup']
            subprocess.Popen(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            log_success(f"Started backup process ({frequency})")
        
        return JSONResponse({"success": True, "message": f"Started {process_type} process"})
    except Exception as e:
        log_error(f"Failed to start process: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/processes/stop")
async def stop_process(request: Request):
    """Stop a background process"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        try:
            import psutil
        except ImportError:
            return JSONResponse({"error": "psutil not installed"}, status_code=500)
        import signal
        
        data = await request.json()
        process_type = data.get('type')
        
        stopped = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if f'run.py --{process_type}' in cmdline:
                    proc.terminate()
                    # Wait for process to terminate
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()  # Force kill if doesn't terminate gracefully
                    stopped = True
                    log_success(f"Stopped {process_type} process (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not stopped:
            return JSONResponse({"error": f"No {process_type} process found"}, status_code=404)
        
        return JSONResponse({"success": True, "message": f"Stopped {process_type} process"})
    except Exception as e:
        log_error(f"Failed to stop process: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/test-connection")
async def test_connection(request: Request):
    """Test connection to services"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        connection_type = data.get('service') or data.get('type')
        
        if connection_type == 'sentinelone' or connection_type == 'sentinel':
            # Use provided URL and token from request, or fall back to config
            base_url = data.get('url') or data.get('base_url')
            api_token = data.get('token') or data.get('api_token')
            
            # If not provided in request, get from config
            if not base_url or not api_token:
                cfg = safe_load_cfg()
                sentinel_cfg = cfg.get('sentinelone', {})
                base_url = base_url or sentinel_cfg.get('base_url')
                api_token = api_token or sentinel_cfg.get('api_token')
            
            if not base_url or not api_token:
                return JSONResponse({"error": "SentinelOne configuration missing"}, status_code=400)
            
            # Test SentinelOne API connection
            import requests
            headers = {'Authorization': f'ApiToken {api_token}'}
            response = requests.get(f'{base_url}/web/api/v2.1/system/info', headers=headers, timeout=10)
            
            if response.status_code == 200:
                return JSONResponse({"success": True, "message": "SentinelOne connection successful"})
            else:
                return JSONResponse({"error": f"SentinelOne API error: {response.status_code}"}, status_code=400)
                
        elif connection_type == 'backup':
            import os
            storage_path = "storage"
            
            # Test storage directory access
            if not os.path.exists(storage_path):
                os.makedirs(storage_path, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(storage_path, 'test_write.tmp')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return JSONResponse({"success": True, "message": "Storage access successful"})
            except Exception as e:
                return JSONResponse({"error": f"Storage access failed: {str(e)}"}, status_code=400)
        
        return JSONResponse({"error": "Unknown connection type"}, status_code=400)
    except Exception as e:
        log_error(f"Connection test failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/whatsapp/sessions")
async def get_whatsapp_sessions(request: Request):
    """Get WhatsApp sessions from gateway"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        # Get WhatsApp gateway URL from config
        cfg = safe_load_cfg()
        gateway_config = cfg.get('whatsapp_gateway', {})
        gateway_url = gateway_config.get('base_url', 'http://localhost:5013')
        
        import requests
        response = requests.get(f'{gateway_url}/api/sessions', timeout=10)
        
        if response.status_code == 200:
            sessions_data = response.json()
            return JSONResponse({"success": True, "sessions": sessions_data})
        else:
            return JSONResponse({"success": False, "error": f"Gateway error: {response.status_code}", "sessions": []})
            
    except Exception as e:
        log_error(f"Failed to get WhatsApp sessions: {e}")
        return JSONResponse({"success": False, "error": str(e), "sessions": []})

@app.get("/api/processes/logs")
async def get_process_logs(request: Request):
    """Get recent process logs"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        import glob
        
        logs = []
        log_files = glob.glob("logs/*.log")
        
        for log_file in log_files[-3:]:  # Last 3 log files
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-10:]  # Last 10 lines
                    for line in lines:
                        if line.strip():
                            logs.append(line.strip())
            except Exception:
                continue
        
        return JSONResponse({"success": True, "logs": logs[-20:]})  # Last 20 log entries
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/backups/download")
async def download_backup(request: Request, path: str):
    """Download backup file"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        from fastapi.responses import FileResponse
        
        if not os.path.exists(path) or not path.startswith('storage/'):
            return JSONResponse({"error": "File not found"}, status_code=404)
        
        return FileResponse(path, filename=os.path.basename(path))
    except Exception as e:
        log_error(f"Download failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/config")
async def update_config(
    sentinel_base_url: Optional[str] = Form(None),
    sentinel_api_token: Optional[str] = Form(None),
    telegram_enabled: Optional[str] = Form(None),
    telegram_token: Optional[str] = Form(None),
    telegram_chat_id: Optional[str] = Form(None),
    teams_enabled: Optional[str] = Form(None),
    teams_webhook: Optional[str] = Form(None),
    wa_base_url: Optional[str] = Form(None),
    wa_session_name: Optional[str] = Form(None),
    polling_interval: Optional[int] = Form(None),
    web_pin: Optional[str] = Form(None)
):
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    cfg.setdefault("sentinelone", {})
    cfg.setdefault("channels", {})
    cfg.setdefault("polling", {})
    cfg.setdefault("web", {})

    if sentinel_base_url:
        cfg["sentinelone"]["base_url"] = sentinel_base_url.strip()
    if sentinel_api_token:
        cfg["sentinelone"]["api_token"] = sentinel_api_token.strip()

    # Telegram
    cfg["channels"].setdefault("telegram", {})
    cfg["channels"]["telegram"]["enabled"] = bool(telegram_enabled)
    if telegram_token:
        cfg["channels"]["telegram"]["bot_token"] = telegram_token.strip()
    if telegram_chat_id:
        cfg["channels"]["telegram"]["chat_id"] = telegram_chat_id.strip()

    # Teams
    cfg["channels"].setdefault("teams", {})
    cfg["channels"]["teams"]["enabled"] = bool(teams_enabled)
    if teams_webhook:
        cfg["channels"]["teams"]["webhook_url"] = teams_webhook.strip()

    # WhatsApp gateway
    cfg.setdefault("whatsapp", {})
    if wa_base_url:
        cfg["whatsapp"]["base_url"] = wa_base_url.strip()
    if wa_session_name:
        cfg["whatsapp"]["session_name"] = wa_session_name.strip()

    if polling_interval:
        try:
            cfg["polling"]["interval_seconds"] = int(polling_interval)
        except Exception:
            pass

    if web_pin:
        cfg["web"]["pin"] = str(web_pin).strip()

    save_config(cfg)
    log_info("Config updated via web")
    return RedirectResponse("/config", status_code=303)

# ------------- WhatsApp Bridge Helper -------------
def get_whatsapp_bridge():
    """Get configured WhatsApp bridge instance from config.json"""
    cfg = safe_load_cfg()
    wa_cfg = cfg.get("whatsapp", {})
    base_url = wa_cfg.get("base_url", "http://localhost:5013")
    session_name = wa_cfg.get("session_name", "default")
    return WhatsAppBridge(base_url, session_name)

# ---------- WhatsApp UI ----------
@app.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_page(request: Request):
    r = require_auth_redirect()
    if r:
        return r
    cfg = load_config()
    wa_conf = cfg.get("whatsapp", {})
    return templates.TemplateResponse("whatsapp.html", {
        "request": request,
        "wa": wa_conf or {}
    })

@app.post("/whatsapp/config")
async def whatsapp_config_save(
    base_url: str = Form(...),
    session_name: str = Form(...)
):
    r = require_auth_redirect()
    if r:
        return r
    
    cfg = safe_load_cfg()
    if "whatsapp" not in cfg:
        cfg["whatsapp"] = {}
    
    cfg["whatsapp"]["base_url"] = base_url.strip()
    cfg["whatsapp"]["session_name"] = session_name.strip()
    
    save_config(cfg)
    log_success("WhatsApp config saved")
    return RedirectResponse("/whatsapp", status_code=303)

# ------------- WhatsApp API Routes -------------
@app.get("/api/wa/sessions")
async def wa_sessions():
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.list_sessions()
        
        # Fix session status detection
        if isinstance(result, dict) and 'sessions' in result:
            for session in result['sessions']:
                # Fix status detection - check multiple possible status indicators
                if (session.get('ready') == True or 
                    session.get('status') == 'CONNECTED' or 
                    session.get('state') == 'CONNECTED' or
                    session.get('authenticated') == True):
                    session['status'] = 'connected'
                else:
                    session['status'] = 'disconnected'
                
                # Add last activity timestamp if not present
                if 'last_activity' not in session:
                    session['last_activity'] = 'unknown'
                # Add health status indicator
                if 'health' not in session:
                    session['health'] = 'good' if session.get('status') == 'connected' else 'warning'
        
        log_success(f"WA sessions retrieved: {len(result.get('sessions', []))} sessions")
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA sessions: {e}")
        return JSONResponse({"success": False, "error": str(e), "sessions": []})

@app.post("/api/wa/connect")
async def wa_connect(session: str = Form(...)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.connect_session(session)
        log_info(f"WA connect session: {session}")
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error connecting WA session: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/wa/qr")
async def wa_qr(session: str = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        if session:
            wb.session = session
        result = wb.get_qr(session)
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA QR: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/whatsapp/qr/{session}")
async def wa_qr_session(session: str):
    """Get QR code for specific session"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        wb = get_whatsapp_bridge()
        wb.session = session
        result = wb.get_qr(session)
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA QR for session {session}: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/wa/groups")
async def wa_groups(session: str = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.list_groups(session)
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA groups: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/wa/fetch-groups")
async def wa_fetch_groups(session: str = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.fetch_groups(session)
        log_info(f"WA groups fetched for session: {session}")
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA groups: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/kirim-pesan")
async def wa_send(number: str = Form(...), message: str = Form(...), session: str = Form(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        resp = wb.send_message(number, message, session)
        
        # Log WA messages in structured format by session and number
        session_name = session or wb.default_session
        log_dir = os.path.join("logs", "wa", session_name)
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{number}.json")
        
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
        new_log_entry = {
            "timestamp": ts,
            "session": session_name,
            "target": number,
            "message": message,
            "status": "sent" if resp.get("success") else "failed",
            "response": resp
        }
        
        # Read existing log file or create new structure
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
            except:
                log_data = {
                    "success": True,
                    "session": session_name,
                    "target": number,
                    "logs": []
                }
        else:
            log_data = {
                "success": True,
                "session": session_name,
                "target": number,
                "logs": []
            }
        
        # Add new log entry
        log_data["logs"].append(new_log_entry)
        
        # Write back to file
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        log_success(f"WA message sent to {number} via session {session or wb.default_session}")
        return JSONResponse(resp)
    except Exception as e:
        log_error(f"Error sending WA message: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/logs")
async def wa_logs(session: str = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.list_logs(session)
        log_success(f"WA logs retrieved for session: {session or 'default'}")
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA logs: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/wa-logs")
async def get_wa_logs(session: str = Query(None)):
    """Get local WhatsApp logs by session"""
    r = require_auth_redirect()
    if r:
        return r
    try:
        logs_data = {}
        base_log_dir = os.path.join("logs", "wa")
        
        if not os.path.exists(base_log_dir):
            return JSONResponse({"sessions": {}})
        
        # If specific session requested
        if session:
            session_dir = os.path.join(base_log_dir, session)
            if os.path.exists(session_dir):
                logs_data[session] = {}
                for file in os.listdir(session_dir):
                    if file.endswith('.json'):
                        number = file[:-5]  # Remove .json extension
                        file_path = os.path.join(session_dir, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                logs_data[session][number] = json.load(f)
                        except Exception as e:
                            log_error(f"Error reading log file {file_path}: {e}")
        else:
            # Get all sessions
            for session_name in os.listdir(base_log_dir):
                session_dir = os.path.join(base_log_dir, session_name)
                if os.path.isdir(session_dir):
                    logs_data[session_name] = {}
                    for file in os.listdir(session_dir):
                        if file.endswith('.json'):
                            number = file[:-5]  # Remove .json extension
                            file_path = os.path.join(session_dir, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    logs_data[session_name][number] = json.load(f)
                            except Exception as e:
                                log_error(f"Error reading log file {file_path}: {e}")
        
        return JSONResponse({"sessions": logs_data})
    except Exception as e:
        log_error(f"Error fetching local WA logs: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/test-notification")
async def test_notification(request: Request):
    """Send test notifications to specific channels with custom config"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        notification_type = data.get('type')
        message = data.get('message', 'Test notification from SentinelOne Monitor')
        config = data.get('config', {})
        
        if notification_type == 'telegram':
            # Test Telegram with specific config
            token = config.get('token')
            chat_id = config.get('chat_id')
            
            if not token or not chat_id:
                return JSONResponse({"success": False, "error": "Missing Telegram token or chat_id"})
            
            try:
                from notifier.telegram import TelegramNotifier
                tn = TelegramNotifier(token=token, chat_id=chat_id)
                tn.send(message)
                log_success(f"Telegram test sent to {chat_id}")
                return JSONResponse({"success": True, "message": "Telegram test notification sent"})
            except Exception as e:
                log_error(f"Telegram test failed: {e}")
                return JSONResponse({"success": False, "error": str(e)})
        
        elif notification_type == 'teams':
            # Test Teams with specific config
            webhook_url = config.get('webhook_url')
            
            if not webhook_url:
                return JSONResponse({"success": False, "error": "Missing Teams webhook URL"})
            
            try:
                from notifier.teams import TeamsNotifier
                tn = TeamsNotifier(webhook_url)
                tn.send(message)
                log_success("Teams test notification sent")
                return JSONResponse({"success": True, "message": "Teams test notification sent"})
            except Exception as e:
                log_error(f"Teams test failed: {e}")
                return JSONResponse({"success": False, "error": str(e)})
        
        elif notification_type == 'whatsapp':
            # Test WhatsApp with specific config
            gateway_url = config.get('gateway_url')
            session_name = config.get('session_name')
            recipient = config.get('recipient')
            
            if not gateway_url or not session_name or not recipient:
                return JSONResponse({"success": False, "error": "Missing WhatsApp configuration"})
            
            try:
                wb = get_whatsapp_bridge()
                wb.base_url = gateway_url
                wb.session = session_name
                result = wb.send_message(recipient, message)
                
                if result.get('success'):
                    log_success(f"WhatsApp test sent to {recipient}")
                    return JSONResponse({"success": True, "message": "WhatsApp test notification sent"})
                else:
                    return JSONResponse({"success": False, "error": result.get('error', 'Unknown error')})
            except Exception as e:
                log_error(f"WhatsApp test failed: {e}")
                return JSONResponse({"success": False, "error": str(e)})
        
        else:
            return JSONResponse({"success": False, "error": "Unknown notification type"})
        
    except Exception as e:
        log_error(f"Test notification error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/config/save")
async def save_config_api(request: Request):
    """Save configuration via API"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        cfg = safe_load_cfg()
        
        # Update configuration with new data
        if "sentinelone" in data:
            cfg["sentinelone"] = cfg.get("sentinelone", {})
            cfg["sentinelone"].update(data["sentinelone"])
        
        if "channels" in data:
            cfg["channels"] = cfg.get("channels", {})
            cfg["channels"].update(data["channels"])
        
        if "whatsapp_gateway" in data:
            cfg["whatsapp_gateway"] = cfg.get("whatsapp_gateway", {})
            cfg["whatsapp_gateway"].update(data["whatsapp_gateway"])
        
        if "polling" in data:
            cfg["polling"] = cfg.get("polling", {})
            cfg["polling"].update(data["polling"])
        
        if "backup" in data:
            cfg["backup"] = cfg.get("backup", {})
            cfg["backup"].update(data["backup"])
        
        save_config(cfg)
        log_success("Configuration saved via API")
        return JSONResponse({"success": True, "message": "Configuration saved successfully"})
    
    except Exception as e:
        log_error(f"Failed to save config via API: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/config")
async def get_config_api(request: Request):
    """Get current configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        cfg = safe_load_cfg()
        return JSONResponse({"success": True, "config": cfg})
    except Exception as e:
        log_error(f"Failed to get config: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/logs/{target}")
async def wa_logs_target(target: str, session: str = Query(None)):
    r = require_auth_redirect()
    if r:
        return r
    try:
        wb = get_whatsapp_bridge()
        result = wb.get_logs(target, session)
        log_success(f"WA logs retrieved for target {target} in session: {session or 'default'}")
        return JSONResponse(result)
    except Exception as e:
        log_error(f"Error fetching WA logs for target {target}: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# ------------- backups & logs viewer -------------
@app.get("/backups")
async def list_backups():
    r = require_auth_redirect()
    if r:
        return r
    files = []
    base = os.path.join("storage", "events")
    if os.path.isdir(base):
        for root, _, filenames in os.walk(base):
            for fn in filenames:
                if fn.startswith("."):
                    continue
                full = os.path.join(root, fn)
                mtime = os.path.getmtime(full)
                files.append({"path": full, "name": os.path.relpath(full, start="storage"), "mtime": mtime})
    files = sorted(files, key=lambda x: x["mtime"], reverse=True)
    return JSONResponse({"success": True, "files": files})

@app.get("/backups/download")
async def download_backup(path: str = Query(...)):
    r = require_auth_redirect()
    if r:
        return r
    safe_root = os.path.abspath("storage")
    requested = os.path.abspath(path)
    if not requested.startswith(safe_root):
        return JSONResponse({"success": False, "error": "invalid path"}, status_code=400)
    if not os.path.exists(requested):
        return JSONResponse({"success": False, "error": "file not found"}, status_code=404)
    mime, _ = mimetypes.guess_type(requested)
    return FileResponse(requested, media_type=mime or "application/octet-stream", filename=os.path.basename(requested))

@app.get("/logs")
async def list_logs():
    r = require_auth_redirect()
    if r:
        return r
    log_dir = "logs"
    files = []
    if os.path.isdir(log_dir):
        for fn in sorted(os.listdir(log_dir), reverse=True):
            full = os.path.join(log_dir, fn)
            if os.path.isfile(full):
                files.append({"name": fn, "path": full, "size": os.path.getsize(full)})
    return JSONResponse({"success": True, "files": files})

@app.get("/logs/download")
async def download_log(path: str = Query(...)):
    r = require_auth_redirect()
    if r:
        return r
    safe_root = os.path.abspath("logs")
    requested = os.path.abspath(path)
    if not requested.startswith(safe_root):
        return JSONResponse({"success": False, "error": "invalid path"}, status_code=400)
    if not os.path.exists(requested):
        return JSONResponse({"success": False, "error": "file not found"}, status_code=404)
    mime, _ = mimetypes.guess_type(requested)
    return FileResponse(requested, media_type=mime or "text/plain", filename=os.path.basename(requested))

# ------------- sentinel alert receiver -------------
@app.post("/send/alert")
async def receive_alert(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        log_error(f"Invalid JSON payload for /send/alert: {e}")
        return JSONResponse({"status": "error", "message": "invalid json"}, status_code=400)

    # save raw alert (JSON only, no JSONL)
    try:
        now = datetime.utcnow()
        dirpath = os.path.join("storage", "alerts")
        os.makedirs(dirpath, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(dirpath, f"alert_{ts}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_info(f"Saved incoming alert to {filepath}")
    except Exception as e:
        log_error(f"Failed saving alert: {e}")

    # dispatch notifier (best-effort)
    try:
        cfg = safe_load_cfg()
        
        # Extract alert data
        threat = (data.get("threatInfo") or {}).get("threatName") or data.get("threat") or "N/A"
        agent = (data.get("agentRealtimeInfo") or {}).get("agentComputerName") or (data.get("agentDetectionInfo") or {}).get("agentComputerName") or "Unknown"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Template variables
        template_vars = {
            "agent": agent,
            "threat": threat,
            "timestamp": timestamp,
            "file": filepath
        }
        
        def format_template(template, variables):
            """Replace template variables with actual values"""
            for key, value in variables.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))
            return template

        # WhatsApp notifications
        wa_settings = cfg.get("notifications", {}).get("whatsapp", {})
        if wa_settings.get("enabled"):
            session = wa_settings.get("session", "default")
            recipients = wa_settings.get("recipients", [])
            template = wa_settings.get("template", "🚨 *SentinelOne Alert*\n\n*Agent:* {{agent}}\n*Threat:* {{threat}}\n*Time:* {{timestamp}}\n*File:* {{file}}")
            
            message = format_template(template, template_vars)
            
            for recipient in recipients:
                try:
                    wb = get_whatsapp_bridge()
                    wb.session = session
                    result = wb.send_message(recipient, message)
                    if result.get('success'):
                        log_success(f"WA alert sent to {recipient} via session {session}")
                    else:
                        log_error(f"WA send failed to {recipient}: {result.get('message', 'Unknown error')}")
                except Exception as e:
                    log_error(f"Failed to send WA alert to {recipient}: {e}")

        # Telegram notifications
        tg_settings = cfg.get("notifications", {}).get("telegram", {})
        tg_legacy = cfg.get("channels", {}).get("telegram", {})
        
        if (tg_settings.get("enabled") or tg_legacy.get("enabled")) and tg_legacy.get("bot_token"):
            chat_id = tg_settings.get("chat_id") or tg_legacy.get("chat_id")
            template = tg_settings.get("template", "🚨 <b>SentinelOne Alert</b>\n\n<b>Agent:</b> {{agent}}\n<b>Threat:</b> {{threat}}\n<b>Time:</b> {{timestamp}}\n<b>File:</b> {{file}}")
            
            if chat_id:
                message = format_template(template, template_vars)
                try:
                    from notifier.telegram import TelegramNotifier
                    tn = TelegramNotifier(token=tg_legacy.get("bot_token"), chat_id=chat_id)
                    tn.send(message)
                    log_success(f"Telegram alert sent to {chat_id}")
                except Exception as e:
                    log_error(f"Failed to send Telegram alert: {e}")

        # Teams notifications
        teams_settings = cfg.get("notifications", {}).get("teams", {})
        teams_legacy = cfg.get("channels", {}).get("teams", {})
        
        if (teams_settings.get("enabled") or teams_legacy.get("enabled")):
            webhook_url = teams_settings.get("webhook_url") or teams_legacy.get("webhook_url")
            template = teams_settings.get("template", "🚨 SentinelOne Alert\n\nAgent: {{agent}}\nThreat: {{threat}}\nTime: {{timestamp}}\nFile: {{file}}")
            
            if webhook_url:
                message = format_template(template, template_vars)
                try:
                    from notifier.teams import TeamsNotifier
                    tn2 = TeamsNotifier(webhook_url)
                    tn2.send(message)
                    log_success("Teams alert sent")
                except Exception as e:
                    log_error(f"Failed to send Teams alert: {e}")
                    
        log_success("Alert notification dispatched (best-effort)")
    except Exception as e:
        log_error(f"Notifier dispatch error: {e}")

    return JSONResponse({"status": "ok", "file": filepath})

@app.post("/api/wa/config")
async def save_wa_config(request: Request):
    """Save WhatsApp configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        base_url = data.get('base_url', '')
        session_name = data.get('session_name', 'default')
        
        # Load current config
        cfg = safe_load_cfg()
        
        # Update WhatsApp config
        if 'whatsapp' not in cfg:
            cfg['whatsapp'] = {}
        
        cfg['whatsapp']['base_url'] = base_url
        cfg['whatsapp']['session_name'] = session_name
        
        # Save config
        save_config(cfg)
        log_success(f"WhatsApp config saved: {base_url}, session: {session_name}")
        
        return JSONResponse({"success": True, "message": "Configuration saved successfully"})
        
    except Exception as e:
        log_error(f"Failed to save WhatsApp config: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ------------- SentinelOne Advanced API Routes -------------
@app.get("/sentinelone-advanced", response_class=HTMLResponse)
async def sentinelone_advanced_page(request: Request):
    """SentinelOne Advanced Configuration Page"""
    r = require_auth_redirect()
    if r:
        return r
    cfg = safe_load_cfg()
    return templates.TemplateResponse("sentinelone-advanced.html", {"request": request, "config": cfg})

@app.post("/api/sentinel/test-endpoint")
async def test_sentinel_endpoint(request: Request):
    """Test SentinelOne API endpoint"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        endpoint = data.get('endpoint')
        
        cfg = safe_load_cfg()
        sentinel_cfg = cfg.get('sentinelone', {})
        base_url = sentinel_cfg.get('base_url')
        api_token = sentinel_cfg.get('api_token')
        
        if not base_url or not api_token:
            return JSONResponse({"success": False, "error": "SentinelOne configuration missing"})
        
        # Test the endpoint
        headers = {'Authorization': f'ApiToken {api_token}'}
        full_url = f'{base_url.rstrip("/")}{endpoint}'
        
        response = requests.get(full_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            log_success(f"SentinelOne endpoint test successful: {endpoint}")
            return JSONResponse({"success": True, "status_code": response.status_code})
        else:
            log_error(f"SentinelOne endpoint test failed: {endpoint} - {response.status_code}")
            return JSONResponse({"success": False, "error": f"HTTP {response.status_code}", "status_code": response.status_code})
            
    except Exception as e:
        log_error(f"SentinelOne endpoint test error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/sentinel/get-data")
async def get_sentinel_data(request: Request):
    """Get data from SentinelOne API endpoint"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        endpoint = data.get('endpoint')
        limit = data.get('limit', 10)
        
        cfg = safe_load_cfg()
        sentinel_cfg = cfg.get('sentinelone', {})
        base_url = sentinel_cfg.get('base_url')
        api_token = sentinel_cfg.get('api_token')
        
        if not base_url or not api_token:
            return JSONResponse({"success": False, "error": "SentinelOne configuration missing"})
        
        # Get data from endpoint
        headers = {'Authorization': f'ApiToken {api_token}'}
        full_url = f'{base_url.rstrip("/")}{endpoint}'
        params = {'limit': limit}
        
        response = requests.get(full_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            response_data = response.json()
            log_success(f"SentinelOne data retrieved from: {endpoint}")
            return JSONResponse({"success": True, "data": response_data})
        else:
            log_error(f"SentinelOne data retrieval failed: {endpoint} - {response.status_code}")
            return JSONResponse({"success": False, "error": f"HTTP {response.status_code}"})
            
    except Exception as e:
        log_error(f"SentinelOne data retrieval error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/sentinel/save-polling-config")
async def save_polling_config(request: Request):
    """Save SentinelOne polling configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        
        cfg = safe_load_cfg()
        if 'polling' not in cfg:
            cfg['polling'] = {}
        
        # Update polling configuration
        cfg['polling']['interval_seconds'] = int(data.get('interval', 60))
        cfg['polling']['timeout_seconds'] = int(data.get('timeout', 30))
        cfg['polling']['retry_attempts'] = int(data.get('retries', 3))
        cfg['polling']['endpoints'] = data.get('endpoints', [])
        
        # Parse filters JSON
        try:
            filters_str = data.get('filters', '{}')
            cfg['polling']['filters'] = json.loads(filters_str) if filters_str else {}
        except json.JSONDecodeError:
            cfg['polling']['filters'] = {}
        
        save_config(cfg)
        log_success("SentinelOne polling configuration saved")
        
        return JSONResponse({"success": True, "message": "Polling configuration saved successfully"})
        
    except Exception as e:
        log_error(f"Failed to save polling configuration: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/sentinel/test-polling")
async def test_polling_config(request: Request):
    """Test SentinelOne polling configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        
        cfg = safe_load_cfg()
        sentinel_cfg = cfg.get('sentinelone', {})
        base_url = sentinel_cfg.get('base_url')
        api_token = sentinel_cfg.get('api_token')
        
        if not base_url or not api_token:
            return JSONResponse({"success": False, "error": "SentinelOne configuration missing"})
        
        # Test polling with provided configuration
        headers = {'Authorization': f'ApiToken {api_token}'}
        timeout = int(data.get('timeout', 30))
        endpoints = data.get('endpoints', [])
        
        results = []
        for endpoint in endpoints:
            try:
                full_url = f'{base_url.rstrip("/")}{endpoint}'
                response = requests.get(full_url, headers=headers, timeout=timeout)
                
                results.append({
                    "endpoint": endpoint,
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                })
            except Exception as e:
                results.append({
                    "endpoint": endpoint,
                    "success": False,
                    "error": str(e)
                })
        
        success_count = sum(1 for r in results if r.get('success'))
        log_success(f"Polling test completed: {success_count}/{len(results)} endpoints successful")
        
        return JSONResponse({
            "success": success_count > 0,
            "message": f"Polling test completed: {success_count}/{len(results)} endpoints successful",
            "results": results
        })
        
    except Exception as e:
        log_error(f"Polling test error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/save-config")
async def save_backup_config(request: Request):
    """Save backup configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        
        cfg = safe_load_cfg()
        if 'backup' not in cfg:
            cfg['backup'] = {}
        
        # Update backup configuration
        cfg['backup']['frequency'] = data.get('frequency', 'daily')
        cfg['backup']['retention_days'] = int(data.get('retention', 30))
        cfg['backup']['compression'] = data.get('compression', 'gzip')
        cfg['backup']['location'] = data.get('location', './storage/backups')
        cfg['backup']['types'] = data.get('types', {})
        
        save_config(cfg)
        log_success("Backup configuration saved")
        
        return JSONResponse({"success": True, "message": "Backup configuration saved successfully"})
        
    except Exception as e:
        log_error(f"Failed to save backup configuration: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/run-now")
async def run_backup_now(request: Request):
    """Run backup immediately"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import subprocess
        import sys
        
        # Run backup process
        cmd = [sys.executable, 'run.py', '--backup']
        process = subprocess.Popen(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for process to complete (with timeout)
        try:
            stdout, stderr = process.communicate(timeout=60)
            
            if process.returncode == 0:
                log_success("Manual backup completed successfully")
                return JSONResponse({"success": True, "message": "Backup completed successfully"})
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                log_error(f"Manual backup failed: {error_msg}")
                return JSONResponse({"success": False, "error": f"Backup failed: {error_msg}"})
                
        except subprocess.TimeoutExpired:
            process.kill()
            log_error("Manual backup timed out")
            return JSONResponse({"success": False, "error": "Backup timed out"})
        
    except Exception as e:
        log_error(f"Failed to run backup: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/notifications/save-multi-config")
async def save_multi_notification_config(request: Request):
    """Save multi-session/multi-webhook notification configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        
        cfg = safe_load_cfg()
        if 'notifications' not in cfg:
            cfg['notifications'] = {}
        
        # Save Telegram configurations
        if 'telegram' in data:
            cfg['notifications']['telegram'] = {
                'enabled': data['telegram'].get('enabled', False),
                'configs': data['telegram'].get('configs', []),
                'default_config': data['telegram'].get('default_config', 0)
            }
        
        # Save Teams configurations
        if 'teams' in data:
            cfg['notifications']['teams'] = {
                'enabled': data['teams'].get('enabled', False),
                'configs': data['teams'].get('configs', []),
                'default_config': data['teams'].get('default_config', 0)
            }
        
        # Save WhatsApp configurations
        if 'whatsapp' in data:
            cfg['notifications']['whatsapp'] = {
                'enabled': data['whatsapp'].get('enabled', False),
                'gateway_url': data['whatsapp'].get('gateway_url', ''),
                'configs': data['whatsapp'].get('configs', []),
                'default_config': data['whatsapp'].get('default_config', 0)
            }
        
        save_config(cfg)
        log_success("Multi-notification configuration saved")
        
        return JSONResponse({"success": True, "message": "Notification configuration saved successfully"})
        
    except Exception as e:
        log_error(f"Failed to save notification configuration: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/notifications/test-config")
async def test_notification_config(request: Request):
    """Test specific notification configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        config_type = data.get('type')  # telegram, teams, whatsapp
        config_data = data.get('config')
        
        test_message = "🧪 Test notification from SentinelOne Monitor\n\nThis is a connection test."
        
        if config_type == 'telegram':
            bot_token = config_data.get('bot_token')
            chat_id = config_data.get('chat_id')
            
            if not bot_token or not chat_id:
                return JSONResponse({"success": False, "error": "Missing bot token or chat ID"})
            
            tn = TelegramNotifier(token=bot_token, chat_ids=[chat_id])
            result = tn.test_connection()
            
            if result:
                log_success(f"Telegram test successful for chat {chat_id}")
                return JSONResponse({"success": True, "message": "Telegram connection successful"})
            else:
                return JSONResponse({"success": False, "error": "Telegram connection failed"})
        
        elif config_type == 'teams':
            webhook_url = config_data.get('webhook_url')
            
            if not webhook_url:
                return JSONResponse({"success": False, "error": "Missing webhook URL"})
            
            tn = TeamsNotifier(webhook_urls=[webhook_url])
            result = tn.test_connection()
            
            if result:
                log_success("Teams test successful")
                return JSONResponse({"success": True, "message": "Teams connection successful"})
            else:
                return JSONResponse({"success": False, "error": "Teams connection failed"})
        
        elif config_type == 'whatsapp':
            gateway_url = config_data.get('gateway_url')
            session_name = config_data.get('session_name')
            
            if not gateway_url:
                return JSONResponse({"success": False, "error": "Missing gateway URL"})
            
            wb = WhatsAppBridge(gateway_url, session_name or 'default')
            result = wb.test_connection()
            
            if result.get('success'):
                log_success(f"WhatsApp test successful for session {session_name}")
                return JSONResponse({"success": True, "message": "WhatsApp connection successful"})
            else:
                return JSONResponse({"success": False, "error": result.get('error', 'WhatsApp connection failed')})
        
        else:
            return JSONResponse({"success": False, "error": "Unknown configuration type"})
        
    except Exception as e:
        log_error(f"Notification test error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# ------------- Polling and Backup Control API Routes -------------
@app.post("/api/polling/save-config")
async def save_polling_interval_config(request: Request):
    """Save polling interval configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        interval = int(data.get('interval', 60))
        interval_type = data.get('interval_type', 'minutes')
        
        # Convert to seconds
        if interval_type == 'hours':
            interval_seconds = interval * 3600
        else:  # minutes
            interval_seconds = interval * 60
        
        cfg = safe_load_cfg()
        if 'polling' not in cfg:
            cfg['polling'] = {}
        
        cfg['polling']['interval'] = interval
        cfg['polling']['interval_type'] = interval_type
        cfg['polling']['interval_seconds'] = interval_seconds
        
        save_config(cfg)
        log_success(f"Polling interval saved: {interval} {interval_type}")
        
        return JSONResponse({"success": True, "message": "Polling configuration saved"})
        
    except Exception as e:
        log_error(f"Failed to save polling config: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/polling/start")
async def start_polling_service(request: Request):
    """Start polling service"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import subprocess
        import sys
        
        # Start polling process
        cmd = [sys.executable, 'run.py', '--polling']
        subprocess.Popen(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        log_success("Polling service started")
        return JSONResponse({"success": True, "message": "Polling service started"})
        
    except Exception as e:
        log_error(f"Failed to start polling: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/polling/stop")
async def stop_polling_service(request: Request):
    """Stop polling service"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        try:
            import psutil
        except ImportError:
            return JSONResponse({"error": "psutil not installed"}, status_code=500)
        
        stopped = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'run.py --polling' in cmdline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    stopped = True
                    log_success(f"Stopped polling process (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not stopped:
            return JSONResponse({"error": "No polling process found"}, status_code=404)
        
        return JSONResponse({"success": True, "message": "Polling service stopped"})
        
    except Exception as e:
        log_error(f"Failed to stop polling: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/save-config")
async def save_backup_interval_config(request: Request):
    """Save backup interval configuration"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        interval = int(data.get('interval', 1))
        interval_type = data.get('interval_type', 'days')
        
        cfg = safe_load_cfg()
        if 'backup' not in cfg:
            cfg['backup'] = {}
        
        cfg['backup']['interval'] = interval
        cfg['backup']['interval_type'] = interval_type
        
        save_config(cfg)
        log_success(f"Backup interval saved: {interval} {interval_type}")
        
        return JSONResponse({"success": True, "message": "Backup configuration saved"})
        
    except Exception as e:
        log_error(f"Failed to save backup config: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/start")
async def start_backup_service(request: Request):
    """Start backup service"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import subprocess
        import sys
        
        # Start backup process
        cmd = [sys.executable, 'run.py', '--backup']
        subprocess.Popen(cmd, cwd='.', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        log_success("Backup service started")
        return JSONResponse({"success": True, "message": "Backup service started"})
        
    except Exception as e:
        log_error(f"Failed to start backup: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/stop")
async def stop_backup_service(request: Request):
    """Stop backup service"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        try:
            import psutil
        except ImportError:
            return JSONResponse({"error": "psutil not installed"}, status_code=500)
        
        stopped = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'run.py --backup' in cmdline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    stopped = True
                    log_success(f"Stopped backup process (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not stopped:
            return JSONResponse({"error": "No backup process found"}, status_code=404)
        
        return JSONResponse({"success": True, "message": "Backup service stopped"})
        
    except Exception as e:
        log_error(f"Failed to stop backup: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/backup/run-now")
async def run_backup_now(request: Request):
    """Run backup immediately"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import subprocess
        import sys
        
        # Run backup once
        cmd = [sys.executable, 'src/backup.py']
        result = subprocess.run(cmd, cwd='.', capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            log_success("Manual backup completed successfully")
            return JSONResponse({"success": True, "message": "Backup completed successfully", "output": result.stdout})
        else:
            log_error(f"Manual backup failed: {result.stderr}")
            return JSONResponse({"success": False, "error": result.stderr or "Backup failed"})
        
    except subprocess.TimeoutExpired:
        return JSONResponse({"success": False, "error": "Backup operation timed out"})
    except Exception as e:
        log_error(f"Failed to run manual backup: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/config/save")
async def save_system_config(request: Request):
    """Save system configuration with PIN validation"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        data = await request.json()
        current_pin = data.get('current_pin')
        new_pin = data.get('new_pin')
        confirm_pin = data.get('confirm_pin')
        base_url = data.get('base_url')
        port = data.get('port')
        
        cfg = safe_load_cfg()
        
        # Validate current PIN
        if current_pin != get_pin():
            return JSONResponse({"success": False, "error": "Current PIN is incorrect"})
        
        # Validate new PIN if provided
        if new_pin:
            if new_pin != confirm_pin:
                return JSONResponse({"success": False, "error": "New PIN confirmation does not match"})
            if len(new_pin) < 4:
                return JSONResponse({"success": False, "error": "PIN must be at least 4 characters"})
        
        # Update configuration
        if 'web' not in cfg:
            cfg['web'] = {}
        
        if base_url:
            cfg['web']['base_url'] = base_url
        if port:
            cfg['web']['port'] = int(port)
        if new_pin:
            cfg['web']['pin'] = new_pin
        
        save_config(cfg)
        log_success("System configuration updated")
        
        return JSONResponse({"success": True, "message": "Configuration saved successfully"})
        
    except Exception as e:
        log_error(f"Failed to save system config: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/logs/tree")
async def get_logs_tree(request: Request):
    """Get logs directory tree structure"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        
        def build_tree(path, base_path=""):
            tree = []
            if not os.path.exists(path):
                return tree
            
            for item in sorted(os.listdir(path)):
                if item.startswith('.'):
                    continue
                    
                item_path = os.path.join(path, item)
                relative_path = os.path.join(base_path, item) if base_path else item
                
                if os.path.isdir(item_path):
                    tree.append({
                        "name": item,
                        "type": "folder",
                        "path": relative_path,
                        "children": build_tree(item_path, relative_path)
                    })
                else:
                    stat = os.stat(item_path)
                    tree.append({
                        "name": item,
                        "type": "file",
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
            
            return tree
        
        logs_tree = build_tree("logs")
        return JSONResponse({"success": True, "tree": logs_tree})
        
    except Exception as e:
        log_error(f"Failed to get logs tree: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/storage/tree")
async def get_storage_tree(request: Request):
    """Get storage directory tree structure"""
    r = require_auth_redirect()
    if r:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    try:
        import os
        
        def build_tree(path, base_path=""):
            tree = []
            if not os.path.exists(path):
                return tree
            
            for item in sorted(os.listdir(path)):
                if item.startswith('.'):
                    continue
                    
                item_path = os.path.join(path, item)
                relative_path = os.path.join(base_path, item) if base_path else item
                
                if os.path.isdir(item_path):
                    tree.append({
                        "name": item,
                        "type": "folder",
                        "path": relative_path,
                        "children": build_tree(item_path, relative_path)
                    })
                else:
                    stat = os.stat(item_path)
                    tree.append({
                        "name": item,
                        "type": "file",
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
            
            return tree
        
        storage_tree = build_tree("storage")
        return JSONResponse({"success": True, "tree": storage_tree})
        
    except Exception as e:
        log_error(f"Failed to get storage tree: {e}")
        return JSONResponse({"success": False, "error": str(e)})
