#!/usr/bin/env python3
"""
Check what's actually in the Railway volume - find the database and see what's taking up space.
"""

import os
import subprocess
import sys

print("=" * 60)
print("VOLUME CONTENTS CHECK")
print("=" * 60)

# Check /data directory
data_path = "/data"
print(f"\nChecking {data_path}:")
print(f"  Exists: {os.path.exists(data_path)}")
if os.path.exists(data_path):
    try:
        items = os.listdir(data_path)
        print(f"  Items: {items}")
        
        total_size = 0
        for item in items:
            item_path = os.path.join(data_path, item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                total_size += size
                size_mb = size / (1024 * 1024)
                print(f"    {item}: {size:,} bytes ({size_mb:.2f} MB)")
            elif os.path.isdir(item_path):
                print(f"    {item}/ (directory)")
    except Exception as e:
        print(f"  Error listing: {e}")

# Check for database files
print(f"\nSearching for database files:")
db_paths = [
    "/data/pnl_trades.db",
    "/tmp/pnl_trades.db",
    "/persist/pnl_trades.db",
]

for db_path in db_paths:
    exists = os.path.exists(db_path)
    print(f"  {db_path}: {'EXISTS' if exists else 'NOT FOUND'}")
    if exists:
        size = os.path.getsize(db_path)
        size_mb = size / (1024 * 1024)
        print(f"    Size: {size:,} bytes ({size_mb:.2f} MB)")
        
        # Check for WAL file
        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            wal_size = os.path.getsize(wal_path)
            wal_size_mb = wal_size / (1024 * 1024)
            print(f"    WAL: {wal_size:,} bytes ({wal_size_mb:.2f} MB)")
            print(f"    Total: {size + wal_size:,} bytes ({(size + wal_size) / (1024 * 1024):.2f} MB)")

# Check environment
print(f"\nEnvironment:")
print(f"  PNL_DB_PATH: {os.environ.get('PNL_DB_PATH', 'NOT SET')}")

print("\n" + "=" * 60)

