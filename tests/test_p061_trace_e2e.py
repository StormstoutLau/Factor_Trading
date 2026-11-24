"""P-061 端到端验收（T-D01..D04，oracle: manual / invariant / contract / boundary）。"""

from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _scenarios_builder import build_scenario
from _scenarios_spec import ExpectedBlock, ScenarioSpec

A = "000001"
B = "000002"
NO_COST = {
    "commission_rate": 0.0,
    "commission_min": 0.0,
    "stamp_tax_rate": 0.0,
    "slippage_pct": 0.0,
}

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "trace_report.py"
_SPEC = importlib.util.spec_from_file_location("p061_trace_report_e2e", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
trace_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(trace_report)


def _dates(n: int = 5) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n)


def _e2e_spec(root: Path, scenario_id: str) -> ScenarioSpec:
    dates = _dates(5)
    close = np.full((5, 2), 10.0)
    suspend = np.zeros((5, 2), dtype=int)
    suspend[1:, 1] = 1  # B：次日起停牌 → 拒单 → 最终过期
    return ScenarioSpec(
        scenario_id=scenario_id,
        title=scenario_id,
        layer="L5",
        gaps=("P061",),
        dates=dates,
        codes=(A, B),
        close=close,
        suspend=suspend,
        factors={"factor_alpha": np.ones_like(close)},
        signal=np.full((5, 2), 0.5),
        config={
            "audit_trace_dir": root / "audit",
            "write_manifest": True,
            "cost": dict(NO_COST),
            "max_pending_days_buy": 2,
        },
        expected=ExpectedBlock(),
    )


