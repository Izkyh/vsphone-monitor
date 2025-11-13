# VSPhone Multi-Account Monitor

🚀 Automatic 24/7 monitoring and restart system for multiple VSPhone accounts with multiple devices and Roblox apps.

## Features

✅ **Multi-Account Support** - Monitor 4+ VSPhone accounts simultaneously  
✅ **Multi-Device** - Multiple devices per account  
✅ **Multi-App** - 7-10 Roblox clones per device  
✅ **Auto-Restart** - Automatically restart crashed apps  
✅ **ADB Wireless** - Control devices over WiFi  
✅ **Parallel Monitoring** - Check all accounts simultaneously  
✅ **Smart Detection** - Match devices by ID or name  
✅ **Full URL Support** - Use complete Roblox URLs or just codes  
✅ **Detailed Logging** - Track all activities  
✅ **Statistics** - Monitor performance metrics  

## Requirements

- Termux on Android (HP Super)
- Python 3.8+
- ADB tools
- VSPhone account with API credentials
- Network connection to all devices

## Installation

### 1. Setup Termux

```bash
# Update Termux
pkg update && pkg upgrade -y

# Install dependencies
pkg install python git android-tools -y

# Install Python packages
pip install requests colorama