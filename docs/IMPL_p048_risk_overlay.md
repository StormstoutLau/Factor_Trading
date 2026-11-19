# IMPL P-048 风险 overlay（Step 5 实施文档）

> **批次**: P-048 · **Step 5 实施规格**
> **上游**: [DESIGN_p048_risk_overlay.md](DESIGN_p048_risk_overlay.md)（含 Step 4 复审 7/7 修正吸收）+ [RESEARCH_p048_risk_overlay.md](RESEARCH_p048_risk_overlay.md)
> **代码基线**: HEAD `73f9807`；`906 passed` / golden 18 / mypy 110 files / black `146·215`
> **作者**: DeepSeek-V4.1-Flash
> **性质**: 实施指南——精确到函数签名、代码骨架、行号锚点与验收命令；**不含**已完成代码（代码在 Step 5 执行时落盘）

---

## 1. 实施总览

### 1.1 任务与依赖

| 任务 | 内容 | 依赖 | 预估规模 |
|---|---|---|---|
| **T1** | `core/risk_overlay.py` 类型契约（Config / Context / Plan / Protocol / Error / Result） | — | ~90 行 |
| **T2** | 4 实现 + 2 预留 + 注册表 + `resolve_policy` | T1 | ~80 行 |
| **T3** | `compute_drawdown` + `apply_overlay` | T1/T2 | ~60 行 |
| **T4** | `set_signal` 可选 `external_max_weight` | — | +8 行 |
| **T5** | `core/config.py` 字段 + `engine_v2` 接线 + `_nav_history` | T3 | +20 行 |
| **T6** | 2 个测试模块 + S15 双阶段场景 + builder 转换 | T1-T5 | ~260 行 |

**依赖序**：T1 → T2 → T3 →（T4 ∥ T5）→ T6

### 1.2 文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `core/risk_overlay.py` | **新建** | 唯一新源（mypy 110→111） |
| `core/config.py` | 改 | `BacktestConfig` +1 字段（**L402 后、`validate()` 前**） |
| `core/engine_v2.py` | 改 | 3 处：weights 分支补 `returns_data=None`、overlay 调用、`_nav_history` append（L512 后） |
| `tests/_scenarios_cases.py` | 改 | +S15；L652 `17` → `18` |
| `tests/_scenarios_builder.py` | 改 | `risk_overlay` dict → `RiskOverlayConfig`（+2 行） |
| `tests/test_p048_risk_overlay.py` | **新建** | 策略/不变式/能力表 |
| `tests/test_p048_overlay_engine.py` | **新建** | 接线/golden/I4 |

---

## 2. T1：类型契约

### 2.1 模块头

```python
"""P-048 风险 overlay：组合级权重缩放（vol target × DD 闸门）。

设计见 ``docs/DESIGN_p048_risk_overlay.md``。本模块为**纯函数**：
输入权重与 NAV 历史，输出缩放后权重，不触单、不做 I/O。

口径（D5）：``scale_total = max(scale_floor, scale_vol × scale_dd)``，
缩放后**不重新归一化**，残差留现金。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, runtime_checkable

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
```

### 2.2 错误与配置

```python
class CapabilityError(RuntimeError):
    """能力边界外的功能被调用（预留策略 / 滞回）时抛出。"""


@dataclass(frozen=True)
class RiskOverlayConfig:
    """overlay 配置。``enabled`` 是唯一门控；``defensive_policy`` 是策略层语义。"""

    enabled: bool = False
    target_vol: Optional[float] = None          # None = 不做 vol 缩放
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
            raise ValueError(
                f"须满足 0 ≤ dd_soft < dd_hard ≤ 1: {self.dd_soft} / {self.dd_hard}"
            )
        if self.target_vol is not None and self.target_vol <= 0.0:
            raise ValueError(f"target_vol 必须 > 0: {self.target_vol}")
```

### 2.3 上下文 / 决策 / 协议 / 结果

