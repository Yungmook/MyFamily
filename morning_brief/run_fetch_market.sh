#!/bin/bash
# launchd 가 실행하는 래퍼. stdout/stderr 를 ~/morning_brief/logs/ 에 날짜별로 남긴다.
set -u

DIR="$HOME/morning_brief"
LOG_DIR="$DIR/logs"
mkdir -p "$LOG_DIR"

# 전용 venv 를 우선 사용 (launchd 는 PATH 가 최소라 시스템 python 에는 yfinance 가 없을 수 있음)
PY="$DIR/.venv/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"

exec "$PY" "$DIR/fetch_market.py" >> "$LOG_DIR/fetch_market_$(date +%Y-%m-%d).log" 2>&1
