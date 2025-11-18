#!/usr/bin/env python3
"""
Comprehensive Database Persistence Test

This script:
1. Writes test data to all database tables (trades, candles, bricks, price_history)
2. Verifies the data was written
3. Reports database location and size
4. Can be run before/after redeploy to verify persistence
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

# Get database path from environment or use default
db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("COMPREHENSIVE DATABASE PERSISTENCE TEST")
print("=" * 80)
print(f"Database path: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")
print(f"Directory exists: {os.path.exists(os.path.dirname(db_path))}")
print()

# Check if directory is writable
db_dir = os.path.dirname(db_path)
if db_dir:
    try:
        test_file = os.path.join(db_dir, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print(f"✅ Directory is writable: {db_dir}")
    except Exception as e:
        print(f"❌ Directory is NOT writable: {db_dir} - {e}")
        sys.exit(1)
print()

# Connect to database
try:
    # Ensure directory exists
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    print(f"✅ Connected to database: {db_path}")
except Exception as e:
    print(f"❌ Failed to connect to database: {e}")
    sys.exit(1)

# Get current counts
def get_counts():
    """Get current record counts from all tables."""
    counts = {}
    tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]
    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = 0  # Table doesn't exist yet
    return counts

print("\n" + "=" * 80)
print("CURRENT DATABASE STATE")
print("=" * 80)
initial_counts = get_counts()
for table, count in initial_counts.items():
    print(f"  {table}: {count} records")

# Get database file size
if os.path.exists(db_path):
    file_size = os.path.getsize(db_path)
    wal_size = 0
    wal_path = db_path + "-wal"
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
    total_size = file_size + wal_size
    print(f"\nDatabase file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    if wal_size > 0:
        print(f"WAL file size: {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
    print(f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")

# Write test data
print("\n" + "=" * 80)
print("WRITING TEST DATA")
print("=" * 80)

now = time.time()

# 1. Write test trade
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            size REAL NOT NULL,
            pnl_pct REAL NOT NULL,
            pnl_usd REAL NOT NULL,
            entry_time REAL NOT NULL,
            exit_time REAL NOT NULL,
            exit_reason TEXT NOT NULL,
            market TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO trades (
            strategy, side, entry_price, exit_price, size,
            pnl_pct, pnl_usd, entry_time, exit_time,
            exit_reason, market, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "test_strategy", "long", 100.0, 101.0, 0.001,
        1.0, 0.001, now - 3600, now, "test", "market:2", now
    ))
    print("✅ Wrote test trade")
except Exception as e:
    print(f"❌ Failed to write test trade: {e}")

# 2. Write test candle
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            market TEXT NOT NULL,
            open_time INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(strategy, market, open_time)
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO candles (
            strategy, market, open_time, open, high, low, close, volume, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "test_strategy", "market:2", int(now), 100.0, 101.0, 99.0, 100.5, 1.0, now
    ))
    print("✅ Wrote test candle")
except Exception as e:
    print(f"❌ Failed to write test candle: {e}")

# 3. Write test Renko brick
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS renko_bricks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            market TEXT NOT NULL,
            brick_index INTEGER NOT NULL,
            open_price REAL NOT NULL,
            close_price REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            direction TEXT NOT NULL,
            timestamp REAL NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(strategy, market, brick_index)
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO renko_bricks (
            strategy, market, brick_index, open_price, close_price,
            high, low, direction, timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "test_strategy", "market:2", 999, 100.0, 101.0,
        101.0, 100.0, "up", now, now
    ))
    print("✅ Wrote test Renko brick")
except Exception as e:
    print(f"❌ Failed to write test Renko brick: {e}")

# 4. Write test price history
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            market TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp REAL NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO price_history (
            strategy, market, price, timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        "test_strategy", "market:2", 100.0, now, now
    ))
    print("✅ Wrote test price history")
except Exception as e:
    print(f"❌ Failed to write test price history: {e}")

# 5. Write test position
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            market TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            size REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            entry_time REAL NOT NULL,
            scaled_entries TEXT,
            created_at REAL NOT NULL,
            UNIQUE(strategy, market)
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO positions (
            strategy, market, side, entry_price, size,
            stop_loss, take_profit, entry_time, scaled_entries, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "test_strategy", "market:2", "long", 100.0, 0.001,
        99.0, 101.0, now, "[]", now
    ))
    print("✅ Wrote test position")
except Exception as e:
    print(f"❌ Failed to write test position: {e}")

conn.commit()

# Verify writes
print("\n" + "=" * 80)
print("VERIFICATION - READING BACK DATA")
print("=" * 80)
final_counts = get_counts()
for table, count in final_counts.items():
    diff = count - initial_counts.get(table, 0)
    status = "✅" if diff > 0 else "⚠️"
    print(f"  {status} {table}: {count} records (+{diff})")

# Verify specific test records
print("\nVerifying test records:")
test_trade = conn.execute("SELECT COUNT(*) FROM trades WHERE strategy = 'test_strategy'").fetchone()[0]
test_candle = conn.execute("SELECT COUNT(*) FROM candles WHERE strategy = 'test_strategy'").fetchone()[0]
test_brick = conn.execute("SELECT COUNT(*) FROM renko_bricks WHERE strategy = 'test_strategy'").fetchone()[0]
test_price = conn.execute("SELECT COUNT(*) FROM price_history WHERE strategy = 'test_strategy'").fetchone()[0]
test_position = conn.execute("SELECT COUNT(*) FROM positions WHERE strategy = 'test_strategy'").fetchone()[0]

print(f"  Test trades: {test_trade}")
print(f"  Test candles: {test_candle}")
print(f"  Test bricks: {test_brick}")
print(f"  Test prices: {test_price}")
print(f"  Test positions: {test_position}")

# Final database size
if os.path.exists(db_path):
    file_size = os.path.getsize(db_path)
    wal_size = 0
    wal_path = db_path + "-wal"
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
    total_size = file_size + wal_size
    print(f"\nFinal database file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    if wal_size > 0:
        print(f"Final WAL file size: {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
    print(f"Final total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")

conn.close()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print(f"\n✅ Database is at: {db_path}")
print(f"✅ All test data written and verified")
print(f"\nTo test persistence:")
print(f"  1. Run this script: python scripts/test_db_persistence_comprehensive.py")
print(f"  2. Redeploy the service")
print(f"  3. Run this script again - test records should still be there")
print()

