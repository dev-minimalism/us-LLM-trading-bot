# hybrid_trading_system.py
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
import google.generativeai as genai
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pytz

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RuleBasedFilter:
    """규칙 기반 필터 - AI 호출 전 사전 필터링"""

    @staticmethod
    def calculate_signal_score(df: pd.DataFrame) -> Tuple[float, Dict]:
        """기술적 지표 기반 시그널 스코어 계산 (0-100)"""
        latest = df.iloc[-1]
        signals = {}
        score = 0

        # 1. RSI 시그널 (30점)
        if latest['rsi'] < 30:  # 과매도
            signals['rsi'] = 'oversold'
            score += 30
        elif latest['rsi'] > 70:  # 과매수
            signals['rsi'] = 'overbought'
            score -= 30
        else:
            signals['rsi'] = 'neutral'

        # 2. MACD 시그널 (25점)
        if latest['macd'] > latest['signal']:
            signals['macd'] = 'bullish'
            score += 25
        else:
            signals['macd'] = 'bearish'
            score -= 25

        # 3. 이동평균 시그널 (25점)
        if latest['close'] > latest['sma_20'] > latest['sma_50']:
            signals['ma'] = 'uptrend'
            score += 25
        elif latest['close'] < latest['sma_20'] < latest['sma_50']:
            signals['ma'] = 'downtrend'
            score -= 25
        else:
            signals['ma'] = 'sideways'

        # 4. 볼린저 밴드 시그널 (20점)
        bb_position = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
        if bb_position < 0.2:  # 하단 근처
            signals['bb'] = 'lower_band'
            score += 20
        elif bb_position > 0.8:  # 상단 근처
            signals['bb'] = 'upper_band'
            score -= 20
        else:
            signals['bb'] = 'middle'

        # 정규화 (0-100)
        normalized_score = max(0, min(100, 50 + score))

        return normalized_score, signals

    @staticmethod
    def should_query_ai(score: float, current_position: Optional[Dict],
                        volatility: float) -> bool:
        """AI 질의 필요 여부 판단"""

        # 1. 강한 시그널 (80+ 또는 20-)
        if score >= 80 or score <= 20:
            return True

        # 2. 포지션이 있고 중간 정도 시그널 (40-60 범위 벗어남)
        if current_position and (score >= 60 or score <= 40):
            return True

        # 3. 높은 변동성 상황
        if volatility > 0.03:  # 3% 이상 변동성
            return True

        return False


