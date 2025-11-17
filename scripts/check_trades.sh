#!/bin/bash
# Quick script to check if we have trades and show stats

echo "=== Checking for Trades ==="
echo ""

# Try to query database (if accessible)
if command -v python3 &> /dev/null; then
    cd "$(dirname "$0")/.."
    python3 scripts/query_pnl.py --recent 5 2>&1 | head -30
else
    echo "Python not found. Install Python 3 to use query_pnl.py"
fi

echo ""
echo "=== To query from Railway ==="
echo "1. Download database from Railway (if accessible)"
echo "2. Run: python scripts/query_pnl.py --db-path /path/to/pnl_trades.db"
echo ""
echo "Or check Railway logs for 'LIVE PnL' entries"

