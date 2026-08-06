"""업비트 실거래 브로커 (스텁).

⚠️ 아직 실제 주문 로직은 구현되어 있지 않다. 실거래로 확장할 때
이 클래스의 메서드를 채우면 나머지 코드(전략/루프)는 그대로 재사용된다.

실거래 활성화 방법(향후):
  1. `pip install pyjwt` 후 업비트 Open API 키 발급
  2. 환경변수 UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY 설정
  3. 아래 TODO 부분에 서명(JWT) + 주문 REST 호출 구현
  4. config.yaml 의 run.mode 를 "live" 로 변경

실거래는 자금 손실 위험이 있으므로, 반드시 소액으로 충분히 검증한 뒤
사용해야 한다.
"""
from __future__ import annotations

import os

from .base import Broker, Fill, OrderSide


class UpbitLiveBroker(Broker):
    def __init__(self, symbol: str = "KRW-BTC") -> None:
        self.symbol = symbol
        self.access_key = os.getenv("UPBIT_ACCESS_KEY")
        self.secret_key = os.getenv("UPBIT_SECRET_KEY")
        if not (self.access_key and self.secret_key):
            raise RuntimeError(
                "실거래를 위해 UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY 환경변수가 필요합니다."
            )

    def market_buy(self, price: float, ratio: float = 1.0) -> Fill | None:  # pragma: no cover
        raise NotImplementedError(
            "실거래 매수는 아직 구현되지 않았습니다. 업비트 주문 API 연동이 필요합니다."
        )

    def market_sell(self, price: float, ratio: float = 1.0) -> Fill | None:  # pragma: no cover
        raise NotImplementedError(
            "실거래 매도는 아직 구현되지 않았습니다. 업비트 주문 API 연동이 필요합니다."
        )

    @property
    def cash(self) -> float:  # pragma: no cover
        raise NotImplementedError("잔고 조회(GET /v1/accounts) 구현 필요")

    @property
    def position(self) -> float:  # pragma: no cover
        raise NotImplementedError("보유수량 조회 구현 필요")
