# Breakout + Momentum Strategy Plan

## Strategy Overview
**Name:** Breakout Momentum Trader
**Type:** Breakout + Momentum
**Timeframe:** 15 minutes (configurable)
**Target:** 2-5 trades/day, 55-65% win rate, 2:1-3:1 R:R

## Why This Works for SOL
1. **SOL's Personality**: SOL loves explosive breakouts (5-10% moves)
2. **Momentum Confirmation**: Reduces false breakouts
3. **Clear Rules**: Breakout level + momentum = high probability
4. **Good R:R**: 2:1-3:1 achievable with proper stops

## Entry Conditions (ALL must be true)

### 1. Breakout Detection
- **Recent High/Low**: Identify highest high / lowest low in last 20-50 candles
- **Breakout Level**: Price breaks above recent high (long) or below recent low (short)
- **Breakout Confirmation**: Price closes above/below level (not just wick)

### 2. Momentum Filter
- **RSI**: RSI >60 (long) or <40 (short) - momentum confirmation
- **MACD**: MACD line > signal line (long) or < signal line (short)
- **Price Action**: Last 3-5 candles trending in breakout direction

### 3. Volatility Filter
- **ATR Expansion**: ATR increasing (volatility expanding = real move)
- **ATR Range**: ATR 3-15 bps (avoid too choppy or too volatile)
- **BB Width**: Bollinger Band width expanding (volatility squeeze breaking)

### 4. Trend Confirmation
- **EMA Alignment**: EMA 20 > EMA 50 (long) or EMA 20 < EMA 50 (short)
- **Price vs EMA**: Price above EMA 20 (long) or below EMA 20 (short)

## Exit Conditions

### Take Profit
- **Primary TP**: 2-3x ATR from entry
- **Trailing Stop**: Activate after 1x ATR profit, trail by 0.5x ATR
- **Partial Profit**: Take 50% at 1.5x ATR, let rest run with trailing stop

### Stop Loss
- **Initial SL**: 1.5x ATR below breakout level (long) or above (short)
- **Breakout Failure**: If price closes back below/above breakout level, exit immediately

### Time Stop
- **Max Hold**: 60 minutes (4 candles on 15m timeframe)
- **No Movement**: Exit if no progress after 30 minutes

## Risk Management

### Position Sizing
- **Base Size**: 0.1 SOL (same as other strategies)
- **Volatility Adjustment**: Reduce 20% if ATR >10 bps (high vol)
- **Breakout Strength**: Increase 10% if RSI >70 or <30 (very strong momentum)

### Adaptive Features
- **Cooldown**: 20 seconds after exit (prevent re-entry into failed breakouts)
- **Losing Streak**: Pause 5 minutes after 2 consecutive losses
- **Breakout Failure**: Extend cooldown to 60 seconds if breakout fails

## Implementation Details

### Indicators Needed
1. **Price Action**: Recent high/low (20-50 candle lookback)
2. **RSI**: 14 period (momentum)
3. **MACD**: 12, 26, 9 (momentum confirmation)
4. **EMA**: 20 and 50 period (trend)
5. **ATR**: 14 period (volatility)
6. **Bollinger Bands**: 20 period, 2 std (volatility expansion)

### Entry Logic
```python
def check_breakout_entry(price, indicators):
    # 1. Check for breakout
    if price > recent_high and closed_above_high:
        # 2. Check momentum
        if rsi > 60 and macd_bullish:
            # 3. Check volatility
            if atr_expanding and 3 <= atr_bps <= 15:
                # 4. Check trend
                if ema_20 > ema_50 and price > ema_20:
                    return "long"

    # Similar for short
```

### Exit Logic
```python
def check_breakout_exit(price, entry_price, indicators):
    # Trailing stop (if in profit)
    if profit >= 1x_atr:
        trailing_stop = price - (0.5 * atr)  # For long
        if price <= trailing_stop:
            return "trailing_stop"

    # Breakout failure
    if price < breakout_level:  # For long
        return "breakout_failure"

    # Take profit
    if profit >= 2x_atr:
        return "take_profit"

    # Stop loss
    if price <= stop_loss:
        return "stop_loss"
```

## Expected Performance

### Conservative Estimate
- **Trades/Day**: 2-3
- **Win Rate**: 55-60%
- **R:R**: 2:1
- **Daily PnL**: +0.3-0.5%

### Optimistic Estimate
- **Trades/Day**: 4-5
- **Win Rate**: 60-65%
- **R:R**: 2.5:1
- **Daily PnL**: +0.5-0.8%

## Comparison to Existing Strategies

| Strategy | Type | Trades/Day | Win Rate | R:R | Best For |
|----------|------|------------|----------|-----|----------|
| RSI+BB | Trend Following | 1-3 | 40% (target 70%) | 1.18:1 | Trending markets |
| Renko+AO | Divergence | 1-3 | 25% (target 70%) | 2.10:1 | Reversal setups |
| **Breakout** | **Momentum** | **2-5** | **55-65%** | **2:1-3:1** | **Explosive moves** |

## Why This Complements Existing Strategies

1. **Different Market Conditions**:
   - RSI+BB: Trending markets
   - Renko+AO: Reversal/divergence
   - Breakout: Explosive moves

2. **Different Timeframes**: All can run on 15m, but breakout can also work on 5m

3. **Diversification**: Three different approaches = more opportunities

## Next Steps

1. **Build the strategy** (`modules/breakout_trader.py`)
2. **Test in dry-run** for 24-48 hours
3. **Compare performance** with existing strategies
4. **Optimize** based on results
5. **Deploy to separate account** (or same account if no conflicts)

## Questions to Answer

1. Should we use the same account or separate?
   - **Recommendation**: Same account (different strategies can coexist)

2. Should we use same timeframe (15m) or different?
   - **Recommendation**: Start with 15m, can optimize later

3. Should we combine with existing strategies or keep separate?
   - **Recommendation**: Keep separate initially, combine signals later if needed

