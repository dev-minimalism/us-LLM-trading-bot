# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered automated trading system for US stocks using Gemini AI and Alpaca broker. The system implements multiple trading strategies with automatic stop-loss/take-profit execution and position tracking.

## System Architecture

### Two Generations of Trading Systems

**V1 Systems** (Basic implementations):
- `main.py` - Basic AI system (15-min intervals, AI for all decisions)
- `hybrid_trading_system.py` - Hybrid system (rule filter + AI, 80% AI cost reduction)
- `event_driven_system.py` - Event-driven system (AI only on events, 88% AI cost reduction)

**V2 Systems** (Improved - RECOMMENDED):
- `event_driven_system_v2.py` - Improved event-driven with automatic stop-loss/take-profit
- `hybrid_trading_system_v2.py` - Improved hybrid with dynamic scoring

### Key Design Patterns

**Position Tracking Architecture**:
```python
position_tracker = {
    'SYMBOL': {
        'entry_price': float,      # Entry price
        'stop_loss': float,        # Auto-calculated stop loss price
        'take_profit': float,      # Auto-calculated take profit price
        'qty': int,                # Position size
        'entry_time': str          # ISO timestamp
    }
}
```

**Three-Layer Decision Making** (V2 systems):
1. **Stop-Loss/Take-Profit Check** (highest priority, no AI)
   - Executes immediately when price targets are hit
   - Uses `_check_stop_loss_take_profit()` method
2. **Emergency Situations** (high priority, no AI)
   - Rapid loss detection (-5% or worse)
   - Extreme market conditions (RSI < 25 with loss)
3. **AI Query** (normal priority)
   - Triggered by events or signal scores
   - Used for complex decisions

**Dynamic Scoring System** (hybrid_trading_system_v2.py):
- Adjusts technical indicator weights based on volatility
- Higher volatility = increased RSI importance
- Formula: `volatility_factor = min(volatility / 0.02, 1.5)`

## Running the Systems

### Setup
```bash
# 1. Setup environment variables
cp .env.example .env
# Edit .env and add API keys:
# GEMINI_API_KEY, ALPACA_API_KEY, ALPACA_SECRET_KEY

# 2. Install dependencies
pip install -r requirements.txt
```

### Run Directly
```bash
# V2 Event-Driven (recommended for cost efficiency)
python event_driven_system_v2.py

# V2 Hybrid (recommended for balanced approach)
python hybrid_trading_system_v2.py
```

### Run with Config Profiles
```python
from config import TradingConfig
from event_driven_system_v2 import ImprovedEventDrivenSystem

# Use predefined strategy profile
config = TradingConfig.get_config(strategy='moderate')
system = ImprovedEventDrivenSystem(config)
system.run()
```

### Available Strategy Profiles
- `conservative` - 10% position, 1.5% stop-loss, 3% take-profit
- `moderate` - 15% position, 2% stop-loss, 5% take-profit (default)
- `aggressive` - 20% position, 3% stop-loss, 8% take-profit
- `scalping` - 10% position, 0.5% stop-loss, 1% take-profit
- `swing` - 25% position, 5% stop-loss, 15% take-profit

### Symbol Sets
```python
TradingConfig.DEFAULT_SYMBOLS   # ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
TradingConfig.LARGE_CAP_SYMBOLS # ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
TradingConfig.TECH_SYMBOLS      # ['NVDA', 'AMD', 'TSLA', 'PLTR', 'COIN']
```

## Configuration Management

The `config.py` module centralizes all trading parameters:
- API key management (from environment variables)
- 5 predefined strategy profiles
- 3 symbol sets
- Configuration validation via `TradingConfig.validate_config()`

To view all available options:
```bash
python config.py
```

## Backtesting

```bash
# Analyze trade history
python backtest.py trades_improved_event_20241123.json

# Compare two systems
# In backtest.py, use compare_systems() method
```

Trade history files are automatically saved as:
- V1: `trades_<date>.json`, `trades_hybrid_<date>.json`, `trades_event_<date>.json`
- V2: `trades_improved_event_<date>.json`, `trades_improved_hybrid_<date>.json`

## Monitoring

```bash
# Real-time log monitoring
tail -f trading.log

# Filter for trades only
grep "거래\|Exit" trading.log

# Check for errors
grep ERROR trading.log
```

## Critical Implementation Details

### Stop Loss / Take Profit Execution Priority

