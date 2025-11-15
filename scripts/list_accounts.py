#!/usr/bin/env python3
"""
List all Lighter.xyz accounts/sub-accounts for a wallet address.

This script uses the accountsByL1Address API endpoint to retrieve all
sub-accounts associated with your Ethereum wallet, including the "trend" account.

Usage:
    python scripts/list_accounts.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --wallet-address 0x<your_ethereum_wallet_address>

Requirements:
    No special packages needed - uses standard HTTP requests
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional

import aiohttp


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List all Lighter.xyz accounts/sub-accounts for a wallet"
    )
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--wallet-address",
        required=True,
        help="Ethereum wallet address (0x...)",
    )
    return parser.parse_args(argv)


async def list_accounts(base_url: str, wallet_address: str) -> None:
    """List all accounts/sub-accounts for a wallet address."""
    print("=" * 60)
    print("Lighter.xyz Account Lister")
    print("=" * 60)
    print()
    print(f"Wallet Address: {wallet_address}")
    print(f"Base URL: {base_url}")
    print()
    
    # Try the accountsByL1Address endpoint
    # Based on: https://apidocs.lighter.xyz/docs/account-index
    endpoint = f"/api/v1/accountsByL1Address"
    url = f"{base_url.rstrip('/')}{endpoint}"
    
    params = {
        "l1Address": wallet_address.lower(),  # Ensure lowercase
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            print(f"📡 Querying: {endpoint}")
            print(f"   Params: l1Address={wallet_address}")
            print()
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("✅ Successfully retrieved account information!")
                    print()
                    
                    # Pretty print the response
                    print("📋 Account Data:")
                    print(json.dumps(data, indent=2))
                    print()
                    
                    # Try to extract sub-accounts
                    if isinstance(data, dict):
                        sub_accounts = data.get("sub_accounts", [])
                        if sub_accounts:
                            print(f"📊 Found {len(sub_accounts)} account(s):")
                            print()
                            
                            for idx, account in enumerate(sub_accounts):
                                account_index = account.get("account_index") or account.get("index") or account.get("id")
                                account_name = account.get("name") or account.get("label") or "Unnamed"
                                
                                print(f"  Account #{idx + 1}:")
                                print(f"    Name: {account_name}")
                                print(f"    Account Index: {account_index}")
                                print(f"    Full Data: {json.dumps(account, indent=6)}")
                                print()
                                
                                # Check if this is the "trend" account
                                if account_name.lower() == "trend" or "trend" in str(account).lower():
                                    print("  🎯 THIS IS YOUR 'TREND' ACCOUNT!")
                                    print(f"     Account Index: {account_index}")
                                    print()
                        else:
                            print("⚠️  No sub_accounts found in response")
                            print("   Response structure:")
                            print(json.dumps(data, indent=2))
                    elif isinstance(data, list):
                        print(f"📊 Found {len(data)} account(s) (list format):")
                        for idx, account in enumerate(data):
                            account_index = account.get("account_index") or account.get("index") or account.get("id")
                            account_name = account.get("name") or account.get("label") or "Unnamed"
                            print(f"  Account #{idx + 1}: {account_name} (index: {account_index})")
                            
                            if account_name.lower() == "trend" or "trend" in str(account).lower():
                                print("  🎯 THIS IS YOUR 'TREND' ACCOUNT!")
                                print(f"     Account Index: {account_index}")
                    else:
                        print("⚠️  Unexpected response format")
                        print(json.dumps(data, indent=2))
                    
                elif resp.status == 404:
                    print("❌ Endpoint not found (404)")
                    print("   The API endpoint might be different or require authentication")
                    print()
                    print("💡 Alternative: Check the Lighter.xyz dashboard for account_index")
                else:
                    text = await resp.text()
                    print(f"❌ Error: HTTP {resp.status}")
                    print(f"   Response: {text[:500]}")
                    print()
                    print("💡 Troubleshooting:")
                    print("   - Verify wallet address is correct")
                    print("   - Check if endpoint requires authentication")
                    print("   - Try checking Lighter.xyz dashboard instead")
                    
        except aiohttp.ClientError as e:
            print(f"❌ Network error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


async def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    
    # Validate wallet address format
    wallet = args.wallet_address.strip()
    if not wallet.startswith("0x") or len(wallet) != 42:
        print("❌ Error: Invalid wallet address format")
        print("   Expected: 0x followed by 40 hex characters")
        print(f"   Got: {wallet}")
        sys.exit(1)
    
    await list_accounts(
        base_url=args.base_url,
        wallet_address=wallet,
    )
    
    print()
    print("=" * 60)
    print("Next Steps:")
    print("1. Note the account_index for your 'trend' account")
    print("2. Generate an API key for that account in Lighter.xyz dashboard")
    print("3. Use those credentials in Railway environment variables")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

