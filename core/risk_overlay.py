"""P-048 风险 overlay：组合级权重缩放（vol target × DD 闸门）。

设计见 ``docs/DESIGN_p048_risk_overlay.md``。本模块为**纯函数**：
输入权重与 NAV 历史，输出缩放后权重，不触单、不做 I/O。

口径（D5）：``scale_total = max(scale_floor, scale_vol × scale_dd)``，
缩放后**不重新归一化**，残差留现金（与 P-047 ``apply_sizing`` 同语义）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    runtime_checkable,
)

import numpy as np

from core.sizing import vol_target_scale

__all__ = [
    "CapabilityError",
    "RiskOverlayConfig",
    "DeRiskContext",
    "DeRiskPlan",
    "IDefensivePolicy",
    "OverlayResult",
    "DEFENSIVE_POLICIES",
    "OVERLAY_CAPABILITIES",
    "resolve_policy",
    "compute_drawdown",
    "apply_overlay",
]


class CapabilityError(RuntimeError):
    """能力边界外的功能被调用（预留策略 / 滞回）时抛出。"""


@dataclass(frozen=True)
class RiskOverlayConfig:
    """overlay 配置。``enabled`` 是唯一门控；``defensive_policy`` 是策略层语义。"""

    enabled: bool = False
    target_vol: Optional[float] = None  # None = 不做 vol 缩放
    defensive_policy: str = "none"
    dd_soft: float = 0.08
    dd_hard: float = 0.12
    b_min: float = 0.0
    scale_floor: float = 0.0
    dd_hysteresis: bool = False

    def __post_init__(self) -> None:
        # 只校验数值域；策略键校验留给 resolve_policy（避免与注册表循环依赖）
        if not 0.0 <= self.b_min <= 1.0:
            raise ValueError(f"b_min 必须 ∈ [0,1]: {self.b_min}")
        if not 0.0 <= self.scale_floor <= 1.0:
            raise ValueError(f"scale_floor 必须 ∈ [0,1]: {self.scale_floor}")
        if not 0.0 <= self.dd_soft < self.dd_hard <= 1.0:
            raise ValueError(f"须满足 0 ≤ dd_soft < dd_hard ≤ 1: {self.dd_soft} / {self.dd_hard}")
        if self.target_vol is not None and self.target_vol <= 0.0:
            raise ValueError(f"target_vol 必须 > 0: {self.target_vol}")


@dataclass(frozen=True)
class DeRiskContext:
    """单次决策的只读上下文。"""

    drawdown: float
    peak_nav: float
    current_nav: float
    weights: Mapping[str, float]


@dataclass(frozen=True)
class DeRiskPlan:
    """策略输出。``weights`` 为**预留通道**（切资产/对冲），None 表示走标量缩放。"""

    scale: float = 1.0
    action: str = "none"
    weights: Optional[Mapping[str, float]] = None
    reason: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class IDefensivePolicy(Protocol):
    """防守策略协议。

    **实现必须无状态**：``plan`` 为纯函数，输出只依赖 ``ctx``；
    不得持有跨 bar 记忆（滞回属 U-P048-4 预留，未实现）。
    """

    name: str

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan: ...


@dataclass(frozen=True)
class OverlayResult:
    """overlay 的完整输出，便于归因与断言。"""

    weights: Dict[str, float]
    scale_vol: float
    scale_dd: float
    scale_total: float
    cash_residual: float
    action: str = "none"
    reason: str = ""


class NoDeRiskPolicy:
    """恒等策略：不减仓。"""

    name = "none"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        return DeRiskPlan(scale=1.0, action="none")


class CashScalingPolicy:
    """默认策略：连续 ramp（无状态，满足 F1「可独立复算」）。"""

    name = "cash_scaling"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        cfg = self._config
        if ctx.drawdown <= cfg.dd_soft:
            return DeRiskPlan(scale=1.0, action="none")
        if ctx.drawdown >= cfg.dd_hard:
            return DeRiskPlan(scale=cfg.b_min, action="cash_scaling", reason="drawdown_hard")
        t = (ctx.drawdown - cfg.dd_soft) / (cfg.dd_hard - cfg.dd_soft)
        scale = 1.0 - t * (1.0 - cfg.b_min)
        return DeRiskPlan(scale=scale, action="cash_scaling", reason="drawdown_ramp")


class FixedFloorPolicy:
    """单阈值：``dd ≥ dd_hard`` → ``b_min``，否则恒等。"""

    name = "fixed_floor"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        cfg = self._config
        if ctx.drawdown >= cfg.dd_hard:
            return DeRiskPlan(scale=cfg.b_min, action="fixed_floor", reason="drawdown_hard")
        return DeRiskPlan(scale=1.0, action="none")


class TieredLadderPolicy:
    """多档阶梯：取最深命中档。**本批档位为类常量，不可配置**。"""

    name = "ladder"
    LADDER: tuple[tuple[float, float], ...] = ((0.08, 0.5), (0.12, 0.25), (0.20, 0.0))

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        scale, hit = 1.0, ""
        for threshold, value in self.LADDER:
            if ctx.drawdown >= threshold:
                scale, hit = value, f"ladder_{threshold:.2f}"
        return DeRiskPlan(scale=scale, action="ladder" if hit else "none", reason=hit)


class SectorRotationPolicy:
    """预留：切防御行业（需行业映射与防御资产池）。"""

    name = "sector_rotation"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        raise CapabilityError(
            "sector_rotation 未实现：需行业映射与防御资产池，本仓为 long-only 股票池"
        )


class HedgeOverlayPolicy:
    """预留：股指期货 / 期权对冲。"""

    name = "hedge_overlay"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        raise CapabilityError("hedge_overlay 未实现：本仓无股指期货/期权通道")


DEFENSIVE_POLICIES: Dict[str, Callable[[RiskOverlayConfig], IDefensivePolicy]] = {
    "none": NoDeRiskPolicy,
    "cash_scaling": CashScalingPolicy,
    "fixed_floor": FixedFloorPolicy,
    "ladder": TieredLadderPolicy,
    "sector_rotation": SectorRotationPolicy,  # 预留
    "hedge_overlay": HedgeOverlayPolicy,  # 预留
}

OVERLAY_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "defensive_asset_rotation": {
        "supported": False,
        "note": "long-only 股票池，无防御资产池；预留 SectorRotationPolicy",
    },
    "hedge_overlay": {
        "supported": False,
        "note": "无股指期货/期权通道；预留 HedgeOverlayPolicy",
    },
}


def resolve_policy(name: str, config: RiskOverlayConfig) -> IDefensivePolicy:
    """按键实例化策略；未知键 fail-loud。"""
    cls = DEFENSIVE_POLICIES.get(name)
    if cls is None:
        raise ValueError(f"未知 defensive_policy: {name!r}；可选: {sorted(DEFENSIVE_POLICIES)}")
    return cls(config)


def compute_drawdown(nav_history: Sequence[float]) -> tuple[float, float, float]:
    """返回 (drawdown, peak, current)；空序列 → (0.0, 0.0, 0.0)。

    口径与 ``core.guard_pipeline.DrawdownGuard`` 一致（running peak），
    但本模块不 import 该文件（避免订单级组件进入组合级路径）。
    """
    if not nav_history:
        return 0.0, 0.0, 0.0
    peak = float(max(nav_history))
    current = float(nav_history[-1])
    if peak <= 0.0:
        return 0.0, peak, current
    drawdown = (peak - current) / peak
    return max(0.0, min(1.0, drawdown)), peak, current


def apply_overlay(
    weights: Mapping[str, float],
    *,
    nav_history: Sequence[float],
    cov: Optional[np.ndarray] = None,
    codes: Sequence[str] = (),
    config: RiskOverlayConfig,
    policy: Optional[IDefensivePolicy] = None,
) -> OverlayResult:
    """三层缩放：vol × DD，取 ``scale_floor`` 下界，残差留现金。"""
    if config.dd_hysteresis:
        raise CapabilityError("dd_hysteresis 未实现（P-048 预留，见 U-P048-4）")

    current = {str(code): float(weight) for code, weight in weights.items()}

    # ① vol 腿（复用 P-047 golden 已锁公式，不内联重写 —— F-S4-P048-2）
    scale_vol, vol_reason = 1.0, ""
    if config.target_vol is not None:
        if cov is None or not codes:
            vol_reason = "zero_vol"
        else:
            _, scale_vol, vol_reason = vol_target_scale(
                current, cov, codes=codes, target_vol=config.target_vol
            )

    # ② DD 腿
    drawdown, peak, nav = compute_drawdown(nav_history)
    resolved = policy if policy is not None else resolve_policy(config.defensive_policy, config)
    plan = resolved.plan(
        DeRiskContext(drawdown=drawdown, peak_nav=peak, current_nav=nav, weights=current)
    )
    scale_dd = float(plan.scale)

    # ③ 组合（不重新归一化，D5 / I2）
    scale_total = max(float(config.scale_floor), scale_vol * scale_dd)

    if plan.weights is not None:  # 预留通道：完整权重覆盖
        out = {str(code): float(weight) for code, weight in plan.weights.items()}
    else:
        out = {code: weight * scale_total for code, weight in current.items()}

    reasons = [reason for reason in (vol_reason, plan.reason) if reason]
    return OverlayResult(
        weights=out,
        scale_vol=scale_vol,
        scale_dd=scale_dd,
        scale_total=scale_total,
        cash_residual=1.0 - float(sum(out.values())),
        action=plan.action,
        reason="+".join(reasons),
    )
