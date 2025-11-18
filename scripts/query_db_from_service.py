#!/usr/bin/env python3
"""
Query Database from Service

This script queries the database to show what data exists.
Can be run via Railway CLI or added to the service for periodic reporting.
"""

import os
import sqlite3
import sys
from datetime import datetime

# Get database path from environment
db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print("=" * 80)
print("DATABASE QUERY REPORT")
print("=" * 80)
print(f"Database path: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")
print(f"Directory exists: {os.path.exists(os.path.dirname(db_path))}")
print()

if not os.path.exists(db_path):
    print("❌ Database file does not exist!")
    print(f"   Checked: {db_path}")
    print(f"   Directory exists: {os.path.exists(os.path.dirname(db_path))}")
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

# Connect and query
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    print("=" * 80)
    print("DATABASE CONTENTS")
    print("=" * 80)
    
    # Get counts
    tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]
    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()["count"]
            print(f"  {table}: {count} records")
        except sqlite3.OperationalError as e:
            print(f"  {table}: Table does not exist ({e})")
    
    print()
    
    # Get recent trades
    try:
        cursor = conn.execute("""
            SELECT strategy, side, pnl_pct, exit_reason, exit_time, market
            FROM trades
            ORDER BY exit_time DESC
            LIMIT 10
        """)
        trades = cursor.fetchall()
        if trades:
            print("Recent Trades (last 10):")
            for trade in trades:
                exit_time = datetime.fromtimestamp(trade["exit_time"]).strftime("%Y-%m-%d %H:%M:%S")
                pnl_sign = "+" if trade["pnl_pct"] >= 0 else ""
                print(f"  {trade['strategy']:20} {trade['side']:5} {pnl_sign}{trade['pnl_pct']:7.4f}% {trade['exit_reason']:15} {exit_time}")
        else:
            print("No trades found")
    except sqlite3.OperationalError as e:
        print(f"Could not query trades: {e}")
    
    print()
    
    # Get candle counts by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM candles
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        candles = cursor.fetchall()
        if candles:
            print("Candles by Strategy:")
            for candle in candles:
                print(f"  {candle['strategy']:20} {candle['market']:10} {candle['count']:6} candles")
        else:
            print("No candles found")
    except sqlite3.OperationalError as e:
        print(f"Could not query candles: {e}")
    
    print()
    
    # Get brick counts by strategy
    try:
        cursor = conn.execute("""
            SELECT strategy, market, COUNT(*) as count
            FROM renko_bricks
            GROUP BY strategy, market
            ORDER BY strategy, market
        """)
        bricks = cursor.fetchall()
        if bricks:
            print("Renko Bricks by Strategy:")
            for brick in bricks:
                print(f"  {brick['strategy']:20} {brick['market']:10} {brick['count']:6} bricks")
        else:
            print("No bricks found")
    except sqlite3.OperationalError as e:
        print(f"Could not query bricks: {e}")
    
    print()
    
    # Get open positions
    try:
        cursor = conn.execute("""
            SELECT strategy, market, side, entry_price, size, entry_time
            FROM positions
            ORDER BY strategy, market
        """)
        positions = cursor.fetchall()
        if positions:
            print("Open Positions:")
            for pos in positions:
                entry_time = datetime.fromtimestamp(pos["entry_time"]).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {pos['strategy']:20} {pos['market']:10} {pos['side']:5} {pos['entry_price']:10.4f} {pos['size']:8.4f} {entry_time}")
        else:
            print("No open positions")
    except sqlite3.OperationalError as e:
        print(f"Could not query positions: {e}")
    
    conn.close()
    
    print()
    print("=" * 80)
    print("✅ Database query complete")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error querying database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

