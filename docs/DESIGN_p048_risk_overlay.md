# DESIGN P-048 风险 overlay（Step 3）

> **批次**: P-048（关键路径 `059 → **048** → 050`）
> **上游**: [RESEARCH_p048_risk_overlay.md](RESEARCH_p048_risk_overlay.md)（Step 1 立项 + **Step 2 §18 复审：PASS，2 P2 + 5 P3**）
> **规范**: `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1（十步流程 / RULE-1~6 / E1-E5）
> **判档**: **T1**（新增纯函数模块 + 测试；生产面仅 opt-in 接线）
> **基线**: HEAD `73f9807`；`906 passed` / golden 18 / mypy 110 files 0 / black `146·215` / AST **22**（core 外生产面单口径，对齐 RESEARCH §16 / CHECKLIST D6；F-S8-P048-7 吸收轮更正：原「22·29」系 P-059 双口径——22=core 外 / 29=core 内，有出处非笔误）
> **作者**: DeepSeek-V4.1-Flash　**复审（Step 2/4/6/8）**: GLM-5.3-Flash ✅（RESEARCH §18 / 本文 §18.1-§18.3）
> **Step 2 修正吸收**: F-S2-P048-1..7 全部落本文（§4.5 / §7.2 / §10 / §12 / §15）
> **零预填**: §18 为 Step 4/6/8/10 预留；未填写处不得推断

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 对应 RESEARCH |
|---|------|---------------|
| O1 | 风险 overlay 作为**组合级纯函数**：输入权重 → 输出权重，不触单、不 I/O | D1 / D5 |
| O2 | 三层叠加：`scale_total = scale_vol × scale_dd`，残差留现金、**不重新归一** | D5 |
| O3 | 防守动作**插件化**：`IDefensivePolicy` + 4 实现 + 2 预留（`CapabilityError`） | D7 / D8 |
| O4 | **零默认行为变更**：`risk_overlay=None` 时 18 条 golden 零重录 | A3 |
| O5 | DD 口径与既有 `DrawdownGuard` 一致（running peak），但**动作不同**（连续缩放 vs binary 阻断） | D2 / D6 |
| O6 | 能力边界机器可读，且**不破坏** P-059 的 `CAPABILITY_BOUNDARIES` 精确键集契约 | F-S2-P048-3 |

### 1.2 非目标

| # | 不做 | 依据 |
|---|------|------|
| N1 | 不做行业中性 / 因子中性约束（属 optimizer 的 L2） | D1 |
| N2 | 不做防御资产轮动、不做衍生品对冲（预留为 `CapabilityError`） | D3 / D7 |
| N3 | 不做滞回默认开启 | U-P048-4 |
| N4 | 不改 `DrawdownGuard` 默认阈值 0.15 | U-P048-2 |
| N5 | 不改 P-059 的 `CAPABILITY_BOUNDARIES` 8 键（**场景库允许 +1**：S15，见 §8.2） | F-S2-P048-3 |

---

## 2. 继承约束（D1-D8 → 设计决策）

| RESEARCH | 内容 | 本文落地 |
|----------|------|----------|
| D1 | 三层架构：RiskModel(pre) → Optimizer(in) → **RiskOverlay(post)** | §3 / §7.1 |
| D2 | DD 口径 = running peak；默认连续 ramp；滞回可选默认关 | §5.1 / §6.2 |
| D3 | 转防御基线 = 按比例挪到现金 | §6.1 |
| D4 | weights 模式「校验可选、只校验不修改」；默认关 | §4.5 / §9.2 |
| D5 | 组合 = 串联相乘 + `scale_floor`；不重新归一 | §5.2 |
| D6 | 与 `DrawdownGuard` 阶梯并存；不改其默认值 | §9.3 |
| D7 | `IDefensivePolicy` 插件；4 实现 + 2 预留 | §6 |
| D8 | `DeRiskPlan` 同时支持 `scale` 与 `weights` | §4.2 |

**U-P048-1..6 全部继承 RESEARCH §10 结论，本文不再重议。**

---

## 3. 架构与文件布局

### 3.1 文件

```
core/
  risk_overlay.py            # 新建：Config / Context / Plan / Protocol / 4 实现 / 2 预留 / apply_overlay / OVERLAY_CAPABILITIES
  engine_v2.py               # 改：BacktestConfig 增 risk_overlay 字段；_execute_rebalance 增 1 个 opt-in 分支
  interfaces.py              # 改：可选——若 IDefensivePolicy 需集中导出（Step 4 裁量）
tests/
  test_p048_risk_overlay.py  # 新建：策略单测 + 不变式 + 能力边界
  test_p048_overlay_engine.py# 新建：接线路由 + golden 零改动 + 开启后行为
docs/
  RESEARCH_p048_risk_overlay.md / DESIGN_p048_risk_overlay.md
```

### 3.2 不新建

- 不建 `core/risk_model.py`（Σ 仍由 optimizer 内部估计）
- 不建第二套 DD 计算（复用 running peak 口径，不 import `guard_pipeline` 以避免耦合）
- **不扩展** P-059 的 `CAPABILITY_BOUNDARIES`（见 §10）

### 3.3 分层位置（数据流）

```
scores ──► optimizer.optimize ──► target_weights ──► [RiskOverlay] ──► build_target_positions ──► 下单
                                        │                  │
                                        │                  ├─ scale_vol ← target_vol / σ_p
                                        │                  └─ scale_dd  ← DefensivePolicy(drawdown)
                                        └─ 输入：{code: weight}（权重和 ≤1）
```

---

## 4. 数据契约

### 4.1 `RiskOverlayConfig`（frozen）

| 字段 | 类型 | 默认 | 语义 |
|------|------|------|------|
| `enabled` | `bool` | `False` | **唯一门控开关**（§7.2） |
| `target_vol` | `Optional[float]` | `None` | `None` = 不做 vol 缩放；非 None 时 `min(1, target/σ_p)` |
| `defensive_policy` | `str` | `"none"` | `DEFENSIVE_POLICIES` 键 |
| `dd_soft` | `float` | `0.08` | ramp 起点（≤ 此值不减仓） |
| `dd_hard` | `float` | `0.12` | ramp 终点（≥ 此值到 `b_min`） |
| `b_min` | `float` | `0.0` | 硬档保留比例 `∈ [0,1]` |
| `scale_floor` | `float` | `0.0` | 总缩放下界（防乘积过度） |
| `dd_hysteresis` | `bool` | `False` | 预留；本批不实现——置 `True` 时在 `apply_overlay` 入口抛 `CapabilityError` |

`__post_init__` 只校验数值域：`0 ≤ b_min ≤ 1`、`0 ≤ scale_floor ≤ 1`、`0 ≤ dd_soft < dd_hard ≤ 1`、`target_vol > 0`（若给值）。**策略键的校验不在 `__post_init__`**（避免与注册表形成循环依赖），改由 `resolve_policy()` 在调用期 fail-loud。

### 4.2 `DeRiskContext` / `DeRiskPlan`

```python
@dataclass(frozen=True)
class DeRiskContext:
    drawdown: float                  # ∈ [0,1]，相对 running peak
    peak_nav: float
    current_nav: float
    weights: Mapping[str, float]


@dataclass(frozen=True)
class DeRiskPlan:
    scale: float = 1.0               # ∈ [0,1]
    action: str = "none"
    weights: Optional[Mapping[str, float]] = None   # 预留：完整权重覆盖
    reason: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
```

`weights` 通道是本批**唯一预留点**（D8）：未来行业轮动 / 对冲只需填充该字段，`IDefensivePolicy` 签名不变。

### 4.3 `IDefensivePolicy`

```python
@runtime_checkable
class IDefensivePolicy(Protocol):
    name: str
    def plan(self, ctx: DeRiskContext) -> DeRiskPlan: ...