class HybridTradingSystem:
    """하이브리드 트레이딩 시스템 - 규칙 필터 + AI"""

    def __init__(self, config: Dict):
        self.config = config

        # Gemini AI 초기화
        genai.configure(api_key=config['gemini_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Alpaca 초기화
        self.trading_client = TradingClient(
            config['alpaca_api_key'],
            config['alpaca_secret_key'],
            paper=config.get('paper_trading', True)
        )
        self.data_client = StockHistoricalDataClient(
            config['alpaca_api_key'],
            config['alpaca_secret_key']
        )

        self.symbols = config['symbols']
        self.query_interval = config.get('query_interval', 300)  # 5분으로 단축
        self.max_position_size = config.get('max_position_size', 0.2)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.take_profit_pct = config.get('take_profit_pct', 0.05)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)

        # 필터
        self.filter = RuleBasedFilter()

        # 통계
        self.ai_query_count = 0
        self.total_checks = 0
        self.daily_pnl = 0.0
        self.start_equity = self._get_account_equity()
        self.trade_history = []

    def _get_account_equity(self) -> float:
        account = self.trading_client.get_account()
        return float(account.equity)

    def _get_market_data(self, symbol: str, days: int = 5) -> pd.DataFrame:
        try:
            end = datetime.now(pytz.UTC)
            start = end - timedelta(days=days)

            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start,
                end=end
            )

            bars = self.data_client.get_stock_bars(request_params)
            df = bars.df

            if df.empty:
                return pd.DataFrame()

            df = self._calculate_indicators(df)
            return df

        except Exception as e:
            logger.error(f"Market data error for {symbol}: {e}")
            return pd.DataFrame()

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 이동평균
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # 볼린저 밴드
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        return df

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """변동성 계산 (일중 변동률)"""
        if len(df) < 20:
            return 0.0
        recent = df.tail(20)
        return recent['close'].pct_change().std()

    def _get_positions(self) -> Dict:
        positions = self.trading_client.get_all_positions()
        return {pos.symbol: {
            'qty': float(pos.qty),
            'avg_entry_price': float(pos.avg_entry_price),
            'current_price': float(pos.current_price),
            'unrealized_pl': float(pos.unrealized_pl),
            'unrealized_plpc': float(pos.unrealized_plpc)
        } for pos in positions}

    def _create_ai_prompt(self, symbol: str, market_data: pd.DataFrame,
                          positions: Dict, account_equity: float,
                          signal_score: float, signals: Dict) -> str:
        """간소화된 AI 프롬프트 - 규칙 필터 결과 포함"""

        latest = market_data.iloc[-1]
        current_position = positions.get(symbol, None)

        prompt = f"""
전문 트레이더로서 {symbol}의 매매 결정을 내려주세요.

## 자동 분석 결과
- 시그널 스코어: {signal_score:.1f}/100 (80+: 강한 매수, 20-: 강한 매도)
- RSI: {signals['rsi']} ({latest['rsi']:.2f})
- MACD: {signals['macd']}
- 이동평균: {signals['ma']}
- 볼린저밴드: {signals['bb']}

## 현재 상황
- 가격: ${latest['close']:.2f}
- 포지션: {json.dumps(current_position) if current_position else "없음"}
- 계좌 자산: ${account_equity:,.2f}
- 일일 손익: ${self.daily_pnl:,.2f}

## 요청
다음 JSON 형식으로만 응답:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "quantity": <정수>,
    "confidence": <0-100>,
    "reasoning": "<1문장>"
}}

규칙:
- 신뢰도 75% 미만이면 HOLD
- 시그널 스코어를 참고하되, 최종 판단은 당신이 결정
"""
        return prompt

    def _parse_ai_decision(self, response_text: str) -> Optional[Dict]:
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start == -1 or end == 0:
                return None

            json_str = response_text[start:end]
            decision = json.loads(json_str)

            required_fields = ['action', 'quantity', 'confidence']
            if not all(field in decision for field in required_fields):
                return None

            return decision

        except Exception as e:
            logger.error(f"Failed to parse AI decision: {e}")
            return None

    def _execute_rule_based_trade(self, symbol: str, score: float,
                                   signals: Dict, positions: Dict) -> bool:
        """규칙 기반 자동 거래 (AI 없이)"""
        try:
            current_position = positions.get(symbol, None)

            # 간단한 규칙
            action = None
            quantity = 10  # 기본 수량

            # 포지션 없을 때
            if not current_position:
                if score >= 85:  # 매우 강한 매수 시그널
                    action = 'BUY'
            # 포지션 있을 때
            else:
                if score <= 15:  # 매우 강한 매도 시그널
                    action = 'SELL'
                    quantity = int(current_position['qty'])

            if not action:
                return False

            # 주문 실행
            side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(order_data)

            logger.info(f"""
[규칙 기반 거래]
- 종목: {symbol}
- 액션: {action}
- 수량: {quantity}
- 시그널 스코어: {score:.1f}
- 주문 ID: {order.id}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'method': 'rule_based',
                'score': score,
                'signals': signals
            })

            return True

        except Exception as e:
            logger.error(f"Rule-based trade failed: {e}")
            return False

    def _execute_ai_trade(self, symbol: str, decision: Dict) -> bool:
        """AI 기반 거래"""
        try:
            action = decision['action']
            quantity = int(decision['quantity'])

            if action == 'HOLD' or quantity == 0:
                logger.info(f"{symbol}: AI HOLD - {decision.get('reasoning', '')}")
                return True

            side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(order_data)

            logger.info(f"""
[AI 거래]
- 종목: {symbol}
- 액션: {action}
- 수량: {quantity}
- 신뢰도: {decision['confidence']}%
- 이유: {decision.get('reasoning', '')}
- 주문 ID: {order.id}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'method': 'ai_based',
                'confidence': decision['confidence'],
                'reasoning': decision.get('reasoning', '')
            })

            return True

        except Exception as e:
            logger.error(f"AI trade failed: {e}")
            return False

    def process_symbol(self, symbol: str):
        """종목 처리 - 하이브리드 방식"""
        try:
            self.total_checks += 1
            logger.info(f"Processing {symbol}...")

            # 1. 시장 데이터 수집
            market_data = self._get_market_data(symbol)
            if market_data.empty:
                return

            # 2. 규칙 기반 필터링
            signal_score, signals = self.filter.calculate_signal_score(market_data)
            volatility = self._calculate_volatility(market_data)

            positions = self._get_positions()
            current_position = positions.get(symbol, None)

            logger.info(f"{symbol} - Score: {signal_score:.1f}, Signals: {signals}")

            # 3. AI 질의 필요 여부 판단
            need_ai = self.filter.should_query_ai(signal_score, current_position, volatility)

            if need_ai:
                # AI 질의
                self.ai_query_count += 1
                logger.info(f"🤖 Querying AI for {symbol} (Query #{self.ai_query_count})")

                account_equity = self._get_account_equity()
                prompt = self._create_ai_prompt(symbol, market_data, positions,
                                                account_equity, signal_score, signals)

                response = self.model.generate_content(prompt)
                decision = self._parse_ai_decision(response.text)

                if decision and decision['confidence'] >= 75:
                    self._execute_ai_trade(symbol, decision)
            else:
                # 규칙 기반 처리
                logger.info(f"📊 Using rule-based decision for {symbol}")
                self._execute_rule_based_trade(symbol, signal_score, signals, positions)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    def _check_risk_limits(self) -> bool:
        current_equity = self._get_account_equity()
        self.daily_pnl = current_equity - self.start_equity
        daily_loss_pct = self.daily_pnl / self.start_equity

        if daily_loss_pct <= -self.max_daily_loss:
            logger.warning(f"일일 손실 한도 도달: {daily_loss_pct*100:.2f}%")
            return False
        return True

    def _is_market_open(self) -> bool:
        clock = self.trading_client.get_clock()
        return clock.is_open

    def run(self):
        """메인 실행 루프"""
        logger.info("=== Hybrid AI Trading System Started ===")
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Query Interval: {self.query_interval}s")

        try:
            while True:
                if not self._is_market_open():
                    logger.info("Market closed. Waiting...")
                    time.sleep(300)
                    continue

                if not self._check_risk_limits():
                    logger.warning("Risk limit reached.")
                    time.sleep(3600)
                    continue

                # 각 종목 처리
                for symbol in self.symbols:
                    self.process_symbol(symbol)
                    time.sleep(2)

                # 통계 출력
                ai_usage_rate = (self.ai_query_count / max(self.total_checks, 1)) * 100
                logger.info(f"""
📊 System Stats:
- Total Checks: {self.total_checks}
- AI Queries: {self.ai_query_count}
- AI Usage Rate: {ai_usage_rate:.1f}%
- Daily P&L: ${self.daily_pnl:,.2f}
                """)

                time.sleep(self.query_interval)

        except KeyboardInterrupt:
            logger.info("System stopped")
        finally:
            self._save_trade_history()

    def _save_trade_history(self):
        filename = f"trades_hybrid_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump({
                'trades': self.trade_history,
                'stats': {
                    'total_checks': self.total_checks,
                    'ai_queries': self.ai_query_count,
                    'ai_usage_rate': (self.ai_query_count / max(self.total_checks, 1)) * 100
                }
            }, f, indent=2)
        logger.info(f"Trade history saved to {filename}")


def main():
    config = {
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'alpaca_api_key': os.getenv('ALPACA_API_KEY'),
        'alpaca_secret_key': os.getenv('ALPACA_SECRET_KEY'),

        'symbols': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],

        # 5분 간격으로 체크하되, AI는 필요시만 호출
        'query_interval': 300,
        'max_position_size': 0.15,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_daily_loss': 0.05,
        'paper_trading': True
    }

    system = HybridTradingSystem(config)
    system.run()


if __name__ == "__main__":
    main()