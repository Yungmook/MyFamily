"""페이퍼(가상) 브로커.

실제 주문을 내지 않고 현금/보유수량을 장부상으로만 관리한다.
수수료와 슬리피지를 반영하므로 백테스트와 페이퍼트레이딩 양쪽에서
동일하게 쓰인다. 실거래가 아니므로 자금 손실 위험이 없다.
"""
from __future__ import annotations

from .base import Broker, Fill, OrderSide


class PaperBroker(Broker):
    def __init__(
        self,
        initial_cash: float,
        fee_pct: float = 0.05,
        slippage_pct: float = 0.02,
    ) -> None:
        self._cash = float(initial_cash)
        self._position = 0.0        # 보유 수량
        self._avg_price = 0.0       # 평균 매입단가
        self.fee_rate = fee_pct / 100.0
        self.slippage_rate = slippage_pct / 100.0

    # ------------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self._cash

    @property
    def position(self) -> float:
        return self._position

    @property
    def avg_price(self) -> float:
        return self._avg_price

    # ------------------------------------------------------------------
    def market_buy(self, price: float, ratio: float = 1.0) -> Fill | None:
        spend = self._cash * ratio
        if spend <= 0:
            return None
        fill_price = price * (1 + self.slippage_rate)   # 불리한 방향으로 체결
        fee = spend * self.fee_rate
        qty = (spend - fee) / fill_price
        if qty <= 0:
            return None

        # 평균단가 갱신
        total_cost = self._avg_price * self._position + fill_price * qty
        self._position += qty
        self._avg_price = total_cost / self._position if self._position else 0.0
        self._cash -= spend

        return Fill(OrderSide.BUY, fill_price, qty, fee, self._cash, self._position)

    def market_sell(self, price: float, ratio: float = 1.0) -> Fill | None:
        qty = self._position * ratio
        if qty <= 0:
            return None
        fill_price = price * (1 - self.slippage_rate)   # 불리한 방향으로 체결
        proceeds = fill_price * qty
        fee = proceeds * self.fee_rate
        self._cash += proceeds - fee
        self._position -= qty
        if self._position <= 1e-12:
            self._position = 0.0
            self._avg_price = 0.0

        return Fill(OrderSide.SELL, fill_price, qty, fee, self._cash, self._position)
