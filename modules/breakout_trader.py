# modules/breakout_trader.py
"""
Breakout + Momentum Strategy for SOL.

Strategy:
- Detects breakouts above recent highs (long) or below recent lows (short)
- Confirms with momentum (RSI + MACD)
- Filters by volatility (ATR expansion, BB width)
- Confirms trend (EMA alignment)
- Uses trailing stops and breakout failure exits

This strategy works best when SOL has explosive moves (5-10% breakouts).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.trading_client import TradingClient, PlacedOrder

LOG = logging.getLogger("breakout")


@dataclass
class Candle:
    """OHLCV candle (configurable interval)."""
    open_time: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Indicators:
    """Technical indicators computed from candles."""
    ema_20: float  # 20-period EMA
    ema_50: float  # 50-period EMA
    rsi: float  # 14-period RSI
    macd: float  # MACD line
    macd_signal: float  # MACD signal line
    macd_histogram: float  # MACD histogram
    atr: float  # 14-period ATR
    bb_upper: float  # Bollinger Band upper
    bb_middle: float  # Bollinger Band middle
    bb_lower: float  # Bollinger Band lower
    bb_width: float  # BB width (upper - lower) / middle
    volatility_bps: float  # Current volatility in basis points
    recent_high: float  # Highest high in lookback period
    recent_low: float  # Lowest low in lookback period
    breakout_level_long: Optional[float]  # Breakout level for longs
    breakout_level_short: Optional[float]  # Breakout level for shorts
    atr_expanding: bool  # ATR is increasing
    bb_width_expanding: bool  # BB width is increasing


@dataclass
class Signal:
    """Trading signal."""
    side: str  # "long" or "short"
    strength: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    reason: str
    breakout_level: float  # The level that was broken


class BreakoutTrader:
    """
    Breakout + Momentum trader for SOL.

    Entry conditions:
    - Long: Price breaks above recent high + RSI >60 + MACD bullish + ATR expanding + EMA alignment
    - Short: Price breaks below recent low + RSI <40 + MACD bearish + ATR expanding + EMA alignment

    Exit conditions:
    - Take profit: 2-3x ATR from entry
    - Trailing stop: After 1x ATR profit, trail by 0.5x ATR
    - Breakout failure: Price closes back below/above breakout level
    - Stop loss: 1.5x ATR below/above breakout level
    - Time stop: 60 minutes max hold
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any = None,
        trading_client: Optional[TradingClient] = None,
        alert_manager: Any = None,
        telemetry: Any = None,
    ):
        self.cfg = config or {}
        self.state = state
        self.trading_client = trading_client
        self.alerts = alert_manager
        self.telemetry = telemetry

        # Market config
        self.market = str(self.cfg.get("market", "market:2"))
        self.dry_run = bool(self.cfg.get("dry_run", True))
        self.candle_interval_seconds = int(self.cfg.get("candle_interval_seconds", 900))  # 15 minutes default

        # Indicator parameters
        self.ema_fast_period = int(self.cfg.get("ema_fast_period", 20))
        self.ema_slow_period = int(self.cfg.get("ema_slow_period", 50))
        self.rsi_period = int(self.cfg.get("rsi_period", 14))
        self.macd_fast = int(self.cfg.get("macd_fast", 12))
        self.macd_slow = int(self.cfg.get("macd_slow", 26))
        self.macd_signal = int(self.cfg.get("macd_signal", 9))
        self.atr_period = int(self.cfg.get("atr_period", 14))
        self.bb_period = int(self.cfg.get("bb_period", 20))
        self.bb_std = float(self.cfg.get("bb_std", 2.0))
        self.breakout_lookback = int(self.cfg.get("breakout_lookback", 30))  # 30 candles to find recent high/low

        # Entry filters
        self.rsi_bullish_threshold = float(self.cfg.get("rsi_bullish_threshold", 60.0))  # RSI >60 for longs
        self.rsi_bearish_threshold = float(self.cfg.get("rsi_bearish_threshold", 40.0))  # RSI <40 for shorts
        self.atr_min_bps = float(self.cfg.get("atr_min_bps", 3.0))  # Minimum volatility
        self.atr_max_bps = float(self.cfg.get("atr_max_bps", 15.0))  # Maximum volatility
        self.min_atr_expansion = float(self.cfg.get("min_atr_expansion", 1.1))  # ATR must be 10% higher than recent average

        # Risk management
        self.take_profit_atr_multiplier = float(self.cfg.get("take_profit_atr_multiplier", 2.5))  # 2.5x ATR TP
        self.stop_loss_atr_multiplier = float(self.cfg.get("stop_loss_atr_multiplier", 1.5))  # 1.5x ATR SL
        self.trailing_stop_activation_atr = float(self.cfg.get("trailing_stop_activation_atr", 1.0))  # Activate after 1x ATR profit
        self.trailing_stop_distance_atr = float(self.cfg.get("trailing_stop_distance_atr", 0.5))  # Trail by 0.5x ATR
        self.max_hold_minutes = int(self.cfg.get("max_hold_minutes", 60))  # 60 minutes max hold
        self.no_movement_minutes = int(self.cfg.get("no_movement_minutes", 30))  # Exit if no progress after 30 min

        # Position sizes
        self.max_position_size = float(self.cfg.get("max_position_size", 0.1))  # Max SOL per trade
        self.min_position_size = float(self.cfg.get("min_position_size", 0.1))  # Min SOL per trade

        # Position tracking
        self._candles: Deque[Candle] = deque(maxlen=200)
        self._current_position: Optional[Dict[str, Any]] = None
        self._open_orders: Dict[int, PlacedOrder] = {}
        self._order_timestamps: Dict[int, float] = {}
        self._order_timeout_seconds = 30.0
        self._stop = asyncio.Event()

        # Breakout tracking
        self._breakout_levels: Dict[str, float] = {}  # "long" or "short" -> breakout level
        self._breakout_confirmed: Dict[str, bool] = {}  # Track if breakout was confirmed (closed above/below)

        # Adaptive trading
        self._recent_pnl: Deque[float] = deque(maxlen=10)
        self._losing_streak = 0
        self._max_losing_streak_before_pause = 2  # Pause after 2 consecutive losses
        self._pause_until = 0.0
        self._pause_duration_seconds = 300  # 5 minutes

        # Cooldown
        self._last_exit_time = 0.0
        self._base_exit_cooldown_seconds = 20.0
        self._exit_cooldown_seconds = 20.0
        self._recent_exit_reasons: Deque[str] = deque(maxlen=5)

        # MFE/MAE tracking
        self._mfe_tracker: Dict[str, float] = {}
        self._mae_tracker: Dict[str, float] = {}

        # PnL tracker
        self.pnl_tracker = None

        LOG.info(
            f"[breakout] initialized: market={self.market}, "
            f"dry_run={self.dry_run}, candle_interval={self.candle_interval_seconds}s"
        )

    # ... (continuing with rest of implementation)

