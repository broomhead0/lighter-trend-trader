#!/usr/bin/env python3
"""
Quick database verification script - runs with timeout, shows exact counts and sizes.
"""

import os
import sqlite3
import sys
import time

# Get database path
db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 60)
print("DATABASE VERIFICATION REPORT")
print("=" * 60)
print(f"Database path: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    sys.exit(1)

# Get file size
file_size = os.path.getsize(db_path)
file_size_mb = file_size / (1024 * 1024)
print(f"File size: {file_size:,} bytes ({file_size_mb:.2f} MB)")
print()

# Connect and query
try:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5.0)
    cursor = conn.cursor()

    print("TABLE COUNTS:")
    print("-" * 60)

    # Check each table
    tables = [
        ("trades", "Completed trades"),
        ("candles", "Candles (breakout strategy)"),
        ("renko_bricks", "Renko bricks"),
        ("price_history", "Price history points"),
        ("positions", "Open positions"),
    ]

    total_rows = 0
    for table_name, description in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            total_rows += count

            # Get size estimate for this table
            cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            table_exists = cursor.fetchone()[0] > 0

            if table_exists:
                # Get approximate size
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                print(f"  {table_name:20s} {count:>10,} rows - {description}")
            else:
                print(f"  {table_name:20s} {'N/A':>10} - Table does not exist")
        except Exception as e:
            print(f"  {table_name:20s} {'ERROR':>10} - {e}")

    print()
    print(f"Total rows across all tables: {total_rows:,}")
    print()

    # Check recent activity
    print("RECENT ACTIVITY (last 24 hours):")
    print("-" * 60)

    try:
        # Recent trades
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE exit_time > ?
        """, (time.time() - 86400,))
        recent_trades = cursor.fetchone()[0]
        print(f"  Trades in last 24h: {recent_trades}")

        # Recent candles
        cursor.execute("""
            SELECT COUNT(*) FROM candles
            WHERE created_at > ?
        """, (time.time() - 86400,))
        recent_candles = cursor.fetchone()[0]
        print(f"  Candles in last 24h: {recent_candles}")

        # Recent bricks
        cursor.execute("""
            SELECT COUNT(*) FROM renko_bricks
            WHERE created_at > ?
        """, (time.time() - 86400,))
        recent_bricks = cursor.fetchone()[0]
        print(f"  Bricks in last 24h: {recent_bricks}")

    except Exception as e:
        print(f"  Error checking recent activity: {e}")

    print()

    # Database info
    print("DATABASE INFO:")
    print("-" * 60)
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    db_size_bytes = page_count * page_size
    db_size_mb = db_size_bytes / (1024 * 1024)

    print(f"  Page count: {page_count:,}")
    print(f"  Page size: {page_size:,} bytes")
    print(f"  Database size (internal): {db_size_bytes:,} bytes ({db_size_mb:.2f} MB)")
    print(f"  File size (external): {file_size:,} bytes ({file_size_mb:.2f} MB)")
    print()

    # Check for WAL file
    wal_path = db_path + "-wal"
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
        wal_size_mb = wal_size / (1024 * 1024)
        print(f"  WAL file size: {wal_size:,} bytes ({wal_size_mb:.2f} MB)")
        print(f"  Total (DB + WAL): {file_size + wal_size:,} bytes ({(file_size + wal_size) / (1024 * 1024):.2f} MB)")

    conn.close()

    print()
    print("=" * 60)
    print("✅ Verification complete")
    print("=" * 60)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


