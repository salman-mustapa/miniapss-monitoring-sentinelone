# run.py - SentinelOne Monitor v2.0
import argparse
import sys
import time
import signal
from datetime import datetime
from src.main import start_app
import setup_config
from src.config import load_config
from src.sentinel_api import SentinelAPI
from src.logger import log_info, log_success, log_error
from src.backup import BackupManager

def signal_handler(sig, frame):
    """Handle graceful shutdown"""
    log_info("Received shutdown signal, stopping gracefully...")
    sys.exit(0)

def run_polling_with_monitoring():
    """Enhanced polling with better error handling and monitoring"""
    cfg = load_config()
    if not cfg:
        log_error("Config not found — run `python run.py --setup` first")
        return False
    
    log_success("Starting SentinelOne polling service...")
    
    try:
        api = SentinelAPI(cfg)
        interval = cfg.get("polling", {}).get("interval_seconds", 60)
        
        log_info(f"Polling interval: {interval} seconds")
        log_info("Press Ctrl+C to stop polling")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start polling with enhanced monitoring
        api.start_polling(interval=interval)
        
    except KeyboardInterrupt:
        log_info("Polling stopped by user")
        return True
    except Exception as e:
        log_error(f"Polling error: {e}")
        return False

def run_backup_with_monitoring():
    """Enhanced backup with better scheduling and monitoring"""
    cfg = load_config()
    if not cfg:
        log_error("Config not found — run `python run.py --setup` first")
        return False
    
    log_success("Starting backup service...")
    
    try:
        backup_mgr = BackupManager(cfg)
        frequency = cfg.get("backup", {}).get("frequency", "daily")
        
        log_info(f"Backup frequency: {frequency}")
        log_info("Press Ctrl+C to stop backup service")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start backup scheduler
        backup_mgr.start_scheduler(frequency)
        
    except KeyboardInterrupt:
        log_info("Backup service stopped by user")
        return True
    except Exception as e:
        log_error(f"Backup error: {e}")
        return False

def print_banner():
    """Print application banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                 SENTINELONE MONITOR v2.0                  ║
    ║                Advanced Security Monitoring                ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

if __name__ == "__main__":
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="SentinelOne Monitor v2.0 - Advanced Security Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --setup          # Interactive setup wizard
  python run.py --web            # Start web dashboard
  python run.py --polling        # Start automated polling
  python run.py --backup         # Start backup service
  
PM2 Usage:
  pm2 start ecosystem.config.js  # Start all services
  pm2 status                     # Check service status
  pm2 logs                       # View logs
        """
    )
    
    parser.add_argument("--setup", action="store_true", 
                       help="Run interactive setup configuration wizard")
    parser.add_argument("--web", action="store_true", 
                       help="Start web dashboard server")
    parser.add_argument("--polling", action="store_true", 
                       help="Start SentinelOne automated polling service")
    parser.add_argument("--backup", action="store_true", 
                       help="Start automated backup service")
    parser.add_argument("--version", action="version", version="SentinelOne Monitor v2.0")
    
    args = parser.parse_args()

    if args.setup:
        log_info("Starting setup wizard...")
        if hasattr(setup_config, "run_setup"):
            try:
                setup_config.run_setup()
                log_success("Setup completed successfully")
            except Exception as e:
                log_error(f"Setup failed: {e}")
                sys.exit(1)
        else:
            log_error("Setup wizard not available (setup_config.run_setup missing)")
            sys.exit(1)
            
    elif args.web:
        log_info("Starting web dashboard...")
        try:
            start_app()
        except Exception as e:
            log_error(f"Web server failed to start: {e}")
            sys.exit(1)
            
    elif args.polling:
        success = run_polling_with_monitoring()
        sys.exit(0 if success else 1)
        
    elif args.backup:
        success = run_backup_with_monitoring()
        sys.exit(0 if success else 1)
        
    else:
        parser.print_help()
        print("\n" + "="*60)
        print("QUICK START:")
        print("1. python run.py --setup    # Configure the system")
        print("2. python run.py --web      # Start web interface")
        print("3. pm2 start ecosystem.config.js  # Start all services")
        print("="*60)
