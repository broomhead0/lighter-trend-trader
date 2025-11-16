#!/usr/bin/env python3
"""
Find the breakout account from ETH wallet private key.

This script lists all accounts and helps identify the breakout account.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

try:
    import eth_account
    import lighter
except ImportError as exc:
    print(
        "Error: lighter-python and eth-account packages not found. Install with:",
        "pip install 'git+https://github.com/elliottech/lighter-python.git' eth-account",
        file=sys.stderr,
    )
    sys.exit(1)


async def find_accounts(base_url: str, eth_private_key: str) -> None:
    """Find all accounts for the given ETH wallet."""
    print("=" * 60)
    print("Finding Accounts")
    print("=" * 60)
    print()

    # Get Ethereum address from private key
    eth_acc = eth_account.Account.from_key(eth_private_key)
    eth_address = eth_acc.address
    print(f"Ethereum Address: {eth_address}")
    print()

    # Find account(s) using accounts_by_l1_address
    print("📡 Querying Lighter API for accounts...")
    api_client = lighter.ApiClient(configuration=lighter.Configuration(host=base_url))

    try:
        response = await lighter.AccountApi(api_client).accounts_by_l1_address(
            l1_address=eth_address
        )
    except lighter.ApiException as e:
        if "account not found" in str(e.data.message).lower():
            print(f"❌ Error: Account not found for {eth_address}")
            print()
            print("💡 You may need to create an account first via the Lighter.xyz UI:")
            print("   https://app.lighter.xyz")
            return
        else:
            raise e

    # Display all accounts
    if len(response.sub_accounts) > 0:
        print(f"✅ Found {len(response.sub_accounts)} account(s):")
        print()
        for idx, sub_account in enumerate(response.sub_accounts):
            acc_idx = sub_account.index
            acc_name = getattr(sub_account, 'name', None) or f"Account {idx + 1}"
            print(f"   Account #{idx + 1}: {acc_name} (index: {acc_idx})")
        print()

        # Look for breakout account
        breakout_account = None
        for acc in response.sub_accounts:
            acc_name = getattr(acc, 'name', '').lower()
            if 'breakout' in acc_name:
                breakout_account = acc
                break

        if breakout_account:
            print("🎯 Found breakout account!")
            print(f"   Name: {getattr(breakout_account, 'name', 'N/A')}")
            print(f"   Index: {breakout_account.index}")
            print()
            print("📋 Use this account index for API key setup:")
            print(f"   python scripts/setup_api_key.py \\")
            print(f"       --eth-private-key {eth_private_key[:10]}... \\")
            print(f"       --account-index {breakout_account.index} \\")
            print(f"       --api-key-index 17")
        else:
            print("⚠️  No account named 'breakout' found.")
            print("   Please create a sub-account named 'breakout' in the Lighter.xyz UI:")
            print("   https://app.lighter.xyz")
            print()
            print("   Or use one of the existing accounts above.")
    else:
        print("❌ No accounts found!")
        print()
        print("💡 Create an account first via the Lighter.xyz UI:")
        print("   https://app.lighter.xyz")

    await api_client.close()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Find breakout account")
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--eth-private-key",
        required=True,
        help="Hex-encoded Ethereum wallet private key (0x...)",
    )
    args = parser.parse_args(argv)

    asyncio.run(find_accounts(args.base_url, args.eth_private_key))


if __name__ == "__main__":
    main()

