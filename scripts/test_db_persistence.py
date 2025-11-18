#!/usr/bin/env python3
"""
Test script to verify database persistence across deploys.

This script:
1. Writes test data to the database
2. Verifies the data is there
3. After a redeploy, the data should still be there
"""

import os
import sqlite3
import sys
import time

# Get database path from environment or use default
db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")

print(f"Testing database persistence at: {db_path}")
print(f"Database directory exists: {os.path.exists(os.path.dirname(db_path))}")
print(f"Database file exists: {os.path.exists(db_path)}")

# Connect to database
try:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # Create test table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persistence_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_data TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """)
    conn.commit()
    
    # Write test data
    test_data = f"TEST_DATA_{int(time.time())}"
    cursor.execute("""
        INSERT INTO persistence_test (test_data, timestamp) VALUES (?, ?)
    """, (test_data, time.time()))
    conn.commit()
    
    print(f"✅ Wrote test data: {test_data}")
    
    # Verify it's there
    cursor.execute("SELECT COUNT(*) FROM persistence_test")
    count = cursor.fetchone()[0]
    print(f"✅ Total test records in database: {count}")
    
    # Check other tables
    cursor.execute("SELECT COUNT(*) FROM trades")
    trades_count = cursor.fetchone()[0]
    print(f"✅ Total trades in database: {trades_count}")
    
    cursor.execute("SELECT COUNT(*) FROM candles")
    candles_count = cursor.fetchone()[0]
    print(f"✅ Total candles in database: {candles_count}")
    
    cursor.execute("SELECT COUNT(*) FROM renko_bricks")
    bricks_count = cursor.fetchone()[0]
    print(f"✅ Total Renko bricks in database: {bricks_count}")
    
    cursor.execute("SELECT COUNT(*) FROM price_history")
    price_count = cursor.fetchone()[0]
    print(f"✅ Total price history points in database: {price_count}")
    
    conn.close()
    print(f"\n✅ Database test completed successfully!")
    print(f"   Database path: {db_path}")
    print(f"   File exists: {os.path.exists(db_path)}")
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"   File size: {file_size} bytes")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

