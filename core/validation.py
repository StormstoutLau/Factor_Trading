"""回测偏差声明（P-011 D6）。

设计依据：DESIGN_backtest_validation.md §4.3。本模块定义"本回测**不声称**什么"，
字段全部来自运行时状态或能力常量；禁止在报告里就地硬编码 ``True``。
"""

from __future__ import annotations

from typing import Any, Mapping

from core.metrics import SHARPE_METHOD

SCHEMA_VERSION = "1.0"

# 能力常量：随能力实现而修改，禁止在调用处硬编码
PIT_SUPPORTED = False
MULTIPLE_TESTING_SUPPORTED = False
BENCHMARK_SUPPORTED = False  # BacktestConfig.benchmark 仅为占位
WALK_FORWARD_AVAILABLE = True

KNOWN_LIMITATIONS = [
    "未做多重检验校正（无 trials 登记）",
    "数据层无 point-in-time 版本轴",
    "基准指数未实现（benchmark 为占位字段）",
    "V2 目标持仓为整数股且含 0.985 现金缓冲系数",
    "V3 为筛选器定位：同日收盘成交、无风控/待执行队列",
]


def build_validation_declaration(
    *,
    risk_free_rate: float,
    universe_report: Mapping[str, Any],
    execution_timing: str,
    benchmark_configured: bool = False,
) -> dict[str, Any]:
    """构造可被第三方复核的偏差声明。

    Args:
        risk_free_rate: 本run 实际使用的年化无风险利率。
        universe_report: ``engine_v2._universe_report()`` 的输出。
        execution_timing: 成交时点口径（V2 = ``"next_open"``）。
        benchmark_configured: 是否配置了基准（仅登记，不声称可比）。

    Returns:
        声明字典（键集固定，见 DESIGN §4.3）。
    """
    survivorship_source = universe_report.get("survivorship") or "unknown"
    return {
        "schema_version": SCHEMA_VERSION,
        "multiple_testing": {"corrected": MULTIPLE_TESTING_SUPPORTED, "n_trials": None},
        "survivorship": {
            "corrected": survivorship_source == "corrected",
            "source": survivorship_source,
        },
        "pit_data": PIT_SUPPORTED,
        "benchmark": {
            "configured": bool(benchmark_configured),
            # 即使配置了基准，本批也不声称"可与基准比较"（无基准实现）
            "comparable": BENCHMARK_SUPPORTED,
        },
        "out_of_sample": {
            "walk_forward_available": WALK_FORWARD_AVAILABLE,
            "used_in_this_run": False,
        },
        "risk_free_rate": float(risk_free_rate),
        "sharpe_method": SHARPE_METHOD,
        "execution_timing": execution_timing,
        "known_limitations": list(KNOWN_LIMITATIONS),
    }
