#!/usr/bin/env python3
"""Quick test script to verify bot setup."""
import asyncio
import sys
import yaml
from pathlib import Path

async def test_setup():
    """Test that all components can be imported and initialized."""
    print("Testing Lighter Trend Trader setup...\n")
    
    # Test 1: Imports
    print("1. Testing imports...")
    try:
        from core.state_store import StateStore
        from core.trading_client import TradingClient, TradingConfig
        from modules.mean_reversion_trader import MeanReversionTrader
        from modules.price_feed import PriceFeed
        print("   ✓ All imports successful\n")
    except Exception as e:
        print(f"   ✗ Import failed: {e}\n")
        return False
    
    # Test 2: Config loading
    print("2. Testing config loading...")
    try:
        cfg_path = Path("config.yaml")
        if not cfg_path.exists():
            print("   ✗ config.yaml not found\n")
            return False
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        if cfg.get("mean_reversion", {}).get("enabled"):
            print("   ✓ Config loaded, mean_reversion enabled\n")
        else:
            print("   ⚠ Config loaded but mean_reversion not enabled\n")
    except Exception as e:
        print(f"   ✗ Config load failed: {e}\n")
        return False
    
    # Test 3: State store
    print("3. Testing state store...")
    try:
        state = StateStore()
        state.update_mid("market:2", 150.0)
        price = state.get_mid("market:2")
        if price == 150.0:
            print("   ✓ State store works\n")
        else:
            print(f"   ✗ State store issue: expected 150.0, got {price}\n")
            return False
    except Exception as e:
        print(f"   ✗ State store failed: {e}\n")
        return False
    
    # Test 4: Price feed initialization
    print("4. Testing price feed initialization...")
    try:
        feed = PriceFeed(cfg, state, "market:2", 5.0)
        print("   ✓ Price feed initialized\n")
    except Exception as e:
        print(f"   ✗ Price feed init failed: {e}\n")
        return False
    
    # Test 5: Trader initialization
    print("5. Testing trader initialization...")
    try:
        trader = MeanReversionTrader(
            config=cfg,
            state=state,
            trading_client=None,  # No trading client for test
            alert_manager=None,
            telemetry=None,
        )
        print("   ✓ Trader initialized\n")
    except Exception as e:
        print(f"   ✗ Trader init failed: {e}\n")
        return False
    
    # Test 6: API connectivity (optional)
    print("6. Testing API connectivity...")
    try:
        import aiohttp
        api_url = cfg.get("api", {}).get("base_url", "https://mainnet.zklighter.elliot.ai")
        url = f"{api_url}/public/markets/2/candles"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"interval": "1m", "limit": 1}, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("candles"):
                        print("   ✓ API connectivity works\n")
                    else:
                        print("   ⚠ API responded but no candles\n")
                else:
                    print(f"   ⚠ API returned status {resp.status}\n")
    except Exception as e:
        print(f"   ⚠ API test failed (may be network issue): {e}\n")
    
    print("✓ All basic tests passed! Bot is ready to run.")
    print("\nNext step: Run 'python main.py' to start the bot in dry-run mode.")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_setup())
    sys.exit(0 if success else 1)

