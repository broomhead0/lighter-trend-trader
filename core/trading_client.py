"""Trading client wrapper around Lighter's SignerClient.

This keeps the rest of the bot decoupled from the external SDK while
providing strongly-typed helpers for creating and cancelling orders.

The implementation is intentionally defensive:
  * Import failures for `lighter-python` surface as RuntimeError with
    an actionable message so dry-run usage still works without the SDK.
  * Market identifiers (`market:{index}`) are validated before issuing
    any signed transactions.
  * Size / price scaling are configurable per market so we do not make
    incorrect assumptions about instrument precision.

Usage flow (async):

    cfg = TradingConfig(
        base_url="https://mainnet.zklighter.elliot.ai",
        api_key_private_key="0x...",
        account_index=123,
        api_key_index=3,
        base_scale=1_000_000,
        price_scale=100,
    )

    client = TradingClient(cfg)
    await client.ensure_ready()
    order = await client.create_post_only_limit(
        market="market:1",
        side="ask",
        price=102_000.5,
        size=0.001,
    )
    await client.cancel_order("market:1", order.client_order_index)

"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


LOG = logging.getLogger("trading")


try:  # Optional dependency – only required for live trading
    import lighter  # type: ignore
    from lighter import SignerClient  # type: ignore
except Exception:  # pragma: no cover - handled lazily in TradingClient
    SignerClient = None  # type: ignore
    lighter = None  # type: ignore


@dataclass(slots=True)
class TradingConfig:
    base_url: str
    api_key_private_key: str
    account_index: int
    api_key_index: int
    base_scale: Decimal
    price_scale: Decimal
    nonce_management: Optional[str] = None
    max_api_key_index: Optional[int] = None


@dataclass(slots=True)
class PlacedOrder:
    """Thin representation of a placed order returned by TradingClient."""

    market: str
    side: str
    size: Decimal
    price: Decimal
    client_order_index: int
    tx_hash: Optional[str]


class TradingClient:
    def __init__(self, cfg: TradingConfig):
        self.cfg = cfg
        self._signer: Optional[SignerClient] = None
        self._lock = asyncio.Lock()
        self._next_client_order_index = int(time.time() * 1000)

    async def ensure_ready(self) -> None:
        if self._signer is not None:
            return

        if SignerClient is None or lighter is None:
            raise RuntimeError(
                "lighter-python package is not installed. Install via"
                " `pip install \"git+https://github.com/elliottech/lighter-python.git\"`"
                " to enable live order routing."
            )

        nonce_mgmt = None
        if self.cfg.nonce_management:
            try:
                nonce_mgmt = getattr(lighter.nonce_manager.NonceManagerType, self.cfg.nonce_management)
            except AttributeError as exc:  # pragma: no cover - config error
                raise ValueError(
                    f"Unknown nonce management mode: {self.cfg.nonce_management}"
                ) from exc

        LOG.info(
            "[trading] instantiating SignerClient account=%s api_index=%s",
            self.cfg.account_index,
            self.cfg.api_key_index,
        )

        self._signer = SignerClient(
            url=self.cfg.base_url,
            private_key=self.cfg.api_key_private_key,
            account_index=self.cfg.account_index,
            api_key_index=self.cfg.api_key_index,
            max_api_key_index=(self.cfg.max_api_key_index or self.cfg.api_key_index),
            nonce_management_type=(nonce_mgmt or lighter.nonce_manager.NonceManagerType.OPTIMISTIC),
        )

        err = self._signer.check_client()
        if err is not None:
            raise RuntimeError(f"Signer client health check failed: {err}")

    async def close(self) -> None:
        if self._signer is not None:
            await self._signer.close()
            self._signer = None

    # ------------------------------------------------------------------
    # Order helpers

    async def create_post_only_limit(
        self,
        market: str,
        side: str,
        price: float,
        size: float,
        reduce_only: bool = False,
        expiry: Optional[int] = None,
    ) -> PlacedOrder:
        return await self.create_limit_order(
            market=market,
            side=side,
            price=price,
            size=size,
            reduce_only=reduce_only,
            expiry=expiry,
            post_only=True,
        )

    async def create_limit_order(
        self,
        market: str,
        side: str,
        price: float,
        size: float,
        reduce_only: bool = False,
        expiry: Optional[int] = None,
        *,
        post_only: bool = True,
        time_in_force: Optional[int] = None,
    ) -> PlacedOrder:
        signer = await self._require_signer()
        market_index = self._parse_market_index(market)
        client_order_index = await self._next_order_index()

        base_units = self._round_scaled_value(size, self.cfg.base_scale, "size")
        price_units = self._round_scaled_value(price, self.cfg.price_scale, "price")

        base_int = int(base_units)
        price_int = int(price_units)
        if base_int <= 0:
            raise ValueError(f"size scales to non-positive integer ({base_units})")
        if price_int <= 0:
            raise ValueError(f"price scales to non-positive integer ({price_units})")

        LOG.info(
            "[trading] submitting %s order: market=%s client_order_index=%s base_units=%s price_units=%s tif=%s post_only=%s",
            side,
            market,
            client_order_index,
            base_int,
            price_int,
            time_in_force if time_in_force is not None else ("POST_ONLY" if post_only else "DEFAULT"),
            post_only,
        )

        tif = time_in_force
        if tif is None:
            assert SignerClient is not None
            tif = (
                SignerClient.ORDER_TIME_IN_FORCE_POST_ONLY
                if post_only
                else SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
            )

        expiry_val = self._resolve_expiry(expiry, tif)

        tx, tx_hash, err = await signer.create_order(
            market_index=market_index,
            client_order_index=client_order_index,
            base_amount=base_int,
            price=price_int,
            is_ask=side.lower() == "ask",
            order_type=SignerClient.ORDER_TYPE_LIMIT,
            time_in_force=tif,
            reduce_only=reduce_only,
            order_expiry=expiry_val,
        )

        if err:
            raise RuntimeError(f"Create order failed: {err}")

        tx_hash_value = None
        if tx_hash is not None:
            tx_hash_value = getattr(tx_hash, "tx_hash", None) or getattr(tx_hash, "hash", None) or str(tx_hash)

        return PlacedOrder(
            market=market,
            side=side,
            size=Decimal(str(size)),
            price=Decimal(str(price)),
            client_order_index=client_order_index,
            tx_hash=tx_hash_value,
        )

    async def cancel_order(self, market: str, client_order_index: int) -> None:
        signer = await self._require_signer()
        market_index = self._parse_market_index(market)

        LOG.info(
            "[trading] cancelling order market=%s client_order_index=%s",
            market,
            client_order_index,
        )

        _tx, _tx_hash, err = await signer.cancel_order(
            market_index=market_index,
            order_index=int(client_order_index),
        )

        if err:
            raise RuntimeError(f"Cancel order failed: {err}")

    # ------------------------------------------------------------------
    # Internal helpers

    async def _require_signer(self) -> SignerClient:
        await self.ensure_ready()
        assert self._signer is not None  # satisfy type-checkers
        return self._signer

    async def _next_order_index(self) -> int:
        async with self._lock:
            self._next_client_order_index += 1
            return self._next_client_order_index

    def _parse_market_index(self, market: str) -> int:
        if not market:
            raise ValueError("market identifier is required")
        if ":" not in market:
            raise ValueError(f"unexpected market format: {market}")
        prefix, suffix = market.split(":", 1)
        if prefix != "market":
            raise ValueError(f"unsupported market prefix: {prefix}")
        try:
            return int(suffix)
        except ValueError as exc:
            raise ValueError(f"invalid market index: {market}") from exc

    def _scale_value(self, raw_value: float, scale: Decimal, label: str) -> Decimal:
        if scale <= 0:
            raise ValueError(f"{label} scale must be positive (got {scale})")
        return Decimal(str(raw_value)) * scale

    def _round_scaled_value(self, raw_value: float, scale: Decimal, label: str) -> Decimal:
        scaled = self._scale_value(raw_value, scale, label)
        return scaled.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    def _resolve_expiry(self, override: Optional[int], tif: Optional[int]) -> int:
        if override is not None:
            return int(override)
        if SignerClient is None:
            raise RuntimeError("SignerClient unavailable; cannot resolve expiry")
        if tif == getattr(SignerClient, "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL", None):
            return 0
        # Default to the SDK's 28-day expiry for post-only / GTT limit orders
        return SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY


