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

LOG = logging.getLogger("main")


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    cfg_path = os.environ.get("LIGHTER_CONFIG", "config.yaml")
    if not Path(cfg_path).exists():
        LOG.error(f"Config file not found: {cfg_path}")
        sys.exit(1)
    
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def setup_logging():
    """Setup logging configuration."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )


async def main():
    """Main entry point."""
    setup_logging()
    cfg = load_config()
    
    LOG.info("Starting Lighter Trend Trader...")
    
    # Initialize state store
    state = StateStore()
    
    # Initialize trading client if configured
    trading_client: Optional[TradingClient] = None
    api_cfg = cfg.get("api") or {}
    if api_cfg.get("key") and api_cfg.get("account_index") is not None:
        try:
            from decimal import Decimal
            trading_cfg = TradingConfig(
                base_url=str(api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai")),
                api_key_private_key=str(api_cfg.get("key", "")),
                account_index=int(api_cfg.get("account_index", 0)),
                api_key_index=int(api_cfg.get("api_key_index", 0)),
                base_scale=Decimal("1000000"),  # Default scaling
                price_scale=Decimal("1000"),  # Default scaling
                nonce_management=api_cfg.get("nonce_management"),
                max_api_key_index=api_cfg.get("max_api_key_index"),
            )
            trading_client = TradingClient(trading_cfg)
            LOG.info("Trading client initialized")
        except Exception as exc:
            LOG.warning(f"Failed to initialize trading client: {exc}")
    
    # Initialize mean reversion trader
    trader_cfg = cfg.get("mean_reversion") or {}
    if not trader_cfg.get("enabled", False):
        LOG.error("Mean reversion trader is not enabled in config")
        sys.exit(1)
    
    try:
        trader = MeanReversionTrader(
            config=cfg,
            state=state,
            trading_client=trading_client,
            alert_manager=None,  # Optional
            telemetry=None,  # Optional
        )
        LOG.info("Mean reversion trader initialized")
    except Exception as exc:
        LOG.exception(f"Failed to initialize trader: {exc}")
        sys.exit(1)
    
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
    
    # Run trader
    try:
        await asyncio.gather(
            trader.run(),
            stop_event.wait(),
            return_exceptions=True,
        )
    except KeyboardInterrupt:
        pass
    finally:
        LOG.info("Shutting down...")
        await trader.stop()
        if trading_client:
            try:
                await trading_client.close()
            except Exception:
                pass
        LOG.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)

