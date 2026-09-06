# morning_brief — 시세 스냅샷 배치

Claude 아침 브리핑(예약작업)은 클라우드에서 돌기 때문에 Mac 로컬 파일을 읽지 못한다.
그래서 이 배치가 매일 06:10 에 시세를 조회해 **Google Drive 동기화 폴더**에 써 두고,
브리핑은 Drive 쪽에서 그 파일을 읽는다.

## 설치 (Mac 에서 1회)

```bash
cd <이 저장소>/morning_brief
./install.sh
```

install.sh 가 하는 일
1. `~/morning_brief/` 에 `fetch_market.py`, `run_fetch_market.sh` 복사
2. `~/morning_brief/.venv` 생성 후 `yfinance` 설치
   (launchd 는 PATH 가 최소라 시스템 python 에 의존하면 안 된다)
3. `~/Library/LaunchAgents/com.morningbrief.fetch-market.plist` 생성 후 bootstrap
   — 매일 **06:10** 실행

> 스크립트를 고친 뒤에는 `./install.sh` 를 다시 돌려 `~/morning_brief` 로 반영한다.

## 출력

경로: `~/Library/CloudStorage/GoogleDrive-*/My Drive/morning/market.md`
- 계정 폴더명은 하드코딩하지 않고 `GoogleDrive-*` glob 으로 탐색
- 여러 개면 **첫 번째**를 쓰고 로그에 전부 남김
- `morning` 폴더는 없으면 생성
- 매칭되는 경로가 하나도 없으면 에러 로그 남기고 종료(exit 1)
- Drive 가 한국어 로케일이면 `My Drive` 대신 `내 드라이브` 도 자동으로 인식

형식 (첫 줄 고정):

```
생성시각: 2026-09-06 06:10 KST

- 다우(^DJI): 44,123.45 (+0.52%, 09-05 종가)
- S&P500(^GSPC): 조회 실패
...
```

조회 대상: `^DJI ^GSPC ^IXIC ^SOX ^KS11 ^KQ11 KRW=X NQ=F`
개별 종목(NVDA, TSLA 등)은 다른 경로로 받으므로 **넣지 않는다**.

## 에러 처리

- 티커 하나가 실패하면 그 줄만 `조회 실패` 로 적고 계속 진행 (2회 재시도)
- 전 종목이 실패해도 첫 줄(생성시각)이 있는 파일은 **반드시** 쓴다
  — 파일이 없으면 브리핑이 "배치 미실행"으로 오인하기 때문
- `market.md.tmp` 로 쓴 뒤 rename 하므로 반쯤 쓰인 파일이 읽히지 않는다

## 절전 방지

마지막에 `caffeinate -s -t 7200` 을 띄워 08:00 evening.py 까지 Mac 이 잠들지 않게 한다.
출력 경로를 못 찾아 실패로 끝나는 경우에도 caffeinate 는 실행한다 (기상 핸드오프 유지).

06:10 에 Mac 이 **이미 자고 있으면** launchd 는 깨어난 뒤에야 실행된다. 정시 실행이 필요하면:

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 06:05:00
```

## 로그

`~/morning_brief/logs/fetch_market_YYYY-MM-DD.log` (날짜별)
`~/morning_brief/logs/launchd.{out,err}.log` — 래퍼 자체가 죽은 경우용

## 수동 실행 / 상태 확인

```bash
~/morning_brief/.venv/bin/python3 ~/morning_brief/fetch_market.py
launchctl print gui/$UID/com.morningbrief.fetch-market
launchctl kickstart -p gui/$UID/com.morningbrief.fetch-market
tail -f ~/morning_brief/logs/fetch_market_$(date +%F).log
```

해제:

```bash
launchctl bootout gui/$UID/com.morningbrief.fetch-market
rm ~/Library/LaunchAgents/com.morningbrief.fetch-market.plist
```
