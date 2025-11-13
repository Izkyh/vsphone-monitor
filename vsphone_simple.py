#!/usr/bin/env python3
"""
VSPhone Simple Monitor - Versi Sederhana
Hanya monitor status device online/offline
Tidak perlu ribet dengan ADB command
"""

import requests
import json
import datetime
import hmac
import hashlib
import time
from typing import Optional, Dict, List

class VSPhoneAPI:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.api_host = "api.vsphone.com"
        self.base_url = f"https://{self.api_host}"
        self.content_type = "application/json;charset=UTF-8"
    
    def _sign_request(self, x_date: str, body_str: str) -> str:
        """Generate signature"""
        try:
            # SHA-256 hash of body
            x_content_sha256 = hashlib.sha256(body_str.encode()).hexdigest()
            
            # Canonical string
            canonical = (
                f"host:{self.api_host}\n"
                f"x-date:{x_date}\n"
                f"content-type:{self.content_type}\n"
                f"signedHeaders:content-type;host;x-content-sha256;x-date\n"
                f"x-content-sha256:{x_content_sha256}"
            )
            
            short_date = x_date[:8]
            credential = f"{short_date}/armcloud-paas/request"
            
            # String to sign
            string_to_sign = (
                f"HMAC-SHA256\n"
                f"{x_date}\n"
                f"{credential}\n"
                f"{hashlib.sha256(canonical.encode()).hexdigest()}"
            )
            
            # Signing key
            k_date = hmac.new(self.secret_key.encode(), short_date.encode(), hashlib.sha256).digest()
            k_service = hmac.new(k_date, b'armcloud-paas', hashlib.sha256).digest()
            k_signing = hmac.new(k_service, b'request', hashlib.sha256).digest()
            
            # Signature
            signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
            return signature
            
        except Exception as e:
            print(f"[ERROR] Signature failed: {e}")
            raise
    
    def _make_request(self, endpoint: str, body: dict) -> Optional[dict]:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        
        # Prepare body
        body_str = json.dumps(body, separators=(',', ':'), ensure_ascii=False)
        
        # Generate timestamp
        x_date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        short_date = x_date[:8]
        
        # Sign request
        signature = self._sign_request(x_date, body_str)
        
        # Headers
        headers = {
            "content-type": self.content_type,
            "x-date": x_date,
            "x-host": self.api_host,
            "authorization": (
                f"HMAC-SHA256 Credential={self.access_key}/{short_date}/armcloud-paas/request, "
                f"SignedHeaders=content-type;host;x-content-sha256;x-date, "
                f"Signature={signature}"
            )
        }
        
        try:
            response = requests.post(url, headers=headers, data=body_str, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    return result.get('data')
                else:
                    print(f"[ERROR] API Error: {result.get('msg')}")
                    return None
            else:
                print(f"[ERROR] HTTP {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return None
    
    def get_devices(self, page: int = 1, rows: int = 100) -> Optional[List[Dict]]:
        """Get device list"""
        body = {"page": page, "rows": rows}
        data = self._make_request("/vsphone/api/padApi/userPadList", body)
        
        if data and isinstance(data, dict):
            records = data.get('records', [])
            return records if isinstance(records, list) else []
        return []
    
    def restart_device(self, pad_code: str) -> bool:
        """Restart device"""
        body = {"padCodes": [pad_code], "changeIpFlag": False}
        result = self._make_request("/vsphone/api/padApi/restart", body)
        return result is not None


def main():
    """Simple monitoring - Cek status online/offline saja"""
    
    # Your API credentials
    ACCESS_KEY = "WpUO0r4Wpdb1HRvgLaFd7BVcuztJecol"
    SECRET_KEY = "l6GHq2ZvPvwnWpq66aFeqQcR"
    
    # Settings
    CHECK_INTERVAL = 30  # seconds
    AUTO_RESTART_OFFLINE = False  # Set True untuk auto-restart device offline
    
    api = VSPhoneAPI(ACCESS_KEY, SECRET_KEY)
    
    check_count = 0
    restart_count = 0
    
    print("=" * 57)
    print("📱 VSPhone Simple Monitor Started")
    print("=" * 57)
    print(f"⏱️  Check interval: {CHECK_INTERVAL} seconds")
    print(f"🔄 Auto-restart offline: {'YES' if AUTO_RESTART_OFFLINE else 'NO'}")
    print("=" * 57)
    
    while True:
        try:
            check_count += 1
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n🔍 Check #{check_count} - {timestamp}")
            print("=" * 57)
            
            # Get all devices
            devices = api.get_devices()
            
            if not devices:
                print("❌ No devices found or API error")
                print("   Please check your credentials and network")
            else:
                print(f"📊 Found {len(devices)} device(s)\n")
                
                online_count = 0
                offline_count = 0
                
                for device in devices:
                    if not isinstance(device, dict):
                        continue
                    
                    pad_code = device.get('padCode', 'Unknown')
                    vm_status = device.get('vmStatus', -1)
                    
                    # Status emoji
                    if vm_status == 1:
                        status = "🟢 ONLINE"
                        online_count += 1
                    elif vm_status == 0:
                        status = "🔴 OFFLINE"
                        offline_count += 1
                        
                        # Auto restart if enabled
                        if AUTO_RESTART_OFFLINE:
                            print(f"   ↳ Attempting restart...")
                            if api.restart_device(pad_code):
                                restart_count += 1
                                print(f"   ↳ ✅ Restart command sent")
                            else:
                                print(f"   ↳ ❌ Restart failed")
                    else:
                        status = f"⚠️  STATUS={vm_status}"
                    
                    print(f"{status} - {pad_code}")
                
                # Summary
                print("\n" + "-" * 57)
                print(f"📈 Summary: {online_count} online, {offline_count} offline")
                
            print("=" * 57)
            print(f"✅ Total checks: {check_count} | Restarts: {restart_count}")
            print(f"⏳ Next check in {CHECK_INTERVAL} seconds...")
            print("=" * 57)
            
            # Wait
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n⛔ Monitor stopped by user")
            print(f"📊 Final stats: {check_count} checks, {restart_count} restarts")
            break
            
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n⏳ Retrying in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()