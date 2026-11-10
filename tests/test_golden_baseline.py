"""P-013：golden 基线断言（锁定当前行为，**不证明正确性**）。

边界（DESIGN §1 / A20）：本测试只回答「当前代码是否仍产生与基线一致的结果」，
不回答「结果是否正确」。正确性由 P-011 的 L1-L3 承担（不变量 / 参考实现差分 /
事件级等价）。

基线由 ``scripts/record_golden.py`` 生成，case 构造器为 ``tests/_golden_cases.py``
（与录制脚本共用同一份，杜绝两侧夹具漂移）。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from _golden_cases import CASE_IDS, build_case

GOLDEN_DIR = Path(__file__).parent / "golden"

_MONEY_PATHS = (
    ("nav", "first"),
    ("nav", "last"),
    ("nav", "min"),
    ("nav", "max"),
    ("metrics", "final_value"),
    ("trades", "total_amount"),
    ("trades", "total_cost"),
)

_RATIO_PATHS = (
    ("metrics", "total_return"),
    ("metrics", "annual_return"),
    ("metrics", "annual_volatility"),
    ("metrics", "sharpe_ratio"),
    ("metrics", "max_drawdown"),
)

_INT_PATHS = (
    ("nav", "length"),
    ("trades", "count"),
)


def _load(case_id: str) -> dict:
    path = GOLDEN_DIR / f"{case_id}.json"
    assert path.exists(), f"缺少基线文件 {path}（请先运行 scripts/record_golden.py）"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_close(case_id: str, label: str, expected: float, actual: float, rtol, atol) -> None:
    if not math.isclose(actual, expected, rel_tol=rtol, abs_tol=atol):
        rel_err = abs(actual - expected) / abs(expected) if expected else float("inf")
        raise AssertionError(
            f"[{case_id}] {label}: expected={expected!r} got={actual!r} "
            f"rel_err={rel_err:.3e} (rtol={rtol:g}, atol={atol:g})"
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_golden_case(case_id: str, tmp_path):
    """重跑 case 并与基线逐字段比对（分字段容差；计数精确）。"""
    baseline = _load(case_id)
    tol = baseline["tolerance"]
    actual = build_case(case_id, tmp_path)

    rtol = float(tol["rtol"])
    atol = float(tol["atol"])
    money_atol = float(tol.get("money_atol", atol))

    for section, key in _MONEY_PATHS:
        _assert_close(
            case_id,
            f"{section}.{key}",
            float(baseline[section][key]),
            float(actual[section][key]),
            rtol,
            money_atol,
        )

    for section, key in _RATIO_PATHS:
        _assert_close(
            case_id,
            f"{section}.{key}",
            float(baseline[section][key]),
            float(actual[section][key]),
            rtol,
            atol,
        )

    for section, key in _INT_PATHS:
        assert int(actual[section][key]) == int(baseline[section][key]), (
            f"[{case_id}] {section}.{key}: expected={baseline[section][key]!r} "
            f"got={actual[section][key]!r}（计数不允许漂移）"
        )


def test_all_cases_present():
    """I5：`case_id` 集合恰为 G1-G6，缺一即 fail。"""
    found = {path.stem for path in GOLDEN_DIR.glob("*.json")}
    assert found == set(
        CASE_IDS
    ), f"基线集合不完整：found={sorted(found)} expected={list(CASE_IDS)}"


def test_baseline_schema_valid():
    """I1/I3/I6：schema 字段齐备、数值有限、容差不被放宽。"""
    for case_id in CASE_IDS:
        payload = _load(case_id)

        assert payload["schema_version"] == "1.0", f"[{case_id}] schema_version 非 1.0"
        assert payload["case_id"] == case_id
        assert payload["git_commit"], f"[{case_id}] 缺少 git_commit"
        assert payload["engine"] in ("v2", "v3")
        assert payload["scenario"] in ("baseline", "cost", "mask", "delisting", "suspend")

        tol = payload["tolerance"]
        assert float(tol["rtol"]) <= 1e-9, f"[{case_id}] rtol 被放宽到 {tol['rtol']}"
        assert float(tol["money_atol"]) <= 1e-6, f"[{case_id}] money_atol 被放宽"

        for section, key in _MONEY_PATHS + _RATIO_PATHS:
            value = float(payload[section][key])
            assert math.isfinite(value), f"[{case_id}] {section}.{key} 非有限值: {value}"
        for section, key in _INT_PATHS:
            assert isinstance(payload[section][key], int), f"[{case_id}] {section}.{key} 应为整数"
