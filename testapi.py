#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test VSPhone API Connection
Quick test untuk memastikan API credentials bekerja
"""

import sys
import json
from vsphone_monitor import VSPhoneAPI

def test_api():
    """Test API connection"""
    
    print("="*70)
    print("🧪 VSPhone API Connection Test")
    print("="*70)
    
    # Load config
    try:
        with open('account.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found!")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    
    # Test each account
    success = True
    for account in config.get('accounts', []):
        account_name = account['name']
        api_key = account['api_key']
        api_secret = account['api_secret']
        
        print(f"\n📱 Testing account: {account_name}")
        print(f"   API Key: {api_key[:10]}...")
        
        # Initialize API client
        api = VSPhoneAPI(api_key, api_secret)
        
        # Test get device list
        print("   ⏳ Fetching device list...")
        devices = api.get_device_list()
        
        if devices is not None:
            print(f"   ✅ Success! Found {len(devices)} devices:")
            
            for i, device in enumerate(devices, 1):
                phone_id = device.get('phoneId') or device.get('id')
                phone_name = device.get('phoneName') or device.get('name')
                is_online = device.get('online') == 1
                smart_ip = device.get('smartIp') or device.get('adbIp') or 'N/A'
                
                status = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
                
                print(f"\n   Device #{i}:")
                print(f"      Name: {phone_name}")
                print(f"      ID: {phone_id}")
                print(f"      Status: {status}")
                print(f"      IP: {smart_ip}")
                
                # Test get device detail
                if phone_id:
                    print(f"      ⏳ Fetching device details...")
                    detail = api.get_device_detail(phone_id)
                    if detail:
                        print(f"      ✅ Device details retrieved")
                    else:
                        print(f"      ⚠️  Failed to get device details")
        else:
            print(f"   ❌ Failed to get device list!")
            print(f"   Possible causes:")
            print(f"      - API credentials are incorrect")
            print(f"      - Account has no balance/credit")
            print(f"      - Network connection issue")
            print(f"      - VSPhone API is down")
            success = False
    
    print("\n" + "="*70)
    if success:
        print("✅ All API tests passed!")
    else:
        print("❌ Some API tests failed. Check the errors above.")
    print("="*70)
    
    return success

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)