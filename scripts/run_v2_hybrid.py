#!/usr/bin/env python3
"""
Run Improved Hybrid Trading System (V2)

This script starts the V2 hybrid system with configurable strategy profiles.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.trading_config import TradingConfig
from src.systems.v2.hybrid import ImprovedHybridSystem


def main():
    print("=" * 60)
    print("AI Trading Bot - Improved Hybrid System (V2)")
    print("=" * 60)
    print()

    # Display available strategies
    TradingConfig.print_available_strategies()

    # Get strategy choice
    print("Select a strategy:")
    print("1. Conservative (안정적)")
    print("2. Moderate (균형잡힌) - Default")
    print("3. Aggressive (공격적)")
    print("4. Scalping (빠른 매매)")
    print("5. Swing (중장기)")
    print()

    choice = input("Enter choice (1-5) or press Enter for default [2]: ").strip()

    strategy_map = {
        '1': 'conservative',
        '2': 'moderate',
        '3': 'aggressive',
        '4': 'scalping',
        '5': 'swing',
        '': 'moderate'  # Default
    }

    strategy = strategy_map.get(choice, 'moderate')

    print(f"\nSelected strategy: {strategy.upper()}")
    print()

    # Get configuration
    config = TradingConfig.get_config(strategy=strategy, paper_trading=True)

    # Validate configuration
    if not TradingConfig.validate_config(config):
        print("\n❌ Configuration validation failed!")
        print("Please check your .env file and ensure all API keys are set.")
        sys.exit(1)

    print("\n✅ Configuration validated")
    print(f"📊 Symbols: {config['symbols']}")
    print(f"⚠️  Paper Trading: {config['paper_trading']}")
    print()

    # Confirm start
    confirm = input("Start trading system? (yes/no) [yes]: ").strip().lower()
    if confirm and confirm not in ['yes', 'y']:
        print("Aborted.")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("Starting system...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    # Start system
    system = ImprovedHybridSystem(config)
    system.run()


if __name__ == "__main__":
    main()