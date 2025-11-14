#!/bin/bash
# Helper script to check Railway logs

echo "=== Railway Log Checker ==="
echo ""

# Check if Railway CLI is linked
if railway link --help > /dev/null 2>&1; then
    echo "📋 To link Railway project, run:"
    echo "   railway link"
    echo ""
fi

echo "Option 1: Export logs from Railway dashboard"
echo "  1. Go to Railway dashboard"
echo "  2. Click on your service"
echo "  3. Go to 'Logs' tab"
echo "  4. Copy logs (or use 'Export' if available)"
echo "  5. Save to file: railway_logs.txt"
echo "  6. Run: python analyze_logs.py railway_logs.txt"
echo ""

echo "Option 2: Use Railway CLI (if linked)"
echo "  railway logs > railway_logs.txt"
echo "  python analyze_logs.py railway_logs.txt"
echo ""

echo "Option 3: Share logs with me"
echo "  Copy/paste the last 50-100 lines from Railway logs"
echo "  I can analyze them for you"
echo ""

echo "Quick check - what to look for in Railway logs:"
echo "  ✅ [INFO] Starting Lighter Trend Trader..."
echo "  ✅ [price_feed] market:2 price: XXX.XX"
echo "  ✅ [mean_reversion] fetched X candles"
echo "  ⚠️  [WARNING] failed to fetch (API issues)"
echo "  🎯 [mean_reversion] entering position (signals!)"

