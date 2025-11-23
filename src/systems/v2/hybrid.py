# hybrid_trading_system_v2.py
"""개선된 하이브리드 시스템 - 동적 스코어링 + 손절/익절 자동화"""
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
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


class ImprovedRuleBasedFilter:
    """개선된 규칙 기반 필터 - 동적 스코어링"""

    @staticmethod
    def calculate_signal_score(df: pd.DataFrame, volatility: float) -> Tuple[float, Dict]:
        """기술적 지표 기반 시그널 스코어 계산 (0-100)

        변동성에 따라 가중치를 동적으로 조정
        """
        latest = df.iloc[-1]
        signals = {}
        score = 0

        # 변동성 기반 가중치 조정 (높은 변동성 = RSI 더 중요)
        volatility_factor = min(volatility / 0.02, 1.5)  # 최대 1.5배

        # 1. RSI 시그널 (기본 30점)
        rsi_weight = 30 * volatility_factor
        if latest['rsi'] < 30:  # 과매도
            signals['rsi'] = 'oversold'
            score += rsi_weight
        elif latest['rsi'] > 70:  # 과매수
            signals['rsi'] = 'overbought'
            score -= rsi_weight
        elif latest['rsi'] < 40:  # 약한 과매도
            signals['rsi'] = 'weak_oversold'
            score += rsi_weight * 0.5
        elif latest['rsi'] > 60:  # 약한 과매수
            signals['rsi'] = 'weak_overbought'
            score -= rsi_weight * 0.5
        else:
            signals['rsi'] = 'neutral'

        # 2. MACD 시그널 (25점)
        macd_diff = latest['macd'] - latest['signal']
        if macd_diff > 0:
            signals['macd'] = 'bullish'
            # MACD 격차가 클수록 강한 시그널
            strength = min(abs(macd_diff) / 0.5, 1.0)
            score += 25 * strength
        else:
            signals['macd'] = 'bearish'
            strength = min(abs(macd_diff) / 0.5, 1.0)
            score -= 25 * strength

        # 3. 이동평균 시그널 (25점)
        if latest['close'] > latest['sma_20'] > latest['sma_50']:
            signals['ma'] = 'strong_uptrend'
            score += 25
        elif latest['close'] > latest['sma_20']:
            signals['ma'] = 'uptrend'
            score += 15
        elif latest['close'] < latest['sma_20'] < latest['sma_50']:
            signals['ma'] = 'strong_downtrend'
            score -= 25
        elif latest['close'] < latest['sma_20']:
            signals['ma'] = 'downtrend'
            score -= 15
        else:
            signals['ma'] = 'sideways'

        # 4. 볼린저 밴드 시그널 (20점)
        bb_position = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
        if bb_position < 0.2:  # 하단 근처
            signals['bb'] = 'lower_band'
            score += 20
        elif bb_position < 0.3:
            signals['bb'] = 'near_lower'
            score += 10
        elif bb_position > 0.8:  # 상단 근처
            signals['bb'] = 'upper_band'
            score -= 20
        elif bb_position > 0.7:
            signals['bb'] = 'near_upper'
            score -= 10
        else:
            signals['bb'] = 'middle'

        # 정규화 (0-100)
        normalized_score = max(0, min(100, 50 + score))

        signals['raw_score'] = score
        signals['volatility_factor'] = volatility_factor

        return normalized_score, signals

    @staticmethod
    def should_query_ai(score: float, current_position: Optional[Dict],
                        volatility: float) -> Tuple[bool, str]:
        """AI 질의 필요 여부 판단 - 이유도 함께 반환"""

        # 1. 매우 강한 시그널 (75+ 또는 25-)
        if score >= 75:
            return True, 'strong_buy_signal'
        if score <= 25:
            return True, 'strong_sell_signal'

        # 2. 포지션이 있고 중간 정도 시그널 (35-65 범위 벗어남)
        if current_position:
            if score >= 65:
                return True, 'position_exit_signal_bullish'
            if score <= 35:
                return True, 'position_exit_signal_bearish'

        # 3. 높은 변동성 + 중간 정도 시그널
        if volatility > 0.025:  # 2.5% 이상
            if score >= 60 or score <= 40:
                return True, 'high_volatility'

        return False, 'no_significant_signal'

    @staticmethod
    def make_rule_based_decision(score: float, signals: Dict,
                                  current_position: Optional[Dict]) -> Optional[Dict]:
        """규칙 기반 자동 거래 결정 (AI 없이)"""

        # 포지션 없을 때 - 매수 조건 완화
        if not current_position:
            if score >= 70:  # 70점 이상 (기존 85에서 완화)
                return {
                    'action': 'BUY',
                    'quantity': 10,
                    'confidence': int(score),
                    'reasoning': f'Strong buy signal: {signals}'
                }

        # 포지션 있을 때 - 매도 조건 완화
        else:
            if score <= 30:  # 30점 이하 (기존 15에서 완화)
                qty = int(current_position.get('qty', 10))
                return {
                    'action': 'SELL',
                    'quantity': qty,
                    'confidence': int(100 - score),
                    'reasoning': f'Strong sell signal: {signals}'
                }

        return None


