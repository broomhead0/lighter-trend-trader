#!/usr/bin/env python3
"""
Test placing an order to verify API key setup is working.

This script places a small test order (post-only, unlikely to fill) and then cancels it.

Usage:
    python scripts/test_order.py \
        --base-url https://mainnet.zklighter.elliot.ai \
        --account-index 281474976639501 \
        --api-key-index 16 \
        --api-key-private-key 0x<your_api_key_private_key>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal

try:
    import lighter
except ImportError as exc:
    print(
        "Error: lighter-python package not found. Install with:",
        "pip install 'git+https://github.com/elliottech/lighter-python.git'",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Test placing an order")
    parser.add_argument(
        "--base-url",
        default="https://mainnet.zklighter.elliot.ai",
        help="Lighter API base URL",
    )
    parser.add_argument(
        "--account-index",
        type=int,
        required=True,
        help="Account index",
    )
    parser.add_argument(
        "--api-key-index",
        type=int,
        required=True,
        help="API key index",
    )
    parser.add_argument(
        "--api-key-private-key",
        required=True,
        help="API key private key (0x...)",
    )
    parser.add_argument(
        "--market",
        default="market:2",
        help="Market to trade (default: market:2 for SOL)",
    )
    return parser.parse_args()


async def test_order():
    args = parse_args()

    print("=" * 60)
    print("Order Placement Test")
    print("=" * 60)
    print()
    print(f"Account Index: {args.account_index}")
    print(f"API Key Index: {args.api_key_index}")
    print(f"Market: {args.market}")
    print()

    # Initialize SignerClient
    print("📡 Step 1: Initializing SignerClient...")
    client = lighter.SignerClient(
        url=args.base_url,
        private_key=args.api_key_private_key,
        account_index=args.account_index,
        api_key_index=args.api_key_index,
    )

    try:
        # Check client health
        print("🔍 Step 2: Checking API key...")
        err = client.check_client()
        if err is not None:
            print(f"❌ API key check failed: {err}")
            sys.exit(1)
        print("✅ API key is valid!")
        print()

        # Get current market price (we'll use a safe price far from market)
        print("📊 Step 3: Getting market data...")
        api_client = lighter.ApiClient(configuration=lighter.Configuration(host=args.base_url))
        order_api = lighter.OrderApi(api_client)

        try:
            # Get orderbook to find current price
            market_id = int(args.market.split(":")[1])
            orderbook = await order_api.order_book_details(market_id=market_id)

            # Get mid price
            if orderbook.bids and orderbook.asks:
                best_bid = float(orderbook.bids[0].price) / 1000.0  # Assuming price_scale=1000
                best_ask = float(orderbook.asks[0].price) / 1000.0
                mid_price = (best_bid + best_ask) / 2.0
                print(f"   Current market: bid={best_bid:.2f}, ask={best_ask:.2f}, mid={mid_price:.2f}")
            else:
                # Fallback: use a reasonable price for SOL
                mid_price = 142.0
                print(f"   Using fallback price: {mid_price:.2f}")
        except Exception as e:
            print(f"   ⚠️  Could not get market data: {e}")
            print(f"   Using fallback price: 142.0")
            mid_price = 142.0

        print()

        # Place a test order (post-only, very small size, far from market)
        # We'll place a bid order 5% below market (very unlikely to fill)
        test_price = mid_price * 0.95  # 5% below market
        test_size = 0.001  # Very small size (0.001 SOL)

        print("📤 Step 4: Placing test order...")
        print(f"   Side: BID (buy)")
        print(f"   Price: {test_price:.2f} (5% below market)")
        print(f"   Size: {test_size} SOL")
        print(f"   Type: POST_ONLY (won't fill immediately)")
        print()

        # Scale price and size (assuming price_scale=1000, base_scale=1000000)
        price_units = int(test_price * 1000)
        base_units = int(test_size * 1000000)

        # Generate unique client_order_index
        import time
        client_order_index = int(time.time() * 1000)

        # Place the order
        market_index = int(args.market.split(":")[1])
        result = await client.create_order(
            market_index=market_index,
            is_ask=False,  # False = bid (buy), True = ask (sell)
            order_type=client.ORDER_TYPE_LIMIT,
            base_amount=base_units,
            price=price_units,
            client_order_index=client_order_index,
            time_in_force=client.ORDER_TIME_IN_FORCE_POST_ONLY,
        )

        # Handle different return formats
        if isinstance(result, tuple):
            if len(result) == 2:
                order_response, err = result
                if err is not None:
                    print(f"❌ Failed to place order: {err}")
                    sys.exit(1)
            elif len(result) == 3:
                tx, tx_hash, err = result
                if err is not None:
                    print(f"❌ Failed to place order: {err}")
                    sys.exit(1)
                order_response = type('obj', (object,), {'order_index': client_order_index, 'tx_hash': tx_hash})()
            else:
                order_response = result[0] if result else None
        else:
            order_response = result

        print("✅ Order placed successfully!")
        order_index = getattr(order_response, 'order_index', client_order_index)
        tx_hash = getattr(order_response, 'tx_hash', getattr(order_response, 'hash', 'N/A'))
        print(f"   Order Index: {order_index}")
        print(f"   Client Order Index: {client_order_index}")
        print(f"   Transaction Hash: {tx_hash}")
        print()

        # Wait a moment
        print("⏳ Waiting 2 seconds...")
        await asyncio.sleep(2)

        # Cancel the test order
        print("🗑️  Step 5: Canceling test order...")
        cancel_result = await client.cancel_order(
            market_index=market_index,
            order_index=order_index,
        )

        # Handle different return formats
        if isinstance(cancel_result, tuple):
            if len(cancel_result) == 2:
                cancel_response, err = cancel_result
                if err is not None:
                    print(f"⚠️  Warning: Failed to cancel order: {err}")
                    print("   You may need to cancel it manually in the UI")
                else:
                    tx_hash = getattr(cancel_response, 'tx_hash', getattr(cancel_response, 'hash', 'N/A'))
                    print("✅ Order canceled successfully!")
                    print(f"   Cancel Transaction Hash: {tx_hash}")
            elif len(cancel_result) == 3:
                tx, tx_hash, err = cancel_result
                if err is not None:
                    print(f"⚠️  Warning: Failed to cancel order: {err}")
                    print("   You may need to cancel it manually in the UI")
                else:
                    print("✅ Order canceled successfully!")
                    print(f"   Cancel Transaction Hash: {tx_hash}")
            else:
                print("✅ Cancel request sent!")
        else:
            print("✅ Cancel request sent!")
        print()

        print("=" * 60)
        print("✅ Test Complete!")
        print("=" * 60)
        print()
        print("Your API key is working correctly and can place orders!")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await client.close()
        try:
            await api_client.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_order())