```python
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
```

---

## 3. T2：策略实现

### 3.1 统一构造签名

**所有策略 `__init__(self, config: RiskOverlayConfig)`**——ramp / floor / ladder 都需要阈值参数，统一签名避免 `resolve_policy` 分支。

```python
class NoDeRiskPolicy:
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
    name = "fixed_floor"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        cfg = self._config
        if ctx.drawdown >= cfg.dd_hard:
            return DeRiskPlan(scale=cfg.b_min, action="fixed_floor", reason="drawdown_hard")
        return DeRiskPlan(scale=1.0, action="none")


class TieredLadderPolicy:
    """多档阶梯：取最深命中档。**本批档位为类常量，不可配置**（F-S6-P048-3）。"""

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
```

### 3.2 预留策略（fail-loud）

```python
class SectorRotationPolicy:
    name = "sector_rotation"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        raise CapabilityError(
            "sector_rotation 未实现：需行业映射与防御资产池，本仓为 long-only 股票池"
        )


class HedgeOverlayPolicy:
    name = "hedge_overlay"

    def __init__(self, config: RiskOverlayConfig) -> None:
        self._config = config

    def plan(self, ctx: DeRiskContext) -> DeRiskPlan:
        raise CapabilityError("hedge_overlay 未实现：本仓无股指期货/期权通道")
```

### 3.3 注册表与解析

```python
DEFENSIVE_POLICIES: Dict[str, type] = {
    "none": NoDeRiskPolicy,
    "cash_scaling": CashScalingPolicy,
    "fixed_floor": FixedFloorPolicy,
    "ladder": TieredLadderPolicy,
    "sector_rotation": SectorRotationPolicy,   # 预留
    "hedge_overlay": HedgeOverlayPolicy,       # 预留
}


def resolve_policy(name: str, config: RiskOverlayConfig) -> IDefensivePolicy:
    """按键实例化策略；未知键 fail-loud。"""
    try:
        cls = DEFENSIVE_POLICIES[name]
    except KeyError:
        raise ValueError(
            f"未知 defensive_policy: {name!r}；可选: {sorted(DEFENSIVE_POLICIES)}"
        ) from None
    return cls(config)


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
```

---

## 4. T3：组合编排

### 4.1 DD 计算

```python
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
```

### 4.2 主入口

```python
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
    resolved = policy if policy is not None else resolve_policy(
        config.defensive_policy, config
    )
    plan = resolved.plan(
        DeRiskContext(drawdown=drawdown, peak_nav=peak, current_nav=nav, weights=current)
    )
    scale_dd = float(plan.scale)

    # ③ 组合（不重新归一化，D5 / I2）
    scale_total = max(float(config.scale_floor), scale_vol * scale_dd)

    if plan.weights is not None:                       # 预留通道：完整权重覆盖
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
```

> **`plan.weights` 通道的 I2 例外**：此时 `Σ w_out` 由策略负责，不再满足 `≤ Σ w_in`（§12 I2 已声明）。

---

## 5. T4：`set_signal` 可选校验

**位置**：[engine_v2.py L362-364](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L362-L364) 签名；校验插入 L386 之后（`aligned = values` 之后）。

```python
    def set_signal(
        self,
        signal: pd.DataFrame,
        *,
        mode: Literal["scores", "weights"] = "scores",
        external_max_weight: Optional[float] = None,
    ) -> None:
```

校验片段：

```python
            if external_max_weight is not None:
                row_max = values.max(axis=1)
                breach = row_max[row_max > external_max_weight + 1e-12]
                if not breach.empty:
                    worst_date = breach.idxmax()
                    worst_code = values.loc[worst_date].idxmax()
                    raise ValueError(
                        f"weights 模式单票超限: {worst_code} @ {worst_date} = "
                        f"{float(row_max.max()):.6f} > {external_max_weight}"
                    )
```

