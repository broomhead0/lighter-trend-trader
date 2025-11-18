"""
Candle State Tracker - Persists candle data across deploys.

This module tracks OHLCV candles in a database so they survive deploys.
When a strategy builds candles, they're saved. On startup, candles are
automatically recovered so the strategy can resume immediately.

Features:
- Database-backed candle storage (SQLite, same as PnL tracker)
- Automatic recovery on startup
- Per-strategy candle tracking
- Supports multiple markets
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("candle_tracker")


@dataclass
class CandleData:
    """Represents a single candle."""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleTracker:
    """
    Tracks candles in a database for recovery after deploys.

    When a strategy builds candles, they're saved here. On startup,
    candles are automatically loaded so the strategy can resume immediately.
    """

    def __init__(self, db_path: str = "pnl_trades.db"):
        """
        Initialize candle tracker.

        Uses the same database as PnL tracker for simplicity.
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for candles."""
        try:
            # Ensure directory exists
            import os
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            # Create candles table
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

            # Create indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_market ON candles(strategy, market)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_open_time ON candles(open_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_market_time ON candles(strategy, market, open_time)")

            conn.commit()
            self._conn = conn
            
            # Verify database is writable
            test_cursor = conn.execute("SELECT COUNT(*) FROM candles")
            test_cursor.fetchone()
            
            LOG.info(f"[candle_tracker] ✅ Database initialized and verified: {self.db_path}")
        except Exception as e:
            LOG.exception(f"[candle_tracker] ❌ CRITICAL: Failed to initialize database at {self.db_path}: {e}")
            raise

    async def save_candles(self, strategy: str, market: str, candles: List[Dict[str, Any]]) -> None:
        """Save or update candles for a strategy."""
        if not candles:
            return

        if not self._conn:
            LOG.error(f"[candle_tracker] ❌ Cannot save candles: database connection is None (db_path={self.db_path})")
            return

        async with self._lock:
            try:
                # Verify database file exists
                if not os.path.exists(self.db_path):
                    LOG.error(f"[candle_tracker] ❌ Database file does not exist: {self.db_path}")
                    return
                
                now = time.time()

                # Use INSERT OR REPLACE to handle updates
                for candle in candles:
                    self._conn.execute("""
                        INSERT OR REPLACE INTO candles (
                            strategy, market, open_time, open, high, low, close, volume, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        strategy,
                        market,
                        candle.get("open_time") or candle.get("openTime") or 0,
                        candle.get("open") or 0.0,
                        candle.get("high") or 0.0,
                        candle.get("low") or 0.0,
                        candle.get("close") or 0.0,
                        candle.get("volume") or 0.0,
                        now,
                    ))

                self._conn.commit()
                
                # Verify the write succeeded
                verify_cursor = self._conn.execute(
                    "SELECT COUNT(*) FROM candles WHERE strategy = ? AND market = ?",
                    (strategy, market)
                )
                count = verify_cursor.fetchone()[0]
                
                LOG.info(f"[candle_tracker] ✅ Saved {len(candles)} candles for {strategy} {market} (total in DB: {count})")
            except Exception as e:
                LOG.exception(f"[candle_tracker] ❌ Error saving candles: {e}")
                if self._conn:
                    self._conn.rollback()

    async def load_candles(self, strategy: str, market: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Load candles for a strategy, sorted by open_time."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return []

                # Debug: Check what's in the database
                debug_cursor = conn.execute("""
                    SELECT COUNT(*) FROM candles WHERE strategy = ? AND market = ?
                """, (strategy, market))
                count = debug_cursor.fetchone()[0]
                LOG.info(f"[candle_tracker] DEBUG: Found {count} candles in DB for {strategy} {market} (db_path={self.db_path})")

                # Also check all strategies/markets
                all_cursor = conn.execute("SELECT strategy, market, COUNT(*) FROM candles GROUP BY strategy, market")
                all_counts = all_cursor.fetchall()
                if all_counts:
                    LOG.info(f"[candle_tracker] DEBUG: All candles in DB: {all_counts}")

                cursor = conn.execute("""
                    SELECT open_time, open, high, low, close, volume
                    FROM candles
                    WHERE strategy = ? AND market = ?
                    ORDER BY open_time ASC
                    LIMIT ?
                """, (strategy, market, limit))

                candles = []
                for row in cursor.fetchall():
                    candles.append({
                        "open_time": row[0],
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5],
                    })

                if candles:
                    LOG.info(f"[candle_tracker] ✅ Loaded {len(candles)} candles for {strategy} {market} (oldest: {candles[0]['open_time']}, newest: {candles[-1]['open_time']})")
                else:
                    LOG.warning(f"[candle_tracker] ⚠️ No candles loaded for {strategy} {market} (query returned 0 rows)")
                return candles
            except Exception as e:
                LOG.exception(f"[candle_tracker] Error loading candles: {e}")
                return []

    async def clear_candles(self, strategy: str, market: str) -> None:
        """Clear all candles for a strategy (optional cleanup)."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                conn.execute("DELETE FROM candles WHERE strategy = ? AND market = ?", (strategy, market))
                conn.commit()
                LOG.debug(f"[candle_tracker] Cleared candles for {strategy} {market}")
            except Exception as e:
                LOG.exception(f"[candle_tracker] Error clearing candles: {e}")

