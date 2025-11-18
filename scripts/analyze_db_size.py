#!/usr/bin/env python3
"""
Analyze Database Size Breakdown

Shows what's taking up space in the database and what's necessary vs not.
"""

import os
import sqlite3
import sys
from collections import defaultdict

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("DATABASE SIZE ANALYSIS")
print("=" * 80)
print(f"Database path: {db_path}")
print()

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    sys.exit(1)

# Get file sizes
file_size = os.path.getsize(db_path)
wal_size = 0
wal_path = db_path + "-wal"
shm_size = 0
shm_path = db_path + "-shm"
if os.path.exists(wal_path):
    wal_size = os.path.getsize(wal_path)
if os.path.exists(shm_path):
    shm_size = os.path.getsize(shm_path)
total_size = file_size + wal_size + shm_size

print(f"Main database file: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
if wal_size > 0:
    print(f"WAL file (-wal):     {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
if shm_size > 0:
    print(f"SHM file (-shm):     {shm_size:,} bytes ({shm_size / 1024 / 1024:.2f} MB)")
print(f"Total size:           {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
print()

# Connect and analyze
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("TABLE SIZES (approximate)")
    print("=" * 80)

    # Get table sizes using page count
    tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]
    table_sizes = {}

    for table in tables:
        try:
            # Get row count
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            row_count = cursor.fetchone()["count"]

            # Get page count (approximate size)
            cursor = conn.execute(f"SELECT COUNT(*) as pages FROM pragma_page_count() WHERE name = '{table}'")
            # Alternative: use sqlite_master to get info
            cursor = conn.execute(f"""
                SELECT
                    (SELECT COUNT(*) FROM {table}) as row_count,
                    (SELECT page_count FROM pragma_page_count()) as pages
            """)
            result = cursor.fetchone()

            # Estimate size: each row is roughly 100-500 bytes depending on table
            # Use actual row count and estimate
            if row_count > 0:
                # Sample a few rows to estimate average size
                cursor = conn.execute(f"SELECT * FROM {table} LIMIT 10")
                sample_rows = cursor.fetchall()
                if sample_rows:
                    # Rough estimate: count columns and estimate data size
                    avg_row_size = len(sample_rows[0].keys()) * 50  # rough estimate
                    estimated_size = row_count * avg_row_size
                else:
                    estimated_size = row_count * 200  # default estimate
            else:
                estimated_size = 0

            table_sizes[table] = {
                "rows": row_count,
                "estimated_size": estimated_size
            }

            print(f"{table:20} {row_count:8,} rows  ~{estimated_size / 1024 / 1024:.2f} MB")
        except sqlite3.OperationalError as e:
            print(f"{table:20} {'N/A':8} (table doesn't exist: {e})")
            table_sizes[table] = {"rows": 0, "estimated_size": 0}

    print()

    # Detailed breakdown by strategy
    print("=" * 80)
    print("DETAILED BREAKDOWN BY STRATEGY")
    print("=" * 80)

    # Trades
    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count,
                   AVG(LENGTH(strategy) + LENGTH(side) + LENGTH(exit_reason) + LENGTH(market) + 8*8) as avg_size
            FROM trades
            GROUP BY strategy
            ORDER BY strategy
        """)
        trades_by_strategy = cursor.fetchall()
        if trades_by_strategy:
            print("\nTrades by strategy:")
            total_trade_rows = 0
            for row in trades_by_strategy:
                count = row["count"]
                total_trade_rows += count
                # Estimate: ~200 bytes per trade record
                size_est = count * 200
                print(f"  {row['strategy']:20} {count:6,} trades  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {total_trade_rows:6,} trades")
    except sqlite3.OperationalError:
        print("\nTrades: Table doesn't exist")

    # Candles
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM candles
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        candles_by_strategy = cursor.fetchall()
        if candles_by_strategy:
            print("\nCandles by strategy:")
            total_candle_rows = 0
            for row in candles_by_strategy:
                count = row["count"]
                total_candle_rows += count
                # Estimate: ~100 bytes per candle (OHLCV + metadata)
                size_est = count * 100
                print(f"  {row['strategy']:20} {row['market']:10} {count:6,} candles  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_candle_rows:6,} candles")
    except sqlite3.OperationalError:
        print("\nCandles: Table doesn't exist")

    # Renko Bricks
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM renko_bricks
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        bricks_by_strategy = cursor.fetchall()
        if bricks_by_strategy:
            print("\nRenko Bricks by strategy:")
            total_brick_rows = 0
            for row in bricks_by_strategy:
                count = row["count"]
                total_brick_rows += count
                # Estimate: ~120 bytes per brick
                size_est = count * 120
                print(f"  {row['strategy']:20} {row['market']:10} {count:6,} bricks  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_brick_rows:6,} bricks")
    except sqlite3.OperationalError:
        print("\nRenko Bricks: Table doesn't exist")

    # Price History
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM price_history
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        prices_by_strategy = cursor.fetchall()
        if prices_by_strategy:
            print("\nPrice History by strategy:")
            total_price_rows = 0
            for row in prices_by_strategy:
                count = row["count"]
                total_price_rows += count
                # Estimate: ~50 bytes per price point
                size_est = count * 50
                print(f"  {row['strategy']:20} {row['market']:10} {count:6,} prices  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_price_rows:6,} prices")
    except sqlite3.OperationalError:
        print("\nPrice History: Table doesn't exist")

    # Positions
    try:
        cursor = conn.execute("SELECT COUNT(*) as count FROM positions")
        pos_count = cursor.fetchone()["count"]
        if pos_count > 0:
            print(f"\nOpen Positions: {pos_count} (minimal size)")
    except sqlite3.OperationalError:
        print("\nPositions: Table doesn't exist")

    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Check for old data
    try:
        cursor = conn.execute("""
            SELECT MIN(exit_time) as oldest_trade, MAX(exit_time) as newest_trade, COUNT(*) as count
            FROM trades
        """)
        trade_info = cursor.fetchone()
        if trade_info and trade_info["count"] > 0:
            print(f"\nTrades: {trade_info['count']} total")
            print("  ✅ KEEP: All trades needed for PnL analysis and strategy optimization")
    except:
        pass

    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count, MIN(open_time) as oldest, MAX(open_time) as newest
            FROM candles
            GROUP BY strategy
        """)
        candle_info = cursor.fetchall()
        if candle_info:
            print(f"\nCandles:")
            for row in candle_info:
                print(f"  {row['strategy']}: {row['count']} candles")
                # Check if we're keeping too many old candles
                if row['count'] > 1000:
                    print(f"    ⚠️  Consider: Keeping only last 500-1000 candles per strategy")
                else:
                    print(f"    ✅ Reasonable size")
    except:
        pass

    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count
            FROM renko_bricks
            GROUP BY strategy
        """)
        brick_info = cursor.fetchall()
        if brick_info:
            print(f"\nRenko Bricks:")
            for row in brick_info:
                print(f"  {row['strategy']}: {row['count']} bricks")
                if row['count'] > 200:
                    print(f"    ⚠️  Strategy keeps 200 bricks max (oldest removed)")
                else:
                    print(f"    ✅ Reasonable size (200 max)")
    except:
        pass

    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count
            FROM price_history
            GROUP BY strategy
        """)
        price_info = cursor.fetchall()
        if price_info:
            print(f"\nPrice History:")
            for row in price_info:
                print(f"  {row['strategy']}: {row['count']} price points")
                if row['count'] > 10000:
                    print(f"    ⚠️  LARGE: Consider cleaning old price history (>30 days old)")
                    print(f"    💡 Price history used for ATR/AO calculations - only need recent data")
                elif row['count'] > 5000:
                    print(f"    ⚠️  Consider: Keeping only last 5000-10000 price points")
                else:
                    print(f"    ✅ Reasonable size")
    except:
        pass

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Essential for strategy optimization:")
    print("  ✅ Trades: ALL (needed for PnL analysis, win rate, R:R ratios)")
    print("  ✅ Recent Candles: Last 500-1000 per strategy (for indicators)")
    print("  ✅ Recent Bricks: Last 200 per strategy (for Renko indicators)")
    print("  ⚠️  Price History: Only recent needed (for ATR/AO - can clean old)")
    print()
    print("Can be cleaned:")
    print("  🗑️  Old candles (>1000 per strategy)")
    print("  🗑️  Old price history (>30 days or >10000 points)")
    print("  🗑️  WAL file (will be recreated, but can checkpoint to reduce size)")

    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