**必须放在 `if mode == "weights":` 块内**。默认 `None` → 既有 4 个非法用例与全部合法用例行为逐字不变。

---

## 6. T5：引擎接线

### 6.1 `core/config.py` 字段

**位置**：L402（`debug_mode`）之后、`def validate()`（L404）之前。

```python
    # 风险 overlay（P-048）；None = 未启用（零行为变更）
    risk_overlay: "RiskOverlayConfig | None" = None
```

**导入**（文件顶部，TYPE_CHECKING 避免运行期循环）：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.risk_overlay import RiskOverlayConfig
```

> **禁止加到 config_v2.py**：engine L21 与 builder L23 均从 `core.config` 导入（F-S4-P048-1）。

### 6.2 `engine_v2` 三处改动

**(a) weights 分支补 `returns_data`**（L1041-1042）：

```python
        if self._signal_mode == "weights":
            target_weights = daily_signal.clip(lower=0.0)
            returns_data = None                      # 新增：统一定义（overlay 需要）
```

**(b) overlay 调用**——放在 `try/except` 之后、`build_target_positions` 之前（**L1094 之前**）：

```python
        # 风险 overlay（P-048，opt-in；D1 三层架构的 post-optimizer 层）
        overlay_cfg = self.cfg.risk_overlay
        if overlay_cfg is not None and overlay_cfg.enabled:
            if returns_data is not None and len(returns_data) >= 2:
                # np.atleast_2d：单标的时 np.cov 返回 0-d 标量，需升维成 (1,1) 才过 _check_cov
                cov = np.atleast_2d(np.cov(returns_data.to_numpy().T))
                cov_codes = [str(code) for code in returns_data.columns]
            else:
                cov, cov_codes = None, []
            overlay_result = apply_overlay(
                {str(code): float(weight) for code, weight in target_weights.items()},
                nav_history=self._nav_history,
                cov=cov,
                codes=cov_codes,
                config=overlay_cfg,
            )
            target_weights = pd.Series(overlay_result.weights).reindex(
                target_weights.index
            ).fillna(0.0)
```

> **三个致命陷阱（实施必读）**：
> 1. **`codes` 必须与 `cov` 的列序一致**，即 `returns_data.columns`（= `dm.stock_codes`），**不能**用 `target_weights.index`（后者是 tradable 子集，维度不匹配会在 `_check_cov` 抛错）。
> 2. **单标的必须 `np.atleast_2d`**：`np.cov` 对 1 维输入返回 0-d 标量，`_check_cov` 期望 `(n,n)` 二维数组。
> 3. **`cov_lookback` 默认 60**（L1045）：数据不足 60 日时 `returns_data is None` → vol 腿降级为 `scale_vol=1.0`。S15 必须调小该值（见 §7.3）。

**(c) `_nav_history` 初始化与 append**：

`__init__` 内（与其他状态并列）：

```python
        self._nav_history: list[float] = []
```

日循环 **L512** 之后（`tracker.update_market_values(...)` 后、`self._emit(DAY_END)` 前）：

```python
        overlay_cfg = self.cfg.risk_overlay
        if overlay_cfg is not None and overlay_cfg.enabled:
            self._nav_history.append(float(tracker.get_total_value()))
