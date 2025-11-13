#!/data/data/com.termux/files/usr/bin/bash
# Stop VSPhone Monitor

cd ~/vsphone-monitor

echo "🛑 Stopping VSPhone Monitor..."

if [ -f monitor.pid ]; then
    PID=$(cat monitor.pid)
    
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "✅ Monitor stopped (PID: $PID)"
        
        # Wait for process to stop
        for i in {1..5}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  Process not responding, force killing..."
            kill -9 $PID
        fi
    else
        echo "ℹ️  Monitor not running (stale PID file)"
    fi
    
    rm monitor.pid
else
    # Try to find and kill by process name
    pkill -f vsphone_monitor.py
    if [ $? -eq 0 ]; then
        echo "✅ Monitor stopped"
    else
        echo "ℹ️  Monitor not running"
    fi
fi