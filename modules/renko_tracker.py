"""
Renko State Tracker - Persists Renko bricks and price history across deploys.

This module tracks Renko bricks and price history in a database so they survive deploys.
When a strategy builds bricks, they're saved. On startup, bricks are automatically
recovered so the strategy can resume immediately.

Features:
- Database-backed brick storage (SQLite, same as PnL tracker)
- Automatic recovery on startup
- Per-strategy brick tracking
- Supports multiple markets
- Price history persistence for ATR/AO calculations
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("renko_tracker")


class RenkoTracker:
    """
    Tracks Renko bricks and price history in a database for recovery after deploys.

    When a strategy builds bricks, they're saved here. On startup,
    bricks are automatically loaded so the strategy can resume immediately.
    """

    def __init__(self, db_path: str = "pnl_trades.db"):
        """
        Initialize Renko tracker.

        Uses the same database as PnL tracker for simplicity.
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for Renko bricks and price history."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # Create renko_bricks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS renko_bricks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                market TEXT NOT NULL,
                open_time INTEGER NOT NULL,
                open REAL NOT NULL,
                close REAL NOT NULL,
                direction TEXT NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(strategy, market, open_time)
            )
        """)

        # Create price_history table
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

        # Create indexes for fast queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_renko_strategy_market ON renko_bricks(strategy, market)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_renko_open_time ON renko_bricks(open_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_strategy_market ON price_history(strategy, market)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp)")

        conn.commit()
        self._conn = conn
        LOG.info(f"[renko_tracker] Database initialized: {self.db_path}")

    async def save_bricks(self, strategy: str, market: str, bricks: List[Dict[str, Any]]) -> None:
        """Save or update Renko bricks for a strategy."""
        if not bricks:
            return

        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                now = time.time()

                # Use INSERT OR REPLACE to handle updates
                for brick in bricks:
                    conn.execute("""
                        INSERT OR REPLACE INTO renko_bricks (
                            strategy, market, open_time, open, close, direction, high, low, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        strategy,
                        market,
                        brick.get("open_time") or 0,
                        brick.get("open") or 0.0,
                        brick.get("close") or 0.0,
                        brick.get("direction") or "up",
                        brick.get("high") or brick.get("close") or 0.0,
                        brick.get("low") or brick.get("close") or 0.0,
                        now,
                    ))

                conn.commit()
                LOG.debug(f"[renko_tracker] Saved {len(bricks)} bricks for {strategy} {market}")
            except Exception as e:
                LOG.exception(f"[renko_tracker] Error saving bricks: {e}")

    async def load_bricks(self, strategy: str, market: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Load Renko bricks for a strategy, sorted by open_time."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return []

                cursor = conn.execute("""
                    SELECT open_time, open, close, direction, high, low
                    FROM renko_bricks
                    WHERE strategy = ? AND market = ?
                    ORDER BY open_time ASC
                    LIMIT ?
                """, (strategy, market, limit))

                bricks = []
                for row in cursor.fetchall():
                    bricks.append({
                        "open_time": row[0],
                        "open": row[1],
                        "close": row[2],
                        "direction": row[3],
                        "high": row[4],
                        "low": row[5],
                    })

                if bricks:
                    LOG.info(f"[renko_tracker] ✅ Loaded {len(bricks)} bricks for {strategy} {market} (oldest: {bricks[0]['open_time']}, newest: {bricks[-1]['open_time']})")
                return bricks
            except Exception as e:
                LOG.exception(f"[renko_tracker] Error loading bricks: {e}")
                return []

    async def save_price_history(self, strategy: str, market: str, prices: List[float], timestamps: Optional[List[float]] = None) -> None:
        """Save price history for a strategy."""
        if not prices:
            return

        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                now = time.time()
                if timestamps is None:
                    timestamps = [now - (len(prices) - i) for i in range(len(prices))]

                # Clear old history and save new (keep last 1000)
                conn.execute("DELETE FROM price_history WHERE strategy = ? AND market = ?", (strategy, market))

                for price, ts in zip(prices[-1000:], timestamps[-1000:]):  # Keep last 1000
                    conn.execute("""
                        INSERT INTO price_history (
                            strategy, market, price, timestamp, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (strategy, market, price, ts, now))

                conn.commit()
                LOG.debug(f"[renko_tracker] Saved {len(prices)} price points for {strategy} {market}")
            except Exception as e:
                LOG.exception(f"[renko_tracker] Error saving price history: {e}")

    async def load_price_history(self, strategy: str, market: str, limit: int = 1000) -> List[float]:
        """Load price history for a strategy, sorted by timestamp."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return []

                cursor = conn.execute("""
                    SELECT price
                    FROM price_history
                    WHERE strategy = ? AND market = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (strategy, market, limit))

                prices = [row[0] for row in cursor.fetchall()]

                if prices:
                    LOG.info(f"[renko_tracker] ✅ Loaded {len(prices)} price points for {strategy} {market}")
                return prices
            except Exception as e:
                LOG.exception(f"[renko_tracker] Error loading price history: {e}")
                return []

    async def clear_bricks(self, strategy: str, market: str) -> None:
        """Clear all bricks for a strategy (optional cleanup)."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                conn.execute("DELETE FROM renko_bricks WHERE strategy = ? AND market = ?", (strategy, market))
                conn.commit()
                LOG.debug(f"[renko_tracker] Cleared bricks for {strategy} {market}")
            except Exception as e:
                LOG.exception(f"[renko_tracker] Error clearing bricks: {e}")

