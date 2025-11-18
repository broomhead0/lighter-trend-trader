"""
Database Cleanup Module

Cleans old data that's not needed for strategy optimization.
Runs automatically on startup and can be called periodically.
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

LOG = logging.getLogger("db_cleanup")


def analyze_database_size(db_path: str) -> dict:
    """
    Analyze database size and contents.

    Returns:
        dict with detailed size breakdown
    """
    import os

    analysis = {
        "db_file_size": 0,
        "wal_file_size": 0,
        "shm_file_size": 0,
        "backup_dir_size": 0,
        "backup_count": 0,
        "table_counts": {},
        "total_rows": 0,
        "errors": []
    }

    try:
        # File sizes
        if os.path.exists(db_path):
            analysis["db_file_size"] = os.path.getsize(db_path)

        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            analysis["wal_file_size"] = os.path.getsize(wal_path)

        shm_path = db_path + "-shm"
        if os.path.exists(shm_path):
            analysis["shm_file_size"] = os.path.getsize(shm_path)

        # Backup directory
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
            analysis["backup_count"] = len(backup_files)
            for f in backup_files:
                analysis["backup_dir_size"] += os.path.getsize(os.path.join(backup_dir, f))

        # List ALL files on the volume
        data_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "/data"
        analysis["all_files"] = []
        if os.path.exists(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        rel_path = os.path.relpath(file_path, data_dir)
                        analysis["all_files"].append({
                            "path": rel_path,
                            "size": size
                        })
                    except Exception:
                        pass
            # Sort by size descending
            analysis["all_files"].sort(key=lambda x: x["size"], reverse=True)

        # Database contents
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        tables = ["trades", "candles", "renko_bricks", "price_history", "positions"]
        for table in tables:
            try:
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()["count"]
                analysis["table_counts"][table] = count
                analysis["total_rows"] += count
            except sqlite3.OperationalError:
                analysis["table_counts"][table] = 0

        # Detailed breakdown for price_history (likely culprit)
        if "price_history" in analysis["table_counts"] and analysis["table_counts"]["price_history"] > 0:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM price_history
                GROUP BY strategy, market
            """)
            analysis["price_history_by_strategy"] = {f"{row['strategy']}/{row['market']}": row["count"] for row in cursor.fetchall()}

        # Detailed breakdown for candles
        if "candles" in analysis["table_counts"] and analysis["table_counts"]["candles"] > 0:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM candles
                GROUP BY strategy, market
            """)
            analysis["candles_by_strategy"] = {f"{row['strategy']}/{row['market']}": row["count"] for row in cursor.fetchall()}

        conn.close()

    except Exception as e:
        analysis["errors"].append(str(e))

    return analysis


def cleanup_old_data(db_path: str, dry_run: bool = False) -> dict:
    """
    Clean up old database data.

    Args:
        db_path: Path to database file
        dry_run: If True, only report what would be deleted without actually deleting

    Returns:
        dict with cleanup statistics
    """
    stats = {
        "price_history_deleted": 0,
        "candles_deleted": 0,
        "wal_checkpointed": False,
        "vacuumed": False,
        "errors": []
    }

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # 1. Clean old price history (keep only last 1000 per strategy)
        try:
            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM price_history
                GROUP BY strategy, market
            """)
            price_data = cursor.fetchall()

            for row in price_data:
                strategy = row["strategy"]
                market = row["market"]
                count = row["count"]

                if count > 1000:
                    if dry_run:
                        to_delete = count - 1000
                        stats["price_history_deleted"] += to_delete
                        LOG.info(f"[db_cleanup] Would delete {to_delete} old price points from {strategy}/{market}")
                    else:
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
                        stats["price_history_deleted"] += deleted
                        if deleted > 0:
                            LOG.info(f"[db_cleanup] Deleted {deleted} old price points from {strategy}/{market}")
        except sqlite3.OperationalError as e:
            stats["errors"].append(f"Price history cleanup: {e}")

        # 2. Clean old candles (keep only last 1000 per strategy, or >30 days)
        try:
            thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())

            cursor = conn.execute("""
                SELECT strategy, market, COUNT(*) as count
                FROM candles
                GROUP BY strategy, market
            """)
            candle_data = cursor.fetchall()

            for row in candle_data:
                strategy = row["strategy"]
                market = row["market"]
                count = row["count"]

                if count > 1000:
                    if dry_run:
                        to_delete = count - 1000
                        stats["candles_deleted"] += to_delete
                        LOG.info(f"[db_cleanup] Would delete {to_delete} old candles from {strategy}/{market}")
                    else:
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
                        stats["candles_deleted"] += deleted
                        if deleted > 0:
                            LOG.info(f"[db_cleanup] Deleted {deleted} old candles from {strategy}/{market}")

                # Also delete candles older than 30 days
                if not dry_run:
                    cursor = conn.execute("""
                        DELETE FROM candles
                        WHERE strategy = ? AND market = ? AND open_time < ?
                    """, (strategy, market, thirty_days_ago))
                    deleted = cursor.rowcount
                    if deleted > 0:
                        stats["candles_deleted"] += deleted
                        LOG.info(f"[db_cleanup] Deleted {deleted} candles older than 30 days from {strategy}/{market}")
        except sqlite3.OperationalError as e:
            stats["errors"].append(f"Candle cleanup: {e}")

        if not dry_run:
            # Commit deletions
            conn.commit()

            # 3. Vacuum database to reclaim space
            try:
                LOG.info("[db_cleanup] Vacuuming database...")
                conn.execute("VACUUM")
                stats["vacuumed"] = True
                LOG.info("[db_cleanup] ✅ Database vacuumed")
            except Exception as e:
                stats["errors"].append(f"Vacuum: {e}")

            # 4. Checkpoint WAL file
            try:
                LOG.info("[db_cleanup] Checkpointing WAL file...")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                stats["wal_checkpointed"] = True
                LOG.info("[db_cleanup] ✅ WAL checkpointed")
            except Exception as e:
                stats["errors"].append(f"WAL checkpoint: {e}")

        conn.close()

        return stats

    except Exception as e:
        LOG.exception(f"[db_cleanup] Error during cleanup: {e}")
        stats["errors"].append(str(e))
        return stats

