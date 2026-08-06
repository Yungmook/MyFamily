"""OHLCV 데이터 로더.

두 가지 소스를 지원한다.
  - ``csv``   : 로컬 CSV 파일 (오프라인/재현 가능한 백테스트에 적합)
  - ``upbit`` : 업비트 공개 시세 API (무료, 인증 불필요) — 페이퍼트레이딩용

반환 형식은 항상 다음 컬럼을 가진 :class:`pandas.DataFrame` 이다:
    index: datetime (오름차순)
    columns: open, high, low, close, volume
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명을 소문자로 통일하고 필수 컬럼/정렬을 보장한다."""
    df = df.rename(columns={c: c.lower() for c in df.columns})
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV 데이터에 필수 컬럼이 없습니다: {missing}")
    df = df.sort_index()
    return df[REQUIRED_COLS].astype(float)


def load_csv(path: str) -> pd.DataFrame:
    """CSV 파일에서 OHLCV 를 읽는다.

    첫 컬럼(또는 'date'/'datetime'/'timestamp' 컬럼)을 시간 인덱스로 사용한다.
    """
    df = pd.read_csv(path)
    time_col = next(
        (c for c in df.columns if c.lower() in ("date", "datetime", "timestamp", "time")),
        df.columns[0],
    )
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.set_index(time_col)
    return _normalize(df)


def load_upbit(symbol: str = "KRW-BTC", interval: str = "day", count: int = 200) -> pd.DataFrame:
    """업비트 공개 시세 API 에서 최근 캔들을 가져온다 (인증 불필요).

    interval: "day", "minute1", "minute60" 등.
    네트워크가 필요하며, 실패 시 예외를 던진다.
    """
    import requests  # 지연 임포트: CSV 전용 사용 시 requests 불필요

    if interval == "day":
        url = "https://api.upbit.com/v1/candles/days"
        params = {"market": symbol, "count": count}
    elif interval.startswith("minute"):
        unit = interval.replace("minute", "") or "1"
        url = f"https://api.upbit.com/v1/candles/minutes/{unit}"
        params = {"market": symbol, "count": count}
    else:
        raise ValueError(f"지원하지 않는 interval: {interval!r}")

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    rows = resp.json()

    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "candle_date_time_kst": "datetime",
            "opening_price": "open",
            "high_price": "high",
            "low_price": "low",
            "trade_price": "close",
            "candle_acc_trade_volume": "volume",
        }
    )
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    return _normalize(df)


def load_ohlcv(market_cfg: dict) -> pd.DataFrame:
    """설정(config.yaml 의 market 섹션)에 따라 데이터를 로드한다."""
    source = market_cfg.get("source", "csv")
    if source == "csv":
        return load_csv(market_cfg["csv_path"])
    if source == "upbit":
        return load_upbit(
            symbol=market_cfg.get("symbol", "KRW-BTC"),
            interval=market_cfg.get("interval", "day"),
        )
    raise ValueError(f"지원하지 않는 데이터 소스: {source!r} (csv/upbit)")
