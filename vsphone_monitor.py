#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSPhone Multi-Account Monitor v1.1 - FIXED VERSION
24/7 Automatic Device & App Management
Fixed: API 405 Error with GET/POST fallback
"""

# ========== IMPORTS ==========
import requests
import hashlib
import hmac
import json
import time
import subprocess
import sys
import os
import logging
import signal
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

# Colorama for colored output (with fallback)
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    class Fore:
        CYAN = GREEN = YELLOW = RED = MAGENTA = BLUE = WHITE = RESET = ''
    class Style:
        RESET_ALL = BRIGHT = ''
    HAS_COLOR = False

# ========== CONFIGURATION ==========
VERSION = "1.1.0"
CONFIG_FILE = "account.json"  # Changed to match your repo
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "vsphone_monitor.log")
STATS_FILE = os.path.join(LOG_DIR, "monitor_stats.json")
PID_FILE = "monitor.pid"

# ========== SETUP LOGGING ==========
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ========== SIGNAL HANDLER ==========
def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("\n🛑 Received stop signal, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ========== VSPHONE API CLIENT (FIXED) ==========
class VSPhoneAPI:
    """VSPhone API Client with HMAC-SHA256 signature authentication - FIXED VERSION"""
    
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = "api.vsphone.com"
        self.base_url = f"https://{self.host}"
        logger.debug(f"Initialized VSPhoneAPI for key: {api_key[:8]}...")
    
    def _sign_request(self, method, uri, query_params="", body=""):
        """
        Generate HMAC-SHA256 signature for VSPhone API request
        FIXED: Support both GET and POST methods
        """
        # Generate timestamp
        now = datetime.now(timezone.utc)
        x_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')
        
        # Calculate body hash
        if method == "GET" or body == "":
            body_str = ""
        else:
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
        
        content_sha256 = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
        
        # Build canonical headers (sorted)
        canonical_headers = {
            'content-type': 'application/json',
            'host': self.host,
            'x-content-sha256': content_sha256,
            'x-date': x_date
        }
        
        canonical_header_str = '\n'.join([f"{k}:{v}" for k, v in sorted(canonical_headers.items())])
        signed_headers = ';'.join(sorted(canonical_headers.keys()))
        
        # Build canonical request
        canonical_request = f"{method}\n{uri}\n{query_params}\n{canonical_header_str}\n\n{signed_headers}\n{content_sha256}"
        
        # Create string to sign
        algorithm = "SDK-HMAC-SHA256"
        credential_scope = f"{date_stamp}/vsphone/sdk_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        string_to_sign = f"{algorithm}\n{x_date}\n{credential_scope}\n{canonical_request_hash}"
        
        # Calculate signature with layered HMAC
        k_date = hmac.new(
            f"SDK{self.api_secret}".encode('utf-8'),
            date_stamp.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        k_service = hmac.new(
            k_date,
            "vsphone".encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        k_signing = hmac.new(
            k_service,
            "sdk_request".encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        signature = hmac.new(
            k_signing,
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Build authorization header
        authorization = f"{algorithm} Credential={self.api_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        # Return complete headers
        return {
            'Content-Type': 'application/json',
            'Host': self.host,
            'X-Content-Sha256': content_sha256,
            'X-Date': x_date,
            'Authorization': authorization
        }
    
    def get_devices(self):
        """
        Get all devices for this account
        FIXED: Try multiple methods to avoid 405 error
        """
        uri = "/api/v1/phone/list"
        
        # Method 1: Try POST with empty body (original method)
        try:
            logger.debug("Trying POST request to get devices...")
            body = {}
            headers = self._sign_request("POST", uri, body=body)
            
            response = requests.post(
                f"{self.base_url}{uri}",
                headers=headers,
                json=body,
                timeout=15
            )
            
            # If success, return data
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"POST success: Got {len(data.get('data', {}).get('list', []))} devices")
                return data
            
            # If 405, try other methods
            if response.status_code == 405:
                logger.warning(f"POST returned 405, trying alternative methods...")
            else:
                logger.error(f"POST failed with status {response.status_code}: {response.text}")
        
        except Exception as e:
            logger.error(f"POST request error: {e}")
        
        # Method 2: Try GET request
        try:
            logger.debug("Trying GET request to get devices...")
            headers = self._sign_request("GET", uri, body="")
            
            response = requests.get(
                f"{self.base_url}{uri}",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"GET success: Got {len(data.get('data', {}).get('list', []))} devices")
                return data
            else:
                logger.error(f"GET failed with status {response.status_code}: {response.text}")
        
        except Exception as e:
            logger.error(f"GET request error: {e}")
        
        # Method 3: Try POST with explicit empty string body
        try:
            logger.debug("Trying POST with empty string body...")
            headers = self._sign_request("POST", uri, body="")
            
            response = requests.post(
                f"{self.base_url}{uri}",
                headers=headers,
                data="",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"POST (empty string) success: Got {len(data.get('data', {}).get('list', []))} devices")
                return data
            else:
                logger.error(f"POST (empty string) failed with status {response.status_code}: {response.text}")
        
        except Exception as e:
            logger.error(f"POST (empty string) error: {e}")
        
        # All methods failed
        logger.error("❌ All API request methods failed!")
        logger.error("Please check:")
        logger.error("1. API Key and Secret are correct")
        logger.error("2. Account has active subscription")
        logger.error("3. Network connection is working")
        logger.error("4. VSPhone API is not down")
        
        return None
    
    def get_device_detail(self, device_id):
        """Get specific device details"""
        uri = "/api/v1/phone/detail"
        body = {"phoneId": device_id}
        headers = self._sign_request("POST", uri, body=body)
        
        try:
            response = requests.post(
                f"{self.base_url}{uri}",
                headers=headers,
                json=body,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting device detail {device_id}: {e}")
            return None

# ========== DEVICE CONTROLLER ==========
class DeviceController:
    """Control Android devices via ADB wireless"""
    
    @staticmethod
    def extract_roblox_code(url_or_code):
        """Extract Roblox share code from URL or return code directly"""
        if not url_or_code:
            return None
        
        url_or_code = str(url_or_code).strip()
        
        if url_or_code.startswith('http'):
            try:
                parsed = urlparse(url_or_code)
                params = parse_qs(parsed.query)
                code = params.get('code', [None])[0]
                return code
            except Exception as e:
                logger.error(f"Failed to parse URL: {e}")
                return None
        
        return url_or_code
    
    @staticmethod
    def build_roblox_url(url_or_code):
        """Build full Roblox URL"""
        if not url_or_code:
            return None
        
        url_or_code = str(url_or_code).strip()
        
        if url_or_code.startswith('http'):
            return url_or_code
        
        return f"https://www.roblox.com/share?code={url_or_code}&type=Server"
    
    @staticmethod
    def connect_device(ip):
        """Connect to device via ADB wireless"""
        try:
            cmd = f"adb connect {ip}:5555"
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                timeout=15,
                text=True
            )
            output = result.stdout.lower()
            is_connected = "connected" in output or "already connected" in output
            
            if is_connected:
                logger.debug(f"ADB connected to {ip}")
            else:
                logger.warning(f"Failed to connect to {ip}: {result.stdout}")
            
            return is_connected
        except subprocess.TimeoutExpired:
            logger.error(f"ADB connect timeout for {ip}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to {ip}: {e}")
            return False
    
    @staticmethod
    def check_app_running(ip, package):
        """Check if app is running on device"""
        try:
            cmd = f"adb -s {ip}:5555 shell \"ps | grep {package}\""
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                timeout=10,
                text=True
            )
            is_running = package in result.stdout
            logger.debug(f"App {package} on {ip}: {'RUNNING' if is_running else 'NOT RUNNING'}")
            return is_running
        except subprocess.TimeoutExpired:
            logger.error(f"Check app timeout for {package} on {ip}")
            return False
        except Exception as e:
            logger.error(f"Error checking app {package} on {ip}: {e}")
            return False
    
    @staticmethod
    def kill_app(ip, package):
        """Force stop app on device"""
        try:
            cmd = f"adb -s {ip}:5555 shell \"am force-stop {package}\""
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                timeout=10,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✓ Killed {package} on {ip}")
                return True
            else:
                logger.error(f"Failed to kill {package}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error killing {package} on {ip}: {e}")
            return False
    
    @staticmethod
    def start_app(ip, package, url_or_code):
        """Start Roblox app with URL or code"""
        try:
            roblox_url = DeviceController.build_roblox_url(url_or_code)
            
            if not roblox_url:
                logger.error(f"Invalid Roblox URL/code: {url_or_code}")
                return False
            
            cmd = f"adb -s {ip}:5555 shell \"am start -a android.intent.action.VIEW -d '{roblox_url}' {package}\""
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                timeout=10,
                text=True
            )
            
            if result.returncode == 0:
                code = DeviceController.extract_roblox_code(url_or_code)
                logger.info(f"✓ Started {package} on {ip} (code: {code[:8] if code else 'N/A'}...)")
                return True
            else:
                logger.error(f"Failed to start {package}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting {package} on {ip}: {e}")
            return False
    
    @staticmethod
    def restart_app(ip, package, url_or_code, delay=5):
        """Restart app: kill → wait → start"""
        logger.info(f"🔄 Restarting {package} on {ip}")
        
        DeviceController.kill_app(ip, package)
        time.sleep(delay)
        success = DeviceController.start_app(ip, package, url_or_code)
        
        return success

# ========== MONITOR ==========
class VSPhoneMonitor:
    """Main monitoring system"""
    
    def __init__(self, config_file=CONFIG_FILE):
        logger.info(f"Loading configuration from {config_file}...")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        
        # Initialize accounts
        self.accounts = []
        for acc_config in self.config.get('accounts', []):
            account = {
                'name': acc_config['name'],
                'api': VSPhoneAPI(acc_config['api_key'], acc_config['api_secret']),
                'devices': acc_config.get('devices', [])
            }
            self.accounts.append(account)
            logger.info(f"Loaded account: {account['name']} with {len(account['devices'])} devices")
        
        # Monitoring config
        self.monitoring_config = self.config.get('monitoring', {})
        self.check_interval = self.monitoring_config.get('check_interval', 30)
        self.restart_delay = self.monitoring_config.get('restart_delay', 5)
        self.max_restart_attempts = self.monitoring_config.get('max_restart_attempts', 3)
        
        # Statistics
        self.stats = self.load_stats()
        
        logger.info(f"Monitor initialized with {len(self.accounts)} accounts")
    
    def load_stats(self):
        """Load statistics from file"""
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load stats: {e}")
        
        return {
            'total_checks': 0,
            'total_restarts': 0,
            'last_check': None,
            'started_at': datetime.now().isoformat()
        }
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def print_banner(self):
        """Print startup banner"""
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║          VSPhone Multi-Account Monitor v{VERSION}                ║
║          24/7 Automatic Device & App Management              ║
║                    FIXED: API 405 Error                      ║
╚══════════════════════════════════════════════════════════════╝

📊 Accounts: {len(self.accounts)}
📱 Total devices: {sum(len(acc['devices']) for acc in self.accounts)}
⏱️  Check interval: {self.check_interval}s
🔄 Restart delay: {self.restart_delay}s
📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📝 Logs: {LOG_FILE}
"""
        if HAS_COLOR:
            print(Fore.CYAN + Style.BRIGHT + banner + Style.RESET_ALL)
        else:
            print(banner)
    
    def check_account_devices(self, account):
        """Check all devices for one account"""
        account_name = account['name']
        api = account['api']
        
        logger.info(f"Checking account: {account_name}")
        
        # Get device list from VSPhone API
        api_response = api.get_devices()
        
        if not api_response or 'data' not in api_response:
            logger.error(f"{account_name}: Failed to get device list from API")
            logger.warning(f"{account_name}: Will still try to check devices via ADB...")
            # Continue to check devices via ADB even if API fails
            for device_config in account['devices']:
                device_ip = device_config.get('device_ip')
                if device_ip:
                    self.check_device_apps(account_name, device_ip, device_config.get('apps', []))
            return
        
        api_devices = api_response.get('data', {}).get('list', [])
        
        # Check each configured device
        for device_config in account['devices']:
            device_id = device_config.get('device_id')
            device_name = device_config.get('device_name')
            device_ip = device_config.get('device_ip')
            
            if not device_ip:
                logger.error(f"Missing device_ip for {device_name or device_id}")
                continue
            
            # Find device in API response
            api_device = None
            for d in api_devices:
                d_id = d.get('phoneId') or d.get('id')
                d_name = d.get('phoneName') or d.get('name')
                
                if (device_id and d_id == device_id) or (device_name and d_name == device_name):
                    api_device = d
                    break
            
            if not api_device:
                logger.warning(f"{account_name} - {device_name or device_id}: Device not found in API")
                self.check_device_apps(account_name, device_ip, device_config.get('apps', []))
                continue
            
            # Check device online status
            is_online = api_device.get('online') == 1 or api_device.get('status') == 'online'
            
            display_name = device_name or api_device.get('phoneName') or device_id
            status_icon = "🟢" if is_online else "🔴"
            status_color = Fore.GREEN if is_online else Fore.RED
            
            if HAS_COLOR:
                print(f"{status_color}{status_icon} {account_name} - {display_name}: {'ONLINE' if is_online else 'OFFLINE'}{Style.RESET_ALL}")
            else:
                print(f"{status_icon} {account_name} - {display_name}: {'ONLINE' if is_online else 'OFFLINE'}")
            
            if not is_online:
                logger.warning(f"{account_name} - {display_name}: Device offline, skipping app check")
                continue
            
            # Check and restart apps if needed
            self.check_device_apps(account_name, device_ip, device_config.get('apps', []))
    
    def check_device_apps(self, account_name, device_ip, apps):
        """Check all apps on a device"""
        
        if not apps:
            logger.debug(f"No apps configured for {device_ip}")
            return
        
        # Connect to device first
        if not DeviceController.connect_device(device_ip):
            logger.error(f"{account_name} - {device_ip}: Failed to connect via ADB")
            return
        
        # Check each app
        for app in apps:
            package = app.get('package')
            url_or_code = app.get('roblox_url') or app.get('share_code')
            game_name = app.get('game_name', package)
            
            if not package:
                logger.error(f"Missing package name in app config")
                continue
            
            if not url_or_code:
                logger.error(f"Missing roblox_url/share_code for {package}")
                continue
            
            # Check if app is running
            is_running = DeviceController.check_app_running(device_ip, package)
            
            if not is_running:
                if HAS_COLOR:
                    print(f"  {Fore.YELLOW}⚠️  {game_name} ({package}): NOT RUNNING{Style.RESET_ALL}")
                else:
                    print(f"  ⚠️  {game_name} ({package}): NOT RUNNING")
                
                logger.warning(f"{account_name} - {device_ip} - {game_name}: App stopped, restarting...")
                
                success = DeviceController.restart_app(
                    device_ip, 
                    package, 
                    url_or_code, 
                    delay=self.restart_delay
                )
                
                if success:
                    self.stats['total_restarts'] += 1
                    if HAS_COLOR:
                        print(f"  {Fore.GREEN}✅ {game_name}: RESTARTED{Style.RESET_ALL}")
                    else:
                        print(f"  ✅ {game_name}: RESTARTED")
                else:
                    if HAS_COLOR:
                        print(f"  {Fore.RED}❌ {game_name}: RESTART FAILED{Style.RESET_ALL}")
                    else:
                        print(f"  ❌ {game_name}: RESTART FAILED")
            else:
                if HAS_COLOR:
                    print(f"  {Fore.GREEN}✅ {game_name} ({package}): RUNNING{Style.RESET_ALL}")
                else:
                    print(f"  ✅ {game_name} ({package}): RUNNING")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.print_banner()
        
        logger.info("Starting monitoring loop...")
        
        while True:
            try:
                separator = "=" * 70
                print(f"\n{separator}")
                print(f"🔍 Checking all accounts - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{separator}\n")
                
                # Check all accounts in parallel
                with ThreadPoolExecutor(max_workers=min(len(self.accounts), 4)) as executor:
                    futures = [
                        executor.submit(self.check_account_devices, account)
                        for account in self.accounts
                    ]
                    
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.error(f"Error in account check: {e}", exc_info=True)
                
                # Update statistics
                self.stats['total_checks'] += 1
                self.stats['last_check'] = datetime.now().isoformat()
                self.save_stats()
                
                # Print summary
                print(f"\n{separator}")
                print(f"📈 Total checks: {self.stats['total_checks']} | Total restarts: {self.stats['total_restarts']}")
                print(f"⏳ Next check in {self.check_interval} seconds...")
                print(f"{separator}")
                
                # Wait for next interval
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                logger.info("Waiting 10 seconds before retry...")
                time.sleep(10)
        
        logger.info("Monitor stopped")

# ========== MAIN ENTRY POINT ==========
def main():
    """Main entry point"""
    
    # Write PID file
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"Failed to write PID file: {e}")
    
    try:
        monitor = VSPhoneMonitor(CONFIG_FILE)
        monitor.monitor_loop()
    except FileNotFoundError:
        logger.error(f"❌ Config file not found: {CONFIG_FILE}")
        logger.error(f"Please create {CONFIG_FILE} with your VSPhone account details")
        return 1
    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")
        return 0
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1
    finally:
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass
    
    return 0

if __name__ == "__main__":
    sys.exit(main())