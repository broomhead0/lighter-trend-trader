#!/usr/bin/env python3
"""Analyze bot logs to extract key metrics and events.

Works with:
- Local log files (logs/bot_*.log)
- Railway logs (if exported to file)
- stdin (pipe logs directly)
"""
import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def analyze_logs(log_dir="logs", log_file=None):
    """Analyze bot logs and extract key information.

    Args:
        log_dir: Directory containing log files (for local logs)
        log_file: Specific log file to analyze (optional)
    """
    # If log_file is provided, analyze that
    if log_file:
        log_files = [Path(log_file)]
    # If stdin has data, use that
    elif not sys.stdin.isatty():
        # Read from stdin
        lines = sys.stdin.readlines()
        return _analyze_lines(lines, "stdin")
    else:
        # Look for local log files
        log_dir = Path(log_dir)
        if not log_dir.exists():
            print(f"Log directory {log_dir} not found")
            print("\n💡 Tip: For Railway logs, export them first:")
            print("   railway logs > railway_logs.txt")
            print("   python analyze_logs.py railway_logs.txt")
            return
        log_files = sorted(log_dir.glob("bot_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

        if not log_files:
            print("No log files found")
            print("\n💡 Tip: For Railway logs, export them first:")
            print("   railway logs > railway_logs.txt")
            print("   python analyze_logs.py railway_logs.txt")
            return

    print(f"Analyzing {len(log_files)} log file(s)...\n")

    # Read all lines from all files
    all_lines = []
    for log_file in log_files:
        print(f"Reading {log_file.name}...")
        with open(log_file) as f:
            all_lines.extend(f.readlines())

    return _analyze_lines(all_lines, "log files")


def _analyze_lines(lines, source_name="logs"):
    """Analyze log lines and extract metrics."""
    # Track metrics
    price_updates = []
    candle_fetches = []
    signals_generated = []
    entries = []
    exits = []
    errors = []

    for line in lines:
        # Price updates
        if "[price_feed]" in line and "price:" in line:
            match = re.search(r"price: ([\d.]+)", line)
            if match:
                price_updates.append(float(match.group(1)))

        # Candle fetches
        if "fetched" in line and "candles" in line:
            match = re.search(r"fetched (\d+) candles", line)
            if match:
                candle_fetches.append(int(match.group(1)))

        # Signals
        if "entering" in line.lower() and "position" in line.lower():
            signals_generated.append(line.strip())
            # Extract signal details
            match = re.search(r"entering (\w+) position.*price=([\d.]+).*size=([\d.]+)", line)
            if match:
                entries.append({
                    "side": match.group(1),
                    "price": float(match.group(2)),
                    "size": float(match.group(3)),
                    "line": line.strip(),
                })

        # Exits
        if "exiting position" in line.lower():
            match = re.search(r"exiting position.*entry=([\d.]+).*reason=(\w+)", line)
            if match:
                exits.append({
                    "entry_price": float(match.group(1)),
                    "reason": match.group(2),
                    "line": line.strip(),
                })

        # Errors
        if "[ERROR]" in line or "Exception" in line or "Traceback" in line:
            errors.append(line.strip())

    # Print summary
    print("\n" + "="*60)
    print("BOT LOG ANALYSIS SUMMARY")
    print("="*60)

    print(f"\n📊 Price Updates: {len(price_updates)}")
    if price_updates:
        print(f"   First: ${price_updates[0]:.2f}")
        print(f"   Last:  ${price_updates[-1]:.2f}")
        if len(price_updates) > 1:
            price_change = ((price_updates[-1] - price_updates[0]) / price_updates[0]) * 100
            print(f"   Change: {price_change:+.2f}%")

    print(f"\n📈 Candle Fetches: {len(candle_fetches)}")
    if candle_fetches:
        print(f"   Average candles per fetch: {sum(candle_fetches)/len(candle_fetches):.1f}")

    print(f"\n🎯 Signals Generated: {len(signals_generated)}")
    if signals_generated:
        print("   Recent signals:")
        for sig in signals_generated[-5:]:
            print(f"   - {sig}")

    print(f"\n📥 Entries: {len(entries)}")
    if entries:
        long_entries = [e for e in entries if e["side"] == "long"]
        short_entries = [e for e in entries if e["side"] == "short"]
        print(f"   Long: {len(long_entries)}")
        print(f"   Short: {len(short_entries)}")
        if entries:
            print("   Recent entries:")
            for entry in entries[-3:]:
                print(f"   - {entry['side'].upper()}: {entry['size']:.4f} @ ${entry['price']:.2f}")

    print(f"\n📤 Exits: {len(exits)}")
    if exits:
        exit_reasons = defaultdict(int)
        for exit in exits:
            exit_reasons[exit["reason"]] += 1
        print("   By reason:")
        for reason, count in exit_reasons.items():
            print(f"   - {reason}: {count}")

    print(f"\n❌ Errors: {len(errors)}")
    if errors:
        print("   Recent errors:")
        for err in errors[-5:]:
            print(f"   - {err[:100]}...")
    else:
        print("   ✅ No errors found!")

    # Calculate PnL if we have entries and exits
    if entries and exits:
        print(f"\n💰 PnL Analysis:")
        # Simple PnL calculation (would need more data for accurate)
        print("   (PnL calculation requires more detailed position tracking)")

    print("\n" + "="*60)
    print(f"Analysis complete! (Source: {source_name})")
    print("="*60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Analyze specific file
        analyze_logs(log_file=sys.argv[1])
    else:
        # Analyze local logs or stdin
        analyze_logs()

