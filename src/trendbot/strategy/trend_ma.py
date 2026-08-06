"""추세매매 전략: 이평선 우상향 진입 / 우하향 청산.

핵심 아이디어
--------------
- **진입(매수)**: 이동평균선의 기울기가 양(+), 즉 *우상향* 이고
  (옵션) 종가가 이평선 위에 있으며, (옵션) 단기 이평선이 장기 이평선
  위에 있는 정배열일 때.
- **청산(매도)**: 이평선 기울기가 0 이하로 꺾여 *우하향* 으로 전환하거나
  정배열이 무너지거나, 손절/익절 조건에 닿았을 때.

추세추종이므로 "오르는 추세에 올라타서, 추세가 꺾이면 내린다" 는
단순하고 견고한 규칙을 따른다.
"""
from __future__ import annotations

import pandas as pd

from .. import indicators as ind
from .base import SignalType, Strategy


class TrendMAStrategy(Strategy):
    """이평선 기울기 기반 추세추종 전략."""

    name = "trend_ma"

    def __init__(
        self,
        ma_type: str = "ema",
        ma_period: int = 20,
        slope_lookback: int = 3,
        slope_threshold: float = 0.0,
        use_dual_ma: bool = True,
        fast_period: int = 10,
        slow_period: int = 30,
        price_above_ma: bool = True,
    ) -> None:
        self.ma_type = ma_type
        self.ma_period = ma_period
        self.slope_lookback = slope_lookback
        self.slope_threshold = slope_threshold
        self.use_dual_ma = use_dual_ma
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.price_above_ma = price_above_ma

    # ------------------------------------------------------------------
    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]

        # 1) 기준 이평선과 그 기울기(우상향 여부의 핵심 지표)
        out["ma"] = ind.moving_average(close, self.ma_period, self.ma_type)
        out["ma_slope"] = ind.slope_pct(out["ma"], self.slope_lookback)

        # 2) 우상향(추세 상승) 조건
        uptrend = out["ma_slope"] > self.slope_threshold

        # 3) (옵션) 종가가 이평선 위 — 추세에 순응하는 위치인지
        if self.price_above_ma:
            uptrend &= close > out["ma"]

        # 4) (옵션) 단기>장기 정배열 — 추가 확인
        if self.use_dual_ma:
            out["ma_fast"] = ind.moving_average(close, self.fast_period, self.ma_type)
            out["ma_slow"] = ind.moving_average(close, self.slow_period, self.ma_type)
            uptrend &= out["ma_fast"] > out["ma_slow"]

        out["uptrend"] = uptrend.fillna(False)

        # 5) 상태 전환을 신호로 변환
        #    - 관망 -> 우상향 : 매수(BUY)
        #    - 우상향 -> 우하향 : 매도(SELL)
        prev = out["uptrend"].shift(1, fill_value=False)
        entered = out["uptrend"] & (~prev)   # 새로 우상향 진입
        exited = (~out["uptrend"]) & prev    # 우상향에서 이탈

        signals = []
        reasons = []
        for is_enter, is_exit, slope in zip(entered, exited, out["ma_slope"]):
            if is_enter:
                signals.append(SignalType.BUY)
                reasons.append(f"이평선 우상향 진입 (기울기 {slope:+.3f}%/봉)")
            elif is_exit:
                signals.append(SignalType.SELL)
                # 기울기가 꺾였는지, 다른 조건(정배열/종가) 붕괴인지 구분해 표기
                if slope <= self.slope_threshold:
                    reasons.append(f"이평선 우하향 전환 (기울기 {slope:+.3f}%/봉)")
                else:
                    reasons.append(f"상승추세 이탈 (정배열/종가 조건 붕괴, 기울기 {slope:+.3f}%/봉)")
            else:
                signals.append(SignalType.HOLD)
                reasons.append("")

        out["signal"] = signals
        out["reason"] = reasons
        return out
