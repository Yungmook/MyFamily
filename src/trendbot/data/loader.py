"""OHLCV 데이터 로더 (주식).

두 가지 소스를 지원한다.
  - ``csv`` : 로컬 CSV 파일 (오프라인/재현 가능한 백테스트에 적합)
  - ``fdr`` : FinanceDataReader — 국내(KRX)·해외 주가를 무료·인증 없이 조회
              (예: 삼성전자 "005930", 애플 "AAPL")

반환 형식은 항상 다음 컬럼을 가진 :class:`pandas.DataFrame` 이다:
    index: datetime (오름차순)
    columns: open, high, low, close, volume
"""
from __future__ import annotations

import pandas as pd

REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명을 소문자로 통일하고 필수 컬럼/정렬을 보장한다."""
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
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


def load_fdr(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """FinanceDataReader 로 주가(OHLCV)를 조회한다 (인증 불필요).

    symbol 예시:
      - 국내: "005930"(삼성전자), "000660"(SK하이닉스), "035720"(카카오)
      - 지수: "KS11"(코스피), "KQ11"(코스닥)
      - 해외: "AAPL", "MSFT", "TSLA"
    네트워크가 필요하며, 실패 시 예외를 던진다.
    """
    import FinanceDataReader as fdr  # 지연 임포트: CSV 전용 사용 시 불필요

    df = fdr.DataReader(symbol, start, end)
    # FinanceDataReader 컬럼: Open/High/Low/Close/Volume (+ Change/Adj Close 등)
    return _normalize(df)


def load_ohlcv(market_cfg: dict) -> pd.DataFrame:
    """설정(config.yaml 의 market 섹션)에 따라 데이터를 로드한다."""
    source = market_cfg.get("source", "csv")
    if source == "csv":
        return load_csv(market_cfg["csv_path"])
    if source == "fdr":
        return load_fdr(
            symbol=market_cfg["symbol"],
            start=market_cfg.get("start"),
            end=market_cfg.get("end"),
        )
    raise ValueError(f"지원하지 않는 데이터 소스: {source!r} (csv/fdr)")
