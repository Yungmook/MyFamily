"""데모용 샘플 OHLCV 데이터를 생성한다.

상승/하락 추세가 번갈아 나타나는 합성 시계열을 만들어
추세매매 전략을 오프라인에서 재현 가능하게 검증할 수 있도록 한다.
(시드 고정 → 항상 같은 데이터 생성)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate(n: int = 500, seed: int = 42, start_price: float = 50_000_000.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")

    # 국면(추세)을 여러 개 이어 붙여 추세장/횡보장을 섞는다
    drifts = []
    remaining = n
    regimes = [0.0025, -0.002, 0.001, 0.003, -0.0015, 0.0, 0.002]
    i = 0
    while remaining > 0:
        length = min(rng.integers(50, 90), remaining)
        drifts.extend([regimes[i % len(regimes)]] * int(length))
        remaining -= int(length)
        i += 1

    price = start_price
    closes = []
    for d in drifts[:n]:
        shock = rng.normal(0, 0.02)          # 일간 변동성 2%
        price *= max(0.5, 1 + d + shock)
        closes.append(price)

    closes = np.array(closes)
    highs = closes * (1 + np.abs(rng.normal(0, 0.01, n)))
    lows = closes * (1 - np.abs(rng.normal(0, 0.01, n)))
    opens = np.concatenate([[closes[0]], closes[:-1]])
    volume = rng.uniform(100, 1000, n)

    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": np.maximum.reduce([opens, highs, closes]),
            "low": np.minimum.reduce([opens, lows, closes]),
            "close": closes,
            "volume": volume,
        }
    )


if __name__ == "__main__":
    import os

    out = os.path.join(os.path.dirname(__file__), "..", "data", "sample_ohlcv.csv")
    df = generate()
    df.to_csv(out, index=False)
    print(f"샘플 데이터 {len(df)}봉 생성 -> {os.path.normpath(out)}")
