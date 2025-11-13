#!/data/data/com.termux/files/usr/bin/bash
# Check VSPhone Monitor Status

cd ~/vsphone-monitor

echo "📊 VSPhone Monitor Status"
echo "========================"

if [ -f monitor.pid ]; then
    PID=$(cat monitor.pid)
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Status: RUNNING"
        echo "📍 PID: $PID"
        
        # Show stats if available
        if [ -f logs/monitor_stats.json ]; then
            echo ""
            echo "Statistics:"
            cat logs/monitor_stats.json | python3 -m json.tool 2>/dev/null || cat logs/monitor_stats.json
        fi
        
        echo ""
        echo "Recent logs (last 10 lines):"
        echo "----------------------------"
        tail -n 10 logs/vsphone_monitor.log
    else
        echo "❌ Status: NOT RUNNING (stale PID)"
        rm monitor.pid
    fi
else
    if pgrep -f vsphone_monitor.py > /dev/null; then
        echo "⚠️  Status: RUNNING (no PID file)"
        PID=$(pgrep -f vsphone_monitor.py)
        echo "📍 PID: $PID"
    else
        echo "❌ Status: NOT RUNNING"
    fi
fi

echo ""
echo "Commands:"
echo "  - Start: bash start_monitor.sh"
echo "  - Stop: bash stop_monitor.sh"
echo "  - Restart: bash restart_monitor.sh"
echo "  - Logs: tail -f logs/vsphone_monitor.log"