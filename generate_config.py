#!/usr/bin/env python3
# generate_config.py

import json
import subprocess

def get_device_packages(device_ip):
    """Get all mangcut packages from device"""
    try:
        result = subprocess.run(
            f'adb -s {device_ip}:5555 shell "pm list packages | grep mangcut"',
            shell=True,
            capture_output=True,
            timeout=5
        )
        packages = []
        for line in result.stdout.decode().split('\n'):
            if 'package:' in line:
                pkg = line.replace('package:', '').strip()
                packages.append(pkg)
        return packages
    except:
        return []

def generate_config():
    """Interactive config generator"""
    
    config = {
        "accounts": [],
        "monitoring": {
            "check_interval": 30,
            "restart_delay": 5,
            "max_restart_attempts": 3,
            "webhook_url": ""
        }
    }
    
    print("🔧 VSPhone Config Generator\n")
    
    # Number of accounts
    num_accounts = int(input("Berapa banyak akun VSPhone? (1-4): "))
    
    for i in range(num_accounts):
        print(f"\n--- Account {i+1} ---")
        
        account_name = input(f"Nama account {i+1}: ")
        api_key = input(f"API Key account {i+1}: ")
        api_secret = input(f"API Secret account {i+1}: ")
        
        account = {
            "name": account_name,
            "api_key": api_key,
            "api_secret": api_secret,
            "devices": []
        }
        
        # Devices
        num_devices = int(input(f"Berapa banyak device untuk {account_name}? "))
        
        for j in range(num_devices):
            print(f"\n  --- Device {j+1} ---")
            
            device_id = input(f"  Device ID/Name: ")
            device_ip = input(f"  Device IP (contoh: 192.168.1.101): ")
            
            # Try to auto-detect packages
            print(f"  Scanning packages di {device_ip}...")
            packages = get_device_packages(device_ip)
            
            if packages:
                print(f"  Found {len(packages)} packages:")
                for pkg in packages:
                    print(f"    - {pkg}")
            
            device = {
                "device_id": device_id,
                "device_name": device_id,
                "device_ip": device_ip,
                "apps": []
            }
            
            # Apps
            num_apps = int(input(f"  Berapa banyak apps untuk device ini? ({len(packages)} detected): ") or len(packages))
            
            for k in range(num_apps):
                if k < len(packages):
                    package = packages[k]
                else:
                    package = input(f"    Package name app {k+1}: ")
                
                share_code = input(f"    Share code untuk {package}: ")
                
                device['apps'].append({
                    "package": package,
                    "share_code": share_code,
                    "game_name": f"Game_{k+1}"
                })
            
            account['devices'].append(device)
        
        config['accounts'].append(account)
    
    # Save config
    with open('accounts.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n✅ Config saved to accounts.json")
    print("\nNext steps:")
    print("1. Review accounts.json")
    print("2. Run: python3 vsphone_monitor.py")

if __name__ == "__main__":
    generate_config()