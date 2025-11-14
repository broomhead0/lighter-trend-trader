#!/bin/bash
# Quick status check script for the trend trader bot

echo "=== Lighter Trend Trader Status ==="
echo ""

# Get recent logs
railway logs --tail 200 2>&1 | grep -E "(candle interval|collecting candles|indicators computed|entering|exiting|created new candle)" | tail -20

echo ""
echo "=== Recent Activity ==="
railway logs --tail 100 2>&1 | tail -10

echo ""
echo "=== Full Analysis ==="
railway logs --tail 5000 2>&1 > /tmp/bot_logs.txt
if [ -f analyze_logs.py ]; then
    python analyze_logs.py /tmp/bot_logs.txt 2>&1
fi