class ImprovedHybridSystem:
    """개선된 하이브리드 트레이딩 시스템"""

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
        self.query_interval = config.get('query_interval', 300)
        self.max_position_size = config.get('max_position_size', 0.2)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.take_profit_pct = config.get('take_profit_pct', 0.05)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)

        # 필터
        self.filter = ImprovedRuleBasedFilter()

        # 포지션 추적
        self.position_tracker = {}

        # 통계
        self.ai_query_count = 0
        self.rule_based_trades = 0
        self.rule_based_exits = 0
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
        """변동성 계산"""
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

    def _update_position_tracker(self, symbol: str, action: str, quantity: int, price: float):
        """포지션 추적기 업데이트"""
        if action == 'BUY':
            self.position_tracker[symbol] = {
                'entry_price': price,
                'stop_loss': price * (1 - self.stop_loss_pct),
                'take_profit': price * (1 + self.take_profit_pct),
                'qty': quantity,
                'entry_time': datetime.now().isoformat()
            }
            logger.info(f"""
📍 Position Opened: {symbol}
- Entry: ${price:.2f}
- Stop Loss: ${self.position_tracker[symbol]['stop_loss']:.2f}
- Take Profit: ${self.position_tracker[symbol]['take_profit']:.2f}
            """)
        elif action == 'SELL':
            if symbol in self.position_tracker:
                del self.position_tracker[symbol]

    def _check_stop_loss_take_profit(self, symbol: str, current_price: float) -> Optional[Tuple[str, str]]:
        """손절/익절 체크"""
        if symbol not in self.position_tracker:
            return None

        position = self.position_tracker[symbol]

        if current_price <= position['stop_loss']:
            logger.warning(f"🛑 STOP LOSS: {symbol}")
            return ('SELL', 'stop_loss')

        if current_price >= position['take_profit']:
            logger.info(f"🎯 TAKE PROFIT: {symbol}")
            return ('SELL', 'take_profit')

        return None

    def _execute_rule_based_exit(self, symbol: str, reason: str, current_price: float) -> bool:
        """규칙 기반 청산"""
        try:
            if symbol not in self.position_tracker:
                return False

            quantity = self.position_tracker[symbol]['qty']

            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(order_data)

            entry_price = self.position_tracker[symbol]['entry_price']
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            logger.info(f"""
[규칙 기반 청산]
- 종목: {symbol}
- 수량: {quantity}
- 진입: ${entry_price:.2f} → 청산: ${current_price:.2f}
- 손익: {pnl_pct:+.2f}%
- 이유: {reason}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': 'SELL',
                'quantity': quantity,
                'price': current_price,
                'entry_price': entry_price,
                'pnl_pct': pnl_pct,
                'method': 'rule_based_exit',
                'reason': reason
            })

            self._update_position_tracker(symbol, 'SELL', quantity, current_price)
            self.rule_based_exits += 1

            return True

        except Exception as e:
            logger.error(f"Exit failed: {e}")
            return False

    def _execute_rule_based_trade(self, symbol: str, decision: Dict, score: float,
                                   signals: Dict, current_price: float) -> bool:
        """규칙 기반 거래"""
        try:
            action = decision['action']
            quantity = decision['quantity']

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
- 가격: ${current_price:.2f}
- 스코어: {score:.1f}
- 시그널: {signals}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': current_price,
                'method': 'rule_based',
                'score': score,
                'signals': signals
            })

            self._update_position_tracker(symbol, action, quantity, current_price)
            self.rule_based_trades += 1

            return True

        except Exception as e:
            logger.error(f"Rule-based trade failed: {e}")
            return False

    def _execute_ai_trade(self, symbol: str, decision: Dict, score: float,
                          current_price: float) -> bool:
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
- 가격: ${current_price:.2f}
- 신뢰도: {decision['confidence']}%
- 스코어: {score:.1f}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': current_price,
                'method': 'ai_based',
                'confidence': decision['confidence'],
                'score': score
            })

            self._update_position_tracker(symbol, action, quantity, current_price)

            return True

        except Exception as e:
            logger.error(f"AI trade failed: {e}")
            return False

    def _create_ai_prompt(self, symbol: str, market_data: pd.DataFrame,
                          positions: Dict, account_equity: float,
                          signal_score: float, signals: Dict,
                          query_reason: str) -> str:
        """AI 프롬프트 생성"""
        latest = market_data.iloc[-1]
        current_position = positions.get(symbol, None)

        prompt = f"""
전문 트레이더로서 {symbol}의 매매 결정을 내려주세요.

## 자동 분석 결과
- 시그널 스코어: {signal_score:.1f}/100
- 질의 이유: {query_reason}
- RSI: {signals.get('rsi', 'N/A')} ({latest['rsi']:.2f})
- MACD: {signals.get('macd', 'N/A')}
- 이동평균: {signals.get('ma', 'N/A')}
- 볼린저밴드: {signals.get('bb', 'N/A')}

## 현재 상황
- 가격: ${latest['close']:.2f}
- 포지션: {json.dumps(current_position) if current_position else "없음"}
- 계좌: ${account_equity:,.2f} | 일일 손익: ${self.daily_pnl:,.2f}

## 요청
다음 JSON 형식으로만 응답:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "quantity": <정수>,
    "confidence": <0-100>,
    "reasoning": "<1문장>"
}}

