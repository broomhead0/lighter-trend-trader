"""
PnL Tracker for high-volume trading.

Stores all trades in a database for fast aggregation and analysis.
Supports 100k+ trades with efficient queries.

Features:
- Database storage (SQLite for simplicity, can upgrade to PostgreSQL)
- Real-time WebSocket updates (optional)
- Fast aggregation queries (total PnL, win rate, etc.)
- Per-strategy tracking
- Historical analysis
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

LOG = logging.getLogger("pnl_tracker")


@dataclass
class TradeRecord:
    """Represents a completed trade."""
    strategy: str  # "mean_reversion" or "renko_ao"
    side: str  # "long" or "short"
    entry_price: float
    exit_price: float
    size: float
    pnl_pct: float
    pnl_usd: float  # Approximate USD value (price * size * pnl_pct)
    entry_time: float
    exit_time: float
    exit_reason: str  # "take_profit", "stop_loss", "time_stop", etc.
    market: str  # e.g., "market:2"


class PnLTracker:
    """
    Tracks PnL for high-volume trading using database storage.

    For 100k+ trades, this provides:
    - Fast storage (SQLite with WAL mode)
    - Efficient aggregation queries
    - Per-strategy breakdown
    - Historical analysis
    """

    def __init__(self, db_path: str = "pnl_trades.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache for better performance

            # Create trades table
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

            # Create indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy ON trades(strategy)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exit_time ON trades(exit_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market ON trades(market)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pnl_pct ON trades(pnl_pct)")

            conn.commit()
            self._conn = conn
            
            # Verify database is writable
            test_cursor = conn.execute("SELECT COUNT(*) FROM trades")
            test_cursor.fetchone()
            
            LOG.info(f"[pnl_tracker] ✅ Database initialized and verified: {self.db_path}")
        except Exception as e:
            LOG.exception(f"[pnl_tracker] ❌ CRITICAL: Failed to initialize database at {self.db_path}: {e}")
            raise

    async def record_trade(
        self,
        strategy: str,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
        pnl_pct: float,
        entry_time: float,
        exit_time: float,
        exit_reason: str,
        market: str,
    ) -> None:
        """Record a completed trade."""
        if not self._conn:
            LOG.error(f"[pnl_tracker] ❌ Cannot record trade: database connection is None (db_path={self.db_path})")
            raise RuntimeError("Database connection not initialized")
        
        # Calculate approximate USD PnL
        # For SOL, use exit_price as approximation (could be improved with actual USD conversion)
        pnl_usd = (pnl_pct / 100.0) * exit_price * size

        async with self._lock:
            try:
                # Verify database file exists and is writable
                if not os.path.exists(self.db_path):
                    LOG.error(f"[pnl_tracker] ❌ Database file does not exist: {self.db_path}")
                    raise FileNotFoundError(f"Database file not found: {self.db_path}")
                
                self._conn.execute("""
                    INSERT INTO trades (
                        strategy, side, entry_price, exit_price, size,
                        pnl_pct, pnl_usd, entry_time, exit_time,
                        exit_reason, market, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    strategy, side, entry_price, exit_price, size,
                    pnl_pct, pnl_usd, entry_time, exit_time,
                    exit_reason, market, time.time()
                ))
                self._conn.commit()
                
                # Verify the write succeeded
                verify_cursor = self._conn.execute("SELECT COUNT(*) FROM trades WHERE strategy = ? AND exit_time = ?", (strategy, exit_time))
                count = verify_cursor.fetchone()[0]
                if count == 0:
                    LOG.error(f"[pnl_tracker] ❌ Trade was not saved! Verification query returned 0 rows")
                    raise RuntimeError("Trade write verification failed")
                
                LOG.info(f"[pnl_tracker] ✅ Recorded trade: {strategy} {side} {pnl_pct:.2f}% (entry={entry_price:.2f}, exit={exit_price:.2f}, size={size:.4f}) - VERIFIED in DB")
            except Exception as e:
                LOG.exception(f"[pnl_tracker] ❌ Error recording trade: {e}")
                if self._conn:
                    self._conn.rollback()
                raise  # Re-raise to surface the error

    async def get_stats(
        self,
        strategy: Optional[str] = None,
        market: Optional[str] = None,
        since_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics.

        Returns:
            {
                "total_trades": int,
                "wins": int,
                "losses": int,
                "win_rate": float,
                "total_pnl_pct": float,
                "total_pnl_usd": float,
                "avg_pnl_pct": float,
                "avg_win_pct": float,
                "avg_loss_pct": float,
                "best_trade_pct": float,
                "worst_trade_pct": float,
            }
        """
        async with self._lock:
            try:
                # Build query
                conditions = []
                params = []

                if strategy:
                    conditions.append("strategy = ?")
                    params.append(strategy)
                if market:
                    conditions.append("market = ?")
                    params.append(market)
                if since_time:
                    conditions.append("exit_time >= ?")
                    params.append(since_time)

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                # Get basic stats
                result = self._conn.execute(f"""
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) as losses,
                        SUM(pnl_pct) as total_pnl_pct,
                        SUM(pnl_usd) as total_pnl_usd,
                        AVG(pnl_pct) as avg_pnl_pct,
                        AVG(CASE WHEN pnl_pct > 0 THEN pnl_pct ELSE NULL END) as avg_win_pct,
                        AVG(CASE WHEN pnl_pct < 0 THEN pnl_pct ELSE NULL END) as avg_loss_pct,
                        MAX(pnl_pct) as best_trade_pct,
                        MIN(pnl_pct) as worst_trade_pct
                    FROM trades
                    {where_clause}
                """, params).fetchone()

                total_trades, wins, losses, total_pnl_pct, total_pnl_usd, avg_pnl_pct, \
                    avg_win_pct, avg_loss_pct, best_trade_pct, worst_trade_pct = result

                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

                return {
                    "total_trades": total_trades or 0,
                    "wins": wins or 0,
                    "losses": losses or 0,
                    "win_rate": round(win_rate, 2),
                    "total_pnl_pct": round(total_pnl_pct or 0.0, 4),
                    "total_pnl_usd": round(total_pnl_usd or 0.0, 2),
                    "avg_pnl_pct": round(avg_pnl_pct or 0.0, 4),
                    "avg_win_pct": round(avg_win_pct or 0.0, 4) if avg_win_pct else 0.0,
                    "avg_loss_pct": round(avg_loss_pct or 0.0, 4) if avg_loss_pct else 0.0,
                    "best_trade_pct": round(best_trade_pct or 0.0, 4) if best_trade_pct else 0.0,
                    "worst_trade_pct": round(worst_trade_pct or 0.0, 4) if worst_trade_pct else 0.0,
                }
            except Exception as e:
                LOG.exception(f"[pnl_tracker] Error getting stats: {e}")
                return {}

    async def get_recent_trades(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent trades."""
        async with self._lock:
            try:
                rows = self._conn.execute("""
                    SELECT * FROM trades
                    ORDER BY exit_time DESC
                    LIMIT ?
                """, (limit,)).fetchall()

                columns = [desc[0] for desc in self._conn.execute("PRAGMA table_info(trades)").fetchall()]
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                LOG.exception(f"[pnl_tracker] Error getting recent trades: {e}")
                return []

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

