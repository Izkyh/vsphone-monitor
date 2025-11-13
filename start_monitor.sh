#!/data/data/com.termux/files/usr/bin/bash
# Start VSPhone Monitor

cd ~/vsphone-monitor

echo "🚀 Starting VSPhone Monitor..."

# Check if already running
if [ -f monitor.pid ]; then
    PID=$(cat monitor.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Monitor already running (PID: $PID)"
        echo "   Run 'bash stop_monitor.sh' first to stop it"
        exit 1
    else
        # Stale PID file
        rm monitor.pid
    fi
fi

# Check if accounts.json exists
if [ ! -f accounts.json ]; then
    echo "❌ accounts.json not found!"
    echo "   Copy accounts.example.json to accounts.json and edit it"
    exit 1
fi

# Start monitor in background
nohup python3 vsphone_monitor.py > logs/monitor_output.log 2>&1 &
PID=$!

echo "✅ Monitor started (PID: $PID)"
echo "📝 Logs: logs/vsphone_monitor.log"
echo ""
echo "Commands:"
echo "  - Check status: bash check_status.sh"
echo "  - Stop monitor: bash stop_monitor.sh"
echo "  - View logs: tail -f logs/vsphone_monitor.log"

# Wait a bit and show initial output
sleep 3
echo ""
echo "Initial output:"
tail -n 15 logs/vsphone_monitor.log