규칙: 신뢰도 75% 미만이면 HOLD
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
            logger.error(f"Parse error: {e}")
            return None

    def process_symbol(self, symbol: str):
        """종목 처리 - 개선된 하이브리드"""
        try:
            self.total_checks += 1
            logger.info(f"Processing {symbol}...")

            # 1. 시장 데이터
            market_data = self._get_market_data(symbol)
            if market_data.empty:
                return

            current_price = market_data.iloc[-1]['close']

            # 2. 손절/익절 체크 (최우선)
            sl_tp_result = self._check_stop_loss_take_profit(symbol, current_price)
            if sl_tp_result:
                action, reason = sl_tp_result
                self._execute_rule_based_exit(symbol, reason, current_price)
                return

            # 3. 규칙 기반 분석
            volatility = self._calculate_volatility(market_data)
            signal_score, signals = self.filter.calculate_signal_score(market_data, volatility)

            positions = self._get_positions()
            current_position = positions.get(symbol, None)

            logger.info(f"{symbol} - Score: {signal_score:.1f}, Volatility: {volatility:.4f}")

            # 4. AI 질의 필요 여부 판단
            need_ai, query_reason = self.filter.should_query_ai(signal_score, current_position, volatility)

            if need_ai:
                # AI 질의
                self.ai_query_count += 1
                logger.info(f"🤖 AI Query: {symbol} ({query_reason}) [#{self.ai_query_count}]")

                account_equity = self._get_account_equity()
                prompt = self._create_ai_prompt(symbol, market_data, positions,
                                                account_equity, signal_score, signals,
                                                query_reason)

                response = self.model.generate_content(prompt)
                decision = self._parse_ai_decision(response.text)

                if decision and decision['confidence'] >= 75:
                    self._execute_ai_trade(symbol, decision, signal_score, current_price)

            else:
                # 규칙 기반 처리
                logger.info(f"📊 Rule-based: {symbol}")
                rule_decision = self.filter.make_rule_based_decision(
                    signal_score, signals, current_position
                )

                if rule_decision:
                    self._execute_rule_based_trade(symbol, rule_decision,
                                                   signal_score, signals, current_price)

        except Exception as e:
            logger.error(f"Error: {symbol}: {e}")

    def _check_risk_limits(self) -> bool:
        current_equity = self._get_account_equity()
        self.daily_pnl = current_equity - self.start_equity
        daily_loss_pct = self.daily_pnl / self.start_equity

        if daily_loss_pct <= -self.max_daily_loss:
            logger.warning(f"일일 손실 한도: {daily_loss_pct*100:.2f}%")
            return False
        return True

    def _is_market_open(self) -> bool:
        clock = self.trading_client.get_clock()
        return clock.is_open

    def run(self):
        """메인 실행"""
        logger.info("=== Improved Hybrid Trading System Started ===")
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Interval: {self.query_interval}s")

        try:
            while True:
                if not self._is_market_open():
                    logger.info("Market closed...")
                    time.sleep(300)
                    continue

                if not self._check_risk_limits():
                    logger.warning("Risk limit reached")
                    time.sleep(3600)
                    continue

                for symbol in self.symbols:
                    self.process_symbol(symbol)
                    time.sleep(2)

                ai_rate = (self.ai_query_count / max(self.total_checks, 1)) * 100
                logger.info(f"""
📊 System Stats:
- Total Checks: {self.total_checks}
- AI Queries: {self.ai_query_count} ({ai_rate:.1f}%)
- Rule Trades: {self.rule_based_trades}
- Rule Exits: {self.rule_based_exits}
- Active Positions: {len(self.position_tracker)}
- Daily P&L: ${self.daily_pnl:,.2f}
                """)

                time.sleep(self.query_interval)

        except KeyboardInterrupt:
            logger.info("Stopped")
        finally:
            self._save_trade_history()

    def _save_trade_history(self):
        filename = f"trades_improved_hybrid_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump({
                'trades': self.trade_history,
                'stats': {
                    'total_checks': self.total_checks,
                    'ai_queries': self.ai_query_count,
                    'rule_based_trades': self.rule_based_trades,
                    'rule_based_exits': self.rule_based_exits,
                    'ai_usage_rate': (self.ai_query_count / max(self.total_checks, 1)) * 100
                }
            }, f, indent=2)
        logger.info(f"Saved: {filename}")


def main():
    config = {
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'alpaca_api_key': os.getenv('ALPACA_API_KEY'),
        'alpaca_secret_key': os.getenv('ALPACA_SECRET_KEY'),

        'symbols': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],

        'query_interval': 300,
        'max_position_size': 0.15,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_daily_loss': 0.05,
        'paper_trading': True
    }

    system = ImprovedHybridSystem(config)
    system.run()


if __name__ == "__main__":
    main()