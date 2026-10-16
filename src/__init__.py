"""
AI-powered US Stock Trading Bot
"""
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env (the directory above this package) BEFORE TradingConfig
# is imported: it captures the API keys via os.getenv at class-definition time.
# Resolving the path here, rather than relying on python-dotenv's search, makes
# it work from any working directory and for `python -m src...`. When no such
# file exists (e.g. a non-editable install) fall back to the default search of
# the current directory and its parents. Shell-exported variables take precedence.
_REPO_ROOT_ENV = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(_REPO_ROOT_ENV if _REPO_ROOT_ENV.is_file() else None)

__version__ = '2.0.0'
__author__ = 'Yungoo Park'

# Package exports
from src.config.trading_config import TradingConfig

__all__ = ['TradingConfig']
