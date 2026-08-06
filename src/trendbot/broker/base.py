"""브로커 인터페이스.

백테스트/페이퍼/실거래가 동일한 인터페이스를 공유하도록 추상화한다.
실거래 연동(예: 업비트, 한국투자증권)은 이 :class:`Broker` 를 상속해
``market_buy`` / ``market_sell`` / ``get_balance`` 를 구현하면 된다.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Fill:
    """주문 체결 결과."""

    side: OrderSide
    price: float        # 체결가 (슬리피지 반영)
    quantity: float     # 체결 수량
    fee: float          # 지불 수수료
    cash_after: float   # 체결 후 현금
    position_after: float  # 체결 후 보유 수량


class Broker:
    """브로커 추상 베이스."""

    def market_buy(self, price: float, ratio: float = 1.0) -> Fill | None:
        """시장가 매수. ``ratio`` 는 사용할 현금 비율(0~1)."""
        raise NotImplementedError

    def market_sell(self, price: float, ratio: float = 1.0) -> Fill | None:
        """시장가 매도. ``ratio`` 는 청산할 보유수량 비율(0~1)."""
        raise NotImplementedError

    @property
    def cash(self) -> float:
        raise NotImplementedError

    @property
    def position(self) -> float:
        raise NotImplementedError

    def equity(self, price: float) -> float:
        """현재가 기준 총 평가자산 (현금 + 보유수량*현재가)."""
        return self.cash + self.position * price
