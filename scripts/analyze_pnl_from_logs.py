#!/usr/bin/env python3
"""
Analyze PnL from Railway logs.
Parses LIVE PnL entries and provides statistics and recommendations.
"""
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Trade:
    strategy: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl_pct: float
    exit_reason: str
    timestamp: str

def parse_logs() -> List[Trade]:
    """Parse Railway logs for PnL data."""
    try:
        result = subprocess.run(
            ["railway", "logs", "--tail", "10000"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        logs = result.stdout + result.stderr
    except Exception as e:
        print(f"Error fetching logs: {e}", file=sys.stderr)
        return []

    trades = []
    # Pattern: LIVE PnL: X.XX% (entry=Y.YY, exit=Z.ZZ, size=0.XXXX)
    # Log format: timestamp [INFO] [strategy] LIVE PnL: X.XX% (entry=Y.YY, exit=Z.ZZ, size=0.XXXX)
    # We need to match the exiting position line first, then the LIVE PnL line

    lines = logs.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for LIVE PnL line (it contains all the info we need)
        # Format: 2025-11-15 16:50:38,248 [INFO] [mean_reversion] [mean_reversion] LIVE PnL: -0.03% (entry=142.31, exit=142.27, size=0.1000)
        pnl_match = re.search(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?LIVE PnL: ([\d.+-]+)% \(entry=([\d.]+), exit=([\d.]+), size=([\d.]+)\)',
            line
        )
        if pnl_match:
            timestamp, pnl_pct, entry_price, exit_price, size = pnl_match.groups()
            # Extract strategy from line
            strategy = "unknown"
            if "mean_reversion" in line:
                strategy = "mean_reversion"
            elif "renko_ao" in line:
                strategy = "renko_ao"
            # Look backwards for exit reason (should be on previous line)
            reason = "unknown"
            for j in range(max(0, i-5), i):
                exit_match = re.search(
                    r'exiting position: side=(\w+) entry=([\d.]+) reason=(\w+)',
                    lines[j]
                )
                if exit_match and abs(float(exit_match.group(2)) - float(entry_price)) < 0.01:
                    reason = exit_match.group(3)
                    side = exit_match.group(1)
                    break

            trades.append(Trade(
                strategy=strategy,
                side=side if 'side' in locals() else "unknown",
                entry_price=float(entry_price),
                exit_price=float(exit_price),
                size=float(size),
                pnl_pct=float(pnl_pct),
                exit_reason=reason,
                timestamp=timestamp,
            ))
        i += 1

    return trades

def analyze_trades(trades: List[Trade]) -> dict:
    """Analyze trades and return statistics."""
    if not trades:
        return {}

    total_trades = len(trades)
    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct < 0]
    breakeven = [t for t in trades if t.pnl_pct == 0]

    total_pnl_pct = sum(t.pnl_pct for t in trades)
    avg_pnl_pct = total_pnl_pct / total_trades if total_trades > 0 else 0

    # By strategy
    by_strategy = defaultdict(list)
    for t in trades:
        by_strategy[t.strategy].append(t)

    # By exit reason
    by_reason = defaultdict(list)
    for t in trades:
        by_reason[t.exit_reason].append(t)

    # Calculate stats per strategy
    strategy_stats = {}
    for strategy, strategy_trades in by_strategy.items():
        strategy_wins = [t for t in strategy_trades if t.pnl_pct > 0]
        strategy_losses = [t for t in strategy_trades if t.pnl_pct < 0]
        strategy_pnl = sum(t.pnl_pct for t in strategy_trades)

        strategy_stats[strategy] = {
            "total": len(strategy_trades),
            "wins": len(strategy_wins),
            "losses": len(strategy_losses),
            "win_rate": (len(strategy_wins) / len(strategy_trades) * 100) if strategy_trades else 0,
            "total_pnl_pct": strategy_pnl,
            "avg_pnl_pct": strategy_pnl / len(strategy_trades) if strategy_trades else 0,
            "avg_win": sum(t.pnl_pct for t in strategy_wins) / len(strategy_wins) if strategy_wins else 0,
            "avg_loss": sum(t.pnl_pct for t in strategy_losses) / len(strategy_losses) if strategy_losses else 0,
        }

    # Calculate stats per exit reason
    reason_stats = {}
    for reason, reason_trades in by_reason.items():
        reason_wins = [t for t in reason_trades if t.pnl_pct > 0]
        reason_losses = [t for t in reason_trades if t.pnl_pct < 0]
        reason_pnl = sum(t.pnl_pct for t in reason_trades)

        reason_stats[reason] = {
            "total": len(reason_trades),
            "wins": len(reason_wins),
            "losses": len(reason_losses),
            "win_rate": (len(reason_wins) / len(reason_trades) * 100) if reason_trades else 0,
            "total_pnl_pct": reason_pnl,
            "avg_pnl_pct": reason_pnl / len(reason_trades) if reason_trades else 0,
        }

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate": (len(wins) / total_trades * 100) if total_trades > 0 else 0,
        "total_pnl_pct": total_pnl_pct,
        "avg_pnl_pct": avg_pnl_pct,
        "avg_win": sum(t.pnl_pct for t in wins) / len(wins) if wins else 0,
        "avg_loss": sum(t.pnl_pct for t in losses) / len(losses) if losses else 0,
        "best_trade": max(trades, key=lambda t: t.pnl_pct).pnl_pct if trades else 0,
        "worst_trade": min(trades, key=lambda t: t.pnl_pct).pnl_pct if trades else 0,
        "strategy_stats": strategy_stats,
        "reason_stats": reason_stats,
        "trades": trades,
    }

