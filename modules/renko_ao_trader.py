# modules/renko_ao_trader.py
"""
Renko + Awesome Oscillator Divergence Strategy.

Strategy:
- Uses Renko candles (3-tick bricks) to filter noise
- Detects divergences between Renko price action and Awesome Oscillator (AO)
- Bullish divergence: Price makes lower lows, AO makes higher lows → Long signal
- Bearish divergence: Price makes higher highs, AO makes lower highs → Short signal
- Enhanced signal if divergence occurs near/in Bollinger Bands
- Waits for mean reversion after divergence confirmation

This strategy works best in trending markets with pullbacks.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.trading_client import TradingClient, PlacedOrder

LOG = logging.getLogger("renko_ao")


@dataclass
class RenkoBrick:
    """Renko brick (price-based, not time-based)."""
    open_time: int  # Unix timestamp in seconds
    open: float
    close: float
    direction: str  # "up" or "down"
    high: float
    low: float


@dataclass
class Indicators:
    """Technical indicators computed from Renko bricks."""
    ao: float  # Awesome Oscillator (current value)
    ao_prev: float  # Previous AO value
    ao_trend: str  # "bullish", "bearish", or "neutral"
    bb_upper: float  # Bollinger Band upper
    bb_middle: float  # Bollinger Band middle (SMA)
    bb_lower: float  # Bollinger Band lower
    price_position_bb: float  # Position in BB range (0.0 = lower, 1.0 = upper)
    divergence_type: Optional[str]  # "bullish", "bearish", or None
    divergence_strength: float  # 0.0 to 1.0


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


class RenkoAOTrader:
    """
    Renko + AO divergence trader.

    Entry conditions:
    - Bullish divergence: Renko makes lower low, AO makes higher low → Long
    - Bearish divergence: Renko makes higher high, AO makes lower high → Short
    - Enhanced if divergence occurs near/in Bollinger Bands
    - Wait for mean reversion confirmation

    Exit conditions:
    - Take profit: price reaches target or AO reverses
    - Stop loss: price continues against us
    - Time stop: exit after max hold time
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

        trader_cfg = (self.cfg.get("renko_ao") or {}) if isinstance(self.cfg.get("renko_ao"), dict) else {}

        # Market
        self.market = str(trader_cfg.get("market", "market:2"))
        self.dry_run = bool(trader_cfg.get("dry_run", True))

        # Renko parameters (ATR-based)
        self.renko_atr_period = int(trader_cfg.get("renko_atr_period", 14))  # ATR period for brick size
        self.renko_atr_multiplier = float(trader_cfg.get("renko_atr_multiplier", 1.0))  # ATR multiplier for brick size
        self.renko_lookback = int(trader_cfg.get("renko_lookback", 20))  # Look back 20 bricks for divergence
        self._current_renko_brick_size: Optional[float] = None  # Dynamic brick size based on ATR

        # Awesome Oscillator parameters
        self.ao_fast_period = int(trader_cfg.get("ao_fast_period", 5))
        self.ao_slow_period = int(trader_cfg.get("ao_slow_period", 34))

        # Bollinger Bands parameters
        self.bb_period = int(trader_cfg.get("bb_period", 20))
        self.bb_std = float(trader_cfg.get("bb_std", 2.0))

        # Entry filters
        self.bb_enhancement_threshold = float(trader_cfg.get("bb_enhancement_threshold", 0.2))  # Within 20% of BB edge
        self.min_divergence_strength = float(trader_cfg.get("min_divergence_strength", 0.05))  # Increased from 0.03 to be more selective (need 35.9% WR, currently 23.5%)

        # Risk management
        self.take_profit_bps = float(trader_cfg.get("take_profit_bps", 12.0))  # Increased from 10.0 for better R:R
        self.stop_loss_bps = float(trader_cfg.get("stop_loss_bps", 7.0))  # Tightened from 8.0 to 7.0 to improve win rate (R:R already good at 1.79:1)
        self.max_hold_minutes = int(trader_cfg.get("max_hold_minutes", 8))  # Increased from 5 to reduce time stops
        self.risk_per_trade_pct = float(trader_cfg.get("risk_per_trade_pct", 1.0))
        # Position sizes - Lighter minimum is 0.001 SOL, but there may be a minimum notional requirement
        # At ~141 SOL price, 0.05 SOL = ~$7 notional (still rejected with code=21706)
        # Using 0.1 SOL (~$14 notional) to ensure we meet minimum quote amount requirements
        # Defaults are set in code (single source of truth) but can be overridden by config/env
        self.max_position_size = float(trader_cfg.get("max_position_size", 0.1))  # Max SOL per trade (default: 0.1 for $100 account)
        self.min_position_size = float(trader_cfg.get("min_position_size", 0.1))  # Min SOL per trade (default: 0.1 to meet minimum notional)

        # State
        self._renko_bricks: Deque[RenkoBrick] = deque(maxlen=200)
        self._current_brick: Optional[RenkoBrick] = None
        self._price_history: Deque[float] = deque(maxlen=1000)  # For ATR and AO calculation
        self._current_position: Optional[Dict[str, Any]] = None
        self._open_orders: Dict[int, PlacedOrder] = {}
        self._order_timestamps: Dict[int, float] = {}  # client_order_index -> creation timestamp
        self._order_timeout_seconds = 30.0  # Cancel orders that haven't filled after 30 seconds
        self._stop = asyncio.Event()

        # Adaptive trading: track recent performance
        self._recent_pnl: Deque[float] = deque(maxlen=10)  # Track last 10 trades
        self._losing_streak = 0
        self._max_losing_streak_before_pause = 5  # Increased from 3 to 5 for Renko (needs time to play out)
        self._pause_until = 0.0  # Timestamp to resume trading after pause
        self._pause_duration_seconds = 180  # Reduced from 300 to 180s (3 min) - shorter pause for Renko

        # Position scaling/averaging in for divergence strategies
        self._enable_scaling = bool(trader_cfg.get("enable_scaling", True))  # Enable averaging in
        self._max_scales = int(trader_cfg.get("max_scales", 3))  # Max 3 additional entries (4 total)
        self._scale_interval_seconds = float(trader_cfg.get("scale_interval_seconds", 60.0))  # Scale every 60s if divergence persists
        self._scale_price_threshold_bps = float(trader_cfg.get("scale_price_threshold_bps", 5.0))  # Scale if price moves 5 bps against us
        self._scale_size_multiplier = float(trader_cfg.get("scale_size_multiplier", 0.5))  # Each scale is 50% of initial size
        self._scaled_entries: List[Dict[str, Any]] = []  # Track scaled entries for average entry price

        # Position cooldown: prevent position accumulation (adaptive based on volatility/performance)
        self._last_exit_time = 0.0  # Timestamp of last exit
        self._base_exit_cooldown_seconds = 10.0  # Base cooldown: 10 seconds
        self._exit_cooldown_seconds = 10.0  # Current cooldown (adaptive)
        self._recent_exit_reasons: Deque[str] = deque(maxlen=5)  # Track recent exit reasons

        LOG.info(
            "[renko_ao] initialized: market=%s dry_run=%s renko_atr_period=%d renko_atr_multiplier=%.2f min_size=%.6f max_size=%.6f",
            self.market,
            self.dry_run,
            self.renko_atr_period,
            self.renko_atr_multiplier,
            self.min_position_size,
            self.max_position_size,
        )

    async def run(self):
        """Main trading loop."""
        LOG.info("[renko_ao] starting trading loop")
        while not self._stop.is_set():
            try:
                current_price = self._get_current_price()
                if current_price is None:
                    await asyncio.sleep(1.0)
                    continue

                # Update price history for ATR calculation
                self._price_history.append(current_price)

                # Calculate ATR and update Renko brick size
                atr = self._calculate_atr()
                if atr is not None:
                    self._current_renko_brick_size = atr * self.renko_atr_multiplier
                elif len(self._price_history) < self.renko_atr_period:
                    # Not enough data yet, use a default small size
                    self._current_renko_brick_size = current_price * 0.001  # 0.1% as fallback

                # Update Renko bricks
                if self._current_renko_brick_size:
                    self._update_renko(current_price)

                # Need enough bricks for indicators
                needed_bricks = max(self.bb_period, self.ao_slow_period, self.renko_lookback)
                if len(self._renko_bricks) < needed_bricks:
                    if len(self._renko_bricks) % 5 == 0 or len(self._renko_bricks) == 0:  # Log every 5 bricks or first brick
                        atr_display = f"{self._current_renko_brick_size:.4f}" if self._current_renko_brick_size else "0.0000"
                        LOG.info(f"[renko_ao] collecting bricks: {len(self._renko_bricks)}/{needed_bricks}, ATR={atr_display}, price_history={len(self._price_history)}")
                    await asyncio.sleep(1.0)
                    continue

                # Cancel stale orders (orders that haven't filled after timeout)
                await self._cancel_stale_orders()

                # Compute indicators
                indicators = self._compute_indicators(current_price)
                if indicators is None:
                    await asyncio.sleep(1.0)
                    continue

                # Log indicator values periodically
                if int(time.time()) % 30 == 0:  # Every 30 seconds
                    LOG.info(f"[renko_ao] indicators: AO={indicators.ao:.4f}, AO_trend={indicators.ao_trend}, divergence={indicators.divergence_type}, strength={indicators.divergence_strength:.2f}, BB_pos={indicators.price_position_bb:.2f}")

                # Check for exit first
                if self._current_position:
                    exit_reason = self._check_exit(current_price, indicators)
                    if exit_reason:
                        await self._exit_position(exit_reason)
                    elif self._enable_scaling:
                        # Check if we should scale into the position (average in)
                        await self._check_scale_in(current_price, indicators)
                else:
                    # Adaptive trading: check if we should pause after losing streak
                    if time.time() < self._pause_until:
                        if int(time.time()) % 30 == 0:  # Log every 30 seconds
                            LOG.info(f"[renko_ao] paused due to losing streak, resuming in {int(self._pause_until - time.time())}s")
                        await asyncio.sleep(1.0)
                        continue

                    # Adaptive position cooldown: prevent position accumulation
                    # Adjust cooldown based on volatility and recent performance
                    self._update_adaptive_cooldown(indicators, current_price)
                    time_since_exit = time.time() - self._last_exit_time
                    if time_since_exit < self._exit_cooldown_seconds:
                        if int(time.time()) % 10 == 0:  # Log every 10 seconds
                            LOG.info(f"[renko_ao] exit cooldown: waiting {self._exit_cooldown_seconds - time_since_exit:.1f}s before new entry (adaptive, base={self._base_exit_cooldown_seconds:.1f}s)")
                        await asyncio.sleep(1.0)
                        continue

                    # Check for entry
                    signal = self._check_entry(current_price, indicators)
                    if signal:
                        await self._enter_position(signal)
                    elif indicators.divergence_type:
                        # Log when divergence detected but signal not generated
                        LOG.debug(f"[renko_ao] divergence detected ({indicators.divergence_type}) but no signal: strength={indicators.divergence_strength:.2f} < {self.min_divergence_strength:.2f}")

                self._update_telemetry(indicators, current_price)

                await asyncio.sleep(1.0)  # Check every second

            except Exception as e:
                LOG.exception("[renko_ao] error in trading loop: %s", e)
                await asyncio.sleep(5.0)

    async def stop(self):
        """Stop the trader."""
        self._stop.set()
        LOG.info("[renko_ao] stopping")

    # ------------------------- Renko Brick Building -------------------------

    def _calculate_atr(self) -> Optional[float]:
        """Calculate Average True Range (ATR) for Renko brick sizing."""
        if len(self._price_history) < self.renko_atr_period + 1:
            return None

        # Calculate True Range for each period
        # Since we get mid prices from WebSocket, use price changes as True Range approximation
        true_ranges = []
        for i in range(1, len(self._price_history)):
            if i >= len(self._price_history):
                break
            # Use price change as True Range (since we only have mid prices)
            # This is a reasonable approximation for ATR
            price_change = abs(self._price_history[i] - self._price_history[i - 1])
            true_ranges.append(price_change)

        if not true_ranges or len(true_ranges) < self.renko_atr_period:
            return None

        # ATR is the average of the last N True Ranges
        recent_trs = true_ranges[-self.renko_atr_period:]
        atr = sum(recent_trs) / len(recent_trs)
        return atr

    def _update_renko(self, price: float) -> None:
        """Update Renko bricks based on price movement (ATR-based brick size)."""
        if self._current_renko_brick_size is None or self._current_renko_brick_size <= 0:
            return

        if self._current_brick is None:
            # Initialize first brick
            self._current_brick = RenkoBrick(
                open_time=int(time.time()),
                open=price,
                close=price,
                direction="neutral",
                high=price,
                low=price,
            )
            return

        # Check if price moved enough to form a new brick (using ATR-based size)
        price_change = abs(price - self._current_brick.close)

        if price_change >= self._current_renko_brick_size:
            # Close current brick and start new one
            if price > self._current_brick.close:
                # Upward brick
                new_close = self._current_brick.close + self._current_renko_brick_size
                direction = "up"
            else:
                # Downward brick
                new_close = self._current_brick.close - self._current_renko_brick_size
                direction = "down"

            # Finalize current brick
            self._current_brick.close = new_close
            self._current_brick.direction = direction
            self._current_brick.high = max(self._current_brick.high, price)
            self._current_brick.low = min(self._current_brick.low, price)

            # Add to history
            self._renko_bricks.append(self._current_brick)
            self._price_history.append(new_close)

            # Start new brick
            self._current_brick = RenkoBrick(
                open_time=int(time.time()),
                open=new_close,
                close=new_close,
                direction="neutral",
                high=price,
                low=price,
            )

            LOG.info(f"[renko_ao] new brick: {direction} @ {new_close:.2f}, brick_size={self._current_renko_brick_size:.4f}, total bricks: {len(self._renko_bricks)}")
        else:
            # Update current brick high/low
            self._current_brick.high = max(self._current_brick.high, price)
            self._current_brick.low = min(self._current_brick.low, price)
            self._current_brick.close = price

    # ------------------------- Indicator Computation -------------------------

    def _compute_indicators(self, price: float) -> Optional[Indicators]:
        """Compute technical indicators from Renko bricks."""
        if len(self._renko_bricks) < max(self.bb_period, self.ao_slow_period):
            return None

        # Get brick closes for calculations
        brick_closes = [brick.close for brick in self._renko_bricks]

        # Awesome Oscillator
        ao = self._calculate_ao(brick_closes)
        if ao is None:
            return None

        # Previous AO (need at least 2 values)
        if len(self._renko_bricks) < self.ao_slow_period + 1:
            ao_prev = ao
        else:
            prev_closes = [brick.close for brick in list(self._renko_bricks)[:-1]]
            ao_prev = self._calculate_ao(prev_closes) or ao

        # AO trend
        if ao > ao_prev:
            ao_trend = "bullish"
        elif ao < ao_prev:
            ao_trend = "bearish"
        else:
            ao_trend = "neutral"

        # Bollinger Bands
        bb_middle = sum(brick_closes[-self.bb_period:]) / self.bb_period
        variance = sum((x - bb_middle) ** 2 for x in brick_closes[-self.bb_period:]) / self.bb_period
        std_dev = math.sqrt(variance)
        bb_upper = bb_middle + (self.bb_std * std_dev)
        bb_lower = bb_middle - (self.bb_std * std_dev)

        # Price position in BB range
        if bb_upper > bb_lower:
            price_position_bb = (price - bb_lower) / (bb_upper - bb_lower)
        else:
            price_position_bb = 0.5

        # Divergence detection
        divergence_type, divergence_strength = self._detect_divergence(brick_closes, ao, ao_prev)

        return Indicators(
            ao=ao,
            ao_prev=ao_prev,
            ao_trend=ao_trend,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            price_position_bb=price_position_bb,
            divergence_type=divergence_type,
            divergence_strength=divergence_strength,
        )

    def _calculate_ao(self, prices: List[float]) -> Optional[float]:
        """Calculate Awesome Oscillator (AO)."""
        if len(prices) < self.ao_slow_period:
            return None

        # AO = SMA(5) - SMA(34) of median prices (high+low)/2
        # For Renko, we use close prices
        fast_ma = sum(prices[-self.ao_fast_period:]) / self.ao_fast_period
        slow_ma = sum(prices[-self.ao_slow_period:]) / self.ao_slow_period
        ao = fast_ma - slow_ma

        return ao

    def _detect_divergence(self, prices: List[float], ao: float, ao_prev: float) -> Tuple[Optional[str], float]:
        """
        Detect divergence between price and AO.

        Returns:
            (divergence_type, strength) where type is "bullish", "bearish", or None
        """
        if len(prices) < self.renko_lookback:
            return None, 0.0

        # Get recent price extremes
        recent_prices = prices[-self.renko_lookback:]

        # Find recent lows and highs
        recent_lows = []
        recent_highs = []

        for i in range(1, len(recent_prices) - 1):
            if recent_prices[i] < recent_prices[i-1] and recent_prices[i] < recent_prices[i+1]:
                recent_lows.append((i, recent_prices[i]))
            if recent_prices[i] > recent_prices[i-1] and recent_prices[i] > recent_prices[i+1]:
                recent_highs.append((i, recent_prices[i]))

        # Need at least 2 lows for bullish divergence, 2 highs for bearish
        if len(recent_lows) < 2 and len(recent_highs) < 2:
            return None, 0.0

        # Bullish divergence: price makes lower low, AO should make higher low
        if len(recent_lows) >= 2:
            # Sort by index (time)
            recent_lows.sort(key=lambda x: x[0])
            latest_low_idx, latest_low_price = recent_lows[-1]
            prev_low_idx, prev_low_price = recent_lows[-2]

            if latest_low_price < prev_low_price:  # Price made lower low
                # Check if AO is trending up (making higher low)
                if ao > ao_prev:  # AO is increasing
                    strength = (prev_low_price - latest_low_price) / prev_low_price if prev_low_price > 0 else 0.0
                    return "bullish", min(1.0, strength * 100)  # Scale strength

        # Bearish divergence: price makes higher high, AO should make lower high
        if len(recent_highs) >= 2:
            recent_highs.sort(key=lambda x: x[0])
            latest_high_idx, latest_high_price = recent_highs[-1]
            prev_high_idx, prev_high_price = recent_highs[-2]

            if latest_high_price > prev_high_price:  # Price made higher high
                # Check if AO is trending down (making lower high)
                if ao < ao_prev:  # AO is decreasing
                    strength = (latest_high_price - prev_high_price) / prev_high_price if prev_high_price > 0 else 0.0
                    return "bearish", min(1.0, strength * 100)  # Scale strength

        return None, 0.0

    # ------------------------- Signal Generation -------------------------

    def _check_entry(self, price: float, indicators: Indicators) -> Optional[Signal]:
        """Check for entry signals based on divergence."""
        if indicators.divergence_type is None:
            return None

        if indicators.divergence_strength < self.min_divergence_strength:
            return None

        # Check BB enhancement
        bb_enhanced = False
        if indicators.divergence_type == "bullish":
            # Bullish divergence near lower BB
            if indicators.price_position_bb <= self.bb_enhancement_threshold:
                bb_enhanced = True
        elif indicators.divergence_type == "bearish":
            # Bearish divergence near upper BB
            if indicators.price_position_bb >= (1.0 - self.bb_enhancement_threshold):
                bb_enhanced = True

        # Create signal
        side = "long" if indicators.divergence_type == "bullish" else "short"
        strength = indicators.divergence_strength
        if bb_enhanced:
            strength = min(1.0, strength * 1.5)  # Boost strength if BB enhanced

        reason = f"{indicators.divergence_type} divergence"
        if bb_enhanced:
            reason += " + BB enhanced"

        return self._create_signal(side, price, indicators, strength, reason)

    def _create_signal(self, side: str, price: float, indicators: Indicators, strength: float, reason: str) -> Signal:
        """Create a trading signal with risk management."""
        # Calculate stop loss and take profit
        if side == "long":
            stop_loss = price * (1 - self.stop_loss_bps / 10000)
            take_profit = price * (1 + self.take_profit_bps / 10000)
        else:  # short
            stop_loss = price * (1 + self.stop_loss_bps / 10000)
            take_profit = price * (1 - self.take_profit_bps / 10000)

        # Position sizing
        # Lighter minimum order size: 0.001 SOL (enforced)
        LIGHTER_MIN_ORDER_SIZE = 0.001

        risk_amount = price * (self.stop_loss_bps / 10000)
        if risk_amount > 0:
            size = min(
                self.max_position_size,
                max(self.min_position_size, abs(indicators.ao) * 0.1 / price)  # Rough sizing based on AO
            )
        else:
            size = self.min_position_size

        # Enforce Lighter's minimum order size
        if size < LIGHTER_MIN_ORDER_SIZE:
            LOG.warning(f"[renko_ao] calculated size {size:.4f} below Lighter minimum {LIGHTER_MIN_ORDER_SIZE}, using minimum")
            size = LIGHTER_MIN_ORDER_SIZE

        # Ensure size doesn't exceed max
        size = min(size, self.max_position_size)

        return Signal(
            side=side,
            strength=min(1.0, max(0.0, strength)),
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size=size,
            reason=reason,
        )

    def _check_exit(self, price: float, indicators: Indicators) -> Optional[str]:
        """Check for exit signals."""
        if not self._current_position:
            return None

        pos = self._current_position
        side = pos["side"]
        entry_price = pos["entry_price"]
        stop_loss = pos["stop_loss"]
        take_profit = pos["take_profit"]
        entry_time = pos["entry_time"]

        # Stop loss
        if side == "long" and price <= stop_loss:
            return "stop_loss"
        if side == "short" and price >= stop_loss:
            return "stop_loss"

        # Take profit
        if side == "long" and price >= take_profit:
            return "take_profit"
        if side == "short" and price <= take_profit:
            return "take_profit"

        # Time stop
        max_hold_seconds = self.max_hold_minutes * 60
        if time.time() - entry_time > max_hold_seconds:
            return "time_stop"

        # AO reversal (opposite trend)
        if side == "long" and indicators.ao_trend == "bearish" and indicators.ao < 0:
            return "ao_reversal"
        if side == "short" and indicators.ao_trend == "bullish" and indicators.ao > 0:
            return "ao_reversal"

        return None

    # ------------------------- Position Management -------------------------

    async def _enter_position(self, signal: Signal) -> None:
        """Enter a position based on signal."""
        if not self.trading_client and not self.dry_run:
            LOG.warning("[renko_ao] no trading client, cannot enter position")
            return

        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            # Cancel any existing entry orders before placing new one (one at a time)
            # This prevents multiple entry orders from accumulating
            await self._cancel_stale_orders()

            order_side = "bid" if signal.side == "long" else "ask"

            if signal.side == "long":
                order_price = signal.entry_price * 1.0001
            else:
                order_price = signal.entry_price * 0.9999

            # Final validation: ensure size meets minimum
            if signal.size < self.min_position_size:
                LOG.error(f"[renko_ao] order size {signal.size:.4f} below minimum {self.min_position_size}, skipping order")
                return

            LOG.info(
                "[renko_ao] entering %s position: price=%.2f size=%.4f reason=%s",
                signal.side,
                order_price,
                signal.size,
                signal.reason,
            )

            if self.dry_run:
                LOG.info("[renko_ao] DRY RUN: would place %s order", order_side)
                self._current_position = {
                    "side": signal.side,
                    "entry_price": signal.entry_price,
                    "size": signal.size,
                    "initial_size": signal.size,  # Store initial size for scaling
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "order_index": 0,
                }
                self._scaled_entries = []  # Reset scaled entries for new position
            else:
                # Place entry order with retry logic for API errors
                max_retries = 3
                retry_delay = 1.0
                order = None
                for attempt in range(max_retries):
                    try:
                        order = await self.trading_client.create_limit_order(
                            market=self.market,
                            side=order_side,
                            price=order_price,
                            size=signal.size,
                            post_only=False,
                        )
                        break  # Success
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "rate limit" in error_str.lower():
                            # Rate limit: exponential backoff
                            wait_time = retry_delay * (2 ** attempt)
                            LOG.warning(f"[renko_ao] rate limit on entry (attempt {attempt+1}/{max_retries}), waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                        elif "21104" in error_str or "invalid nonce" in error_str.lower():
                            # Invalid nonce: wait a bit and retry once
                            if attempt < max_retries - 1:
                                LOG.warning(f"[renko_ao] invalid nonce on entry (attempt {attempt+1}/{max_retries}), waiting {retry_delay:.1f}s")
                                await asyncio.sleep(retry_delay)
                            else:
                                raise  # Last attempt, re-raise
                        else:
                            raise  # Other errors, re-raise immediately
                
                if order is None:
                    LOG.error(f"[renko_ao] failed to create entry order after {max_retries} attempts, skipping entry")
                    return

                self._open_orders[order.client_order_index] = order
                self._order_timestamps[order.client_order_index] = time.time()  # Track order creation time
                self._current_position = {
                    "side": signal.side,
                    "entry_price": signal.entry_price,
                    "size": signal.size,
                    "initial_size": signal.size,  # Store initial size for scaling
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "order_index": order.client_order_index,
                }
                self._scaled_entries = []  # Reset scaled entries for new position

        except Exception as e:
            LOG.exception("[renko_ao] error entering position: %s", e)

    async def _exit_position(self, reason: str) -> None:
        """Exit current position."""
        if not self._current_position:
            return

        pos = self._current_position
        LOG.info(
            "[renko_ao] exiting position: side=%s entry=%.2f reason=%s",
            pos["side"],
            pos["entry_price"],
            reason,
        )

        if not self.trading_client and not self.dry_run:
            self._current_position = None
            return

        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            exit_side = "ask" if pos["side"] == "long" else "bid"
            current_price = self._get_current_price() or pos["entry_price"]

            # Calculate PnL (for both dry-run and live)
            # Use average entry price if we scaled in
            avg_entry_price = pos["entry_price"]  # This is already the average if we scaled
            if pos["side"] == "long":
                pnl_pct = (current_price - avg_entry_price) / avg_entry_price * 100
            else:
                pnl_pct = (avg_entry_price - current_price) / avg_entry_price * 100

            # Log scaling info if we scaled
            if self._scaled_entries:
                LOG.info(
                    f"[renko_ao] exiting scaled position: {len(self._scaled_entries)} scales, "
                    f"avg_entry={avg_entry_price:.2f}, total_size={pos['size']:.4f}"
                )

            if self.dry_run:
                LOG.info("[renko_ao] DRY RUN: would exit %s position", exit_side)
                LOG.info("[renko_ao] simulated PnL: %.2f%%", pnl_pct)
            else:
                # Place market order to exit with retry logic for API errors
                max_retries = 3
                retry_delay = 1.0
                order = None
                for attempt in range(max_retries):
                    try:
                        order = await self.trading_client.create_limit_order(
                            market=self.market,
                            side=exit_side,
                            price=current_price,
                            size=pos["size"],
                            post_only=False,
                        )
                        break  # Success
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "rate limit" in error_str.lower():
                            # Rate limit: exponential backoff
                            wait_time = retry_delay * (2 ** attempt)
                            LOG.warning(f"[renko_ao] rate limit on exit (attempt {attempt+1}/{max_retries}), waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                        elif "21104" in error_str or "invalid nonce" in error_str.lower():
                            # Invalid nonce: wait a bit and retry once
                            if attempt < max_retries - 1:
                                LOG.warning(f"[renko_ao] invalid nonce on exit (attempt {attempt+1}/{max_retries}), waiting {retry_delay:.1f}s")
                                await asyncio.sleep(retry_delay)
                            else:
                                raise  # Last attempt, re-raise
                        else:
                            raise  # Other errors, re-raise immediately

                if order is None:
                    raise RuntimeError(f"Failed to create exit order after {max_retries} attempts")

                # Cancel entry order
                if pos["order_index"] in self._open_orders:
                    try:
                        await self.trading_client.cancel_order(self.market, pos["order_index"])
                        LOG.info(f"[renko_ao] cancelled entry order {pos['order_index']}")
                    except Exception as e:
                        LOG.warning(f"[renko_ao] failed to cancel order {pos['order_index']}: {e}")
                    finally:
                        if pos["order_index"] in self._open_orders:
                            del self._open_orders[pos["order_index"]]
                        if pos["order_index"] in self._order_timestamps:
                            del self._order_timestamps[pos["order_index"]]

                # Cancel all scaled entry orders
                for scaled_entry in self._scaled_entries:
                    scale_order_index = scaled_entry.get("order_index")
                    if scale_order_index and scale_order_index in self._open_orders:
                        try:
                            await self.trading_client.cancel_order(self.market, scale_order_index)
                            LOG.info(f"[renko_ao] cancelled scaled entry order {scale_order_index}")
                        except Exception as e:
                            LOG.warning(f"[renko_ao] failed to cancel scaled order {scale_order_index}: {e}")
                        finally:
                            if scale_order_index in self._open_orders:
                                del self._open_orders[scale_order_index]
                            if scale_order_index in self._order_timestamps:
                                del self._order_timestamps[scale_order_index]

                # Cancel all other stale orders
                await self._cancel_stale_orders()

                # Log live PnL
                LOG.info("[renko_ao] LIVE PnL: %.2f%% (entry=%.2f, exit=%.2f, size=%.4f)",
                         pnl_pct, pos["entry_price"], current_price, pos["size"])

                # Track exit reason for adaptive cooldown
                self._recent_exit_reasons.append(reason)

                # Track recent performance for adaptive trading
                self._recent_pnl.append(pnl_pct)
                if pnl_pct < 0:
                    self._losing_streak += 1
                    # Pause trading after consecutive losses
                    if self._losing_streak >= self._max_losing_streak_before_pause:
                        self._pause_until = time.time() + self._pause_duration_seconds
                        LOG.warning(f"[renko_ao] ⚠️  Losing streak: {self._losing_streak} trades, pausing for {self._pause_duration_seconds}s")
                else:
                    self._losing_streak = 0  # Reset on win

                # Record in PnL tracker if available
                if hasattr(self, "pnl_tracker") and self.pnl_tracker:
                    await self.pnl_tracker.record_trade(
                        strategy="renko_ao",
                        side=pos["side"],
                        entry_price=pos["entry_price"],
                        exit_price=current_price,
                        size=pos["size"],
                        pnl_pct=pnl_pct,
                        entry_time=pos["entry_time"],
                        exit_time=time.time(),
                        exit_reason=reason,
                        market=self.market,
                    )

            self._current_position = None
            self._scaled_entries = []  # Clear scaled entries
            self._last_exit_time = time.time()  # Record exit time for cooldown

        except Exception as e:
            LOG.exception("[renko_ao] error exiting position: %s", e)

    def _get_current_price(self) -> Optional[float]:
        """Get current market price from state."""
        if not self.state:
            return None
        mid = self.state.get_mid(self.market)
        return float(mid) if mid is not None else None

    async def _check_scale_in(self, price: float, indicators: Indicators) -> None:
        """Check if we should scale into an existing position (average in)."""
        if not self._current_position or not self._enable_scaling:
            return

        pos = self._current_position
        side = pos["side"]
        entry_price = pos["entry_price"]
        entry_time = pos["entry_time"]

        # Check if divergence still exists and is strengthening
        if indicators.divergence_type is None:
            return

        # Check if we've hit max scales
        if len(self._scaled_entries) >= self._max_scales:
            return

        # Check time since last scale (or entry)
        last_scale_time = self._scaled_entries[-1]["time"] if self._scaled_entries else entry_time
        time_since_last = time.time() - last_scale_time
        if time_since_last < self._scale_interval_seconds:
            return

        # Check if price has moved against us enough to warrant scaling
        if side == "long":
            price_move_bps = (entry_price - price) / entry_price * 10000  # Price moved down
            should_scale = price_move_bps >= self._scale_price_threshold_bps and indicators.divergence_type == "bullish"
        else:  # short
            price_move_bps = (price - entry_price) / entry_price * 10000  # Price moved up
            should_scale = price_move_bps >= self._scale_price_threshold_bps and indicators.divergence_type == "bearish"

        if not should_scale:
            return

        # Calculate scale size
        initial_size = pos.get("initial_size", pos["size"])
        scale_size = initial_size * self._scale_size_multiplier
        # For scaling, we allow sizes below min_position_size (but still enforce Lighter's absolute minimum of 0.001 SOL)
        LIGHTER_MIN_ORDER_SIZE = 0.001  # Lighter's absolute minimum
        scale_size = max(LIGHTER_MIN_ORDER_SIZE, min(scale_size, self.max_position_size))

        # Calculate new average entry price
        total_size = pos["size"] + scale_size
        if side == "long":
            new_avg_entry = (entry_price * pos["size"] + price * scale_size) / total_size
        else:
            new_avg_entry = (entry_price * pos["size"] + price * scale_size) / total_size

        LOG.info(
            f"[renko_ao] scaling into {side} position: scale_size={scale_size:.4f}, "
            f"price={price:.2f} (moved {price_move_bps:.1f} bps), "
            f"avg_entry={new_avg_entry:.2f} (was {entry_price:.2f}), "
            f"total_size={total_size:.4f}, scales={len(self._scaled_entries)+1}/{self._max_scales}"
        )

        # Place scale order
        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            order_side = "bid" if side == "long" else "ask"
            order_price = price * 1.0001 if side == "long" else price * 0.9999

            order = await self.trading_client.create_limit_order(
                market=self.market,
                side=order_side,
                price=order_price,
                size=scale_size,
                post_only=False,
            )

            self._open_orders[order.client_order_index] = order
            self._order_timestamps[order.client_order_index] = time.time()

            # Track scaled entry
            self._scaled_entries.append({
                "price": price,
                "size": scale_size,
                "time": time.time(),
                "order_index": order.client_order_index
            })

            # Update position with new average entry and total size
            pos["entry_price"] = new_avg_entry
            pos["size"] = total_size
            pos["initial_size"] = initial_size  # Store original size

            # Adjust stop loss based on average entry with progressive widening
            # Progressive widening: 2.0x for 1 scale, 2.5x for 2 scales, 3.0x for 3 scales
            # This gives more room as position grows and accounts for larger position size
            num_scales = len(self._scaled_entries) + 1  # +1 because we just added a scale
            stop_multiplier = 1.5 + (num_scales * 0.5)  # 2.0x for 1 scale, 2.5x for 2, 3.0x for 3

            # Use average entry price (better reflects actual position cost basis)
            if side == "long":
                pos["stop_loss"] = new_avg_entry * (1 - self.stop_loss_bps * stop_multiplier / 10000)
            else:
                pos["stop_loss"] = new_avg_entry * (1 + self.stop_loss_bps * stop_multiplier / 10000)

            LOG.info(
                f"[renko_ao] position updated: avg_entry={new_avg_entry:.2f}, "
                f"total_size={total_size:.4f}, stop_loss={pos['stop_loss']:.2f}"
            )

        except Exception as e:
            LOG.exception(f"[renko_ao] error scaling into position: {e}")

    async def _cancel_stale_orders(self) -> None:
        """Cancel orders that haven't filled after timeout."""
        if not self.trading_client or self.dry_run:
            return

        current_time = time.time()
        stale_orders = []

        for order_index, order in list(self._open_orders.items()):
            order_time = self._order_timestamps.get(order_index, current_time)
            age = current_time - order_time

            if age > self._order_timeout_seconds:
                stale_orders.append(order_index)

        for order_index in stale_orders:
            try:
                LOG.warning(f"[renko_ao] cancelling stale order {order_index} (age: {current_time - self._order_timestamps.get(order_index, current_time):.1f}s > {self._order_timeout_seconds}s)")
                await self.trading_client.cancel_order(self.market, order_index)
                if order_index in self._open_orders:
                    del self._open_orders[order_index]
                if order_index in self._order_timestamps:
                    del self._order_timestamps[order_index]
            except Exception as e:
                LOG.warning(f"[renko_ao] failed to cancel stale order {order_index}: {e}")
                # Remove from tracking even if cancel failed (order might already be filled/cancelled)
                if order_index in self._open_orders:
                    del self._open_orders[order_index]
                if order_index in self._order_timestamps:
                    del self._order_timestamps[order_index]

    def _update_adaptive_cooldown(self, indicators: Optional[Indicators], price: Optional[float]) -> None:
        """Update exit cooldown based on volatility and recent performance."""
        if indicators is None or price is None:
            self._exit_cooldown_seconds = self._base_exit_cooldown_seconds
            return

        # Calculate volatility in bps from ATR
        vol_bps = 0.0
        if self._current_renko_brick_size and price > 0:
            # ATR as percentage of price, converted to basis points
            vol_bps = (self._current_renko_brick_size / price) * 10000

        # Start with base cooldown
        cooldown = self._base_exit_cooldown_seconds

        # Increase cooldown in high volatility (choppy markets)
        # Use similar thresholds as RSI+BB (8 bps high, 2 bps low)
        if vol_bps > 8.0:
            cooldown *= 1.5  # 50% longer in high vol
            LOG.debug(f"[renko_ao] high volatility ({vol_bps:.1f} bps), extending cooldown to {cooldown:.1f}s")
        elif vol_bps < 2.0:
            cooldown *= 0.8  # 20% shorter in low vol (smoother markets)
            LOG.debug(f"[renko_ao] low volatility ({vol_bps:.1f} bps), reducing cooldown to {cooldown:.1f}s")

        # Increase cooldown if recent exits were stop losses (prevent re-entry into losing trades)
        stop_loss_count = sum(1 for r in self._recent_exit_reasons if r == "stop_loss")
        if stop_loss_count >= 2:
            cooldown *= 1.3  # 30% longer after multiple stop losses
            LOG.debug(f"[renko_ao] {stop_loss_count} recent stop losses, extending cooldown to {cooldown:.1f}s")

        # Increase cooldown during losing streak
        if self._losing_streak >= 2:
            cooldown *= 1.2  # 20% longer during losing streak
            LOG.debug(f"[renko_ao] losing streak {self._losing_streak}, extending cooldown to {cooldown:.1f}s")

        # Cap cooldown at reasonable maximum (60 seconds)
        self._exit_cooldown_seconds = min(cooldown, 60.0)

    def _update_telemetry(self, indicators: Optional[Indicators], price: Optional[float]) -> None:
        """Update telemetry metrics."""
        if not self.telemetry or indicators is None:
            return

        try:
            self.telemetry.set_gauge("renko_ao_ao", indicators.ao)
            self.telemetry.set_gauge("renko_ao_bb_upper", indicators.bb_upper)
            self.telemetry.set_gauge("renko_ao_bb_lower", indicators.bb_lower)
            self.telemetry.set_gauge("renko_ao_divergence_strength", indicators.divergence_strength)
        except Exception:
            pass

