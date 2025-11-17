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

        # Position sizes (small for testing)
        self.max_position_size = float(self.cfg.get("max_position_size", 0.002))  # Max SOL per trade (small for testing)
        self.min_position_size = float(self.cfg.get("min_position_size", 0.001))  # Min SOL per trade (small for testing)

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

        # API base URL for fetching candles
        api_cfg = self.cfg.get("api", {})
        self.api_base_url = str(api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai"))
        self._last_candle_fetch = 0.0
        self._candle_fetch_interval = 300.0  # Fetch candles every 5 minutes

        LOG.info(
            f"[breakout] initialized: market={self.market}, "
            f"dry_run={self.dry_run}, candle_interval={self.candle_interval_seconds}s"
        )

    async def run(self) -> None:
        """Main trading loop."""
        LOG.info("[breakout] starting trading loop")

        # Check for existing position on startup (recover from deploy)
        await self._recover_existing_position()

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

                # Cancel stale orders
                await self._cancel_stale_orders()

                # Update indicators
                indicators = self._compute_indicators()
                if indicators is None:
                    needed = max(self.bb_period, self.rsi_period, self.atr_period, self.ema_slow_period, self.macd_slow)
                    if len(self._candles) < needed:
                        LOG.info(f"[breakout] collecting candles: {len(self._candles)}/{needed}")
                    await asyncio.sleep(5.0)
                    continue

                # Check for exit signals if in position
                if self._current_position:
                    exit_signal = self._check_exit(current_price, indicators)
                    if exit_signal:
                        await self._exit_position(exit_signal)

                # Check for entry signals if no position
                if not self._current_position:
                    # Adaptive trading: check if we should pause after losing streak
                    if time.time() < self._pause_until:
                        if int(time.time()) % 30 == 0:
                            LOG.info(f"[breakout] paused due to losing streak, resuming in {int(self._pause_until - time.time())}s")
                        await asyncio.sleep(5.0)
                        continue

                    # Adaptive position cooldown
                    self._update_adaptive_cooldown(indicators)
                    time_since_exit = time.time() - self._last_exit_time
                    if time_since_exit < self._exit_cooldown_seconds:
                        if int(time.time()) % 10 == 0:
                            LOG.info(f"[breakout] exit cooldown: waiting {self._exit_cooldown_seconds - time_since_exit:.1f}s")
                        await asyncio.sleep(5.0)
                        continue

                    signal = self._check_entry(current_price, indicators)
                    if signal:
                        await self._enter_position(signal)

                # Update telemetry
                self._update_telemetry(indicators, current_price)

                await asyncio.sleep(5.0)  # Check every 5 seconds

            except Exception as e:
                LOG.exception("[breakout] error in trading loop: %s", e)
                await asyncio.sleep(10.0)

    async def _recover_existing_position(self) -> None:
        """Check for existing position on exchange and recover state."""
        if self.dry_run or not self.trading_client:
            return

        try:
            # Get current price
            current_price = self._get_current_price()
            if not current_price:
                LOG.warning("[breakout] Cannot recover position: no current price available")
                return

            # Try to get position from signer client if available
            try:
                if hasattr(self.trading_client, "_signer") and self.trading_client._signer:
                    await self.trading_client.ensure_ready()
                    LOG.info("[breakout] Checking for existing positions on exchange...")
                    LOG.warning(
                        "[breakout] ⚠️  Position recovery: If you have an open position, "
                        "the bot will not manage it until it's manually closed or the bot takes a new trade. "
                        "Consider manually closing profitable positions or wait for exit conditions to trigger."
                    )
            except Exception as e:
                LOG.debug(f"[breakout] Could not check exchange positions: {e}")

        except Exception as e:
            LOG.exception(f"[breakout] error recovering position: {e}")

    async def stop(self) -> None:
        """Stop the trader."""
        self._stop.set()
        if self._current_position:
            await self._exit_position("stop")

    # ------------------------- Candle Management -------------------------

    async def _fetch_candles(self) -> None:
        """Fetch recent candles from REST API."""
        try:
            import aiohttp

            market_id = self._parse_market_id(self.market)
            if market_id is None:
                LOG.warning("[breakout] invalid market: %s", self.market)
                return

            urls_to_try = [
                f"{self.api_base_url.rstrip('/')}/public/markets/{market_id}/candles",
                f"{self.api_base_url.rstrip('/')}/markets/{market_id}/candles",
            ]

            interval_map = {
                60: "1m",
                300: "5m",
                900: "15m",
                3600: "1h",
            }
            interval_str = interval_map.get(self.candle_interval_seconds, "15m")

            params = {"interval": interval_str, "limit": 100}

            async with aiohttp.ClientSession() as session:
                data = None
                for url in urls_to_try:
                    try:
                        async with session.get(url, params=params, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                break
                    except Exception:
                        continue

                if data is None:
                    return

                candles_data = data.get("candles") if isinstance(data, dict) else data
                if not isinstance(candles_data, list):
                    return

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
                    new_candles.sort(key=lambda x: x.open_time)
                    self._candles.clear()
                    self._candles.extend(new_candles)
                    LOG.debug("[breakout] fetched %d candles", len(new_candles))

        except Exception as e:
            LOG.warning("[breakout] error fetching candles: %s", e)

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
        current_candle_time = int(now // self.candle_interval_seconds) * self.candle_interval_seconds

        if not self._candles or self._candles[-1].open_time < current_candle_time:
            new_candle = Candle(
                open_time=current_candle_time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=0.0,
            )
            self._candles.append(new_candle)
            if len(self._candles) > 200:
                self._candles = self._candles[-200:]
            LOG.debug(f"[breakout] created new candle at {current_candle_time}, price={price:.2f}")
        else:
            current_candle = self._candles[-1]
            current_candle.high = max(current_candle.high, price)
            current_candle.low = min(current_candle.low, price)
            current_candle.close = price

    def _parse_market_id(self, market: str) -> Optional[int]:
        """Parse market ID from market string (e.g., 'market:2' -> 2)."""
        try:
            if ":" in market:
                return int(market.split(":")[1])
            return int(market)
        except (ValueError, IndexError):
            return None

    # ------------------------- Indicator Computation -------------------------

    def _compute_indicators(self) -> Optional[Indicators]:
        """Compute all technical indicators from candles."""
        if len(self._candles) < max(self.bb_period, self.rsi_period, self.atr_period, self.ema_slow_period, self.macd_slow):
            return None

        candles_list = list(self._candles)

        # EMA
        ema_20 = self._compute_ema(candles_list, self.ema_fast_period)
        ema_50 = self._compute_ema(candles_list, self.ema_slow_period)

        # Bollinger Bands
        bb_middle, bb_upper, bb_lower = self._compute_bollinger_bands(candles_list, self.bb_period, self.bb_std)
        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.0

        # RSI
        rsi = self._compute_rsi(candles_list, self.rsi_period)

        # MACD
        macd, macd_signal, macd_histogram = self._compute_macd(candles_list)

        # ATR
        atr = self._compute_atr(candles_list, self.atr_period)

        # Volatility
        volatility_bps = self._compute_volatility_bps(candles_list)

        # Recent high/low (for breakout detection)
        recent_high, recent_low = self._compute_recent_high_low(candles_list, self.breakout_lookback)

        # Breakout levels
        breakout_level_long = recent_high if recent_high > 0 else None
        breakout_level_short = recent_low if recent_low > 0 else None

        # ATR expansion check
        atr_expanding = self._check_atr_expansion(candles_list, atr)

        # BB width expansion check
        bb_width_expanding = self._check_bb_width_expansion(candles_list, bb_width)

        return Indicators(
            ema_20=ema_20,
            ema_50=ema_50,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            atr=atr,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            bb_width=bb_width,
            volatility_bps=volatility_bps,
            recent_high=recent_high,
            recent_low=recent_low,
            breakout_level_long=breakout_level_long,
            breakout_level_short=breakout_level_short,
            atr_expanding=atr_expanding,
            bb_width_expanding=bb_width_expanding,
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
            return 50.0

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
        avg_loss = sum(losses) / len(losses) if losses else 0.0001

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _compute_macd(self, candles: List[Candle]) -> Tuple[float, float, float]:
        """Compute MACD (Moving Average Convergence Divergence)."""
        if len(candles) < self.macd_slow:
            return 0.0, 0.0, 0.0

        # EMA fast (12)
        ema_fast = self._compute_ema(candles, self.macd_fast)
        # EMA slow (26)
        ema_slow = self._compute_ema(candles, self.macd_slow)

        macd_line = ema_fast - ema_slow

        # MACD signal line (9-period EMA of MACD line)
        # We need to compute this from MACD values over time
        # For simplicity, use a smoothed version
        if len(candles) >= self.macd_slow + self.macd_signal:
            macd_values = []
            for i in range(self.macd_slow, len(candles)):
                fast_ema = self._compute_ema(candles[:i+1], self.macd_fast)
                slow_ema = self._compute_ema(candles[:i+1], self.macd_slow)
                macd_values.append(fast_ema - slow_ema)

            if len(macd_values) >= self.macd_signal:
                # Compute EMA of MACD values
                multiplier = 2.0 / (self.macd_signal + 1)
                signal_line = macd_values[0]
                for val in macd_values[1:]:
                    signal_line = (val * multiplier) + (signal_line * (1 - multiplier))
            else:
                signal_line = macd_line * 0.9  # Approximate
        else:
            signal_line = macd_line * 0.9  # Approximate

        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

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

    def _compute_volatility_bps(self, candles: List[Candle], lookback: int = 20) -> float:
        """Compute volatility in basis points."""
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
        volatility_bps = avg_return * 10000
        return volatility_bps

    def _compute_recent_high_low(self, candles: List[Candle], lookback: int) -> Tuple[float, float]:
        """Compute recent high and low for breakout detection."""
        if len(candles) < lookback:
            lookback = len(candles)

        recent_candles = candles[-lookback:]
        recent_high = max(c.high for c in recent_candles)
        recent_low = min(c.low for c in recent_candles)

        return recent_high, recent_low

    def _check_atr_expansion(self, candles: List[Candle], current_atr: float) -> bool:
        """Check if ATR is expanding (current > average of recent ATRs)."""
        if len(candles) < self.atr_period * 2:
            return False

        # Compute ATR for last 5 periods
        recent_atrs = []
        for i in range(5):
            if len(candles) >= self.atr_period + i:
                atr_val = self._compute_atr(candles[:-(i or None) or len(candles)], self.atr_period)
                recent_atrs.append(atr_val)

        if not recent_atrs:
            return False

        avg_atr = sum(recent_atrs) / len(recent_atrs)
        return current_atr >= avg_atr * self.min_atr_expansion

    def _check_bb_width_expansion(self, candles: List[Candle], current_bb_width: float) -> bool:
        """Check if BB width is expanding."""
        if len(candles) < self.bb_period * 2:
            return False

        # Compute BB width for last 5 periods
        recent_widths = []
        for i in range(5):
            if len(candles) >= self.bb_period + i:
                _, upper, lower = self._compute_bollinger_bands(candles[:-(i or None) or len(candles)], self.bb_period, self.bb_std)
                middle = (upper + lower) / 2.0
                width = (upper - lower) / middle if middle > 0 else 0.0
                recent_widths.append(width)

        if not recent_widths:
            return False

        avg_width = sum(recent_widths) / len(recent_widths)
        return current_bb_width >= avg_width * 1.05  # 5% expansion

    # ------------------------- Signal Generation -------------------------

    def _check_entry(self, price: float, indicators: Indicators) -> Optional[Signal]:
        """Check for breakout entry signals."""
        # Volatility filter
        vol_bps = indicators.volatility_bps
        if vol_bps < self.atr_min_bps or vol_bps > self.atr_max_bps:
            LOG.debug(f"[breakout] volatility filter: {vol_bps:.1f} bps (need {self.atr_min_bps}-{self.atr_max_bps})")
            return None

        # Check for long breakout
        if indicators.breakout_level_long and price > indicators.breakout_level_long:
            # Check if candle closed above breakout level (confirmation)
            latest_candle = self._candles[-1] if self._candles else None
            if latest_candle and latest_candle.close > indicators.breakout_level_long:
                # All filters must pass
                if (indicators.rsi > self.rsi_bullish_threshold and
                    indicators.macd > indicators.macd_signal and
                    indicators.atr_expanding and
                    indicators.ema_20 > indicators.ema_50 and
                    price > indicators.ema_20):

                    # ENHANCED LOGGING
                    hour = datetime.fromtimestamp(time.time()).hour
                    minute = datetime.fromtimestamp(time.time()).minute
                    LOG.info(f"[breakout] ENTRY CONDITIONS: "
                             f"Breakout={price:.2f}>{indicators.breakout_level_long:.2f}, "
                             f"RSI={indicators.rsi:.1f}, MACD={indicators.macd:.4f}>{indicators.macd_signal:.4f}, "
                             f"ATR_exp={indicators.atr_expanding}, EMA_20={indicators.ema_20:.2f}>{indicators.ema_50:.2f}, "
                             f"Vol={vol_bps:.1f}bps, Time={hour:02d}:{minute:02d}")

                    return self._create_signal("long", price, indicators, indicators.breakout_level_long)

        # Check for short breakout
        if indicators.breakout_level_short and price < indicators.breakout_level_short:
            latest_candle = self._candles[-1] if self._candles else None
            if latest_candle and latest_candle.close < indicators.breakout_level_short:
                if (indicators.rsi < self.rsi_bearish_threshold and
                    indicators.macd < indicators.macd_signal and
                    indicators.atr_expanding and
                    indicators.ema_20 < indicators.ema_50 and
                    price < indicators.ema_20):

                    # ENHANCED LOGGING
                    hour = datetime.fromtimestamp(time.time()).hour
                    minute = datetime.fromtimestamp(time.time()).minute
                    LOG.info(f"[breakout] ENTRY CONDITIONS: "
                             f"Breakout={price:.2f}<{indicators.breakout_level_short:.2f}, "
                             f"RSI={indicators.rsi:.1f}, MACD={indicators.macd:.4f}<{indicators.macd_signal:.4f}, "
                             f"ATR_exp={indicators.atr_expanding}, EMA_20={indicators.ema_20:.2f}<{indicators.ema_50:.2f}, "
                             f"Vol={vol_bps:.1f}bps, Time={hour:02d}:{minute:02d}")

                    return self._create_signal("short", price, indicators, indicators.breakout_level_short)

        return None

    def _create_signal(self, side: str, price: float, indicators: Indicators, breakout_level: float) -> Signal:
        """Create a trading signal with risk management."""
        atr = indicators.atr
        if atr <= 0:
            atr = price * 0.01  # Fallback: 1% of price

        # Calculate stop loss and take profit based on ATR
        if side == "long":
            stop_loss = breakout_level - (atr * self.stop_loss_atr_multiplier)
            take_profit = price + (atr * self.take_profit_atr_multiplier)
        else:  # short
            stop_loss = breakout_level + (atr * self.stop_loss_atr_multiplier)
            take_profit = price - (atr * self.take_profit_atr_multiplier)

        # Position sizing
        size = self.min_position_size
        if indicators.volatility_bps > 10:  # High vol, reduce size
            size *= 0.8
        if indicators.rsi > 70 or indicators.rsi < 30:  # Very strong momentum, increase size
            size *= 1.1

        size = max(self.min_position_size, min(self.max_position_size, size))

        strength = min(1.0, abs(indicators.macd_histogram) * 100)  # Based on MACD strength

        return Signal(
            side=side,
            strength=min(1.0, max(0.0, strength)),
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size=size,
            reason=f"breakout_{side}",
            breakout_level=breakout_level,
        )

    def _check_exit(self, price: float, indicators: Indicators) -> Optional[str]:
        """Check for exit signals with trailing stops and MFE/MAE tracking."""
        if not self._current_position:
            return None

        pos = self._current_position
        side = pos["side"]
        entry_price = pos["entry_price"]
        stop_loss = pos["stop_loss"]
        take_profit = pos["take_profit"]
        entry_time = pos["entry_time"]
        breakout_level = pos.get("breakout_level", entry_price)
        position_id = f"{side}_{entry_price}_{entry_time}"

        # Calculate current PnL for MFE/MAE tracking
        if side == "long":
            current_pnl_pct = (price - entry_price) / entry_price * 100
        else:
            current_pnl_pct = (entry_price - price) / entry_price * 100

        # Track MFE/MAE
        if position_id not in self._mfe_tracker:
            self._mfe_tracker[position_id] = current_pnl_pct
        else:
            self._mfe_tracker[position_id] = max(self._mfe_tracker[position_id], current_pnl_pct)

        if position_id not in self._mae_tracker:
            self._mae_tracker[position_id] = current_pnl_pct
        else:
            self._mae_tracker[position_id] = min(self._mae_tracker[position_id], current_pnl_pct)

        # Trailing stop
        mfe = self._mfe_tracker.get(position_id, 0.0)
        atr = indicators.atr
        # Check if we've reached activation threshold (1x ATR profit in bps)
        activation_threshold_bps = (atr / entry_price) * 10000 * self.trailing_stop_activation_atr
        if atr > 0 and mfe >= activation_threshold_bps:
            # Activate trailing stop
            trailing_distance = atr * self.trailing_stop_distance_atr
            if side == "long":
                trailing_stop = price - trailing_distance
                if trailing_stop > stop_loss:  # Only tighten, never widen
                    pos["stop_loss"] = trailing_stop
                    stop_loss = trailing_stop
                    LOG.debug(f"[breakout] trailing stop activated: MFE={mfe:.2f}%, new stop={stop_loss:.2f}")
            else:  # short
                trailing_stop = price + trailing_distance
                if trailing_stop < stop_loss:  # Only tighten, never widen
                    pos["stop_loss"] = trailing_stop
                    stop_loss = trailing_stop
                    LOG.debug(f"[breakout] trailing stop activated: MFE={mfe:.2f}%, new stop={stop_loss:.2f}")

        # Breakout failure (price closes back below/above breakout level)
        latest_candle = self._candles[-1] if self._candles else None
        if latest_candle:
            if side == "long" and latest_candle.close < breakout_level:
                return "breakout_failure"
            if side == "short" and latest_candle.close > breakout_level:
                return "breakout_failure"

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

        # No movement stop
        if time.time() - entry_time > (self.no_movement_minutes * 60):
            # Check if we've made progress
            if side == "long" and price <= entry_price:
                return "no_movement"
            if side == "short" and price >= entry_price:
                return "no_movement"

        return None

    # ------------------------- Position Management -------------------------

    async def _enter_position(self, signal: Signal) -> None:
        """Enter a position based on signal."""
        if not self.trading_client and not self.dry_run:
            LOG.warning("[breakout] no trading client, cannot enter position")
            return

        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            await self._cancel_stale_orders()

            order_side = "bid" if signal.side == "long" else "ask"
            order_price = signal.entry_price * 1.0001 if signal.side == "long" else signal.entry_price * 0.9999

            if signal.size < self.min_position_size:
                LOG.error(f"[breakout] order size {signal.size:.4f} below minimum {self.min_position_size}")
                return

            if self.dry_run:
                LOG.info(f"[breakout] DRY RUN: would place {order_side} order")
                self._current_position = {
                    "side": signal.side,
                    "entry_price": signal.entry_price,
                    "size": signal.size,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "breakout_level": signal.breakout_level,
                    "order_index": 0,
                }
            else:
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
                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "rate limit" in error_str.lower():
                            wait_time = retry_delay * (2 ** attempt)
                            LOG.warning(f"[breakout] rate limit on entry (attempt {attempt+1}/{max_retries}), waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                        elif "21104" in error_str or "invalid nonce" in error_str.lower():
                            LOG.warning(f"[breakout] invalid nonce on entry (attempt {attempt+1}/{max_retries}), retrying...")
                            await asyncio.sleep(retry_delay)
                        else:
                            raise

                if order is None:
                    LOG.error(f"[breakout] failed to create entry order after {max_retries} attempts")
                    return

                self._open_orders[order.client_order_index] = order
                self._order_timestamps[order.client_order_index] = time.time()
                self._current_position = {
                    "side": signal.side,
                    "entry_price": signal.entry_price,
                    "size": signal.size,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "entry_time": time.time(),
                    "breakout_level": signal.breakout_level,
                    "order_index": order.client_order_index,
                }

                if self.telemetry:
                    self.telemetry.set_gauge("breakout_position_side", 1.0 if signal.side == "long" else -1.0)
                    self.telemetry.set_gauge("breakout_position_size", float(signal.size))

        except Exception as e:
            LOG.exception("[breakout] error entering position: %s", e)

    async def _exit_position(self, reason: str) -> None:
        """Exit current position."""
        if not self._current_position:
            return

        pos = self._current_position
        LOG.info(f"[breakout] exiting position: side={pos['side']} entry={pos['entry_price']:.2f} reason={reason}")

        if not self.trading_client and not self.dry_run:
            self._current_position = None
            return

        try:
            if self.trading_client:
                await self.trading_client.ensure_ready()

            exit_side = "ask" if pos["side"] == "long" else "bid"
            current_price = self._get_current_price() or pos["entry_price"]

            # Calculate PnL
            if pos["side"] == "long":
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            else:
                pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100

            if self.dry_run:
                LOG.info(f"[breakout] DRY RUN: would exit {exit_side} position")
                LOG.info(f"[breakout] simulated PnL: {pnl_pct:.2f}%")
            else:
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
                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "rate limit" in error_str.lower():
                            wait_time = retry_delay * (2 ** attempt)
                            LOG.warning(f"[breakout] rate limit on exit (attempt {attempt+1}/{max_retries}), waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                        elif "21104" in error_str or "invalid nonce" in error_str.lower():
                            LOG.warning(f"[breakout] invalid nonce on exit (attempt {attempt+1}/{max_retries}), retrying...")
                            await asyncio.sleep(retry_delay)
                        else:
                            raise

                if order:
                    if pos["order_index"] in self._open_orders:
                        del self._open_orders[pos["order_index"]]
                    if pos["order_index"] in self._order_timestamps:
                        del self._order_timestamps[pos["order_index"]]

                await self._cancel_stale_orders()

            # Calculate MFE/MAE for enhanced logging
            position_id = f"{pos['side']}_{pos['entry_price']}_{pos['entry_time']}"
            mfe = self._mfe_tracker.get(position_id, pnl_pct)
            mae = self._mae_tracker.get(position_id, pnl_pct)
            time_in_trade = time.time() - pos["entry_time"]

            # ENHANCED LOGGING
            hour = datetime.fromtimestamp(time.time()).hour
            minute = datetime.fromtimestamp(time.time()).minute
            LOG.info(f"[breakout] EXIT CONDITIONS: "
                     f"Reason={reason}, Time_in_trade={time_in_trade:.0f}s, "
                     f"MFE={mfe:.2f}%, MAE={mae:.2f}%, Time={hour:02d}:{minute:02d}")

            LOG.info(f"[breakout] LIVE PnL: {pnl_pct:.2f}% (entry={pos['entry_price']:.2f}, exit={current_price:.2f}, size={pos['size']:.4f})")

            self._recent_exit_reasons.append(reason)
            self._recent_pnl.append(pnl_pct)

            if pnl_pct < 0:
                self._losing_streak += 1
                if self._losing_streak >= self._max_losing_streak_before_pause:
                    self._pause_until = time.time() + self._pause_duration_seconds
                    LOG.warning(f"[breakout] ⚠️  Losing streak: {self._losing_streak} trades, pausing for {self._pause_duration_seconds}s")
            else:
                self._losing_streak = 0

            # Record in PnL tracker
            if hasattr(self, "pnl_tracker") and self.pnl_tracker:
                await self.pnl_tracker.record_trade(
                    strategy="breakout",
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

            # Clean up
            if position_id in self._mfe_tracker:
                del self._mfe_tracker[position_id]
            if position_id in self._mae_tracker:
                del self._mae_tracker[position_id]

            self._last_exit_time = time.time()
            self._current_position = None

            if self.telemetry:
                self.telemetry.set_gauge("breakout_position_side", 0.0)
                self.telemetry.set_gauge("breakout_position_size", 0.0)

        except Exception as e:
            LOG.exception("[breakout] error exiting position: %s", e)

    async def _cancel_stale_orders(self) -> None:
        """Cancel orders that haven't filled after timeout."""
        if not self.trading_client:
            return

        current_time = time.time()
        stale_indices = [
            idx for idx, ts in self._order_timestamps.items()
            if current_time - ts > self._order_timeout_seconds
        ]

        for idx in stale_indices:
            try:
                await self.trading_client.cancel_order(self.market, idx)
                LOG.info(f"[breakout] cancelled stale order {idx}")
                if idx in self._open_orders:
                    del self._open_orders[idx]
                if idx in self._order_timestamps:
                    del self._order_timestamps[idx]
            except Exception as e:
                LOG.warning(f"[breakout] failed to cancel stale order {idx}: {e}")

    def _update_adaptive_cooldown(self, indicators: Optional[Indicators]) -> None:
        """Update exit cooldown based on volatility and recent performance."""
        if indicators is None:
            self._exit_cooldown_seconds = self._base_exit_cooldown_seconds
            return

        cooldown = self._base_exit_cooldown_seconds
        vol = indicators.volatility_bps

        if vol > 10:
            cooldown *= 1.5
        elif vol < 3:
            cooldown *= 0.8

        stop_loss_count = sum(1 for r in self._recent_exit_reasons if r == "stop_loss")
        if stop_loss_count >= 2:
            cooldown *= 1.3

        if self._losing_streak >= 2:
            cooldown *= 1.2

        # Breakout failure extends cooldown
        if any(r == "breakout_failure" for r in self._recent_exit_reasons):
            cooldown *= 2.0  # 60 seconds for failed breakouts

        self._exit_cooldown_seconds = min(cooldown, 120.0)  # Cap at 120 seconds

    def _update_telemetry(self, indicators: Optional[Indicators], price: float) -> None:
        """Update telemetry metrics."""
        if not self.telemetry or indicators is None:
            return

        self.telemetry.set_gauge("breakout_rsi", indicators.rsi)
        self.telemetry.set_gauge("breakout_macd", indicators.macd)
        self.telemetry.set_gauge("breakout_atr", indicators.atr)
        self.telemetry.set_gauge("breakout_volatility_bps", indicators.volatility_bps)

