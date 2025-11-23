# config.py
"""트레이딩 시스템 설정 관리"""
import os
from typing import Dict


class TradingConfig:
    """트레이딩 설정 클래스"""

    # API Keys (환경변수에서 로드)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
    ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')

    # 기본 종목 리스트
    DEFAULT_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

    # 대형주 중심 (안정적)
    LARGE_CAP_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # 테크 중심 (변동성)
    TECH_SYMBOLS = ['NVDA', 'AMD', 'TSLA', 'PLTR', 'COIN']

    # 전략 프로필
    STRATEGIES = {
        'conservative': {
            'description': '보수적 전략 - 작은 포지션, 빠른 손절',
            'max_position_size': 0.10,  # 10%
            'stop_loss_pct': 0.015,     # 1.5% 손절
            'take_profit_pct': 0.03,    # 3% 익절
            'max_daily_loss': 0.03,     # 일일 최대 3% 손실
            'query_interval': 300,       # 5분
        },

        'moderate': {
            'description': '중도적 전략 - 균형잡힌 리스크/리워드',
            'max_position_size': 0.15,  # 15%
            'stop_loss_pct': 0.02,      # 2% 손절
            'take_profit_pct': 0.05,    # 5% 익절
            'max_daily_loss': 0.05,     # 일일 최대 5% 손실
            'query_interval': 300,       # 5분
        },

        'aggressive': {
            'description': '공격적 전략 - 큰 포지션, 여유로운 손절',
            'max_position_size': 0.20,  # 20%
            'stop_loss_pct': 0.03,      # 3% 손절
            'take_profit_pct': 0.08,    # 8% 익절
            'max_daily_loss': 0.08,     # 일일 최대 8% 손실
            'query_interval': 300,       # 5분
        },

        'scalping': {
            'description': '스캘핑 전략 - 빠른 매매, 작은 수익',
            'max_position_size': 0.10,  # 10%
            'stop_loss_pct': 0.005,     # 0.5% 손절
            'take_profit_pct': 0.01,    # 1% 익절
            'max_daily_loss': 0.03,     # 일일 최대 3% 손실
            'query_interval': 180,       # 3분
        },

        'swing': {
            'description': '스윙 전략 - 중장기 포지션',
            'max_position_size': 0.25,  # 25%
            'stop_loss_pct': 0.05,      # 5% 손절
            'take_profit_pct': 0.15,    # 15% 익절
            'max_daily_loss': 0.10,     # 일일 최대 10% 손실
            'query_interval': 900,       # 15분
        }
    }

    @classmethod
    def get_config(cls, strategy: str = 'moderate', symbols: list = None,
                   paper_trading: bool = True) -> Dict:
        """설정 딕셔너리 생성

        Args:
            strategy: 전략 이름 ('conservative', 'moderate', 'aggressive', 'scalping', 'swing')
            symbols: 거래할 종목 리스트 (None이면 DEFAULT_SYMBOLS 사용)
            paper_trading: 페이퍼 트레이딩 여부

        Returns:
            설정 딕셔너리
        """
        if strategy not in cls.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. "
                           f"Available: {list(cls.STRATEGIES.keys())}")

        strategy_config = cls.STRATEGIES[strategy].copy()

        config = {
            # API Keys
            'gemini_api_key': cls.GEMINI_API_KEY,
            'alpaca_api_key': cls.ALPACA_API_KEY,
            'alpaca_secret_key': cls.ALPACA_SECRET_KEY,

            # 종목
            'symbols': symbols or cls.DEFAULT_SYMBOLS,

            # 전략 파라미터
            **strategy_config,

            # 기타
            'paper_trading': paper_trading,
            'strategy_name': strategy
        }

        return config

    @classmethod
    def validate_config(cls, config: Dict) -> bool:
        """설정 유효성 검증"""
        required_keys = [
            'gemini_api_key', 'alpaca_api_key', 'alpaca_secret_key',
            'symbols', 'max_position_size', 'stop_loss_pct',
            'take_profit_pct', 'max_daily_loss', 'query_interval'
        ]

        for key in required_keys:
            if key not in config:
                print(f"❌ Missing config key: {key}")
                return False

        # API 키 확인
        if not config['gemini_api_key']:
            print("❌ GEMINI_API_KEY not set")
            return False
        if not config['alpaca_api_key']:
            print("❌ ALPACA_API_KEY not set")
            return False
        if not config['alpaca_secret_key']:
            print("❌ ALPACA_SECRET_KEY not set")
            return False

        # 종목 확인
        if not config['symbols'] or len(config['symbols']) == 0:
            print("❌ No symbols specified")
            return False

        print("✅ Config validation passed")
        return True

    @classmethod
    def print_available_strategies(cls):
        """사용 가능한 전략 출력"""
        print("\n=== Available Trading Strategies ===\n")
        for name, details in cls.STRATEGIES.items():
            print(f"📊 {name.upper()}")
            print(f"   {details['description']}")
            print(f"   - Position Size: {details['max_position_size']*100}%")
            print(f"   - Stop Loss: {details['stop_loss_pct']*100}%")
            print(f"   - Take Profit: {details['take_profit_pct']*100}%")
            print(f"   - Max Daily Loss: {details['max_daily_loss']*100}%")
            print(f"   - Check Interval: {details['query_interval']}s ({details['query_interval']/60:.1f}min)")
            print()

    @classmethod
    def print_symbol_sets(cls):
        """사용 가능한 종목 세트 출력"""
        print("\n=== Available Symbol Sets ===\n")
        print(f"📈 DEFAULT: {cls.DEFAULT_SYMBOLS}")
        print(f"🏢 LARGE_CAP: {cls.LARGE_CAP_SYMBOLS}")
        print(f"💻 TECH: {cls.TECH_SYMBOLS}")
        print()


# 사용 예시
if __name__ == "__main__":
    # 사용 가능한 전략 출력
    TradingConfig.print_available_strategies()

    # 사용 가능한 종목 세트 출력
    TradingConfig.print_symbol_sets()

    # 설정 생성 예시
    print("=== Config Example: Moderate Strategy ===\n")
    config = TradingConfig.get_config(strategy='moderate')

    # API 키는 출력하지 않음
    for key, value in config.items():
        if 'key' in key.lower():
            print(f"{key}: {'*' * 10 if value else 'NOT SET'}")
        else:
            print(f"{key}: {value}")

    print("\n=== Validating Config ===\n")
    TradingConfig.validate_config(config)

    print("\n=== Usage in Trading System ===\n")
    print("""
# Conservative strategy with large cap stocks
from config import TradingConfig
config = TradingConfig.get_config(
    strategy='conservative',
    symbols=TradingConfig.LARGE_CAP_SYMBOLS,
    paper_trading=True
)

# Start trading system
from event_driven_system_v2 import ImprovedEventDrivenSystem
system = ImprovedEventDrivenSystem(config)
system.run()
    """)