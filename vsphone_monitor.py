#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSPhone Roblox Auto Monitor & Reconnect v2.0
Monitors Roblox app status and auto-restarts on crash/force-close
"""

import os
import sys
import json
import time
import hmac
import hashlib
import requests
import logging
import subprocess
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
RUNNING = True

# ============================================================================
# LOGGING SETUP
# ============================================================================
def setup_logging(config: Dict) -> logging.Logger:
    """Setup logging dengan rotating file handler"""
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("log_level", "INFO"))
    log_file = os.path.join(SCRIPT_DIR, log_config.get("log_file", "logs/monitor.log"))
    
    # Buat folder logs jika belum ada
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Setup logger
    logger = logging.getLogger("RobloxMonitor")
    logger.setLevel(log_level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler (rotating)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=log_config.get("log_max_size", 10485760),
        backupCount=log_config.get("log_backup_count", 5)
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# ============================================================================
# VSPHONE API CLIENT
# ============================================================================
class VSPhoneAPI:
    """Client untuk komunikasi dengan VSPhone API"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str, logger: logging.Logger):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'VSPhone-Monitor/2.0'
        })
    
    def _generate_signature(self, timestamp: str, data: str = "") -> str:
        """Generate HMAC-SHA256 signature"""
        message = f"{self.api_key}{timestamp}{data}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, endpoint: str, method: str = "POST", data: Dict = None) -> Optional[Dict]:
        """Make authenticated API request"""
        timestamp = str(int(time.time() * 1000))
        data_str = json.dumps(data) if data else ""
        signature = self._generate_signature(timestamp, data_str)
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-API-Key': self.api_key,
            'X-Timestamp': timestamp,
            'X-Signature': signature
        }
        
        try:
            if method == "POST":
                response = self.session.post(url, json=data, headers=headers, timeout=10)
            else:
                response = self.session.get(url, headers=headers, timeout=10)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API Request failed: {e}")
            return None
    
    def get_device_status(self, device_id: str) -> Optional[Dict]:
        """Get device status from API"""
        endpoint = "/padApi/padDetail"
        data = {"padId": device_id}
        return self._make_request(endpoint, "POST", data)
    
    def restart_device(self, device_id: str) -> bool:
        """Restart device via API"""
        endpoint = "/padApi/restart"
        data = {"padId": device_id}
        result = self._make_request(endpoint, "POST", data)
        return result is not None and result.get("code") == 0
    
    def get_sts_token(self, device_id: str) -> Optional[str]:
        """Get STS token for SDK connection"""
        endpoint = "/padApi/stsToken"
        data = {"padId": device_id}
        result = self._make_request(endpoint, "POST", data)
        if result and result.get("code") == 0:
            return result.get("data", {}).get("token")
        return None

