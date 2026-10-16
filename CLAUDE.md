# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Gemini-driven US stock trading bot on the Alpaca broker, paper trading by default. Five self-contained trading loops live under `src/systems/` (V1 = reference implementations, V2 = recommended). Code comments, log messages, AI prompts and the README are in Korean. Keep new log strings in the same style: the README's monitoring greps (`grep "거래\|Exit" trading.log`) match on labels such as `[규칙 기반 청산]` and `[AI 기반 거래]`.

## Commands

Use `python3` (there is no `python` on PATH on this machine). The third-party deps are not installed in the system interpreter and the repo ships no venv, so create one first (`python3 -m venv .venv && source .venv/bin/activate`; `.venv/` is gitignored). Run everything from the repo root: the systems write `trading.log` and `trades_*.json` into the current working directory, and all imports are absolute `src.*` paths.

```bash
pip install -r requirements.txt   # deps only
pip install -e .                  # editable install; also registers trading-bot-v2-event,
                                  # trading-bot-v2-hybrid and trading-bot-v1-basic console scripts

# API keys: cp .env.example .env and fill it in; src/__init__.py loads it automatically

# Interactive launchers: prompt for a strategy profile, validate config, ask to confirm
python3 scripts/run_v2_event_driven.py
python3 scripts/run_v2_hybrid.py

# Non-interactive: each module's main() uses its own hard-coded config, not a TradingConfig profile
python3 -m src.systems.v2.event_driven
python3 -m src.systems.v2.hybrid

# Print strategy profiles and symbol sets, then validate that the API keys are set
# (a RuntimeWarning that the module is already in sys.modules is expected: src/__init__.py imports it first)
python3 -m src.config.trading_config

# Analyze a saved trade file
python3 -m src.utils.backtest trades_improved_event_YYYYMMDD.json
python3 scripts/run_backtest.py   # picks from trades_*.json in the CWD
```

There is no test suite (`tests/` holds only `__init__.py`), no pytest or lint configuration, and no CI.

## Environment variables are read at import time

`src/__init__.py` calls `load_dotenv()` before anything else, so importing any `src.*` module (the scripts, `python3 -m src...` and the console scripts all do) loads `.env` from the repo root; variables already exported in the shell take precedence. `TradingConfig` then captures `GEMINI_API_KEY`, `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` as class attributes via `os.getenv` when `src.config.trading_config` is imported, and each system module's `main()` reads them the same way. Consequences:

- The `load_dotenv()` call must stay above the `TradingConfig` import in `src/__init__.py`.
- Setting `os.environ[...]` after importing `TradingConfig` does not change what `get_config()` returns.
- `TradingConfig.validate_config()` is the only place missing keys are reported. Without it, `genai.configure(api_key=None)` and `TradingClient(None, None)` fail later with unhelpful errors.

## Architecture

### Five independent modules, no shared base class

`src/systems/v1/{basic_ai,hybrid,event_driven}.py` and `src/systems/v2/{event_driven,hybrid}.py` each define one system class that is fully self-contained. Every file carries its own copy of `_get_market_data`, `_calculate_indicators` (RSI 14, SMA 20/50, MACD 12/26/9, Bollinger 20/2σ over 5 days of Alpaca minute bars), `_get_positions`, `_check_risk_limits`, `_is_market_open`, `run` and `_save_trade_history`. Nothing is imported between them. A change to indicator math, the main loop, the AI prompt or the response parser must be replicated in every file it should apply to (at minimum both V2 files).

Other things implied by this layout:

- Each module calls `logging.basicConfig(...)` at import with handlers for `trading.log` and stdout. Importing the `src.systems` package pulls in all five modules, and therefore `yfinance`, which only V1 `basic_ai` uses (for news headlines in its prompt).
- The Gemini model name (`gemini-2.0-flash-exp`) is hard-coded in each class's `__init__`.
- `src/systems/v1/__init__.py` re-exports `AITradingSystem` under the name `BasicAISystem`.
- The `setup.py` console scripts point at each module's `main()`, which builds an inline config and bypasses `TradingConfig` profiles. Profiles are only applied through `scripts/run_*.py` or by building the config dict yourself.

