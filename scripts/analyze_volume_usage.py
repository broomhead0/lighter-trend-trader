#!/usr/bin/env python3
"""
Comprehensive Volume Usage Analysis

Analyzes everything on the volume to find what's using 67MB.
"""

import os
import sqlite3
import sys
from pathlib import Path

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")
data_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "/data"

print("=" * 80)
print("COMPREHENSIVE VOLUME USAGE ANALYSIS")
print("=" * 80)
print(f"Data directory: {data_dir}")
print()

# 1. Check all files in /data directory
print("=" * 80)
print("1. ALL FILES ON VOLUME")
print("=" * 80)

total_size = 0
file_sizes = {}

if os.path.exists(data_dir):
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                total_size += size
                rel_path = os.path.relpath(file_path, data_dir)
                file_sizes[rel_path] = size
                print(f"  {rel_path:60} {size:>12,} bytes ({size / 1024 / 1024:>6.2f} MB)")
            except Exception as e:
                print(f"  {rel_path:60} ERROR: {e}")

    print()
    print(f"Total files size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
else:
    print(f"  ❌ Directory {data_dir} does not exist!")

print()

# 2. Database file breakdown
print("=" * 80)
print("2. DATABASE FILES BREAKDOWN")
print("=" * 80)

db_files = {
    "Main DB": db_path,
    "WAL": db_path + "-wal",
    "SHM": db_path + "-shm"
}

db_total = 0
for name, path in db_files.items():
    if os.path.exists(path):
        size = os.path.getsize(path)
        db_total += size
        print(f"  {name:20} {size:>12,} bytes ({size / 1024 / 1024:>6.2f} MB)")
    else:
        print(f"  {name:20} {'NOT FOUND':>12}")

print(f"  {'TOTAL':20} {db_total:>12,} bytes ({db_total / 1024 / 1024:>6.2f} MB)")
print()

# 3. Database contents analysis
print("=" * 80)
print("3. DATABASE CONTENTS (ROW COUNTS)")
print("=" * 80)

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]

        total_rows = 0
        for table in tables:
            try:
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()["count"]
                total_rows += count

                # Estimate size (rough)
                if table == "trades":
                    est_size = count * 200  # ~200 bytes per trade
                elif table == "candles":
                    est_size = count * 100  # ~100 bytes per candle
                elif table == "renko_bricks":
                    est_size = count * 120  # ~120 bytes per brick
                elif table == "price_history":
                    est_size = count * 50  # ~50 bytes per price
                else:
                    est_size = count * 100

                print(f"  {table:20} {count:>10,} rows  ~{est_size / 1024 / 1024:>6.2f} MB")
            except sqlite3.OperationalError:
                print(f"  {table:20} {'N/A':>10} (table doesn't exist)")

        print(f"  {'TOTAL ROWS':20} {total_rows:>10,}")
        print()

        # Detailed breakdown by strategy
        print("  Detailed breakdown:")

        # Price history (likely the biggest)
        try:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM price_history
                GROUP BY strategy, market
                ORDER BY count DESC
            """)
            price_data = cursor.fetchall()
            if price_data:
                print("    Price History:")
                for row in price_data:
                    count = row["count"]
                    size_est = count * 50
                    print(f"      {row['strategy']:20} {row['market']:10} {count:>10,} prices  ~{size_est / 1024 / 1024:>6.2f} MB")
        except:
            pass

        # Candles
        try:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM candles
                GROUP BY strategy, market
                ORDER BY count DESC
            """)
            candle_data = cursor.fetchall()
            if candle_data:
                print("    Candles:")
                for row in candle_data:
                    count = row["count"]
                    size_est = count * 100
                    print(f"      {row['strategy']:20} {row['market']:10} {count:>10,} candles  ~{size_est / 1024 / 1024:>6.2f} MB")
        except:
            pass

        # Bricks
        try:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM renko_bricks
                GROUP BY strategy, market
                ORDER BY count DESC
            """)
            brick_data = cursor.fetchall()
            if brick_data:
                print("    Renko Bricks:")
                for row in brick_data:
                    count = row["count"]
                    size_est = count * 120
                    print(f"      {row['strategy']:20} {row['market']:10} {count:>10,} bricks  ~{size_est / 1024 / 1024:>6.2f} MB")
        except:
            pass

        # Trades
        try:
            cursor = conn.execute("""
                SELECT strategy, COUNT(*) as count
                FROM trades
                GROUP BY strategy
                ORDER BY count DESC
            """)
            trade_data = cursor.fetchall()
            if trade_data:
                print("    Trades:")
                for row in trade_data:
                    count = row["count"]
                    size_est = count * 200
                    print(f"      {row['strategy']:20} {count:>10,} trades  ~{size_est / 1024 / 1024:>6.2f} MB")
        except:
            pass

        conn.close()
    except Exception as e:
        print(f"  ❌ Error analyzing database: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  ❌ Database file not found: {db_path}")

print()

# 4. Backup directory
print("=" * 80)
print("4. BACKUP DIRECTORY")
print("=" * 80)

backup_dir = os.path.join(data_dir, "backups")
if os.path.exists(backup_dir):
    backup_files = []
    backup_total = 0
    for file in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            backup_total += size
            backup_files.append((file, size))

    if backup_files:
        backup_files.sort(key=lambda x: x[1], reverse=True)
        print(f"  Found {len(backup_files)} backup files:")
        for file, size in backup_files:
            print(f"    {file:50} {size:>12,} bytes ({size / 1024 / 1024:>6.2f} MB)")
        print(f"  {'TOTAL BACKUPS':50} {backup_total:>12,} bytes ({backup_total / 1024 / 1024:>6.2f} MB)")
    else:
        print("  No backup files found")
else:
    print(f"  Backup directory does not exist: {backup_dir}")

print()

# 5. Summary
print("=" * 80)
print("5. SUMMARY")
print("=" * 80)
print(f"Railway volume reports: 67 MB")
print(f"Database files: {db_total / 1024 / 1024:.2f} MB")
if os.path.exists(backup_dir):
    backup_total = sum(os.path.getsize(os.path.join(backup_dir, f)) for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f)))
    print(f"Backup files: {backup_total / 1024 / 1024:.2f} MB")
else:
    backup_total = 0
    print(f"Backup files: 0 MB (directory doesn't exist)")

accounted = db_total + backup_total
unaccounted = (67 * 1024 * 1024) - accounted

print(f"Accounted for: {accounted / 1024 / 1024:.2f} MB")
print(f"Unaccounted: {unaccounted / 1024 / 1024:.2f} MB")
print()

if unaccounted > 1024 * 1024:  # > 1MB
    print("⚠️  WARNING: Significant unaccounted space!")
    print("   This could be:")
    print("   - Other files on the volume")
    print("   - Railway volume overhead")
    print("   - Filesystem metadata")
    print("   - Volume snapshot/backup data")

print("=" * 80)

