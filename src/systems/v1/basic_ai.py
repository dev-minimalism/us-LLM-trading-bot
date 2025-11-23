# main.py
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf
import google.generativeai as genai
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pytz

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AITradingSystem:
    """AI 기반 자동매매 시스템"""

    def __init__(self, config: Dict):
        self.config = config

        # Gemini AI 초기화
        genai.configure(api_key=config['gemini_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Alpaca 브로커 초기화 (미국 주식 거래)
        self.trading_client = TradingClient(
            config['alpaca_api_key'],
            config['alpaca_secret_key'],
            paper=config.get('paper_trading', True)
        )
        self.data_client = StockHistoricalDataClient(
            config['alpaca_api_key'],
            config['alpaca_secret_key']
        )

        # 거래 파라미터
        self.symbols = config['symbols']  # 거래할 종목 리스트
        self.query_interval = config.get('query_interval', 900)  # 15분 (초 단위)
        self.max_position_size = config.get('max_position_size', 0.2)  # 포트폴리오의 20%
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)  # 2% 손절
        self.take_profit_pct = config.get('take_profit_pct', 0.05)  # 5% 익절
        self.max_daily_loss = config.get('max_daily_loss', 0.05)  # 일일 최대 5% 손실

        # 상태 추적
        self.daily_pnl = 0.0
        self.start_equity = self._get_account_equity()
        self.trade_history = []

    def _get_account_equity(self) -> float:
        """계좌 자산 조회"""
        account = self.trading_client.get_account()
        return float(account.equity)

    def _get_market_data(self, symbol: str, days: int = 5) -> pd.DataFrame:
        """시장 데이터 수집 (기술적 분석용)"""
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

            # 기술적 지표 계산
            df = self._calculate_indicators(df)
            return df

        except Exception as e:
            logger.error(f"Market data error for {symbol}: {e}")
            return pd.DataFrame()

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
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

    def _get_news_sentiment(self, symbol: str) -> str:
        """뉴스 및 센티먼트 수집 (간소화)"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news[:5] if hasattr(ticker, 'news') else []

            news_summary = []
            for item in news:
                news_summary.append({
                    'title': item.get('title', ''),
                    'publisher': item.get('publisher', ''),
                    'link': item.get('link', '')
                })

            return json.dumps(news_summary, indent=2)
        except:
            return "No recent news available"

    def _get_positions(self) -> Dict:
        """현재 포지션 조회"""
        positions = self.trading_client.get_all_positions()
        return {pos.symbol: {
            'qty': float(pos.qty),
            'avg_entry_price': float(pos.avg_entry_price),
            'current_price': float(pos.current_price),
            'unrealized_pl': float(pos.unrealized_pl),
            'unrealized_plpc': float(pos.unrealized_plpc)
        } for pos in positions}

    def _create_ai_prompt(self, symbol: str, market_data: pd.DataFrame,
                          positions: Dict, account_equity: float) -> str:
        """AI에게 전달할 구조화된 프롬프트 생성"""

        # 최근 데이터 추출
        latest = market_data.iloc[-1]
        prev = market_data.iloc[-2] if len(market_data) > 1 else latest

        # 현재 포지션 확인
        current_position = positions.get(symbol, None)

        # 뉴스 정보
        news = self._get_news_sentiment(symbol)

        prompt = f"""
당신은 전문 퀀트 트레이더입니다. 다음 정보를 분석하여 {symbol}에 대한 매매 결정을 내려주세요.

## 시장 데이터 (최신)
- 현재가: ${latest['close']:.2f}
- 이전 종가: ${prev['close']:.2f}
- 변화율: {((latest['close'] - prev['close']) / prev['close'] * 100):.2f}%
- 거래량: {latest['volume']:,.0f}
- RSI(14): {latest['rsi']:.2f}
- MACD: {latest['macd']:.4f}
- Signal: {latest['signal']:.4f}
- 볼린저 밴드: Lower ${latest['bb_lower']:.2f} | Middle ${latest['bb_middle']:.2f} | Upper ${latest['bb_upper']:.2f}
- SMA(20): ${latest['sma_20']:.2f}
- SMA(50): ${latest['sma_50']:.2f}

## 현재 포지션
{json.dumps(current_position, indent=2) if current_position else "포지션 없음"}

## 계좌 정보
- 총 자산: ${account_equity:,.2f}
- 일일 손익: ${self.daily_pnl:,.2f}
- 최대 포지션 크기: {self.max_position_size * 100}% (${account_equity * self.max_position_size:,.2f})

## 최근 뉴스
{news}

## 리스크 파라미터
- 손절: {self.stop_loss_pct * 100}%
- 익절: {self.take_profit_pct * 100}%
- 일일 최대 손실: {self.max_daily_loss * 100}%

## 요청사항
다음 형식의 JSON으로만 응답해주세요:

{{
    "action": "BUY" | "SELL" | "HOLD",
    "quantity": <매매할 주식 수, 정수>,
    "confidence": <0-100, 신뢰도>,
    "reasoning": "<간단한 이유, 3문장 이내>",
    "stop_loss": <손절가격, 숫자>,
    "take_profit": <익절가격, 숫자>
}}

규칙:
1. 이미 손실 한도에 도달했으면 절대 매수하지 마세요
2. 기술적 지표, 뉴스, 리스크를 종합적으로 고려하세요
3. 과도한 거래를 지양하세요 (신뢰도 70% 이상에서만 거래)
"""
        return prompt

    def _parse_ai_decision(self, response_text: str) -> Optional[Dict]:
        """AI 응답 파싱"""
        try:
            # JSON 추출
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start == -1 or end == 0:
                return None

            json_str = response_text[start:end]
            decision = json.loads(json_str)

            # 유효성 검증
            required_fields = ['action', 'quantity', 'confidence', 'reasoning']
            if not all(field in decision for field in required_fields):
                return None

            return decision

        except Exception as e:
            logger.error(f"Failed to parse AI decision: {e}")
            return None

    def _execute_trade(self, symbol: str, decision: Dict) -> bool:
        """실제 거래 실행"""
        try:
            action = decision['action']
            quantity = int(decision['quantity'])

            if action == 'HOLD' or quantity == 0:
                logger.info(f"{symbol}: HOLD - {decision['reasoning']}")
                return True

            # 주문 생성
            side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL

            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(order_data)

            logger.info(f"""
거래 실행:
- 종목: {symbol}
- 액션: {action}
- 수량: {quantity}
- 신뢰도: {decision['confidence']}%
- 이유: {decision['reasoning']}
- 주문 ID: {order.id}
            """)

            # 거래 기록
            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'confidence': decision['confidence'],
                'reasoning': decision['reasoning']
            })

            return True

        except Exception as e:
            logger.error(f"Trade execution failed for {symbol}: {e}")
            return False

    def _check_risk_limits(self) -> bool:
        """리스크 한도 체크"""
        current_equity = self._get_account_equity()
        self.daily_pnl = current_equity - self.start_equity
        daily_loss_pct = self.daily_pnl / self.start_equity

        if daily_loss_pct <= -self.max_daily_loss:
            logger.warning(f"일일 손실 한도 도달: {daily_loss_pct*100:.2f}%")
            return False

        return True

    def _is_market_open(self) -> bool:
        """미국 시장 오픈 확인"""
        clock = self.trading_client.get_clock()
        return clock.is_open

    def process_symbol(self, symbol: str):
        """개별 종목 처리"""
        try:
            logger.info(f"Processing {symbol}...")

            # 1. 시장 데이터 수집
            market_data = self._get_market_data(symbol)
            if market_data.empty:
                logger.warning(f"No data for {symbol}")
                return

            # 2. 포지션 및 계좌 정보
            positions = self._get_positions()
            account_equity = self._get_account_equity()

            # 3. AI 프롬프트 생성
            prompt = self._create_ai_prompt(symbol, market_data, positions, account_equity)

            # 4. AI에게 질의
            logger.info(f"Querying AI for {symbol}...")
            response = self.model.generate_content(prompt)

            # 5. 응답 파싱
            decision = self._parse_ai_decision(response.text)
            if not decision:
                logger.error(f"Invalid AI response for {symbol}")
                return

            # 6. 신뢰도 체크
            if decision['confidence'] < 70:
                logger.info(f"{symbol}: Low confidence ({decision['confidence']}%), skipping")
                return

            # 7. 거래 실행
            self._execute_trade(symbol, decision)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    def run(self):
        """메인 실행 루프"""
        logger.info("=== AI Trading System Started ===")
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Query Interval: {self.query_interval}s ({self.query_interval/60:.1f} min)")
        logger.info(f"Paper Trading: {self.config.get('paper_trading', True)}")

        try:
            while True:
                # 시장 오픈 확인
                if not self._is_market_open():
                    logger.info("Market is closed. Waiting...")
                    time.sleep(300)  # 5분 대기
                    continue

                # 리스크 한도 체크
                if not self._check_risk_limits():
                    logger.warning("Risk limit reached. Stopping trading for today.")
                    time.sleep(3600)  # 1시간 대기 후 재확인
                    continue

                # 각 종목 처리
                for symbol in self.symbols:
                    self.process_symbol(symbol)
                    time.sleep(2)  # API 레이트 리미트 방지

                # 다음 주기까지 대기
                logger.info(f"Waiting {self.query_interval}s until next cycle...")
                time.sleep(self.query_interval)

        except KeyboardInterrupt:
            logger.info("System stopped by user")
        except Exception as e:
            logger.error(f"System error: {e}")
        finally:
            self._save_trade_history()

    def _save_trade_history(self):
        """거래 기록 저장"""
        filename = f"trades_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump(self.trade_history, f, indent=2)
        logger.info(f"Trade history saved to {filename}")


def main():
    """메인 함수"""

    # 설정
    config = {
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'alpaca_api_key': os.getenv('ALPACA_API_KEY'),
        'alpaca_secret_key': os.getenv('ALPACA_SECRET_KEY'),

        # 거래 종목 (예시)
        'symbols': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],

        # 거래 파라미터
        'query_interval': 900,  # 15분
        'max_position_size': 0.15,  # 포트폴리오의 15%
        'stop_loss_pct': 0.02,  # 2% 손절
        'take_profit_pct': 0.05,  # 5% 익절
        'max_daily_loss': 0.05,  # 일일 최대 5% 손실

        # 페이퍼 트레이딩 (실제 돈 사용 X)
        'paper_trading': True
    }

    # 시스템 시작
    system = AITradingSystem(config)
    system.run()


if __name__ == "__main__":
    main()