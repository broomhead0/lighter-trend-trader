#!/usr/bin/env python3
"""Focused PnL Analysis - Maximize Profitability"""
import os
import sqlite3
import sys
from pathlib import Path

db_path = os.environ.get("PNL_DB_PATH")
if db_path is None:
    for path in ["/data/pnl_trades.db", "/persist/pnl_trades.db", "pnl_trades.db"]:
        if os.path.exists(path):
            db_path = path
            break
    if db_path is None:
        db_path = "/data/pnl_trades.db"

if not os.path.exists(db_path):
    print(f"❌ Database not found")
    sys.exit(1)

conn = sqlite3.connect(db_path, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("PnL ANALYSIS - MAXIMIZE PROFITABILITY")
print("=" * 80)
print()

# Overall stats
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losses,
        SUM(pnl_pct) as total_pnl,
        AVG(pnl_pct) as avg_pnl,
        AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct END) as avg_win,
        AVG(CASE WHEN pnl_pct < 0 THEN pnl_pct END) as avg_loss,
        MAX(pnl_pct) as best_trade,
        MIN(pnl_pct) as worst_trade
    FROM trades
""")
overall = cursor.fetchone()

total = overall["total"]
wins = overall["wins"]
losses = overall["losses"]
total_pnl = overall["total_pnl"] or 0
avg_pnl = overall["avg_pnl"] or 0
avg_win = overall["avg_win"] or 0
avg_loss = overall["avg_loss"] or 0
win_rate = (wins / total * 100) if total > 0 else 0
rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

print("OVERALL PERFORMANCE:")
print(f"  Total Trades: {total:,}")
print(f"  Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
print(f"  Total PnL: {total_pnl:+.3f}%")
print(f"  Avg PnL per Trade: {avg_pnl:+.3f}%")
print(f"  Avg Win: {avg_win:+.3f}%")
print(f"  Avg Loss: {avg_loss:.3f}%")
print(f"  Risk/Reward: {rr_ratio:.2f}:1")
print(f"  Best Trade: {overall['best_trade']:+.3f}%")
print(f"  Worst Trade: {overall['worst_trade']:.3f}%")
print()

# By strategy
print("BY STRATEGY:")
cursor.execute("""
    SELECT 
        strategy,
        COUNT(*) as total,
        SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losses,
        SUM(pnl_pct) as total_pnl,
        AVG(pnl_pct) as avg_pnl,
        AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct END) as avg_win,
        AVG(CASE WHEN pnl_pct < 0 THEN pnl_pct END) as avg_loss
    FROM trades
    GROUP BY strategy
    ORDER BY total_pnl DESC
""")

for row in cursor.fetchall():
    strategy = row["strategy"]
    s_total = row["total"]
    s_wins = row["wins"]
    s_losses = row["losses"]
    s_total_pnl = row["total_pnl"] or 0
    s_avg_pnl = row["avg_pnl"] or 0
    s_avg_win = row["avg_win"] or 0
    s_avg_loss = row["avg_loss"] or 0
    s_win_rate = (s_wins / s_total * 100) if s_total > 0 else 0
    s_rr = abs(s_avg_win / s_avg_loss) if s_avg_loss != 0 else 0
    
    print(f"\n  {strategy.upper()}:")
    print(f"    Trades: {s_total:,} | Win Rate: {s_win_rate:.1f}% ({s_wins}W/{s_losses}L)")
    print(f"    Total PnL: {s_total_pnl:+.3f}% | Avg: {s_avg_pnl:+.3f}%")
    print(f"    Avg Win: {s_avg_win:+.3f}% | Avg Loss: {s_avg_loss:.3f}%")
    print(f"    R:R: {s_rr:.2f}:1")
print()

# By exit reason
print("BY EXIT REASON:")
cursor.execute("""
    SELECT 
        exit_reason,
        COUNT(*) as total,
        SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
        SUM(pnl_pct) as total_pnl,
        AVG(pnl_pct) as avg_pnl
    FROM trades
    WHERE exit_reason IS NOT NULL
    GROUP BY exit_reason
    HAVING COUNT(*) >= 5
    ORDER BY total_pnl DESC
