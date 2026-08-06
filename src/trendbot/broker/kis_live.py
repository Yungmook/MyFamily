"""한국투자증권(KIS) 실거래 브로커 (스텁).

⚠️ 아직 실제 주문 로직은 구현되어 있지 않다. 실거래로 확장할 때
이 클래스의 메서드를 채우면 나머지 코드(전략/루프)는 그대로 재사용된다.

실거래 활성화 방법(향후):
  1. 한국투자증권 KIS Developers(https://apiportal.koreainvestment.com)에서
     API 앱키(APP KEY)/시크릿(APP SECRET) 발급 — 모의투자 계좌도 지원
  2. 환경변수 KIS_APP_KEY / KIS_APP_SECRET / KIS_ACCOUNT_NO 설정
  3. 아래 TODO 부분에 접근토큰 발급 + 국내주식 주문 REST 호출 구현
     - 주문: POST /uapi/domestic-stock/v1/trading/order-cash
     - 잔고: GET  /uapi/domestic-stock/v1/trading/inquire-balance
  4. config.yaml 의 run.mode 를 "live" 로 변경

실거래는 자금 손실 위험이 있으므로, 반드시 모의투자로 충분히 검증한 뒤
소액으로 시작해야 한다.
"""
from __future__ import annotations

import os

from .base import Broker, Fill


class KISLiveBroker(Broker):
    def __init__(self, symbol: str = "005930", paper_trading: bool = True) -> None:
        self.symbol = symbol
        self.paper_trading = paper_trading   # True 면 KIS 모의투자 도메인 사용
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_no = os.getenv("KIS_ACCOUNT_NO")
        if not (self.app_key and self.app_secret and self.account_no):
            raise RuntimeError(
                "실거래를 위해 KIS_APP_KEY / KIS_APP_SECRET / KIS_ACCOUNT_NO "
                "환경변수가 필요합니다."
            )

    def market_buy(self, price: float, ratio: float = 1.0) -> Fill | None:  # pragma: no cover
        raise NotImplementedError(
            "실거래 매수는 아직 구현되지 않았습니다. KIS 주문 API 연동이 필요합니다."
        )

    def market_sell(self, price: float, ratio: float = 1.0) -> Fill | None:  # pragma: no cover
        raise NotImplementedError(
            "실거래 매도는 아직 구현되지 않았습니다. KIS 주문 API 연동이 필요합니다."
        )

    @property
    def cash(self) -> float:  # pragma: no cover
        raise NotImplementedError("예수금 조회(inquire-balance) 구현 필요")

    @property
    def position(self) -> float:  # pragma: no cover
        raise NotImplementedError("보유수량 조회 구현 필요")
