#!/data/data/com.termux/files/usr/bin/bash
# Restart VSPhone Monitor

cd ~/vsphone-monitor

echo "🔄 Restarting VSPhone Monitor..."

bash stop_monitor.sh
sleep 2
bash start_monitor.sh