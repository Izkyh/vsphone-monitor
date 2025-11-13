#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSPhone Device Detector
Auto-detect all devices from VSPhone API
"""

import json
import sys
import os

# Try to import from vsphone_monitor
try:
    from vsphone_monitor import VSPhoneAPI, logger
except ImportError:
    # Fallback: create minimal versions if vsphone_monitor not available
    import requests
    import hashlib
    import hmac
    import logging
    from datetime import datetime, timezone
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    class VSPhoneAPI:
        """Minimal VSPhone API Client"""
        
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret
            self.host = "api.vsphone.com"
            self.base_url = f"https://{self.host}"
        
        def _sign_request(self, method, uri, query_params="", body=""):
            """Generate HMAC-SHA256 signature"""
            now = datetime.now(timezone.utc)
            x_date = now.strftime('%Y%m%dT%H%M%SZ')
            date_stamp = now.strftime('%Y%m%d')
            
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
            content_sha256 = hashlib.sha256(body_str.encode('utf-8')).hexdigest()
            
            canonical_headers = {
                'content-type': 'application/json',
                'host': self.host,
                'x-content-sha256': content_sha256,
                'x-date': x_date
            }
            
            canonical_header_str = '\n'.join([f"{k}:{v}" for k, v in sorted(canonical_headers.items())])
            signed_headers = ';'.join(sorted(canonical_headers.keys()))
            
            canonical_request = f"{method}\n{uri}\n{query_params}\n{canonical_header_str}\n\n{signed_headers}\n{content_sha256}"
            
            algorithm = "SDK-HMAC-SHA256"
            credential_scope = f"{date_stamp}/vsphone/sdk_request"
            canonical_request_hash = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
            string_to_sign = f"{algorithm}\n{x_date}\n{credential_scope}\n{canonical_request_hash}"
            
            k_date = hmac.new(f"SDK{self.api_secret}".encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
            k_service = hmac.new(k_date, "vsphone".encode('utf-8'), hashlib.sha256).digest()
            k_signing = hmac.new(k_service, "sdk_request".encode('utf-8'), hashlib.sha256).digest()
            signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
            
            authorization = f"{algorithm} Credential={self.api_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
            
            return {
                'Content-Type': 'application/json',
                'Host': self.host,
                'X-Content-Sha256': content_sha256,
                'X-Date': x_date,
                'Authorization': authorization
            }
        
        def get_devices(self):
            """Get all devices"""
            uri = "/api/v1/phone/list"
            headers = self._sign_request("POST", uri, body={})
            
            try:
                response = requests.post(f"{self.base_url}{uri}", headers=headers, json={}, timeout=15)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error getting devices: {e}")
                return None


def print_table(data, headers):
    """Simple table printer with borders"""
    if not data:
        print("(empty)")
        return
    
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Print top border
    top_border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    print(top_border)
    
    # Print header
    header_row = "|" + "|".join(f" {h.ljust(col_widths[i])} " for i, h in enumerate(headers)) + "|"
    print(header_row)
    
    # Print separator
    separator = "+" + "+".join("=" * (w + 2) for w in col_widths) + "+"
    print(separator)
    
    # Print rows
    for row in data:
        row_str = "|" + "|".join(f" {str(cell).ljust(col_widths[i])} " for i, cell in enumerate(row)) + "|"
        print(row_str)
    
    # Print bottom border
    print(top_border)


def main():
    """Main function"""
    
    print("=" * 80)
    print(" " * 25 + "VSPhone Device Detector")
    print("=" * 80)
    
    # Get API credentials
    print("\nEnter API credentials (or press Enter to use default):")
    
    api_key = input("API Key: ").strip()
    if not api_key:
        api_key = "BGtN6bmiB3NmBEo27nOPLzgIlbkkk53q"
        print(f"  Using default: {api_key[:20]}...")
    
    api_secret = input("API Secret: ").strip()
    if not api_secret:
        api_secret = "zzo1h0qn0i9qnXGUTV6m3Kyk"
        print(f"  Using default: {api_secret[:20]}...")
    
    print("\n🔍 Fetching devices from VSPhone API...")
    print("-" * 80)
    
    # Get devices from API
    api = VSPhoneAPI(api_key, api_secret)
    result = api.get_devices()
    
    if not result:
        print("\n❌ Failed to connect to API")
        print("   Please check your API credentials and internet connection")
        return 1
    
    if 'data' not in result:
        print("\n❌ Unexpected API response")
        print(f"   Response: {result}")
        return 1
    
    devices = result.get('data', {}).get('list', [])
    
    if not devices:
        print("\n⚠️  No devices found in this account")
        print("   Make sure you have devices registered in VSPhone")
        return 0
    
    print(f"\n✅ Found {len(devices)} device(s)\n")
    
    # Prepare table data
    table_data = []
    config_devices = []
    
    for idx, device in enumerate(devices, 1):
        # Extract device info
        phone_id = device.get('phoneId') or device.get('id') or 'N/A'
        phone_name = device.get('phoneName') or device.get('name') or f'Device_{idx}'
        is_online = device.get('online') == 1
        status = "🟢 Online" if is_online else "🔴 Offline"
        
        # Try multiple IP fields
        ip = (device.get('ip') or 
              device.get('localIp') or 
              device.get('wifiIp') or 
              device.get('ipAddress') or 
              'N/A')
        
        # Add to table
        table_data.append([
            str(idx),
            phone_name,
            phone_id,
            ip,
            status
        ])
        
        # Prepare config entry
        config_devices.append({
            "device_id": phone_id,
            "device_name": phone_name,
            "device_ip": ip if ip != 'N/A' else "192.168.1.XXX",
            "apps": [
                {
                    "package": "com.mangcut.rulod",
                    "roblox_url": "https://www.roblox.com/share?code=YOUR_CODE_HERE&type=Server",
                    "game_name": f"{phone_name} - Game 1"
                },
                {
                    "package": "com.mangcut.ruloe",
                    "roblox_url": "https://www.roblox.com/share?code=YOUR_CODE_HERE&type=Server",
                    "game_name": f"{phone_name} - Game 2"
                }
            ]
        })
    
    # Print table
    headers = ["#", "Device Name", "Device ID", "IP Address", "Status"]
    print_table(table_data, headers)
    
    # Show summary
    online_count = sum(1 for d in devices if d.get('online') == 1)
    print(f"\n📊 Summary: {online_count} online, {len(devices) - online_count} offline")
    
    # Generate config template
    print("\n" + "=" * 80)
    print(" " * 20 + "📝 Config Template for accounts.json")
    print("=" * 80 + "\n")
    
    config_template = {
        "devices": config_devices
    }
    
    # Pretty print JSON
    json_output = json.dumps(config_template, indent=2, ensure_ascii=False)
    print(json_output)
    
    # Save to file
    output_file = "devices_detected.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config_template, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Config template saved to: {output_file}")
    except Exception as e:
        print(f"\n⚠️  Warning: Could not save to file: {e}")
    
    # Print instructions
    print("\n" + "=" * 80)
    print("📋 Next Steps:")
    print("=" * 80)
    print("""
1. Copy the 'devices' array above to your accounts.json file

2. Update each device:
   - Replace 'YOUR_CODE_HERE' with actual Roblox server codes
   - Update device_ip if showing '192.168.1.XXX'
   - Add more apps to 'apps' array as needed

3. Example app entry:
   {
     "package": "com.mangcut.rulod",
     "roblox_url": "https://www.roblox.com/share?code=abc123xyz789&type=Server",
     "game_name": "Blox Fruits Main"
   }

4. Common package names:
   - com.mangcut.rulod
   - com.mangcut.ruloe
   - com.mangcut.rulof
   - com.mangcut.rulog
   - com.mangcut.ruloh
   - com.mangcut.ruloi
   - com.mangcut.ruloj

5. To find packages installed on device, run:
   adb -s <DEVICE_IP>:5555 shell "pm list packages | grep mangcut"

6. Test your config:
   python3 test_connection.py

7. Start monitoring:
   bash start_monitor.sh
""")
    
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)