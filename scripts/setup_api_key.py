#!/usr/bin/env python3
"""
Setup API key for Lighter.xyz account.

Based on the official lighter-python example:
https://github.com/elliottech/lighter-python/blob/main/examples/system_setup.py

This script:
1. Finds your account(s) using your ETH_PRIVATE_KEY
2. Generates a new API key
3. Registers it on-chain
4. Returns the configuration you need

Usage:
    python scripts/setup_api_key.py \
        --eth-private-key 0x<your_wallet_private_key> \
        --api-key-index 16 \
        --account-index 16  # Optional: if you know it, otherwise will use first account

Requirements:
    pip install lighter-python eth-account
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
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


logging.basicConfig(level=logging.INFO)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Setup API key for Lighter.xyz account"
    )
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
    parser.add_argument(
        "--api-key-index",
        type=int,
        default=16,
        help="API key index to create (2-254, default: %(default)s)",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        help="Account index to use (optional: will find it if not provided)",
    )
    return parser.parse_args(argv)


async def setup_api_key(
    base_url: str,
    eth_private_key: str,
    api_key_index: int,
    account_index: Optional[int] = None,
) -> None:
    """Setup API key for Lighter account."""
    print("=" * 60)
    print("Lighter API Key Setup")
    print("=" * 60)
    print()
    print(f"Base URL: {base_url}")
    print(f"API Key Index: {api_key_index}")
    print()

    # Step 1: Get Ethereum address from private key
    print("📡 Step 1: Getting Ethereum address from private key...")
    eth_acc = eth_account.Account.from_key(eth_private_key)
    eth_address = eth_acc.address
    print(f"   Ethereum Address: {eth_address}")
    print()

    # Step 2: Find account(s) using accounts_by_l1_address
    print("📡 Step 2: Finding your account(s)...")
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

        # Use provided account_index or first account
        if account_index is None:
            account_index = response.sub_accounts[0].index
            print(f"📌 Using first account: index {account_index}")
        else:
            # Verify account_index exists
            found = any(acc.index == account_index for acc in response.sub_accounts)
            if not found:
                print(f"⚠️  Warning: Account index {account_index} not found in your accounts!")
                print(f"   Using first account instead: {response.sub_accounts[0].index}")
                account_index = response.sub_accounts[0].index
            else:
                print(f"📌 Using account index: {account_index}")
    else:
        print("❌ No accounts found!")
        return

    print()

    # Step 3: Generate new API key
    print("🔑 Step 3: Generating new API key...")
    private_key, public_key, err = lighter.create_api_key()
    if err is not None:
        raise Exception(f"Failed to create API key: {err}")

    print(f"   ✅ API key generated!")
    print(f"   Private Key: {private_key[:20]}...{private_key[-10:]}")
    print(f"   Public Key: {public_key[:20]}...{public_key[-10:]}")
    print()

    # Step 4: Register API key on-chain
    print("📤 Step 4: Registering API key on-chain...")
    print("   (This requires signing a transaction with your wallet)")
    print()

    tx_client = lighter.SignerClient(
        url=base_url,
        private_key=private_key,
        account_index=account_index,
        api_key_index=api_key_index,
    )

    try:
        # Change the API key (register it)
        response, err = await tx_client.change_api_key(
            eth_private_key=eth_private_key,
            new_pubkey=public_key,
        )
        if err is not None:
            raise Exception(f"Failed to register API key: {err}")

        print("✅ API key registration transaction sent!")
        print()
        print("⏳ Waiting 10 seconds for transaction to propagate...")
        time.sleep(10)

        # Step 5: Verify API key is registered
        print("🔍 Step 5: Verifying API key registration...")
        err = tx_client.check_client()
        if err is not None:
            print(f"⚠️  Warning: API key check returned: {err}")
            print("   The transaction may still be processing. Wait a bit longer and try again.")
            print()
            print("   You can verify manually by checking:")
            print(f"   - Account: {account_index}")
            print(f"   - API Key Index: {api_key_index}")
        else:
            print("✅ API key is registered and ready to use!")
            print()

    except Exception as e:
        print(f"❌ Error registering API key: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("💡 Troubleshooting:")
        print("   - Verify ETH_PRIVATE_KEY is correct")
        print("   - Check that you own the account")
        print("   - Ensure you have sufficient funds for gas")
        raise
    finally:
        await tx_client.close()
        await api_client.close()

    # Step 6: Output configuration
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print("📋 Add these to your Railway environment variables:")
    print()
    print(f"BASE_URL={base_url}")
    print(f"API_KEY_PRIVATE_KEY={private_key}")
    print(f"ACCOUNT_INDEX={account_index}")
    print(f"API_KEY_INDEX={api_key_index}")
    print()
    print("Or use this format:")
    print()
    print(f"BASE_URL = '{base_url}'")
    print(f"API_KEY_PRIVATE_KEY = '{private_key}'")
    print(f"ACCOUNT_INDEX = {account_index}")
    print(f"API_KEY_INDEX = {api_key_index}")
    print()


async def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    # Validate API key index
    if args.api_key_index < 2 or args.api_key_index > 254:
        print("❌ Error: API_KEY_INDEX must be between 2 and 254")
        print("   (0 and 1 are reserved for desktop/mobile)")
        sys.exit(1)

    await setup_api_key(
        base_url=args.base_url,
        eth_private_key=args.eth_private_key,
        api_key_index=args.api_key_index,
        account_index=args.account_index,
    )


if __name__ == "__main__":
    asyncio.run(main())

