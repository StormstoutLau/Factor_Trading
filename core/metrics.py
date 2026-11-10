"""指标单一口径（P-011 D5）。

设计依据：DESIGN_backtest_validation.md §4.2。V2（``analytics``）与 V3
（``engine_v3_vector._metrics_kernel``）必须由同一组公式定义，
避免"同名指标不同口径"（Sharpe 的无风险利率、最大回撤的符号与锚点、
年化分母）在报告层制造假差异。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

DEFAULT_RISK_FREE_RATE = 0.03
ANNUALIZATION_DAYS = 252
SHARPE_METHOD = "annual_return_minus_rf_over_annual_vol"

# 指标口径声明（P-011 D5 / DESIGN §5.4）：随结果落 additional_info/results，
# 让报告消费者无需读码即可复核公式与常量；引擎侧用运行时 rf 覆盖默认值。
METRICS_METHOD: dict[str, object] = {
    "annualization_days": ANNUALIZATION_DAYS,
    "risk_free_rate": DEFAULT_RISK_FREE_RATE,
    "annual_return": "(1+total_return)**(252/N)-1, N=len(portfolio_value)",
    "annual_volatility": "std(diff_returns,ddof=0)*sqrt(252)",
    "sharpe_ratio": "(annual_return-risk_free_rate)/annual_volatility",
    "max_drawdown": "max((cummax(pv/pv0)-pv/pv0)/cummax(pv/pv0)), >=0 量级约定（F-R1）",
}


@dataclass(frozen=True)
class MetricsResult:
    """统一口径的绩效指标。

    Attributes:
        max_drawdown: **非负量级**（0.19 表示最大回撤 19%）。
    """

    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    final_value: float
    n_periods: int
    risk_free_rate: float


def sharpe_ratio(annual_return: float, annual_volatility: float, risk_free_rate: float) -> float:
    """``(annual_return - rf) / annual_vol``；波动为 0 时返回 0.0。"""
    if annual_volatility <= 0:
        return 0.0
    return (annual_return - risk_free_rate) / annual_volatility


def compute_metrics(
    portfolio_value: Sequence[float] | np.ndarray,
    *,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods: int = ANNUALIZATION_DAYS,
) -> MetricsResult:
    """由组合价值序列计算指标（唯一口径）。

    Args:
        portfolio_value: 组合价值序列（逐日收盘），要求 ``len >= 2``。
        risk_free_rate: 年化无风险利率。
        periods: 年化交易日数。

    Raises:
        ValueError: 序列长度小于 2（唯一抛出处）。

    Note:
        公式（``N = len(portfolio_value)``、``pv0 = portfolio_value[0]``）：

        - ``returns[t] = (pv[t]-pv[t-1])/pv[t-1]``（N-1 个差分收益）
        - ``cumulative[t] = pv[t]/pv0``（N 点，含 t=0 锚点 1.0）
        - ``annual_return = (1+total_return)**(periods/N) - 1``
        - ``annual_vol = std(returns, ddof=0) * sqrt(periods)``
        - ``max_drawdown = max((cummax(cumulative)-cumulative)/cummax(cumulative))``
    """
    pv = np.asarray(portfolio_value, dtype=float)
    n = int(pv.size)
    if n < 2:
        raise ValueError(f"portfolio_value 至少需要 2 个点，当前 {n}")

    returns = np.diff(pv) / pv[:-1]
    cumulative = pv / pv[0]
    total_return = float(cumulative[-1] - 1.0)
    annual_return = float((1.0 + total_return) ** (periods / n) - 1.0)
    annual_volatility = float(np.std(returns) * np.sqrt(periods))

    running_max = np.maximum.accumulate(cumulative)
    drawdown = (running_max - cumulative) / running_max

    return MetricsResult(
        total_return=total_return,
        annual_return=annual_return,
        annual_volatility=annual_volatility,
        sharpe_ratio=sharpe_ratio(annual_return, annual_volatility, risk_free_rate),
        max_drawdown=float(np.max(drawdown)),
        final_value=float(pv[-1]),
        n_periods=n,
        risk_free_rate=float(risk_free_rate),
    )
