#!/usr/bin/env python3
"""
Manually recover an existing position for a strategy.

This script helps recover position state after a deploy that reset the bot's memory.
It queries the exchange for current positions and provides the information needed
to manually set the position in the bot, or you can use this to close the position.

Usage:
    python scripts/recover_position.py --strategy renko_ao --market market:2
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import lighter
    from lighter import SignerClient
except ImportError:
    print("ERROR: lighter-python not installed. Install via:")
    print('  pip install "git+https://github.com/elliottech/lighter-python.git"')
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("recover_position")


async def recover_position(
    account_index: int,
    api_key_index: int,
    api_key_private_key: str,
    market: str,
    base_url: str = "https://mainnet.zklighter.elliot.ai",
):
    """Recover position information from exchange."""
    LOG.info(f"Connecting to {base_url}...")
    LOG.info(f"Account: {account_index}, API Key: {api_key_index}")
    
    signer = SignerClient(
        url=base_url,
        private_key=api_key_private_key,
        account_index=account_index,
        api_key_index=api_key_index,
    )
    
    err = signer.check_client()
    if err:
        LOG.error(f"Signer client health check failed: {err}")
        return
    
    LOG.info("✓ Connected successfully")
    
    # Parse market
    if ":" not in market:
        LOG.error(f"Invalid market format: {market}. Expected format: market:2")
        return
    
    market_id = int(market.split(":")[1])
    LOG.info(f"Checking positions for market: {market} (ID: {market_id})")
    
    # Note: lighter-python may not have direct position query methods
    # This is a placeholder - you may need to check the UI or use WebSocket account_all channel
    LOG.warning("⚠️  Direct position query not available in lighter-python SDK")
    LOG.info("")
    LOG.info("To check your position:")
    LOG.info("1. Check the Lighter.xyz UI for your account positions")
    LOG.info("2. Or use the WebSocket account_all channel to subscribe to position updates")
    LOG.info("")
    LOG.info("If you have an open position:")
    LOG.info("- The bot will NOT manage it automatically after a deploy")
    LOG.info("- You should either:")
    LOG.info("  a) Manually close it in the UI if profitable")
    LOG.info("  b) Wait for the bot to take a new trade (it will then manage positions)")
    LOG.info("  c) Use the position recovery feature (if implemented)")
    
    await signer.close()


def main():
    parser = argparse.ArgumentParser(description="Recover position information")
    parser.add_argument("--account-index", type=int, required=True, help="Account index")
    parser.add_argument("--api-key-index", type=int, required=True, help="API key index")
    parser.add_argument("--api-key-private-key", type=str, required=True, help="API key private key")
    parser.add_argument("--market", type=str, default="market:2", help="Market (default: market:2)")
    parser.add_argument("--base-url", type=str, default="https://mainnet.zklighter.elliot.ai", help="Base URL")
    
    args = parser.parse_args()
    
    asyncio.run(
        recover_position(
            account_index=args.account_index,
            api_key_index=args.api_key_index,
            api_key_private_key=args.api_key_private_key,
            market=args.market,
            base_url=args.base_url,
        )
    )


if __name__ == "__main__":
    main()

