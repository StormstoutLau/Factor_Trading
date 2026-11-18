"""仓位管理（position sizing）纯函数层（P-047）。

设计依据：``docs/DESIGN_p047_position_sizing.md``（D2 类型 / D3 方法契约 / D4 现金预算）。

契约（I4）：
- 全部无副作用：不 print、不读文件、不读时间、无全局状态、无随机；
- 异常仅 ``ValueError``（形状/参数非法）与 ``KeyError``（缺价格，调用方用 ``prices.get`` 规避）；
- 权重/价格入参为 ``Mapping[str, float]``，不绑定 pandas；
- 默认 ``method="none"`` → 完全零行为（返回输入副本）。

本模块**不做整手落地**：``granularity`` 仅用于预算估算与 ``min_size/max_size`` 过滤，
最终整手由 ``core.target_positions.build_target_positions`` 统一出口完成（DESIGN §4 边界 1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "SizingConfig",
    "SizingDiagnostics",
    "SizingResult",
    "RiskContribution",
    "CashBudgetResult",
    "SizingState",
    "estimate_buy_cash",
    "kelly_fraction_scale",
    "vol_target_scale",
    "risk_contributions",
    "apply_sizing",
    "cash_budget_scale",
    "pyramid_step",
    "holding_age",
]


# ---------------------------------------------------------------------------
# 配置与结果类型（D2）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SizingConfig:
    """仓位管理配置（默认值与既有 CostConfig / build_target_positions 对齐）。"""

    method: Literal["none", "kelly", "vol_target", "risk_parity"] = "none"
    kelly_fraction: float = 0.5  # 0 < f <= 1；半凯利默认
    target_vol: float = 0.15  # 年化目标波动
    vol_lookback: int = 60  # 交易日
    atr_period: int = 14  # Wilder
    atr_k: float = 2.0  # Turtle 2N
    max_weight: float = 1.0
    min_weight: float = 0.0
    max_size: Optional[float] = None  # 单标的金额上限（元）
    min_size: Optional[float] = None  # 单标的金额下限（元），过滤后余额留现金
    granularity: int = 100
    cash_buffer: float = 0.985  # 与 build_target_positions 同值
    commission_rate: float = 0.0003  # 与 CostConfig 同默认
    commission_min: float = 5.0
    slippage_pct: float = 0.001
    pyramid_enabled: bool = False
    pyramid_max_adds: int = 3
    pyramid_decay: float = 0.5
    pyramid_step_atr: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 < self.kelly_fraction <= 1.0:
            raise ValueError(f"kelly_fraction 必须在 (0, 1]: {self.kelly_fraction}")
        if self.target_vol <= 0.0:
            raise ValueError(f"target_vol 必须 > 0: {self.target_vol}")
        if self.granularity <= 0:
            raise ValueError(f"granularity 必须 > 0: {self.granularity}")
        if self.max_weight <= 0.0 or self.max_weight > 1.0:
            raise ValueError(f"max_weight 必须在 (0, 1]: {self.max_weight}")
        if self.min_weight < 0.0 or self.min_weight > self.max_weight:
            raise ValueError(f"min_weight 必须在 [0, max_weight]: {self.min_weight}")


@dataclass(frozen=True)
class SizingDiagnostics:
    """诊断信息（JSON 安全）。"""

    reasons: Mapping[str, str]
    dropped: tuple[str, ...] = ()
    clipped: tuple[str, ...] = ()


@dataclass(frozen=True)
class SizingResult:
    """sizing 输出：最终目标权重 + 组合缩放系数 + 诊断。"""

    weights: Mapping[str, float]
    scale: float
    diagnostics: SizingDiagnostics


@dataclass(frozen=True)
class RiskContribution:
    """风险贡献诊断（只诊断、不求解；U-P047-2）。"""

    rc: Mapping[str, float]
    pct: Mapping[str, float]


@dataclass(frozen=True)
class CashBudgetResult:
    """现金预算结果（实算 buy_cost 与 budget，供诊断/断言）。"""

    weights: Mapping[str, float]
    buy_cost: float
    budget: float
    scale: float


@dataclass(frozen=True)
class SizingState:
    """金字塔加仓状态（可序列化，P-051 可存 extras）。"""

    entry_price: float
    last_add_price: float
    add_count: int = 0


# ---------------------------------------------------------------------------
# D4 买入现金（与 ExecutionSimulator._calculate_cost 同源）
# ---------------------------------------------------------------------------


def estimate_buy_cash(
    amount: float,
    *,
    commission_rate: float,
    commission_min: float = 5.0,
    slippage_pct: float = 0.0,
) -> float:
    """买入成交所需现金（含佣金、滑点；``amount`` 为不含费用本金）。

    同源限定：默认股票路径且无 ``CostConfig.asset_costs`` 按资产覆盖
    （DESIGN F-S4-P047-5）。``amount <= 0`` 返回 0，避免 ``max(0, min)``
    把最低佣金计入空单（F-S4-P047-2）。
    """
    if amount <= 0:
        return 0.0
    commission = max(amount * commission_rate, commission_min)
    return amount + commission + amount * slippage_pct


# ---------------------------------------------------------------------------
# D3 方法
# ---------------------------------------------------------------------------


def _as_vector(
    weights: Mapping[str, float], codes: Sequence[str]
) -> tuple[np.ndarray, dict[str, int]]:
    """按 ``codes`` 顺序展开权重向量；未出现的 code 记 0。"""
    pos = {code: i for i, code in enumerate(codes)}
    vec = np.zeros(len(codes), dtype=float)
    for code, weight in weights.items():
        if code not in pos:
            raise ValueError(f"权重含未在 codes 中声明的标的: {code}")
        vec[pos[code]] = float(weight)
    return vec, pos


def _check_cov(cov: np.ndarray, codes: Sequence[str]) -> np.ndarray:
    """协方差形状校验（fail-fast）。"""
    matrix = np.asarray(cov, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"cov 必须为方阵: shape={matrix.shape}")
    if matrix.shape[0] != len(codes):
        raise ValueError(f"cov 维度 {matrix.shape[0]} 与 codes 长度 {len(codes)} 不一致")
    return matrix


def kelly_fraction_scale(
    expected_return: float, variance: float, *, fraction: float = 0.5
) -> tuple[float, str]:
    """分数凯利缩放：``scale = clip(fraction * μ/σ², 0, 1)``。

    Returns:
        (scale, reason)；``reason`` ∈ {"", "zero_var", "non_positive_edge", "clipped_max"}
    """
    if not 0.0 < fraction <= 1.0:
        raise ValueError(f"fraction 必须在 (0, 1]: {fraction}")
    if variance <= 0.0:
        return 0.0, "zero_var"
    if expected_return <= 0.0:
        return 0.0, "non_positive_edge"
    raw = fraction * float(expected_return) / float(variance)
    if raw >= 1.0:
        return 1.0, "clipped_max"
    return raw, ""


def vol_target_scale(
    weights: Mapping[str, float],
    cov: np.ndarray,
    *,
    codes: Sequence[str],
    target_vol: float = 0.15,
) -> tuple[dict[str, float], float, str]:
    """波动率目标缩放：``scale = min(target_vol/σ_p, 1.0)``（不加杠杆）。

    Returns:
        (缩放后权重, scale, reason)；``reason`` ∈ {"", "zero_vol"}
    """
    if target_vol <= 0.0:
        raise ValueError(f"target_vol 必须 > 0: {target_vol}")
    matrix = _check_cov(cov, codes)
    vec, _ = _as_vector(weights, codes)
    sigma_p = float(np.sqrt(max(vec @ matrix @ vec, 0.0)))
    if sigma_p <= 0.0:
        return {code: float(weight) for code, weight in weights.items()}, 1.0, "zero_vol"
    scale = min(float(target_vol) / sigma_p, 1.0)
    return {code: float(weight) * scale for code, weight in weights.items()}, scale, ""


def risk_contributions(
    weights: Mapping[str, float], cov: np.ndarray, *, codes: Sequence[str]
) -> RiskContribution:
    """风险贡献诊断：``RC_i = w_i(Σw)_i/σ_p``，``pct = RC/σ_p``（和为 1）。"""
    matrix = _check_cov(cov, codes)
    vec, _ = _as_vector(weights, codes)
    sigma_p = float(np.sqrt(max(vec @ matrix @ vec, 0.0)))
    if sigma_p <= 0.0:
        return RiskContribution(rc={code: 0.0 for code in codes}, pct={code: 0.0 for code in codes})
    marginal = matrix @ vec
    rc = {code: float(vec[i] * marginal[i] / sigma_p) for i, code in enumerate(codes)}
    pct = {code: float(value / sigma_p) for code, value in rc.items()}
    return RiskContribution(rc=rc, pct=pct)


# ---------------------------------------------------------------------------
# D3 主入口
# ---------------------------------------------------------------------------


def apply_sizing(
    weights: Mapping[str, float],
    *,
    config: SizingConfig,
    cov: Optional[np.ndarray] = None,
    codes: Optional[Sequence[str]] = None,
    expected_returns: Optional[Mapping[str, float]] = None,
    total_value: Optional[float] = None,
    prices: Optional[Mapping[str, float]] = None,
) -> SizingResult:
    """按 ``config.method`` 缩放目标权重，并施加权重/金额约束。

    分派语义（DESIGN D3）：
    - ``none``：不做方法缩放（默认配置下完全幂等），但仍施加约束层；
    - ``kelly``：逐标的缩放 ``fraction·μ_i/σ²_i``；
    - ``vol_target``：组合层缩放 ``min(target_vol/σ_p, 1)``；
    - ``risk_parity``：**只输出诊断**，权重不变（U-P047-2）。

    随后统一裁剪 ``[min_weight, max_weight]``、按 ``min_size/max_size``
    过滤（需 ``total_value`` + ``prices``），最后总权重 >1 时等比缩放。
    """
    base = {code: float(weight) for code, weight in weights.items()}
    reasons: dict[str, str] = {}
    dropped: list[str] = []
    clipped: list[str] = []
    scale = 1.0

    if config.method == "kelly":
        if codes is None or cov is None:
            raise ValueError("method='kelly' 需要 codes 与 cov")
        matrix = _check_cov(cov, codes)
        pos = {code: i for i, code in enumerate(codes)}
        for code in base:
            if code not in pos:
                reasons[code] = "no_cov"
                continue
            variance = float(matrix[pos[code], pos[code]])
            mu = (
                float(expected_returns[code])
                if expected_returns and code in expected_returns
                else 0.0
            )
            if expected_returns is None or code not in expected_returns:
                reasons[code] = "no_expected_return"
                continue
            scale_i, reason = kelly_fraction_scale(mu, variance, fraction=config.kelly_fraction)
            base[code] *= scale_i
            if reason:
                reasons[code] = reason
        old_total = sum(float(weight) for weight in weights.values())
        new_total = sum(base.values())
        scale = new_total / old_total if old_total > 0.0 else 1.0

    elif config.method == "vol_target":
        if codes is None or cov is None:
            raise ValueError("method='vol_target' 需要 codes 与 cov")
        scaled, scale, reason = vol_target_scale(
            base, cov, codes=codes, target_vol=config.target_vol
        )
        base = scaled
        if reason:
            reasons["portfolio"] = reason

    elif config.method == "risk_parity":
        if codes is None or cov is None:
            raise ValueError("method='risk_parity' 需要 codes 与 cov")
        rc = risk_contributions(base, cov, codes=codes)
        for code, pct in rc.pct.items():
            reasons[code] = f"rc_pct={pct:.6f}"

    elif config.method != "none":  # pragma: no cover — Literal 已限定取值
        raise ValueError(f"未知 sizing method: {config.method}")

    # 权重裁剪（I5）
    for code in base:
        weight = base[code]
        if weight > config.max_weight:
            base[code] = config.max_weight
            clipped.append(code)
        elif weight < config.min_weight:
            base[code] = config.min_weight
            clipped.append(code)

    # 金额约束（需 total_value + prices）
    if total_value is not None and total_value > 0.0 and prices:
        for code in list(base):
            price = prices.get(code)
            if price is None or price <= 0.0:
                reasons[code] = "no_price"
                dropped.append(code)
                base[code] = 0.0
                continue
            value = base[code] * total_value
            if config.min_size is not None and value < config.min_size:
                reasons[code] = "dropped_min_size"
                dropped.append(code)
                base[code] = 0.0
            elif config.max_size is not None and value > config.max_size:
                reasons[code] = "clipped_max_size"
                base[code] = config.max_size / total_value
                if code not in clipped:
                    clipped.append(code)

    # 总权重 >1 → 等比缩放（不加杠杆；不重新归一化）
    total = sum(base.values())
    if total > 1.0:
        ratio = 1.0 / total
        base = {code: weight * ratio for code, weight in base.items()}
        scale *= ratio

    return SizingResult(
        weights=base,
        scale=scale,
        diagnostics=SizingDiagnostics(
            reasons=reasons, dropped=tuple(dropped), clipped=tuple(clipped)
        ),
    )


def cash_budget_scale(
    weights: Mapping[str, float],
    *,
    cash: float,
    prices: Mapping[str, float],
    total_value: float,
    config: SizingConfig,
) -> CashBudgetResult:
    """现金预算法：floor 整手后确保 ``buy_cost <= cash·cash_buffer``。

    只用**当前现金**（不含当日卖出回款，G10）；最多 3 次等比收缩，
    仍超预算则 ``scale=0``（空仓守恒）。卖出/清仓侧不受本函数约束。
    """
    if cash < 0.0:
        raise ValueError(f"cash 必须 >= 0: {cash}")
    if total_value <= 0.0:
        raise ValueError(f"total_value 必须 > 0: {total_value}")

    budget = float(cash) * config.cash_buffer
    scale = 1.0

    def _round_trip(scale_value: float) -> tuple[dict[str, float], float]:
        quantities: dict[str, float] = {}
        for code, weight in weights.items():
            price = prices.get(code)
            if price is None or price <= 0.0:
                raise KeyError(f"缺少有效价格: {code}")
            target = weight * scale_value * total_value * config.cash_buffer / price
            lots = np.floor(target / config.granularity) * config.granularity
            quantities[code] = float(lots)
        cost = sum(
            estimate_buy_cash(
                qty * prices[code],
                commission_rate=config.commission_rate,
                commission_min=config.commission_min,
                slippage_pct=config.slippage_pct,
            )
            for code, qty in quantities.items()
        )
        scaled = {
            code: (qty * prices[code] / total_value if total_value > 0.0 else 0.0)
            for code, qty in quantities.items()
        }
        return scaled, cost

    for _ in range(3):
        scaled, cost = _round_trip(scale)
        if cost <= budget:
            return CashBudgetResult(weights=scaled, buy_cost=cost, budget=budget, scale=scale)
        scale = scale * budget / cost

    return CashBudgetResult(
        weights={code: 0.0 for code in weights}, buy_cost=0.0, budget=budget, scale=0.0
    )


def pyramid_step(
    state: SizingState, *, price: float, atr: float, config: SizingConfig
) -> tuple[SizingState, float]:
    """金字塔加仓：只浮盈加仓、递减、禁摊亏。

    Returns:
        (新状态, 加仓增量权重)；不满足条件返回 ``(state, 0.0)`` 且状态不变。
    """
    if not config.pyramid_enabled:
        return state, 0.0
    if state.add_count >= config.pyramid_max_adds:
        return state, 0.0
    if price < state.entry_price:
        # 禁摊亏：浮亏永不加仓（I6）
        return state, 0.0
    if atr <= 0.0:
        return state, 0.0
    threshold = state.last_add_price + config.pyramid_step_atr * atr
    if price < threshold:
        return state, 0.0
    increment = float(config.pyramid_decay) ** state.add_count
    return (
        SizingState(
            entry_price=state.entry_price, last_add_price=price, add_count=state.add_count + 1
        ),
        increment,
    )


def holding_age(
    entry_date: pd.Timestamp, current_date: pd.Timestamp, trade_dates: pd.DatetimeIndex
) -> int:
    """持仓龄（bar 数）：建仓日记 1，按交易日计数。"""
    entry = pd.Timestamp(entry_date)
    current = pd.Timestamp(current_date)
    if current < entry:
        raise ValueError(f"current_date ({current}) 早于 entry_date ({entry})")
    if not isinstance(trade_dates, pd.DatetimeIndex):
        trade_dates = pd.DatetimeIndex(trade_dates)
    bars = int(((trade_dates > entry) & (trade_dates <= current)).sum())
    return bars + 1