# ============================================================================
# ADB CONTROLLER
# ============================================================================
class ADBController:
    """Controller untuk ADB commands"""
    
    def __init__(self, logger: logging.Logger, timeout: int = 10):
        self.logger = logger
        self.timeout = timeout
        self._check_adb()
    
    def _check_adb(self):
        """Check if ADB is installed"""
        try:
            subprocess.run(['adb', 'version'], capture_output=True, timeout=5)
            self.logger.info("✓ ADB detected and ready")
        except FileNotFoundError:
            self.logger.error("✗ ADB not found! Please install Android Debug Bridge")
            self.logger.error("  Termux: pkg install android-tools")
            self.logger.error("  Linux: sudo apt install adb")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"✗ ADB check failed: {e}")
            sys.exit(1)
    
    def _run_command(self, command: List[str]) -> Tuple[bool, str]:
        """Run ADB command and return result"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timeout: {' '.join(command)}")
            return False, ""
        except Exception as e:
            self.logger.error(f"Command failed: {e}")
            return False, ""
    
    def connect(self, device_ip: str) -> bool:
        """Connect to device via wireless ADB"""
        self.logger.info(f"Connecting to device: {device_ip}")
        success, output = self._run_command(['adb', 'connect', device_ip])
        
        if success and ('connected' in output.lower() or 'already connected' in output.lower()):
            self.logger.info(f"✓ Connected to {device_ip}")
            return True
        else:
            self.logger.error(f"✗ Failed to connect to {device_ip}: {output}")
            return False
    
    def is_app_running(self, device_ip: str, package: str) -> bool:
        """Check if app is running"""
        command = ['adb', '-s', device_ip, 'shell', f'pidof {package}']
        success, output = self._run_command(command)
        
        is_running = success and output and output.strip().isdigit()
        status = "RUNNING" if is_running else "NOT RUNNING"
        self.logger.debug(f"App {package} on {device_ip}: {status}")
        
        return is_running
    
    def force_stop_app(self, device_ip: str, package: str) -> bool:
        """Force stop app"""
        self.logger.info(f"Force stopping {package} on {device_ip}")
        command = ['adb', '-s', device_ip, 'shell', f'am force-stop {package}']
        success, _ = self._run_command(command)
        
        if success:
            self.logger.info(f"✓ App force-stopped")
            return True
        else:
            self.logger.error(f"✗ Failed to force-stop app")
            return False
    
    def start_app(self, device_ip: str, package: str, url: str) -> bool:
        """Start app with URL intent"""
        self.logger.info(f"Starting {package} with Roblox URL")
        command = [
            'adb', '-s', device_ip, 'shell',
            f'am start -a android.intent.action.VIEW -d "{url}" {package}'
        ]
        success, output = self._run_command(command)
        
        if success:
            self.logger.info(f"✓ App started successfully")
            return True
        else:
            self.logger.error(f"✗ Failed to start app: {output}")
            return False
    
    def restart_app(self, device_ip: str, package: str, url: str, delay: int = 5) -> bool:
        """Restart app (force-stop + delay + start)"""
        self.logger.info(f"=== Restarting {package} ===")
        
        # Step 1: Force stop
        if not self.force_stop_app(device_ip, package):
            return False
        
        # Step 2: Wait
        self.logger.info(f"Waiting {delay} seconds...")
        time.sleep(delay)
        
        # Step 3: Start with URL
        return self.start_app(device_ip, package, url)
    
    def get_device_info(self, device_ip: str) -> Dict:
        """Get device info"""
        info = {}
        
        # Android version
        success, output = self._run_command(['adb', '-s', device_ip, 'shell', 'getprop ro.build.version.release'])
        if success:
            info['android_version'] = output
        
        # Device model
        success, output = self._run_command(['adb', '-s', device_ip, 'shell', 'getprop ro.product.model'])
        if success:
            info['model'] = output
        
        return info

# ============================================================================
# STATISTICS TRACKER
# ============================================================================
class Statistics:
    """Track monitoring statistics"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.total_checks = 0
        self.total_restarts = 0
        self.devices_status = {}
    
    def increment_checks(self):
        self.total_checks += 1
    
    def increment_restarts(self, device_id: str):
        self.total_restarts += 1
        if device_id not in self.devices_status:
            self.devices_status[device_id] = {'restarts': 0}
        self.devices_status[device_id]['restarts'] += 1
    
    def get_summary(self) -> str:
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        summary = f"\n{'='*60}\n"
        summary += f"MONITORING STATISTICS\n"
        summary += f"{'='*60}\n"
        summary += f"Uptime: {hours}h {minutes}m {seconds}s\n"
        summary += f"Total Checks: {self.total_checks}\n"
        summary += f"Total Restarts: {self.total_restarts}\n"
        
        if self.devices_status:
            summary += f"\nPer-Device Restarts:\n"
            for device_id, status in self.devices_status.items():
                summary += f"  - {device_id}: {status['restarts']} restarts\n"
        
        summary += f"{'='*60}\n"
        return summary

