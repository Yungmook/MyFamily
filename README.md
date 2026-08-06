# 추세매매 자동화 봇 (trendbot)

**이동평균선(이평선)이 우상향할 때 매수하고, 우하향으로 꺾이면 청산**하는
추세추종(trend-following) 자동매매 시스템입니다.

- ✅ **백테스트**: 과거 데이터로 전략 성과를 검증 (수익률/MDD/승률/샤프)
- ✅ **페이퍼트레이딩**: 실시간 시세로 가상매매 (실제 자금 이동 없음)
- 🔜 **실거래**: 브로커 인터페이스만 준비됨 (키 넣고 확장하면 동작)

> ⚠️ 이 프로젝트는 교육/연구용입니다. 실거래 시 발생하는 손실에 대한 책임은
> 사용자 본인에게 있습니다. 반드시 소액으로 충분히 검증한 뒤 사용하세요.

---

## 전략 개요

봉마다 아래 조건으로 상태를 판정하고, **상태가 바뀌는 순간** 매매 신호를 냅니다.

**진입(매수)** — 이평선이 우상향 전환할 때
- 이평선 기울기 > 임계값 (우상향)
- (옵션) 종가가 이평선 위에 위치
- (옵션) 단기 이평선 > 장기 이평선 (정배열)

**청산(매도)** — 추세가 꺾일 때
- 이평선 기울기가 0 이하로 전환 (우하향), 또는 정배열 붕괴
- 손절(`stop_loss_pct`) / 익절(`take_profit_pct`) 도달

기울기는 `indicators.slope_pct()` 에서 *현재 이평선* 과 *N봉 전 이평선* 을
비교해 **봉당 평균 기울기(%)** 로 계산합니다.

---

## 설치

```bash
pip install -r requirements.txt
```

## 빠른 시작 (백테스트)

```bash
# 1) 재현 가능한 샘플 데이터 생성 (합성 OHLCV 500봉)
python scripts/generate_sample_data.py

# 2) 백테스트 실행
python scripts/run_backtest.py --config config.yaml

# 개별 거래 내역까지 보기
python scripts/run_backtest.py --trades
```

출력 예시:

```
==============================================
  백테스트 결과 요약
==============================================
  기간            : 2023-01-01 ~ 2024-05-14
  초기자본        :       1,000,000
  최종자산        :       1,256,163
  총수익률        :          25.62 %
  Buy&Hold 수익률 :          10.37 %
  ...
==============================================
```

## 페이퍼트레이딩 (실시간 가상매매)

업비트 공개 시세(무료·인증 불필요)를 주기적으로 조회해 가상 주문을 냅니다.

```bash
# config.yaml 에서 market.source 를 "upbit" 로 변경 후
python scripts/run_paper.py --iters 5     # 5회만 실행 (생략 시 무한 루프)
```

---

## 설정 (`config.yaml`)

| 섹션 | 키 | 설명 |
|------|-----|------|
| `market` | `source` | `csv` 또는 `upbit` |
| | `symbol` / `interval` | 종목코드 / 캔들간격 |
| `strategy` | `ma_type` / `ma_period` | 이평선 종류(sma/ema)와 기간 |
| | `slope_lookback` / `slope_threshold` | 기울기 측정구간 / 우상향 임계값 |
| | `use_dual_ma` / `fast_period` / `slow_period` | 정배열 조건 |
| | `stop_loss_pct` / `take_profit_pct` | 손절 / 익절 % |
| `account` | `initial_cash` / `order_ratio` | 초기자본 / 매수비율 |
| | `fee_pct` / `slippage_pct` | 수수료 / 슬리피지 |
| `run` | `mode` | `backtest` / `paper` / `live` |

---

## 프로젝트 구조

```
MyFamily/
├── config.yaml                 # 전략·계좌·실행 설정
├── requirements.txt
├── data/sample_ohlcv.csv       # 샘플 데이터
├── scripts/
│   ├── generate_sample_data.py # 샘플 데이터 생성
│   ├── run_backtest.py         # 백테스트 CLI
│   └── run_paper.py            # 페이퍼트레이딩 CLI
├── src/trendbot/
│   ├── indicators.py           # 이동평균·기울기 계산
│   ├── config.py               # 설정 로딩·전략 팩토리
│   ├── strategy/
│   │   ├── base.py             # 전략 인터페이스
│   │   └── trend_ma.py         # ★ 이평선 우상향 추세매매 전략
│   ├── broker/
│   │   ├── base.py             # 브로커 인터페이스
│   │   ├── paper.py            # 페이퍼(가상) 브로커
│   │   └── upbit_live.py       # 실거래 브로커 (스텁)
│   ├── data/loader.py          # CSV / 업비트 데이터 로더
│   ├── backtest/engine.py      # 백테스트 엔진 (성과지표 포함)
│   └── paper_trader.py         # 실시간 가상매매 루프
└── tests/test_strategy.py      # 단위 테스트
```

## 테스트

```bash
python -m pytest tests/ -q
```

---

## 실거래로 확장하기 (향후)

1. `src/trendbot/broker/upbit_live.py` 의 `market_buy` / `market_sell` /
   `cash` / `position` 을 업비트 주문 API 로 구현
2. `UPBIT_ACCESS_KEY` / `UPBIT_SECRET_KEY` 환경변수 설정
3. `config.yaml` 의 `run.mode` 를 `live` 로 변경

전략·백테스트·루프 코드는 브로커 인터페이스(`Broker`)에만 의존하므로,
브로커 구현체만 교체하면 나머지는 그대로 재사용됩니다.