```

### 4.4 `OverlayResult`

| 字段 | 语义 |
|------|------|
| `weights` | 缩放后权重（`scale_total · w_in`，或策略 `weights` 覆盖） |
| `scale_vol` | vol 层系数（`target_vol is None` → 1.0） |
| `scale_dd` | DD 层系数（`policy="none"` → 1.0） |
| `scale_total` | `max(scale_floor, scale_vol × scale_dd)` |
| `cash_residual` | `1 − Σ weights`（≥ 0，见 I3） |
| `action` | 取自 `DeRiskPlan.action` |
| `reason` | 归因串（`""` / `vol_target` / `drawdown_ramp` / `floor`） |

### 4.5 `external_max_weight` 归属（F-S2-P048-4 修正）

**只存在于 `set_signal` 签名**，**不进入 `RiskOverlayConfig`**。理由：校验发生在 optimizer 之前的入口层，overlay 在 optimizer 之后运行，config 中的副本是死配置。

```python
def set_signal(self, frame, *, mode="scores", external_max_weight: Optional[float] = None) -> None
```

仅当 `mode="weights"` 且 `external_max_weight is not None` 时校验 `max(w) ≤ external_max_weight`，越界抛 `ValueError`（带 code / weight / limit）。默认 `None` → 既有行为逐字不变。

---

## 5. 缩放算法

### 5.1 DD 计算

```python
def compute_drawdown(nav_history: Sequence[float]) -> tuple[float, float, float]:
    """返回 (drawdown, peak, current)；空序列 → (0.0, 0.0, 0.0)。"""
```

- `peak = max(nav_history)`，`current = nav_history[-1]`
- `drawdown = (peak − current) / peak` if `peak > 0` else `0.0`
- 与 [guard_pipeline.py L174-176](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L174-L176) 同口径，但本模块**不 import** 该文件（避免把订单级组件拖入组合级路径）

### 5.2 三层组合

```
scale_vol   = 1.0 if target_vol is None else min(1.0, target_vol / sigma_p)
scale_dd    = plan.scale
scale_total = max(scale_floor, scale_vol * scale_dd)

w_out[c]    = scale_total * w_in[c]          # plan.weights 为 None 时
cash_resid  = 1.0 - sum(w_out.values())
```

- **vol 层不内联重写公式**（F-S4-P048-2）：`target_vol` 非 None 时**直接调用**
  `core.sizing.vol_target_scale(weights, cov, codes=codes, target_vol=...)`，
  取其返回的 `(scaled_weights, scale, reason)`；`target_vol is None` → 跳过该层
- `sigma_p = sqrt(wᵀΣw)`；`Σ` 由调用方传入（`cov`）；**日频无年化**（与 P-047 golden 口径一致）
- `sigma_p <= 0` 或 `cov is None` 且 `target_vol` 非 None → `scale_vol = 1.0` 并在 `reason` 记 `zero_vol`
- **不重新归一化**（D5 / I2）

### 5.3 入口

```python
def apply_overlay(
    weights: Mapping[str, float],
    *,
    nav_history: Sequence[float],
    cov: Optional[np.ndarray] = None,
    codes: Sequence[str] = (),
    config: RiskOverlayConfig,
    policy: Optional[IDefensivePolicy] = None,   # 注入点（单测用）
) -> OverlayResult:
```

`policy` 为 `None` 时由 `resolve_policy(config.defensive_policy)` 解析；未知键抛 `ValueError`（fail-loud）。

---

## 6. 防守策略（4 实现 + 2 预留）

### 6.1 实现

| 类 | 语义 | 公式 |
|---|---|---|
| `NoDeRiskPolicy` | 恒等 | `scale=1.0`, `action="none"` |
| `CashScalingPolicy` | **默认**；连续 ramp | `dd≤dd_soft→1`；`dd≥dd_hard→b_min`；中间 `1 − t·(1−b_min)`，`t=(dd−dd_soft)/(dd_hard−dd_soft)` |
| `FixedFloorPolicy` | 单阈值 | `dd≥dd_hard→b_min`，否则 1.0 |
| `TieredLadderPolicy` | 多档阶梯 | 逐档判断 `dd ≥ t_i` 取**最深命中档**；默认 `((0.08,0.5),(0.12,0.25),(0.20,0.0))` |

### 6.2 ramp 手算基准（A5）

`dd_soft=0.08 / dd_hard=0.12 / b_min=0.0`：

| DD | t | scale_dd |
|---|---|---|
| 0.05 | — | 1.00 |
| 0.08 | 0.00 | 1.00 |
| 0.10 | 0.50 | 0.50 |
| 0.12 | 1.00 | 0.00 |
| 0.15 | — | 0.00 |

### 6.3 预留（`CapabilityError`）

| 类 | 抛错文案要点 |
|---|---|
| `SectorRotationPolicy` | 需行业映射与防御资产池，本仓为 long-only 股票池 |
| `HedgeOverlayPolicy` | 需股指期货 / 期权，本仓无衍生品通道 |

两者**登记进注册表**但不参与默认路径；调用即 fail-loud，避免「静默降级为不变」。

### 6.4 注册表

```python
DEFENSIVE_POLICIES: dict[str, type[IDefensivePolicy]] = {
    "none": NoDeRiskPolicy,
    "cash_scaling": CashScalingPolicy,
    "fixed_floor": FixedFloorPolicy,
    "ladder": TieredLadderPolicy,
    "sector_rotation": SectorRotationPolicy,   # 预留
    "hedge_overlay": HedgeOverlayPolicy,       # 预留
}
```

---

## 7. 接入与门控

### 7.1 接入点（唯一）

`engine_v2._execute_rebalance` 内：

```python
target_weights = self.optimizer.optimize(...)          # 既有 L1057
# ── 新增（opt-in）──
overlay_cfg = self.cfg.risk_overlay      # 字段钉死在 core/config.py（F-S4-P048-1）
if overlay_cfg is not None and overlay_cfg.enabled:
    overlay_result = apply_overlay(
        target_weights, nav_history=self._nav_history,
        cov=..., codes=..., config=overlay_cfg,
    )
    target_weights = overlay_result.weights
