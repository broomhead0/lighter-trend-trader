#!/bin/bash
# Continuous monitoring script for Railway logs
# Checks for errors and reports them

cd /Users/nico/cursour_lighter_bot/lighter-trend-trader

echo "Starting continuous log monitoring..."
echo "Press Ctrl+C to stop"
echo ""

CHECK_COUNT=0
ERROR_COUNT=0

while true; do
    CHECK_COUNT=$((CHECK_COUNT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$TIMESTAMP] Check #$CHECK_COUNT - Fetching logs..."

    # Get recent logs
    LOGS=$(railway logs --tail 200 2>&1)

    # Check for errors
    ERRORS=$(echo "$LOGS" | grep -iE "(error|exception|traceback|failed|invalid.*order|code=[0-9]+)" | head -20)

    if [ -n "$ERRORS" ]; then
        ERROR_COUNT=$((ERROR_COUNT + 1))
        echo ""
        echo "⚠️  ERRORS FOUND (Total: $ERROR_COUNT):"
        echo "----------------------------------------"
        echo "$ERRORS"
        echo "----------------------------------------"
        echo ""

        # Check for specific error patterns
        if echo "$ERRORS" | grep -q "invalid order base or quote amount"; then
            echo "🔴 Detected: invalid order base or quote amount (code=21706)"
            echo "   This should be fixed with 0.01 SOL minimum size"
        fi

        if echo "$ERRORS" | grep -q "invalid signature"; then
            echo "🔴 Detected: invalid signature (code=21120)"
            echo "   Check API_KEY_INDEX matches the registered key"
        fi

        if echo "$ERRORS" | grep -q "api key not found"; then
            echo "🔴 Detected: api key not found (code=21109)"
            echo "   API key may not be registered on-chain"
        fi

    else
        # Show recent activity if no errors
        RECENT=$(echo "$LOGS" | tail -10)
        if [ -n "$RECENT" ]; then
            echo "✅ No errors found. Recent activity:"
            echo "$RECENT" | tail -5
        else
            echo "ℹ️  No errors found. Logs appear empty (bot may be starting up)"
        fi
    fi

    echo ""
    sleep 30  # Check every 30 seconds
done