```

> **只此一处 append**（F-S4-P048-6）。L665-666 属结算路径（L725 `update_market_values=False` 的 F-I9 语义），若重复 append 会使 NAV 双计、DD 系统性低估。

---

## 7. T6：测试与场景

### 7.1 `test_p048_risk_overlay.py`（纯函数）

| 测试 | 断言 |
|---|---|
| `test_ramp_three_points` | §6.2 三点：dd=0.05→1.0 / 0.10→0.5 / 0.15→0.0（`b_min=0`） |
| `test_ramp_with_b_min` | `b_min=0.2`：dd=0.10 → `1−0.5×0.8=0.6`；dd=0.15 → 0.2 |
| `test_fixed_floor` | dd=0.11 → 1.0；dd=0.13 → `b_min` |
| `test_ladder_deepest_hit` | dd=0.13 → 0.25；dd=0.21 → 0.0 |
| `test_reserved_policies_raise` | 2 个预留均抛 `CapabilityError` |
| `test_unknown_policy_raises` | `resolve_policy("nope", cfg)` → `ValueError` |
| `test_registry_has_six_keys` | `set(DEFENSIVE_POLICIES) == {6 键}` |
| `test_overlay_capabilities_exact` | `set(OVERLAY_CAPABILITIES) == {"defensive_asset_rotation","hedge_overlay"}` |
| `test_i1_scale_bounds` | 网格扫描 `0 ≤ scale_total ≤ 1` |
| `test_i2_no_renormalize` | `Σ w_out ≤ Σ w_in` |
| `test_i3_cash_residual` | `cash_residual ≥ 0` 且 `Σw + cash == 1` |
| `test_i5_monotone` | σ 越大 `scale_vol` 越小 |
| `test_i4_identity` | `policy="none"` **且** `target_vol=None` → 逐值相等 |
| `test_hysteresis_raises` | `dd_hysteresis=True` → `CapabilityError` |
| `test_config_validation` | `dd_soft >= dd_hard` / `b_min>1` 等抛 `ValueError` |

### 7.2 `test_p048_overlay_engine.py`（接线）

| 测试 | 断言 |
|---|---|
| `test_default_none_keeps_golden` | `risk_overlay=None` 跑一遍，与基线 NAV 一致 |
| `test_enabled_false_equals_none` | `enabled=False` 与 `None` 输出逐值相等 |
| `test_enabled_scales_weights` | 开启后 `target_weight` 按 `scale_total` 等比缩小；**夹具必须显式设小 `cov_lookback` 并断言 `scale_vol < 1.0`**（否则 `returns_data=None` 时 scale=1 会假阳性通过，F-S6-P048-4） |
| `test_nav_history_not_accumulated_when_disabled` | `_nav_history == []` |

### 7.3 S15 场景（DD 腿端到端 + 接线）

**定位（I-P048-3）**：`target_vol=None`，只验证 **DD 腿与接线**；vol 腿归 `test_p048_risk_overlay.py` 纯函数测试。理由：vol 公式已由 P-047 golden 锁定（`sizing.py`），场景层重复验证收益低；而 DD 触发点的时序问题正是端到端才能暴露的。

**三项时序口径（F-S6-P048-1 修正，必须遵守）**：

| # | 口径 | 依据 |
|---|---|---|
| ① | 整手数量按**订单创建日收盘价**计算 | P-059 S05 已锁（4900 股按 d0 价创建、d2 @10.5 成交） |
| ② | 成交价 = **次日 open** | `_execute_next_day_orders` |
| ③ | **`rebalance(d)` 只能看到 `nav(0..d-1)`** | rebalance 在 L508，nav append 在 L512（收盘后） |

**配置**：`cost=NO_COST`、**`rebalance={"frequency": "daily"}`（必须显式；builder 默认 `N_days=len(dates)=5`，否则全场景只再平衡一次）**、`target_vol=None`、`defensive_policy="cash_scaling"`、`dd_soft=0.02`、`dd_hard=0.08`、`b_min=0.0`、单标的、`optimizer={"cov_lookback": 2}`。

**价格路径（6 个交易日；显式给 open 与 close；high/low 取 max/min）**：

| 日期 | open | close | 事件 |
|---|---|---|---|
| d0 | 10.00 | 10.00 | signal=1.0 → 创建订单 **9800 股**（按 d0 close） |
| d1 | 10.00 | 10.50 | 开盘成交 9800 @10.00；收盘 NAV = **104,900**（running peak） |
| d2 | 10.50 | 10.00 | rebalance 见 nav=[100000, 104900] → DD=0；收盘 NAV = **100,000** |
| d3 | 10.00 | 9.20 | rebalance 见 nav=[100000, 104900, 100000] → DD=**4.67%** → `scale=0.5548` → 订单 **5400 股（卖 4400）** |
| d4 | 9.20 | 9.20 | 开盘卖 4400 @9.20；rebalance 见 DD=**12.14%** → 清仓 **5400 股**（d5 执行） |
| d5 | 9.20 | 9.20 | 开盘卖 5400 @9.20；持仓归零 → rebalance 无新单、末日无仓可强平 |

**手算（逐步，须写入场景注释；A5 禁录制）**：

1. **d0 下单**：`floor(1.0 × 100000 × 0.985 / 10.00 / 100) × 100 = 9800` 股
2. **d1 成交**：9800 × 10.00 = 98,000；现金 **2,000**；收盘 NAV = `2000 + 9800 × 10.50 = 104,900`
3. **d2 收盘**：NAV = `2000 + 9800 × 10.00 = 100,000`
4. **d3 rebalance**：nav=[100000, 104900, 100000]；DD = `4900/104900 = 0.046711`；`t = (0.046711−0.02)/(0.08−0.02) = 0.445186`；`scale_dd = 0.554814`
5. **d3 下单**（**必须含 `value_buffer=0.985`**，F-S5-P048-1）：目标 = `floor(0.554814 × 92160 × 0.985 / 9.20 / 100) × 100 = floor(54.744) × 100 = 5400` 股（当前 9800 → **卖 4400**）
6. **d3 收盘**：NAV = `2000 + 9800 × 9.20 = 92,160`
7. **d4 rebalance**：nav=[100000, 104900, 100000, 92160]；DD = `1 − 92160/104900 = 0.121449 ≥ 0.08` → `scale_dd = 0` → 清仓 5400（d5 开盘执行）
8. **d5**：开盘卖 5400 @9.20 → 现金 `42,480 + 49,680 = 92,160`；持仓 0 + 目标 0 → **无新订单**（避免末日清仓单与强平双写，F-S5-P048-2）；末日无仓可强平

> **F-S5-P048-1（P2，实施期实证订正）**：初稿第 5 步漏乘 `value_buffer=0.985`，算出 5500 股（卖 4300）。含缓冲后 `54.744 → 54 手 = 5400 股（卖 4400）`——**跨越整手边界**，按初稿写断言必红。已按上式订正，并以实跑验证（S15 PASS）。
> **F-S5-P048-2（P3，实施期结构订正）**：初稿 5 日路径在最后一日同时产生「清仓挂单」与「末日强平」，触发 `assert_order_states_closed` 的「同一订单既 filled 又 dropped」断言（F-S6-P059-6 末日幂等缺陷）。改为 **6 日**：清仓提前一日建单，末日持仓已归零 → 无新单、无强平。

**期望断言**：

| 项 | 值 |
|---|---|
| fills（**全集，`_match_fills` 为双向精确匹配**） | `(d1, BUY, 9800, 10.00)`；`(d4, SELL, 4400, 9.20)`；`(d5, SELL, 5400, 9.20)` |
| nav_days | d1 = 104,900；d2 = 100,000；d3 = 92,160；d4 = 92,160 |
| final_cash / final_nav | **92,160** |
| final_positions | `{}`（空仓） |

> **注意**：d3 的 `dd` 用 **NAV**（含 2,000 现金缓冲）而非价格回撤率；`_match_fills` 为**双向精确匹配**（有未声明成交即红），故 fills 必须列全集（含 d5 的 5400 清仓成交）。

### 7.4 builder 转换（+2 行）

```python
    overrides = {k: v for k, v in spec.config.items() if k not in RESERVED_KEYS}
    if isinstance(overrides.get("risk_overlay"), dict):
        from core.risk_overlay import RiskOverlayConfig

        overrides["risk_overlay"] = RiskOverlayConfig(**overrides["risk_overlay"])
    _apply_overrides(cfg, overrides)
