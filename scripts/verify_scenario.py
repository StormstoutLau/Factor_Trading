"""P-059 场景验证统一入口（DESIGN §3.2 / §16 T9）。

用法::

    python scripts/verify_scenario.py --list                      # 列出 17 条场景
    python scripts/verify_scenario.py --scenario S02              # 跑单场景并断言
    python scripts/verify_scenario.py --scenario S02 --day 2024-01-04
    python scripts/verify_scenario.py --scenario S02 --json       # 机器可读
    python scripts/verify_scenario.py --boundaries                # 能力边界 8 键

**边界**：CLI 与 pytest 共用 ``build_scenario`` / ``assert_scenario`` 单一入口，
不做第二套夹具；非 ``backtest`` 场景（raises / stops / limit_price）的断言只在
pytest 内执行，CLI 仅列出其声明。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from _scenarios_assert import assert_scenario  # noqa: E402
from _scenarios_builder import build_scenario  # noqa: E402
from _scenarios_capability import CAPABILITY_BOUNDARIES  # noqa: E402
from _scenarios_cases import SCENARIOS  # noqa: E402
from _scenarios_spec import ScenarioSpec  # noqa: E402


def _plain(value: Any) -> Any:
    """递归转换 numpy / pandas / dataclass 标量，保证 ``--json`` 可序列化。"""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def _print_list() -> None:
    print(f"{'ID':<5}{'LAYER':<7}{'KIND':<13}{'GAPS':<22}TITLE")
    for scenario_id, spec in SCENARIOS.items():
        gaps = ",".join(spec.gaps)
        print(f"{scenario_id:<5}{spec.layer:<7}{spec.kind:<13}{gaps:<22}{spec.title}")
    print(f"\n共 {len(SCENARIOS)} 条；层覆盖 {len({s.layer for s in SCENARIOS.values()})}/7")


def _print_boundaries() -> None:
    # DESIGN §10：能力边界以 JSON 输出（机器可读）。
    print(json.dumps(_plain(CAPABILITY_BOUNDARIES), ensure_ascii=False, indent=2))


def _summarize(spec: ScenarioSpec, run: Any) -> dict[str, Any]:
    buckets = run.trace.buckets
    states: dict[str, int] = {}
    for event in run.trace.state_events:
        states[event["state"]] = states.get(event["state"], 0) + 1
    return {
        "scenario_id": spec.scenario_id,
        "kind": spec.kind,
        "layer": spec.layer,
        "gaps": list(spec.gaps),
        "trade_days": len(run.trade_dates),
        "buckets": len(buckets),
        "ohlc_synthetic": run.ohlc_synthetic,
        "fills": _plain(list(run.trace.fills)),
        "order_states": states,
        "final_cash": run.final_cash,
        "final_nav": run.final_nav,
        "final_positions": _plain(run.final_positions),
        "expected": _plain(
            {
                "fills": spec.expected.fills,
                "no_fill": spec.expected.no_fill,
                "order_states": spec.expected.order_states,
                "nav_days": spec.expected.nav_days,
                "final_cash": spec.expected.final_cash,
                "final_nav": spec.expected.final_nav,
            }
        ),
    }


def _run_scenario(scenario_id: str, day: str | None, as_json: bool) -> int:
    spec = SCENARIOS.get(scenario_id)
    if spec is None:
        print(f"未知场景 {scenario_id!r}；可选：{', '.join(SCENARIOS)}", file=sys.stderr)
        return 2
    if spec.kind != "backtest":
        print(
            f"{scenario_id}: kind={spec.kind}（payload 已声明，断言由 "
            f"pytest tests/test_p059_scenarios.py -k {scenario_id} 执行）"
        )
        return 0

    with tempfile.TemporaryDirectory(prefix=f"p059-{scenario_id}-") as tmp:
        run = build_scenario(spec, Path(tmp))
        assert_scenario(spec, run)
        summary = _summarize(spec, run)
        if day is not None:
            key = pd.Timestamp(day).strftime("%Y-%m-%d")
            if key not in run.trace.buckets:
                print(
                    f"{scenario_id}: 无 {key} 桶；已有 {list(run.trace.buckets)}", file=sys.stderr
                )
                return 2
            summary["day"] = _plain(run.trace.buckets[key])

    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"{scenario_id} [{spec.layer}] {spec.title}")
        print(
            f"  桶 {summary['buckets']}/{summary['trade_days']}  "
            f"成交 {len(summary['fills'])}  订单态 {summary['order_states']}"
        )
        print(
            f"  期末 现金 {summary['final_cash']:.2f}  NAV {summary['final_nav']:.2f}  "
            f"持仓 {summary['final_positions']}"
        )
        if "day" in summary:
            print(json.dumps(summary["day"], ensure_ascii=False, indent=2))
        print("  PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P-059 场景验证入口")
    parser.add_argument("--list", action="store_true", help="列出全部场景")
    parser.add_argument("--boundaries", action="store_true", help="打印能力边界 8 键")
    parser.add_argument("--scenario", help="运行指定场景（如 S02）")
    parser.add_argument("--day", help="输出指定交易日的完整 trace 桶（YYYY-MM-DD）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args(argv)

    if args.list:
        _print_list()
    if args.boundaries:
        _print_boundaries()
    if args.scenario:
        return _run_scenario(args.scenario, args.day, args.json)
    if not (args.list or args.boundaries):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
