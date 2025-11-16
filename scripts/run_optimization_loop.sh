#!/bin/bash
# Continuous optimization feedback loop
# Runs optimization check every 2 hours until profitable

cd "$(dirname "$0")/.."

echo "Starting automated optimization loop..."
echo "Will check every 2 hours until strategies are profitable"
echo "Press Ctrl+C to stop"
echo ""

ITERATION=1
while true; do
    echo "=========================================="
    echo "Iteration $ITERATION - $(date)"
    echo "=========================================="
    echo ""

    python3 scripts/auto_optimize.py
    EXIT_CODE=$?

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ All strategies are PROFITABLE!"
        echo "Optimization complete. Ready for production."
        break
    elif [ $EXIT_CODE -eq 1 ]; then
        echo "⏳ Need more data. Waiting 2 hours..."
    else
        echo "⚠️  Strategies need optimization. Waiting 2 hours before next check..."
    fi

    echo ""
    echo "Next check in 2 hours..."
    echo ""

    sleep 7200  # 2 hours
    ITERATION=$((ITERATION + 1))
done