def _trace_csv(root: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(root / "audit" / name, dtype=str, keep_default_na=False)


def test_t_d01_five_questions_answerable(tmp_path: Path) -> None:
    """T-D01 | oracle=manual：固定 scenario 五问逐条可答（读产物而非内存）。"""
    root = tmp_path / "d01"
    build_scenario(_e2e_spec(root, "P061-D01"), root)
    # 报告侧 join：manifest 与 trace 同目录（D-06：run 末写 manifest，事后 join）
    shutil.copy(root / "out" / "manifest.json", root / "audit" / "manifest.json")

    assert trace_report.main(["--run-dir", str(root / "audit")]) == 0
    html_text = (root / "audit" / "trace.html").read_text(encoding="utf-8")
    for label in ("目标", "订单", "成交", "平仓", "数据来源"):
        assert label in html_text

    day = _trace_csv(root, "trace_day.csv")
    order = _trace_csv(root, "trace_order.csv")
    fill = _trace_csv(root, "trace_fill.csv")
    alignment = json.loads((root / "audit" / "alignment.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))

    # ① 有目标无成交的单：B 目标为正，但订单被拒（原因闭集）
    target_b = day[(day["stock"] == B) & (pd.to_numeric(day["target_qty"], errors="coerce") > 0)]
    assert not target_b.empty
    order_b = order[order["stock"] == B].iloc[0]
    assert order_b["reject_reason"] == "suspended"

    # ② 卖出单：A 的平仓原因可读
    assert (day["close_reason"] == "final_liquidation").any()
    assert (fill["order_ref"] == "direct").any()

    # ③ 同日 NAV 差异：alignment 残差与终值
    assert alignment["reconcile"]["residual"] < 1e-8
    snapshots = pd.read_csv(root / "out" / "portfolio_snapshots.csv")
    assert alignment["reconcile"]["snapshots_final_nav"] == pytest.approx(
        float(snapshots["total_value"].iloc[-1]), abs=1e-6
    )

    # ④ 挂起单：B 的终态在 retry / expired 闭集内
    assert order_b["status"] in ("retry", "expired")

    # ⑤ 可复现：指纹 + commit 可读
    assert manifest["input_fingerprint"].startswith("sha256:")
    assert "commit" in manifest["git"]
    assert manifest["config"]["audit_trace_dir"]


def test_t_d02_same_input_same_trace_bytes(tmp_path: Path) -> None:
    """T-D02 | oracle=invariant：同输入两次运行三表字节相同。"""
    first_root = tmp_path / "d02a"
    second_root = tmp_path / "d02b"
    build_scenario(_e2e_spec(first_root, "P061-D02"), first_root)
    build_scenario(_e2e_spec(second_root, "P061-D02"), second_root)
    for name in ("trace_day.csv", "trace_order.csv", "trace_fill.csv"):
        left = (first_root / "audit" / name).read_bytes()
        right = (second_root / "audit" / name).read_bytes()
        assert left == right, name


def test_t_d03_trace_module_import_boundary() -> None:
    """T-D03 | oracle=contract：core.trace 只依赖 stdlib/pandas（不引入上层）。"""
    source = (_REPO_ROOT / "core" / "trace.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {
        "__future__",
        "json",
        "logging",
        "collections",
        "dataclasses",
        "pathlib",
        "typing",
        "pandas",
        "core",
    }
    assert roots <= allowed, roots - allowed
    assert not (roots & {"live", "services", "strategies"})

    executable = Path(sys.executable).parent / (
        "lint-imports.exe" if sys.platform == "win32" else "lint-imports"
    )
    cli = str(executable) if executable.is_file() else shutil.which("lint-imports")
    if cli:
        result = subprocess.run(
            [cli], cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=180
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_t_d04_trace_overhead_below_ten_percent(tmp_path: Path) -> None:
    """T-D04 | oracle=boundary：trace 开启的增量耗时 < 10%（3 次取最小值）。

    计时口径限定在 ``engine.run()``（夹具写入与 setup 两模式相同，计入会放大噪声）。
    取**最小值**而非中位数：长进程后段会出现系统性变慢（figure/GC/内存），
    中位数会被「成对中后跑者」的漂移污染；micro-benchmark 以最优轮次衡量纯增量。
    """
    from _scenarios_builder import _write_fixtures, build_config
    from core.engine_v2 import BacktestEngineV2

    import matplotlib.pyplot as plt

    dates = _dates(20)
    prices = np.full((20, 2), 10.0)

    def one_run(root: Path, enabled: bool) -> float:
        config: dict[str, Any] = {"cost": dict(NO_COST)}
        if enabled:
            config["audit_trace_dir"] = root / "audit"
        spec = ScenarioSpec(
            scenario_id="P061-D04",
            title="D04",
            layer="L5",
            gaps=("P061",),
            dates=dates,
            codes=(A, B),
            close=prices,
            factors={"factor_alpha": np.ones_like(prices)},
            signal=np.full((20, 2), 0.5),
            config=config,
            expected=ExpectedBlock(),
        )
        _write_fixtures(spec, root)
        engine = BacktestEngineV2(build_config(spec, root))
        engine.setup()
        started = time.perf_counter()
        try:
            engine.run()
            return time.perf_counter() - started
        finally:
            plt.close("all")  # 防止 figure 累积拖慢后续轮次（跨模式同口径）

    one_run(tmp_path / "warmup-off", False)
    one_run(tmp_path / "warmup-on", True)
    baseline: list[float] = []
    enabled: list[float] = []
    for index in range(3):
        # 交替先后顺序，抵消「后跑者付 figure/缓存代价」的系统偏差
        if index % 2 == 0:
            baseline.append(one_run(tmp_path / f"off-{index}", False))
            enabled.append(one_run(tmp_path / f"on-{index}", True))
        else:
            enabled.append(one_run(tmp_path / f"on-{index}", True))
            baseline.append(one_run(tmp_path / f"off-{index}", False))
    base_min = min(baseline)
    on_min = min(enabled)
    assert (
        on_min < base_min * 1.10
    ), f"trace 增量超限: baseline_min={base_min:.3f}s enabled_min={on_min:.3f}s"
