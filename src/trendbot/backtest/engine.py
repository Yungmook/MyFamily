"""백테스트 엔진.

전략이 만든 신호를 과거 데이터에 대해 순차 체결하고,
수익률/MDD/승률 등 성과 지표와 자산곡선(equity curve)을 산출한다.

체결 규칙(look-ahead bias 방지)
--------------------------------
어떤 봉에서 신호가 발생하면 **다음 봉의 시가** 로 체결한다.
(신호를 만든 종가로 즉시 체결하면 미래 정보를 쓰는 셈이 되므로 배제)
손절/익절은 봉의 저가/고가를 이용해 봉 내에서 판정한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..broker.paper import PaperBroker
from ..strategy.base import SignalType, Strategy


@dataclass
class Trade:
    entry_time: object
    entry_price: float
    exit_time: object = None
    exit_price: float = None
    qty: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason_in: str = ""
    reason_out: str = ""


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    signals: pd.DataFrame = None

    def summary(self) -> str:
        m = self.metrics
        lines = [
            "=" * 46,
            "  백테스트 결과 요약",
            "=" * 46,
            f"  기간            : {m['start']} ~ {m['end']}",
            f"  초기자본        : {m['initial']:>15,.0f}",
            f"  최종자산        : {m['final']:>15,.0f}",
            f"  총수익률        : {m['total_return_pct']:>14.2f} %",
            f"  Buy&Hold 수익률 : {m['buy_hold_pct']:>14.2f} %",
            f"  연환산(CAGR)    : {m['cagr_pct']:>14.2f} %",
            f"  최대낙폭(MDD)   : {m['mdd_pct']:>14.2f} %",
            f"  샤프지수        : {m['sharpe']:>14.2f}",
            f"  거래횟수        : {m['num_trades']:>14d}",
            f"  승률            : {m['win_rate_pct']:>14.2f} %",
            f"  손익비(P/F)     : {m['profit_factor']:>14.2f}",
            "=" * 46,
        ]
        return "\n".join(lines)


def _max_drawdown(equity: pd.Series) -> float:
    """최대낙폭(MDD)을 % 로 반환 (양수)."""
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    return abs(drawdown.min()) * 100.0 if len(drawdown) else 0.0


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    initial_cash: float = 1_000_000,
    order_ratio: float = 0.99,
    fee_pct: float = 0.05,
    slippage_pct: float = 0.02,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
) -> BacktestResult:
    enriched = strategy.generate(df)
    broker = PaperBroker(initial_cash, fee_pct=fee_pct, slippage_pct=slippage_pct)

    equity = []
    trades: list[Trade] = []
    open_trade: Trade | None = None

    rows = list(enriched.itertuples())
    for i, row in enumerate(rows):
        price_close = row.close
        # 다음 봉 시가로 체결 (없으면 마지막 봉은 종가로)
        next_open = rows[i + 1].open if i + 1 < len(rows) else price_close

        # --- 1) 보유 중이면 손절/익절 우선 판정 (봉 내 고저 사용) ---
        if broker.position > 0 and open_trade is not None:
            entry = broker.avg_price
            hit_exit = False
            exit_price = None
            reason = ""
            if stop_loss_pct > 0:
                sl_price = entry * (1 - stop_loss_pct / 100.0)
                if row.low <= sl_price:
                    exit_price, reason, hit_exit = sl_price, f"손절 -{stop_loss_pct:.1f}%", True
            if not hit_exit and take_profit_pct > 0:
                tp_price = entry * (1 + take_profit_pct / 100.0)
                if row.high >= tp_price:
                    exit_price, reason, hit_exit = tp_price, f"익절 +{take_profit_pct:.1f}%", True
            if hit_exit:
                fill = broker.market_sell(exit_price, ratio=1.0)
                _close_trade(open_trade, row.Index, fill, reason)
                trades.append(open_trade)
                open_trade = None

        # --- 2) 전략 신호 처리 (다음 봉 시가 체결) ---
        signal = row.signal
        if signal == SignalType.BUY and broker.position == 0:
            fill = broker.market_buy(next_open, ratio=order_ratio)
            if fill:
                open_trade = Trade(
                    entry_time=row.Index,
                    entry_price=fill.price,
                    qty=fill.quantity,
                    reason_in=str(getattr(row, "reason", "")),
                )
        elif signal == SignalType.SELL and broker.position > 0 and open_trade is not None:
            fill = broker.market_sell(next_open, ratio=1.0)
            _close_trade(open_trade, row.Index, fill, str(getattr(row, "reason", "")))
            trades.append(open_trade)
            open_trade = None

        equity.append((row.Index, broker.equity(price_close)))

    # 종료 시 미청산 포지션 정리
    if broker.position > 0 and open_trade is not None:
        last = rows[-1]
        fill = broker.market_sell(last.close, ratio=1.0)
        _close_trade(open_trade, last.Index, fill, "백테스트 종료 청산")
        trades.append(open_trade)

    equity_curve = pd.Series(dict(equity)).sort_index()
    metrics = _compute_metrics(equity_curve, trades, enriched, initial_cash)
    return BacktestResult(equity_curve, trades, metrics, enriched)


def _close_trade(trade: Trade, exit_time, fill, reason: str) -> None:
    trade.exit_time = exit_time
    trade.exit_price = fill.price
    gross = (fill.price - trade.entry_price) * trade.qty
    trade.pnl = gross
    trade.pnl_pct = (fill.price / trade.entry_price - 1.0) * 100.0
    trade.reason_out = reason


def _compute_metrics(equity: pd.Series, trades: list, enriched: pd.DataFrame, initial: float) -> dict:
    final = float(equity.iloc[-1]) if len(equity) else initial
    total_return = (final / initial - 1.0) * 100.0

    # Buy & Hold 비교
    first_close = float(enriched["close"].iloc[0])
    last_close = float(enriched["close"].iloc[-1])
    buy_hold = (last_close / first_close - 1.0) * 100.0

    # CAGR
    days = max((equity.index[-1] - equity.index[0]).days, 1) if len(equity) > 1 else 1
    years = days / 365.25
    cagr = ((final / initial) ** (1 / years) - 1.0) * 100.0 if years > 0 else 0.0

    # 샤프지수 (봉 단위 수익률 기준, 무위험수익률 0 가정)
    rets = equity.pct_change().dropna()
    sharpe = float(np.sqrt(252) * rets.mean() / rets.std()) if rets.std() > 0 else 0.0

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    return {
        "start": str(equity.index[0].date()) if len(equity) else "-",
        "end": str(equity.index[-1].date()) if len(equity) else "-",
        "initial": initial,
        "final": final,
        "total_return_pct": total_return,
        "buy_hold_pct": buy_hold,
        "cagr_pct": cagr,
        "mdd_pct": _max_drawdown(equity),
        "sharpe": sharpe,
        "num_trades": len(trades),
        "win_rate_pct": (len(wins) / len(trades) * 100.0) if trades else 0.0,
        "profit_factor": profit_factor,
    }
