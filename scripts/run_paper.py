"""페이퍼트레이딩(실시간 가상매매) 실행 CLI.

업비트 공개 시세를 주기적으로 조회해 최신 신호대로 가상 주문을 낸다.
실거래가 아니므로 자금 손실 위험이 없다.

사용법:
    python scripts/run_paper.py [--config config.yaml] [--iters N]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trendbot.config import build_strategy, load_config  # noqa: E402
from trendbot.paper_trader import run_paper_trading       # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="추세매매 페이퍼트레이딩")
    parser.add_argument("--config", default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--iters", type=int, default=None, help="반복 횟수(생략 시 무한)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    # 페이퍼트레이딩은 실시간 시세가 필요하므로 upbit 소스를 권장
    if cfg["market"].get("source") == "csv":
        logging.warning("페이퍼트레이딩에는 실시간 데이터가 필요합니다. config 의 market.source 를 'upbit' 로 바꾸세요.")

    logging.basicConfig(
        level=getattr(logging, cfg["run"].get("log_level", "INFO")),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    strategy = build_strategy(cfg)
    run_paper_trading(cfg, strategy, max_iters=args.iters)


if __name__ == "__main__":
    main()
