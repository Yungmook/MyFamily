"""백테스트 실행 CLI.

사용법:
    python scripts/run_backtest.py [--config config.yaml]
"""
from __future__ import annotations

import argparse
import os
import sys

# src 를 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trendbot.backtest import run_backtest          # noqa: E402
from trendbot.config import build_strategy, load_config  # noqa: E402
from trendbot.data.loader import load_ohlcv          # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="추세매매 백테스트")
    parser.add_argument("--config", default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--trades", action="store_true", help="개별 거래 내역 출력")
    args = parser.parse_args()

    cfg = load_config(args.config)
    df = load_ohlcv(cfg["market"])
    strategy = build_strategy(cfg)
    acc = cfg["account"]
    strat = cfg["strategy"]

    result = run_backtest(
        df,
        strategy,
        initial_cash=acc["initial_cash"],
        order_ratio=acc.get("order_ratio", 0.99),
        fee_pct=acc.get("fee_pct", 0.05),
        slippage_pct=acc.get("slippage_pct", 0.02),
        stop_loss_pct=strat.get("stop_loss_pct", 0.0),
        take_profit_pct=strat.get("take_profit_pct", 0.0),
    )

    print(result.summary())

    if args.trades:
        print("\n[거래 내역]")
        for i, t in enumerate(result.trades, 1):
            print(
                f"  {i:>3}. {str(t.entry_time)[:10]} 매수 {t.entry_price:,.0f}"
                f" -> {str(t.exit_time)[:10]} 매도 {t.exit_price:,.0f}"
                f" | 손익 {t.pnl_pct:+.2f}% ({t.reason_out})"
            )


if __name__ == "__main__":
    main()
