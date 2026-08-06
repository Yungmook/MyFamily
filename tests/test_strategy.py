"""전략/백테스트 핵심 로직 테스트."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trendbot import indicators as ind          # noqa: E402
from trendbot.backtest import run_backtest       # noqa: E402
from trendbot.broker import PaperBroker          # noqa: E402
from trendbot.strategy import SignalType, TrendMAStrategy  # noqa: E402


def _make_df(closes):
    n = len(closes)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0},
        index=idx,
    )


def test_slope_positive_on_rising_series():
    s = pd.Series(np.linspace(100, 200, 50))
    ma = ind.moving_average(s, 10, "ema")
    slope = ind.slope_pct(ma, 3)
    assert slope.dropna().iloc[-1] > 0  # 상승 구간에서 기울기 양수


def test_slope_negative_on_falling_series():
    s = pd.Series(np.linspace(200, 100, 50))
    ma = ind.moving_average(s, 10, "ema")
    slope = ind.slope_pct(ma, 3)
    assert slope.dropna().iloc[-1] < 0


def test_buy_signal_appears_in_uptrend():
    # 상승 후 하락으로 꺾이는 시계열 -> 상승 구간에서 BUY, 하락 전환 시 SELL
    closes = list(np.linspace(60, 160, 80)) + list(np.linspace(160, 90, 60))
    df = _make_df(closes)
    strat = TrendMAStrategy(ma_period=10, slope_lookback=3, use_dual_ma=False, price_above_ma=False)
    out = strat.generate(df)
    assert (out["signal"] == SignalType.BUY).any()
    assert (out["signal"] == SignalType.SELL).any()


def test_paper_broker_buy_sell_accounting():
    b = PaperBroker(1_000_000, fee_pct=0.0, slippage_pct=0.0)
    fill = b.market_buy(100.0, ratio=1.0)
    assert fill is not None
    assert b.position > 0
    assert abs(b.cash) < 1e-6                 # 전량 매수 -> 현금 소진
    b.market_sell(150.0, ratio=1.0)           # 50% 상승 후 청산
    assert b.position == 0
    assert b.cash > 1_000_000                 # 이익 실현


def test_backtest_runs_and_reports():
    closes = list(np.linspace(100, 60, 60)) + list(np.linspace(60, 200, 100))
    df = _make_df(closes)
    strat = TrendMAStrategy(ma_period=10, slope_lookback=3, use_dual_ma=False)
    res = run_backtest(df, strat, initial_cash=1_000_000)
    assert "total_return_pct" in res.metrics
    assert len(res.equity_curve) == len(df)
    # 강한 상승 추세를 잡았으므로 수익이 나야 한다
    assert res.metrics["total_return_pct"] > 0


def test_no_lookahead_uses_next_open():
    # 신호 봉의 종가가 아니라 다음 봉 시가로 체결되는지 확인
    idx = pd.date_range("2023-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {"open": [10, 20, 30], "high": [10, 20, 30], "low": [10, 20, 30],
         "close": [10, 20, 30], "volume": 1.0},
        index=idx,
    )

    class AlwaysBuyFirst(TrendMAStrategy):
        def generate(self, d):
            o = d.copy()
            o["signal"] = [SignalType.BUY, SignalType.HOLD, SignalType.HOLD]
            o["reason"] = ""
            return o

    res = run_backtest(df, AlwaysBuyFirst(), initial_cash=1000, fee_pct=0, slippage_pct=0)
    # 0번봉에서 BUY -> 1번봉 시가(20)로 체결되어야 함
    assert abs(res.trades[0].entry_price - 20.0) < 1e-6