# ============================================================================
# MAIN MONITOR CLASS
# ============================================================================
class RobloxMonitor:
    """Main monitoring class"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.logger = setup_logging(self.config)
        self.adb = ADBController(self.logger, self.config['monitoring'].get('adb_timeout', 10))
        self.stats = Statistics()
        self.api_clients = {}
        
        self._init_api_clients()
        self.logger.info("="*60)
        self.logger.info("VSPhone Roblox Monitor v2.0 - STARTED")
        self.logger.info("="*60)
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON"""
        if not os.path.exists(config_path):
            print(f"ERROR: Config file not found: {config_path}")
            sys.exit(1)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in config file: {e}")
            sys.exit(1)
    
    def _init_api_clients(self):
        """Initialize API clients for each account"""
        for account in self.config['accounts']:
            api_client = VSPhoneAPI(
                account['api_key'],
                account['api_secret'],
                account.get('api_base_url', 'https://api.vsphone.com'),
                self.logger
            )
            self.api_clients[account['name']] = api_client
            self.logger.info(f"✓ API client initialized: {account['name']}")
    
    def _check_device(self, account_name: str, device: Dict) -> bool:
        """Check single device and all its apps"""
        device_id = device['device_id']
        device_ip = device['device_ip']
        
        self.logger.info(f"\n--- Checking Device: {device_id} ({device_ip}) ---")
        
        # Connect to device
        if not self.adb.connect(device_ip):
            self.logger.error(f"Cannot connect to device {device_ip}")
            return False
        
        # Check each app
        all_ok = True
        for app in device['apps']:
            package = app['package']
            roblox_url = app['roblox_url']
            game_name = app.get('game_name', 'Unknown')
            
            self.logger.info(f"Checking app: {game_name} ({package})")
            
            # Check if running
            if self.adb.is_app_running(device_ip, package):
                self.logger.info(f"✓ App is running normally")
            else:
                self.logger.warning(f"✗ App is NOT running - initiating restart")
                
                # Restart app
                restart_delay = self.config['monitoring'].get('restart_delay', 5)
                if self.adb.restart_app(device_ip, package, roblox_url, restart_delay):
                    self.logger.info(f"✓ App restarted successfully")
                    self.stats.increment_restarts(device_id)
                else:
                    self.logger.error(f"✗ Failed to restart app")
                    all_ok = False
        
        return all_ok
    
    def monitor_loop(self):
        """Main monitoring loop"""
        check_interval = self.config['monitoring'].get('check_interval', 60)
        
        self.logger.info(f"Starting monitoring loop (check every {check_interval}s)")
        self.logger.info("Press Ctrl+C to stop\n")
        
        while RUNNING:
            try:
                self.stats.increment_checks()
                self.logger.info(f"\n{'#'*60}")
                self.logger.info(f"CHECK #{self.stats.total_checks} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"{'#'*60}")
                
                # Loop through all accounts
                for account in self.config['accounts']:
                    account_name = account['name']
                    self.logger.info(f"\n[ACCOUNT: {account_name}]")
                    
                    # Loop through all devices
                    for device in account['devices']:
                        try:
                            self._check_device(account_name, device)
                        except Exception as e:
                            self.logger.error(f"Error checking device {device['device_id']}: {e}", exc_info=True)
                
                # Show statistics
                if self.stats.total_checks % 10 == 0:
                    self.logger.info(self.stats.get_summary())
                
                # Wait for next check
                self.logger.info(f"\n✓ Check complete. Next check in {check_interval} seconds...")
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("\n\nReceived shutdown signal...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitor loop: {e}", exc_info=True)
                time.sleep(10)
    
    def shutdown(self):
        """Clean shutdown"""
        self.logger.info("\n" + "="*60)
        self.logger.info("SHUTTING DOWN")
        self.logger.info("="*60)
        self.logger.info(self.stats.get_summary())
        self.logger.info("Monitor stopped. Goodbye!")

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================
def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global RUNNING
    RUNNING = False

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    """Main entry point"""
    global RUNNING
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize monitor
    try:
        monitor = RobloxMonitor(CONFIG_FILE)
    except Exception as e:
        print(f"FATAL ERROR: Failed to initialize monitor: {e}")
        sys.exit(1)
    
    # Run monitoring loop
    try:
        monitor.monitor_loop()
    finally:
        monitor.shutdown()

if __name__ == "__main__":
    main()