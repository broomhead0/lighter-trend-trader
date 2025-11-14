# modules/ws_price_feed.py
"""WebSocket-based price feed for real-time market data."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

try:
    import websockets  # type: ignore
except ImportError:
    websockets = None

LOG = logging.getLogger("ws_price_feed")


class WebSocketPriceFeed:
    """WebSocket-based price feed that subscribes to market_stats channel."""

    def __init__(
        self,
        config: Dict[str, Any],
        state: Any,
        market: str = "market:2",
    ):
        self.cfg = config or {}
        self.state = state
        self.market = market

        # WebSocket config
        ws_cfg = (self.cfg.get("ws") or {}) if isinstance(self.cfg.get("ws"), dict) else {}
        self.ws_url = ws_cfg.get("url") or os.environ.get("WS_URL", "wss://mainnet.zklighter.elliot.ai/stream")
        self.ws_auth_token = ws_cfg.get("auth_token") or os.environ.get("WS_AUTH_TOKEN")

        # Parse market ID for channel subscription
        market_id = self._parse_market_id(market)
        if market_id:
            # Subscribe to specific market stats
            self.ws_channels = [f"market_stats/{market_id}", "market_stats:all"]
        else:
            # Fallback to all markets
            self.ws_channels = ["market_stats:all"]

        self._stop = asyncio.Event()
        self._ws_subscribed_channels: set[str] = set()
        self._last_price: Optional[float] = None

    async def run(self):
        """Run WebSocket price feed loop."""
        if websockets is None:
            LOG.error("[ws_price_feed] websockets library not available")
            return

        LOG.info(f"[ws_price_feed] starting for {self.market}")
        LOG.info(f"[ws_price_feed] connecting to {self.ws_url}")

        while not self._stop.is_set():
            try:
                await self._run_ws_once()
            except Exception as e:
                LOG.warning(f"[ws_price_feed] connection error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _run_ws_once(self):
        """Run WebSocket connection once."""
        assert websockets is not None

        async with websockets.connect(
            self.ws_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        ) as ws:  # type: ignore
            LOG.info("[ws_price_feed] WebSocket connected")
            self._ws_subscribed_channels.clear()
            await self._send_subscriptions(ws)

            while not self._stop.is_set():
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=60)  # type: ignore
                    if isinstance(raw_msg, (bytes, bytearray)):
                        raw_msg = raw_msg.decode("utf-8", "ignore")

                    try:
                        obj = json.loads(raw_msg) if raw_msg else {}
                    except Exception:
                        LOG.debug("[ws_price_feed] unable to parse frame as JSON")
                        continue

                    msg_type = obj.get("type")
                    if msg_type == "connected":
                        await self._send_subscriptions(ws)
                        continue
                    if msg_type == "ping":
                        try:
                            await ws.send(json.dumps({"type": "pong"}))
                        except Exception:
                            pass
                        continue

                    # Handle market_stats updates
                    self._handle_market_stats(obj)

                except asyncio.TimeoutError:
                    LOG.debug("[ws_price_feed] no message received in 60s")
                    continue
                except Exception as e:
                    LOG.warning(f"[ws_price_feed] error receiving message: {e}")
                    break

    async def _send_subscriptions(self, ws) -> None:
        """Send WebSocket subscription messages."""
        for channel in self.ws_channels:
            if channel in self._ws_subscribed_channels:
                continue
            payload = {"type": "subscribe", "channel": channel}
            if self.ws_auth_token:
                payload["auth"] = self.ws_auth_token
            try:
                await ws.send(json.dumps(payload))
                LOG.info(f"[ws_price_feed] subscribed to {channel}")
                self._ws_subscribed_channels.add(channel)
            except Exception as e:
                LOG.warning(f"[ws_price_feed] failed to subscribe {channel}: {e}")

    def _handle_market_stats(self, obj: Dict[str, Any]):
        """Handle market_stats update message."""
        channel = obj.get("channel", "")
        msg_type = obj.get("type", "")

        if not msg_type.endswith("market_stats"):
            return

        # Try to extract mid price from various message formats
        data_list = obj.get("data")
        if isinstance(data_list, list):
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                market_id = item.get("market")
                mid = item.get("mid") or item.get("mark_price")
                if market_id and mid is not None:
                    self._update_price(market_id, mid)

        # Also check market_stats key directly
        market_stats_obj = obj.get("market_stats")
        if isinstance(market_stats_obj, dict):
            market_id = market_stats_obj.get("market_id")
            mark_price = market_stats_obj.get("mark_price") or market_stats_obj.get("mid")
            if market_id and mark_price is not None:
                self._update_price(market_id, mark_price)

    def _update_price(self, market_id: Any, mid_value: Any):
        """Update price in state store."""
        formatted_market = self._format_market_id(market_id)
        if not formatted_market:
            return

        try:
            mid = float(mid_value)
        except (ValueError, TypeError):
            return

        # Only update if it's our target market
        if formatted_market == self.market:
            if self.state and hasattr(self.state, "update_mid"):
                try:
                    self.state.update_mid(formatted_market, mid)
                    if mid != self._last_price:
                        LOG.info(f"[ws_price_feed] {formatted_market} price: {mid:.2f}")
                        self._last_price = mid
                except Exception as e:
                    LOG.debug(f"[ws_price_feed] state.update_mid failed: {e}")

    def _format_market_id(self, market_id) -> Optional[str]:
        """Format market ID to market:X format."""
        if isinstance(market_id, str) and market_id:
            if market_id.startswith("market:"):
                return market_id
            try:
                return f"market:{int(market_id)}"
            except ValueError:
                return None
        if isinstance(market_id, int):
            return f"market:{market_id}"
        if isinstance(market_id, float) and market_id.is_integer():
            return f"market:{int(market_id)}"
        return None

    def _parse_market_id(self, market: str) -> Optional[int]:
        """Parse market identifier."""
        if not market or ":" not in market:
            return None
        try:
            return int(market.split(":")[1])
        except (ValueError, IndexError):
            return None

    async def stop(self):
        """Stop the price feed."""
        self._stop.set()

