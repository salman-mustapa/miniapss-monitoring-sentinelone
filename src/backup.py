# src/backup.py
import os
import json
import time
import threading
from datetime import datetime
from typing import Iterable

from src.logger import log_info, log_error, log_success

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "events")


def ensure_storage_dir():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        # create .gitkeep so folder exists in repo if needed
        gitkeep = os.path.join(os.path.dirname(STORAGE_DIR), ".gitkeep")
        try:
            open(gitkeep, "a").close()
        except Exception:
            pass


def daily_filename_for(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.utcnow()
    name = dt.strftime("%Y-%m-%d") + ".jsonl"
    return os.path.join(STORAGE_DIR, name)


def append_events(events: Iterable[dict]) -> int:
    """
    Append a list/iterable of event dictionaries to today's jsonl file.
    Returns number of events appended.
    """
    ensure_storage_dir()
    filepath = daily_filename_for()
    count = 0
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            for ev in events:
                # ensure serializable
                try:
                    line = json.dumps(ev, ensure_ascii=False)
                except Exception:
                    # fallback: convert non-serializable values
                    line = json.dumps(json.loads(json.dumps(ev, default=str)), ensure_ascii=False)
                f.write(line + "\n")
                count += 1
        log_info(f"Appended {count} event(s) to archive: {filepath}")
    except Exception as e:
        log_error(f"Failed to append events to {filepath}: {e}")
    return count


def read_events_for_date(date_str: str):
    """
    Read events for given date string 'YYYY-MM-DD' returning generator of dicts.
    """
    filepath = os.path.join(STORAGE_DIR, f"{date_str}.jsonl")
    if not os.path.exists(filepath):
        return []
    results = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    # skip invalid line
                    continue
    except Exception as e:
        log_error(f"Failed to read events from {filepath}: {e}")
    return results


class BackupManager:
    """Manages backup operations and scheduling"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 3600  # Default 1 hour
        
    def start_backup_service(self, interval_seconds=3600):
        """Start the backup service with specified interval"""
        if self.running:
            log_info("Backup service is already running")
            return
            
        self.interval = interval_seconds
        self.running = True
        self.thread = threading.Thread(target=self._backup_loop, daemon=True)
        self.thread.start()
        log_success(f"Backup service started with {interval_seconds}s interval")
        
    def stop_backup_service(self):
        """Stop the backup service"""
        if not self.running:
            log_info("Backup service is not running")
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log_success("Backup service stopped")
        
    def _backup_loop(self):
        """Main backup loop"""
        while self.running:
            try:
                self.run_backup()
                time.sleep(self.interval)
            except Exception as e:
                log_error(f"Backup loop error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
                
    def run_backup(self):
        """Run immediate backup operation"""
        try:
            log_info("Starting backup operation...")
            
            # Ensure storage directories exist
            ensure_storage_dir()
            
            # Create backup timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup logs
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            if os.path.exists(logs_dir):
                backup_logs_dir = os.path.join(os.path.dirname(STORAGE_DIR), "backup", "logs", timestamp)
                os.makedirs(backup_logs_dir, exist_ok=True)
                
                for log_file in os.listdir(logs_dir):
                    if log_file.endswith('.log'):
                        src = os.path.join(logs_dir, log_file)
                        dst = os.path.join(backup_logs_dir, log_file)
                        try:
                            import shutil
                            shutil.copy2(src, dst)
                        except Exception as e:
                            log_error(f"Failed to backup {log_file}: {e}")
            
            # Backup config
            config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.json")
            if os.path.exists(config_file):
                backup_config_dir = os.path.join(os.path.dirname(STORAGE_DIR), "backup", "config", timestamp)
                os.makedirs(backup_config_dir, exist_ok=True)
                
                try:
                    import shutil
                    shutil.copy2(config_file, os.path.join(backup_config_dir, "config.json"))
                except Exception as e:
                    log_error(f"Failed to backup config: {e}")
            
            log_success(f"Backup completed successfully at {timestamp}")
            
        except Exception as e:
            log_error(f"Backup operation failed: {e}")
            
    def get_status(self):
        """Get backup service status"""
        return {
            "running": self.running,
            "interval": self.interval,
            "thread_alive": self.thread.is_alive() if self.thread else False
        }
