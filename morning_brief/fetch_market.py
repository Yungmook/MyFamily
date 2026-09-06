#!/usr/bin/env python3
"""아침 브리핑용 시세 스냅샷 생성기.

Claude 예약작업은 클라우드에서 돌기 때문에 로컬 파일을 읽지 못한다.
그래서 결과를 Google Drive 동기화 폴더에 써서 전달한다.

    ~/Library/CloudStorage/GoogleDrive-*/My Drive/morning/market.md

동작 원칙
  - 개별 티커 조회 실패는 그 줄만 "조회 실패"로 적고 계속 진행한다.
  - 전 종목이 실패해도 첫 줄(생성시각)이 있는 파일은 반드시 쓴다.
    (파일이 아예 없으면 브리핑이 "배치 미실행"으로 오인한다.)
  - 마지막에 caffeinate 를 띄워 08:00 evening.py 까지 Mac 이 잠들지 않게 한다.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 조회 대상 — 지수/환율/선물만. 개별 종목(NVDA, TSLA 등)은 다른 경로로 받으므로 넣지 않는다.
TICKERS: list[tuple[str, str]] = [
    ("^DJI", "다우"),
    ("^GSPC", "S&P500"),
    ("^IXIC", "나스닥"),
    ("^SOX", "필라델피아 반도체"),
    ("^KS11", "코스피"),
    ("^KQ11", "코스닥"),
    ("KRW=X", "원/달러"),
    ("NQ=F", "나스닥 선물"),
]

# Google Drive 가 만드는 최상위 폴더 이름 (locale 에 따라 다름)
DRIVE_ROOT_NAMES = ("My Drive", "내 드라이브")

FETCH_RETRIES = 2
RETRY_WAIT_SEC = 1.5
CAFFEINATE_SEC = 7200  # 06:10 실행 기준 08:10 까지


def log(msg: str) -> None:
    print(f"[{datetime.now(KST):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def elog(msg: str) -> None:
    print(f"[{datetime.now(KST):%Y-%m-%d %H:%M:%S}] ERROR {msg}", file=sys.stderr, flush=True)


def resolve_out_dir() -> Path | None:
    """~/Library/CloudStorage/GoogleDrive-*/My Drive/morning 을 찾아 만들어 준다.

    계정 폴더명은 하드코딩하지 않고 glob 으로 탐색한다.
    매칭되는 경로가 하나도 없으면 None 을 돌려준다(호출부에서 종료).
    """
    cloud = Path.home() / "Library" / "CloudStorage"
    if not cloud.is_dir():
        elog(f"CloudStorage 폴더가 없습니다: {cloud}")
        return None

    accounts = sorted(p for p in cloud.glob("GoogleDrive-*") if p.is_dir())
    if not accounts:
        elog(f"GoogleDrive-* 계정 폴더를 찾지 못했습니다: {cloud}/GoogleDrive-*")
        return None

    if len(accounts) > 1:
        log(f"GoogleDrive-* 가 {len(accounts)}개 발견됨: {[p.name for p in accounts]}")
        log(f"첫 번째 계정 폴더를 사용합니다: {accounts[0].name}")
    account = accounts[0]

    drive_root = next((account / n for n in DRIVE_ROOT_NAMES if (account / n).is_dir()), None)
    if drive_root is None:
        elog(f"'My Drive'(또는 '내 드라이브') 폴더가 없습니다: {account}")
        return None

    out_dir = drive_root / "morning"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        elog(f"morning 폴더 생성 실패: {out_dir} ({exc})")
        return None

    log(f"출력 폴더: {out_dir}")
    return out_dir


def fetch_one(symbol: str):
    """(종가, 등락률%, 종가 기준일) 을 돌려준다. 실패하면 None."""
    import yfinance as yf

    last_exc: Exception | None = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            hist = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
            closes = hist["Close"].dropna() if not hist.empty else None
            if closes is None or len(closes) < 2:
                raise ValueError(f"데이터 부족 (rows={0 if closes is None else len(closes)})")
            close = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            if prev == 0:
                raise ValueError("전일 종가가 0")
            return close, (close - prev) / prev * 100.0, closes.index[-1].date()
        except Exception as exc:  # 개별 티커 실패는 그 줄만 실패로 처리한다
            last_exc = exc
            if attempt < FETCH_RETRIES:
                time.sleep(RETRY_WAIT_SEC)

    elog(f"{symbol} 조회 실패: {type(last_exc).__name__}: {last_exc}")
    return None


def build_lines() -> list[str]:
    lines: list[str] = []
    ok = 0
    for symbol, name in TICKERS:
        result = fetch_one(symbol)
        if result is None:
            lines.append(f"- {name}({symbol}): 조회 실패")
            continue
        close, pct, asof = result
        lines.append(f"- {name}({symbol}): {close:,.2f} ({pct:+.2f}%, {asof:%m-%d} 종가)")
        ok += 1
    log(f"조회 완료: 성공 {ok} / 전체 {len(TICKERS)}")
    return lines


def write_market_md(out_dir: Path, lines: list[str]) -> Path:
    """첫 줄은 반드시 '생성시각: YYYY-MM-DD HH:MM KST'."""
    header = f"생성시각: {datetime.now(KST):%Y-%m-%d %H:%M} KST"
    body = "\n".join([header, "", *lines, ""])

    path = out_dir / "market.md"
    tmp = out_dir / "market.md.tmp"
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)  # 부분 기록된 파일이 브리핑에 읽히지 않도록 원자적으로 교체
    log(f"기록 완료: {path} ({len(lines)}개 항목)")
    return path


def keep_awake() -> None:
    """08:00 evening.py 로 기상 상태를 넘겨주기 위해 Mac 절전을 막는다."""
    if sys.platform != "darwin" or shutil.which("caffeinate") is None:
        log("caffeinate 사용 불가 (macOS 아님) — 절전 방지 생략")
        return
    subprocess.Popen(["caffeinate", "-s", "-t", str(CAFFEINATE_SEC)])
    log(f"caffeinate -s -t {CAFFEINATE_SEC} 실행 (약 {CAFFEINATE_SEC // 3600}시간 절전 방지)")


def main() -> int:
    parser = argparse.ArgumentParser(description="아침 브리핑용 시세 스냅샷 생성")
    parser.add_argument("--out", help="출력 폴더 직접 지정 (미지정 시 Google Drive 폴더 자동 탐색)")
    args = parser.parse_args()

    log("fetch_market 시작")

    if args.out:
        out_dir = Path(args.out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        log(f"출력 폴더(수동 지정): {out_dir}")
    else:
        out_dir = resolve_out_dir()

    if out_dir is None:
        elog("출력 경로를 찾지 못해 종료합니다. Google Drive 앱이 켜져 있는지 확인하세요.")
        keep_awake()  # 시세를 못 써도 08:00 기상 핸드오프는 살려 둔다
        return 1

    try:
        lines = build_lines()
    except Exception as exc:  # 전 종목 실패해도 파일은 반드시 남긴다
        elog(f"시세 조회 단계 전체 실패: {type(exc).__name__}: {exc}")
        lines = [f"- {name}({symbol}): 조회 실패" for symbol, name in TICKERS]

    try:
        write_market_md(out_dir, lines)
    except OSError as exc:
        elog(f"market.md 기록 실패: {exc}")
        keep_awake()
        return 1

    keep_awake()
    log("fetch_market 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
