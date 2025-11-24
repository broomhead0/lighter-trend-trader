#!/usr/bin/env python3
"""Clean up old database backups, keeping only the most recent N."""
import os
import sys
from pathlib import Path

db_path = os.environ.get("PNL_DB_PATH", "/data/pnl_trades.db")
backup_dir = os.path.join(os.path.dirname(db_path), "backups")
max_backups = int(os.environ.get("PNL_BACKUP_MAX_BACKUPS", "3"))

print(f"Cleaning backups in: {backup_dir}")
print(f"Keeping: {max_backups} most recent backups")
print()

if not os.path.exists(backup_dir):
    print(f"Backup directory not found: {backup_dir}")
    sys.exit(0)

# Get all backup files
backup_files = []
for file in os.listdir(backup_dir):
    file_path = os.path.join(backup_dir, file)
    if os.path.isfile(file_path) and file.startswith("pnl_trades_") and file.endswith(".db"):
        backup_files.append((file_path, os.path.getmtime(file_path)))

# Sort by modification time (newest first)
backup_files.sort(key=lambda x: x[1], reverse=True)

if len(backup_files) <= max_backups:
    print(f"Only {len(backup_files)} backups found, no cleanup needed")
    sys.exit(0)

# Delete old backups
to_delete = backup_files[max_backups:]
total_freed = 0

print(f"Found {len(backup_files)} backups, will delete {len(to_delete)} old ones:")
for file_path, mtime in to_delete:
    size = os.path.getsize(file_path)
    total_freed += size
    print(f"  Deleting: {os.path.basename(file_path)} ({size / 1024 / 1024:.2f} MB)")
    os.remove(file_path)

print()
print(f"✅ Cleaned up {len(to_delete)} backups")
print(f"✅ Freed {total_freed / 1024 / 1024:.2f} MB")
print(f"✅ Kept {max_backups} most recent backups")

