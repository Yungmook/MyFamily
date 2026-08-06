"""페이퍼트레이딩(실시간 가상매매) 루프.

실시간 시세를 주기적으로 조회해 최신 봉의 신호를 확인하고,
:class:`PaperBroker` 로 가상 주문을 낸다. **실거래가 아니므로 실제 자금
이동은 전혀 없다.** 실거래로 확장하려면 ``broker`` 자리에 실제 브로커
구현체를 넣기만 하면 된다.
"""
from __future__ import annotations

import logging
import time

from .broker import Broker, PaperBroker
from .data.loader import load_ohlcv
from .strategy.base import SignalType, Strategy

log = logging.getLogger("trendbot.paper")


def run_paper_trading(
    cfg: dict,
    strategy: Strategy,
    broker: Broker | None = None,
    max_iters: int | None = None,
) -> Broker:
    """페이퍼트레이딩 루프를 실행한다.

    max_iters 를 주면 그 횟수만큼만 돌고 종료한다(테스트/데모용).
    None 이면 무한 루프(Ctrl+C 로 종료).
    """
    acc = cfg["account"]
    market = cfg["market"]
    poll = cfg["run"].get("poll_interval_sec", 60)
    order_ratio = acc.get("order_ratio", 0.99)

    if broker is None:
        broker = PaperBroker(
            acc["initial_cash"],
            fee_pct=acc.get("fee_pct", 0.05),
            slippage_pct=acc.get("slippage_pct", 0.02),
        )

    log.info("페이퍼트레이딩 시작 — 종목=%s, 초기자본=%s", market.get("symbol"), acc["initial_cash"])
    iters = 0
    try:
        while max_iters is None or iters < max_iters:
            df = load_ohlcv(market)
            sig = strategy.latest_signal(df)
            price = float(df["close"].iloc[-1])

            if sig.type == SignalType.BUY and broker.position == 0:
                fill = broker.market_buy(price, ratio=order_ratio)
                if fill:
                    log.info("[매수] %s @ %.2f  x %.6f | %s", market.get("symbol"), fill.price, fill.quantity, sig.reason)
            elif sig.type == SignalType.SELL and broker.position > 0:
                fill = broker.market_sell(price, ratio=1.0)
                if fill:
                    log.info("[매도] %s @ %.2f  x %.6f | %s", market.get("symbol"), fill.price, fill.quantity, sig.reason)
            else:
                log.info("[관망] 현재가 %.2f | 보유 %.6f | 평가자산 %.0f", price, broker.position, broker.equity(price))

            iters += 1
            if max_iters is not None and iters >= max_iters:
                break
            time.sleep(poll)
    except KeyboardInterrupt:
        log.info("사용자 종료. 최종 평가자산: %.0f", broker.equity(price))

    return broker
