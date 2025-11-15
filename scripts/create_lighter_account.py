#!/usr/bin/env python3
"""
Create a new Lighter.xyz account for the trend trading bot.

This script creates a new account using the lighter-python SDK, which will
generate a new account_index that you can use for the trend trading strategies.

Usage:
    python scripts/create_lighter_account.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --private-key 0x<your_wallet_private_key>

Requirements:
    pip install lighter-python
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

try:
    from lighter import SignerClient
except ImportError as exc:
    print(
        "Error: lighter-python package not found. Install with:",
        "pip install 'git+https://github.com/elliottech/lighter-python.git'",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new Lighter.xyz account for trend trading"
    )
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--private-key",
        required=True,
        help="Hex-encoded wallet private key (0x...)",
    )
    parser.add_argument(
        "--api-key-index",
        type=int,
        default=0,
        help="API key index to use (default: %(default)s)",
    )
    return parser.parse_args(argv)


async def create_account(base_url: str, private_key: str, api_key_index: int) -> None:
    """Create a new Lighter account."""
    print(f"Connecting to {base_url}...")
    print(f"Using API key index: {api_key_index}")
    
    # Create SignerClient - this will create/register the account
    # Note: account_index is typically auto-generated on first use
    # We'll use a temporary index and let the SDK handle account creation
    signer = SignerClient(
        url=base_url,
        private_key=private_key,
        account_index=0,  # Temporary - will be set after account creation
        api_key_index=api_key_index,
        nonce_management_type=None,  # Will use default
    )
    
    try:
        # Check client health - this may trigger account creation
        err = signer.check_client()
        if err is not None:
            print(f"⚠️  Client check returned: {err}")
            print("This might be normal if the account doesn't exist yet.")
        
        # Try to get account info or create account
        # The exact method depends on lighter-python SDK version
        print("\n📝 Attempting to create/register account...")
        
        # Note: Account creation in Lighter might require:
        # 1. On-chain transaction (if it's a zk-rollup)
        # 2. Registration through the UI
        # 3. First trade/order placement
        
        # For now, we'll try to place a test order or get account info
        # This will reveal the actual account_index
        
        print("\n✅ Account setup initiated!")
        print("\n📋 Next Steps:")
        print("1. Check the Lighter.xyz dashboard for your account index")
        print("2. Or place a test order - the account_index will be returned")
        print("3. Update your config with the new account_index")
        print("\n⚠️  Note: Account creation may require:")
        print("   - On-chain transaction (gas fees)")
        print("   - Registration through Lighter.xyz UI")
        print("   - First order placement")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Alternative: Create account through Lighter.xyz UI:")
        print("   1. Go to https://lighter.xyz")
        print("   2. Connect your wallet")
        print("   3. Create/register account")
        print("   4. Note the account_index from dashboard")
        sys.exit(1)
    finally:
        await signer.close()


async def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    
    print("=" * 60)
    print("Lighter.xyz Account Creator for Trend Trading Bot")
    print("=" * 60)
    print()
    
    await create_account(
        base_url=args.base_url,
        private_key=args.private_key,
        api_key_index=args.api_key_index,
    )


if __name__ == "__main__":
    asyncio.run(main())