""")

for row in cursor.fetchall():
    reason = row["exit_reason"]
    r_total = row["total"]
    r_wins = row["wins"]
    r_total_pnl = row["total_pnl"] or 0
    r_avg_pnl = row["avg_pnl"] or 0
    r_win_rate = (r_wins / r_total * 100) if r_total > 0 else 0
    
    print(f"  {reason:20} {r_total:>4} trades | {r_win_rate:>5.1f}% WR | {r_total_pnl:>+7.3f}% total | {r_avg_pnl:>+6.3f}% avg")
print()

# Recent performance
print("RECENT PERFORMANCE:")
for period in [10, 20, 50, 100]:
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
            SUM(pnl_pct) as total_pnl,
            AVG(pnl_pct) as avg_pnl
        FROM (
            SELECT pnl_pct FROM trades ORDER BY exit_time DESC LIMIT ?
        )
    """, (period,))
    recent = cursor.fetchone()
    if recent["total"] > 0:
        r_wins = recent["wins"]
        r_total = recent["total"]
        r_total_pnl = recent["total_pnl"] or 0
        r_avg_pnl = recent["avg_pnl"] or 0
        r_wr = (r_wins / r_total * 100) if r_total > 0 else 0
        print(f"  Last {period:3} trades: {r_wins}W/{r_total-r_wins}L ({r_wr:.1f}% WR) | {r_total_pnl:+.3f}% total | {r_avg_pnl:+.3f}% avg")
print()

# PnL Maximization Recommendations
print("=" * 80)
print("PnL MAXIMIZATION RECOMMENDATIONS")
print("=" * 80)
print()

recommendations = []

if total_pnl < 0:
    recommendations.append(f"⚠️  CRITICAL: Total PnL is NEGATIVE ({total_pnl:.3f}%)")
    recommendations.append("   - Strategy needs immediate review")
    recommendations.append("   - Consider pausing trading until fixed")

if win_rate < 50:
    recommendations.append(f"⚠️  Win rate is {win_rate:.1f}% (target: >50%)")
    recommendations.append("   - Tighten entry filters to improve quality")
    recommendations.append("   - Review exit conditions (too many premature exits?)")

if rr_ratio < 1.0:
    recommendations.append(f"⚠️  Risk/Reward is {rr_ratio:.2f}:1 (target: >1.0)")
    recommendations.append("   - Widen take profit targets")
    recommendations.append("   - Tighten stop losses")
    recommendations.append("   - Current: Avg win {avg_win:.3f}% vs Avg loss {avg_loss:.3f}%")

# Strategy-specific
cursor.execute("""
    SELECT strategy, SUM(pnl_pct) as total_pnl, COUNT(*) as total
    FROM trades
    GROUP BY strategy
    ORDER BY total_pnl DESC
""")
strategy_pnl = cursor.fetchall()

best_strategy = strategy_pnl[0] if strategy_pnl else None
worst_strategy = strategy_pnl[-1] if len(strategy_pnl) > 1 else None

if best_strategy:
    recommendations.append(f"✅ Best Strategy: {best_strategy['strategy']} ({best_strategy['total_pnl']:+.3f}% PnL, {best_strategy['total']} trades)")
    recommendations.append("   - Focus on this strategy, scale up if profitable")

if worst_strategy and worst_strategy['total_pnl'] < 0:
    recommendations.append(f"⚠️  Worst Strategy: {worst_strategy['strategy']} ({worst_strategy['total_pnl']:.3f}% PnL)")
    recommendations.append("   - Review entry/exit conditions")
    recommendations.append("   - Consider disabling if consistently unprofitable")

# Exit reason analysis
cursor.execute("""
    SELECT exit_reason, AVG(pnl_pct) as avg_pnl, COUNT(*) as total
    FROM trades
    WHERE exit_reason IS NOT NULL
    GROUP BY exit_reason
    HAVING COUNT(*) >= 10
    ORDER BY avg_pnl DESC
""")
exit_reasons = cursor.fetchall()

if exit_reasons:
    best_exit = exit_reasons[0]
    worst_exit = exit_reasons[-1]
    
    recommendations.append(f"✅ Best Exit: {best_exit['exit_reason']} ({best_exit['avg_pnl']:+.3f}% avg, {best_exit['total']} trades)")
    recommendations.append(f"⚠️  Worst Exit: {worst_exit['exit_reason']} ({worst_exit['avg_pnl']:.3f}% avg, {worst_exit['total']} trades)")
    if worst_exit['avg_pnl'] < -0.05:
        recommendations.append("   - This exit reason is losing money, review logic")

if not recommendations:
    recommendations.append("✅ No major issues - continue current approach")

for rec in recommendations:
    print(rec)

print()
print("=" * 80)

conn.close()

