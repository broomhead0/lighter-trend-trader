#!/usr/bin/env python3
"""
Snapshot Database State

Captures current database state for comparison after redeploy.
"""

import os
import sqlite3
import sys
from datetime import datetime

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("DATABASE STATE SNAPSHOT")
print("=" * 80)
print(f"Timestamp: {datetime.now().isoformat()}")
print(f"Database path: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")
print()

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    sys.exit(1)

# Get file size
file_size = os.path.getsize(db_path)
wal_size = 0
wal_path = db_path + "-wal"
if os.path.exists(wal_path):
    wal_size = os.path.getsize(wal_path)
total_size = file_size + wal_size

print(f"Database file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
if wal_size > 0:
    print(f"WAL file size: {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
print(f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
print()

# Connect and get counts
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    print("RECORD COUNTS:")
    print("-" * 80)

    tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]
    counts = {}
    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()["count"]
            counts[table] = count
            print(f"  {table:20} {count:8} records")
        except sqlite3.OperationalError:
            counts[table] = 0
            print(f"  {table:20} {'N/A':8} (table doesn't exist)")

    print()

    # Get breakdown by strategy
    print("BREAKDOWN BY STRATEGY:")
    print("-" * 80)

    # Trades by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count
            FROM trades
            GROUP BY strategy
            ORDER BY strategy
        """)
        trades_by_strategy = cursor.fetchall()
        if trades_by_strategy:
            print("  Trades:")
            for row in trades_by_strategy:
                print(f"    {row['strategy']:20} {row['count']:6} trades")
        else:
            print("  Trades: None")
    except sqlite3.OperationalError:
        print("  Trades: Table doesn't exist")

    # Candles by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM candles
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        candles_by_strategy = cursor.fetchall()
        if candles_by_strategy:
            print("  Candles:")
            for row in candles_by_strategy:
                print(f"    {row['strategy']:20} {row['market']:10} {row['count']:6} candles")
        else:
            print("  Candles: None")
    except sqlite3.OperationalError:
        print("  Candles: Table doesn't exist")

    # Bricks by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM renko_bricks
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        bricks_by_strategy = cursor.fetchall()
        if bricks_by_strategy:
            print("  Bricks:")
            for row in bricks_by_strategy:
                print(f"    {row['strategy']:20} {row['market']:10} {row['count']:6} bricks")
        else:
            print("  Bricks: None")
    except sqlite3.OperationalError:
        print("  Bricks: Table doesn't exist")

    # Price history by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM price_history
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        prices_by_strategy = cursor.fetchall()
        if prices_by_strategy:
            print("  Price History:")
            for row in prices_by_strategy:
                print(f"    {row['strategy']:20} {row['market']:10} {row['count']:6} prices")
        else:
            print("  Price History: None")
    except sqlite3.OperationalError:
        print("  Price History: Table doesn't exist")

    # Positions
    try:
        cursor = conn.execute("""
            SELECT strategy, market, side, entry_price, size
            FROM positions
            ORDER BY strategy, market
        """)
        positions = cursor.fetchall()
        if positions:
            print("  Open Positions:")
            for row in positions:
                print(f"    {row['strategy']:20} {row['market']:10} {row['side']:5} {row['entry_price']:10.4f} {row['size']:8.4f}")
        else:
            print("  Open Positions: None")
    except sqlite3.OperationalError:
        print("  Positions: Table doesn't exist")

    conn.close()

    print()
    print("=" * 80)
    print("✅ Snapshot complete")
    print("=" * 80)
    print()
    print("Save these counts to compare after redeploy:")
    for table, count in counts.items():
        print(f"  {table}: {count}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

