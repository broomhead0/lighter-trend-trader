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
from modules.breakout_trader import BreakoutTrader
from modules.ws_price_feed import WebSocketPriceFeed
from modules.pnl_tracker import PnLTracker
from modules.position_tracker import PositionTracker
from modules.candle_tracker import CandleTracker
from modules.renko_tracker import RenkoTracker

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

    # Breakout strategy config
    if os.environ.get("BREAKOUT_ENABLED"):
        cfg.setdefault("breakout", {})["enabled"] = os.environ["BREAKOUT_ENABLED"].lower() == "true"
    if os.environ.get("BREAKOUT_DRY_RUN"):
        cfg.setdefault("breakout", {})["dry_run"] = os.environ["BREAKOUT_DRY_RUN"].lower() == "true"
    if os.environ.get("BREAKOUT_MARKET"):
        cfg.setdefault("breakout", {})["market"] = os.environ["BREAKOUT_MARKET"]
    if os.environ.get("BREAKOUT_CANDLE_INTERVAL_SECONDS"):
        cfg.setdefault("breakout", {})["candle_interval_seconds"] = int(os.environ["BREAKOUT_CANDLE_INTERVAL_SECONDS"])

    # Breakout per-strategy account config (optional, falls back to shared)
    if os.environ.get("BREAKOUT_ACCOUNT_INDEX"):
        cfg.setdefault("breakout", {}).setdefault("api", {})["account_index"] = int(os.environ["BREAKOUT_ACCOUNT_INDEX"])
    if os.environ.get("BREAKOUT_API_KEY_INDEX"):
        cfg.setdefault("breakout", {}).setdefault("api", {})["api_key_index"] = int(os.environ["BREAKOUT_API_KEY_INDEX"])
    if os.environ.get("BREAKOUT_API_KEY_PRIVATE_KEY"):
        cfg.setdefault("breakout", {}).setdefault("api", {})["key"] = os.environ["BREAKOUT_API_KEY_PRIVATE_KEY"]


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
    # Use persistent path: Check for Railway volume, then fallback to local
    pnl_db_path = os.environ.get("PNL_DB_PATH")
    if pnl_db_path:
        # PNL_DB_PATH is explicitly set - use it (volume should be mounted)
        # Ensure directory exists
        db_dir = os.path.dirname(pnl_db_path)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
                # Verify directory is writable
                test_file = os.path.join(db_dir, ".test_write")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                LOG.warning(f"✅ Using PNL_DB_PATH from environment: {pnl_db_path} (directory exists and is writable)")
            except Exception as e:
                LOG.error(f"❌ CRITICAL: Cannot write to {db_dir}: {e}")
                LOG.error(f"❌ Falling back to /tmp (NOT PERSISTENT)")
                pnl_db_path = "/tmp/pnl_trades.db"
                os.makedirs("/tmp", exist_ok=True)
        else:
            LOG.warning(f"Using PNL_DB_PATH from environment: {pnl_db_path}")
    else:
        # Try multiple persistent locations
        # Railway volumes might be at /data, /persist (these are persistent)
        # /tmp is NOT persistent on Railway, so we avoid it
        for path in ["/data", "/persist"]:
            if os.path.exists(path):
                pnl_db_path = os.path.join(path, "pnl_trades.db")
                os.makedirs(path, exist_ok=True)
                LOG.info(f"Using persistent volume: {path}")
                break
        else:
            # If no persistent volume found, use /tmp as fallback (but warn)
            # Note: /tmp is NOT persistent on Railway, data will be lost on deploy
            pnl_db_path = "/tmp/pnl_trades.db"
            os.makedirs("/tmp", exist_ok=True)
            LOG.warning("⚠️ WARNING: Using /tmp for database (NOT PERSISTENT on Railway). Set PNL_DB_PATH env var or mount a volume at /data or /persist")

    # CRITICAL: Log database path and verify it exists
    LOG.warning("=" * 80)
    LOG.warning("DATABASE INITIALIZATION")
    LOG.warning("=" * 80)
    LOG.warning(f"🔍 DATABASE PATH: {pnl_db_path}")
    LOG.warning(f"🔍 Database directory: {os.path.dirname(pnl_db_path)}")
    LOG.warning(f"🔍 Directory exists: {os.path.exists(os.path.dirname(pnl_db_path))}")
    LOG.warning(f"🔍 Database file exists: {os.path.exists(pnl_db_path)}")
    if os.path.exists(pnl_db_path):
        file_size = os.path.getsize(pnl_db_path)
        LOG.warning(f"🔍 Database file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        # Check WAL file too
        wal_path = pnl_db_path + "-wal"
        if os.path.exists(wal_path):
            wal_size = os.path.getsize(wal_path)
            LOG.warning(f"🔍 WAL file size: {wal_size:,} bytes ({wal_size / 1024 / 1024:.2f} MB)")
    else:
        LOG.warning(f"🔍 Database file will be created on first write")
    LOG.warning("=" * 80)

    pnl_tracker = PnLTracker(db_path=pnl_db_path)
    LOG.info(f"PnL tracker initialized: {pnl_db_path} (database-backed for high volume)")

    # Initialize position tracker (uses same database)
    position_tracker = PositionTracker(db_path=pnl_db_path)
    LOG.info(f"Position tracker initialized: {pnl_db_path} (persists positions across deploys)")

    # Initialize candle tracker (uses same database)
    candle_tracker = CandleTracker(db_path=pnl_db_path)
    LOG.info(f"Candle tracker initialized: {pnl_db_path} (persists candles across deploys)")

    # Initialize Renko tracker (uses same database)
    renko_tracker = RenkoTracker(db_path=pnl_db_path)
    LOG.info(f"Renko tracker initialized: {pnl_db_path} (persists bricks and price history across deploys)")

    # Initialize backup if configured
    backup_config = cfg.get("pnl_backup") or {}
    if backup_config.get("enabled", False):
        from modules.pnl_backup import PnLBackup
        pnl_backup = PnLBackup(pnl_db_path, backup_config)
        LOG.info("PnL backup enabled")
    else:
        pnl_backup = None
        LOG.info("PnL backup disabled (set pnl_backup.enabled=true in config to enable)")

    # Analyze database size BEFORE cleanup
    try:
        from modules.db_cleanup import analyze_database_size
        LOG.warning("=" * 80)
        LOG.warning("DATABASE SIZE ANALYSIS (BEFORE CLEANUP)")
        LOG.warning("=" * 80)
        analysis = analyze_database_size(pnl_db_path)

        total_db_size = analysis["db_file_size"] + analysis["wal_file_size"] + analysis["shm_file_size"]
        LOG.warning(f"Database files: {total_db_size:,} bytes ({total_db_size / 1024 / 1024:.2f} MB)")
        LOG.warning(f"  Main DB: {analysis['db_file_size']:,} bytes ({analysis['db_file_size'] / 1024 / 1024:.2f} MB)")
        if analysis["wal_file_size"] > 0:
            LOG.warning(f"  WAL: {analysis['wal_file_size']:,} bytes ({analysis['wal_file_size'] / 1024 / 1024:.2f} MB)")
        if analysis["shm_file_size"] > 0:
            LOG.warning(f"  SHM: {analysis['shm_file_size']:,} bytes ({analysis['shm_file_size'] / 1024 / 1024:.2f} MB)")

        if analysis["backup_count"] > 0:
            LOG.warning(f"Backup files: {analysis['backup_dir_size']:,} bytes ({analysis['backup_dir_size'] / 1024 / 1024:.2f} MB) in {analysis['backup_count']} files")

        LOG.warning(f"Total accounted: {(total_db_size + analysis['backup_dir_size']):,} bytes ({(total_db_size + analysis['backup_dir_size']) / 1024 / 1024:.2f} MB)")
        LOG.warning(f"Railway reports: 67 MB")
        LOG.warning(f"Unaccounted: {(67 * 1024 * 1024) - (total_db_size + analysis['backup_dir_size']):,} bytes ({(67 * 1024 * 1024 - total_db_size - analysis['backup_dir_size']) / 1024 / 1024:.2f} MB)")
        LOG.warning("")

        LOG.warning("Table row counts:")
        for table, count in analysis["table_counts"].items():
            LOG.warning(f"  {table:20} {count:>10,} rows")

        if "price_history_by_strategy" in analysis:
            LOG.warning("")
            LOG.warning("Price history breakdown (⚠️  Main space consumer):")
            for key, count in analysis["price_history_by_strategy"].items():
                size_est = count * 50
                LOG.warning(f"  {key:30} {count:>10,} prices  ~{size_est / 1024 / 1024:.2f} MB")

        if "candles_by_strategy" in analysis:
            LOG.warning("")
            LOG.warning("Candles breakdown:")
            for key, count in analysis["candles_by_strategy"].items():
                size_est = count * 100
                LOG.warning(f"  {key:30} {count:>10,} candles  ~{size_est / 1024 / 1024:.2f} MB")

        # List ALL files on volume
        if "all_files" in analysis and analysis["all_files"]:
            LOG.warning("")
            LOG.warning("ALL FILES ON VOLUME (sorted by size):")
            total_file_size = 0
            for file_info in analysis["all_files"]:
                size = file_info["size"]
                total_file_size += size
                LOG.warning(f"  {file_info['path']:60} {size:>12,} bytes ({size / 1024 / 1024:>6.2f} MB)")
            LOG.warning(f"  {'TOTAL FILES':60} {total_file_size:>12,} bytes ({total_file_size / 1024 / 1024:>6.2f} MB)")
            LOG.warning("")
            LOG.warning(f"Railway reports: 67 MB")
            LOG.warning(f"Files found: {total_file_size / 1024 / 1024:.2f} MB")
            LOG.warning(f"Difference: {(67 * 1024 * 1024 - total_file_size) / 1024 / 1024:.2f} MB (Railway overhead/metadata)")

        LOG.warning("=" * 80)
    except Exception as e:
        LOG.warning(f"[db_analysis] Analysis failed: {e}")

    # Run database cleanup on startup (clean old data, checkpoint WAL)
    try:
        from modules.db_cleanup import cleanup_old_data
        LOG.info("Running database cleanup...")
        cleanup_stats = cleanup_old_data(pnl_db_path, dry_run=False)
        if cleanup_stats["price_history_deleted"] > 0 or cleanup_stats["candles_deleted"] > 0:
            LOG.warning(f"[db_cleanup] Cleaned up: {cleanup_stats['price_history_deleted']} price points, {cleanup_stats['candles_deleted']} candles")
        if cleanup_stats["wal_checkpointed"]:
            LOG.info("[db_cleanup] WAL file checkpointed (reduced size)")
        if cleanup_stats["vacuumed"]:
            LOG.info("[db_cleanup] Database vacuumed (reclaimed space)")
        if cleanup_stats["errors"]:
            for error in cleanup_stats["errors"]:
                LOG.warning(f"[db_cleanup] Error: {error}")
    except Exception as e:
        LOG.warning(f"[db_cleanup] Cleanup failed (non-critical): {e}")

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

                api_key = str(api_cfg.get("key", ""))
                # Debug: Check key length (should be 66 chars: 0x + 64 hex)
                key_len = len(api_key)
                if key_len < 66:
                    LOG.error(f"⚠️  API key for account {account_index} is too short: {key_len} chars (expected 66). Key starts with: {api_key[:20]}...")
                    LOG.error(f"   This will cause 'invalid private key length' errors. Check Railway variables.")
                    return None

                trading_cfg = TradingConfig(
                    base_url=str(api_cfg.get("base_url", "https://mainnet.zklighter.elliot.ai")),
                    api_key_private_key=api_key,
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
            rsi_bb_trader.position_tracker = position_tracker  # Attach position tracker
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
            renko_ao_trader.position_tracker = position_tracker  # Attach position tracker
            renko_ao_trader.renko_tracker = renko_tracker  # Attach Renko tracker
            if renko_ao_api_cfg:
                LOG.info(f"Renko + AO trader initialized with dedicated account {renko_ao_api_cfg.get('account_index')}")
            else:
                LOG.info("Renko + AO trader initialized (using shared account)")
        except Exception as exc:
            LOG.exception(f"Failed to initialize Renko + AO trader: {exc}")
    else:
        LOG.info("Renko + AO trader disabled")

    # Initialize Breakout trader
    breakout_trader: Optional[BreakoutTrader] = None
    breakout_cfg = cfg.get("breakout") or {}
    if breakout_cfg.get("enabled", False):
        try:
            # Use strategy-specific trading client if configured, otherwise use shared
            breakout_api_cfg = breakout_cfg.get("api")
            breakout_trading_client = create_trading_client(breakout_api_cfg) if breakout_api_cfg else shared_trading_client

            breakout_trader = BreakoutTrader(
                config=cfg,
                state=state,
                trading_client=breakout_trading_client,
                alert_manager=None,
                telemetry=None,
            )
            breakout_trader.pnl_tracker = pnl_tracker  # Attach PnL tracker
            breakout_trader.position_tracker = position_tracker  # Attach position tracker
            breakout_trader.candle_tracker = candle_tracker  # Attach candle tracker
            if breakout_api_cfg:
                LOG.info(f"Breakout trader initialized with dedicated account {breakout_api_cfg.get('account_index')}")
            else:
                LOG.info("Breakout trader initialized (using shared account)")
        except Exception as exc:
            LOG.exception(f"Failed to initialize Breakout trader: {exc}")
    else:
        LOG.info("Breakout trader disabled")

    if not rsi_bb_trader and not renko_ao_trader and not breakout_trader:
        LOG.error("No traders enabled! Enable at least one strategy in config.")
        sys.exit(1)

    # Initialize WebSocket price feed to update state with current prices
    # Use market from first enabled trader
    market = rsi_bb_cfg.get("market") or renko_ao_cfg.get("market") or breakout_cfg.get("market") or "market:2"
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

    # Periodic backup task
    async def backup_loop():
        """Periodic backup of PnL database."""
        if pnl_backup:
            while not stop_event.is_set():
                await pnl_backup.backup()
                await asyncio.sleep(300)  # Check every 5 minutes

    # Run traders and price feed in parallel
    tasks = [price_feed.run(), stop_event.wait()]

    if rsi_bb_trader:
        tasks.append(rsi_bb_trader.run())
    if renko_ao_trader:
        tasks.append(renko_ao_trader.run())
    if breakout_trader:
        tasks.append(breakout_trader.run())

    if pnl_backup:
        tasks.append(backup_loop())

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
        if breakout_trader:
            await breakout_trader.stop()
        # Close all trading clients
        clients_to_close = []
        if shared_trading_client:
            clients_to_close.append(shared_trading_client)
        if rsi_bb_trader and rsi_bb_trader.trading_client and rsi_bb_trader.trading_client != shared_trading_client:
            clients_to_close.append(rsi_bb_trader.trading_client)
        if renko_ao_trader and renko_ao_trader.trading_client and renko_ao_trader.trading_client != shared_trading_client:
            clients_to_close.append(renko_ao_trader.trading_client)
        if breakout_trader and breakout_trader.trading_client and breakout_trader.trading_client != shared_trading_client:
            clients_to_close.append(breakout_trader.trading_client)

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

