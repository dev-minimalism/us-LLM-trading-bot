"""
AI-powered US Stock Trading Bot
"""
from dotenv import load_dotenv

# Load .env (searched from this package's directory upward, i.e. the repo root)
# BEFORE TradingConfig is imported: it captures the API keys via os.getenv at
# class-definition time. Variables already exported in the shell take precedence.
load_dotenv()

__version__ = '2.0.0'
__author__ = 'Yungoo Park'

# Package exports
from src.config.trading_config import TradingConfig

__all__ = ['TradingConfig']