```

### 7.5 计数自检

`_scenarios_cases.py` L652：

```python
assert len(SCENARIOS) == 18, f"场景数应为 18，实际 {len(SCENARIOS)}"
```

层覆盖断言（L653-660）无需改动——S15 归入已有层（L2）。

---

## 8. 实施锚点总表

| # | 文件 | 锚点 | 改法 |
|---|---|---|---|
| 1 | `core/risk_overlay.py` | 新建 | §2-§4 全部骨架 |
| 2 | `core/config.py` | L402 后 | +`risk_overlay` 字段；顶部 TYPE_CHECKING 导入 |
| 3 | `core/engine_v2.py` | L362-364 | `set_signal` 签名 +`external_max_weight` |
| 4 | `core/engine_v2.py` | L386 后 | 单票超限校验 |
| 5 | `core/engine_v2.py` | L1041-1042 | weights 分支补 `returns_data = None` |
| 6 | `core/engine_v2.py` | L1094 前 | overlay 调用（含 cov/codes 对齐） |
| 7 | `core/engine_v2.py` | `__init__` | `self._nav_history: list[float] = []` |
| 8 | `core/engine_v2.py` | L512 后 | 条件 append |
| 9 | `tests/_scenarios_builder.py` | L125-126 | dict→Config 转换 2 行 |
| 10 | `tests/_scenarios_cases.py` | 尾部 | +S15；L652 17→18 |
| 11-12 | `tests/test_p048_*.py` | 新建 | 见 §7.1/§7.2 |

---

## 9. 门禁与目标读数

```powershell
$env:MPLBACKEND = "Agg"
python -m pytest -q                              # 906 → 906 + 新增
python -m pytest -q -k golden                    # 18 passed（零重录）
python -m pytest -q -k p059                      # 39 → 40
python -m pytest --collect-only -q               # 60 → 61
python -m black --check --line-length 100 core tests
python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples  # 110 → 111（逐字对齐 CI，F-S6-P048-2）
uv lock --check                                  # exit 0
```

**AST 不变量**：`except Exception`（core 外生产面）保持 **22**（本批不新增裸捕获）。

---

## 10. 风险与回退

| 风险 | 症状 | 处置 |
|---|---|---|
| 字段加错模块 | overlay 永不生效且测试全绿 | §6.1 钉死 `core/config.py`；直接属性访问（无 `getattr`） |
| cov/codes 维度不匹配 | `_check_cov` 抛 ValueError | §6.2 陷阱 1：用 `returns_data.columns` |
| vol 腿被 `cov_lookback` 降级 | `scale_vol` 恒为 1.0 | §7.3：S15 设 `cov_lookback=2` |
| NAV 双计 | DD 偏小、防守不触发 | §6.2 陷阱 3：仅 L512 append |
| golden 漂移 | A3 红 | `risk_overlay=None` 默认 + 全部分支前置判空 |

**回退**：删除 `core/risk_overlay.py` + 撤销 engine/config 三处改动 + S15；T4 独立可单独回退。

---

## 11. 实施级微调登记（对 DESIGN 的偏离）

| ID | DESIGN 原文 | 实施调整 | 理由 |
|---|---|---|---|
| I-P048-1 | §7.3「未启用时不创建 `_nav_history`」 | **总是**初始化为空 list，append 条件由 `enabled` 控制 | 空 list 成本可忽略；避免 `None` 分支与 `hasattr` 判断，降低出错面 |
| I-P048-2 | §4.1「策略键校验在 `resolve_policy`」 | 保持；所有策略统一 `__init__(config)` | 统一签名使 `resolve_policy` 无分支 |
| I-P048-3 | §8.2「S15 双阶段覆盖 vol + DD 两腿」 | S15 改为 **DD 腿 + 接线**（`target_vol=None`）；vol 腿归纯函数测试 | vol 公式已由 P-047 golden 锁定；DD 触发时序（见 I-P048-5）才是端到端独有风险 |
| I-P048-4 | §8.2「S15 单标的 + `np.cov(...)`」 | 必须 `np.atleast_2d` 升维 | 单标的时 `np.cov` 返回 0-d 标量，`_check_cov` 期望 `(n,n)` |
| I-P048-5 | §8.2「S15 手算要求」 | 新增**三项时序口径**：创建日价定数量 / 次日 open 成交 / `rebalance(d)` 只见 `nav(0..d-1)` | F-S6-P048-1：初稿四维度全失真，必红 |

> **五项微调**须在 Step 6 IMPL 复审后续轮确认，并在 DESIGN §18.2 回写。

---

## 12. Step 5 执行记录

| 项 | 状态 |
|---|---|
| T1-T6 落码 | ✅ 完成（`core/risk_overlay.py` 254 行；engine 6 锚点；config +1 字段；S15；2 测试模块） |
| 门禁七条 | ✅ pytest **932** / golden **18** / `-k p059` **63** / mypy **111 files 0** / black **149·218** / AST **22** / `uv lock --check` exit **0**；`tests/*.py` **106** |
| DESIGN §16.1 回写 | ✅ |
| PROGRESS 登记 | ✅ |
| Step 9 验收回填（GLM-5.3-Flash） | ✅ 40 项中 39 项回填 `✅ + 证据`（A12+B11+C7+D9），D10 留 Step 10；门禁八项全命中（pytest **932 passed, 219 warnings** / golden **18** / p059 collect **63/932** / mypy **111 files 0** / black **149·218** / AST **22**/risk_overlay Try 0 / uv exit 0 / tests **106**）；零预填机械核验通过；发现 **F-S9-P048-1**（D6 偏差，已修，见 §14） |

