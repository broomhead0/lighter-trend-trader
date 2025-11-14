#!/usr/bin/env python3
"""Analyze trade performance from logs."""
import re
import sys
from collections import defaultdict
from typing import List, Dict, Optional

trades = []
current_trade = None

# Parse log lines
for line in sys.stdin:
    # Entry
    entry_match = re.search(r'entering (\w+) position: price=([\d.]+) size=([\d.]+) reason=(.+)', line)
    if entry_match:
        if current_trade:
            trades.append(current_trade)  # Save previous incomplete trade
        current_trade = {
            'side': entry_match.group(1),
            'entry_price': float(entry_match.group(2)),
            'size': float(entry_match.group(3)),
            'reason': entry_match.group(4),
            'timestamp': line.split('[')[0].strip() if '[' in line else '',
        }
        continue

    # Exit
    exit_match = re.search(r'exiting position: side=(\w+) entry=([\d.]+) reason=(.+)', line)
    if exit_match and current_trade:
        current_trade['exit_reason'] = exit_match.group(3)
        current_trade['exit_price'] = None  # Not in log, will calculate
        trades.append(current_trade)
        current_trade = None
        continue

    # PnL
    pnl_match = re.search(r'simulated PnL: ([\d.-]+)%', line)
    if pnl_match and trades:
        trades[-1]['pnl_pct'] = float(pnl_match.group(1))

# Calculate stats
if not trades:
    print("No trades found")
    sys.exit(0)

total_trades = len(trades)
wins = sum(1 for t in trades if t.get('exit_reason') == 'take_profit')
losses = sum(1 for t in trades if t.get('exit_reason') == 'stop_loss')
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

longs = sum(1 for t in trades if t['side'] == 'long')
shorts = sum(1 for t in trades if t['side'] == 'short')

print(f"=== TRADE ANALYSIS ===\n")
print(f"Total Trades: {total_trades}")
print(f"  Longs: {longs} | Shorts: {shorts}")
print(f"  Wins: {wins} ({win_rate:.1f}%) | Losses: {losses} ({100-win_rate:.1f}%)")
print(f"\n=== TRADE BREAKDOWN ===\n")

for i, trade in enumerate(trades, 1):
    pnl = trade.get('pnl_pct', 'N/A')
    print(f"Trade {i}: {trade['side'].upper()} @ ${trade['entry_price']:.2f}")
    print(f"  Reason: {trade['reason']}")
    print(f"  Exit: {trade.get('exit_reason', 'unknown')}")
    if pnl != 'N/A':
        print(f"  PnL: {pnl:+.2f}%")
    print()

# Exit reason breakdown
print(f"\n=== EXIT REASONS ===")
reasons = defaultdict(int)
for t in trades:
    reasons[t.get('exit_reason', 'unknown')] += 1
for reason, count in reasons.items():
    print(f"  {reason}: {count}")

