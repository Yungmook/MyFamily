"""자동매매용 종목 스크리너 (유동성·변동성·추세 정량 지표 계산).

`/research` 명령어의 STEP 2·3·5 를 담당하는 재사용 스크립트다.
지정한 티커들의 주가를 ``FinanceDataReader`` 로 받아 아래를 계산·출력한다.

  - 유동성   : 평균거래량(최근 N일) × 현재가 = 일평균 거래대금, ``$10M`` 통과 여부
  - 변동성   : ATR(14), ATR%(=ATR/현재가), 52주 고저 대비 현재 위치(%)
  - 추세     : 이평선(EMA) 기울기(%) — 추세추종 적합도 참고용
  - 히스토리 : 각 종목 OHLCV 를 ``data/<TICKER>.csv`` 로 저장(백테스터 로더 호환)

펀더멘털(매출성장·부채 등)은 무료 주가 데이터로 알 수 없으므로 여기서 다루지 않는다.
그 부분은 `/research` 명령어가 웹 검색으로 채운다.

사용법:
    python scripts/research_screener.py NVDA AMD PLTR
    python scripts/research_screener.py --file tickers.txt --years 3
    python scripts/research_screener.py AAPL MSFT --min-dollar-volume 20_000_000 --no-save-data

출력:
    - 콘솔에 정렬된 요약 표
    - results/screener_<YYYYMMDD>.csv (스코어링용 원자료)
    - data/<TICKER>.csv (유동성 통과 종목의 일봉, --no-save-data 로 끌 수 있음)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

# src 를 import 경로에 추가 (프로젝트 지표 모듈 재사용)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trendbot.data.loader import load_fdr  # noqa: E402
from trendbot.indicators import moving_average, slope_pct  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
RESULTS_DIR = os.path.join(ROOT, "results")


# ---------------------------------------------------------------------------
# 지표 계산
# ---------------------------------------------------------------------------
def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR(Average True Range). TR 을 period 만큼 EMA(Wilder) 평활한다."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    # Wilder 방식(=span 대신 alpha=1/period 지수평활)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def analyze(symbol: str, df: pd.DataFrame, *, vol_window: int, min_dollar_volume: float) -> dict:
    """단일 종목의 정량 지표를 계산해 dict 로 반환한다."""
    close = df["close"]
    price = float(close.iloc[-1])

    avg_vol = float(df["volume"].tail(vol_window).mean())
    dollar_vol = avg_vol * price

    atr14 = atr(df, 14)
    atr_val = float(atr14.iloc[-1])
    atr_pct = (atr_val / price * 100.0) if price else float("nan")

    # 52주(약 252 거래일) 고저 대비 현재 위치
    window = df.tail(252)
    hi52 = float(window["high"].max())
    lo52 = float(window["low"].min())
    pos52 = ((price - lo52) / (hi52 - lo52) * 100.0) if hi52 > lo52 else float("nan")

    # 추세: EMA20 기울기(%) — 우상향(>0)이면 추세추종 진입 우호
    ema20 = moving_average(close, 20, "ema")
    trend_slope = float(slope_pct(ema20, 3).iloc[-1])

    passed = dollar_vol >= min_dollar_volume and len(df) >= vol_window

    return {
        "티커": symbol,
        "현재가": round(price, 2),
        "평균거래량": int(avg_vol),
        "일평균거래대금($)": int(dollar_vol),
        "유동성": "O" if dollar_vol >= min_dollar_volume else "X",
        "ATR%": round(atr_pct, 2),
        "52주위치%": round(pos52, 1) if pos52 == pos52 else float("nan"),
        "추세기울기%": round(trend_slope, 3) if trend_slope == trend_slope else float("nan"),
        "봉수": len(df),
        "통과": passed,
    }


# ---------------------------------------------------------------------------
# 데이터 조회 (네트워크 재시도 포함)
# ---------------------------------------------------------------------------
def fetch_with_retry(symbol: str, start: str, retries: int = 4):
    """FinanceDataReader 조회. 실패 시 지수 백오프(2·4·8·16s)로 재시도."""
    delay = 2
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            df = load_fdr(symbol, start=start)
            if df is None or df.empty:
                raise ValueError("빈 데이터")
            return df
        except Exception as e:  # noqa: BLE001 — 네트워크/심볼 오류 모두 재시도
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"{symbol} 조회 실패: {last_err}")


def read_tickers(args) -> list[str]:
    tickers: list[str] = list(args.tickers)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip().upper()
                if t and not t.startswith("#"):
                    tickers.append(t)
    # 중복 제거(순서 유지)
    seen: set[str] = set()
    out: list[str] = []
    for t in (x.upper() for x in tickers):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="자동매매용 종목 스크리너 (유동성/변동성/추세)")
    parser.add_argument("tickers", nargs="*", help="티커 목록 (예: NVDA AMD PLTR)")
    parser.add_argument("--file", help="티커가 줄단위로 적힌 파일 (# 주석 허용)")
    parser.add_argument("--years", type=int, default=3, help="조회 기간(년), 기본 3")
    parser.add_argument("--vol-window", type=int, default=60, help="평균거래량 계산 구간(일), 기본 60")
    parser.add_argument(
        "--min-dollar-volume", type=float, default=10_000_000,
        help="유동성 통과 기준: 일평균 거래대금($), 기본 1000만",
    )
    parser.add_argument("--no-save-data", action="store_true", help="data/<TICKER>.csv 저장 생략")
    args = parser.parse_args()

    tickers = read_tickers(args)
    if not tickers:
        parser.error("티커를 인자나 --file 로 하나 이상 지정하세요.")

    start = (datetime.today() - timedelta(days=int(args.years * 365.25))).strftime("%Y-%m-%d")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"대상 {len(tickers)}개 | 기간 {start}~ | 유동성 기준 ${args.min_dollar_volume:,.0f}\n")

    rows: list[dict] = []
    failed: list[str] = []
    saved: list[str] = []

    for sym in tickers:
        try:
            df = fetch_with_retry(sym, start)
        except Exception as e:  # noqa: BLE001
            print(f"  [실패] {sym}: {e}")
            failed.append(sym)
            continue

        row = analyze(
            sym, df,
            vol_window=args.vol_window,
            min_dollar_volume=args.min_dollar_volume,
        )
        rows.append(row)

        # 유동성 통과 종목만 히스토리 저장(백테스터 로더 호환: date + OHLCV)
        if row["통과"] and not args.no_save_data:
            out_csv = os.path.join(DATA_DIR, f"{sym}.csv")
            out = df.copy()
            out.index.name = "date"
            out.reset_index().to_csv(out_csv, index=False)
            saved.append(os.path.relpath(out_csv, ROOT))

        print(
            f"  [완료] {sym:<6} 현재가 {row['현재가']:>10,.2f} | "
            f"거래대금 ${row['일평균거래대금($)']:>14,} {row['유동성']} | "
            f"ATR% {row['ATR%']:>5} | 52주위치 {row['52주위치%']}%"
        )

    if not rows:
        print("\n조회 성공한 종목이 없습니다.")
        sys.exit(1)

    result = pd.DataFrame(rows)
    # 통과 종목을 ATR%(변동성) 내림차순으로 정렬 → 추세추종 우선순위 참고
    result = result.sort_values(["통과", "ATR%"], ascending=[False, False])

    out_csv = os.path.join(RESULTS_DIR, f"screener_{datetime.today():%Y%m%d}.csv")
    result.to_csv(out_csv, index=False, encoding="utf-8-sig")

    n_pass = int(result["통과"].sum())
    print("\n" + "=" * 70)
    print("  스크리닝 요약")
    print("=" * 70)
    print(result.to_string(index=False))
    print("=" * 70)
    print(f"  통과(유동성 O & 데이터 충분): {n_pass}/{len(result)}개")
    if saved:
        print(f"  히스토리 저장: {len(saved)}개 -> " + ", ".join(saved))
    if failed:
        print(f"  조회 실패: {', '.join(failed)}")
    print(f"  스코어링 원자료 -> {os.path.relpath(out_csv, ROOT)}")
    print("\n  ※ 유동성/변동성은 무료 일봉 기준. 펀더멘털·실시간 스프레드는 별도 확인 필요.")


if __name__ == "__main__":
    main()
