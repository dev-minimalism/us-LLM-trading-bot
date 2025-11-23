# backtest.py
"""백테스팅 유틸리티"""
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List


class Backtester:
    """간단한 백테스팅 도구"""

    def __init__(self, trade_history_file: str):
        with open(trade_history_file) as f:
            data = json.load(f)

        # 데이터 형식 확인 (hybrid/event 시스템은 다른 형식)
        if isinstance(data, dict) and 'trades' in data:
            self.trades = data['trades']
            self.stats = data.get('stats', {})
        else:
            self.trades = data
            self.stats = {}

    def analyze(self):
        """거래 성과 분석"""
        df = pd.DataFrame(self.trades)

        print("=" * 60)
        print("거래 성과 분석")
        print("=" * 60)

        if len(df) == 0:
            print("거래 기록이 없습니다.")
            return df

        print(f"총 거래 수: {len(df)}")
        print(f"매수: {len(df[df['action'] == 'BUY'])}")
        print(f"매도: {len(df[df['action'] == 'SELL'])}")

        if 'confidence' in df.columns:
            print(f"평균 신뢰도: {df['confidence'].mean():.2f}%")

        print("\n종목별 거래:")
        print(df['symbol'].value_counts())

        if 'method' in df.columns:
            print("\n거래 방식:")
            print(df['method'].value_counts())

        if 'event_type' in df.columns:
            print("\n이벤트 타입:")
            print(df['event_type'].value_counts())

        # 시스템 통계
        if self.stats:
            print("\n시스템 통계:")
            for key, value in self.stats.items():
                print(f"- {key}: {value}")

        print("=" * 60)
        return df

    def analyze_by_symbol(self, symbol: str):
        """특정 종목 분석"""
        df = pd.DataFrame(self.trades)
        symbol_trades = df[df['symbol'] == symbol]

        print(f"\n{symbol} 거래 분석:")
        print(f"총 거래: {len(symbol_trades)}")
        print(f"매수: {len(symbol_trades[symbol_trades['action'] == 'BUY'])}")
        print(f"매도: {len(symbol_trades[symbol_trades['action'] == 'SELL'])}")

        if 'confidence' in symbol_trades.columns:
            print(f"평균 신뢰도: {symbol_trades['confidence'].mean():.2f}%")

        return symbol_trades

    def compare_systems(self, other_file: str):
        """두 시스템 비교"""
        other = Backtester(other_file)

        print("\n시스템 비교:")
        print(f"현재 시스템: {len(self.trades)} 거래")
        print(f"비교 시스템: {len(other.trades)} 거래")

        if self.stats and other.stats:
            print("\nAI 사용률 비교:")
            if 'ai_usage_rate' in self.stats:
                print(f"현재 시스템: {self.stats['ai_usage_rate']:.1f}%")
            if 'ai_usage_rate' in other.stats:
                print(f"비교 시스템: {other.stats['ai_usage_rate']:.1f}%")


# 사용 예시
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python backtest.py <거래_기록_파일.json>")
        print("예시: python backtest.py trades_20241123.json")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        backtester = Backtester(filename)
        df = backtester.analyze()

        # 종목별 분석
        if not df.empty and 'symbol' in df.columns:
            unique_symbols = df['symbol'].unique()
            for symbol in unique_symbols[:3]:  # 상위 3개 종목만
                backtester.analyze_by_symbol(symbol)

    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filename}")
    except Exception as e:
        print(f"오류 발생: {e}")