**实测与计划偏差（详见 §14）**：pytest 929→**932**、`-k p059` 61→**63**（S15 参与 3 处参数化）、纯函数测试 15→**16**（补 I6 专用用例）。

---

## 13. Step 6 复审发现吸收（2026-11-19）

| 发现 | 级别 | 吸收位置 | 吸收内容 | 状态 |
|---|---|---|---|---|
| **F-S6-P048-1** | **P2** | §7.3 | S15 整节重写：显式 open/close、`rebalance=daily`、三项时序口径、手算八步与期望值（final 92,160） | ✅ |
| F-S6-P048-2 | P3 | §9 | mypy 命令逐字对齐 CI（去 `tests`、补 `cli.py order_strategy web factor_library tools examples`） | ✅ |
| F-S6-P048-3 | P3 | §3.1 | `TieredLadderPolicy` docstring 声明「本批档位为类常量，不可配置」 | ✅ |
| F-S6-P048-4 | P3 | §7.2 | `test_enabled_scales_weights` 要求夹具设小 `cov_lookback` 并断言 `scale_vol < 1.0` | ✅ |
| F-S6-P048-5 | P3 | §2.3 | `IDefensivePolicy` docstring 声明「实现必须无状态」 | ✅ |

**闭环：5/5 全部吸收。**新增微调 I-P048-5（三项时序口径）已登记 §11。

