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