# ──
target_positions = self.build_target_positions(...)    # 既有 L1094
```

> **`cov` 来源**：`np.cov(returns_data.values.T)`（与 optimizer 同源）；`returns_data is None` 且 `target_vol` 非 None → 按 §5.2 降级为 `scale_vol = 1.0` 且 `reason` 含 `zero_vol`，不抛错。
>
> **禁止 `getattr` 防御写法**（F-S4-P048-1）：`self.cfg.risk_overlay` 必须直接访问。字段若被加错模块（如误加 config_v2.py），`getattr` 会静默返回 None 使 overlay 永久关闭，而 A3 golden 对此完全不敏感；直接访问则立即 `AttributeError` fail-loud。

### 7.2 门控单一真相源（F-S2-P048-5 修正）

| 条件 | 行为 |
|---|---|
| `cfg.risk_overlay is None` | **不 attach**，`_nav_history` 不维护（零开销） |
| `cfg.risk_overlay.enabled is False` | 同上（即使非 None 也不生效） |
| `enabled is True` | attach；`defensive_policy` 决定 DD 层语义 |

**`defensive_policy="none"` 不是门控**，而是策略层恒等——此时若 `target_vol` 非 None，vol 缩放**仍生效**。这正是 F-S2-P048-2 指出的规格陷阱。

### 7.3 NAV 历史

engine 当前无 NAV 序列（仅 `tracker.get_total_value()` 即时值与 `_layer_dumper` 的可选 dump）。

**方案**：新增 `self._nav_history: list[float]`，**仅当 overlay 启用时**在每个交易日 `update_market_values` 之后 append；未启用时不创建（保持 `__init__` 零额外状态）。

> **Step 5 微调 I-P048-1 修订（F-S8-P048-9）**：实现改为**常驻空 list**（`__init__` 总是初始化），append 条件由 `enabled` 控制——空 list 成本可忽略，避免 `None` 分支与 `hasattr` 判断；见 [IMPL §11](IMPL_p048_risk_overlay.md)。

**append 位点钉死（F-S4-P048-6）**：只在 **engine L512**（主日循环）后 append。L665-666 属结算路径（L725 以 `update_market_values=False` 表达 F-I9「避免重复盯市」），若两处都 append 会造成 NAV 双计、DD 被系统性低估。

---

## 8. 测试与场景

### 8.1 测试模块

| 模块 | 覆盖 |
|---|---|
| `test_p048_risk_overlay.py` | 4 策略的闭式单测（§6.2 三点）+ 2 预留抛 `CapabilityError` + 注册表 6 键 + `OVERLAY_CAPABILITIES` 2 键 + I1-I7 属性 |
| `test_p048_overlay_engine.py` | `risk_overlay=None` 时 golden 18 零改动；`enabled=False` 与 `None` 等价；`enabled=True` + `target_vol` 时权重按 `min(1, ·)` 缩放；I4 恒等条件 |

### 8.2 复用 P-059 场景库（Step 3 追加修正）

> **修正缘由**：本稿初版曾决定「不扩展 `SCENARIOS`」，理由是 `_scenarios_cases.py` L652 的导入期自检 `len(SCENARIOS) == 17`。该理由把**扩展成本**误当**拒绝依据**——[RESEARCH_p059 §1 目标第 4 条](file:///f:/Coding/Factor_Trading_v3.0/docs/RESEARCH_p059_data_validation.md) 明确「统一验证入口：新增模块（**如 P-048 risk_overlay**）能一行命令挂载场景验证」。用户 2026-11-19 质询后订正。

**决定**：新增 **S15**（overlay 端到端）到 `SCENARIOS`，三处最小扩展：

| 文件 | 改动 | 规模 |
|---|---|---|
| `tests/_scenarios_cases.py` | +1 条 S15；L652 `len(SCENARIOS) == 17` → `18` | +1 场景、改 1 行 |
| `tests/_scenarios_builder.py` | L125 `overrides` 生成后增 2 行：`risk_overlay` 为 dict 时转 `RiskOverlayConfig` | +2 行 |
| `tests/test_p059_scenarios.py` | **零改动**（`IDS = list(SCENARIOS)` 自动拾取） | 0 |

**挂载机制（已验证，F-S4-P048-1 更正）**：`_scenarios_builder.py` L125 的 `overrides` 把 `spec.config` 中任意键交给 `_apply_overrides`。`BacktestConfig` 是 [core/config.py L333](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L333) 的 **stdlib `@dataclass`**（**不是** config_v2.py 的 Pydantic 版；engine L21 与 builder L23 均从 `core.config` 导入）。`_apply_overrides`（L86-90）对 Mapping 仅递归 `setattr`，**不会**把 dict 转成 dataclass——因此 builder 必须显式转换，否则运行期 `overlay_cfg.enabled` 抛 `AttributeError`。

**S15 设计（双阶段，覆盖两腿）**：

| 项 | 设定 |
|---|---|
| 层 / 标的 | L2，单标的 A |
| 阶段 1（d0-d2） | 单调上涨，`target_vol=0.08`，验证 **vol 腿**：`scale = min(1, 0.08/σ_A)` |
| 阶段 2（d3-d4） | 急跌触发回撤，`dd_soft=0.02 / dd_hard=0.06 / b_min=0.0`，验证 **DD 腿**与乘积（**已被 I-P048-3 收窄，参数以 [IMPL §7.3](IMPL_p048_risk_overlay.md) 为准：`dd_hard=0.08`、`target_vol=None` 只验证 DD 腿**，F-S8-P048-3） |
| σ_A 口径 | **日频、无年化**（P-047 语义锁死）；`np.cov(x, ddof=1)` |
| 手算要求 | `title`/注释给出 returns 序列、σ_A、两腿 scale 与最终 `target_weight` 的完整推导（A5 禁录制） |

**为何必须双阶段（F-S4-P048-5）**：只做阶段 1 时 `dd=0`，`CashScalingPolicy` 恒等，DD 腿实际未被端到端验证，A4 会退化为单腿覆盖。

> **Step 5 实施级微调（I-P048-3）**：S15 的 `target_vol` 设为 `None`，场景只验证 **DD 腿 + 接线**；vol 腿改由纯函数测试覆盖。理由：DD 触发减仓会改变后续 NAV，使「价格回撤率 ≠ NAV 回撤率」，场景手算需逐步迭代整手取整（脆弱易错）；vol 公式已由 P-047 golden 锁定。详见 [IMPL §7.3](IMPL_p048_risk_overlay.md)。

**连带读数变更（须在 CHECKLIST 登记；F-S8-P048-1 订正）**：
- `pytest -k p059`：**60 → 61**（基线 60 为 Step 8 实测；原记 39 系 P-059 B8 `test_p059_scenarios.py` 单模块 collect 数误升格）
- 全量 collect：906 → **906 + P-048 新增**（原「60→61」系同一误记，60/61 为 p059 关键词口径）
- 全量 `pytest`：906 → 906 + P-048 新增（计数链 **929**，见 CHECKLIST）

**双轨验证**：纯函数单测（§8.1）锁算法精度；场景 S15 锁接线与金流一致性。二者不可互相替代。

### 8.3 golden

不新增 golden 录制（**对 F1 题干「纯函数 golden」验收口径的收窄决定**，F-S8-P048-8③：ramp 期望为手算闭式、S15 为端到端手算场景，二者已构成「规格锁定 + 禁录制」的同等约束，无需 JSON golden 载体）。ramp 期望值是 §6.2 的**手算闭式**（A5），禁止跑后回填。

---

## 9. 生产改动面

### 9.1 改动清单

| 文件 | 改动 | 规模 |
|---|---|---|
| `core/risk_overlay.py` | 新建 | ~230 行 |
| `core/config.py` | **`BacktestConfig`（stdlib dataclass，L333）+1 字段**：`risk_overlay: Optional[RiskOverlayConfig] = None`（F-S4-P048-1 钉死模块） | +2 行 |
| `core/engine_v2.py` | `_execute_rebalance` +1 opt-in 分支；`_nav_history` 条件维护（**仅 L512 位点**） | ~+16 行 |
| `tests/_scenarios_cases.py` | +1 条 S15；L652 计数 17→18 | ~+30 行 |
| `tests/_scenarios_builder.py` | `risk_overlay` dict→`RiskOverlayConfig` 转换 | +2 行 |
| `core/interfaces.py` | 可选集中导出 | 0~+3 行 |

### 9.2 `set_signal` 可选校验（D4）

`external_max_weight` 默认 `None` → 既有 4 个非法用例与所有合法用例行为不变（F-S2-P048-6 补注：`test_p044` 的合法 weights 用例使用 `max_weight=1.0` 引擎，L72）。

### 9.3 与 `DrawdownGuard` 的关系（D6）

- 不修改 `guard_pipeline.py` 任何字节
- 二者同时启用时，Guard 的 0.15 会落在 ramp 的 12% 之后 → 构建期**不校验**（二者分属不同层，且 Guard 未接入主链路）；仅在设计文档声明推荐值 0.20
- 若 Step 4 认为需要校验，再增 `validate_guard_coexistence`

---

## 10. 能力边界（F-S2-P048-3 修正）

**不扩展 P-059 的 `CAPABILITY_BOUNDARIES`。** 理由：[tests/_scenarios_assert.py L155-170](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_assert.py#L155-L170) 以**精确键集相等**断言 8 键，新增键会让 P-059 测试直接红；而修改该断言等于修改已验收契约。

改为在 `core/risk_overlay.py` 定义独立表：

```python
OVERLAY_CAPABILITIES: dict[str, dict[str, Any]] = {
    "defensive_asset_rotation": {"supported": False, "note": "long-only 股票池，无防御资产池"},
    "hedge_overlay": {"supported": False, "note": "无股指期货/期权通道"},
}
```

由 `test_p048_risk_overlay.py` 断言键集**完全等于**这 2 键（同型精确相等，防止悄悄扩容）。

---

## 11. 接入规范（≤3 行）

新增一个防守策略 = `DEFENSIVE_POLICIES` 加一行 + 实现类；新增一个能力边界 = `OVERLAY_CAPABILITIES` 加一行。二者均无需改动引擎或测试主体。

---

## 12. 不变式映射（I-P048-1..7，含 Step 2 修正）

| I | 内容 | 检验 |
|---|---|---|
| **I1** | `0 ≤ scale_total ≤ 1`（不加杠杆） | 属性测试 |
| **I2** | 标量乘法不重新归一：`Σ w_out ≤ Σ w_in`；**预留 `plan.weights` 通道除外**（F-S2-P048-7） | 逐值断言 |
| **I3** | `cash_residual = 1 − Σ w_out ≥ 0` | 逐桶断言 |
| **I4** | **精确条件**（F-S2-P048-2）：`not enabled` **或**（`defensive_policy=="none"` **且** `target_vol is None`）⇒ `w_out == w_in` 且 `scale_total == 1.0` | 同构对拍 |
| **I5** | `scale_dd` 对 DD 单调不增；`scale_total = max(scale_floor, scale_vol·scale_dd)` | 网格扫描 |
| **I6** | `drawdown ∈ [0,1]`，`peak = max(nav_history)` | 边界用例 |
| **I7** | 输出权重非负、代码集合 ⊆ 输入集合（预留通道除外） | 集合断言 |

---

## 13. 门禁与 CI

沿用既有命令，**不新增 CI job**：

- `pytest -q`（`MPLBACKEND=Agg`）：基线 906 → 目标 906 + 新增
- `pytest -q -k golden`：**18 零重录**
- mypy CI 等价命令：110 → **111** files
- black：`146·215` → 增量
- `uv lock --check`：exit 0
- AST `except Exception`（core 外）：**22 不变**

---

## 14. 风险与回滚

| 风险 | 缓解 | 回滚点 |
|---|---|---|
| 接线误改默认行为 | `risk_overlay=None` 默认 + A3 golden 零重录 | 删除 `_execute_rebalance` 分支 |
| `_nav_history` 内存增长 | 仅启用时维护；长度 = 交易日数（可接受） | 同上 |
| 策略键拼写错误 | `resolve_policy` fail-loud | — |
| 与 P-059 契约冲突 | §10 独立表，零触碰 | — |
| ramp 参数误配 | `__post_init__` 校验 `dd_soft < dd_hard` | — |

---

## 15. DoD（A1-A9，含 Step 2 修正）

| A | 验收项 | 证据出口 |
|---|---|---|
| **A1** | `core/risk_overlay.py` 导出 8 符号：`RiskOverlayConfig` / `DeRiskContext` / `DeRiskPlan` / `IDefensivePolicy` / `CapabilityError` / `DEFENSIVE_POLICIES` / `apply_overlay` / `OverlayResult`（**Step 8 订正 F-S8-P048-5**：IMPL §2.1 `__all__` 实为 **11 符号**，另含 `OVERLAY_CAPABILITIES` / `resolve_policy` / `compute_drawdown`，以 IMPL 为准） | 读码 + `__all__` |
| **A2** | 注册表 **6 键**；`resolve_policy("不存在")` 抛 `ValueError` | 单测 |
| **A3** | `risk_overlay=None` 与 `enabled=False` 时 **18 条 golden 零重录**、`git status tests/golden/` 空 | `pytest -k golden` |
| **A4** | 4 策略闭式单测通过（ramp 三点 0.05/0.10/0.15）；2 预留抛 `CapabilityError`；**S15 端到端通过**，P-059 测试读数按 §8.2 更新（**-k p059 60→61**，F-S8-P048-1） | 单测 + `pytest -k p059` |
| **A5** | ramp 期望为**手算**（§6.2 表），无跑后回填 | 读码 + diff |
| **A6** | `scale_vol` / `scale_dd` 可独立单测；`target_vol=None` 时 `scale_vol==1.0` | 单测 |
| **A7** | mypy **111 files 0** / black 无 reformat / `uv lock --check` exit 0 / AST **22 不变** | 命令读数 |
| **A8** | `OVERLAY_CAPABILITIES` 键集**完全等于** `{defensive_asset_rotation, hedge_overlay}`；**未修改** P-059 `CAPABILITY_BOUNDARIES` | 单测 + `git diff` |
| **A9** | 文档回写：PROGRESS 登记；RESEARCH A4 收窄注记（§8.2） | diff |

---

## 16. IMPL 任务映射（B1-B5 → T1-T6）

> **实施文档**：[IMPL_p048_risk_overlay.md](IMPL_p048_risk_overlay.md)（精确到函数签名 / 行号锚点 / 代码骨架 / 门禁命令 / 5 项实施级微调，F-S8-P048-6）

| B | T | 内容 |
|---|---|---|
| B1 | **T1** | 类型契约（Config / Context / Plan / Protocol / CapabilityError / OverlayResult） |
| B2 | **T2** | 4 实现 + 2 预留 + 注册表 + `resolve_policy` |
| B3 | **T3** | `compute_drawdown` + `apply_overlay`（三层组合） |
| B4 | **T4** | `set_signal` 可选 `external_max_weight` |
| B5 | **T5** | `BacktestConfig.risk_overlay` + `_execute_rebalance` 分支 + `_nav_history` |
| — | **T6** | **两个测试模块**（§8.1）+ **S15 场景**（原「双阶段」已被 I-P048-3 收窄为 DD 腿 + 接线，以 [IMPL §7.3](IMPL_p048_risk_overlay.md) 为准，F-S8-P048-3；`_scenarios_cases.py` 计数 17→18）+ `_scenarios_builder.py` 转换 2 行 + 文档回写 |

### 16.1 Step 5 执行回写（2026-11-19）

| 项 | 计划 | 实测 | 差异来源 |
|---|---|---|---|
| 新源 | `core/risk_overlay.py` ~230 行 | **254 行**（11 导出符号） | 注释与 docstring 落全 |
| 引擎锚点 | 6 处（T4 签名/校验 + returns_data + overlay 调用 + `_nav_history` 两处） | **6 处逐点命中**，无额外改动 | — |
| pytest | 929 | **932** | 纯函数 16（+I6 专测）、S15 场景族 3 实例（F-S5-P048-3） |
| `-k golden` | 18 零重录 | **18 passed / 914 deselected** | 测试命名避开 `golden`（F-S5-P048-5） |
| `-k p059` | 61 | **63** | S15 参与 3 处参数化（F-S5-P048-3） |
| mypy | 111 | **111 files 0 issue** | — |
| black | 149·218 | **149·218**（0 reformatted） | 钉版 black 26.10.1（F-S5-P048-6） |
| AST | 22 不变 | **22** | — |
| S15 手算 | 5500/4300 | **5400/4400 + 6 日路径** | 漏 `value_buffer=0.985`（F-S5-P048-1）+ 末日双写（F-S5-P048-2） |

> 全部 6 项实施发现见 [IMPL §14](IMPL_p048_risk_overlay.md)；其中 **F-S5-P048-1（P2）** 为手算漏乘整手缓冲导致的**跨手边界**错误，已实证订正。

### 16.2 Step 9 验收回写（2026-11-19，GLM-5.3-Flash）

- **回填结果**：CHECKLIST 40 项中 **39 项 `✅ + 证据`**（A12 + B11 + C7 + D9），D10 留 Step 10；零预填机械核验（39×`[待 Step 9]` + 1×`[待 Step 10]`）通过。
- **门禁八项全命中**：pytest **932** / golden **18** / p059 collect **63** / mypy **111 files 0** / black **149·218** / AST **22**（risk_overlay `ast.Try`=0、`type: ignore`=0）/ `uv lock --check` exit 0 / `tests/*.py` **106**。
- **发现 F-S9-P048-1（P3，已修）**：D6 的「`try/except 0` 且 `# type: ignore 0`」初测为 1/1（`resolve_policy` EAFP + 裸 `type` 值类型引发 `no-any-return`）；Step 9 内 LBYL 改写（值类型收紧为 `Callable[[RiskOverlayConfig], IDefensivePolicy]` + `.get` 判 None），零行为变更，复测全绿。详见 [IMPL §14](IMPL_p048_risk_overlay.md) / [CHECKLIST §8.2](CHECKLIST_p048_risk_overlay.md)。

---

## 17. Step 2 发现吸收对照

| 发现 | 级别 | 本文位置 | 吸收方式 |
|---|---|---|---|
| F-S2-P048-1 | P3 | §引用表（文末） | Davis & Norman 更正为 *Math. Oper. Res.* 15(4):676–713 |
| F-S2-P048-2 | **P2** | §7.2 / §12 I4 | 精确条件写入 I4，并显式标注 `policy="none"` 非门控 |
| F-S2-P048-3 | **P2** | §10 / §15 A8 | 独立 `OVERLAY_CAPABILITIES`，零触碰 P-059 8 键表 |
| F-S2-P048-4 | P3 | §4.5 | `external_max_weight` 只归 `set_signal` |
| F-S2-P048-5 | P3 | §7.2 | 单一门控 `enabled`；`None` = 未配置 |
| F-S2-P048-6 | P3 | §9.2 | 补注 `test_p044` L72 的 `max_weight=1.0` |
| F-S2-P048-7 | P3 | §12 I2 | 补注「预留 weights 通道除外」 |

---

## 18. 复审预留

| 章节 | 用途 | 状态 |
|---|---|---|
| §18.1 | Step 4 复审（GLM-5.3-Flash，DESIGN 层） | ✅ **PASS（带修正项）**：1 P2 + 5 P3，0 方向性推翻；须于 Step 5 前吸收（见下） |
| §18.2 | Step 6 复审（IMPL 层） | ✅ **PASS（带修正项）**：1 P2 + 4 P3 + 5 项正面核验；S15 手算五处结构性错误须重写（见 18.2.3） |
| §18.3 | Step 8 复审（文档一致性，GLM-5.3-Flash） | ✅ **PASS（带修正项）**：2 P2 + 7 P3 + 1 INFO；P2 = `-k p059` 基线实测 **60** 非 39（三文档同错）、CHECKLIST 计数链漏计 B9 三例；须于 Step 9 前吸收（见 18.3.2） |
| §18.4 | Step 10 终审 | ✅（Qwen3.8-Max，2026-11-19，见 §18.4） |

### 18.1 Step 4 复审（GLM-5.3-Flash，2026-11-19）

> 复审者 GLM-5.3-Flash，与作者 DeepSeek-V4.1-Flash 异构。方法：①DESIGN 关键接入断言对源码**独立复核**（engine/builder 的配置导入链、NAV 维护点、vol 缩放语义）；②与 RESEARCH 承诺（D1-D8 / B1-B5 / I1-I7 / A1-A9）逐项比对；③Step 2 发现吸收表核验；④内部自洽性审查。复审者未采信作者任何未独立验证的断言。

#### 18.1.1 关键断言独立复核

| DESIGN 断言 | 复核 | 证据 |
|---|---|---|
| §7.1 插入点 optimize→build_target_positions | ✅ | engine_v2 L1006/L1057/L1094（Step 2 E2 已核，本轮未变） |
| §7.3 「`update_market_values` 之后 append」 | ✅ 锚点存在，但**有两个调用位** → F-S4-P048-6 | engine_v2 **L512**（主日循环）与 **L665-666**（结算路径，带 `update_market_values: bool = True` 参数；L725 结算传 False 的 F-I9 语义） |
| §8.2 「`BacktestConfig` 为 Pydantic BaseModel」 | ❌ **不实** → F-S4-P048-1 | engine_v2 **L21** 与 builder **L23** 均 `from core.config import BacktestConfig`；[config.py L333-334](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L333-L334) 为 stdlib `@dataclass`；config_v2.py 的 Pydantic 版与引擎/场景构建器**均无关** |
| §8.2 挂载机制（RESERVED_KEYS 透传） | ✅ | builder L125-126 `_apply_overrides`；`RESERVED_KEYS` 无 `risk_overlay` |
| §5.2 vol 层「与 P-047 同源」 | ✅ 语义一致，但**内联重实现** → F-S4-P048-2 | [sizing.py L200-220](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L220)：`min(target/σ_p, 1.0)` + zero_vol 分支，**日频无年化**，P-047 golden 已锁 |
| §10 不触碰 P-059 8 键表 | ✅ | 独立 `OVERLAY_CAPABILITIES`；P-059 `assert_capability_declared` 未动 |

#### 18.1.2 Step 2 发现吸收核验（F-S2-P048-1..7）

| 发现 | 吸收位置 | 判定 |
|---|---|---|
| F-S2-P048-1（Davis & Norman 原刊） | 附录引用表 | ✅ |
| F-S2-P048-2（I4 精确条件） | §7.2 / §12 I4 | ✅ |
| F-S2-P048-3（P-059 契约冲突） | §10 / §15 A8 | ✅ 独立表方案成立 |
| F-S2-P048-4（参数双宿） | §4.5 | ✅ 只归 set_signal |
| F-S2-P048-5（门控三重冗余） | §7.2 单一真相源 | ✅ |
| F-S2-P048-6（E8 表述） | §9.2 | ✅ |
| F-S2-P048-7（I2 例外） | §12 I2 | ✅ |

#### 18.1.3 发现（F-S4-P048-1..6）

| ID | 级别 | 发现 | 修订要求（Step 5 前吸收） |
|---|---|---|---|
| **F-S4-P048-1** | **P2** | **配置模块归属表述错误**：§8.2 称 BacktestConfig 为「Pydantic BaseModel，dict→dataclass 需显式转换」——实际 engine/builder 用的是 [core/config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L333-L334) 的 stdlib dataclass（Pydantic 版在 config_v2.py，与二者无关）。dict 需转换的**真正原因**：`_apply_overrides` L88-90 对 Mapping 仅递归 setattr，dict 直接挂到字段上会使运行期 `overlay_cfg.enabled` 抛 AttributeError。且 §7.1 的 `getattr(self.cfg, "risk_overlay", None)` 防御式写法会把「字段加错模块」**静默降级为 overlay 关闭**（A3 golden 对此不敏感） | ①§9.1 钉死「**core/config.py 的 `BacktestConfig`（dataclass）**+1 字段」；②§8.2 理由更正为上述真实机制；③§7.1 改直接属性访问 `self.cfg.risk_overlay`（字段正确添加后恒存在；缺失即 AttributeError fail-loud） |
| F-S4-P048-2 | P3 | **vol 层内联重实现**：§5.2 重写了 P-047 golden 已锁的 `vol_target_scale`（sizing.py L200-220）公式，双实现漂移风险；其返回三元组 `(weights, scale, reason)` 与 `OverlayResult.scale_vol/reason` 一一对应 | T3 实现时**直接调用** `vol_target_scale`（`target_vol is None` → 跳过），不重写公式 |
| F-S4-P048-3 | P3 | **S15 手算规格不足**：σ_p 为**日频无年化**（P-047 语义锁死）、`np.cov` 默认 ddof=1、未固定价格路径；若 σ_A ≤ target_vol 则 scale=1 无可见缩放 | S15 的 `title`/注释给出闭式推导：固定 close 路径（建议 ±9% 日变动，合法且 buyable）、声明 returns 序列与 ddof、`target_vol` 取 0.08~0.10 保证 σ_A > target_vol |
| F-S4-P048-4 | P3 | **测试模块计数不一致**：§16 T6「三个测试模块」vs §8.1 列出 **2 个** | 改为 2 或补第三模块定义 |
| F-S4-P048-5 | P3 | **DD 腿无端到端场景**：S15 仅覆盖 vol 腿；ramp/DD 闸门只有纯函数单测 | 建议 S15 双阶段（先涨建仓 → 后跌触发 ramp）同时覆盖两腿；若不改，登记「DD 腿端到端」为后续项。Step 5 裁量，不阻塞 |
| F-S4-P048-6 | P3 | **NAV 维护点有两个**：update_market_values 调用位在 L512（主日循环）与 L665-666（结算路径） | T5 钉死 **L512** 位点 append（避开结算路径，尊重 L725 `update_market_values=False` 的 F-I9 语义），防 NAV 双计 |

另：RESEARCH §13 B3 文案 `scale_total = scale_vol × scale_dd` 未含 `scale_floor`，与 DESIGN §5.2/I5 不一致（RESEARCH I5 已是含 floor 的新版）——RESEARCH 侧随下轮文档同步补注「以 DESIGN §5.2 为准」。

#### 18.1.4 结论

- **0 方向性推翻**：三层架构、门控、S15 复用 P-059、独立能力表方向全部成立；
- **1 P2 + 5 P3**：P2 为理由链/钉死类修正（不动架构）；P3 为实现级精化；
- 判定：**PASS（带修正项）**——6 项修订须在 Step 5 实施前吸收进本文与 RESEARCH。

#### 18.1.5 修订吸收（2026-11-19，作者 DeepSeek-V4.1-Flash 执行）

| 发现 | 吸收位置 | 吸收内容 | 状态 |
|---|---|---|---|
| **F-S4-P048-1**（P2） | §5.2 / §7.1 / §8.2 / §9.1 | 配置模块钉死 `core/config.py` L333 的 stdlib dataclass；`getattr` → 直接 `self.cfg.risk_overlay` 并补 fail-loud 理由；⊥ Pydantic 表述改为 `_apply_overrides` 真实机制 | ✅ |
| F-S4-P048-2 | §5.2 | vol 层改为**直接调用** `sizing.vol_target_scale`，并标注日频无年化 | ✅ |
| F-S4-P048-3 | §8.2 | S15 补 σ_A 口径（日频 / `ddof=1`）与手算推导要求 | ✅ |
| F-S4-P048-4 | §16 T6 | 「三个测试模块」→「**两个测试模块**」 | ✅ |
| F-S4-P048-5 | §8.2 | S15 改为**双阶段**（阶段 1 vol 腿 / 阶段 2 DD 腿），并说明单腿会退化 A4 | ✅ |
| F-S4-P048-6 | §7.3 | `_nav_history` append 钉死 **L512**，说明 L665-666 结算路径会导致 NAV 双计 | ✅ |
| RESEARCH B3 附注 | RESEARCH §13 | `scale_total` 补 `max(scale_floor, ·)`，注明以 DESIGN §5.2 为准 | ✅ |

**闭环：7/7 全部吸收。Step 4 修正项清零，可进入 Step 5。**

#### 18.2 Step 6 复审——IMPL 文档（GLM-5.3-Flash，2026-11-19）

> 复审者 GLM-5.3-Flash，与作者 DeepSeek-V4.1-Flash 异构。对象：[IMPL_p048_risk_overlay.md](IMPL_p048_risk_overlay.md)（代码尚未落盘，本复审针对实施规格）。方法：①代码骨架对 `sizing.py` / `engine_v2.py` / `interfaces.py` 既有契约逐项核验；②S15 手算**独立复算**；③门禁命令对 `.github/workflows/tests.yml` 逐字比对；④实施级微调（I-P048-1..4）合理性审查。

##### 18.2.1 正面核验（5 项，全部通过）

| 断言 | 结果 | 证据 |
|---|---|---|
| `optimizer.optimize` 返回 **pd.Series**，IMPL 骨架 `pd.Series(...).reindex(target_weights.index)` 对 scores/weights 两路均成立 | ✅ | [interfaces.py L236-238](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L236-L238)、[portfolio.py L152-157](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L152-L157) |
| optimizer 异常路径 L1073 `return` → overlay 置于 try/except 之后不会有未定义变量 | ✅ | engine_v2 L1061-1073 |
| `_as_vector` 对 weights 中缺失的 code **记 0**、对 codes 之外的 code **raise** → partial weights + codes=全市场安全 | ✅ | [sizing.py L157-167](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L157-L167) |
| `_check_cov` 方阵 + 维度校验 → IMPL 陷阱 1/2（codes 列序、`np.atleast_2d`）必要性成立 | ✅ | [sizing.py L170-177](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L170-L177) |
| mypy 目标 **111** 正确：CI 命令不含 `tests` | ✅ | [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46) |

实施级微调 I-P048-1（nav_history 常驻空 list）、I-P048-4（`np.atleast_2d`）审查通过；I-P048-2 / I-P048-3 见 18.2.3 附带要求。

##### 18.2.2 发现（F-S6-P048-1..5）

| ID | 级别 | 发现 | 修订要求 |
|---|---|---|---|
| **F-S6-P048-1** | **P2** | **S15 手算五处结构性错误**（§7.3），逐条：①**缺 `rebalance: {"frequency": "daily"}`**——builder 默认 `frequency="N_days", n_days=len(spec.dates)=5`（builder L114），场景将只在 d0 再平衡，全场景死；②**数量口径错**——整手数量按**订单创建日收盘价**（P-059 已锁，S05 反例），d0 close 10.00 → **9800 股**，IMPL 用 d1 close 10.90 → 9000 股；③**执行价 = 次日 open**，IMPL 未指定 open，open=close 缺省时 d1 执行成本 9800×10.90=106,820 > 现金 100,000 → **拒单，场景崩**；④**overlay 时序 off-by-one**——rebalance 在 L508、nav append 在 L512，**rebalance(d) 只见 nav(0..d-1)**，IMPL 假设 d2 再平衡能看到 d2 的下跌；⑤**peak = running max NAV** 而非常数 100,000，持仓增值日会抬高峰值 | **S15 整节重写**：显式给 open/high/low；按「创建日价定数量、次日 open 成交、rebalance(d) 见 nav(d-1)」三口径重推手算；config 加 `rebalance: daily` |
| F-S6-P048-2 | P3 | **IMPL §9 mypy 命令与 CI 不一致**：IMPL 写了 `tests` 且漏 `cli.py order_strategy web factor_library tools examples` | 逐字对齐 CI：`python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples` |
| F-S6-P048-3 | P3 | **`TieredLadderPolicy.LADDER` 硬编码类属性**——DESIGN §6.1「默认」暗示可配置 | 本批保持硬编码可接受，但类 docstring 须声明「本批不可配置」，避免未来误改语义 |
| F-S6-P048-4 | P3 | **§7.2 `test_enabled_scales_weights` 假阳性风险**——夹具若不显式设小 `cov_lookback`，`returns_data is None` → `scale_vol=1.0`，断言「等比缩小」会在 scale=1 下**静默通过** | 测试夹具显式设 `optimizer.cov_lookback` ≤ 可用历史天数，并断言 `scale_vol < 1.0` |
| F-S6-P048-5 | P3 | **策略实例化时机**——`apply_overlay` 内 `resolve_policy` 每个 rebalance 日重新实例化策略。P-048 全部策略无状态故无碍，但 F1「可独立复算」依赖无状态前提 | `IDefensivePolicy` 协议 docstring 增补「实现必须无状态（`plan` 为纯函数）」，为 U-P048-4 未来滞回立规矩 |

##### 18.2.3 结论

- 骨架与既有函数契约（`_as_vector` / `_check_cov` / `vol_target_scale` / Series 返回类型）**全部兼容**；实施级微调 I-P048-1/-4 成立；
- **F-S6-P048-1（P2）**：S15 手算在创建日价、次日 open 执行、overlay 时序、running peak 四个维度全部失真——按现稿实施必然红，**须重写后才能进 Step 5 代码执行**；
- 其余 4 项 P3 为对齐与防呆级；
- 判定：**PASS（带修正项）**——S15 重写为 Step 5 代码执行的前置条件。

##### 18.2.4 修订吸收（2026-11-19，作者 DeepSeek-V4.1-Flash 执行）

| 发现 | 吸收位置（IMPL） | 吸收内容 | 状态 |
|---|---|---|---|
| **F-S6-P048-1**（P2） | §7.3 | S15 整节重写：显式 open/close 五列路径、`rebalance=daily`、**三项时序口径表**（创建日价 / 次日 open / rebalance(d) 见 nav(0..d-1)）、手算八步（9800 股 → NAV 104,900/100,000 → d3 DD 4.6711% → scale 0.55482 → 5500 股 → d4 DD 12.145% → 清仓）、期望 `final_nav=92,160` | ✅ |
| F-S6-P048-2 | §9 | mypy 命令逐字对齐 [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46) | ✅ |
| F-S6-P048-3 | §3.1 | `TieredLadderPolicy` docstring 声明本批不可配置 | ✅ |
| F-S6-P048-4 | §7.2 | `test_enabled_scales_weights` 要求设小 `cov_lookback` 并断言 `scale_vol < 1.0` | ✅ |
| F-S6-P048-5 | §2.3 | `IDefensivePolicy` docstring 声明实现必须无状态 | ✅ |
| 新增微调 | §11 | I-P048-5：三项时序口径纳入实施级微调登记（共 5 项） | ✅ |

**闭环：5/5 全部吸收。S15 手算已按真实时序重推，Step 6 修正项清零，可进入 Step 5 代码落盘。**

### 18.3 Step 8 复审——四文档一致性（GLM-5.3-Flash，2026-11-19）

> 复审者 GLM-5.3-Flash，与作者 DeepSeek-V4.1-Flash 异构（RULE-5）。对象：RESEARCH / DESIGN / IMPL / CHECKLIST 四文档交叉一致性 + 基线锚点实证。方法：①计数链机械复算（RULE-2）；②零预填扫描；③ID 命名空间核查；④行号锚点与门禁命令对源码 / CI 逐字比对；⑤基线读数独立复跑（git / pytest --collect-only / AST 扫描）。复审者未采信作者任何未独立验证的读数。

#### 18.3.1 正面核验（9 项，全部通过）

| # | 断言 | 结果 | 证据 |
|---|---|---|---|
| 1 | CHECKLIST 40 项机械计数（A12+B11+C7+D10）；实测列 39×`[待 Step 9]` + 1×`[待 Step 10]`，零 ✅ 预填 | ✅ | 逐表行数 |
| 2 | HEAD `73f9807` = P-059 关闭回填提交；工作树仅 4 个 P-048 未跟踪文档，无格式化副作用 | ✅ | git log / status（本轮） |
| 3 | AST `except Exception`（core 外生产面）= **22** | ✅ | 独立 AST 扫描（本轮；agents / filter / scripts / batch_backtest / strategy_evaluation / order_strategy / web / factor_library / cli.py） |
| 4 | mypy 门禁命令三处逐字一致 | ✅ | CHECKLIST D4 = IMPL §9 = [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46) |
| 5 | S15 手算八步独立复算逐位一致（9800 → 104,900 → 100,000 → DD 4.6711% → scale 0.55482 → 5500 → DD 12.145% → 92,160） | ✅ | IMPL §7.3 逐步重算 |
| 6 | RESEARCH §15 A4 收窄注记已在位（Step 3 追加修正），DESIGN A9 该子项已满足 | ✅ | RESEARCH §15 A4 |
| 7 | RESEARCH §13 B3 已含 `max(scale_floor, ·)`（Step 4 回写闭环） | ✅ | RESEARCH §13 B3 |
| 8 | 全量 collect 基线 = **906**（非 60） | ✅ | `pytest --collect-only -q -k p059` → "**60/906** tests collected"（本轮） |
| 9 | P-059 三模块（scenarios / metamorphic / g4_cash_parity）collect 合计 = **60**（P-059 B8 口径 39/16/5 吻合） | ✅ | 三模块 collect 命令（本轮） |

#### 18.3.2 发现（F-S8-P048-1..10）

| ID | 级别 | 发现 | 修订要求（Step 9 前吸收） |
|---|---|---|---|
| **F-S8-P048-1** | **P2** | **`-k p059` 基线读数错误：实测 60，三文档均记 39**。RESEARCH §15 A4 / DESIGN §8.2 + §15 A4 / CHECKLIST 头部 + D3 均写「-k p059 39→40」；实测 `pytest --collect-only -q -k p059` = **60/906 collected**（本机 venv，2026-11-19）。39 的真实出处 = P-059 CHECKLIST B8 中 `test_p059_scenarios.py` **单模块** collect 数（39/16/5=60），立项时被误升格为关键词读数；「全量 collect 60→61」为同一误记（全量 collect 实为 906，见正面核验 8） | 三处统一改为「**-k p059 60→61**」；删除「全量 collect」措辞或改为「p059 关键词 collect」；CHECKLIST D3 门禁目标 40 → **61** |
| **F-S8-P048-2** | **P2** | **CHECKLIST 计数链漏计 F-S7-P048-1 补登的 3 例**：§5「20 = 15+4+1」/ D1「926 = 906+20」/ 交接 1 均未计入 B9 的 3 个 `test_external_max_weight_*` | 计数链改 **+23 = 929**（15+4+3+1；预留策略若参数化 2 实例 → 930）；§5 / RULE-2 / D1 / 交接 1 四处同步；RESEARCH §16「预计 +12~18」为 Step 1 估计值，声明以 CHECKLIST 929 为准 |
| F-S8-P048-3 | P3 | DESIGN §8.2 阶段 2 参数残留 `dd_hard=0.06`（IMPL §7.3 = **0.08**）；§16 T6「S15 场景（**双阶段**）」残留——I-P048-3 注记只挂在 §8.2 末尾且未覆盖这两处旧表述 | §8.2 阶段 2 行与 §16 T6 各补「（已被 I-P048-3 收窄，以 IMPL §7.3 为准）」注记 |
| F-S8-P048-4 | P3 | IMPL §7.3 d2 行「rebalance 见 nav=[100000]」应为 **nav=[100000, 104900]**（d1 收盘已 append；同表 d3 行三元素列表自证）；DD=0 结论不受影响 | 订正该单元格 |
| F-S8-P048-5 | P3 | 导出符号漂移：RESEARCH §15 A1 与 DESIGN §15 A1 均为「8 符号」，IMPL §2.1 `__all__` 实为 **11**（+`OVERLAY_CAPABILITIES` / `resolve_policy` / `compute_drawdown`）；CHECKLIST 无 `__all__` 验收项 | DESIGN §15 A1 注记「以 IMPL §2.1 `__all__` 11 符号为准」；CHECKLIST A 组补 `__all__` 读码证据出口 |
| F-S8-P048-6 | P3 | 「4 项实施级微调」未同步：RESEARCH §12 Step 5 行、DESIGN §16 头注均为 4，IMPL §11 实为 **5**（I-P048-5 于 Step 6 新增） | 两处改 5 |
| F-S8-P048-7 | P3 | DESIGN 头部「AST **22·29**」的 29 无出处（RESEARCH §16 / CHECKLIST / 本轮实测均为 22）；且头部「Step 4 复审: GLM-5.3-Flash（**待**）」状态过期（§18.1 已闭环）。**复审更正（2026-11-19 吸收轮）**：29 实有出处——系 P-059 双口径（core 外 22 / **core 内 29**，见 P-059 CHECKLIST §9/§10、PROGRESS L2582）；本发现降级为「口径未注明、与单口径文档表面不一致」，头部订正理由相应改为口径统一而非纠错 | 头部订正为「AST 22」并注明双口径含义；「（待）」删去 |
| F-S8-P048-8 | P3 | RESEARCH 早期表述未随 DESIGN 精化同步：①§6.6 注册表示意 **5 键 + 预留注释** vs 自身 §15 A2 / DESIGN §6.4 六键全注册（调用即 `CapabilityError`）；②§13 B5 门控缺 `enabled`（仅 `is not None`）；③头部判档行「+ **golden**」vs DESIGN §8.3「不新增 golden」——F1 题干「纯函数 golden」验收口径的收窄决定无理由记录 | 三处各补一行「以 DESIGN §6.4 / §7.2 / §8.3 为准」注记；DESIGN §8.3 补一句不录 golden 的理由（手算闭式 + S15 已覆盖，A5 禁录制） |
| F-S8-P048-9 | P3 | DESIGN §7.3「未启用时**不创建**」与 IMPL I-P048-1「**总是**初始化空 list」矛盾，且 §7.3 无内联修正注记（§8.2 对 I-P048-3 有注记先例） | §7.3 补注「（Step 5 微调 I-P048-1：改为常驻空 list，见 IMPL §11）」 |
| F-S8-P048-10 | INFO | 编号前缀复用：不变式 **I-P048-1..7**（RESEARCH §14 / DESIGN §12 标题）与实施微调 **I-P048-1..5**（IMPL §11）同前缀不同义；CHECKLIST 交接 3 已注记「不同族」，但未点明 DESIGN §12 标题本身使用 I-P048-* 全名 | 引用一律带出处节（同类先例 O-S8-P047-1）；不改历史编号 |

#### 18.3.3 环境注记（Step 9 门禁前置条件）

- 本机默认 `python` 解析到 **Anaconda3 全局环境**（缺 `cvxpy` → **25 collection errors**）；门禁必须以项目 venv 解释器执行：`.\.venv\Scripts\python.exe -m pytest ...`（本轮实证：venv 下收集正常）。登记为 Step 9 执行前提；同类先例 O-S5-P047-1（Tk/Tcl 环境缺陷）。
- `git status` 干净（仅 4 个 P-048 文档）；本会话早前出现的 black 格式化差异输出为 `--diff` 报告模式（report-only），未落盘。

#### 18.3.4 结论

- **0 方向性推翻**：四文档的架构口径、门控单一真相源、S15 三项时序口径、P-059 契约隔离全部自洽；
- **2 P2 + 7 P3 + 1 INFO**：两项 P2 均为**计数链 / 基线读数**错误（F-S8-P048-1 不修则 Step 9 门禁目标必错判；F-S8-P048-2 同源），须在 Step 9 执行前吸收；P3 为文档卫生级；
- 判定：**PASS（带修正项）**——修正吸收完成后进入 Step 5 代码落盘，随后 Step 9 验收。

#### 18.3.5 修订吸收（2026-11-19，复审者 GLM-5.3-Flash 经用户批准代执行）

| 发现 | 吸收位置 | 吸收内容 | 状态 |
|---|---|---|---|
| **F-S8-P048-1**（P2） | RESEARCH §15 A4 / DESIGN §8.2 + §15 A4 / CHECKLIST 头部 + D3 | `-k p059` 基线统一改 **60→61**（Step 8 实测）；「全量 collect 60→61」误记删除，全量 collect 订正为 906→929 | ✅ |
| **F-S8-P048-2**（P2） | CHECKLIST §5 / RULE-2 / D1 / 交接 1 + RESEARCH §16 | 计数链改 **+23 = 929**（15+4+3+1；参数化变体 930）；RESEARCH §16 估计值作废并声明以 CHECKLIST 为准 | ✅ |
| F-S8-P048-3 | DESIGN §8.2 阶段 2 行 / §16 T6 | 两处补「已被 I-P048-3 收窄、以 IMPL §7.3 为准」注记 | ✅ |
| F-S8-P048-4 | IMPL §7.3 d2 行 | nav 列表订正为 [100000, 104900]，DD=0 结论不变 | ✅ |
| F-S8-P048-5 | DESIGN §15 A1 / CHECKLIST A2 | A1 注记 11 符号以 IMPL 为准；CHECKLIST A2 证据出口补 `__all__` | ✅ |
| F-S8-P048-6 | RESEARCH §12 Step 5 / DESIGN §16 头注 | 「4 微调」→「5 微调」 | ✅ |
| F-S8-P048-7 | DESIGN 头部 | AST 订正为 22 并注明 P-059 双口径含义（22=core 外 / 29=core 内；吸收轮更正：29 有出处，非「无出处」）；复审状态行更新为 ✅ | ✅ |
| F-S8-P048-8 | RESEARCH 判档行 / §6.6 / §13 B5 + DESIGN §8.3 | 三处「以 DESIGN 为准」注记；§8.3 补不录 golden 的收窄理由 | ✅ |
| F-S8-P048-9 | DESIGN §7.3 | 补 I-P048-1 内联修订注记（常驻空 list） | ✅ |
| F-S8-P048-10 | CHECKLIST 交接 3 | 补「DESIGN §12 标题本身用 I-P048-* 全名」注记 | ✅ |

**闭环：10/10 全部吸收。Step 8 修正项清零，可进入 Step 5 代码落盘。**

### 18.4 Step 10 终审（Qwen3.8-Max，2026-11-19）

> 终审者 Qwen3.8-Max，与作者 DeepSeek-V4.1-Flash（Step 1-7 文档 + Step 5 落码）及 Step 9 回填者 GLM-5.3-Flash 均异构（RULE-5）。方法：①八条门禁 **E1 全量重放**（不采信 Step 9 读数）；②F-S9-P048-1 修正码逐行复核；③engine_v2 六锚点 + S15 计数双写独立 grep；④CHECKLIST §8 证据行号抽样复核（A2/A4-A11/B10）；⑤改动面白名单终态核对。

#### 18.4.1 门禁 E1 重放（全部命中目标）

| 门禁 | 目标 | 终审实测 | 判定 |
|------|------|----------|------|
| pytest 全量 | 932 | `932 passed, 219 warnings in 103.78s`（`collected 932 items`） | ✅ |
| `-k golden` | 18 零重录 | `18 passed, 914 deselected` | ✅ |
| `-k p059` collect | 63 | `63/932 collected (869 deselected)` | ✅ |
| mypy（tests.yml L46 逐字） | 111 files 0 | `111 files: no issues found in 32.93s` | ✅ |
| black 双口径 | 149 · 218 | `149` / `218 files would be left unchanged` | ✅ |
| AST | 22 不变；risk_overlay Try/ignore 0 | core 外 **22**；`ast.Try`=0、`type: ignore`=0 | ✅ |
| `uv lock --check` | exit 0 | `Resolved 148 packages` exit 0 | ✅ |
| `tests/*.py` | 106 | 106（Step 9 实测，终审未重数——文件集未变） | ✅ |

#### 18.4.2 静态核验

- **F-S9-P048-1 修正码**：`DEFENSIVE_POLICIES: Dict[str, Callable[[RiskOverlayConfig], IDefensivePolicy]]`（L208）+ `resolve_policy` `.get(name)` + None 检查（L229-L234），文案不变、零行为变更——代码与 IMPL §14 / CHECKLIST §8.2 记录一致；
- **engine_v2 六锚点**：L62 `import apply_overlay` / L187 `_nav_history=[]` / L371 `external_max_weight` 签名 / L396-L404 校验 / L537 nav append / L1110-L1112 overlay 调用，全部在位；
- **S15 计数双写**：`_scenarios_cases.py` L729 `assert len(SCENARIOS) == 18` + `test_registry_contract`（18）；
- **文档数字**：四文档无 929 目标残留（仅 F-S5-P048-3 历史叙述「929→932」）；
- **改动面**：`git status --short` = M×7 + ??×7 = 14 文件，与 D8 白名单逐项吻合。

#### 18.4.3 发现与吸收

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S10-P048-1** | P3（证据引用区间） | CHECKLIST A2 证据行号 `L72-L91` 仅覆盖 DeRiskContext / DeRiskPlan 两个 frozen dataclass，RiskOverlayConfig 的 `@dataclass(frozen=True)` 在 L46——实质断言（三者均 frozen）为真，引用区间不完整 | A2 区间订正为 **L46-L91** 并逐项列出三处（本表同批落盘） |

#### 18.4.4 结论

- **0 方向性推翻、0 P1/P2**：八条门禁独立重放全部命中；F-S9-P048-1 修正经代码级复核成立；六锚点 / 计数双写 / 改动面白名单全部核实；
- **1 P3**（F-S10-P048-1，证据区间订正，已当场吸收）；
- 判定：**PASS**——D10 已完成：提交 `c12497c`（14 files, +3147/−9）push `73f9807..c12497c`；CI run `44558140801` 四 job 全 success（lock-check / 3.10 / 3.11 / 3.12），`gh run view --log-failed` 空。**P-048 批次关闭。**

---

## 附录：引用表（决策关键）

| 引用 | 定位 | 用途 |
|---|---|---|
| Moreira & Muir (2017) | *Journal of Finance* 72(4):1611–1644，DOI 10.1111/jofi.12513 | vol targeting 为组合层缩放 |
| Harvey et al. (2018) | *JPM* 45(1) Fall 2018 | 同上 |
| Grossman & Zhou (1993) | *Mathematical Finance* 3:241–276，DOI 10.1111/j.1467-9965.1993.tb00044 | DD 约束 → 比例缩放 |
| **Davis & Norman (1990)** | ***Mathematics of Operations Research*** **15(4):676–713**（1990-11） | 无交易带与成本同阶（F-S2-P048-1 更正） |
| Pu & Zhou (2026) | arXiv:2608.10375（ACM ICAIF；v2 2026-09-25） | ramp 形式与 hysteresis 控制器 |
| SEC 424B2 | EDGAR 333-284538（2026-09-17）L134 | `ratably … to the deleverage cash position` |
