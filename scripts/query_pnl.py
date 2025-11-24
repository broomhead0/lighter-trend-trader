#!/usr/bin/env python3
"""
Query PnL database for analysis.

Usage:
    python scripts/query_pnl.py                    # Overall stats
    python scripts/query_pnl.py --strategy mean_reversion  # By strategy
    python scripts/query_pnl.py --since 24h        # Last 24 hours
    python scripts/query_pnl.py --export csv        # Export to CSV
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.pnl_tracker import PnLTracker


def parse_time_ago(time_str: str) -> Optional[float]:
    """Parse time strings like '24h', '7d', '30d' into Unix timestamp."""
    if not time_str:
        return None

    time_str = time_str.lower().strip()

    if time_str.endswith('h'):
        hours = int(time_str[:-1])
        return (datetime.now() - timedelta(hours=hours)).timestamp()
    elif time_str.endswith('d'):
        days = int(time_str[:-1])
        return (datetime.now() - timedelta(days=days)).timestamp()
    elif time_str.endswith('m'):
        minutes = int(time_str[:-1])
        return (datetime.now() - timedelta(minutes=minutes)).timestamp()
    else:
        try:
            # Try parsing as hours
            hours = int(time_str)
            return (datetime.now() - timedelta(hours=hours)).timestamp()
        except ValueError:
            return None


def format_stats(stats: dict) -> None:
    """Format and print statistics."""
    print("=" * 60)
    print("PnL Analysis")
    print("=" * 60)
    print()

    print(f"Total Trades: {stats['total_trades']}")
    print(f"Win Rate: {stats['win_rate']:.1f}% ({stats['wins']} wins, {stats['losses']} losses)")
    print(f"Total PnL: {stats['total_pnl_pct']:.2f}%")
    print(f"Total PnL (USD): ${stats['total_pnl_usd']:.2f}")
    print(f"Avg PnL per Trade: {stats['avg_pnl_pct']:.2f}%")

    if stats['avg_win_pct'] > 0:
        print(f"Avg Win: {stats['avg_win_pct']:.2f}%")
    if stats['avg_loss_pct'] < 0:
        print(f"Avg Loss: {stats['avg_loss_pct']:.2f}%")

    if stats['avg_loss_pct'] != 0:
        rr_ratio = abs(stats['avg_win_pct'] / stats['avg_loss_pct'])
        print(f"R:R Ratio: {rr_ratio:.2f}")

    if stats['best_trade_pct'] > 0:
        print(f"Best Trade: {stats['best_trade_pct']:.2f}%")
    if stats['worst_trade_pct'] < 0:
        print(f"Worst Trade: {stats['worst_trade_pct']:.2f}%")

    print()


async def main():
    parser = argparse.ArgumentParser(description="Query PnL database")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to PnL database (default: auto-detect from PNL_DB_PATH or /data/pnl_trades.db)",
    )
    parser.add_argument(
        "--strategy",
        choices=["mean_reversion", "renko_ao", "breakout"],
        help="Filter by strategy",
    )
    parser.add_argument(
        "--since",
        help="Time period (e.g., '24h', '7d', '30d')",
    )
    parser.add_argument(
        "--export",
        choices=["csv", "json"],
        help="Export format",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout or pnl_export.csv/json)",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=0,
        help="Show N most recent trades",
    )

    args = parser.parse_args()

    # Auto-detect database path
    if args.db_path is None:
        args.db_path = os.environ.get("PNL_DB_PATH")
        if args.db_path is None:
            # Try common paths
            for path in ["/data/pnl_trades.db", "/persist/pnl_trades.db", "pnl_trades.db"]:
                if os.path.exists(path):
                    args.db_path = path
                    break
            if args.db_path is None:
                args.db_path = "/data/pnl_trades.db"  # Default for Railway

    # Initialize tracker
    tracker = PnLTracker(db_path=args.db_path)

    # Parse since_time
    since_time = parse_time_ago(args.since) if args.since else None

    # Get stats
    stats = await tracker.get_stats(
        strategy=args.strategy,
        since_time=since_time,
    )

    if args.export:
        # Export trades
        if args.strategy or since_time:
            # Need to query specific trades
            conn = sqlite3.connect(args.db_path)
            cursor = conn.cursor()

            conditions = []
            params = []

            if args.strategy:
                conditions.append("strategy = ?")
                params.append(args.strategy)
            if since_time:
                conditions.append("exit_time >= ?")
                params.append(since_time)

            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

            cursor.execute(f"""
                SELECT * FROM trades
                {where_clause}
                ORDER BY exit_time DESC
            """, params)

            columns = [desc[0] for desc in cursor.execute("PRAGMA table_info(trades)").fetchall()]
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
        else:
            trades = await tracker.get_recent_trades(limit=10000)  # Get all

        if args.export == "csv":
            output_path = args.output or "pnl_export.csv"
            with open(output_path, "w", newline="") as f:
                if trades:
                    writer = csv.DictWriter(f, fieldnames=trades[0].keys())
                    writer.writeheader()
                    writer.writerows(trades)
            print(f"Exported {len(trades)} trades to {output_path}")
        elif args.export == "json":
            import json
            output_path = args.output or "pnl_export.json"
            with open(output_path, "w") as f:
                json.dump(trades, f, indent=2)
            print(f"Exported {len(trades)} trades to {output_path}")
    elif args.recent > 0:
        # Show recent trades
        trades = await tracker.get_recent_trades(limit=args.recent)
        print(f"=== RECENT {args.recent} TRADES ===")
        print()
        for trade in trades:
            exit_dt = datetime.fromtimestamp(trade['exit_time']).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"{exit_dt} | {trade['strategy']} | {trade['side']} | "
                f"Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f} | "
                f"PnL: {trade['pnl_pct']:.2f}% | {trade['exit_reason']}"
            )
    else:
        # Show stats
        format_stats(stats)

        # Show breakdown by strategy if not filtering
        if not args.strategy:
            print("=== BY STRATEGY ===")
            for strategy in ["mean_reversion", "renko_ao", "breakout"]:
                strat_stats = await tracker.get_stats(strategy=strategy, since_time=since_time)
                if strat_stats['total_trades'] > 0:
                    print(f"\n{strategy}:")
                    format_stats(strat_stats)

        # Show breakdown by exit reason
        conn = sqlite3.connect(args.db_path)
        cursor = conn.cursor()

        conditions = []
        params = []

        if args.strategy:
            conditions.append("strategy = ?")
            params.append(args.strategy)
        if since_time:
            conditions.append("exit_time >= ?")
            params.append(since_time)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor.execute(f"""
            SELECT exit_reason,
                   COUNT(*) as count,
                   SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(pnl_pct) as total_pnl
            FROM trades
            {where_clause}
            GROUP BY exit_reason
            ORDER BY count DESC
        """, params)

        print("=== BY EXIT REASON ===")
        for row in cursor.fetchall():
            reason, count, wins, total_pnl = row
            win_rate = (wins / count * 100) if count > 0 else 0
            print(f"{reason}: {count} trades, {win_rate:.1f}% win rate, {total_pnl:.2f}% total PnL")

        conn.close()

    tracker.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
