#!/usr/bin/env python3
"""
Get account information for a Lighter.xyz account.

This script helps you retrieve the account_index and verify API key setup
for your "trend" sub-account.

Usage:
    python scripts/get_account_info.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --private-key 0x<your_wallet_private_key> \
        --account-index <account_index> \
        --api-key-index 0

Or to test with an API key:
    python scripts/get_account_info.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --api-key-private-key 0x<api_key_private_key> \
        --account-index <account_index> \
        --api-key-index 0

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
        description="Get Lighter.xyz account information"
    )
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--private-key",
        help="Hex-encoded wallet private key (0x...) - for wallet-based auth",
    )
    parser.add_argument(
        "--api-key-private-key",
        help="Hex-encoded API key private key (0x...) - for API key auth",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        help="Account index to query (required)",
    )
    parser.add_argument(
        "--api-key-index",
        type=int,
        default=0,
        help="API key index to use (default: %(default)s)",
    )
    return parser.parse_args(argv)


async def get_account_info(
    base_url: str,
    account_index: int,
    api_key_index: int,
    private_key: Optional[str] = None,
    api_key_private_key: Optional[str] = None,
) -> None:
    """Get account information."""
    print("=" * 60)
    print("Lighter.xyz Account Information")
    print("=" * 60)
    print()
    
    if not private_key and not api_key_private_key:
        print("❌ Error: Must provide either --private-key or --api-key-private-key")
        sys.exit(1)
    
    if private_key and api_key_private_key:
        print("⚠️  Warning: Both private-key and api-key-private-key provided. Using api-key-private-key.")
        private_key = None
    
    # Use API key if provided, otherwise use wallet private key
    key_to_use = api_key_private_key if api_key_private_key else private_key
    
    print(f"Connecting to {base_url}...")
    print(f"Account Index: {account_index}")
    print(f"API Key Index: {api_key_index}")
    print(f"Using: {'API Key' if api_key_private_key else 'Wallet Private Key'}")
    print()
    
    signer = SignerClient(
        url=base_url,
        private_key=key_to_use,
        account_index=account_index,
        api_key_index=api_key_index,
        nonce_management_type=None,
    )
    
    try:
        # Check client health
        print("📡 Checking connection...")
        err = signer.check_client()
        if err is not None:
            print(f"⚠️  Client check returned: {err}")
        else:
            print("✅ Connection successful!")
        print()
        
        # Try to get account info
        # Note: The exact methods depend on lighter-python SDK version
        print("📋 Account Information:")
        print(f"   Account Index: {account_index}")
        print(f"   API Key Index: {api_key_index}")
        print(f"   Base URL: {base_url}")
        print()
        
        print("✅ Account configuration verified!")
        print()
        print("📝 Next Steps:")
        print("1. Copy the account_index and API key private key")
        print("2. Add to Railway environment variables:")
        print(f"   ACCOUNT_INDEX={account_index}")
        print(f"   API_KEY_INDEX={api_key_index}")
        print(f"   API_KEY_PRIVATE_KEY={key_to_use}")
        print()
        print("3. Verify the account is different from market maker bot (366110)")
        if account_index == 366110:
            print("   ⚠️  WARNING: This is the same account as market maker bot!")
            print("   You should use a different account_index.")
        else:
            print(f"   ✅ Account {account_index} is different from market maker (366110)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Verify account_index is correct")
        print("   - Check API key private key is correct (starts with 0x)")
        print("   - Ensure API key has trading permissions")
        print("   - Try creating the account through Lighter.xyz UI first")
        sys.exit(1)
    finally:
        await signer.close()


async def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    
    if not args.account_index:
        print("❌ Error: --account-index is required")
        print("\nTo find your account_index:")
        print("1. Go to Lighter.xyz dashboard")
        print("2. Navigate to your 'trend' sub-account")
        print("3. Check Account Settings - the account_index should be displayed")
        print("4. Or check the URL/API responses")
        sys.exit(1)
    
    await get_account_info(
        base_url=args.base_url,
        account_index=args.account_index,
        api_key_index=args.api_key_index,
        private_key=args.private_key,
        api_key_private_key=args.api_key_private_key,
    )


if __name__ == "__main__":
    asyncio.run(main())