### Config contract

`TradingConfig.get_config(strategy, symbols, paper_trading)` returns a flat dict: the three API keys, `symbols`, the profile's `max_position_size`, `stop_loss_pct`, `take_profit_pct`, `max_daily_loss`, `query_interval`, plus `paper_trading` and `strategy_name`. Systems read the keys and `symbols` with `config[...]` and everything else with `config.get(key, default)`, so extra keys are harmless and missing ones silently fall back to defaults. Profiles (`conservative`, `moderate`, `aggressive`, `scalping`, `swing`) and symbol sets are dict literals in `src/config/trading_config.py`; add a profile by adding an entry there.

`max_position_size` is advisory. It is only rendered into the AI prompt as a dollar figure; nothing in code caps order size, and the hybrid rule-based BUY is a hard-coded 10 shares.

### V2 per-symbol pipeline (`process_symbol`)

Order matters and each early step returns immediately:

1. Fetch bars and indicators; bail if empty.
2. `_check_stop_loss_take_profit` against `position_tracker`, then `_execute_rule_based_exit` (market sell of the tracked qty). No AI.
3. Event-driven only: `_detect_emergency_situation` (loss ≤ -5%, or RSI < 25 with loss worse than -2%), then rule exit. No AI.
4. Decide whether to call Gemini:
   - **event_driven**: `should_query_ai` fires on a ≥5% price move since the previous check, volume ≥2× the 20-bar average, a MACD or SMA crossover, or a 2-hour scheduled check. Executes when parsed `confidence >= 70`.
   - **hybrid**: `ImprovedRuleBasedFilter.calculate_signal_score` yields 0–100 (50 = neutral) from RSI (weight scaled by `min(volatility/0.02, 1.5)`), MACD, MA trend and Bollinger position. Gemini is queried at ≥75/≤25, at ≥65/≤35 when holding, or at ≥60/≤40 when 20-bar volatility exceeds 2.5%; executes when `confidence >= 75`. Otherwise `make_rule_based_decision`: no position and score ≥70 → BUY 10; holding and score ≤30 → SELL all.

Prompts are Korean and demand a JSON object. `_parse_ai_decision` slices from the first `{` to the last `}` and requires `action`, `quantity` and `confidence`. The confidence gate is enforced in code after parsing, not only in the prompt text.

### `position_tracker` is the sole source of truth for SL/TP, and it is in-memory

Shape: `{symbol: {entry_price, stop_loss, take_profit, qty, entry_time}}`, written by `_update_position_tracker` after each fill, never persisted, empty on every start. Therefore:

- Positions already open in Alpaca when the process starts get no stop-loss, take-profit or emergency protection; those checks return `None` for untracked symbols. Alpaca's own positions (`_get_positions`) are used only to tell the AI and the hybrid filter whether a position exists.
- A BUY overwrites the entry (no averaging); a SELL deletes the entry even when the quantity was partial.
- SL/TP are client-side: compared against the latest minute-bar close once per loop (`query_interval` plus 2 s per symbol), not broker stop orders.

### Loop, risk limit and persistence

`run()` loops forever: it sleeps 5 min while Alpaca's clock says the market is closed, and sleeps 1 h (without exiting) once equity has dropped `max_daily_loss` below `start_equity`. `start_equity` is captured in `__init__`, so "daily" P&L really means "since process start". Trade history is written only in the `finally` of `run()` (Ctrl+C) to `trades_improved_event_YYYYMMDD.json` or `trades_improved_hybrid_YYYYMMDD.json` as `{"trades": [...], "stats": {...}}`. V1 `basic_ai` writes a bare list; `Backtester` accepts both shapes. These files and `trading.log` are gitignored.

`Backtester` groups by the `method` field, whose values differ by system. V2 hybrid uses `rule_based` (score trades), `rule_based_exit` (SL/TP) and `ai_based`. V2 event-driven records SL/TP and emergency exits as `rule_based`, not `rule_based_exit`, despite what the README says.
