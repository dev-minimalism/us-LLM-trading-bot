# AI 기반 미국 주식 자동매매 시스템 V2

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

Gemini AI와 Alpaca 브로커를 활용한 실전 가능한 자동매매 시스템입니다.

> **English:** An AI-powered US stock trading bot built on Gemini and the Alpaca broker. Event-driven and hybrid (rule + AI) strategies with automatic stop-loss/take-profit, five risk profiles, and paper trading by default. See [CLAUDE.md](CLAUDE.md) for an architecture walkthrough.

## 목차

- [빠른 시작](#-빠른-시작-5분)
- [프로젝트 구조](#-프로젝트-구조)
- [시스템 설명](#-시스템-설명)
- [설정 및 실행](#-설정-및-실행)
- [전략 프로필](#-전략-프로필)
- [실행 방법](#-실행-방법)
- [백테스팅](#-백테스팅)
- [모니터링](#-모니터링)
- [개발자 가이드](#-개발자-가이드)
- [문제 해결](#-문제-해결)
- [주의사항](#️-주의사항)

---

## 🚀 빠른 시작 (5분)

### 1단계: 환경 설정 (2분)
```bash
# 1. .env 파일 생성
cp .env.example .env

# 2. .env 파일 편집하여 API 키 입력
# GEMINI_API_KEY=your_key_here
# ALPACA_API_KEY=your_key_here
# ALPACA_SECRET_KEY=your_key_here
```

`.env` 파일은 `src` 패키지를 임포트할 때 자동으로 로드되므로(python-dotenv), 환경변수를 따로 export할 필요가 없습니다.

**API 키 발급:**
- **Gemini**: [Google AI Studio](https://makersuite.google.com/app/apikey) → Create API Key
- **Alpaca**: [Alpaca Markets](https://alpaca.markets/) → Paper Trading 계정 생성 → API Keys

### 2단계: 패키지 설치 (2분)
```bash
pip install -r requirements.txt
```

### 3단계: 시스템 실행 (1분)
```bash
# V2 이벤트 기반 (추천 - 최고 효율)
python scripts/run_v2_event_driven.py

# 또는 V2 하이브리드 (균형잡힌)
python scripts/run_v2_hybrid.py
```

---

## 📦 프로젝트 구조

```
us-LLM-trading-bot/
├── src/                              # 소스 코드 패키지
│   ├── systems/                     # 트레이딩 시스템
│   │   ├── v1/                     # V1 시스템 (기본 구현)
│   │   │   ├── basic_ai.py        # 기본 AI 시스템
│   │   │   ├── hybrid.py          # 하이브리드 시스템
│   │   │   └── event_driven.py    # 이벤트 기반 시스템
│   │   └── v2/                     # V2 시스템 (개선, 추천)
│   │       ├── event_driven.py    # 개선된 이벤트 기반
│   │       └── hybrid.py          # 개선된 하이브리드
│   ├── config/                     # 설정 관리
│   │   └── trading_config.py      # TradingConfig 클래스
│   └── utils/                      # 유틸리티
│       └── backtest.py            # 백테스팅 도구
│
├── scripts/                         # 실행 스크립트
│   ├── run_v2_event_driven.py     # V2 이벤트 기반 실행
│   ├── run_v2_hybrid.py           # V2 하이브리드 실행
│   └── run_backtest.py            # 백테스트 분석
│
├── tests/                          # 테스트 (현재 비어 있음)
│   └── __init__.py
│
├── CLAUDE.md                       # 아키텍처 및 개발 가이드 (Claude Code용)
├── LICENSE                         # MIT 라이선스
├── setup.py                        # 패키지 설치 설정
├── requirements.txt                # Python 패키지 의존성
├── .env.example                    # 환경변수 예시
└── .gitignore                      # Git 제외 파일
```

### 패키지별 설명

**src/systems/** - 트레이딩 시스템
- **V1 시스템**: 기본 구현, 교육/참고용
  - `basic_ai.py`: AI가 모든 결정 (15분 간격)
  - `hybrid.py`: 규칙 필터 + AI (80% AI 절감)
  - `event_driven.py`: 이벤트시에만 AI (88% AI 절감)
- **V2 시스템**: 개선 버전, **프로덕션 추천**
  - `event_driven.py`: 자동 손절/익절 + 이벤트 기반 (92% AI 절감)
  - `hybrid.py`: 동적 스코어링 + 자동 손절/익절 (85% AI 절감)

**src/config/** - 설정 관리
- `TradingConfig` 클래스로 중앙 관리
- 5가지 전략 프로필: conservative, moderate, aggressive, scalping, swing
- 3가지 종목 세트: DEFAULT, LARGE_CAP, TECH

**src/utils/** - 유틸리티
- `Backtester` 클래스: 거래 기록 분석 및 성과 리포트

---

## 🎯 시스템 설명

### V2 시스템 주요 개선사항

- ✅ **손절/익절 자동 실행**: AI 없이 가격 도달 시 즉시 처리
- ✅ **포지션 추적 강화**: 진입가, 손절가, 익절가 자동 관리
- ✅ **규칙 기반 자동 대응**: 명확한 상황에서 AI 없이 즉시 거래
- ✅ **동적 스코어링**: 변동성에 따라 가중치 자동 조정
- ✅ **긴급 상황 감지**: 급격한 손실 시 자동 청산
- ✅ **5가지 전략 프로필**: 투자 성향별 선택 가능

### V2 이벤트 기반 시스템 (추천)

**장점:**
- 최고의 AI 비용 효율 (92% 절감)
- 명확한 트리거 (가격 급변, 거래량 급증, 크로스오버)
- 감정적 거래 완전 배제
- 오버트레이딩 방지

**자동 처리 항목:**
1. 손절가 도달 → 즉시 청산 (AI 없이)
2. 익절가 도달 → 즉시 청산 (AI 없이)
3. 급격한 손실 (-5%) → 긴급 청산 (AI 없이)
4. 명확한 이벤트 → AI 질의

**이벤트 트리거:**
- 가격 급변 (5% 이상)
- 거래량 급증 (평균의 2배 이상)
- 기술적 지표 크로스오버 (MACD, 이동평균)
- 포지션 손익 ±3% 이상
- 정기 체크 (2시간마다)

**통계 예시:**
```
- Total Checks: 180
- AI Queries: 22 (12% 사용)
- Rule-Based Exits: 8
- Active Positions: 2
- Daily P&L: +$125.50
```

### V2 하이브리드 시스템

**장점:**
- 규칙 + AI의 균형
- 동적 스코어링 (변동성 반영)
- 더 세밀한 시그널 분석
- 손절/익절 자동 실행

**스코어 기반 자동 거래:**
- 스코어 70+ → 자동 매수 (AI 없이)
- 스코어 30- → 자동 매도 (AI 없이)
- 스코어 75+/25- → AI 질의
- 포지션 있고 스코어 65+/35- → AI 질의

**동적 스코어링:**
```python
# 변동성에 따라 RSI 가중치 자동 조정
volatility_factor = min(volatility / 0.02, 1.5)
rsi_weight = 30 * volatility_factor  # 30 ~ 45점
```

**통계 예시:**
```
- Total Checks: 180
- AI Queries: 35 (19% 사용)
- Rule Trades: 12
- Rule Exits: 8
- Active Positions: 3
```

### V1 vs V2 비교

| 항목 | V1 | V2 |
|------|----|----|
| 손절/익절 | 수동/AI 의존 | **자동 실행** |
| 포지션 관리 | 기본 추적 | **상세 추적** (진입가, 손절가, 익절가) |
| 긴급 대응 | AI 질의 필요 | **즉시 자동 청산** |
| 규칙 기반 거래 | 제한적 (85/15) | **완화 및 강화** (70/30) |
| 스코어링 | 고정 가중치 | **동적 가중치** (변동성 반영) |
| 설정 관리 | 코드 내 직접 수정 | **trading_config.py** (5가지 프로필) |
| AI 비용 절감 | 80-88% | **85-92%** |

---

## ⚙️ 설정 및 실행

### 패키지 설치

```bash
# 개발 모드로 설치 (코드 변경사항 즉시 반영)
pip install -e .

# 또는 의존성만 설치
pip install -r requirements.txt
```

### 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# API 키 입력
nano .env
```

`.env` 파일 내용:
```
GEMINI_API_KEY=your_gemini_api_key_here
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
```

---

## 🎲 전략 프로필

### 1. Conservative (보수적)
```python
config = TradingConfig.get_config(strategy='conservative')
```
- **포지션 크기**: 10%
- **손절**: 1.5% / **익절**: 3%
- **일일 최대 손실**: 3%
- **체크 간격**: 5분
- **추천 대상**: 초보자, 안정성 중시

### 2. Moderate (중도적) - 기본값
```python
config = TradingConfig.get_config(strategy='moderate')
```
- **포지션 크기**: 15%
- **손절**: 2% / **익절**: 5%
- **일일 최대 손실**: 5%
- **체크 간격**: 5분
- **추천 대상**: 일반 투자자

### 3. Aggressive (공격적)
```python
config = TradingConfig.get_config(strategy='aggressive')
```
- **포지션 크기**: 20%
- **손절**: 3% / **익절**: 8%
- **일일 최대 손실**: 8%
- **체크 간격**: 5분
- **추천 대상**: 경험 많은 투자자, 높은 리스크 감수

### 4. Scalping (스캘핑)
```python
config = TradingConfig.get_config(strategy='scalping')
```
- **포지션 크기**: 10%
- **손절**: 0.5% / **익절**: 1%
- **일일 최대 손실**: 3%
- **체크 간격**: 3분
- **추천 대상**: 빠른 매매 선호, 높은 거래 빈도

### 5. Swing (스윙)
```python
config = TradingConfig.get_config(strategy='swing')
```
- **포지션 크기**: 25%
- **손절**: 5% / **익절**: 15%
- **일일 최대 손실**: 10%
- **체크 간격**: 15분
- **추천 대상**: 중장기 투자, 큰 수익 목표

### 종목 세트

```python
# 기본 종목
TradingConfig.DEFAULT_SYMBOLS   # ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

# 대형주 (안정적)
TradingConfig.LARGE_CAP_SYMBOLS # ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

# 테크주 (변동성)
TradingConfig.TECH_SYMBOLS      # ['NVDA', 'AMD', 'TSLA', 'PLTR', 'COIN']
```

---

## 🏃 실행 방법

### 방법 1: 실행 스크립트 (가장 쉬움, 추천)

```bash
# V2 이벤트 기반 (최고 효율)
python scripts/run_v2_event_driven.py

# V2 하이브리드 (균형잡힌)
python scripts/run_v2_hybrid.py

# 백테스트 분석
python scripts/run_backtest.py
```

**스크립트 특징:**
- 대화형 인터페이스로 전략 선택
- 자동 설정 검증
- 사용자 친화적

### 방법 2: 패키지 임포트

```python
from src.config import TradingConfig
from src.systems.v2 import ImprovedEventDrivenSystem

# 1. 사용 가능한 전략 확인
TradingConfig.print_available_strategies()

# 2. 설정 생성
config = TradingConfig.get_config(
    strategy='moderate',  # conservative, moderate, aggressive, scalping, swing
    symbols=TradingConfig.LARGE_CAP_SYMBOLS,
    paper_trading=True
)

# 3. 설정 검증
TradingConfig.validate_config(config)

# 4. 시스템 시작
system = ImprovedEventDrivenSystem(config)
system.run()
```

### 방법 3: 패키지 설치 후 콘솔 명령어

```bash
# 패키지 설치
pip install -e .

# 콘솔 명령어로 실행
trading-bot-v2-event     # V2 이벤트 기반
trading-bot-v2-hybrid    # V2 하이브리드
trading-bot-v1-basic     # V1 기본 AI
```

### 실전 사용 예시

#### 예시 1: 안정적인 대형주 투자
```python
from src.config import TradingConfig
from src.systems.v2 import ImprovedEventDrivenSystem

config = TradingConfig.get_config(
    strategy='conservative',
    symbols=TradingConfig.LARGE_CAP_SYMBOLS,
    paper_trading=True
)

system = ImprovedEventDrivenSystem(config)
system.run()
```

#### 예시 2: 공격적인 테크주 트레이딩
```python
from src.config import TradingConfig
from src.systems.v2 import ImprovedHybridSystem

config = TradingConfig.get_config(
    strategy='aggressive',
    symbols=TradingConfig.TECH_SYMBOLS,
    paper_trading=True
)

system = ImprovedHybridSystem(config)
system.run()
```

#### 예시 3: 맞춤형 설정
```python
from src.config import TradingConfig
from src.systems.v2 import ImprovedEventDrivenSystem

# 기본 설정으로 시작
config = TradingConfig.get_config(strategy='moderate')

# 일부 파라미터 커스터마이징
config['symbols'] = ['AAPL', 'TSLA', 'NVDA']
config['stop_loss_pct'] = 0.025  # 2.5% 손절
config['query_interval'] = 240   # 4분

system = ImprovedEventDrivenSystem(config)
system.run()
```

---

## 📊 백테스팅

### 백테스트 실행

```bash
# 스크립트 사용
python scripts/run_backtest.py

# 또는 직접 실행
python -c "from src.utils import Backtester; Backtester('trades_improved_event_20241123.json').analyze()"
```

### 거래 기록 파일

자동 저장되는 파일명:
- V1: `trades_<date>.json`, `trades_hybrid_<date>.json`, `trades_event_<date>.json`
- V2: `trades_improved_event_<date>.json`, `trades_improved_hybrid_<date>.json`

### 백테스트 출력 예시

```
============================================================
거래 성과 분석
============================================================
총 거래 수: 58
매수: 28
매도: 30
평균 신뢰도: 84.20%

종목별 거래:
AAPL    15
NVDA    12
MSFT    11
TSLA     10
GOOGL    10

거래 방식:
ai_based            22
rule_based          18
rule_based_exit     18

시스템 통계:
- total_checks: 180
- ai_queries: 22
- rule_based_exits: 18
- ai_usage_rate: 12.2%
============================================================
```

---

## 📈 모니터링

### 실시간 로그 모니터링

```bash
# 실시간 로그 확인
tail -f trading.log

# 거래 내역만
grep "거래\|Exit" trading.log

# 에러 확인
grep ERROR trading.log

# 최근 50줄
tail -n 50 trading.log
```

### 시스템 통계 확인

로그에서 주기적으로 출력:
```
📊 System Stats:
- Total Checks: 180
- AI Queries: 22 (12% 사용)
- Rule-Based Exits: 8
- Active Positions: 2
- Event Breakdown: {'price_spike': 3, 'volume_spike': 5, ...}
- Daily P&L: +$125.50
```

---

## 👨‍💻 개발자 가이드

### 핵심 아키텍처

#### 포지션 추적 시스템

```python
position_tracker = {
    'SYMBOL': {
        'entry_price': float,      # 진입 가격
        'stop_loss': float,        # 자동 계산된 손절가
        'take_profit': float,      # 자동 계산된 익절가
        'qty': int,                # 포지션 크기
        'entry_time': str          # ISO 타임스탬프
    }
}
```

#### 3단계 의사결정 시스템 (V2)

1. **손절/익절 체크** (최우선, AI 없음)
   - 가격 도달 시 즉시 실행
   - `_check_stop_loss_take_profit()` 메서드
2. **긴급 상황** (높은 우선순위, AI 없음)
   - 급격한 손실 감지 (-5% 이상)
   - 극단적 시장 상황 (RSI < 25 + 손실)
3. **AI 질의** (일반 우선순위)
   - 이벤트 또는 시그널 스코어 트리거
   - 복잡한 결정에 사용

#### 처리 순서 (중요)

```python
def process_symbol(self, symbol: str):
    # 1. 시장 데이터 수집
    market_data = self._get_market_data(symbol)
    current_price = market_data.iloc[-1]['close']

    # 2. 최우선: 손절/익절 체크 (AI 없음)
    sl_tp_result = self._check_stop_loss_take_profit(symbol, current_price)
    if sl_tp_result:
        self._execute_rule_based_exit(symbol, reason, current_price)
        return  # 즉시 종료

    # 3. 긴급 상황 체크
    emergency = self._detect_emergency_situation(symbol, market_data)
    if emergency:
        self._execute_rule_based_exit(symbol, f'emergency_{emergency}', current_price)
        return

    # 4. 일반 이벤트 체크 및 AI 질의
    event_type = self.should_query_ai(symbol, market_data)
    if event_type:
        # AI 질의 및 거래 실행
        ...
```

### 기술적 지표 계산

모든 시스템에서 표준화된 지표 사용:

```python
def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
    # RSI (14-period)
    df['rsi'] = ...

    # 이동평균 (SMA 20, 50)
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()

    # MACD (12, 26, 9)
    df['macd'] = ...
    df['signal'] = ...

    # 볼린저 밴드 (20-period, 2 std dev)
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_upper'] = df['bb_middle'] + (std * 2)
    df['bb_lower'] = df['bb_middle'] - (std * 2)

    return df
```

### 거래 기록 구조

```python
trade_record = {
    'timestamp': datetime.now().isoformat(),
    'symbol': 'AAPL',
    'action': 'BUY',  # or 'SELL'
    'quantity': 10,
    'price': 180.50,
    'method': 'ai_based',  # or 'rule_based', 'rule_based_exit'
    'confidence': 85,  # AI만
    'reasoning': '...',  # AI만
    'score': 75.5,  # 하이브리드만
}
```

### 설정 검증

```python
from src.config import TradingConfig

# 설정 생성
config = TradingConfig.get_config(strategy='moderate')

# 검증
if TradingConfig.validate_config(config):
    print("✅ 설정 유효")
else:
    print("❌ 설정 오류")
```

### 일반적인 수정 사항

#### 새로운 전략 프로필 추가

`src/config/trading_config.py` 편집:
```python
STRATEGIES = {
    # 기존 전략들...
    'my_strategy': {
        'description': '나만의 전략',
        'max_position_size': 0.12,
        'stop_loss_pct': 0.025,
        'take_profit_pct': 0.06,
        'max_daily_loss': 0.04,
        'query_interval': 240,
    }
}
```

#### AI 모델 변경

시스템 파일에서:
```python
self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
# 다른 모델로 변경: gemini-pro, gemini-1.5-pro 등
```

#### 규칙 기반 임계값 조정

`src/systems/v2/hybrid.py`의 `make_rule_based_decision()`:
```python
# 매수 임계값 (현재 70)
if score >= 70:  # 이 값 조정
    return {'action': 'BUY', ...}

# 매도 임계값 (현재 30)
if score <= 30:  # 이 값 조정
    return {'action': 'SELL', ...}
```

#### 긴급 청산 조건 수정

`src/systems/v2/event_driven.py`의 `_detect_emergency_situation()`:
```python
# 급격한 손실 임계값 (현재 -5%)
if loss_pct <= -0.05:  # 임계값 조정
    return 'rapid_loss'

# RSI 과매도 임계값 (현재 25)
if latest['rsi'] < 25 and loss_pct < -0.02:
    return 'extreme_oversold'
```

### 안전 메커니즘

1. **Paper Trading 기본값**: 모든 설정이 `paper_trading: True`로 기본 설정
2. **일일 손실 한도**: 일일 손실이 한도 초과 시 거래 중지
3. **시장 시간 체크**: 미국 시장 시간에만 거래 (9:30 AM - 4:00 PM ET)
4. **API 레이트 리미팅**: 종목 처리 간 2초 지연
5. **거래 기록 자동 저장**: 시스템 종료 시 (Ctrl+C) 자동 저장

### 아키텍처 결정

**왜 V1과 V2가 존재하는가?**
- V1: 교육/참고용 구현
- V2: 자동 리스크 관리가 포함된 프로덕션 준비 버전

**왜 position_tracker가 Alpaca positions와 별도인가?**
- Alpaca API에 지연이 있을 수 있음
- 손절 계산을 위해 진입가에 즉시 접근 필요
- 오프라인 테스트/시뮬레이션 가능

**왜 이벤트 기반이 하이브리드보다 권장되는가?**
- 더 낮은 AI 비용 (88-92% vs 85% 절감)
- 더 명확한 트리거 조건
- 오버트레이딩 방지에 유리

---

## 🆘 문제 해결

### "Market is closed" 메시지

미국 주식 시장 시간 확인:
- **동부시간**: 9:30 AM - 4:00 PM (월-금)
- **한국시간**: 23:30 - 06:00 (여름) / 22:30 - 05:00 (겨울)

### API 키 오류

```bash
# 설정 검증
python -c "from src.config import TradingConfig; TradingConfig.validate_config(TradingConfig.get_config())"

# 환경변수 확인
python -c "import os; print(os.getenv('GEMINI_API_KEY'))"
```

### 패키지 설치 오류

```bash
# Python 버전 확인 (3.8 이상 필요)
python --version

# pip 업그레이드
pip install --upgrade pip

# 강제 재설치
pip install -r requirements.txt --force-reinstall
```

### 손절/익절이 작동하지 않음

- `position_tracker` 로그 확인
- 진입 가격이 올바르게 설정되었는지 확인
- 현재가가 손절가/익절가에 실제로 도달했는지 확인

```bash
# 포지션 추적 로그 확인
grep "Position Opened\|Position Closed" trading.log
```

---

## ⚠️ 주의사항

### 반드시 지켜야 할 사항

1. ⚠️ **페이퍼 트레이딩으로 시작**: `paper_trading: True`
2. ⚠️ **충분한 테스트**: 최소 1개월 이상 시뮬레이션
3. ⚠️ **소액으로 시작**: 실제 거래 시 작은 금액부터
4. ⚠️ **리스크 관리**: 손실 한도를 반드시 설정
5. ⚠️ **지속적 모니터링**: 자동화되어도 정기적으로 확인

### AI의 한계

- AI는 완벽하지 않습니다
- 예측 불가능한 시장 상황 존재
- 과거 데이터 기반 판단의 한계
- **손실 가능성 항상 존재**

### V2 시스템 특별 주의사항

- 손절/익절이 자동 실행되므로 파라미터 설정에 주의
- Conservative 전략으로 시작 권장
- 처음에는 1-2개 종목으로 테스트
- 로그를 주의 깊게 모니터링

### 실전 투입 전 체크리스트

- [ ] Paper Trading으로 1개월 이상 테스트 완료
- [ ] 거래 로그 분석 완료
- [ ] 손익률 확인 및 만족
- [ ] 리스크 관리 설정 확인 (손절/익절)
- [ ] API 키 보안 확인
- [ ] 긴급 정지 방법 숙지 (Ctrl+C)
- [ ] 계좌 잔고 및 한도 확인
- [ ] 시장 시간대 이해
- [ ] V2 자동 청산 기능 이해
- [ ] 전략 프로필 선택 완료

---

## 📚 추가 개발 아이디어

- [ ] 웹 대시보드 (실시간 모니터링)
- [ ] Slack/Discord 알림 통합
- [ ] 더 정교한 기술적 분석 지표
- [ ] 머신러닝 모델 통합
- [ ] 다중 브로커 지원
- [ ] 자동 리밸런싱
- [ ] 포트폴리오 최적화

---

## 📄 라이선스

[MIT License](LICENSE) © 2025-2026 Yungoo Park

---

## 🙏 기여

버그 리포트, 기능 제안, Pull Request 모두 환영합니다! 코드를 수정하기 전에 [CLAUDE.md](CLAUDE.md)의 아키텍처 노트(특히 `position_tracker`와 다섯 개 시스템 모듈이 서로 독립적이라는 점)를 먼저 읽어 보시길 권합니다.

---

**면책 조항**: 이 소프트웨어는 교육 목적으로 제공됩니다. 투자 결정에 따른 모든 손실은 사용자의 책임입니다. 실제 자금을 투자하기 전에 충분한 테스트와 검증을 거치시기 바랍니다.

---

## 📞 지원

- 문제 발생 시: [GitHub Issues](https://github.com/dev-minimalism/us-LLM-trading-bot/issues)
- 아키텍처 및 개발 가이드: [CLAUDE.md](CLAUDE.md)