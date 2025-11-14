#!/bin/bash
# Quick status check script (for local development)

echo "=== Lighter Trend Trader Status ==="
echo ""

# Check if running on Railway
if [ -n "$RAILWAY_ENVIRONMENT" ] || [ -n "$RAILWAY_PROJECT_ID" ]; then
    echo "🚂 Running on Railway"
    echo ""
    echo "View logs in Railway dashboard:"
    echo "   https://railway.app"
    echo ""
    echo "Or export logs:"
    echo "   railway logs > railway_logs.txt"
    echo "   python analyze_logs.py railway_logs.txt"
    exit 0
fi

# Local development checks
# Check if bot is running locally
if pgrep -f "python main.py" > /dev/null; then
    echo "✅ Bot is RUNNING (local)"
    PID=$(pgrep -f "python main.py" | head -1)
    echo "   PID: $PID"
    
    # Check uptime
    if [ -n "$PID" ]; then
        UPTIME=$(ps -p $PID -o etime= | xargs)
        echo "   Uptime: $UPTIME"
    fi
else
    echo "❌ Bot is NOT running (local)"
    echo ""
    echo "💡 If deployed on Railway, check Railway dashboard for status"
fi

echo ""

# Check log files (local only)
LOG_COUNT=$(ls -1 logs/bot_*.log 2>/dev/null | wc -l | xargs)
if [ "$LOG_COUNT" -gt 0 ]; then
    echo "📝 Local log files: $LOG_COUNT"
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
    echo "📝 No local log files found"
    echo "   (If on Railway, logs are in Railway dashboard)"
fi

echo ""
echo "Local commands:"
echo "  View logs: tail -f logs/bot_*.log"
echo "  Analyze: python analyze_logs.py"
echo "  Stop: pkill -f 'python main.py'"
echo ""
echo "Railway commands:"
echo "  View logs: railway logs"
echo "  Export logs: railway logs > railway_logs.txt"
echo "  Analyze: python analyze_logs.py railway_logs.txt"

