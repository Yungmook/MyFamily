"""전략 인터페이스 정의.

모든 전략은 OHLCV 데이터프레임을 받아 봉마다 매매 신호를 생성한다.
새로운 전략을 추가하려면 :class:`Strategy` 를 상속해 ``generate`` 를 구현한다.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

import pandas as pd


class SignalType(enum.Enum):
    """매매 신호 종류."""

    BUY = "buy"      # 신규 진입(매수)
    SELL = "sell"    # 청산(매도)
    HOLD = "hold"    # 관망(신호 없음)


@dataclass
class Signal:
    """한 시점의 매매 신호."""

    type: SignalType
    reason: str = ""   # 신호가 발생한 근거(로그/디버깅용)


class Strategy:
    """전략 베이스 클래스."""

    name: str = "base"

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """OHLCV 데이터프레임에 지표와 신호 컬럼을 추가해 반환한다.

        반환 데이터프레임은 최소한 다음 컬럼을 포함해야 한다:
          - ``signal`` : :class:`SignalType` 값
          - ``reason``  : 신호 근거 문자열
        """
        raise NotImplementedError

    def latest_signal(self, df: pd.DataFrame) -> Signal:
        """가장 최근 봉의 신호를 :class:`Signal` 로 반환한다 (실시간 매매용)."""
        enriched = self.generate(df)
        last = enriched.iloc[-1]
        return Signal(type=last["signal"], reason=str(last.get("reason", "")))
