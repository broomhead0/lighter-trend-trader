# modules/price_feed.py
"""Simple price feed to update state with current market prices."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

LOG = logging.getLogger("price_feed")


class PriceFeed:
    """Fetches current market price and updates state."""

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any,
        market: str = "market:2",
        update_interval: float = 5.0,
    ):
        self.cfg = config or {}
        self.state = state
        self.market = market
        self.update_interval = update_interval

        api_cfg = self.cfg.get("api") or {}
        self.api_base_url = api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai")

        self._stop = asyncio.Event()
        self._last_price: Optional[float] = None

    async def run(self):
        """Run price feed loop."""
        LOG.info(f"[price_feed] starting for {self.market}")

        while not self._stop.is_set():
            try:
                price = await self._fetch_current_price()
                if price is not None:
                    if self.state and hasattr(self.state, "update_mid"):
                        self.state.update_mid(self.market, price)
                        if price != self._last_price:
                            LOG.debug(f"[price_feed] {self.market} price: {price:.2f}")
                            self._last_price = price
                else:
                    LOG.warning("[price_feed] failed to fetch price")
            except Exception as e:
                LOG.warning(f"[price_feed] error: {e}")

            await asyncio.sleep(self.update_interval)

    async def stop(self):
        """Stop the price feed."""
        self._stop.set()

    async def _fetch_current_price(self) -> Optional[float]:
        """Fetch current market price from REST API."""
        if aiohttp is None:
            LOG.warning("[price_feed] aiohttp not available")
            return None

        try:
            market_id = self._parse_market_id(self.market)
            if market_id is None:
                return None

            # Try to get latest candle (most recent close price)
            url = f"{self.api_base_url.rstrip('/')}/public/markets/{market_id}/candles"
            params = {
                "interval": "1m",
                "limit": 1,  # Just get the latest candle
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    candles = data.get("candles") if isinstance(data, dict) else data

                    if isinstance(candles, list) and len(candles) > 0:
                        latest = candles[-1]
                        close_price = latest.get("close")
                        if close_price is not None:
                            return float(close_price)

                    # Fallback: try market stats endpoint if available
                    stats_url = f"{self.api_base_url.rstrip('/')}/public/markets/{market_id}/stats"
                    async with session.get(stats_url, timeout=5) as stats_resp:
                        if stats_resp.status == 200:
                            stats_data = await stats_resp.json()
                            mark_price = stats_data.get("mark_price") or stats_data.get("mid")
                            if mark_price is not None:
                                return float(mark_price)

        except Exception as e:
            LOG.debug(f"[price_feed] fetch error: {e}")

        return None

    def _parse_market_id(self, market: str) -> Optional[int]:
        """Parse market identifier."""
        if not market or ":" not in market:
            return None
        try:
            return int(market.split(":")[1])
        except (ValueError, IndexError):
            return None

