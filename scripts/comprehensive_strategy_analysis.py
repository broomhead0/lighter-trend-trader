#!/usr/bin/env python3
"""
Comprehensive Strategy Analysis

Analyzes all trades in the database to identify:
- Best/worst performing setups
- Entry condition patterns
- Exit reason analysis
- Market condition correlations
- Strategy comparison
- Optimization recommendations
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

db_path = os.environ.get("PNL_DB_PATH")
if db_path is None:
    # Try common paths
    for path in ["/data/pnl_trades.db", "/persist/pnl_trades.db", "pnl_trades.db"]:
        if os.path.exists(path):
            db_path = path
            break
    if db_path is None:
        db_path = "/data/pnl_trades.db"  # Default for Railway

if not os.path.exists(db_path):
    print(f"❌ Database not found at {db_path}")
    sys.exit(1)

print("=" * 80)
print("COMPREHENSIVE STRATEGY ANALYSIS")
print("=" * 80)
print(f"Database: {db_path}")
print()

conn = sqlite3.connect(db_path, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all trades
cursor.execute("""
    SELECT strategy, side, pnl_pct, entry_price, exit_price, 
           exit_time, exit_reason, entry_time, size
    FROM trades
    ORDER BY exit_time DESC
""")
trades = cursor.fetchall()

if not trades:
    print("❌ No trades found in database")
    sys.exit(0)

print(f"Total trades: {len(trades)}")
print()

# ==================== Overall Statistics ====================
print("=" * 80)
print("OVERALL STATISTICS")
print("=" * 80)

total_pnl = sum(t["pnl_pct"] for t in trades)
wins = [t for t in trades if t["pnl_pct"] > 0]
losses = [t for t in trades if t["pnl_pct"] < 0]
breakeven = [t for t in trades if t["pnl_pct"] == 0]

print(f"Total PnL: {total_pnl:.3f}%")
print(f"Win Rate: {len(wins)}/{len(trades)} ({len(wins)/len(trades)*100:.1f}%)")
print(f"Wins: {len(wins)}, Losses: {len(losses)}, Breakeven: {len(breakeven)}")
if wins:
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins)
    print(f"Average Win: {avg_win:.3f}%")
if losses:
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses)
    print(f"Average Loss: {avg_loss:.3f}%")
    if wins:
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        print(f"Risk/Reward Ratio: {rr_ratio:.2f}:1")
print()

# ==================== By Strategy ====================
print("=" * 80)
print("BY STRATEGY")
print("=" * 80)

strategy_stats = defaultdict(lambda: {"trades": [], "wins": [], "losses": []})
for trade in trades:
    strategy_stats[trade["strategy"]]["trades"].append(trade)
    if trade["pnl_pct"] > 0:
        strategy_stats[trade["strategy"]]["wins"].append(trade)
    elif trade["pnl_pct"] < 0:
        strategy_stats[trade["strategy"]]["losses"].append(trade)

for strategy, stats in sorted(strategy_stats.items()):
    trades_list = stats["trades"]
    wins_list = stats["wins"]
    losses_list = stats["losses"]
    
    total_pnl = sum(t["pnl_pct"] for t in trades_list)
    win_rate = len(wins_list) / len(trades_list) * 100 if trades_list else 0
    
    print(f"\n{strategy.upper()}:")
    print(f"  Total Trades: {len(trades_list)}")
    print(f"  Win Rate: {win_rate:.1f}% ({len(wins_list)}W/{len(losses_list)}L)")
    print(f"  Total PnL: {total_pnl:.3f}%")
    if wins_list:
        avg_win = sum(t["pnl_pct"] for t in wins_list) / len(wins_list)
        print(f"  Avg Win: {avg_win:.3f}%")
    if losses_list:
        avg_loss = sum(t["pnl_pct"] for t in losses_list) / len(losses_list)
        print(f"  Avg Loss: {avg_loss:.3f}%")
        if wins_list:
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f"  R:R Ratio: {rr:.2f}:1")
print()

# ==================== By Exit Reason ====================
print("=" * 80)
print("BY EXIT REASON")
print("=" * 80)

exit_reason_stats = defaultdict(lambda: {"trades": [], "wins": [], "losses": []})
for trade in trades:
    reason = trade["exit_reason"] or "unknown"
    exit_reason_stats[reason]["trades"].append(trade)
    if trade["pnl_pct"] > 0:
        exit_reason_stats[reason]["wins"].append(trade)
    elif trade["pnl_pct"] < 0:
        exit_reason_stats[reason]["losses"].append(trade)

for reason, stats in sorted(exit_reason_stats.items()):
    trades_list = stats["trades"]
    wins_list = stats["wins"]
    losses_list = stats["losses"]
    
    total_pnl = sum(t["pnl_pct"] for t in trades_list)
    win_rate = len(wins_list) / len(trades_list) * 100 if trades_list else 0
    
    print(f"\n{reason.upper()}:")
    print(f"  Trades: {len(trades_list)}")
    print(f"  Win Rate: {win_rate:.1f}% ({len(wins_list)}W/{len(losses_list)}L)")
    print(f"  Total PnL: {total_pnl:.3f}%")
    if wins_list:
        avg_win = sum(t["pnl_pct"] for t in wins_list) / len(wins_list)
        print(f"  Avg Win: {avg_win:.3f}%")
    if losses_list:
        avg_loss = sum(t["pnl_pct"] for t in losses_list) / len(losses_list)
        print(f"  Avg Loss: {avg_loss:.3f}%")
print()

# ==================== Best/Worst Trades ====================
print("=" * 80)
print("BEST/WORST TRADES")
print("=" * 80)

sorted_trades = sorted(trades, key=lambda t: t["pnl_pct"], reverse=True)
print("\nTop 5 Best Trades:")
for i, trade in enumerate(sorted_trades[:5], 1):
    exit_dt = datetime.fromtimestamp(trade["exit_time"])
    print(f"  {i}. {trade['strategy']} {trade['side']:5} {trade['pnl_pct']:>7.2f}% "
          f"({trade['exit_reason']}) - {exit_dt.strftime('%Y-%m-%d %H:%M:%S')}")

print("\nTop 5 Worst Trades:")
for i, trade in enumerate(sorted_trades[-5:], 1):
    exit_dt = datetime.fromtimestamp(trade["exit_time"])
    print(f"  {i}. {trade['strategy']} {trade['side']:5} {trade['pnl_pct']:>7.2f}% "
          f"({trade['exit_reason']}) - {exit_dt.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ==================== Recent Performance Trend ====================
print("=" * 80)
print("RECENT PERFORMANCE TREND")
print("=" * 80)

# Last 10 trades
recent_10 = trades[:10]
recent_pnl = sum(t["pnl_pct"] for t in recent_10)
recent_wins = len([t for t in recent_10 if t["pnl_pct"] > 0])
print(f"Last 10 trades: {recent_wins}W/{len(recent_10)-recent_wins}L, PnL: {recent_pnl:.3f}%")

# Last 20 trades
recent_20 = trades[:20]
recent_pnl_20 = sum(t["pnl_pct"] for t in recent_20)
recent_wins_20 = len([t for t in recent_20 if t["pnl_pct"] > 0])
print(f"Last 20 trades: {recent_wins_20}W/{len(recent_20)-recent_wins_20}L, PnL: {recent_pnl_20:.3f}%")
print()

# ==================== Recommendations ====================
print("=" * 80)
print("OPTIMIZATION RECOMMENDATIONS")
print("=" * 80)

recommendations = []

# Check R:R ratio
if wins and losses:
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins)
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses)
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    if rr_ratio < 1.0:
        recommendations.append(f"⚠️  Risk/Reward ratio is {rr_ratio:.2f}:1 (target >1.0). Consider:")
        recommendations.append("   - Widen take profit targets")
        recommendations.append("   - Tighten stop loss levels")
        recommendations.append("   - Improve entry quality to increase average win size")

# Check exit reasons
if exit_reason_stats.get("stop_loss", {}).get("trades"):
    sl_trades = exit_reason_stats["stop_loss"]["trades"]
    sl_win_rate = len(exit_reason_stats["stop_loss"]["wins"]) / len(sl_trades) * 100
    if sl_win_rate < 30:
        recommendations.append(f"⚠️  Stop loss win rate is {sl_win_rate:.1f}%. Consider:")
        recommendations.append("   - Widening stop loss to reduce premature exits")
        recommendations.append("   - Improving entry timing to avoid false signals")

# Check strategy performance
for strategy, stats in strategy_stats.items():
    if len(stats["trades"]) >= 5:  # Only analyze if enough data
        win_rate = len(stats["wins"]) / len(stats["trades"]) * 100
        total_pnl = sum(t["pnl_pct"] for t in stats["trades"])
        
        if win_rate < 50 and total_pnl < 0:
            recommendations.append(f"⚠️  {strategy} underperforming: {win_rate:.1f}% WR, {total_pnl:.3f}% PnL")
            recommendations.append("   - Review entry conditions")
            recommendations.append("   - Consider tightening filters")

if not recommendations:
    recommendations.append("✅ No major issues detected. Continue monitoring.")

for rec in recommendations:
    print(rec)
print()

conn.close()
print("=" * 80)
print("Analysis complete")
print("=" * 80)

