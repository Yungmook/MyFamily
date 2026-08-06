"""백테스트 결과를 시각적 HTML 리포트로 생성한다.

자산곡선(equity curve), 주가+이평선+매매시점, 성과지표, 거래내역을
하나의 자체완결 HTML 파일로 저장한다. 외부 라이브러리(matplotlib 등)
없이 인라인 SVG 로 그리므로 브라우저에서 바로 열어볼 수 있다.

사용법:
    python scripts/report.py [--config config.yaml] [--out results/report.html]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trendbot.backtest import run_backtest              # noqa: E402
from trendbot.config import build_strategy, load_config  # noqa: E402
from trendbot.data.loader import load_ohlcv              # noqa: E402
from trendbot.strategy.base import SignalType           # noqa: E402


# --- SVG 좌표 헬퍼 -----------------------------------------------------
def _scale(vals, lo, hi, size, pad_lo, pad_hi, invert=False):
    span = (hi - lo) or 1.0
    out = []
    usable = size - pad_lo - pad_hi
    for v in vals:
        t = (v - lo) / span
        px = pad_lo + t * usable
        out.append(size - px if invert else px)
    return out


def _fmt(n):
    return f"{n:,.0f}"


def _line_chart_equity(equity, initial, W=920, H=300):
    """자산곡선 SVG 를 생성한다 (단일 시리즈 + 초기자본 기준선)."""
    vals = list(equity.values)
    n = len(vals)
    lo, hi = min(vals + [initial]), max(vals + [initial])
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad

    xs = _scale(range(n), 0, n - 1, W, 54, 12)
    ys = _scale(vals, lo, hi, H, 24, 28, invert=True)
    base_y = _scale([initial], lo, hi, H, 24, 28, invert=True)[0]

    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"M{xs[0]:.1f},{H-28:.1f} L" + " L".join(
        f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys)
    ) + f" L{xs[-1]:.1f},{H-28:.1f} Z"

    # y축 눈금 3개
    ticks = []
    for i in range(4):
        v = lo + (hi - lo) * i / 3
        y = _scale([v], lo, hi, H, 24, 28, invert=True)[0]
        ticks.append(
            f'<line x1="54" y1="{y:.1f}" x2="{W-12}" y2="{y:.1f}" class="grid"/>'
            f'<text x="48" y="{y+4:.1f}" class="ytick">{_fmt(v)}</text>'
        )

    return f'''<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="자산곡선">
  {"".join(ticks)}
  <line x1="54" y1="{base_y:.1f}" x2="{W-12}" y2="{base_y:.1f}" class="baseline-ref"/>
  <text x="{W-14}" y="{base_y-6:.1f}" class="reflabel">초기자본 {_fmt(initial)}</text>
  <path d="{area}" class="eq-area"/>
  <polyline points="{pts}" class="eq-line"/>
</svg>'''


def _price_chart(sig, trades, W=920, H=340):
    """주가 + 이평선 + 매수/매도 시점 SVG."""
    closes = list(sig["close"].values)
    ma = list(sig["ma"].values)
    idx = list(sig.index)
    n = len(closes)
    valid_ma = [m for m in ma if m == m]  # NaN 제거
    lo = min(closes + valid_ma)
    hi = max(closes + valid_ma)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad

    xs = _scale(range(n), 0, n - 1, W, 54, 12)

    def y_of(v):
        return _scale([v], lo, hi, H, 24, 28, invert=True)[0]

    price_pts = " ".join(f"{x:.1f},{y_of(c):.1f}" for x, c in zip(xs, closes))
    ma_pts = " ".join(
        f"{x:.1f},{y_of(m):.1f}" for x, m in zip(xs, ma) if m == m
    )

    pos = {t: i for i, t in enumerate(idx)}
    markers = []
    for t in trades:
        if t.entry_time in pos:
            i = pos[t.entry_time]
            x, y = xs[i], y_of(closes[i])
            markers.append(
                f'<path d="M{x:.1f},{y-11:.1f} l5,9 l-10,0 Z" class="mk-buy"/>'
            )
        if t.exit_time in pos:
            i = pos[t.exit_time]
            x, y = xs[i], y_of(closes[i])
            markers.append(
                f'<path d="M{x:.1f},{y+11:.1f} l5,-9 l-10,0 Z" class="mk-sell"/>'
            )

    ticks = []
    for i in range(4):
        v = lo + (hi - lo) * i / 3
        y = y_of(v)
        ticks.append(
            f'<line x1="54" y1="{y:.1f}" x2="{W-12}" y2="{y:.1f}" class="grid"/>'
            f'<text x="48" y="{y+4:.1f}" class="ytick">{_fmt(v)}</text>'
        )

    return f'''<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="주가와 이평선, 매매시점">
  {"".join(ticks)}
  <polyline points="{price_pts}" class="price-line"/>
  <polyline points="{ma_pts}" class="ma-line"/>
  {"".join(markers)}
</svg>'''


def _stat_tiles(m):
    ret = m["total_return_pct"]
    ret_cls = "up" if ret >= 0 else "down"
    tiles = [
        ("총수익률", f"{ret:+.2f}%", ret_cls),
        ("최종자산", _fmt(m["final"]) + "원", ""),
        ("Buy&Hold 대비", f"{ret - m['buy_hold_pct']:+.2f}%p", "up" if ret >= m["buy_hold_pct"] else "down"),
        ("최대낙폭(MDD)", f"-{m['mdd_pct']:.2f}%", "down"),
        ("승률", f"{m['win_rate_pct']:.1f}%", ""),
        ("거래횟수", f"{m['num_trades']}회", ""),
        ("연환산(CAGR)", f"{m['cagr_pct']:+.2f}%", "up" if m["cagr_pct"] >= 0 else "down"),
        ("샤프지수", f"{m['sharpe']:.2f}", ""),
    ]
    cells = "".join(
        f'<div class="tile"><div class="tile-label">{lbl}</div>'
        f'<div class="tile-val {cls}">{val}</div></div>'
        for lbl, val, cls in tiles
    )
    return f'<div class="tiles">{cells}</div>'


def _trade_rows(trades):
    rows = []
    for i, t in enumerate(trades, 1):
        cls = "up" if t.pnl_pct >= 0 else "down"
        rows.append(
            f"<tr><td>{i}</td>"
            f"<td>{str(t.entry_time)[:10]}</td><td class='num'>{_fmt(t.entry_price)}</td>"
            f"<td>{str(t.exit_time)[:10]}</td><td class='num'>{_fmt(t.exit_price)}</td>"
            f"<td class='num {cls}'>{t.pnl_pct:+.2f}%</td>"
            f"<td class='reason'>{t.reason_out}</td></tr>"
        )
    return "".join(rows)


def build_html(cfg, result) -> str:
    m = result.metrics
    sym = cfg["market"].get("symbol", "-")
    src = cfg["market"].get("source", "csv")
    src_label = "샘플 데이터" if src == "csv" else f"{sym}"
    s = cfg["strategy"]
    strat_desc = (
        f"{s.get('ma_type','ema').upper()} {s.get('ma_period')}일선 기울기 "
        f"({'정배열 ' if s.get('use_dual_ma') else ''}추세추종)"
    )

    return f'''<div class="viz-root">
<style>
  .viz-root {{
    color-scheme: light;
    --surface-1:#fcfcfb; --plane:#f9f9f7;
    --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
    --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
    --price:#2a78d6; --ma:#eb6834; --up:#0ca30c; --down:#d03b3b;
    font-family: system-ui,-apple-system,"Segoe UI",sans-serif;
    max-width:980px; margin:0 auto; padding:20px; color:var(--text-primary);
  }}
  @media (prefers-color-scheme:dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme:dark;
      --surface-1:#1a1a19; --plane:#0d0d0d;
      --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
      --price:#3987e5; --ma:#d95926;
    }}
  }}
  :root[data-theme="dark"] .viz-root {{
    color-scheme:dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
    --price:#3987e5; --ma:#d95926;
  }}
  .viz-root h1 {{ font-size:1.4rem; margin:0 0 4px; }}
  .viz-root .sub {{ color:var(--text-secondary); font-size:.9rem; margin-bottom:18px; }}
  .tiles {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:24px; }}
  @media (max-width:640px) {{ .tiles {{ grid-template-columns:repeat(2,1fr); }} }}
  .tile {{ background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:12px 14px; }}
  .tile-label {{ color:var(--muted); font-size:.78rem; margin-bottom:6px; }}
  .tile-val {{ font-size:1.35rem; font-weight:650; }}
  .tile-val.up {{ color:var(--up); }} .tile-val.down {{ color:var(--down); }}
  .card {{ background:var(--surface-1); border:1px solid var(--border); border-radius:12px; padding:16px 18px; margin-bottom:20px; }}
  .card h2 {{ font-size:1.02rem; margin:0 0 10px; }}
  .legend {{ display:flex; gap:16px; font-size:.82rem; color:var(--text-secondary); margin-bottom:6px; flex-wrap:wrap; }}
  .legend i {{ display:inline-block; width:14px; height:3px; border-radius:2px; vertical-align:middle; margin-right:5px; }}
  .legend .sw-buy,.legend .sw-sell {{ width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent; }}
  .legend .sw-buy {{ border-bottom:9px solid var(--up); }}
  .legend .sw-sell {{ border-top:9px solid var(--down); }}
  .chart {{ width:100%; height:auto; display:block; }}
  .grid {{ stroke:var(--grid); stroke-width:1; }}
  .baseline-ref {{ stroke:var(--baseline); stroke-width:1.5; stroke-dasharray:4 4; }}
  .reflabel {{ fill:var(--muted); font-size:11px; text-anchor:end; }}
  .ytick {{ fill:var(--muted); font-size:11px; text-anchor:end; font-variant-numeric:tabular-nums; }}
  .eq-area {{ fill:var(--price); opacity:.12; }}
  .eq-line {{ fill:none; stroke:var(--price); stroke-width:2; stroke-linejoin:round; }}
  .price-line {{ fill:none; stroke:var(--price); stroke-width:1.6; stroke-linejoin:round; }}
  .ma-line {{ fill:none; stroke:var(--ma); stroke-width:2; stroke-linejoin:round; }}
  .mk-buy {{ fill:var(--up); stroke:var(--surface-1); stroke-width:1; }}
  .mk-sell {{ fill:var(--down); stroke:var(--surface-1); stroke-width:1; }}
  table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
  th,td {{ padding:7px 10px; border-bottom:1px solid var(--border); text-align:left; }}
  th {{ color:var(--muted); font-weight:600; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.up {{ color:var(--up); }} td.down {{ color:var(--down); }}
  td.reason {{ color:var(--text-secondary); font-size:.8rem; }}
</style>

<h1>추세매매 백테스트 결과</h1>
<div class="sub">종목: {src_label} &nbsp;·&nbsp; 전략: {strat_desc} &nbsp;·&nbsp; 기간: {m['start']} ~ {m['end']}</div>

{_stat_tiles(m)}

<div class="card">
  <h2>자산곡선 (Equity Curve)</h2>
  <div class="legend"><span><i class="eq" style="background:var(--price)"></i>평가자산</span>
    <span><i style="background:var(--baseline)"></i>초기자본 기준선</span></div>
  {_line_chart_equity(result.equity_curve, m['initial'])}
</div>

<div class="card">
  <h2>주가 · 이평선 · 매매시점</h2>
  <div class="legend">
    <span><i style="background:var(--price)"></i>종가</span>
    <span><i style="background:var(--ma)"></i>이평선({cfg['strategy'].get('ma_period')})</span>
    <span><i class="sw-buy"></i>매수</span>
    <span><i class="sw-sell"></i>매도</span>
  </div>
  {_price_chart(result.signals, result.trades)}
</div>

<div class="card">
  <h2>거래 내역 ({m['num_trades']}건)</h2>
  <table>
    <thead><tr><th>#</th><th>매수일</th><th>매수가</th><th>매도일</th><th>매도가</th><th>손익</th><th>청산 사유</th></tr></thead>
    <tbody>{_trade_rows(result.trades)}</tbody>
  </table>
</div>
</div>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="백테스트 결과 HTML 리포트 생성")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default="results/report.html")
    args = parser.parse_args()

    cfg = load_config(args.config)
    df = load_ohlcv(cfg["market"])
    strategy = build_strategy(cfg)
    acc, strat = cfg["account"], cfg["strategy"]
    result = run_backtest(
        df, strategy,
        initial_cash=acc["initial_cash"],
        order_ratio=acc.get("order_ratio", 0.99),
        fee_pct=acc.get("fee_pct", 0.05),
        slippage_pct=acc.get("slippage_pct", 0.02),
        stop_loss_pct=strat.get("stop_loss_pct", 0.0),
        take_profit_pct=strat.get("take_profit_pct", 0.0),
    )

    fragment = build_html(cfg, result)
    page = (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>추세매매 백테스트 결과</title>"
        "<style>body{margin:0;background:#f9f9f7}"
        "@media(prefers-color-scheme:dark){body{background:#0d0d0d}}</style>"
        f"</head><body>{fragment}</body></html>"
    )
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"리포트 생성 완료 -> {args.out}")
    print(f"  총수익률 {result.metrics['total_return_pct']:+.2f}% / 거래 {result.metrics['num_trades']}건")


if __name__ == "__main__":
    main()
