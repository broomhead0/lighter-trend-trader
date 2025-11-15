#!/usr/bin/env python3
"""Main entry point for Lighter Trend Trader."""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from core.state_store import StateStore
from core.trading_client import TradingClient, TradingConfig
from modules.mean_reversion_trader import MeanReversionTrader
from modules.renko_ao_trader import RenkoAOTrader
from modules.ws_price_feed import WebSocketPriceFeed
from modules.pnl_tracker import PnLTracker

LOG = logging.getLogger("main")


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file or use defaults."""
    cfg_path = os.environ.get("LIGHTER_CONFIG", "config.yaml")

    # If config file doesn't exist, use defaults (Railway uses env vars)
    if not Path(cfg_path).exists():
        LOG.warning(f"Config file not found: {cfg_path}, using defaults from config.yaml.example")
        # Try to load from example, or use empty dict (env vars will override)
        example_path = "config.yaml.example"
        if Path(example_path).exists():
            with open(example_path, "r") as f:
                cfg = yaml.safe_load(f) or {}
        else:
            cfg = {}
    else:
        with open(cfg_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    # Apply environment variable overrides (Railway style)
    _apply_env_overrides(cfg)

    return cfg


def _apply_env_overrides(cfg: Dict[str, Any]) -> None:
    """Apply environment variable overrides to config."""
    # API config (shared defaults)
    if os.environ.get("API_BASE_URL"):
        cfg.setdefault("api", {})["base_url"] = os.environ["API_BASE_URL"]
    if os.environ.get("API_KEY_PRIVATE_KEY"):
        cfg.setdefault("api", {})["key"] = os.environ["API_KEY_PRIVATE_KEY"]
    if os.environ.get("ACCOUNT_INDEX"):
        cfg.setdefault("api", {})["account_index"] = int(os.environ["ACCOUNT_INDEX"])
    if os.environ.get("API_KEY_INDEX"):
        cfg.setdefault("api", {})["api_key_index"] = int(os.environ["API_KEY_INDEX"])
    if os.environ.get("BASE_SCALE"):
        cfg.setdefault("api", {})["base_scale"] = os.environ["BASE_SCALE"]
    if os.environ.get("PRICE_SCALE"):
        cfg.setdefault("api", {})["price_scale"] = os.environ["PRICE_SCALE"]

    # RSI + BB (mean reversion) config
    if os.environ.get("MEAN_REVERSION_ENABLED"):
        cfg.setdefault("mean_reversion", {})["enabled"] = os.environ["MEAN_REVERSION_ENABLED"].lower() == "true"
    if os.environ.get("MEAN_REVERSION_DRY_RUN"):
        cfg.setdefault("mean_reversion", {})["dry_run"] = os.environ["MEAN_REVERSION_DRY_RUN"].lower() == "true"
    if os.environ.get("MEAN_REVERSION_MARKET"):
        cfg.setdefault("mean_reversion", {})["market"] = os.environ["MEAN_REVERSION_MARKET"]
    if os.environ.get("MEAN_REVERSION_CANDLE_INTERVAL_SECONDS"):
        cfg.setdefault("mean_reversion", {})["candle_interval_seconds"] = int(os.environ["MEAN_REVERSION_CANDLE_INTERVAL_SECONDS"])

    # RSI + BB per-strategy account config (optional, falls back to shared)
    if os.environ.get("MEAN_REVERSION_ACCOUNT_INDEX"):
        cfg.setdefault("mean_reversion", {}).setdefault("api", {})["account_index"] = int(os.environ["MEAN_REVERSION_ACCOUNT_INDEX"])
    if os.environ.get("MEAN_REVERSION_API_KEY_INDEX"):
        cfg.setdefault("mean_reversion", {}).setdefault("api", {})["api_key_index"] = int(os.environ["MEAN_REVERSION_API_KEY_INDEX"])
    if os.environ.get("MEAN_REVERSION_API_KEY_PRIVATE_KEY"):
        cfg.setdefault("mean_reversion", {}).setdefault("api", {})["key"] = os.environ["MEAN_REVERSION_API_KEY_PRIVATE_KEY"]

    # Renko + AO config
    if os.environ.get("RENKO_AO_ENABLED"):
        cfg.setdefault("renko_ao", {})["enabled"] = os.environ["RENKO_AO_ENABLED"].lower() == "true"
    if os.environ.get("RENKO_AO_DRY_RUN"):
        cfg.setdefault("renko_ao", {})["dry_run"] = os.environ["RENKO_AO_DRY_RUN"].lower() == "true"
    if os.environ.get("RENKO_AO_MARKET"):
        cfg.setdefault("renko_ao", {})["market"] = os.environ["RENKO_AO_MARKET"]

    # Renko + AO per-strategy account config (optional, falls back to shared)
    if os.environ.get("RENKO_AO_ACCOUNT_INDEX"):
        cfg.setdefault("renko_ao", {}).setdefault("api", {})["account_index"] = int(os.environ["RENKO_AO_ACCOUNT_INDEX"])
    if os.environ.get("RENKO_AO_API_KEY_INDEX"):
        cfg.setdefault("renko_ao", {}).setdefault("api", {})["api_key_index"] = int(os.environ["RENKO_AO_API_KEY_INDEX"])
    if os.environ.get("RENKO_AO_API_KEY_PRIVATE_KEY"):
        cfg.setdefault("renko_ao", {}).setdefault("api", {})["key"] = os.environ["RENKO_AO_API_KEY_PRIVATE_KEY"]


def setup_logging():
    """Setup logging configuration."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Check if running in Railway (or other cloud) - log to stdout only
    is_railway = os.environ.get("RAILWAY_ENVIRONMENT") is not None or os.environ.get("RAILWAY_PROJECT_ID") is not None

    handlers = [logging.StreamHandler(sys.stdout)]

    # Only log to file if running locally (not Railway)
    if not is_railway:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        from datetime import datetime
        log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        handlers.append(logging.FileHandler(log_file))
        LOG.info(f"Logging to {log_file}")
    else:
        LOG.info("Logging to stdout (Railway/cloud environment)")

    # Setup logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=handlers,
    )


