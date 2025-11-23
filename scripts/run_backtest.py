#!/usr/bin/env python3
"""
Run Backtest Analysis

Analyze trade history files and generate performance reports.
"""
import sys
import os
import glob

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.backtest import Backtester


def main():
    print("=" * 60)
    print("Trading Bot - Backtest Analysis")
    print("=" * 60)
    print()

    # Find all trade history files
    trade_files = glob.glob("trades_*.json")

    if not trade_files:
        print("❌ No trade history files found!")
        print("Trade files should be named: trades_*.json")
        sys.exit(1)

    print("Available trade history files:")
    for i, filename in enumerate(trade_files, 1):
        print(f"{i}. {filename}")
    print()

    # Get file choice
    if len(trade_files) == 1:
        filename = trade_files[0]
        print(f"Analyzing: {filename}\n")
    else:
        choice = input(f"Select file (1-{len(trade_files)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(trade_files):
                filename = trade_files[idx]
            else:
                print("Invalid choice!")
                sys.exit(1)
        except ValueError:
            print("Invalid input!")
            sys.exit(1)

    # Run backtest
    try:
        backtester = Backtester(filename)
        df = backtester.analyze()

        # Analyze top symbols
        if not df.empty and 'symbol' in df.columns:
            print("\n" + "=" * 60)
            print("Symbol Analysis")
            print("=" * 60)
            unique_symbols = df['symbol'].unique()
            for symbol in unique_symbols[:5]:  # Top 5 symbols
                print(f"\n--- {symbol} ---")
                backtester.analyze_by_symbol(symbol)

    except Exception as e:
        print(f"\n❌ Error analyzing trades: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()