#!/usr/bin/env python3
"""
Query PnL statistics from the database.

Supports high-volume queries (100k+ trades) with fast aggregation.

Usage:
    python scripts/query_pnl.py [--strategy mean_reversion|renko_ao] [--since-hours 24]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.pnl_tracker import PnLTracker


def parse_args():
    parser = argparse.ArgumentParser(description="Query PnL statistics")
    parser.add_argument(
        "--db-path",
        default="pnl_trades.db",
        help="Path to PnL database (default: pnl_trades.db)",
    )
    parser.add_argument(
        "--strategy",
        choices=["mean_reversion", "renko_ao"],
        help="Filter by strategy",
    )
    parser.add_argument(
        "--since-hours",
        type=float,
        help="Only show trades from last N hours",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=10,
        help="Show N most recent trades (default: 10)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    tracker = PnLTracker(db_path=args.db_path)

    try:
        # Get stats
        since_time = None
        if args.since_hours:
            since_time = time.time() - (args.since_hours * 3600)

        stats = await tracker.get_stats(
            strategy=args.strategy,
            since_time=since_time,
        )

        print("=" * 60)
        print("PnL Statistics")
        print("=" * 60)
        print()

        if args.strategy:
            print(f"Strategy: {args.strategy}")
        if args.since_hours:
            print(f"Time Period: Last {args.since_hours} hours")
        print()

        if stats.get("total_trades", 0) == 0:
            print("No trades found.")
            return

        print(f"Total Trades: {stats['total_trades']}")
        print(f"Wins: {stats['wins']} ({stats['win_rate']:.1f}%)")
        print(f"Losses: {stats['losses']}")
        print()
        print(f"Total PnL: {stats['total_pnl_pct']:.4f}% (${stats['total_pnl_usd']:.2f} USD)")
        print(f"Average PnL: {stats['avg_pnl_pct']:.4f}% per trade")
        print()
        print(f"Average Win: {stats['avg_win_pct']:.4f}%")
        print(f"Average Loss: {stats['avg_loss_pct']:.4f}%")
        print()
        print(f"Best Trade: {stats['best_trade_pct']:.4f}%")
        print(f"Worst Trade: {stats['worst_trade_pct']:.4f}%")
        print()

        # Show recent trades
        print("=" * 60)
        print(f"Recent Trades (Last {args.recent})")
        print("=" * 60)
        print()

        recent = await tracker.get_recent_trades(limit=args.recent)
        if recent:
            print(f"{'Strategy':<15} {'Side':<6} {'Entry':<10} {'Exit':<10} {'PnL %':<10} {'Reason':<15}")
            print("-" * 70)
            for trade in recent:
                entry_time = time.strftime("%H:%M:%S", time.localtime(trade["entry_time"]))
                exit_time = time.strftime("%H:%M:%S", time.localtime(trade["exit_time"]))
                pnl_str = f"{trade['pnl_pct']:+.4f}%"
                print(f"{trade['strategy']:<15} {trade['side']:<6} {entry_time:<10} {exit_time:<10} {pnl_str:<10} {trade['exit_reason']:<15}")
        else:
            print("No recent trades.")

    finally:
        tracker.close()


if __name__ == "__main__":
    asyncio.run(main())