---

## 14. Step 5 实施发现（F-S5-P048-1..6）+ Step 9 验收发现（F-S9-P048-1）

> 本批为「实施期实证」：全部发现均由代码落盘后的**实跑**暴露，非文档推演。P2 一项已实证订正并以 S15 PASS 复核。

| ID | 级别 | 发现 | 处置 | 状态 |
|---|---|---|---|---|
| **F-S5-P048-1** | **P2** | **S15 手算漏 `value_buffer=0.985`**：初稿第 5 步 `floor(51132/9.2/100)*100 = 5500` 未乘缓冲；含缓冲后 `floor(54.744)*100 = 5400`——恰好**跨越整手边界**，按初稿写断言必红 | §7.3 手算第 5 步与 fills 全集订正为 5400/4400 | ✅ 实跑 PASS |
| **F-S5-P048-2** | P3 | **5 日路径触发「同单既 filled 又 dropped」**：最后一日同时产生清仓挂单（dropped）与末日强平（filled），命中 `assert_order_states_closed`（F-S6-P059-6 末日幂等缺陷的连带暴露） | S15 改 **6 日**：清仓提前一日建单（d4 建、d5 成交），末日持仓归零 → 无新单、无强平 | ✅ |
| F-S5-P048-3 | P3 | **计数偏差**：`-k p059` 计划 61 实测 **63**（S15 同时进入 `test_p059_scenario` / 第二个按 ID 参数化的用例 / `test_p059_metamorphic` 三处）；总量 929→**932**；纯函数用例 15→**16**（C6 要求 `compute_drawdown` 边界专测，IMPL §7.1 原表未列） | 以实测更新 CHECKLIST 目标与 §12 记录 | ✅ |
| F-S5-P048-4 | P3 | **场景计数存在第二处硬编码**：`test_p059_scenarios.py::test_registry_contract` 断言 `len(SCENARIOS) == 17`（IMPL 仅登记 `_scenarios_cases.py` L652）；另有 3 处注释/CLI 帮助残留「17 条」 | 四处同步改 18 | ✅ |
| F-S5-P048-5 | P3 | **测试命名污染 golden 门禁**：`test_default_none_keeps_golden` 含 `golden` 关键词 → `-k golden` 读数为 19（应为 18） | 重命名 `test_default_none_keeps_baseline`，并在 docstring 声明命名约束 | ✅ 18 passed |
| F-S5-P048-6 | P3（环境） | 项目 `.venv` **无 black / mypy / pip**（`python -m black` 报 `No module named black`）；全局 Anaconda 为 black 24.10 / mypy 1.14，与 CI 钉版（black~=26.0 / mypy~=2.4.1）不一致，读数不可比 | `uv pip install --python .venv\Scripts\python.exe "black~=26.0" "mypy~=2.4.1"` → 实得 black **26.10.1** / mypy **2.4.1**；未改 `pyproject.toml` / `uv.lock` | ✅ |
| F-S9-P048-1 | P3（规格-实现偏差，Step 9 发现） | D6 要求 `risk_overlay.py` 内 `try/except 0` 且 `# type: ignore 0`；初测 `resolve_policy` 为 EAFP（`try/except KeyError` + `# type: ignore[no-any-return]`，`ast.Try`=1/ignore=1）。根因：`DEFENSIVE_POLICIES: Dict[str, type]` 值类型裸 `type` → `cls(config)` 返回 Any 触发 `no-any-return` | **LBYL 改写**（零行为变更）：值类型收紧为 `Dict[str, Callable[[RiskOverlayConfig], IDefensivePolicy]]`；`resolve_policy` 改 `.get(name)` + None 检查抛 `ValueError`（文案不变）。复测 `ast.Try`=0/ignore=0；p048 两模块 **23 passed** / mypy **111 files 0** / black **149 unchanged** | ✅ |

**Step 5 门禁实测（venv 解释器 + `MPLBACKEND=Agg`）**：

| 门禁 | 实测 |
|---|---|
| `pytest -q` | **932 passed**（906 + 26 = 16 纯函数 + 7 接线 + 3 场景族实例） |
| `pytest -q -k golden` | **18 passed / 914 deselected**（零重录） |
| `pytest --collect-only -q -k p059` | **63**（60 + 3） |
| mypy（CI 逐字命令） | **Success: no issues found in 111 source files** |
| black `core tests` / 全仓 | **149** / **218** unchanged，0 reformatted |
| AST `except Exception`（core 外） | **22**（不变） |
| `uv lock --check` | Resolved 148 packages，exit **0** |
| `tests/*.py` | **106**（104 + 2） |