async def main():
    """Main entry point."""
    setup_logging()
    cfg = load_config()

    LOG.info("Starting Lighter Trend Trader (RSI+BB & Renko+AO strategies)...")

    # Initialize state store
    state = StateStore()

    # Initialize PnL tracker (database-backed for high volume)
    pnl_tracker = PnLTracker(db_path=os.environ.get("PNL_DB_PATH", "pnl_trades.db"))
    LOG.info("PnL tracker initialized (database-backed for high volume)")

    # Helper function to create trading client from config
    def create_trading_client(strategy_api_cfg: Optional[Dict[str, Any]] = None) -> Optional[TradingClient]:
        """Create a TradingClient from config, with per-strategy overrides."""
        # Use strategy-specific config if provided, otherwise fall back to shared config
        api_cfg = strategy_api_cfg or cfg.get("api") or {}

        # If strategy has its own api config, merge with shared defaults
        if strategy_api_cfg:
            shared_api_cfg = cfg.get("api") or {}
            # Merge: strategy-specific overrides shared defaults
            merged_cfg = {**shared_api_cfg, **strategy_api_cfg}
            api_cfg = merged_cfg

        # Safety check: Warn if using same account as market maker bot
        account_index = api_cfg.get("account_index")
        if account_index == 366110:  # Known market maker bot account
            LOG.warning(
                "⚠️  WARNING: Using same account_index (366110) as market maker bot! "
                "This will cause order conflicts. Use a different account or API key."
            )

        if api_cfg.get("key") and account_index is not None:
            try:
                from decimal import Decimal
                # Get scales from config or use defaults
                # For SOL (market:2), base_scale should be 1000 (1 SOL = 1000 base units)
                base_scale = Decimal(str(api_cfg.get("base_scale", "1000")))
                price_scale = Decimal(str(api_cfg.get("price_scale", "1000")))

                trading_cfg = TradingConfig(
                    base_url=str(api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai")),
                    api_key_private_key=str(api_cfg.get("key", "")),
                    account_index=int(account_index),
                    api_key_index=int(api_cfg.get("api_key_index", 0)),
                    base_scale=base_scale,
                    price_scale=price_scale,
                    nonce_management=api_cfg.get("nonce_management"),
                    max_api_key_index=api_cfg.get("max_api_key_index"),
                )
                client = TradingClient(trading_cfg)
                LOG.info(f"Trading client initialized for account {account_index}, API key index {api_cfg.get('api_key_index', 0)}")
                return client
            except Exception as exc:
                LOG.warning(f"Failed to initialize trading client: {exc}")
                return None
        return None

    # Create shared trading client (for backward compatibility)
    shared_trading_client = create_trading_client()

    # Initialize RSI + BB (mean reversion) trader
    rsi_bb_trader: Optional[MeanReversionTrader] = None
    rsi_bb_cfg = cfg.get("mean_reversion") or {}
    if rsi_bb_cfg.get("enabled", False):
        try:
            # Use strategy-specific trading client if configured, otherwise use shared
            rsi_bb_api_cfg = rsi_bb_cfg.get("api")
            rsi_bb_trading_client = create_trading_client(rsi_bb_api_cfg) if rsi_bb_api_cfg else shared_trading_client

            rsi_bb_trader = MeanReversionTrader(
                config=cfg,
                state=state,
                trading_client=rsi_bb_trading_client,
                alert_manager=None,
                telemetry=None,
            )
            rsi_bb_trader.pnl_tracker = pnl_tracker  # Attach PnL tracker
            if rsi_bb_api_cfg:
                LOG.info(f"RSI + BB trader initialized with dedicated account {rsi_bb_api_cfg.get('account_index')}")
            else:
                LOG.info("RSI + BB trader initialized (using shared account)")
        except Exception as exc:
            LOG.exception(f"Failed to initialize RSI + BB trader: {exc}")
    else:
        LOG.info("RSI + BB trader disabled")

    # Initialize Renko + AO trader
    renko_ao_trader: Optional[RenkoAOTrader] = None
    renko_ao_cfg = cfg.get("renko_ao") or {}
    if renko_ao_cfg.get("enabled", False):
        try:
            # Use strategy-specific trading client if configured, otherwise use shared
            renko_ao_api_cfg = renko_ao_cfg.get("api")
            renko_ao_trading_client = create_trading_client(renko_ao_api_cfg) if renko_ao_api_cfg else shared_trading_client

            renko_ao_trader = RenkoAOTrader(
                config=cfg,
                state=state,
                trading_client=renko_ao_trading_client,
                alert_manager=None,
                telemetry=None,
            )
            renko_ao_trader.pnl_tracker = pnl_tracker  # Attach PnL tracker
            if renko_ao_api_cfg:
                LOG.info(f"Renko + AO trader initialized with dedicated account {renko_ao_api_cfg.get('account_index')}")
            else:
                LOG.info("Renko + AO trader initialized (using shared account)")
        except Exception as exc:
            LOG.exception(f"Failed to initialize Renko + AO trader: {exc}")
    else:
        LOG.info("Renko + AO trader disabled")

    if not rsi_bb_trader and not renko_ao_trader:
        LOG.error("No traders enabled! Enable at least one strategy in config.")
        sys.exit(1)

    # Initialize WebSocket price feed to update state with current prices
    # Use market from first enabled trader
    market = rsi_bb_cfg.get("market") or renko_ao_cfg.get("market") or "market:2"
    price_feed = WebSocketPriceFeed(
        config=cfg,
        state=state,
        market=market,
    )
    LOG.info(f"WebSocket price feed initialized for {market}")

    # Setup graceful shutdown
    stop_event = asyncio.Event()

    def signal_handler():
        LOG.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, signal_handler)
        except NotImplementedError:
            pass

    # Run traders and price feed in parallel
    tasks = [price_feed.run(), stop_event.wait()]

    if rsi_bb_trader:
        tasks.append(rsi_bb_trader.run())
    if renko_ao_trader:
        tasks.append(renko_ao_trader.run())

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        pass
    finally:
        LOG.info("Shutting down...")
        await price_feed.stop()
        if rsi_bb_trader:
            await rsi_bb_trader.stop()
        if renko_ao_trader:
            await renko_ao_trader.stop()
        # Close all trading clients
        clients_to_close = []
        if shared_trading_client:
            clients_to_close.append(shared_trading_client)
        if rsi_bb_trader and rsi_bb_trader.trading_client and rsi_bb_trader.trading_client != shared_trading_client:
            clients_to_close.append(rsi_bb_trader.trading_client)
        if renko_ao_trader and renko_ao_trader.trading_client and renko_ao_trader.trading_client != shared_trading_client:
            clients_to_close.append(renko_ao_trader.trading_client)

        for client in clients_to_close:
            try:
                await client.close()
            except Exception:
                pass
        pnl_tracker.close()  # Close database connection
        LOG.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)

