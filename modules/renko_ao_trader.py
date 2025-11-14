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
        self.min_divergence_strength = float(trader_cfg.get("min_divergence_strength", 0.3))  # Minimum divergence strength

        # Risk management
        self.take_profit_bps = float(trader_cfg.get("take_profit_bps", 10.0))
        self.stop_loss_bps = float(trader_cfg.get("stop_loss_bps", 5.0))
        self.max_hold_minutes = int(trader_cfg.get("max_hold_minutes", 5))
        self.risk_per_trade_pct = float(trader_cfg.get("risk_per_trade_pct", 1.0))
        self.max_position_size = float(trader_cfg.get("max_position_size", 0.1))
        self.min_position_size = float(trader_cfg.get("min_position_size", 0.01))

        # State
        self._renko_bricks: Deque[RenkoBrick] = deque(maxlen=200)
        self._current_brick: Optional[RenkoBrick] = None
        self._price_history: Deque[float] = deque(maxlen=1000)  # For AO calculation
        self._price_highs: Deque[float] = deque(maxlen=1000)  # For ATR calculation
        self._price_lows: Deque[float] = deque(maxlen=1000)  # For ATR calculation
        self._current_position: Optional[Dict[str, Any]] = None
        self._open_orders: Dict[int, PlacedOrder] = {}
        self._stop = asyncio.Event()

        LOG.info(
            "[renko_ao] initialized: market=%s dry_run=%s renko_atr_period=%d renko_atr_multiplier=%.2f",
            self.market,
            self.dry_run,
            self.renko_atr_period,
            self.renko_atr_multiplier,
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
                # Track price with timestamp for ATR
                self._price_history.append(current_price)
                # For ATR, we'll use price changes (since we only have mid prices)
                # Track high/low as the price itself (will be updated if we get better data)
                if len(self._price_highs) == 0 or current_price > self._price_highs[-1]:
                    self._price_highs.append(current_price)
                else:
                    self._price_highs.append(self._price_highs[-1] if self._price_highs else current_price)
                
                if len(self._price_lows) == 0 or current_price < self._price_lows[-1]:
                    self._price_lows.append(current_price)
                else:
                    self._price_lows.append(self._price_lows[-1] if self._price_lows else current_price)

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
                if len(self._renko_bricks) < max(self.bb_period, self.ao_slow_period, self.renko_lookback):
                    await asyncio.sleep(1.0)
                    continue

                # Compute indicators
                indicators = self._compute_indicators(current_price)
                if indicators is None:
                    await asyncio.sleep(1.0)
                    continue

                # Check for exit first
                if self._current_position:
                    exit_reason = self._check_exit(current_price, indicators)
                    if exit_reason:
                        await self._exit_position(exit_reason)
                else:
                    # Check for entry
                    signal = self._check_entry(current_price, indicators)
                    if signal:
                        await self._enter_position(signal)

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

            LOG.debug(f"[renko_ao] new brick: {direction} @ {new_close:.2f}, brick_size={self._current_renko_brick_size:.4f}, total bricks: {len(self._renko_bricks)}")
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
        risk_amount = price * (self.stop_loss_bps / 10000)
        if risk_amount > 0:
            size = min(
                self.max_position_size,
                max(self.min_position_size, abs(indicators.ao) * 0.1 / price)  # Rough sizing based on AO
            )
        else:
            size = self.min_position_size

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

            order_side = "bid" if signal.side == "long" else "ask"

            if signal.side == "long":
                order_price = signal.entry_price * 1.0001
            else:
                order_price = signal.entry_price * 0.9999

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
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "order_index": 0,
                }
            else:
                order = await self.trading_client.create_limit_order(
                    market=self.market,
                    side=order_side,
                    price=order_price,
                    size=signal.size,
                    post_only=False,
                )

                self._open_orders[order.client_order_index] = order
                self._current_position = {
                    "side": signal.side,
                    "entry_price": signal.entry_price,
                    "size": signal.size,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "order_index": order.client_order_index,
                }

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

            if self.dry_run:
                LOG.info("[renko_ao] DRY RUN: would exit %s position", exit_side)
                if pos["side"] == "long":
                    pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
                else:
                    pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100
                LOG.info("[renko_ao] simulated PnL: %.2f%%", pnl_pct)
            else:
                order = await self.trading_client.create_limit_order(
                    market=self.market,
                    side=exit_side,
                    price=current_price,
                    size=pos["size"],
                    post_only=False,
                )

                if pos["order_index"] in self._open_orders:
                    try:
                        await self.trading_client.cancel_order(self.market, pos["order_index"])
                    except Exception:
                        pass
                    del self._open_orders[pos["order_index"]]

            self._current_position = None

        except Exception as e:
            LOG.exception("[renko_ao] error exiting position: %s", e)

    def _get_current_price(self) -> Optional[float]:
        """Get current market price from state."""
        if not self.state:
            return None
        mid = self.state.get_mid(self.market)
        return float(mid) if mid is not None else None

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

