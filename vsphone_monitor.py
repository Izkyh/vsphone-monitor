import requests
import json
import datetime
import hmac
import hashlib
import time
import subprocess
from typing import List, Dict, Optional

class VSPhoneMonitor:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.api_host = "api.vsphone.com"
        self.content_type = "application/json;charset=UTF-8"
        self.service = "armcloud-paas"
        self.algorithm = "HMAC-SHA256"
        self.base_url = f"https://{self.api_host}"
    
    def _get_signature(self, x_date: str, body: str) -> str:
        """Generate HMAC-SHA256 signature for API request"""
        try:
            # Parse JSON to remove spaces
            if body:
                json_obj = json.loads(body)
                json_string = json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
            else:
                json_string = ""
            
            # Calculate SHA-256 hash
            x_content_sha256 = hashlib.sha256(json_string.encode()).hexdigest()
            
            # Build canonical string
            canonical_string = (
                f"host:{self.api_host}\n"
                f"x-date:{x_date}\n"
                f"content-type:{self.content_type}\n"
                f"signedHeaders:content-type;host;x-content-sha256;x-date\n"
                f"x-content-sha256:{x_content_sha256}"
            )
            
            # Short date
            short_x_date = x_date[:8]
            
            # Credential scope
            credential_scope = f"{short_x_date}/{self.service}/request"
            
            # Hash canonical string
            hash_sha256 = hashlib.sha256(canonical_string.encode()).hexdigest()
            
            # String to sign
            string_to_sign = f"{self.algorithm}\n{x_date}\n{credential_scope}\n{hash_sha256}"
            
            # Generate signing key
            k_date = hmac.new(self.secret_key.encode(), short_x_date.encode(), hashlib.sha256).digest()
            k_service = hmac.new(k_date, self.service.encode(), hashlib.sha256).digest()
            signing_key = hmac.new(k_service, b'request', hashlib.sha256).digest()
            
            # Final signature
            signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
            
            return signature
        except Exception as e:
            print(f"[ERROR] Signature generation failed: {e}")
            raise
    
    def _get_headers(self, body: Optional[str] = None) -> Dict[str, str]:
        """Generate request headers with signature"""
        x_date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        short_date = x_date[:8]
        
        body_str = json.dumps(body, separators=(',', ':'), ensure_ascii=False) if body else ""
        signature = self._get_signature(x_date, body_str)
        
        authorization = (
            f"{self.algorithm} Credential={self.access_key}/{short_date}/{self.service}/request, "
            f"SignedHeaders=content-type;host;x-content-sha256;x-date, "
            f"Signature={signature}"
        )
        
        return {
            "content-type": self.content_type,
            "x-date": x_date,
            "x-host": self.api_host,
            "authorization": authorization
        }
    
    def get_device_list(self, page: int = 1, rows: int = 100) -> Optional[List[Dict]]:
        """Get cloud phone list - CORRECT API ENDPOINT"""
        url = f"{self.base_url}/vsphone/api/padApi/userPadList"
        
        # Request body for pagination
        body = {
            "page": page,
            "rows": rows
        }
        
        try:
            headers = self._get_headers(body)
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    data = result.get('data', {})
                    devices = data.get('records', [])
                    print(f"[INFO] Successfully retrieved {len(devices)} devices")
                    return devices
                else:
                    print(f"[ERROR] API returned error: {result.get('msg')}")
                    return None
            else:
                print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decode error: {e}")
            return None
    
    def get_adb_info(self, pad_code: str, enable: bool = True) -> Optional[Dict]:
        """Get ADB connection information for a device"""
        url = f"{self.base_url}/vsphone/api/padApi/adb"
        
        body = {
            "padCode": pad_code,
            "enable": enable
        }
        
        try:
            headers = self._get_headers(body)
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    return result.get('data')
                else:
                    print(f"[ERROR] {pad_code}: API error - {result.get('msg')}")
                    return None
            else:
                print(f"[ERROR] {pad_code}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ERROR] {pad_code}: Failed to get ADB info - {e}")
            return None
    
    def check_adb_connection(self, ip: str, port: int) -> bool:
        """Check if ADB connection is working"""
        try:
            # Try to connect via ADB
            cmd = f"adb connect {ip}:{port}"
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "connected" in result.stdout.lower():
                return True
            else:
                print(f"[WARNING] ADB connection failed: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"[ERROR] ADB connection timeout: {ip}:{port}")
            return False
        except Exception as e:
            print(f"[ERROR] ADB check failed: {e}")
            return False
    
    def restart_device(self, pad_code: str, change_ip: bool = False) -> bool:
        """Restart a device"""
        url = f"{self.base_url}/vsphone/api/padApi/restart"
        
        body = {
            "padCodes": [pad_code],
            "changeIpFlag": change_ip
        }
        
        try:
            headers = self._get_headers(body)
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    print(f"[INFO] {pad_code}: Restart command sent successfully")
                    return True
                else:
                    print(f"[ERROR] {pad_code}: Restart failed - {result.get('msg')}")
                    return False
            else:
                print(f"[ERROR] {pad_code}: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[ERROR] {pad_code}: Restart request failed - {e}")
            return False


def main():
    """Main monitoring loop"""
    
    # Configuration - REPLACE WITH YOUR ACTUAL CREDENTIALS
    ACCESS_KEY = "WpUO0r4Wpdb1HRvgLaFd7BVcuztJecol"
    SECRET_KEY = "l6GHq2ZvPvwnWpq66aFeqQcR"
    
    # Check interval (seconds)
    CHECK_INTERVAL = 30
    
    # Initialize monitor
    monitor = VSPhoneMonitor(ACCESS_KEY, SECRET_KEY)
    
    total_checks = 0
    total_restarts = 0
    
    print("=" * 57)
    print("VSPhone Device Monitor Started")
    print("=" * 57)
    
    while True:
        try:
            total_checks += 1
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n🔍 Checking all accounts - {timestamp}")
            print("=" * 57)
            
            # Get device list
            devices = monitor.get_device_list()
            
            if devices:
                for device in devices:
                    pad_code = device.get('padCode')
                    vm_status = device.get('vmStatus')  # 0: offline, 1: online
                    
                    print(f"[INFO] Checking device: {pad_code}")
                    
                    if vm_status == 0:
                        print(f"[WARNING] {pad_code}: Device is offline")
                        continue
                    
                    # Get ADB info
                    adb_info = monitor.get_adb_info(pad_code)
                    
                    if adb_info and adb_info.get('enable'):
                        command = adb_info.get('command', '')
                        # Parse IP and port from command: "adb connect ip:port"
                        if 'adb connect' in command:
                            connection = command.replace('adb connect ', '').strip()
                            if ':' in connection:
                                ip, port = connection.split(':')
                                
                                # Check ADB connection
                                if not monitor.check_adb_connection(ip, int(port)):
                                    print(f"[ERROR] {pad_code}: ADB connection failed, restarting...")
                                    if monitor.restart_device(pad_code):
                                        total_restarts += 1
                    else:
                        print(f"[INFO] {pad_code}: ADB not enabled or not available")
            else:
                print("[ERROR] Failed to retrieve device list")
                print("[ERROR] Please check:")
                print("[ERROR] 1. Access Key and Secret Key are correct")
                print("[ERROR] 2. Account has active subscription")
                print("[ERROR] 3. Network connection is working")
                print("[ERROR] 4. API endpoint is accessible")
            
            # Print summary
            print("=" * 57)
            print(f"✅ Total checks: {total_checks} | Total restarts: {total_restarts}")
            print(f"🔁 Next check in {CHECK_INTERVAL} seconds...")
            print("=" * 57)
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n[INFO] Monitor stopped by user")
            break
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()