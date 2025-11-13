# Lighter Trend Trader

A mean reversion trading bot for SOL on Lighter.xyz, designed to profit from short-term price reversions on 1-minute timeframes.

## Strategy Overview

The bot uses a **mean reversion strategy** that:
- Identifies overextended price moves using Bollinger Bands and RSI
- Filters trades by volatility (moderate vol only - avoids extreme conditions)
- Uses volume confirmation for entry signals
- Quick entries/exits (target 2-5 bps profit, stop at 4-8 bps loss)
- Position sizing based on ATR (volatility-adjusted)

## Features

- **Technical Indicators**: Bollinger Bands, RSI, EMA, ATR, Volume MA
- **Smart Filters**: Volatility filtering, trend avoidance, volume confirmation
- **Risk Management**: Stop loss, take profit, time-based exits
- **Real-time Trading**: Fetches 1-minute candles and executes trades
- **Dry Run Mode**: Test strategy without risking capital

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/lighter-trend-trader.git
cd lighter-trend-trader

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy the example config:
```bash
cp config.yaml.example config.yaml
```

2. Edit `config.yaml`:
```yaml
api:
  base_url: https://mainnet.zklighter.elliot.ai
  key: YOUR_API_KEY_PRIVATE_KEY
  account_index: YOUR_ACCOUNT_INDEX
  api_key_index: YOUR_API_KEY_INDEX

mean_reversion:
  enabled: true
  dry_run: true  # Start with dry_run=true for testing
  market: market:2  # SOL market
```

### Run

```bash
export PYTHONPATH=.
python -m main
```

## Strategy Details

### Entry Signals

**Long Entry:**
- Price touches/extends beyond lower Bollinger Band (95% threshold)
- RSI < 30 (oversold)
- Volume > 1.2x average volume
- Volatility between 4-25 bps
- No strong trend (EMA divergence < 15 bps)

**Short Entry:**
- Price touches/extends beyond upper Bollinger Band (95% threshold)
- RSI > 70 (overbought)
- Volume > 1.2x average volume
- Volatility between 4-25 bps
- No strong trend (EMA divergence < 15 bps)

### Exit Signals

1. **Take Profit**: Price returns to target (3 bps profit)
2. **Stop Loss**: Price continues against us (6 bps loss)
3. **Time Stop**: Exit after 5 minutes if no movement
4. **Reversal**: RSI flips to opposite extreme

## Configuration Options

See `config.yaml` for all available parameters:

- `take_profit_bps`: Target profit (default: 3 bps)
- `stop_loss_bps`: Stop loss (default: 6 bps)
- `vol_min_bps` / `vol_max_bps`: Volatility range filter
- `rsi_oversold` / `rsi_overbought`: RSI thresholds
- `max_position_size`: Maximum position size
- And more...

## Performance Expectations

**Ideal Conditions:**
- Ranging/choppy markets
- Moderate volatility (6-15 bps)
- Good volume

**Avoid:**
- Strong trends (EMA divergence > 15 bps)
- Extreme volatility (> 25 bps or < 4 bps)
- Low volume periods

## Risk Warning

⚠️ **This is a directional trading strategy (not market making)**
- Requires active monitoring
- Can lose money in trending markets
- Start with small position sizes
- Always test in `dry_run: true` mode first

## License

[Your License Here]

