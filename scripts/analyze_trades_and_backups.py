#!/usr/bin/env python3
"""
Analyze trades and investigate backup size.
Combines comprehensive trade analysis with backup investigation.
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

db_path = os.environ.get("PNL_DB_PATH")
if db_path is None:
    for path in ["/data/pnl_trades.db", "/persist/pnl_trades.db", "pnl_trades.db"]:
        if os.path.exists(path):
            db_path = path
            break
    if db_path is None:
        db_path = "/data/pnl_trades.db"

print("=" * 80)
print("COMPREHENSIVE TRADE ANALYSIS + BACKUP INVESTIGATION")
print("=" * 80)
print(f"Database: {db_path}")
print()

if not os.path.exists(db_path):
    print(f"❌ Database not found at {db_path}")
    sys.exit(1)

# ==================== BACKUP INVESTIGATION ====================
print("=" * 80)
print("BACKUP INVESTIGATION")
print("=" * 80)

backup_dir = os.path.join(os.path.dirname(db_path), "backups")
backup_size = 0
backup_count = 0
backup_files = []

if os.path.exists(backup_dir):
    for file in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            backup_size += size
            backup_count += 1
            backup_files.append((file, size, os.path.getmtime(file_path)))
    
    backup_files.sort(key=lambda x: x[2], reverse=True)  # Sort by mtime
    
    print(f"Backup directory: {backup_dir}")
    print(f"Number of backups: {backup_count}")
    print(f"Total backup size: {backup_size:,} bytes ({backup_size / 1024 / 1024:.2f} MB)")
    print()
    
    if backup_files:
        print("Backup files (newest first):")
        for file, size, mtime in backup_files[:10]:
            dt = datetime.fromtimestamp(mtime)
            print(f"  {file:40} {size:>12,} bytes ({size / 1024 / 1024:>6.2f} MB) - {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        if len(backup_files) > 10:
            print(f"  ... and {len(backup_files) - 10} more")
else:
    print(f"Backup directory not found: {backup_dir}")

print()

# ==================== DATABASE FILE SIZES ====================
print("=" * 80)
print("DATABASE FILE SIZES")
print("=" * 80)

db_size = os.path.getsize(db_path)
wal_size = 0
wal_path = db_path + "-wal"
shm_size = 0
shm_path = db_path + "-shm"

if os.path.exists(wal_path):
    wal_size = os.path.getsize(wal_path)
if os.path.exists(shm_path):
    shm_size = os.path.getsize(shm_path)

total_db_size = db_size + wal_size + shm_size

print(f"Main DB file: {db_size:,} bytes ({db_size / 1024 / 1024:.2f} MB)")
if wal_size > 0:
    print(f"WAL file:     {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
if shm_size > 0:
    print(f"SHM file:     {shm_size:,} bytes ({shm_size / 1024 / 1024:.2f} MB)")
print(f"Total DB:     {total_db_size:,} bytes ({total_db_size / 1024 / 1024:.2f} MB)")
print(f"Backups:      {backup_size:,} bytes ({backup_size / 1024 / 1024:.2f} MB)")
print(f"Grand Total:  {total_db_size + backup_size:,} bytes ({(total_db_size + backup_size) / 1024 / 1024:.2f} MB)")
print()

# ==================== TRADE ANALYSIS ====================
print("=" * 80)
print("COMPREHENSIVE TRADE ANALYSIS")
print("=" * 80)

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
    conn.close()
    sys.exit(0)

print(f"Total trades: {len(trades)}")
print()

# Overall stats
total_pnl = sum(t["pnl_pct"] for t in trades)
wins = [t for t in trades if t["pnl_pct"] > 0]
losses = [t for t in trades if t["pnl_pct"] < 0]

print("OVERALL STATISTICS:")
print(f"  Total PnL: {total_pnl:.3f}%")
print(f"  Win Rate: {len(wins)}/{len(trades)} ({len(wins)/len(trades)*100:.1f}%)")
print(f"  Wins: {len(wins)}, Losses: {len(losses)}")
if wins:
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins)
    print(f"  Avg Win: {avg_win:.3f}%")
if losses:
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses)
    print(f"  Avg Loss: {avg_loss:.3f}%")
    if wins:
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        print(f"  R:R Ratio: {rr_ratio:.2f}:1")
print()

# By strategy
print("BY STRATEGY:")
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
    
    print(f"\n  {strategy.upper()}:")
    print(f"    Trades: {len(trades_list)}")
    print(f"    Win Rate: {win_rate:.1f}% ({len(wins_list)}W/{len(losses_list)}L)")
    print(f"    Total PnL: {total_pnl:.3f}%")
    if wins_list:
        avg_win = sum(t["pnl_pct"] for t in wins_list) / len(wins_list)
        print(f"    Avg Win: {avg_win:.3f}%")
    if losses_list:
        avg_loss = sum(t["pnl_pct"] for t in losses_list) / len(losses_list)
        print(f"    Avg Loss: {avg_loss:.3f}%")
        if wins_list:
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            print(f"    R:R Ratio: {rr:.2f}:1")
print()

# By exit reason
print("BY EXIT REASON:")
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
    
    if len(trades_list) < 5:  # Skip if too few trades
        continue
    
    total_pnl = sum(t["pnl_pct"] for t in trades_list)
    win_rate = len(wins_list) / len(trades_list) * 100 if trades_list else 0
    
    print(f"\n  {reason.upper()}:")
    print(f"    Trades: {len(trades_list)}")
    print(f"    Win Rate: {win_rate:.1f}% ({len(wins_list)}W/{len(losses_list)}L)")
    print(f"    Total PnL: {total_pnl:.3f}%")
print()

# Recent performance
print("RECENT PERFORMANCE:")
recent_20 = trades[:20]
recent_pnl = sum(t["pnl_pct"] for t in recent_20)
recent_wins = len([t for t in recent_20 if t["pnl_pct"] > 0])
print(f"  Last 20 trades: {recent_wins}W/{len(recent_20)-recent_wins}L, PnL: {recent_pnl:.3f}%")

recent_50 = trades[:50]
recent_pnl_50 = sum(t["pnl_pct"] for t in recent_50)
recent_wins_50 = len([t for t in recent_50 if t["pnl_pct"] > 0])
print(f"  Last 50 trades: {recent_wins_50}W/{len(recent_50)-recent_wins_50}L, PnL: {recent_pnl_50:.3f}%")
print()

conn.close()

# ==================== RECOMMENDATIONS ====================
print("=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

recommendations = []

# Backup recommendations
if backup_count > 5:
    recommendations.append(f"⚠️  BACKUP SIZE: {backup_count} backups taking {backup_size / 1024 / 1024:.2f} MB")
    recommendations.append(f"   Recommendation: Reduce max_backups from 10 to 3-5 (saves ~{(backup_count - 5) * db_size / 1024 / 1024:.2f} MB)")
    recommendations.append(f"   Trade data is safe - we only need recent backups for recovery")

# Strategy recommendations
if wins and losses:
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins)
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses)
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    
    if rr_ratio < 1.0:
        recommendations.append(f"⚠️  Risk/Reward ratio is {rr_ratio:.2f}:1 (target >1.0)")
        recommendations.append("   - Widen take profit targets")
        recommendations.append("   - Tighten stop loss levels")
        recommendations.append("   - Improve entry quality")

# Strategy-specific
for strategy, stats in strategy_stats.items():
    if len(stats["trades"]) >= 10:
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
print("=" * 80)
print("Analysis complete")
print("=" * 80)

