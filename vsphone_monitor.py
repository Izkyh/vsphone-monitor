#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSPhone Auto Reconnect v2.0 - COMPLETELY FIXED
Automatic Roblox app monitoring and restart system
"""

import requests
import hashlib
import hmac
import json
import time
import subprocess
import sys
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
import traceback

# ========== CONFIGURATION ==========
VERSION = "2.0.0"
CONFIG_FILE = "config.json"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ========== LOGGING SETUP ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "monitor.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========== VSPHONE API CLIENT (FIXED) ==========
class VSPhoneAPI:
    """VSPhone API Client with proper HMAC-SHA256 authentication"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = "api.vsphone.com"
        self.base_url = f"https://{self.host}"
        logger.info(f"✓ API Client initialized for key: {api_key[:10]}...")
    
    def _generate_signature(self, method: str, uri: str, body: str = "") -> Dict[str, str]:
        """Generate HMAC-SHA256 signature for API request"""
        try:
            # Generate timestamp
            now = datetime.now(timezone.utc)
            x_date = now.strftime('%Y%m%dT%H%M%SZ')
            date_stamp = now.strftime('%Y%m%d')
            
            # Calculate body hash
            content_sha256 = hashlib.sha256(body.encode('utf-8')).hexdigest()
            
            # Build canonical headers
            canonical_headers = [
                f"content-type:application/json",
                f"host:{self.host}",
                f"x-content-sha256:{content_sha256}",
                f"x-date:{x_date}"
            ]
            canonical_header_str = '\n'.join(canonical_headers)
            signed_headers = "content-type;host;x-content-sha256;x-date"
            
            # Build canonical request
            canonical_request = f"{method}\n{uri}\n\n{canonical_header_str}\n\n{signed_headers}\n{content_sha256}"
            
            # Create string to sign
            algorithm = "SDK-HMAC-SHA256"
            credential_scope = f"{date_stamp}/vsphone/sdk_request"
            canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
            string_to_sign = f"{algorithm}\n{x_date}\n{credential_scope}\n{canonical_request_hash}"
            
            # Calculate signature
            k_date = hmac.new(
                f"SDK{self.api_secret}".encode('utf-8'),
                date_stamp.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            k_service = hmac.new(k_date, "vsphone".encode('utf-8'), hashlib.sha256).digest()
            k_signing = hmac.new(k_service, "sdk_request".encode('utf-8'), hashlib.sha256).digest()
            signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            
            # Build authorization header
            authorization = f"{algorithm} Credential={self.api_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
            
            return {
                'Content-Type': 'application/json',
                'Host': self.host,
                'X-Content-Sha256': content_sha256,
                'X-Date': x_date,
                'Authorization': authorization
            }
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            raise
    
    def get_device_list(self) -> Optional[List[Dict]]:
        """Get list of all devices"""
        uri = "/api/v1/phone/list"
        
        # Try POST first (as per API doc)
        try:
            body = json.dumps({})
            headers = self._generate_signature("POST", uri, body)
            
            response = requests.post(
                f"{self.base_url}{uri}",
                headers=headers,
                data=body,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    devices = data.get('data', {}).get('list', [])
                    logger.info(f"✓ Retrieved {len(devices)} devices from API")
                    return devices
                else:
                    logger.error(f"API returned error code: {data.get('code')} - {data.get('msg')}")
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Error fetching device list: {e}")
            logger.debug(traceback.format_exc())
        
        return None
    
    def get_device_detail(self, phone_id: str) -> Optional[Dict]:
        """Get detailed information about a specific device"""
        uri = "/api/v1/phone/detail"
        
        try:
            body = json.dumps({"phoneId": phone_id})
            headers = self._generate_signature("POST", uri, body)
            
            response = requests.post(
                f"{self.base_url}{uri}",
                headers=headers,
                data=body,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    return data.get('data')
            
            logger.error(f"Failed to get device detail: {response.text}")
        
        except Exception as e:
            logger.error(f"Error getting device detail: {e}")
        
        return None

# ========== ADB CONTROLLER ==========
class ADBController:
    """Control Android devices via ADB"""
    
    @staticmethod
    def check_adb_installed() -> bool:
        """Check if ADB is installed"""
        try:
            result = subprocess.run(['adb', 'version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def connect(ip: str, port: int = 5555) -> bool:
        """Connect to device via ADB"""
        try:
            cmd = f"adb connect {ip}:{port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15, text=True)
            
            output = result.stdout.lower()
            success = "connected" in output or "already connected" in output
            
            if success:
                logger.debug(f"✓ ADB connected to {ip}:{port}")
            else:
                logger.warning(f"Failed to connect ADB to {ip}:{port}: {result.stdout}")
            
            return success
        except Exception as e:
            logger.error(f"Error connecting ADB to {ip}:{port}: {e}")
            return False
    
    @staticmethod
    def is_app_running(ip: str, package: str, port: int = 5555) -> bool:
        """Check if app is running on device"""
        try:
            cmd = f'adb -s {ip}:{port} shell "pidof {package}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, text=True)
            
            # If pidof returns a number, app is running
            is_running = result.returncode == 0 and result.stdout.strip().isdigit()
            logger.debug(f"App {package} on {ip}: {'RUNNING' if is_running else 'STOPPED'}")
            return is_running
        except Exception as e:
            logger.error(f"Error checking app status: {e}")
            return False
    
    @staticmethod
    def force_stop_app(ip: str, package: str, port: int = 5555) -> bool:
        """Force stop an app"""
        try:
            cmd = f'adb -s {ip}:{port} shell "am force-stop {package}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, text=True)
            
            if result.returncode == 0:
                logger.info(f"✓ Stopped app: {package} on {ip}")
                return True
            else:
                logger.error(f"Failed to stop app: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error stopping app: {e}")
            return False
    
    @staticmethod
    def start_app(ip: str, package: str, roblox_url: str, port: int = 5555) -> bool:
        """Start app with Roblox URL"""
        try:
            # Ensure URL is properly formatted
            if not roblox_url.startswith('http'):
                if '=' in roblox_url:  # It's a code
                    code = roblox_url.split('=')[-1].split('&')[0]
                    roblox_url = f"https://www.roblox.com/share?code={code}&type=Server"
                else:
                    roblox_url = f"https://www.roblox.com/share?code={roblox_url}&type=Server"
            
            cmd = f'adb -s {ip}:{port} shell "am start -a android.intent.action.VIEW -d \'{roblox_url}\' {package}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10, text=True)
            
            if result.returncode == 0:
                logger.info(f"✓ Started app: {package} on {ip}")
                return True
            else:
                logger.error(f"Failed to start app: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error starting app: {e}")
            return False
    
    @staticmethod
    def restart_app(ip: str, package: str, roblox_url: str, port: int = 5555, delay: int = 3) -> bool:
        """Restart app (force stop + start)"""
        logger.info(f"🔄 Restarting {package} on {ip}")
        
        # Stop app
        ADBController.force_stop_app(ip, package, port)
        
        # Wait before starting
        time.sleep(delay)
        
        # Start app
        return ADBController.start_app(ip, package, roblox_url, port)

# ========== MONITOR ==========
class RobloxMonitor:
    """Main monitoring system"""
    
    def __init__(self, config_path: str = CONFIG_FILE):
        logger.info("="*70)
        logger.info(f"VSPhone Auto Reconnect v{VERSION}")
        logger.info("="*70)
        
        # Check ADB
        if not ADBController.check_adb_installed():
            logger.error("❌ ADB is not installed! Please install Android Debug Bridge (ADB)")
            sys.exit(1)
        
        logger.info("✓ ADB is installed")
        
        # Load configuration
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"✓ Loaded configuration from {config_path}")
        except FileNotFoundError:
            logger.error(f"❌ Config file not found: {config_path}")
            logger.error("Please create config.json with your account details")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file: {e}")
            sys.exit(1)
        
        # Initialize accounts
        self.accounts = []
        for acc in self.config.get('accounts', []):
            api = VSPhoneAPI(acc['api_key'], acc['api_secret'])
            self.accounts.append({
                'name': acc['name'],
                'api': api,
                'devices': acc.get('devices', [])
            })
            logger.info(f"✓ Account loaded: {acc['name']} ({len(acc.get('devices', []))} devices)")
        
        # Monitoring settings
        mon_config = self.config.get('monitoring', {})
        self.check_interval = mon_config.get('check_interval', 30)
        self.restart_delay = mon_config.get('restart_delay', 5)
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'total_restarts': 0,
            'started_at': datetime.now().isoformat()
        }
        
        logger.info("="*70)
        logger.info(f"⏱️  Check interval: {self.check_interval}s")
        logger.info(f"🔄 Restart delay: {self.restart_delay}s")
        logger.info("="*70)
    
    def check_and_restart_apps(self):
        """Check all apps and restart if needed"""
        
        for account in self.accounts:
            account_name = account['name']
            logger.info(f"\n📱 Checking account: {account_name}")
            
            # Get device status from API (optional - for monitoring only)
            devices_online = {}
            try:
                api_devices = account['api'].get_device_list()
                if api_devices:
                    for dev in api_devices:
                        phone_id = dev.get('phoneId') or dev.get('id')
                        is_online = dev.get('online') == 1
                        devices_online[phone_id] = is_online
            except:
                logger.warning(f"Could not fetch device status from API")
            
            # Check each configured device
            for device_config in account['devices']:
                device_id = device_config.get('device_id')
                device_ip = device_config.get('device_ip')
                
                if not device_ip:
                    logger.error(f"❌ Missing device_ip for device {device_id}")
                    logger.error("Please add 'device_ip' to your config.json!")
                    continue
                
                # Check API status if available
                if device_id in devices_online:
                    status = "🟢 ONLINE" if devices_online[device_id] else "🔴 OFFLINE"
                    logger.info(f"  Device {device_id}: {status}")
                
                # Connect via ADB
                if not ADBController.connect(device_ip):
                    logger.error(f"  ❌ Failed to connect to {device_ip} via ADB")
                    continue
                
                logger.info(f"  ✓ Connected to {device_ip}")
                
                # Check each app
                for app in device_config.get('apps', []):
                    package = app.get('package')
                    roblox_url = app.get('roblox_url')
                    game_name = app.get('game_name', package)
                    
                    if not package or not roblox_url:
                        logger.error(f"    ❌ Missing package or roblox_url in config")
                        continue
                    
                    # Check if app is running
                    is_running = ADBController.is_app_running(device_ip, package)
                    
                    if is_running:
                        logger.info(f"    ✅ {game_name}: RUNNING")
                    else:
                        logger.warning(f"    ⚠️  {game_name}: NOT RUNNING")
                        
                        # Restart app
                        success = ADBController.restart_app(
                            device_ip, 
                            package, 
                            roblox_url, 
                            delay=self.restart_delay
                        )
                        
                        if success:
                            self.stats['total_restarts'] += 1
                            logger.info(f"    ✅ {game_name}: RESTARTED SUCCESSFULLY")
                        else:
                            logger.error(f"    ❌ {game_name}: RESTART FAILED")
    
    def run(self):
        """Main monitoring loop"""
        logger.info("\n🚀 Starting monitoring loop...\n")
        
        try:
            while True:
                self.stats['total_checks'] += 1
                
                logger.info("="*70)
                logger.info(f"🔍 CHECK #{self.stats['total_checks']} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("="*70)
                
                try:
                    self.check_and_restart_apps()
                except Exception as e:
                    logger.error(f"Error during check: {e}")
                    logger.debug(traceback.format_exc())
                
                logger.info("\n" + "="*70)
                logger.info(f"📊 Stats: Checks={self.stats['total_checks']}, Restarts={self.stats['total_restarts']}")
                logger.info(f"⏳ Next check in {self.check_interval} seconds...")
                logger.info("="*70 + "\n")
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("\n\n🛑 Stopping monitor (Ctrl+C pressed)")
            logger.info(f"Final stats: {self.stats['total_checks']} checks, {self.stats['total_restarts']} restarts")
            sys.exit(0)

# ========== MAIN ==========
def main():
    """Main entry point"""
    try:
        monitor = RobloxMonitor(CONFIG_FILE)
        monitor.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())