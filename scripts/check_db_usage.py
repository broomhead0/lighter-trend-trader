#!/usr/bin/env python3
"""
Check Database Usage - Can be run from service logs or directly

Analyzes what's taking up space in the database.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("DATABASE USAGE ANALYSIS")
print("=" * 80)
print(f"Database: {db_path}")
print()

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    print("   (This script needs to run inside the service container)")
    sys.exit(1)

# File sizes
file_size = os.path.getsize(db_path)
wal_size = 0
wal_path = db_path + "-wal"
shm_size = 0
shm_path = db_path + "-shm"
if os.path.exists(wal_path):
    wal_size = os.path.getsize(wal_path)
if os.path.exists(shm_path):
    shm_size = os.path.getsize(shm_path)

print(f"Main DB file:  {file_size:>12,} bytes ({file_size / 1024 / 1024:>6.2f} MB)")
if wal_size > 0:
    print(f"WAL file:      {wal_size:>12,} bytes ({wal_size / 1024 / 1024:>6.2f} MB)")
if shm_size > 0:
    print(f"SHM file:      {shm_size:>12,} bytes ({shm_size / 1024 / 1024:>6.2f} MB)")
print(f"{'─' * 80}")
total_db_size = file_size + wal_size + shm_size
print(f"Total DB size: {total_db_size:>12,} bytes ({total_db_size / 1024 / 1024:>6.2f} MB)")
print()

# Check for backup directory
backup_dir = os.path.join(os.path.dirname(db_path), "backups")
backup_size = 0
backup_count = 0
if os.path.exists(backup_dir):
    for f in os.listdir(backup_dir):
        fpath = os.path.join(backup_dir, f)
        if os.path.isfile(fpath):
            backup_size += os.path.getsize(fpath)
            backup_count += 1

if backup_size > 0:
    print(f"Backups:       {backup_size:>12,} bytes ({backup_size / 1024 / 1024:>6.2f} MB) in {backup_count} files")
    print()

print(f"Volume total:  67 MB (from Railway)")
print(f"DB + backups: {total_db_size + backup_size:>12,} bytes ({(total_db_size + backup_size) / 1024 / 1024:>6.2f} MB)")
print(f"Unaccounted:   {(67 * 1024 * 1024) - (total_db_size + backup_size):>12,} bytes ({(67 * 1024 * 1024 - total_db_size - backup_size) / 1024 / 1024:>6.2f} MB)")
print()

# Connect and analyze tables
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("TABLE BREAKDOWN")
    print("=" * 80)

    tables = {
        "trades": "Essential - All trades needed for PnL analysis",
        "candles": "Essential - Recent candles for indicators (can limit to 500-1000 per strategy)",
        "renko_bricks": "Essential - Last 200 bricks per strategy (auto-limited)",
        "price_history": "⚠️  Can be reduced - Only need last 1000 per strategy (for ATR/AO)",
        "positions": "Essential - Open positions (minimal size)"
    }

    for table, note in tables.items():
        try:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()["count"]

            # Get age of oldest record
            if table == "trades":
                cursor = conn.execute("SELECT MIN(exit_time) as oldest FROM trades")
                result = cursor.fetchone()
                if result and result["oldest"]:
                    oldest = datetime.fromtimestamp(result["oldest"])
                    age = datetime.now() - oldest
                    age_str = f" (oldest: {age.days} days ago)"
                else:
                    age_str = ""
            elif table == "candles":
                cursor = conn.execute("SELECT MIN(open_time) as oldest FROM candles")
                result = cursor.fetchone()
                if result and result["oldest"]:
                    oldest = datetime.fromtimestamp(result["oldest"])
                    age = datetime.now() - oldest
                    age_str = f" (oldest: {age.days} days ago)"
                else:
                    age_str = ""
            elif table == "price_history":
                cursor = conn.execute("SELECT MIN(timestamp) as oldest FROM price_history")
                result = cursor.fetchone()
                if result and result["oldest"]:
                    oldest = datetime.fromtimestamp(result["oldest"])
                    age = datetime.now() - oldest
                    age_str = f" (oldest: {age.days} days ago)"
                else:
                    age_str = ""
            else:
                age_str = ""

            print(f"{table:20} {count:>8,} rows{age_str}")
            print(f"  {note}")

        except sqlite3.OperationalError:
            print(f"{table:20} {'N/A':>8} (table doesn't exist)")

    print()
    print("=" * 80)
    print("DETAILED BREAKDOWN BY STRATEGY")
    print("=" * 80)

    # Price history by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM price_history
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        price_data = cursor.fetchall()
        if price_data:
            print("\nPrice History (⚠️  Main space consumer):")
            total_prices = 0
            for row in price_data:
                count = row["count"]
                total_prices += count
                # Each price point is ~50 bytes
                size_est = count * 50
                print(f"  {row['strategy']:20} {row['market']:10} {count:>8,} prices  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_prices:>8,} prices  ~{total_prices * 50 / 1024 / 1024:.2f} MB")
            if total_prices > 5000:
                print(f"\n  ⚠️  WARNING: {total_prices} price points is large!")
                print(f"     Price history is limited to 1000 per strategy in code,")
                print(f"     but old data may not have been cleaned up.")
                print(f"     Recommendation: Clean old price history (>30 days)")
    except sqlite3.OperationalError:
        pass

    # Candles by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM candles
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        candle_data = cursor.fetchall()
        if candle_data:
            print("\nCandles:")
            total_candles = 0
            for row in candle_data:
                count = row["count"]
                total_candles += count
                size_est = count * 100
                print(f"  {row['strategy']:20} {row['market']:10} {count:>8,} candles  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_candles:>8,} candles  ~{total_candles * 100 / 1024 / 1024:.2f} MB")
    except sqlite3.OperationalError:
        pass

    # Bricks by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM renko_bricks
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        brick_data = cursor.fetchall()
        if brick_data:
            print("\nRenko Bricks:")
            total_bricks = 0
            for row in brick_data:
                count = row["count"]
                total_bricks += count
                size_est = count * 120
                print(f"  {row['strategy']:20} {row['market']:10} {count:>8,} bricks  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {'':10} {total_bricks:>8,} bricks  ~{total_bricks * 120 / 1024 / 1024:.2f} MB")
    except sqlite3.OperationalError:
        pass

    # Trades
    try:
        cursor = conn.execute("""
            SELECT strategy, COUNT(*) as count
            FROM trades
            GROUP BY strategy
            ORDER BY strategy
        """)
        trade_data = cursor.fetchall()
        if trade_data:
            print("\nTrades:")
            total_trades = 0
            for row in trade_data:
                count = row["count"]
                total_trades += count
                size_est = count * 200
                print(f"  {row['strategy']:20} {count:>8,} trades  ~{size_est / 1024 / 1024:.2f} MB")
            print(f"  {'TOTAL':20} {total_trades:>8,} trades  ~{total_trades * 200 / 1024 / 1024:.2f} MB")
    except sqlite3.OperationalError:
        pass

    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("✅ KEEP (Essential for strategy optimization):")
    print("  • All trades - Needed for PnL analysis, win rate, R:R ratios")
    print("  • Recent candles - Last 500-1000 per strategy (for indicators)")
    print("  • Recent bricks - Last 200 per strategy (auto-limited)")
    print("  • Open positions - Minimal size")
    print()
    print("⚠️  OPTIMIZE (Can reduce):")
    print("  • Price history - Only need last 1000 per strategy (for ATR/AO)")
    print("    Current code limits to 1000, but old data may exist")
    print("  • Old candles - Can clean candles >30 days old")
    print("  • WAL file - Can checkpoint to reduce size (will regrow)")
    print()
    print("🗑️  CLEANUP OPTIONS:")
    print("  1. Clean old price history (>30 days or >1000 per strategy)")
    print("  2. Clean old candles (>30 days or >1000 per strategy)")
    print("  3. VACUUM database to reclaim space")
    print("  4. Checkpoint WAL file (PRAGMA wal_checkpoint)")
    print()

    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

