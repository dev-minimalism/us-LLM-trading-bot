# event_driven_system.py
"""중요한 이벤트 발생 시에만 AI 호출"""
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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


class EventDrivenSystem:
    """이벤트 기반 트레이딩 시스템 - 중요 이벤트 발생 시에만 AI 호출"""

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
        self.query_interval = config.get('query_interval', 300)  # 5분
        self.max_position_size = config.get('max_position_size', 0.2)
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)
        self.take_profit_pct = config.get('take_profit_pct', 0.05)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)

        # 이벤트 추적
        self.last_ai_query = {}  # 종목별 마지막 AI 질의 시간
        self.last_prices = {}  # 종목별 마지막 가격

        # 통계
        self.ai_query_count = 0
        self.total_checks = 0
        self.event_counts = {
            'price_spike': 0,
            'volume_spike': 0,
            'crossover': 0,
            'position_alert': 0,
            'scheduled': 0
        }
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

    def _get_positions(self) -> Dict:
        positions = self.trading_client.get_all_positions()
        return {pos.symbol: {
            'qty': float(pos.qty),
            'avg_entry_price': float(pos.avg_entry_price),
            'current_price': float(pos.current_price),
            'unrealized_pl': float(pos.unrealized_pl),
            'unrealized_plpc': float(pos.unrealized_plpc)
        } for pos in positions}

    def _get_price_change(self, symbol: str, market_data: pd.DataFrame) -> float:
        """가격 변화율 계산"""
        if len(market_data) < 2:
            return 0.0

        current_price = market_data.iloc[-1]['close']
        last_price = self.last_prices.get(symbol)

        if last_price is None:
            self.last_prices[symbol] = current_price
            return 0.0

        change = (current_price - last_price) / last_price
        self.last_prices[symbol] = current_price
        return change

    def _detect_volume_spike(self, market_data: pd.DataFrame) -> bool:
        """거래량 급증 감지"""
        if len(market_data) < 20:
            return False

        recent = market_data.tail(20)
        avg_volume = recent['volume'].mean()
        current_volume = market_data.iloc[-1]['volume']

        return current_volume >= avg_volume * 2

    def _detect_crossover(self, market_data: pd.DataFrame) -> Optional[str]:
        """기술적 지표 크로스오버 감지"""
        if len(market_data) < 2:
            return None

        current = market_data.iloc[-1]
        prev = market_data.iloc[-2]

        # MACD 크로스오버
        if prev['macd'] <= prev['signal'] and current['macd'] > current['signal']:
            return 'macd_bullish'
        if prev['macd'] >= prev['signal'] and current['macd'] < current['signal']:
            return 'macd_bearish'

        # 이동평균 크로스오버
        if prev['sma_20'] <= prev['sma_50'] and current['sma_20'] > current['sma_50']:
            return 'ma_golden_cross'
        if prev['sma_20'] >= prev['sma_50'] and current['sma_20'] < current['sma_50']:
            return 'ma_death_cross'

        return None

    def _check_position_alert(self, symbol: str) -> bool:
        """포지션 손익 알림 체크"""
        positions = self._get_positions()
        position = positions.get(symbol)

        if not position:
            return False

        unrealized_plpc = position['unrealized_plpc']
        return abs(unrealized_plpc) >= 0.03  # ±3% 이상

    def should_query_ai(self, symbol: str, market_data: pd.DataFrame) -> Optional[str]:
        """이벤트 발생 시에만 True 반환하고 이벤트 종류 반환"""

        # 1. 가격 급변 (5% 이상)
        price_change = self._get_price_change(symbol, market_data)
        if abs(price_change) >= 0.05:
            logger.info(f"{symbol}: 가격 급변 감지 ({price_change*100:.1f}%)")
            self.event_counts['price_spike'] += 1
            return 'price_spike'

        # 2. 거래량 급증 (평균의 2배 이상)
        volume_spike = self._detect_volume_spike(market_data)
        if volume_spike:
            logger.info(f"{symbol}: 거래량 급증 감지")
            self.event_counts['volume_spike'] += 1
            return 'volume_spike'

        # 3. 기술적 지표 크로스오버
        crossover = self._detect_crossover(market_data)
        if crossover:
            logger.info(f"{symbol}: 크로스오버 감지 - {crossover}")
            self.event_counts['crossover'] += 1
            return f'crossover_{crossover}'

        # 4. 포지션 있고 손익 ±3% 이상
        position_alert = self._check_position_alert(symbol)
        if position_alert:
            logger.info(f"{symbol}: 포지션 알림")
            self.event_counts['position_alert'] += 1
            return 'position_alert'

        # 5. 마지막 AI 질의 후 2시간 경과 (정기 체크)
        last_query = self.last_ai_query.get(symbol)
        if last_query is None or (datetime.now() - last_query).seconds > 7200:
            logger.info(f"{symbol}: 정기 체크")
            self.event_counts['scheduled'] += 1
            return 'scheduled'

        return None

    def _create_ai_prompt(self, symbol: str, market_data: pd.DataFrame,
                          positions: Dict, account_equity: float,
                          event_type: str) -> str:
        """이벤트 기반 AI 프롬프트 생성"""

        latest = market_data.iloc[-1]
        current_position = positions.get(symbol, None)

        prompt = f"""
전문 트레이더로서 {symbol}의 매매 결정을 내려주세요.

## 이벤트 발생
**{event_type}** 이벤트가 감지되었습니다.

## 시장 데이터
- 현재가: ${latest['close']:.2f}
- RSI: {latest['rsi']:.2f}
- MACD: {latest['macd']:.4f} / Signal: {latest['signal']:.4f}
- SMA(20): ${latest['sma_20']:.2f} / SMA(50): ${latest['sma_50']:.2f}
- 볼린저밴드: ${latest['bb_lower']:.2f} - ${latest['bb_upper']:.2f}

## 현재 상황
- 포지션: {json.dumps(current_position) if current_position else "없음"}
- 계좌 자산: ${account_equity:,.2f}
- 일일 손익: ${self.daily_pnl:,.2f}

## 요청
다음 JSON 형식으로만 응답:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "quantity": <정수>,
    "confidence": <0-100>,
    "reasoning": "<1-2문장>"
}}

규칙:
- 이벤트를 고려하여 결정하세요
- 신뢰도 70% 미만이면 HOLD
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

    def _execute_trade(self, symbol: str, decision: Dict, event_type: str) -> bool:
        """거래 실행"""
        try:
            action = decision['action']
            quantity = int(decision['quantity'])

            if action == 'HOLD' or quantity == 0:
                logger.info(f"{symbol}: HOLD - {decision.get('reasoning', '')}")
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
[이벤트 기반 거래]
- 종목: {symbol}
- 액션: {action}
- 수량: {quantity}
- 신뢰도: {decision['confidence']}%
- 이벤트: {event_type}
- 이유: {decision.get('reasoning', '')}
- 주문 ID: {order.id}
            """)

            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'event_type': event_type,
                'confidence': decision['confidence'],
                'reasoning': decision.get('reasoning', '')
            })

            return True

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return False

    def process_symbol(self, symbol: str):
        """종목 처리 - 이벤트 기반"""
        try:
            self.total_checks += 1
            logger.info(f"Checking {symbol}...")

            # 1. 시장 데이터 수집
            market_data = self._get_market_data(symbol)
            if market_data.empty:
                return

            # 2. 이벤트 체크
            event_type = self.should_query_ai(symbol, market_data)

            if event_type:
                # 이벤트 발생 - AI 질의
                self.ai_query_count += 1
                self.last_ai_query[symbol] = datetime.now()

                logger.info(f"🚨 Event detected for {symbol}: {event_type} (AI Query #{self.ai_query_count})")

                positions = self._get_positions()
                account_equity = self._get_account_equity()

                prompt = self._create_ai_prompt(symbol, market_data, positions,
                                                account_equity, event_type)

                response = self.model.generate_content(prompt)
                decision = self._parse_ai_decision(response.text)

                if decision and decision['confidence'] >= 70:
                    self._execute_trade(symbol, decision, event_type)
            else:
                logger.info(f"✓ {symbol}: No significant events")

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
        logger.info("=== Event-Driven AI Trading System Started ===")
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
- Event Breakdown: {self.event_counts}
- Daily P&L: ${self.daily_pnl:,.2f}
                """)

                time.sleep(self.query_interval)

        except KeyboardInterrupt:
            logger.info("System stopped")
        finally:
            self._save_trade_history()

    def _save_trade_history(self):
        filename = f"trades_event_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump({
                'trades': self.trade_history,
                'stats': {
                    'total_checks': self.total_checks,
                    'ai_queries': self.ai_query_count,
                    'ai_usage_rate': (self.ai_query_count / max(self.total_checks, 1)) * 100,
                    'event_counts': self.event_counts
                }
            }, f, indent=2)
        logger.info(f"Trade history saved to {filename}")


def main():
    config = {
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'alpaca_api_key': os.getenv('ALPACA_API_KEY'),
        'alpaca_secret_key': os.getenv('ALPACA_SECRET_KEY'),

        'symbols': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],

        # 5분 간격으로 체크하되, 이벤트 발생 시에만 AI 호출
        'query_interval': 300,
        'max_position_size': 0.15,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'max_daily_loss': 0.05,
        'paper_trading': True
    }

    system = EventDrivenSystem(config)
    system.run()


if __name__ == "__main__":
    main()