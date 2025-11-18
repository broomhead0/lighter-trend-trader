"""
Position State Tracker - Persists position state across deploys.

This module tracks open positions in a database so they survive deploys.
When a strategy enters a position, it's saved. On startup, positions are
automatically recovered and managed.

Features:
- Database-backed position storage (SQLite, same as PnL tracker)
- Automatic recovery on startup
- Position state includes: side, entry_price, size, stop_loss, take_profit, entry_time
- Per-strategy position tracking
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

LOG = logging.getLogger("position_tracker")


@dataclass
class PositionState:
    """Represents an open position state."""
    strategy: str  # "mean_reversion", "renko_ao", or "breakout"
    side: str  # "long" or "short"
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    entry_time: float
    entry_ao: float = 0.0  # For Renko+AO strategy
    order_index: int = 0
    initial_size: float = 0.0  # For scaled positions
    scaled_entries: str = "[]"  # JSON string of scaled entries
    market: str = "market:2"
    recovered: bool = False  # True if this was recovered from database


class PositionTracker:
    """
    Tracks open positions in a database for recovery after deploys.

    When a strategy enters a position, it's saved here. On startup,
    positions are automatically loaded and the strategy can resume managing them.
    """

    def __init__(self, db_path: str = "pnl_trades.db"):
        """
        Initialize position tracker.

        Uses the same database as PnL tracker for simplicity.
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for positions."""
        try:
            # Ensure directory exists
            import os
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            # Create positions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    entry_time REAL NOT NULL,
                    entry_ao REAL DEFAULT 0.0,
                    order_index INTEGER DEFAULT 0,
                    initial_size REAL DEFAULT 0.0,
                    scaled_entries TEXT DEFAULT '[]',
                    market TEXT NOT NULL DEFAULT 'market:2',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(strategy, market)
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_market ON positions(strategy, market)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON positions(entry_time)")

            conn.commit()
            self._conn = conn
            
            # Verify database is writable
            test_cursor = conn.execute("SELECT COUNT(*) FROM positions")
            test_cursor.fetchone()
            
            LOG.info(f"[position_tracker] ✅ Database initialized and verified: {self.db_path}")
        except Exception as e:
            LOG.exception(f"[position_tracker] ❌ CRITICAL: Failed to initialize database at {self.db_path}: {e}")
            raise

    async def save_position(self, strategy: str, position: Dict[str, Any], market: str = "market:2") -> None:
        """Save or update a position state."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                # Convert scaled_entries to JSON string if it's a list
                scaled_entries = position.get("scaled_entries", [])
                if isinstance(scaled_entries, list):
                    import json
                    scaled_entries = json.dumps(scaled_entries)
                else:
                    scaled_entries = str(scaled_entries)

                now = time.time()

                # Use INSERT OR REPLACE to handle updates
                conn.execute("""
                    INSERT OR REPLACE INTO positions (
                        strategy, side, entry_price, size, stop_loss, take_profit,
                        entry_time, entry_ao, order_index, initial_size,
                        scaled_entries, market, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM positions WHERE strategy=? AND market=?), ?),
                        ?)
                """, (
                    strategy,
                    position.get("side"),
                    position.get("entry_price"),
                    position.get("size"),
                    position.get("stop_loss"),
                    position.get("take_profit"),
                    position.get("entry_time"),
                    position.get("entry_ao", 0.0),
                    position.get("order_index", 0),
                    position.get("initial_size", position.get("size", 0.0)),
                    scaled_entries,
                    market,
                    now,  # created_at fallback
                    strategy,  # for SELECT in COALESCE
                    market,  # for SELECT in COALESCE
                    now,  # updated_at
                ))

                conn.commit()
                LOG.debug(f"[position_tracker] Saved position for {strategy}: {position.get('side')} {position.get('size'):.4f} @ {position.get('entry_price'):.2f}")
            except Exception as e:
                LOG.exception(f"[position_tracker] Error saving position: {e}")

    async def load_position(self, strategy: str, market: str = "market:2") -> Optional[Dict[str, Any]]:
        """Load position state for a strategy."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return None

                cursor = conn.execute("""
                    SELECT side, entry_price, size, stop_loss, take_profit,
                           entry_time, entry_ao, order_index, initial_size,
                           scaled_entries, market
                    FROM positions
                    WHERE strategy = ? AND market = ?
                """, (strategy, market))

                row = cursor.fetchone()
                if not row:
                    return None

                # Parse scaled_entries JSON
                scaled_entries_str = row[9] or "[]"
                try:
                    import json
                    scaled_entries = json.loads(scaled_entries_str)
                except:
                    scaled_entries = []

                position = {
                    "side": row[0],
                    "entry_price": row[1],
                    "size": row[2],
                    "stop_loss": row[3],
                    "take_profit": row[4],
                    "entry_time": row[5],
                    "entry_ao": row[6] or 0.0,
                    "order_index": row[7] or 0,
                    "initial_size": row[8] or row[2],  # Fallback to size if not set
                    "scaled_entries": scaled_entries,
                    "recovered": True,  # Mark as recovered
                }

                LOG.info(
                    f"[position_tracker] Loaded position for {strategy}: "
                    f"{position['side']} {position['size']:.4f} @ {position['entry_price']:.2f} "
                    f"(entry_time: {position['entry_time']:.0f})"
                )
                return position
            except Exception as e:
                LOG.exception(f"[position_tracker] Error loading position: {e}")
                return None

    async def delete_position(self, strategy: str, market: str = "market:2") -> None:
        """Delete a position (called when position is closed)."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return

                conn.execute("DELETE FROM positions WHERE strategy = ? AND market = ?", (strategy, market))
                conn.commit()
                LOG.debug(f"[position_tracker] Deleted position for {strategy}")
            except Exception as e:
                LOG.exception(f"[position_tracker] Error deleting position: {e}")

    async def list_all_positions(self) -> list[Dict[str, Any]]:
        """List all open positions across all strategies."""
        async with self._lock:
            try:
                conn = self._conn
                if not conn:
                    return []

                cursor = conn.execute("""
                    SELECT strategy, side, entry_price, size, stop_loss, take_profit,
                           entry_time, market
                    FROM positions
                    ORDER BY strategy, market
                """)

                positions = []
                for row in cursor.fetchall():
                    positions.append({
                        "strategy": row[0],
                        "side": row[1],
                        "entry_price": row[2],
                        "size": row[3],
                        "stop_loss": row[4],
                        "take_profit": row[5],
                        "entry_time": row[6],
                        "market": row[7],
                    })

                return positions
            except Exception as e:
                LOG.exception(f"[position_tracker] Error listing positions: {e}")
                return []