In V2 systems, stop-loss and take-profit checks happen BEFORE any other logic:

```python
def process_symbol(self, symbol: str):
    # 1. Get market data
    market_data = self._get_market_data(symbol)
    current_price = market_data.iloc[-1]['close']

    # 2. PRIORITY: Check stop-loss/take-profit (NO AI)
    sl_tp_result = self._check_stop_loss_take_profit(symbol, current_price)
    if sl_tp_result:
        self._execute_rule_based_exit(symbol, reason, current_price)
        return  # Exit immediately

    # 3. Check emergency situations
    # 4. Then proceed with AI queries
```

### Position Tracker Synchronization

The `position_tracker` dict is the source of truth for position management:
- Updated immediately after every trade (`_update_position_tracker()`)
- Separate from Alpaca's position data (which may have delays)
- Must be kept in sync with actual broker positions

### Rule-Based vs AI-Based Trade Recording

Trade history records include a `method` field:
- `'rule_based'` - Executed by signal score threshold
- `'rule_based_exit'` - Automatic stop-loss or take-profit
- `'ai_based'` - Executed after AI decision

This distinction is crucial for performance analysis.

### Technical Indicator Calculations

All systems use standardized indicator calculations in `_calculate_indicators()`:
- RSI (14-period)
- MACD (12, 26, 9)
- SMA (20, 50)
- Bollinger Bands (20-period, 2 std dev)

These are applied to minute-level data from Alpaca.

## Safety Mechanisms

1. **Paper Trading Default**: All configs default to `paper_trading: True`
2. **Daily Loss Limit**: System stops trading if daily loss exceeds threshold
3. **Market Hours Check**: Only trades during US market hours (9:30 AM - 4:00 PM ET)
4. **API Rate Limiting**: 2-second delay between symbol processing
5. **Trade History Auto-Save**: Saves on system exit (Ctrl+C)

## Common Modifications

### Adding a New Strategy Profile

Edit `config.py`:
```python
STRATEGIES = {
    # ... existing strategies ...
    'my_strategy': {
        'description': 'My custom strategy',
        'max_position_size': 0.12,
        'stop_loss_pct': 0.025,
        'take_profit_pct': 0.06,
        'max_daily_loss': 0.04,
        'query_interval': 240,  # 4 minutes
    }
}
```

### Changing AI Model

In any trading system file:
```python
self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
# Change to: gemini-pro, gemini-1.5-pro, etc.
```

### Adjusting Rule-Based Thresholds

In `hybrid_trading_system_v2.py`, modify `ImprovedRuleBasedFilter.make_rule_based_decision()`:
```python
# Buy threshold (currently 70)
if score >= 70:  # Adjust this value
    return {'action': 'BUY', ...}

# Sell threshold (currently 30)
if score <= 30:  # Adjust this value
    return {'action': 'SELL', ...}
```

### Emergency Exit Conditions

In V2 systems, modify `_detect_emergency_situation()`:
```python
# Rapid loss threshold (currently -5%)
if loss_pct <= -0.05:  # Adjust threshold
    return 'rapid_loss'

# RSI oversold threshold (currently 25)
if latest['rsi'] < 25 and loss_pct < -0.02:
    return 'extreme_oversold'
```

## Architecture Decisions

**Why two versions exist**:
- V1: Educational/reference implementation
- V2: Production-ready with automated risk management

**Why position_tracker is separate from Alpaca positions**:
- Alpaca API may have delays
- Need immediate access to entry prices for stop-loss calculations
- Enables offline testing/simulation

**Why event-driven is recommended over hybrid**:
- Lower AI costs (88-92% vs 85% reduction)
- Clearer trigger conditions
- Better for avoiding overtrading

**Why config.py uses class methods**:
- Enables configuration validation
- Centralizes symbol sets
- Supports multiple strategy profiles without code changes

## External Dependencies

- `google.generativeai` - Gemini AI for trading decisions
- `alpaca-py` - US stock trading via Alpaca broker
- `yfinance` - News/sentiment data (V1 only)
- `pandas` - Technical indicator calculations
- `pytz` - Market hours timezone handling

## Development Workflow

When modifying trading logic:
1. Test with `paper_trading: True`
2. Use small position sizes initially
3. Monitor `trading.log` for unexpected behavior
4. Analyze results with `backtest.py`
5. Never commit with actual API keys (use `.env`)