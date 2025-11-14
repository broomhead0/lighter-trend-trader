#!/usr/bin/env python3
"""Quick analysis of log snippet pasted from Railway."""
import re
import sys
from collections import defaultdict

def analyze_snippet(text):
    """Analyze a log snippet pasted from Railway."""
    lines = text.strip().split('\n')

    print("=== Quick Log Analysis ===\n")

    # Count key events
    price_updates = []
    candle_fetches = []
    signals = []
    errors = []
    warnings = []

    for line in lines:
        if "[price_feed]" in line and "price:" in line:
            match = re.search(r"price: ([\d.]+)", line)
            if match:
                price_updates.append(float(match.group(1)))

        if "fetched" in line and "candles" in line:
            match = re.search(r"fetched (\d+) candles", line)
            if match:
                candle_fetches.append(int(match.group(1)))

        if "entering" in line.lower() and "position" in line.lower():
            signals.append(line.strip())

        if "[ERROR]" in line or "Exception" in line:
            errors.append(line.strip())

        if "[WARNING]" in line:
            warnings.append(line.strip())

    # Print summary
    print(f"📊 Price Updates: {len(price_updates)}")
    if price_updates:
        print(f"   Latest: ${price_updates[-1]:.2f}")
        if len(price_updates) > 1:
            print(f"   Range: ${min(price_updates):.2f} - ${max(price_updates):.2f}")

    print(f"\n📈 Candle Fetches: {len(candle_fetches)}")
    if candle_fetches:
        print(f"   Total candles: {sum(candle_fetches)}")

    print(f"\n🎯 Signals: {len(signals)}")
    if signals:
        print("   Recent:")
        for sig in signals[-3:]:
            print(f"   - {sig[:80]}...")

    print(f"\n⚠️  Warnings: {len(warnings)}")
    if warnings:
        unique_warnings = defaultdict(int)
        for w in warnings:
            # Extract warning type
            if "failed to fetch" in w.lower():
                unique_warnings["API fetch failures"] += 1
            else:
                unique_warnings["Other"] += 1
        for wtype, count in unique_warnings.items():
            print(f"   - {wtype}: {count}")

    print(f"\n❌ Errors: {len(errors)}")
    if errors:
        print("   Recent:")
        for err in errors[-3:]:
            print(f"   - {err[:80]}...")
    else:
        print("   ✅ No errors!")

    # Overall status
    print("\n" + "="*50)
    if len(price_updates) > 0 and len(candle_fetches) > 0:
        print("✅ Bot appears to be WORKING")
        print("   - Price feed active")
        print("   - Candle fetching active")
        if len(signals) > 0:
            print("   - Signals being generated!")
        else:
            print("   - No signals yet (normal - conditions may not be met)")
    elif len(errors) > 5:
        print("⚠️  Bot has ISSUES")
        print("   - Multiple errors detected")
    else:
        print("🔄 Bot status: UNKNOWN")
        print("   - Need more log data to determine")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Read from file
        with open(sys.argv[1]) as f:
            text = f.read()
    else:
        # Read from stdin
        text = sys.stdin.read()

    analyze_snippet(text)

