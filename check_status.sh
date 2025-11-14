#!/bin/bash
# Quick status check script

echo "=== Lighter Trend Trader Status ==="
echo ""

# Check if bot is running
if pgrep -f "python main.py" > /dev/null; then
    echo "✅ Bot is RUNNING"
    PID=$(pgrep -f "python main.py" | head -1)
    echo "   PID: $PID"
    
    # Check uptime
    if [ -n "$PID" ]; then
        UPTIME=$(ps -p $PID -o etime= | xargs)
        echo "   Uptime: $UPTIME"
    fi
else
    echo "❌ Bot is NOT running"
fi

echo ""

# Check log files
LOG_COUNT=$(ls -1 logs/bot_*.log 2>/dev/null | wc -l | xargs)
if [ "$LOG_COUNT" -gt 0 ]; then
    echo "📝 Log files: $LOG_COUNT"
    LATEST_LOG=$(ls -t logs/bot_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "   Latest: $(basename $LATEST_LOG)"
        SIZE=$(du -h "$LATEST_LOG" | cut -f1)
        echo "   Size: $SIZE"
        
        # Count key events
        PRICE_UPDATES=$(grep -c "price:" "$LATEST_LOG" 2>/dev/null || echo "0")
        SIGNALS=$(grep -c "entering.*position" "$LATEST_LOG" 2>/dev/null || echo "0")
        ERRORS=$(grep -c "ERROR\|Exception" "$LATEST_LOG" 2>/dev/null || echo "0")
        
        echo "   Price updates: $PRICE_UPDATES"
        echo "   Signals: $SIGNALS"
        echo "   Errors: $ERRORS"
    fi
else
    echo "📝 No log files found"
fi

echo ""
echo "To view logs: tail -f logs/bot_*.log"
echo "To analyze: python analyze_logs.py"
echo "To stop: pkill -f 'python main.py'"