def print_analysis(stats: dict):
    """Print analysis and recommendations."""
    if not stats or stats["total_trades"] == 0:
        print("No trades found in logs.")
        return

    print("=" * 70)
    print("PnL Analysis from Live Trading")
    print("=" * 70)
    print()

    print(f"Total Trades: {stats['total_trades']}")
    print(f"Wins: {stats['wins']} ({stats['win_rate']:.1f}%)")
    print(f"Losses: {stats['losses']}")
    print(f"Breakeven: {stats['breakeven']}")
    print()

    print(f"Total PnL: {stats['total_pnl_pct']:+.4f}%")
    print(f"Average PnL per Trade: {stats['avg_pnl_pct']:+.4f}%")
    print()

    if stats['wins'] > 0:
        print(f"Average Win: {stats['avg_win']:+.4f}%")
    if stats['losses'] > 0:
        print(f"Average Loss: {stats['avg_loss']:+.4f}%")
    print()

    print(f"Best Trade: {stats['best_trade']:+.4f}%")
    print(f"Worst Trade: {stats['worst_trade']:+.4f}%")
    print()

    # Strategy breakdown
    print("=" * 70)
    print("By Strategy")
    print("=" * 70)
    for strategy, s_stats in stats['strategy_stats'].items():
        print(f"\n{strategy}:")
        print(f"  Trades: {s_stats['total']}")
        print(f"  Win Rate: {s_stats['win_rate']:.1f}% ({s_stats['wins']}W / {s_stats['losses']}L)")
        print(f"  Total PnL: {s_stats['total_pnl_pct']:+.4f}%")
        print(f"  Avg PnL: {s_stats['avg_pnl_pct']:+.4f}%")
        if s_stats['wins'] > 0:
            print(f"  Avg Win: {s_stats['avg_win']:+.4f}%")
        if s_stats['losses'] > 0:
            print(f"  Avg Loss: {s_stats['avg_loss']:+.4f}%")

    # Exit reason breakdown
    print()
    print("=" * 70)
    print("By Exit Reason")
    print("=" * 70)
    for reason, r_stats in sorted(stats['reason_stats'].items(), key=lambda x: x[1]['total'], reverse=True):
        print(f"\n{reason}:")
        print(f"  Count: {r_stats['total']}")
        print(f"  Win Rate: {r_stats['win_rate']:.1f}%")
        print(f"  Total PnL: {r_stats['total_pnl_pct']:+.4f}%")
        print(f"  Avg PnL: {r_stats['avg_pnl_pct']:+.4f}%")

    # Recommendations
    print()
    print("=" * 70)
    print("Recommendations")
    print("=" * 70)
    print()

    # Check win rate
    if stats['win_rate'] < 50:
        print(f"⚠️  Low win rate ({stats['win_rate']:.1f}%) - Consider:")
        print("   - Tightening entry filters (more selective)")
        print("   - Adjusting stop loss/take profit ratios")
        print("   - Reviewing entry conditions")

    # Check average loss vs win
    if stats['losses'] > 0 and stats['wins'] > 0:
        risk_reward = abs(stats['avg_win'] / stats['avg_loss']) if stats['avg_loss'] != 0 else 0
        if risk_reward < 1.5:
            print(f"⚠️  Poor risk/reward ratio ({risk_reward:.2f}:1) - Consider:")
            print("   - Widening take profit targets")
            print("   - Tightening stop losses")
            print("   - Improving entry timing")

    # Check exit reasons
    stop_loss_count = stats['reason_stats'].get('stop_loss', {}).get('total', 0)
    take_profit_count = stats['reason_stats'].get('take_profit', {}).get('total', 0)
    time_stop_count = stats['reason_stats'].get('time_stop', {}).get('total', 0)

    if stop_loss_count > take_profit_count * 2:
        print(f"⚠️  Too many stop losses ({stop_loss_count}) vs take profits ({take_profit_count})")
        print("   - Consider wider stop losses or better entry timing")

    if time_stop_count > stats['total_trades'] * 0.3:
        print(f"⚠️  High time stop rate ({time_stop_count}/{stats['total_trades']})")
        print("   - Consider longer max hold time or more aggressive exits")

    # Strategy-specific recommendations
    for strategy, s_stats in stats['strategy_stats'].items():
        if s_stats['total_pnl_pct'] < 0:
            print(f"⚠️  {strategy} is losing money ({s_stats['total_pnl_pct']:+.4f}%)")
            print(f"   - Review entry/exit logic for this strategy")
            print(f"   - Consider disabling or adjusting parameters")

    print()

if __name__ == "__main__":
    print("Fetching logs and analyzing PnL...")
    trades = parse_logs()
    stats = analyze_trades(trades)
    print_analysis(stats)

