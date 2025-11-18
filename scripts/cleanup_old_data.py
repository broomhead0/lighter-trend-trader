#!/usr/bin/env python3
"""
Cleanup Old Database Data

Removes old data that's not needed for strategy optimization:
- Old price history (>1000 per strategy or >30 days)
- Old candles (>1000 per strategy or >30 days)
- Checkpoints WAL file to reduce size
"""

import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("DATABASE CLEANUP")
print("=" * 80)
print(f"Database: {db_path}")
print()

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Get current sizes
    file_size_before = os.path.getsize(db_path)
    wal_size_before = 0
    wal_path = db_path + "-wal"
    if os.path.exists(wal_path):
        wal_size_before = os.path.getsize(wal_path)

    print(f"Before cleanup:")
    print(f"  DB file: {file_size_before:,} bytes ({file_size_before / 1024 / 1024:.2f} MB)")
    if wal_size_before > 0:
        print(f"  WAL file: {wal_size_before:,} bytes ({wal_size_before / 1024 / 1024:.2f} MB)")
    print()

    # 1. Clean old price history (keep only last 1000 per strategy)
    print("1. Cleaning price history...")
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM price_history
            GROUP BY strategy, market
        """)
        price_data = cursor.fetchall()

        deleted_total = 0
        for row in price_data:
            strategy = row["strategy"]
            market = row["market"]
            count = row["count"]

            if count > 1000:
                # Keep only last 1000
                cursor = conn.execute("""
                    DELETE FROM price_history
                    WHERE strategy = ? AND market = ?
                    AND id NOT IN (
                        SELECT id FROM price_history
                        WHERE strategy = ? AND market = ?
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    )
                """, (strategy, market, strategy, market))
                deleted = cursor.rowcount
                deleted_total += deleted
                print(f"   {strategy}/{market}: Kept 1000, deleted {deleted} old price points")
            else:
                print(f"   {strategy}/{market}: {count} price points (already at limit)")

        if deleted_total > 0:
            conn.commit()
            print(f"   ✅ Deleted {deleted_total} old price history records")
        else:
            print(f"   ✅ No cleanup needed")
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Could not clean price history: {e}")

    print()

    # 2. Clean old candles (keep only last 1000 per strategy, or >30 days)
    print("2. Cleaning old candles...")
    try:
        thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())

        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM candles
            GROUP BY strategy, market
        """)
        candle_data = cursor.fetchall()

        deleted_total = 0
        for row in candle_data:
            strategy = row["strategy"]
            market = row["market"]
            count = row["count"]

            if count > 1000:
                # Delete old candles, keep last 1000
                cursor = conn.execute("""
                    DELETE FROM candles
                    WHERE strategy = ? AND market = ?
                    AND id NOT IN (
                        SELECT id FROM candles
                        WHERE strategy = ? AND market = ?
                        ORDER BY open_time DESC
                        LIMIT 1000
                    )
                """, (strategy, market, strategy, market))
                deleted = cursor.rowcount
                deleted_total += deleted
                print(f"   {strategy}/{market}: Kept 1000, deleted {deleted} old candles")
            else:
                # Also delete candles older than 30 days
                cursor = conn.execute("""
                    DELETE FROM candles
                    WHERE strategy = ? AND market = ? AND open_time < ?
                """, (strategy, market, thirty_days_ago))
                deleted = cursor.rowcount
                if deleted > 0:
                    deleted_total += deleted
                    print(f"   {strategy}/{market}: Deleted {deleted} candles older than 30 days")

        if deleted_total > 0:
            conn.commit()
            print(f"   ✅ Deleted {deleted_total} old candle records")
        else:
            print(f"   ✅ No cleanup needed")
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Could not clean candles: {e}")

    print()

    # 3. Vacuum database to reclaim space
    print("3. Vacuuming database...")
    try:
        conn.execute("VACUUM")
        print("   ✅ Database vacuumed")
    except Exception as e:
        print(f"   ⚠️  Could not vacuum: {e}")

    print()

    # 4. Checkpoint WAL file
    print("4. Checkpointing WAL file...")
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("   ✅ WAL checkpointed")
    except Exception as e:
        print(f"   ⚠️  Could not checkpoint WAL: {e}")

    conn.close()

    # Get sizes after cleanup
    file_size_after = os.path.getsize(db_path)
    wal_size_after = 0
    if os.path.exists(wal_path):
        wal_size_after = os.path.getsize(wal_path)

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"After cleanup:")
    print(f"  DB file: {file_size_after:,} bytes ({file_size_after / 1024 / 1024:.2f} MB)")
    if wal_size_after > 0:
        print(f"  WAL file: {wal_size_after:,} bytes ({wal_size_after / 1024 / 1024:.2f} MB)")
    print()

    db_saved = file_size_before - file_size_after
    wal_saved = wal_size_before - wal_size_after
    total_saved = db_saved + wal_saved

    if total_saved > 0:
        print(f"Space saved: {total_saved:,} bytes ({total_saved / 1024 / 1024:.2f} MB)")
    else:
        print("No space saved (database was already optimized)")

    print()
    print("=" * 80)
    print("✅ Cleanup complete")
    print("=" * 80)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

