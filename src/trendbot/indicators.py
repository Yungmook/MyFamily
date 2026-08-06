"""기술적 지표 계산 모듈.

이동평균(SMA/EMA)과 이평선 기울기(slope)를 계산한다.
전략의 핵심인 "이평선 우상향" 판정에 사용된다.
"""
from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """단순이동평균 (Simple Moving Average)."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """지수이동평균 (Exponential Moving Average)."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def moving_average(series: pd.Series, period: int, ma_type: str = "ema") -> pd.Series:
    """설정에 따라 SMA 또는 EMA 이동평균을 반환한다."""
    ma_type = (ma_type or "ema").lower()
    if ma_type == "sma":
        return sma(series, period)
    if ma_type == "ema":
        return ema(series, period)
    raise ValueError(f"지원하지 않는 이동평균 종류입니다: {ma_type!r} (sma/ema 중 선택)")


def slope_pct(ma_series: pd.Series, lookback: int) -> pd.Series:
    """이평선의 기울기를 백분율(%)로 계산한다.

    현재 이평선 값과 ``lookback`` 봉 이전 값을 비교한다.
    반환값이 0보다 크면 우상향, 0보다 작으면 우하향을 의미한다.

    slope(%) = (MA_now - MA_prev) / |MA_prev| * 100 / lookback
    (lookback 으로 나누어 '봉당 평균 기울기'로 정규화한다)
    """
    prev = ma_series.shift(lookback)
    return (ma_series - prev) / prev.abs() * 100.0 / lookback
