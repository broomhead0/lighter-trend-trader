# modules/mean_reversion_trader.py
"""
RSI + BB Strategy (Trend Following) for SOL.

Strategy:
- Trades WITH the trend using RSI momentum and Bollinger Bands
- Long entries: RSI > 50 (bullish momentum) + price near/above BB middle
- Short entries: RSI < 50 (bearish momentum) + price near/below BB middle
- Uses BB as support/resistance for trend continuation
- Filters trades by volatility (moderate vol only)
- Position sizing based on ATR (volatility-adjusted)

This strategy works best in trending markets and follows momentum.
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

LOG = logging.getLogger("mean_reversion")


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
    ema_fast: float  # 8-period EMA
    ema_slow: float  # 21-period EMA
    bb_upper: float  # Bollinger Band upper
    bb_middle: float  # Bollinger Band middle (SMA)
    bb_lower: float  # Bollinger Band lower
    rsi: float  # 14-period RSI
    atr: float  # 14-period ATR
    volume_ma: float  # 20-period volume moving average
    volatility_bps: float  # Current volatility in basis points


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


class MeanReversionTrader:
    """
    Trend following trader using RSI momentum and Bollinger Bands.

    Entry conditions:
    - Long: RSI > 50 (bullish momentum) + price near/above BB middle
    - Short: RSI < 50 (bearish momentum) + price near/below BB middle
    - Volume is above average (confirmation)
    - Volatility is moderate (not too high, not too low)
    - Trend confirmation (EMA fast > EMA slow for longs, vice versa for shorts)

    Exit conditions:
    - Take profit: price reaches target bps
    - Stop loss: price reverses beyond threshold
    - Time stop: exit after max hold time if no movement
    - Trend reversal: RSI crosses opposite direction
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

        trader_cfg = (self.cfg.get("mean_reversion") or {}) if isinstance(self.cfg.get("mean_reversion"), dict) else {}

        # Market
        self.market = trader_cfg.get("market", "market:2")  # SOL
        self.dry_run = bool(trader_cfg.get("dry_run", True))
        self.candle_interval_seconds = int(trader_cfg.get("candle_interval_seconds", 15))  # Default 15s for fastest iteration

        # Indicators parameters
        self.ema_fast_period = int(trader_cfg.get("ema_fast_period", 8))
        self.ema_slow_period = int(trader_cfg.get("ema_slow_period", 21))
        self.bb_period = int(trader_cfg.get("bb_period", 20))
        self.bb_std = float(trader_cfg.get("bb_std", 2.0))
        self.rsi_period = int(trader_cfg.get("rsi_period", 14))
        self.atr_period = int(trader_cfg.get("atr_period", 14))
        self.volume_ma_period = int(trader_cfg.get("volume_ma_period", 20))

        # Entry filters (trend following)
        self.rsi_bullish_threshold = float(trader_cfg.get("rsi_bullish_threshold", 50.0))  # RSI > 50 for longs
        self.rsi_bearish_threshold = float(trader_cfg.get("rsi_bearish_threshold", 50.0))  # RSI < 50 for shorts
        self.rsi_momentum_strength = float(trader_cfg.get("rsi_momentum_strength", 10.0))  # RSI must be at least this far from 50
        self.bb_position_threshold = float(trader_cfg.get("bb_position_threshold", 0.3))  # Price within 30% of BB middle
        self.volume_multiplier = float(trader_cfg.get("volume_multiplier", 1.2))  # Volume must be 1.2x average
        self.vol_min_bps = float(trader_cfg.get("vol_min_bps", 2.0))  # Minimum volatility to trade
        self.vol_max_bps = float(trader_cfg.get("vol_max_bps", 25.0))  # Maximum volatility to trade
        self.trend_confirmation_bps = float(trader_cfg.get("trend_confirmation_bps", 2.0))  # Min EMA divergence for trend confirmation

        # Risk management
        self.take_profit_bps = float(trader_cfg.get("take_profit_bps", 3.0))
        self.stop_loss_bps = float(trader_cfg.get("stop_loss_bps", 6.0))
        self.max_hold_minutes = int(trader_cfg.get("max_hold_minutes", 5))
        self.risk_per_trade_pct = float(trader_cfg.get("risk_per_trade_pct", 1.0))  # 1% of capital per trade
        # Position sizes - Lighter minimum is 0.001 SOL, but there may be a minimum notional requirement
        # At ~141 SOL price, 0.05 SOL = ~$7 notional (still rejected with code=21706)
        # Using 0.1 SOL (~$14 notional) to ensure we meet minimum quote amount requirements
        # Defaults are set in code (single source of truth) but can be overridden by config/env
        self.max_position_size = float(trader_cfg.get("max_position_size", 0.1))  # Max SOL per trade (default: 0.1 for $100 account)
        self.min_position_size = float(trader_cfg.get("min_position_size", 0.1))  # Min SOL per trade (default: 0.1 to meet minimum notional)

        # Position tracking
        self._candles: Deque[Candle] = deque(maxlen=200)  # Keep last 200 candles (more for smaller timeframes)
        self._current_position: Optional[Dict[str, Any]] = None
        self._open_orders: Dict[int, PlacedOrder] = {}  # client_order_index -> order
        self._stop = asyncio.Event()

        # Candle fetching
        self._last_candle_fetch = 0.0
        self._candle_fetch_interval = 60.0  # Fetch every minute

        # API config
        api_cfg = self.cfg.get("api") or {}
        self.api_base_url = api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai")

        LOG.info(
            "[mean_reversion] initialized: market=%s dry_run=%s candle_interval=%ds min_size=%.6f max_size=%.6f",
            self.market,
            self.dry_run,
            self.candle_interval_seconds,
            self.min_position_size,
            self.max_position_size,
        )

    async def run(self):
        """Main trading loop."""
        LOG.info(f"[mean_reversion] starting trading loop (candle interval: {self.candle_interval_seconds}s)")

        # Initial candle fetch
        await self._fetch_candles()

        while not self._stop.is_set():
            try:
                # Update candles periodically
                now = time.time()
                if now - self._last_candle_fetch >= self._candle_fetch_interval:
                    await self._fetch_candles()
                    self._last_candle_fetch = now

                # Build candles from WebSocket price updates (fallback if REST API fails)
                await self._build_candles_from_price()

                # Get latest price
                current_price = self._get_current_price()
                if current_price is None:
                    await asyncio.sleep(5.0)
                    continue

                # Update indicators
                indicators = self._compute_indicators()
                if indicators is not None:
                    LOG.info(f"[mean_reversion] indicators computed: RSI={indicators.rsi:.1f}, BB_lower={indicators.bb_lower:.2f}, BB_upper={indicators.bb_upper:.2f}, price={current_price:.2f}, vol_bps={indicators.volatility_bps:.1f}")
                if indicators is None:
                    needed = max(self.bb_period, self.rsi_period, self.atr_period, self.ema_slow_period)
                    if len(self._candles) < needed:
                        LOG.info(f"[mean_reversion] collecting candles: {len(self._candles)}/{needed}")
                    await asyncio.sleep(5.0)
                    continue

                # Check for exit signals if in position
                if self._current_position:
                    exit_signal = self._check_exit(current_price, indicators)
                    if exit_signal:
                        await self._exit_position(exit_signal)

                # Check for entry signals if no position
                if not self._current_position:
                    signal = self._check_entry(current_price, indicators)
                    if signal:
                        await self._enter_position(signal)

                # Update telemetry
                self._update_telemetry(indicators, current_price)

                await asyncio.sleep(5.0)  # Check every 5 seconds

            except Exception as e:
                LOG.exception("[mean_reversion] error in trading loop: %s", e)
                await asyncio.sleep(10.0)

    async def stop(self):
        """Stop the trader."""
        self._stop.set()
        # Close any open positions
        if self._current_position:
            await self._exit_position("stop")

    # ------------------------- Candle Management -------------------------

    async def _fetch_candles(self) -> None:
        """Fetch recent 1-minute candles from REST API."""
        try:
            import aiohttp

            market_id = self._parse_market_id(self.market)
            if market_id is None:
                LOG.warning("[mean_reversion] invalid market: %s", self.market)
                return

            # Try different endpoint formats
            urls_to_try = [
                f"{self.api_base_url.rstrip('/')}/public/markets/{market_id}/candles",
                f"{self.api_base_url.rstrip('/')}/markets/{market_id}/candles",
            ]

            # Map seconds to interval string
            interval_map = {
                10: "10s",
                15: "15s",
                30: "30s",
                60: "1m",
                300: "5m",
            }
            interval_str = interval_map.get(self.candle_interval_seconds, "15s")

            params = {
                "interval": interval_str,
                "limit": 100,  # Get last 100 candles
            }

            url = urls_to_try[0]  # Default to first

            async with aiohttp.ClientSession() as session:
                # Try each URL until one works
                data = None
                for url in urls_to_try:
                    try:
                        async with session.get(url, params=params, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                break
                            elif url == urls_to_try[-1]:
                                # Last URL failed
                                LOG.warning("[mean_reversion] failed to fetch candles: %s", resp.status)
                                return
                    except Exception as e:
                        if url == urls_to_try[-1]:
                            LOG.warning("[mean_reversion] error fetching candles: %s", e)
                            return
                        continue

                if data is None:
                    return  # All URLs failed

                candles_data = data.get("candles") if isinstance(data, dict) else data

                if not isinstance(candles_data, list):
                    return

                # Parse and update candles
                new_candles = []
                for c in candles_data:
                    try:
                        candle = Candle(
                            open_time=int(c.get("open_time", 0)),
                            open=float(c.get("open", 0)),
                            high=float(c.get("high", 0)),
                            low=float(c.get("low", 0)),
                            close=float(c.get("close", 0)),
                            volume=float(c.get("volume", 0)),
                        )
                        if candle.open_time > 0:
                            new_candles.append(candle)
                    except (ValueError, TypeError):
                        continue

                if new_candles:
                    # Sort by time and update
                    new_candles.sort(key=lambda x: x.open_time)
                    self._candles.clear()
                    self._candles.extend(new_candles)
                    LOG.debug("[mean_reversion] fetched %d candles", len(new_candles))

        except Exception as e:
            LOG.warning("[mean_reversion] error fetching candles: %s", e)

    def _get_current_price(self) -> Optional[float]:
        """Get current mid price from state."""
        if self.state and hasattr(self.state, "get_mid"):
            return self.state.get_mid(self.market)
        return None

    async def _build_candles_from_price(self):
        """Build candles from WebSocket price updates."""
        price = self._get_current_price()
        if price is None:
            return

        now = time.time()
        # Round to candle interval (e.g., 30s, 60s)
        current_candle_time = int(now // self.candle_interval_seconds) * self.candle_interval_seconds

        # Get or create current candle
        if not self._candles or self._candles[-1].open_time < current_candle_time:
            # New candle period - create new candle
            new_candle = Candle(
                open_time=current_candle_time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0.0,  # Volume not available from WS
            )
            self._candles.append(new_candle)
            # Keep only last 200 candles (more for smaller timeframes)
            if len(self._candles) > 200:
                self._candles = self._candles[-200:]
            LOG.info(f"[mean_reversion] created new candle at {current_candle_time} ({self.candle_interval_seconds}s), price={price:.2f}, total candles: {len(self._candles)}")
        else:
            # Update current candle
            current_candle = self._candles[-1]
            current_candle.high = max(current_candle.high, price)
            current_candle.low = min(current_candle.low, price)
            current_candle.close = price

    # ------------------------- Indicator Computation -------------------------

    def _compute_indicators(self) -> Optional[Indicators]:
        """Compute all technical indicators from candles."""
        if len(self._candles) < max(self.bb_period, self.rsi_period, self.atr_period, self.ema_slow_period):
            return None

        candles_list = list(self._candles)

        # EMA
        ema_fast = self._compute_ema(candles_list, self.ema_fast_period)
        ema_slow = self._compute_ema(candles_list, self.ema_slow_period)

        # Bollinger Bands
        bb_middle, bb_upper, bb_lower = self._compute_bollinger_bands(candles_list, self.bb_period, self.bb_std)

        # RSI
        rsi = self._compute_rsi(candles_list, self.rsi_period)

        # ATR
        atr = self._compute_atr(candles_list, self.atr_period)

        # Volume MA
        volume_ma = self._compute_volume_ma(candles_list, self.volume_ma_period)

        # Volatility (from recent price changes)
        volatility_bps = self._compute_volatility_bps(candles_list)

        return Indicators(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            rsi=rsi,
            atr=atr,
            volume_ma=volume_ma,
            volatility_bps=volatility_bps,
        )

    def _compute_ema(self, candles: List[Candle], period: int) -> float:
        """Compute Exponential Moving Average."""
        if len(candles) < period:
            return candles[-1].close if candles else 0.0

        closes = [c.close for c in candles[-period:]]
        multiplier = 2.0 / (period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema

    def _compute_bollinger_bands(self, candles: List[Candle], period: int, std_dev: float) -> Tuple[float, float, float]:
        """Compute Bollinger Bands."""
        if len(candles) < period:
            price = candles[-1].close if candles else 0.0
            return price, price, price

        closes = [c.close for c in candles[-period:]]
        sma = sum(closes) / len(closes)
        variance = sum((x - sma) ** 2 for x in closes) / len(closes)
        std = math.sqrt(variance)

        middle = sma
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return middle, upper, lower

    def _compute_rsi(self, candles: List[Candle], period: int) -> float:
        """Compute Relative Strength Index."""
        if len(candles) < period + 1:
            return 50.0  # Neutral

        closes = [c.close for c in candles[-(period + 1):]]
        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        avg_gain = sum(gains) / len(gains) if gains else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0001  # Avoid division by zero

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _compute_atr(self, candles: List[Candle], period: int) -> float:
        """Compute Average True Range."""
        if len(candles) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(len(candles) - period, len(candles)):
            if i == 0:
                continue
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

    def _compute_volume_ma(self, candles: List[Candle], period: int) -> float:
        """Compute volume moving average."""
        if len(candles) < period:
            return candles[-1].volume if candles else 0.0

        volumes = [c.volume for c in candles[-period:]]
        return sum(volumes) / len(volumes)

    def _compute_volatility_bps(self, candles: List[Candle], lookback: int = 20) -> float:
        """Compute volatility in basis points from recent price changes."""
        if len(candles) < 2:
            return 0.0

        recent = candles[-min(lookback, len(candles)):]
        if len(recent) < 2:
            return 0.0

        returns = []
        for i in range(1, len(recent)):
            if recent[i - 1].close > 0:
                ret = abs((recent[i].close - recent[i - 1].close) / recent[i - 1].close)
                returns.append(ret)

        if not returns:
            return 0.0

        avg_return = sum(returns) / len(returns)
        volatility_bps = avg_return * 10000  # Convert to basis points
        return volatility_bps

    # ------------------------- Signal Generation -------------------------

    def _check_entry(self, price: float, indicators: Indicators) -> Optional[Signal]:
        """Check for entry signals (trend following)."""
        # Volatility filter
        if indicators.volatility_bps < self.vol_min_bps or indicators.volatility_bps > self.vol_max_bps:
            LOG.debug(f"[mean_reversion] volatility filter: {indicators.volatility_bps:.1f} bps (need {self.vol_min_bps}-{self.vol_max_bps})")
            return None

        # Volume filter (skip if volume is 0 - we don't have volume from WS)
        latest_candle = self._candles[-1] if self._candles else None
        if latest_candle and latest_candle.volume > 0 and latest_candle.volume < indicators.volume_ma * self.volume_multiplier:
            LOG.debug(f"[mean_reversion] volume filter: {latest_candle.volume:.0f} < {indicators.volume_ma * self.volume_multiplier:.0f}")
            return None

        # Calculate price position relative to BB middle (0.0 = at lower BB, 1.0 = at upper BB, 0.5 = at middle)
        if indicators.bb_upper > indicators.bb_lower:
            bb_position = (price - indicators.bb_lower) / (indicators.bb_upper - indicators.bb_lower)
        else:
            bb_position = 0.5

        # Long signal: RSI > 50 (bullish momentum) + price near/above BB middle + EMA trend confirmation
        rsi_bullish = indicators.rsi > (self.rsi_bullish_threshold + self.rsi_momentum_strength)
        price_above_middle = bb_position >= (0.5 - self.bb_position_threshold)  # Within threshold of middle or above
        ema_bullish = indicators.ema_fast > indicators.ema_slow
        ema_trend_strength = abs(indicators.ema_fast - indicators.ema_slow) / indicators.ema_slow * 10000
        trend_confirmed = ema_trend_strength >= self.trend_confirmation_bps

        if rsi_bullish and price_above_middle and ema_bullish and trend_confirmed:
            strength = min(1.0, (indicators.rsi - self.rsi_bullish_threshold) / 50.0)  # Strength based on RSI above 50
            LOG.info(f"[mean_reversion] LONG signal (trend following): RSI={indicators.rsi:.1f} (need >{self.rsi_bullish_threshold + self.rsi_momentum_strength:.1f}), BB_pos={bb_position:.2f}, EMA_fast={indicators.ema_fast:.2f} > EMA_slow={indicators.ema_slow:.2f}, price={price:.2f}")
            return self._create_signal("long", price, indicators, strength, "RSI bullish + BB middle + EMA trend")

        # Short signal: RSI < 50 (bearish momentum) + price near/below BB middle + EMA trend confirmation
        rsi_bearish = indicators.rsi < (self.rsi_bearish_threshold - self.rsi_momentum_strength)
        price_below_middle = bb_position <= (0.5 + self.bb_position_threshold)  # Within threshold of middle or below
        ema_bearish = indicators.ema_fast < indicators.ema_slow
        trend_confirmed = ema_trend_strength >= self.trend_confirmation_bps

        if rsi_bearish and price_below_middle and ema_bearish and trend_confirmed:
            strength = min(1.0, (self.rsi_bearish_threshold - indicators.rsi) / 50.0)  # Strength based on RSI below 50
            LOG.info(f"[mean_reversion] SHORT signal (trend following): RSI={indicators.rsi:.1f} (need <{self.rsi_bearish_threshold - self.rsi_momentum_strength:.1f}), BB_pos={bb_position:.2f}, EMA_fast={indicators.ema_fast:.2f} < EMA_slow={indicators.ema_slow:.2f}, price={price:.2f}")
            return self._create_signal("short", price, indicators, strength, "RSI bearish + BB middle + EMA trend")

        return None

    def _create_signal(self, side: str, price: float, indicators: Indicators, strength: float, reason: str) -> Signal:
        """Create a trading signal with risk management."""
        # Calculate stop loss and take profit
        if side == "long":
            stop_loss = price * (1 - self.stop_loss_bps / 10000)
            take_profit = price * (1 + self.take_profit_bps / 10000)
        else:  # short
            stop_loss = price * (1 + self.stop_loss_bps / 10000)
            take_profit = price * (1 - self.take_profit_bps / 10000)

        # Position sizing based on ATR and risk
        # Lighter minimum order size: 0.001 SOL (enforced)
        LIGHTER_MIN_ORDER_SIZE = 0.001

        risk_amount = price * (self.stop_loss_bps / 10000)  # Risk per unit
        if risk_amount > 0:
            # Size based on risk per trade percentage (would need capital tracking)
            # For now, use ATR-based sizing
            atr_based_size = indicators.atr * 0.5 / price
            size = min(
                self.max_position_size,
                max(self.min_position_size, atr_based_size)  # Rough sizing
            )
            LOG.debug(f"[mean_reversion] position sizing: ATR={indicators.atr:.4f}, ATR-based={atr_based_size:.6f}, min={self.min_position_size:.6f}, max={self.max_position_size:.6f}, final={size:.6f}")
        else:
            size = self.min_position_size
            LOG.debug(f"[mean_reversion] position sizing: using minimum={size:.6f}")

        # Ensure size doesn't exceed max
        if size > self.max_position_size:
            LOG.warning(f"[mean_reversion] calculated size {size:.6f} above maximum {self.max_position_size}, capping to max")
            size = self.max_position_size

        LOG.debug(f"[mean_reversion] final position size: {size:.6f} SOL (min={self.min_position_size:.6f}, max={self.max_position_size:.6f})")

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

        # Time stop (scale by candle interval for smaller timeframes)
        max_hold_seconds = self.max_hold_minutes * 60
        # For smaller timeframes, scale down hold time proportionally
        if self.candle_interval_seconds < 60:
            max_hold_seconds = max_hold_seconds * (self.candle_interval_seconds / 60)
        if time.time() - entry_time > max_hold_seconds:
            return "time_stop"

        # Trend reversal signal (RSI crosses opposite direction)
        if side == "long" and indicators.rsi < self.rsi_bearish_threshold:
            return "trend_reversal"
        if side == "short" and indicators.rsi > self.rsi_bullish_threshold:
            return "trend_reversal"

        return None

    # ------------------------- Position Management -------------------------

    async def _enter_position(self, signal: Signal) -> None:
        """Enter a position based on signal."""
        # In dry-run mode, we can simulate without trading client
        if not self.trading_client and not self.dry_run:
            LOG.warning("[mean_reversion] no trading client, cannot enter position")
            return

        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            # Determine order side
            order_side = "bid" if signal.side == "long" else "ask"

            # Place limit order at current price (market order equivalent)
            # For mean reversion, we want quick fills, so use aggressive pricing
            if signal.side == "long":
                order_price = signal.entry_price * 1.0001  # Slightly above to get filled
            else:
                order_price = signal.entry_price * 0.9999  # Slightly below to get filled

            # Final validation: ensure size meets minimum
            if signal.size < self.min_position_size:
                LOG.error(f"[mean_reversion] order size {signal.size:.4f} below minimum {self.min_position_size}, skipping order")
                return

            LOG.info(
                "[mean_reversion] entering %s position: price=%.2f size=%.6f reason=%s (min=%.6f max=%.6f)",
                signal.side,
                order_price,
                signal.size,
                signal.reason,
                self.min_position_size,
                self.max_position_size,
            )

            if self.dry_run:
                LOG.info("[mean_reversion] DRY RUN: would place %s order", order_side)
                # Simulate position
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
                    post_only=False,  # Allow immediate execution
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

                if self.telemetry:
                    self.telemetry.set_gauge("mean_reversion_position_side", 1.0 if signal.side == "long" else -1.0)
                    self.telemetry.set_gauge("mean_reversion_position_size", float(signal.size))

        except Exception as e:
            LOG.exception("[mean_reversion] error entering position: %s", e)

    async def _exit_position(self, reason: str) -> None:
        """Exit current position."""
        if not self._current_position:
            return

        pos = self._current_position
        LOG.info(
            "[mean_reversion] exiting position: side=%s entry=%.2f reason=%s",
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

            # Determine exit side (opposite of entry)
            exit_side = "ask" if pos["side"] == "long" else "bid"
            current_price = self._get_current_price() or pos["entry_price"]

            # Calculate PnL (for both dry-run and live)
            if pos["side"] == "long":
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            else:
                pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100

            if self.dry_run:
                LOG.info("[mean_reversion] DRY RUN: would exit %s position", exit_side)
                LOG.info("[mean_reversion] simulated PnL: %.2f%%", pnl_pct)
            else:
                # Place market order to exit
                order = await self.trading_client.create_limit_order(
                    market=self.market,
                    side=exit_side,
                    price=current_price,
                    size=pos["size"],
                    post_only=False,
                )

                # Cancel any open entry orders
                if pos["order_index"] in self._open_orders:
                    try:
                        await self.trading_client.cancel_order(self.market, pos["order_index"])
                    except Exception:
                        pass
                    del self._open_orders[pos["order_index"]]

                # Log live PnL
                LOG.info("[mean_reversion] LIVE PnL: %.2f%% (entry=%.2f, exit=%.2f, size=%.4f)",
                         pnl_pct, pos["entry_price"], current_price, pos["size"])

                # Record in PnL tracker if available
                if hasattr(self, "pnl_tracker") and self.pnl_tracker:
                    await self.pnl_tracker.record_trade(
                        strategy="mean_reversion",
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

            if self.telemetry:
                self.telemetry.set_gauge("mean_reversion_position_side", 0.0)
                self.telemetry.set_gauge("mean_reversion_position_size", 0.0)

        except Exception as e:
            LOG.exception("[mean_reversion] error exiting position: %s", e)

    def _update_telemetry(self, indicators: Optional[Indicators], price: Optional[float]) -> None:
        """Update telemetry metrics."""
        if not self.telemetry or indicators is None:
            return

        try:
            self.telemetry.set_gauge("mean_reversion_rsi", indicators.rsi)
            self.telemetry.set_gauge("mean_reversion_volatility_bps", indicators.volatility_bps)
            self.telemetry.set_gauge("mean_reversion_bb_upper", indicators.bb_upper)
            self.telemetry.set_gauge("mean_reversion_bb_lower", indicators.bb_lower)
            self.telemetry.set_gauge("mean_reversion_ema_fast", indicators.ema_fast)
            self.telemetry.set_gauge("mean_reversion_ema_slow", indicators.ema_slow)

            if price:
                bb_position = (price - indicators.bb_lower) / (indicators.bb_upper - indicators.bb_lower) if indicators.bb_upper > indicators.bb_lower else 0.5
                self.telemetry.set_gauge("mean_reversion_bb_position", bb_position)
        except Exception:
            pass

    def _parse_market_id(self, market: str) -> Optional[int]:
        """Parse market identifier."""
        if not market or ":" not in market:
            return None
        try:
            return int(market.split(":")[1])
        except (ValueError, IndexError):
            return None

