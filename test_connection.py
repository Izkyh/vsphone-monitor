### **File: test_connection.py**

#!/usr/bin/env python3
# test_connection.py

import json
import subprocess
from vsphone_monitor import VSPhoneAPI, DeviceController

def test_api_connection(api_key, api_secret):
    """Test VSPhone API connection"""
    print("🔍 Testing VSPhone API connection...")
    
    api = VSPhoneAPI(api_key, api_secret)
    result = api.get_devices()
    
    if result and 'data' in result:
        print("✅ API connection successful!")
        devices = result.get('data', {}).get('list', [])
        print(f"   Found {len(devices)} devices")
        for d in devices[:3]:  # Show first 3
            print(f"   - {d.get('phoneName')} ({d.get('online') and 'online' or 'offline'})")
        return True
    else:
        print("❌ API connection failed!")
        print(f"   Response: {result}")
        return False

def test_adb_connection(device_ip):
    """Test ADB connection to device"""
    print(f"\n🔍 Testing ADB connection to {device_ip}...")
    
    if DeviceController.connect_device(device_ip):
        print(f"✅ ADB connected to {device_ip}")
        
        # Get installed packages
        try:
            result = subprocess.run(
                f'adb -s {device_ip}:5555 shell "pm list packages | grep mangcut"',
                shell=True,
                capture_output=True,
                timeout=5
            )
            packages = [line.replace('package:', '').strip() 
                       for line in result.stdout.decode().split('\n') 
                       if 'package:' in line]
            
            print(f"   Found {len(packages)} mangcut packages:")
            for pkg in packages:
                print(f"   - {pkg}")
            
            return True
        except Exception as e:
            print(f"❌ Error checking packages: {e}")
            return False
    else:
        print(f"❌ Failed to connect to {device_ip}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("VSPhone Monitor - Connection Test")
    print("="*60)
    
    # Load config
    try:
        with open('accounts.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ accounts.json not found!")
        print("   Copy accounts.example.json to accounts.json and edit it")
        return
    
    # Test each account
    for account in config['accounts']:
        print(f"\n📱 Testing account: {account['name']}")
        print("-" * 60)
        
        # Test API
        api_ok = test_api_connection(account['api_key'], account['api_secret'])
        
        # Test devices
        for device in account['devices']:
            adb_ok = test_adb_connection(device['device_ip'])
    
    print("\n" + "="*60)
    print("✅ Test completed!")
    print("="*60)

if __name__ == "__main__":
    main()