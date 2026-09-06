#!/bin/bash
# Mac 에서 실행: ~/morning_brief 설치 + venv + launchd(매일 06:10) 등록까지 한 번에.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "이 스크립트는 macOS 에서 실행해야 합니다 (launchd/caffeinate 필요)." >&2
    exit 1
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HOME/morning_brief"
LABEL="com.morningbrief.fetch-market"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "==> 파일 설치: $DIR"
mkdir -p "$DIR/logs"
cp "$SRC/fetch_market.py" "$SRC/run_fetch_market.sh" "$DIR/"
chmod +x "$DIR/fetch_market.py" "$DIR/run_fetch_market.sh"

echo "==> venv 준비: $DIR/.venv"
[ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/python3" -m pip install --quiet --upgrade pip
"$DIR/.venv/bin/python3" -m pip install --quiet --upgrade yfinance

echo "==> launchd plist 생성: $PLIST"
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__HOME__|$HOME|g" "$SRC/$LABEL.plist.template" > "$PLIST"

echo "==> launchd 등록 (매일 06:10)"
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/$LABEL"

echo
echo "설치 완료. 상태:"
launchctl print "gui/$UID/$LABEL" | grep -E "state|program|runs" || true
echo
echo "수동 실행으로 확인하려면:"
echo "  launchctl kickstart -p gui/$UID/$LABEL   # launchd 경로 그대로 실행"
echo "  \$HOME/morning_brief/.venv/bin/python3 \$HOME/morning_brief/fetch_market.py  # 직접 실행"
