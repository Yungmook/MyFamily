"""설정 로딩 및 전략 팩토리."""
from __future__ import annotations

from pathlib import Path

import yaml

from .strategy import TrendMAStrategy


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_strategy(cfg: dict) -> TrendMAStrategy:
    """config 의 strategy 섹션으로 :class:`TrendMAStrategy` 를 만든다."""
    s = cfg["strategy"]
    return TrendMAStrategy(
        ma_type=s.get("ma_type", "ema"),
        ma_period=s.get("ma_period", 20),
        slope_lookback=s.get("slope_lookback", 3),
        slope_threshold=s.get("slope_threshold", 0.0),
        use_dual_ma=s.get("use_dual_ma", True),
        fast_period=s.get("fast_period", 10),
        slow_period=s.get("slow_period", 30),
        price_above_ma=s.get("price_above_ma", True),
    )


def default_config_path() -> str:
    """저장소 루트의 config.yaml 경로를 추정한다."""
    here = Path(__file__).resolve()
    root = here.parents[2]  # src/trendbot/config.py -> repo root
    return str(root / "config.yaml")
