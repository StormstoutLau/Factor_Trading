# RESEARCH：P-048 风险 overlay（risk overlay / F1 决策闭环）

> **批次**: P-048 · **Step 1 调研**（Step 0 架构裁决 + 正式立项补全）· 日期 2026-11-19
> **执行序**: P-059 之后（关键路径 `045/046/047 → 059 → **048** → 050`）；P-046 未立项但不构成前置阻塞
> **判档**: **T1**（新增 `core/risk_overlay.py` 纯函数模块 + 测试；**不新增 golden**，以 [DESIGN §8.3](DESIGN_p048_risk_overlay.md) 为准——F-S8-P048-8③；生产面仅需可选接线）
> **上游**: 用户裁决「先议定歧义①的架构位置」「②overlay 与既有 DrawdownGuard 的关系」「③>12% 转防御的动作定义：方案需要多选，做策略基类，先做容易做的，其他复杂动作预留接口」；[UPGRADE_MASTER_PLAN.md](UPGRADE_MASTER_PLAN.md) F1 题干（v3.0，L150-188）；[PROGRESS.md](PROGRESS.md) P-047 遗留登记
> **代码证据时点**: HEAD `73f9807`（P-059 关闭；`git status` 仅本文 1 个未跟踪文件）
> **基座**: 正文 DeepSeek-V4.1-Flash
> **净收敛**: 本轮关闭 **6/6** 未决项（§10），满足规范 §净收敛纪律第 1 款
> **取证声明**: 本仓源码为 T1（逐字读取，标 HEAD + 行号）；外部文献仅达摘要级，按 §11 实际层级标注，**不冒充 T1**；标识符解析留 Step 2

---

## 0. 本文定位

本文为 P-048 **Step 1 调研**：§3-§10 是 Step 0 阶段的架构裁决（三个歧义 + 四个次生问题），§2.2 / §2.4 / §13-§17 是 Step 1 立项补全（缺口 / 取证 / 拆分 / 不变式 / DoD / 基线 / 待补项）。

| Step 0 已定（架构裁决） | Step 1 已补全（立项产物） |
|---|---|
| 分层架构（§3） | 缺口编号 G-P048-1..6（§2.2） |
| DD 度量与跳变治理（§4） | 取证表 F1-F3（§2.4） |
| overlay 与 Guard 的关系（§5） | 任务拆分 B1-B5 + 回退点（§13） |
| 转防御动作的接口形态（§6） | 不变式 I-P048-1..7（§14） |
| weights 模式一致性（§7） | DoD A1-A9（§15） |
| 组合方式与决策锚点 D1-D8（§8-§9） | 基线 / 目标读数（§16） |
| 未决项 U-P048-1..6 裁决（§10） | Step 2 待补项（§17） |

---

## 1. 触发与题干

### 1.1 触发

用户 2026-11-19 连续三轮指令：先裁决 overlay 在 optimizer 之前还是之后，再要求对「overlay vs DrawdownGuard」「转防御动作定义」补充调研，并明确后者需**多方案 + 策略基类 + 先易后难 + 预留接口**。

### 1.2 题干（F1 原文摘要）

风险 overlay 是把风险约束翻译为**目标权重**的纯函数层：

- 范式：「vol-targeting × 回撤闸门 × 暴露上限」三层叠加
- 缩放公式：`w = min(1, σ目标/σ实测)`
- 回撤闸门：`DD > 8%` 减半、`DD > 12%` 转防御
- 另含单票 / 行业 / 流动性上限
- **输出目标权重，不直接下单**
- 验收口径：风险 → 权重纯函数 golden

### 1.3 明确不做

| # | 不做 | 依据 |
|---|---|---|
| N1 | 不做多资产 / 债券 / 黄金 / 衍生品对冲 | 本仓 A 股 long-only 股票池 |
| N2 | 不做负面舆情降权 / 黑名单 | 属 P-049 sentiment_feed |
| N3 | 不做盘中 / 分钟级 DD 判定 | 日频口径 |
| N4 | 不引入杠杆（`scale ≤ 1`） | F1 `min(1, ·)` |
| N5 | 不改 18 条 golden 期望值 | P-059 已锁 |
| N6 | 不在 P-048 内做矩阵式凯利 / 风险预算求解 | 属 P-046 遗留 |

---

## 2. 代码事实基线（@`73f9807`）

### 2.1 可复用资产

| # | 资产 | 位置 | 可复用内容 |
|---|------|------|-----------|
| 1 | 波动率目标缩放 | [sizing.py L200-220](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L220) | `vol_target_scale(weights, cov, *, codes, target_vol=0.15) -> (weights, scale, reason)`；已实现 `min(target/σ_p, 1.0)`、不加杠杆、`zero_vol` 归因、P-047 golden 锁定 |
| 2 | 订单级风控 | [guard_pipeline.py L161-187](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L161-L187) | `DrawdownGuard(max_drawdown=0.15)`：`drawdown=(peak-current)/peak`，超过即 `passed=False`、`severity="error"`、`"New positions blocked."` |
| 3 | 组合约束 | `core/portfolio.py::_apply_constraints` | `MinVariance/MeanVariance` 用 scipy SLSQP 把 `w <= max_weight` 作为**优化约束**；`EqualWeight/RiskParity` 用**后处理 clip + 归一化** |
| 4 | 风险评分 | `core/risk_monitor.py` | 5 维 monitor + `CompositeRiskEngine` + `RiskGuardAdapter` |
| 5 | 传染度量 | `core/global_contagion.py` | CoVaR / 传染网络 / Granger |
| 6 | 场景验证 | `tests/_scenarios_*.py`（P-059） | `SCENARIOS` dict 注册表 + 10 断言原语 + `scripts/verify_scenario.py`，新模块可低成本挂载 |
| 7 | 接口范式 | [interfaces.py](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py) | 12+ 个 `Protocol`（`IOptimizer` / `IExecutionSimulator` / `IRiskEngine` …），`I*` 命名 + 中文 docstring |

### 2.2 缺口

| # | 缺口 | 证据（HEAD `73f9807`） | 影响 |
|---|------|------|------|
| **G-P048-1** | 无 `core/risk_overlay.py` | 全仓零命中 `risk_overlay` / `RiskOverlay` | 需新建模块（B1） |
| **G-P048-2** | 无组合级连续缩放层 | `vol_target_scale` 存在但**无调用点**接入 rebalance 主链路 | 需接线（B5） |
| **G-P048-3** | 无 DD 闸门的连续 / 阶梯实现 | `DrawdownGuard` 只有 binary 阻断 | 需 `IDefensivePolicy`（B2） |
| **G-P048-4** | 无「防守动作」抽象 | 无 `IDefensivePolicy` / `CapabilityError` | 需新建协议与错误类型（B1-B2） |
| **G-P048-5** | `GuardPipeline` 未接入生产回测路径 | `engine_v2.py` 对 `GuardPipeline` / `DrawdownGuard` **零引用**；仅 `engine_plugins` 可选路径 + `risk_monitor` 适配器 + web 展示 + `test_compatibility` | 决定「并存」只能是显式配置（B5） |
| **G-P048-6** | weights 模式不强制 `max_weight` | `set_signal(mode="weights")` 仅校验「每行和 ≤1 且非负」，随后跳过优化器 | 需可选校验（B4） |

### 2.3 关键事实：`DrawdownGuard` 与 overlay 在生产路径上不相交

`engine_v2.py` 全文无 `GuardPipeline` 引用，说明：

- 回测主链路**当前不受** `DrawdownGuard` 约束；
- 因此 P-048 把 overlay 接入主链路是**新增行为**，不会与既有 Guard 叠加；
- 若二者同时启用，属于**显式配置**而非默认，需在 §5 设定支配关系。

### 2.4 取证表（F1 日期 / F2 版本 / F3 降级链）

**A 类断言（改变方向的关键结论）只接受 T1**。本表只列支撑 D1-D8 与 U-P048-1..6 的**决定性来源**；§11 的其余条目属扩展线索，**不用于支撑任何关键结论**。

| # | 关键结论 | 决定性来源 | 层 | 读取日 | 版本 / 定位 |
|---|---|---|---|---|---|
| E1 | overlay 必须在 optimizer 之后（`σ_p` 需 `w`） | `core/sizing.py` `vol_target_scale(weights, cov, ...)` 签名 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L200-206 |
| E2 | optimizer 前不存在权重对象 | `core/engine_v2.py` `_execute_rebalance` 调用序列 | **T1** 源码 | 2026-11-19 | HEAD `73f9807` |
| E3 | post-clip + 归一化破坏 ERC | `docs/DESIGN_p047_position_sizing.md` L357 | **T1** 仓内文档 | 2026-11-19 | v1.0，L357 |
| E4 | DD 口径 = running peak | `core/guard_pipeline.py` L174-176 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L174-176 |
| E5 | Guard 为 BUY 级 binary 阻断 | `core/guard_pipeline.py` L161-187 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L161-187 |
| E6 | `GuardPipeline` 未接入主链路 | `core/engine_v2.py` 全文零命中 | **T1** 源码 | 2026-11-19 | HEAD `73f9807` |
| E7 | Guard 默认值无测试锁定 | `tests/test_compatibility.py` L144 仅构造 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L144 |
| E8 | weights 合法用例超 `max_weight` | `tests/test_p044_strategy_interface.py` L255 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L255 |
| E9 | `set_signal` weights 仅校验和 ≤1 与非负 | `core/engine_v2.py` L380-385 | **T1** 源码 | 2026-11-19 | HEAD `73f9807`，L380-385 |
| E10 | 敞口按比例移至现金是行业标准 | SEC 424B2 volatility control 条款 | T2 官方文件（片段级） | 2026-11-19 | 未逐字，Step 2 解析 |
| E11 | 连续 ramp / 无交易带公式 | arXiv 2608.10375 | T4 转述（摘要级） | 2026-11-19 | arXiv:2608.10375，未回原文 |
| E12 | 无交易带最优性 | Davis & Norman (1990) | T4 转述（经 arXiv 摘要） | 2026-11-19 | 未回原文 |

**F3 降级链**

| 通道 | 状态 | 读到的事实 | 未取证 |
|---|---|---|---|
| 仓内源码 | **无降级**（逐字读取） | E1-E9 | — |
| 学术原文 | 未执行 PDF 全文读取 → 降级至 WebSearch 摘要 | 公式形态与定性结论 | 原文定理编号、假设条件、样本区间 |
| SEC 官方文件 | 未逐字读 424B2 全文 → 降级至搜索片段 | `ratably reallocating … to the deleverage cash position` | 完整条款、生效日、指数编制细节 |

**A 类达标情况**：E1-E9 为 T1 仓内来源，满足「≥2 独立来源且 ≥1 T1」；E10-E12 仅作佐证，**不单独支撑任何决策**，其标识符解析交 Step 2。

---

## 3. 歧义①：overlay 的架构位置（已裁决）

### 3.1 决策

**不是二选一，而是从 2 层扩展为 3 层：「风险模型」在 optimizer 之前，「风险 overlay」在 optimizer 之后。**

```
Strategy.generate_signals(scores)
  → [L1] RiskModel  : 协方差 Σ 估计（returns_data）            ← pre-optimizer
  → [L2] Optimizer  : 横截面约束 max_weight / industry / turnover  ← in-optimizer
  → [L3] RiskOverlay: 组合级缩放 vol_target × DD_gate          ← post-optimizer（P-048 新模块）
  → build_target_positions → 执行
```

对应 F1 三层叠加的归属：**vol-targeting 与回撤闸门归 L3，暴露上限归 L2**。

### 3.2 决定性依据：`σ_p` 需要 `w`

`σ_p = sqrt(wᵀΣw)` 的输入是权重。optimizer 之前只有 scores，无权重可用；若前置只能拿等权近似，会使「目标波动率」名存实亡。

本仓代码已锁定该事实：[sizing.py L200-206](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L206) 的签名把 `weights` 作为必需参数；`engine_v2._execute_rebalance` 在调用 `optimizer.optimize(...)` 之前不存在任何权重对象。

### 3.3 外部证据

| 来源 | 类型 | 结论 |
|---|---|---|
| Moreira & Muir (2017, *JF*) | 学术 | `y^σ_t = c_t·y_t`，对**已构建组合**的收益序列乘标量 |
| Harvey et al. (2018, *JPM*) | 学术 | "leveraging the portfolio … scaling down"，组合层敞口缩放 |
| Grossman & Zhou (1993) | 学术 | DD 约束最优解 = cushion 的常数比例（缩放形式） |
| Black & Jones (1987) / Black & Perold (1992) CPPI | 学术 | `E(t)=m·C(t)`，总敞口乘数 |
| AllianzGI Risk Management Overlay | 行业 | 规则化下行风险管理层，"an overlay" |
| Overlay 通用定义 | 行业 | "added **on top of** an existing portfolio" |
| AQR RP II MV Fund | 行业 | 基金层目标波动率 10%（组合级校准） |
| Swoopr | 实务 | 资产级 sizing + **组合级 vol 检查并按比例缩放全部持仓** |
| Qlib | 开源 | `RiskModel(Σ)` 作为 optimizer 输入；策略层无组合级 scaling |
| Barra | 行业 | 提供 Σ 与因子暴露供优化器消费（pre） |

### 3.4 顺序不可交换

- 先约束后缩放：`单票 ≤ max_weight × scale ≤ max_weight` ✓，且缩放保持权重比例；
- 先缩放后约束：clip 截断大票 → 必须重新归一 → 破坏 vol target 目标。

P-047 已有硬实证：默认 `max_weight=0.10` 下 `RiskParityOptimizer` 的 post-clip + 归一化把 ERC 解压缩为**等权** `[1/3, 1/3, 1/3]`，其风险贡献 `pct=[0.158, 0.322, 0.520]` 偏离风险预算 `1/3`；把 `max_weight` 放宽到 1.0 后 `pct=1/3` 精确成立（[DESIGN_p047 L357](file:///f:/Coding/Factor_Trading_v3.0/docs/DESIGN_p047_position_sizing.md#L357)；[PROGRESS L2281](file:///f:/Coding/Factor_Trading_v3.0/docs/PROGRESS.md#L2281)）。

**推论**：L3 必须是**纯标量乘法、不归一化、余额留现金**。

### 3.5 需订正的文档

[UPGRADE_MASTER_PLAN.md](UPGRADE_MASTER_PLAN.md) 架构图中的 `RiskOverlay → Optimizer` 顺序需改为 `Optimizer → RiskOverlay`（或明确区分「风险模型 pre」与「风险 overlay post」）。`[待 Step 1 回写]`

---

## 4. 次生问题 A：DD 的度量口径与跳变治理

### 4.1 度量口径（无争议）

学术标准为 running peak 到谷底：

```
peak_t = max(NAV_0 .. NAV_t)
dd_t   = 1 - NAV_t / peak_t
MDD    = max_{k<j} (p_k - p_j) / p_k
```

不用 rolling window（引入窗口参数与边界效应），不用绝对值（DD 惯例是相对值）。

该口径与既有 `DrawdownGuard` 完全一致（[guard_pipeline.py L174-176](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L174-L176)）。

### 4.2 跳变治理：三种可用手段

F1 的「8% 减半 / 12% 转防御」是阶跃函数，在 8% 边界必然反复穿越。

| 方案 | 形式 | 依据 | 状态依赖 |
|---|---|---|---|
| **连续 ramp** | `dd≤8%` → 1；`8%~12%` 线性降到 `b_min`；`≥12%` → `b_min` | arXiv 2608.10375 `max(b_min, 1−k·(d−d_start)/(d_full−d_start))` | **无** |
| **双阈值滞回** | 入场 12%、出场 8%（Schmitt trigger） | Davis & Norman (1990) 无交易区严格证明；Kallsen–Muhle-Karbe `[s−Δ, s+Δ]` | 需上期 scale |
| **权重无交易带** | `\|w^raw − w_{t−1}\| ≤ 5%` 则不动 | 同上；arXiv 2608.10375 hysteresis controller | 需上期权重 |

### 4.3 建议与理由

**默认连续 ramp（无状态）**，`dd_hysteresis` 作可选开关（默认关）。

理由：

1. F1 要求「overlay 输出权重可独立复算」，指向**无状态**；
2. Davis–Norman 推论：无交易带宽度与交易成本同阶，`cost=0` 时带宽应趋于 0——本仓 `cost` 可配置，无条件加滞后会引入无成本依据的粘滞；
3. 需要滞回时以 `RiskOverlayState` 承载，与既有 `SizingState` 同模式，不污染默认路径。

---

## 5. 次生问题 B：overlay 与既有 `DrawdownGuard` 的关系

### 5.1 本仓事实

| 维度 | `DrawdownGuard` | P-048 overlay |
|---|---|---|
| 层级 | 订单级（逐笔 BUY） | 组合级（整组权重） |
| 动作 | binary 阻断 | 连续缩放 |
| 度量 | `(peak−current)/peak` | 同口径 |
| 接入 | `engine_plugins` 可选路径 | 主链路 L3（待接） |
| 输出 | `GuardResult(passed, severity)` | `scale ∈ [0,1]` |
| 默认阈值 | `max_drawdown=0.15` | `8% / 12%` |

### 5.2 行业实践：soft first, hard last

| 来源 | 结论 |
|---|---|
| Breaking Alpha | hard = inviolable，触发 immediate deleveraging；soft = warning + 允许短暂越界（例：12% 目标允许到 14%） |
| Brenndoerfer | 三级升级：warning（80% utilization）→ soft breach → hard breach；"the trading system simply refuses to execute violating trades" |
| NexusFi | hard DD 阈值典型 **20–25%**；25% 回撤需 33% 收益才回本，故硬阈值须显著高于软阈值 |
| Swoopr | hard cap 立即 trim / soft cap 临时超限 + planned trim |
| Trendsandbreakouts（反面） | 批评 account-level hard stops 的 whipsaw 成本，主张 per-trade 风险预算 |

### 5.3 参数冲突与建议

**冲突**：本仓 `DrawdownGuard` 默认 **0.15**，而 overlay 在 **12%** 已降到防御位。两者只差 3%，同时启用会**重复计数**（overlay 已缩到低比例，Guard 再阻断全部 BUY）。

**建议（D6）**：

| 并存方式 | 配置 |
|---|---|
| 仅 overlay | 默认；主链路 |
| overlay + Guard | overlay `8%→12%` ramp；Guard 上调至 **0.20** 作为最后断路器 |
| 仅 Guard | 保留旧行为（`engine_plugins` 路径），不改 |

`DrawdownGuard` 未接入主链路，调整默认值不影响 18 条 golden，只影响其自身单测。

**可选增强**：给 `GuardResult` 增加 `scale: float = 1.0`（向后兼容默认 1.0），为「Guard 也做软缩放」留口；本批不实现。

---

## 6. 次生问题 C：转防御动作定义（多方案 + 策略基类）

### 6.1 本仓约束

A 股 long-only 股票池，**无债券 / 黄金 / 期货 / 期权**，「切防御资产」在物理上不可实现。

### 6.2 外部证据

| 来源 | 结论 |
|---|---|
| SEC 424B2（volatility control 指数） | `reducing realized volatility … by ratably reallocating a portion of the index exposure from the base index to the deleverage cash position`；显式 `w_k + c_k = 1`、`0 ≤ w_k ≤ L` |
| Grossman–Zhou / CPPI | risky + risk-free，risk-free 即现金 |
| Axplusb | raising cash 是最简对冲；"avoid the temptation to go to all cash without a clear plan to re-enter" |
| Alpha Alternatives | long-only equity 的主要手段是 cash buffer |
| Equicurious / AB | defensive sector equities（beta 0.5–0.8）是「切资产」版本，需行业映射 |
| StockAlpha | step-down ladder（buffer 到 60% 缩 50%，到 30% 归零） |
| FinRL-X（arXiv 2603.21330） | composable pipeline + "portfolio-level risk **overlays** within a **unified protocol**" |

### 6.3 方案对比

| 选项 | 语义 | 判定 |
|---|---|---|
| A 全清仓 | `scale=0` | 简单；错过反弹，需再入场规则 |
| B 固定下界 | `scale=b_min` | 简单；引入参数 |
| C 切防御行业 | 银行 / 公用 / 红利映射 | **破坏纯函数**，需行业外部依赖 |
| **D 比例降敞口到现金** | `w ← s·w`，`cash ← 1−s·Σw` | **建议基线**：纯函数、与 SEC 口径逐字一致 |

**裁决**：默认 D；C 与衍生品对冲作为**可选策略实现**预留（§6.4），并把 `defensive_asset_rotation` 登记为能力边界（P-059 `CAPABILITY_BOUNDARIES` 新增键）。

### 6.4 接口设计（策略基类 + 多实现 + 预留）

```python
@dataclass(frozen=True)
class DeRiskContext:
    """防守动作的输入快照（纯数据，无引擎依赖）。"""
    drawdown: float                      # 相对 running peak
    peak_nav: float
    current_nav: float
    weights: Mapping[str, float]         # 当前目标权重


@dataclass(frozen=True)
class DeRiskPlan:
    """防守动作的产物。

    ``scale`` 为主通道（标量缩放）；``weights`` 为**预留通道**，用于未来
    资产切换 / 对冲等非比例动作，届时无需改动 Protocol。
    """
    scale: float = 1.0                                   # ∈ [0, 1]
    action: str = "none"                                 # none / cash_scaling / fixed_floor / ladder / ...
    weights: Optional[Mapping[str, float]] = None         # 预留：完整权重覆盖
    reason: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class IDefensivePolicy(Protocol):
    """下行防守动作接口（P-048）。"""

    name: str
    def plan(self, ctx: DeRiskContext) -> DeRiskPlan: ...
```

**设计要点**：`DeRiskPlan` 同时携带 `scale`（标量）与 `weights`（可选完整映射）。未来切防御行业或对冲时只需填 `weights`，`IDefensivePolicy` 一行不改——这是「预留接口」的正确形态，而非让基类抛异常。

### 6.5 实现分级（先易后难）

| 实现 | 难度 | 语义 | 本批 |
|---|---|---|---|
| `NoDeRiskPolicy` | 易 | `scale=1` | ✅ 实现（默认关） |
| `CashScalingPolicy` | 易 | `8%→12%` 线性 ramp 到 `b_min` | ✅ **默认** |
| `FixedFloorPolicy` | 易 | `dd ≥ t` → `scale=b_min` | ✅ 实现 |
| `TieredLadderPolicy` | 易 | 多档阶梯 `[(0.08,0.5),(0.12,0.25),(0.20,0.0)]` | ✅ 实现 |
| `SectorRotationPolicy` | 难 | 切防御行业（需行业映射 / universe） | ⏸ 预留，抛 `CapabilityError` |
| `HedgeOverlayPolicy` | 难 | 股指期货 / 期权对冲（本仓无衍生品） | ⏸ 预留，抛 `CapabilityError` |

### 6.6 注册与配置

沿用本仓既有 dict 注册表范式（同 P-059 `SCENARIOS`）：

```python
DEFENSIVE_POLICIES: dict[str, type[IDefensivePolicy]] = {
    "none": NoDeRiskPolicy,
    "cash_scaling": CashScalingPolicy,
    "fixed_floor": FixedFloorPolicy,
    "ladder": TieredLadderPolicy,
    # "sector_rotation": SectorRotationPolicy,   # 预留位，实现即注册
}
```

配置项 `defensive_policy="cash_scaling"`；未知键在构建期 fail-loud（对齐 P-059 S11「脏输入显式失败」范式）。

> **F-S8-P048-8① 订正**：上方代码块为 Step 0 时代表意（5 键 + 预留注释位）；本批以 [DESIGN §6.4](DESIGN_p048_risk_overlay.md) 为准——**六键全注册**（含 2 个预留策略，调用即抛 `CapabilityError`，与本文 §15 A2 一致）。

---

## 7. 次生问题 D：weights 模式的一致性缺口

### 7.1 现状

`set_signal(mode="weights")` 直出权重并**跳过优化器**，仅校验「每行和 ≤1 且非负」，**`max_weight` 不被强制**。因此 weights 模式下 L2 约束层实际被绕过。

### 7.2 工程实践

| 来源 | 做法 |
|---|---|
| QuantJourney Backtester | `weights.clip(upper=0.25)` 后明确注释 **"Do NOT renormalize after clipping"**（残差留现金） |
| tradeexecutor | `value/total` 归一化 → `clip_to_normalised` |
| nanobook-rebalancer | target weights → **pre-trade risk checks** → 发单 |
| QuantConnect | `OrderByMarginImpact`（先减仓后加仓）保证现金约束 |
| SEC 424B2 | 敞口挪到 cash，绝不重新归一 |

### 7.3 三方案与建议

| 方案 | 做法 | 判定 |
|---|---|---|
| 甲 不补约束 | 仅叠加 L3 缩放 | ❌ 单票可能 100%，上限名存实亡 |
| **乙 校验可选** | 显式给阈值才校验，越界抛 `ValueError` | ✅ **选定**：只校验不修改，符合契约 |
| 丙 clip 不归一 | overlay 内截断 | ❌ 违反 P-044「权重不得二次优化」，可能动 golden |

**建议乙（D4，Step 0 复核后修正）**：校验**默认关闭**，改为可选参数 `external_max_weight: Optional[float] = None`——只有显式给值才校验 `max(w) ≤ external_max_weight`，越界 fail-loud。

修正依据（代码事实）：[test_p044_strategy_interface.py L255](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p044_strategy_interface.py#L255) 的合法 weights 用例来自 `adapter.signals_frame`，多票等权天然超过 `OptimizerConfig.max_weight=0.10`；weights 模式的语义本就是「绕过优化器的横截面约束」，再用优化器的 `max_weight` 去校验它自相矛盾。

理由：**校验**不违反 P-044「权重不得二次优化」的契约，**修改**才违反；但校验阈值必须由调用方显式给出，不能从 optimizer 配置隐式继承。

---

## 8. 附加：vol 与 DD 的组合方式

### 8.1 证据

- SEC 424B2：vol control 与 momentum risk control **各自产生独立的 cash position**，串联叠加而非取 min；
- arXiv 2603.01298：`w_k = min{σ^tar/σ̂_k, L}` 后 `c_k = 1 − w_k`，`w + c = 1`。

### 8.2 建议（D5）

```
scale_total = scale_vol × scale_dd
cash        = 1 − scale_total · Σw
```

- **串联相乘**：两个约束语义不同（风险预算 vs 损失控制），乘法保证同时满足；
- 配 `scale_floor` 防止乘积过度（示例 `0.5×0.25=0.125`）；
- **不重新归一化**，残差进现金；
- 缩放后不足一手的持仓交给既有 `min_size` 过滤 → 归零 → 现金（与 P-047 一致）。

---

## 9. 决策锚点

| 锚点 | 内容 | 状态 |
|---|---|---|
| **D1** | 三层架构：RiskModel(pre) → Optimizer(in, 约束) → RiskOverlay(post, 缩放)；架构图 L139 订正 | 已裁决（§3） |
| **D2** | DD 口径 = running peak；默认连续 ramp（8%→12% 线性至 `b_min`），`dd_hysteresis` 可选默认关 | 已裁决（§4） |
| **D3** | 转防御基线 = 按比例挪到现金；`defensive_asset_rotation` 登记能力边界 | 已裁决（§6） |
| **D4** | weights 模式「校验可选、只校验不修改」；默认关，`external_max_weight` 显式给值才校验 | 已裁决（§7.3） |
| **D5** | 组合方式 = 串联相乘 + `scale_floor`；不重新归一，残差留现金 | 已裁决（§8） |
| **D6** | overlay(soft, 8/12%) 与 `DrawdownGuard`(hard) 阶梯并存；**不改** Guard 默认 0.15，并存时显式配置 0.20 并做构建期校验 | 已裁决（§5.3 / §10） |
| **D7** | 防守动作以 `IDefensivePolicy` 插件化；本批 4 个易实现，2 个预留（`CapabilityError`） | 已裁决（§6） |
| **D8** | `DeRiskPlan` 必须同时支持 `scale` 与 `weights`，为资产切换 / 对冲预留 | 已裁决（§6） |

---

## 10. 未决项裁决（Step 0 已闭合）

六项均已得出明确结论，无待裁决项。依据强度按「强（代码事实或数学必然）/ 中（行业惯例推断）」标注。

| ID | 结论 | 依据 | 强度 |
|---|---|---|---|
| U-P048-1 | 默认 `defensive_policy="cash_scaling"`（连续 ramp）；`ladder` 作显式可选 | 与 D2「默认连续 ramp」一致；两者均无状态，差异只在语义连续性 | 强 |
| U-P048-2 | **不改** `DrawdownGuard` 默认 `0.15`；并存时显式配置 `0.20`，并在构建期校验「overlay 上界 < Guard 阈值」，否则 fail-loud | 代码事实：Guard 未接入主链路，`test_compatibility.py` 仅构造不锁默认值；最小改动原则；行业 hard 阈值 20–25% 作为并存时的推荐值 | 强 |
| U-P048-3 | `b_min` 默认 **0.0**（全现金），可配置 | SEC volatility control 允许敞口降到 0（`c_k=1`）；Grossman–Zhou cushion=0 → 风险敞口 0；Axplusb「勿无计划全现金」由 ramp 对称恢复解决，非永久锁定 | 中 |
| U-P048-4 | 默认**不引入** `RiskOverlayState`；`dd_hysteresis=False`（已并入 D2） | §4.3：Davis–Norman 带宽 ∝ 交易成本，`cost=0` 时带宽→0；F1 要求可独立复算 | 强 |
| U-P048-5 | **接入主链路但默认关闭**（opt-in）：`RiskOverlayConfig.enabled=False`、`defensive_policy="none"` | 18 条 golden 必须零改动；不接线会重演 P-047 `vol_target_scale` 无调用点的死代码；接入点 = `_execute_rebalance` 内 `optimizer.optimize` 之后、`build_target_positions` 之前 | 强 |
| U-P048-6 | 校验**默认关**，`external_max_weight` 显式给值才校验 | [test_p044 L255](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p044_strategy_interface.py#L255) 的合法 weights 用例（`adapter.signals_frame` 多票等权）天然超 `max_weight=0.10`；weights 模式语义即绕过优化器约束 | 强 |

**可选增强（不阻塞本批）**：`GuardResult` 增加 `scale: float = 1.0` 字段，为「Guard 也做软缩放」留口；本批不实现。

---

## 11. 参考来源（扩展线索池）

> 本清单除 §2.4 的 E1-E9（仓内 T1）外**均未逐字回原文**，不用于支撑关键结论。层级按实际读取深度标注（T2 官方片段 / T3 社区 / T4 转述），标识符解析交 Step 2。

**学术（T4 转述，摘要级）**

- Moreira & Muir, *Volatility-Managed Portfolios*, Journal of Finance (2017) — https://tylersmuir.com/data.html
- DeMiguel et al., *A Multifactor Perspective on Volatility-Managed Portfolios*, JF (2024) — https://onlinelibrary.wiley.com/doi/10.1111/jofi.13395
- *Smoothing volatility targeting* (arXiv 2212.07288) — https://arxiv.org/html/2212.07288v1
- Harvey et al., *The Impact of Volatility Targeting*, JPM (2018) — https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf
- CFA Digest 摘要 — https://www.cfainstitute.org/en/research/cfa-digest/2019/07/dig-v49-7-2
- Boyd et al., *Multi-period portfolio selection with drawdown control* — https://stanford.edu/~boyd/papers/pdf/multiperiod_portfolio_drawdown.pdf
- Zhou & Shang, *Drawdown Control with a Risk Floor* — https://www.semanticscholar.org/paper/Drawdown-Control-with-a-Risk-Floor-Zhou-Shang/b0fa2ee9d744454a97dee6dce3422a035895a03a
- *Portfolio Optimization Book* §10.5 Drawdown Portfolios — https://portfoliooptimizationbook.com/book/10.5-drawdown-portfolios.html
- *Beyond Forecasting: Recasting Volatility Control as a Routing Problem* (arXiv 2608.10375) — https://arxiv.org/html/2608.10375v2
- *Asymptotics and Duality for the Davis and Norman Problem* (arXiv 1010.0627) — https://arxiv.org/html/1010.0627v1
- *Optimal Investment Under Transaction Costs: A Threshold Rebalanced Portfolio Approach* (arXiv 1203.4156) — https://arxiv.org/pdf/1203.4156
- *Single-Asset Adaptive Leveraged Volatility Control* (arXiv 2603.01298) — https://arxiv.org/html/2603.01298v1
- FinRL-X (arXiv 2603.21330) — https://arxiv.org/html/2603.21330v1

**行业 / 监管**

- AllianzGI RiskLab — Risk Management Overlay — https://hk.allianzgi.com/en-hk/risklab
- Overlay Strategy Definition — https://onwealth.net/glossary/overlay-strategy
- Morgan Stanley — Total Portfolio Approach — https://www.morganstanley.com/im/en-sg/institutional-investor/insights/articles/total-portfolio-approach-holistic-management-trends-upward.html
- Man Group — Applying Dynamic Risk Management — https://www.man.com/insights/applying-dynamic-risk-management
- AQR Risk Parity II MV Fund (SEC 497K) — https://www.sec.gov/Archives/edgar/data/1444822/000119312519133328/d735639d497k.htm
- S&P DJI — Indexing Risk Parity Strategies — https://spglobal.cn/spdji/en/documents/research/research-indexing-risk-parity-strategies.pdf
- SEC 424B2 — Volatility Control / deleverage cash position — https://www.sec.gov/Archives/edgar/data/886982/000119312526394454/amendment_no._1_to_mofca.htm
- SEC 424B2 — exposure reduced, cash positions increased — https://www.sec.gov/Archives/edgar/data/886982/000156459023000383/gs-424b2.htm
- Breaking Alpha — Portfolio-Level Risk Constraints — https://breakingalpha.io/insights/portfolio-level-risk-constraints
- Breaking Alpha — Stop-Loss Mechanisms in Institutional Trading Systems — https://breakingalpha.io/insights/stop-loss-mechanisms-institutional-trading-systems
- Risk Management Practices: Limits, Hedging & Governance — https://mbrenndoerfer.com/writing/risk-management-practices-policies-limits-hedging-governance
- NexusFi — Equity Curve Trading: Soft First, Hard Last — https://nexusfi.com/a/risk-management/equity-curve-trading
- Axplusb — Systematic Strategies for Drawdown Management — https://media.axplusb.eu/2026/07/22/building-resilience-systematic-strategies-for-drawdown-management/
- Swoopr — Volatility Targeting for Portfolios — https://www.getswoopr.com/portfolio-management/rebalancing-risk-budgeting-position-policy/volatility-targeting-for-portfolios/
- Swoopr — Position-Size Limits (hard cap vs soft cap) — https://www.getswoopr.com/research/sell-discipline/risk-limit-sells/position-size-limits/
- Trends and Breakouts — Hard Drawdown Stops — https://trendsandbreakouts.com/hard-drawdown-stops
- StockAlpha — Return Stacking: Dynamic Scaling Rules — https://stockalpha.ai/alpha-learning/return-stacking-overlaying-trendmanaged-futures-without-selling-core-beta
- Alpha Alternatives — Drawdown Reduction in Long-Only Equity Portfolios — https://alt-alpha.sg/strategies-for-drawdown-reduction-in-long-only-equity-portfolios/
- Equicurious — When to Hold Cash or Defensive Assets — https://equicurious.com/learn/markets-and-macro/market-cycles-and-regimes/when-to-hold-cash-or-defensive-assets
- pfolio academy — CPPI — https://www.pfolio.io/academy/portfolio-insurance-cppi
- Black & Perold, *Theory of Constant Proportion Portfolio Insurance* — https://zero.sci-hub.st/267/15138e6e7f2291cf14c12505484a26d0/black1992.pdf
- pfolio academy — Maximum Drawdown — https://www.pfolio.io/academy/maximum-drawdown
- *Implementing and testing the Maximum Drawdown at Risk* (PDF) — https://daneshyari.com/article/preview/5069225.pdf

**开源 / 工程实践**

- Qlib — Portfolio Optimization（Risk Models） — https://deepwiki.com/microsoft/qlib/10.5-portfolio-optimization
- Qlib — Portfolio Strategy — https://qlib.readthedocs.io/en/stable/component/strategy.html
- QuantJourney Backtester — Strategy Modes（clip 不归一） — https://backtester.quantjourney.cloud/strategy-modes
- tradeexecutor.strategy.weighting — https://tradingstrategy.ai/docs/_modules/tradeexecutor/strategy/weighting.html
- nanobook-rebalancer — https://crates.io/crates/nanobook-rebalancer/0.10.2
- QuantConnect — Portfolio Targets / OrderByMarginImpact — https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/execution/key-concepts

---

## 12. 后续步骤预留

| 步骤 | 内容 | 状态 |
|---|---|---|
| Step 1 | 缺口编号 G-P048-1..6、取证表、任务拆分 B1-B5、不变式 I-P048-1..7、DoD A1-A9、基线读数 | ✅ 本章（§2.2 / §2.4 / §13-§16） |
| Step 2 | 异构复审（GLM-5.3-Flash） | ✅ §18（E1-E9 逐条复核 + F4 验证表；0 方向性推翻，**2 P2 + 5 P3**） |
| Step 3 | DESIGN（本文 D1-D8 升格为设计决策） | ✅ [DESIGN_p048](DESIGN_p048_risk_overlay.md)（17 节；F-S2-P048-1..7 全部吸收于 §17） |
| Step 4 | DESIGN 复审 | ✅ [DESIGN §18.1](DESIGN_p048_risk_overlay.md)（PASS 带修正项：1 P2 + 5 P3，0 方向性推翻；P2 = 配置模块须钉死 core/config.py dataclass 并改直接属性访问） |
| Step 5 | 实现（`core/risk_overlay.py` + 测试 + 场景注册） | ✅ 代码落盘（`core/risk_overlay.py` 254 行 + engine 6 锚点 + S15；pytest **932** / golden **18** / `-k p059` **63** / mypy **111** / black **149·218** / AST **22**）；实施发现 6 项见 [IMPL §14](IMPL_p048_risk_overlay.md) |
| Step 6 | IMPL 复审 | ✅ [DESIGN §18.2](DESIGN_p048_risk_overlay.md)（PASS 带修正项：1 P2 + 4 P3 + 5 项正面核验；**修正已 5/5 吸收**，S15 按真实时序重推） |
| Step 7 | CHECKLIST（零预填，40 项） | ✅ [CHECKLIST_p048](CHECKLIST_p048_risk_overlay.md)（A12 + B11 + C7 + D10；39 × `[待 Step 9]` + 1 × `[待 Step 10]`；F-S7-P048-1 补登 T4 用例） |
| Step 8 | 文档一致性复审 | ✅ [DESIGN §18.3](DESIGN_p048_risk_overlay.md)（PASS 带修正项：2 P2 + 7 P3 + 1 INFO；P2 = `-k p059` 基线实测 60 非 39、CHECKLIST 计数链漏计 B9 三例） |
| Step 9 | 验收回填 | ✅ [CHECKLIST §8](CHECKLIST_p048_risk_overlay.md)（39 项全 `✅`；门禁八项全命中：pytest **932** / golden **18** / p059 **63** / mypy **111** / black **149·218** / AST **22** / uv exit 0 / tests **106**；发现 F-S9-P048-1 已修） |
| Step 10 | 终审 + 提交 + CI | `[待 Step 10]` |

---

## 13. 任务拆分（B1-B5，含签名与回退点）

| B | 任务 | 接口签名 / 交付 | 回退点 |
|---|---|---|---|
| **B1** | 类型契约 | `CapabilityError(RuntimeError)`；`DeRiskContext` / `DeRiskPlan`（§6.4）；`IDefensivePolicy.plan(ctx) -> DeRiskPlan`；`RiskOverlayConfig`（`enabled=False` / `defensive_policy="none"` / `target_vol=None` / `dd_soft=0.08` / `dd_hard=0.12` / `b_min=0.0` / `scale_floor=0.0` / `dd_hysteresis=False`）——**`external_max_weight` 不在此**（Step 3 修正 F-S2-P048-4：归 B4 的 `set_signal` 签名） | 新文件，删除即回退 |
| **B2** | 4 个易实现策略 + 2 个预留 | `NoDeRiskPolicy` / `CashScalingPolicy` / `FixedFloorPolicy` / `TieredLadderPolicy`；`SectorRotationPolicy` / `HedgeOverlayPolicy` 抛 `CapabilityError`；`DEFENSIVE_POLICIES` 6 键（含预留位） | 纯新增，无外部依赖 |
| **B3** | 组合级编排 | `apply_overlay(weights, *, nav_history, cov, codes, policy, config) -> OverlayResult`；`OverlayResult(weights, scale_vol, scale_dd, scale_total, cash_residual, action, reason)`；`scale_total = max(scale_floor, scale_vol × scale_dd)`（**以 DESIGN §5.2 为准**，Step 4 修正含 floor）；`cash = 1 − scale_total·Σw` | 纯函数，不改调用方 |
| **B4** | weights 模式可选校验 | `set_signal(..., external_max_weight: Optional[float] = None)`：仅当非 None 时校验 `max(w) ≤ external_max_weight` | 默认 `None` → 既有行为逐字不变 |
| **B5** | 主链路 opt-in 接线 | `BacktestConfig.risk_overlay: Optional[RiskOverlayConfig] = None`；非 None 且在 `_execute_rebalance` 内 `optimizer.optimize` 之后、`build_target_positions` 之前调用 B3；门控精化以 [DESIGN §7.2](DESIGN_p048_risk_overlay.md) 为准（`is not None` 且 `enabled`，F-S8-P048-8②） | `None` → 不 attach，golden 零改动 |

**依赖序**：B1 → B2 → B3 →（B4 与 B5 可并行）。B5 依赖 B3。

---

## 14. 不变式（I-P048-1..7）

| I | 内容 | 检验方式 |
|---|---|---|
| **I1** | `0 ≤ scale_total ≤ 1`（不加杠杆） | 属性测试 + 断言 |
| **I2** | 缩放为标量乘法，**不重新归一化**：`Σ w_out ≤ Σ w_in`；**预留 `plan.weights` 通道除外**（Step 3 修正 F-S2-P048-7） | 逐值断言 |
| **I3** | 现金残差 `= 1 − scale_total·Σw ≥ 0` | 逐桶断言 |
| **I4** | **精确条件（Step 3 修正 F-S2-P048-2）**：`not enabled` **或**（`defensive_policy=="none"` **且** `target_vol is None`）⇒ 输出与输入**逐值相等**且 `scale_total==1.0`（原「或」表述错误：`policy="none"` + `target_vol=0.15` 时 vol 缩放仍生效） | 同构对拍 |
| **I5** | `scale_dd` 对 DD 单调不增；`scale_total = max(scale_floor, scale_vol × scale_dd)` | 网格扫描 |
| **I6** | `DD ∈ [0,1]`，峰值取 running max | 边界用例 |
| **I7** | 输出权重非负、代码集合 ⊆ 输入代码集合（预留 `weights` 通道除外） | 集合断言 |

---

## 15. DoD（A1-A9）

| A | 验收项 | 证据出口 |
|---|---|---|
| **A1** | `core/risk_overlay.py` 存在，导出 `IDefensivePolicy` / `DeRiskContext` / `DeRiskPlan` / `CapabilityError` / `DEFENSIVE_POLICIES` / `RiskOverlayConfig` / `apply_overlay` / `OverlayResult` | 读码 + `__all__` |
| **A2** | 注册表 6 键（4 实现 + 2 预留）；未知键构建期 fail-loud | 单测 |
| **A3** | `enabled=False` / `None` 时 **18 条 golden 零重录** | `pytest -k golden` + `git status tests/golden/` |
| **A4** | 开启后行为由 **P-059 场景 S15（overlay 端到端）**承接（**Step 3 追加修正**：复用 P-059 统一验证入口；`SCENARIOS` 17→18，`-k p059` **60→61**——基线 60 为 Step 8 实测订正 F-S8-P048-1：原记 39 系 P-059 B8 `test_p059_scenarios.py` 单模块 collect 数误升格） | [DESIGN §8.2](DESIGN_p048_risk_overlay.md) |
| **A5** | ramp 的闭式期望**手算**（至少 DD=5% / 10% / 15% 三点），禁录制 | 手算推导入场景 `title`/注释 |
| **A6** | `scale_vol` 与 `scale_dd` 可独立单测（B3 拆分可测） | 单测 |
| **A7** | mypy / black / `uv lock --check` 三绿；AST `except Exception`（core 外）**不增** | 命令读数 |
| **A8** | `core/risk_overlay.py` 导出 `OVERLAY_CAPABILITIES`，键集**完全等于** `{defensive_asset_rotation, hedge_overlay}`；**不扩展** P-059 `CAPABILITY_BOUNDARIES`（**Step 3 修正 F-S2-P048-3**：后者为精确键集相等契约，新增键会使 P-059 测试红） | [DESIGN §10](DESIGN_p048_risk_overlay.md) |
| **A9** | 文档回写：`PROGRESS.md` 登记、`UPGRADE_MASTER_PLAN.md` 架构图 L139 订正 | diff |

---

## 16. 基线 / 目标读数

| 指标 | 基线 @`73f9807` | 目标 |
|---|---|---|
| `pytest -q` | **906 passed** | **932** = 906 + 26（实测；Step 1 估计值 +12~18 作废，F-S5-P048-3） |
| `pytest -k golden` | **18 passed / 888 deselected** | **18（零重录）** |
| mypy（CI 等价命令） | **110 files, 0 issue** | **+1 源** = 111 |
| black `core tests` | **146 files** | +测试文件数 |
| black 全仓 | **215 files** | +新增文件数 |
| `tests/*.py` | **104** | +新增测试模块 |
| AST `except Exception`（core 外生产面） | **22** | **22（不变）** |
| `uv lock --check` | **exit 0** | **exit 0** |

> 基线读数取自 P-059 关闭时 Step 10 独立复跑（CHECKLIST §10）；`HEAD 73f9807`，`git status` 仅本文 1 个未跟踪文件。

---

## 17. Step 2 待补项（引用解析）

| # | 待办 | 原因 | Step 2 处置（§18.3） |
|---|---|---|---|
| S2-1 | SEC 424B2 逐字核验（条款号、生效日、指数编制细节） | 当前为片段级（E10） | ✅ 全文抓取，L134 逐字命中（GS Momentum Builder Focus ER，EDGAR 333-284538，2026-09-17）；条款号/编制细节仍留 Step 3 引用建表 |
| S2-2 | arXiv 2608.10375 全文（定理 / 公式编号、假设条件） | 当前为摘要级（E11） | ✅ abs 页 T1 命中 + HTML v2 目录确认 §D.3.4 Hysteresis Controller / §D.5.12 Portfolio Hysteresis；公式经 html 片段直引 |
| S2-3 | Davis & Norman (1990) 原期刊出处（非 arXiv 转述） | 当前为二传（E12） | ✅ 原文著录：*Math. Oper. Res.* 15(4):676–713（1990-11）；§11 链接指向后续论文 → F-S2-P048-1 |
| S2-4 | Grossman & Zhou (1993)、Moreira & Muir (2017) 原文 | §3.3 的学术支撑需 T1 化 | ✅ G&Z：*Math. Finance* 3:241–276（DOI 10.1111/j.1467-9965.1993.tb00044）；M&M：*JF* 72(4):1611–1644（DOI 10.1111/jofi.12513） |
| S2-5 | 逐条解析 §11 的 48 条 URL / DOI / arXiv ID | 规范 Step 2 要求「ID 可解析」 | ◑ 决策关键 6 条已解析（§18.3）；长尾 ~36 条标**未验证（线索级）**，与 §11 声明一致，不支撑决策 |

---

## 18. Step 2 复审（GLM-5.3-Flash，2026-11-19）

> 复审者 GLM-5.3-Flash，与作者 DeepSeek-V4.1-Flash 异构。方法：①E1-E9 仓内 T1 断言**逐行重读源文件**独立复核；②决策关键外部引用**标识符解析**（WebFetch arXiv abs / SEC 全文，WebSearch 期刊著录）；③D1-D8 / U-P048-1..6 / §13-§15 批判性自洽审查。复审者未采信作者的任何读取结论，全部独立取证。

### 18.1 仓内 T1 断言复核（E1-E9）

| ID | 作者断言 | 复核结果 | 证据 |
|---|---|---|---|
| E1 | `vol_target_scale(weights, cov, *, codes, target_vol=0.15)`，`min(target/σ_p, 1.0)` | ✅ 逐字属实 | [sizing.py L200-206、L219](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L206) |
| E2 | optimizer 前无权重对象；插入点 = optimize 之后、build_target_positions 之前 | ✅ 属实：`_execute_rebalance` L1006 → `optimizer.optimize` L1057 赋值 `target_weights` → `build_target_positions` L1094 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1057) |
| E3 | post-clip+归一化破坏 ERC | ✅ 逐字属实（pct=[0.158,0.322,0.520]；P2b max_weight=1.0 → 1/3） | [DESIGN_p047 L357-358](file:///f:/Coding/Factor_Trading_v3.0/docs/DESIGN_p047_position_sizing.md#L357-L358) |
| E4 | DD = running peak | ✅ 逐字属实（`peak=max(values)`，`(peak−current)/peak`） | [guard_pipeline.py L174-176](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L174-L176) |
| E5 | Guard 为 BUY 级 binary 阻断，默认 0.15 | ✅ 逐字属实（`passed=False`、`severity="error"`、`"New positions blocked."`） | [guard_pipeline.py L161-187](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L161-L187) |
| E6 | engine_v2 对 GuardPipeline/DrawdownGuard 零引用 | ✅ 全文 grep 零命中 | 本轮独立 grep |
| E7 | Guard 默认值无测试锁定 | ✅ tests 全域 grep：仅 test_compatibility.py L144 import 位置构造一次，无用例断言 0.15 | 本轮独立 grep |
| E8 | 合法 weights 用例超默认 max_weight=0.10 | ⚠️ **成立但表述有偏** → F-S2-P048-6 | test_v5（L231）外部权重 0.5/0.5（target_count=2 等权）确实 > 0.10；但该引擎显式构造 `max_weight=1.0`（**L72**），并非在 0.10 下运行 |
| E9 | weights 模式仅校验非负 + 行和 ≤1 | ✅ 逐字属实 | [engine_v2.py L380-385](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L380-L385) |

### 18.2 批判性审查（结论方向）

- D1（三层架构）数学必然性与 E1/E2 独立成立，无反例；
- D2/D5/D6 与 E4/E5/E6/E7 一致；U-P048-1..6 的依据强度标注与复核结果相符；
- §13 B5 插入点与 E2 的行号链一致；A5 的 ramp 手算三点（5%/10%/15% → 1/0.5/0，b_min=0）代数自洽；
- **未发现方向性错误**；发现规格级 / 表述级问题 7 项（§18.4）。

### 18.3 F4 文献验证表（标识符解析）

| 引用 | ID | 验证方式 | 状态 |
|---|---|---|---|
| Pu & Zhou 2026 *Beyond Forecasting…*（VolRouter） | arXiv:2608.10375；DOI 10.48550/arXiv.2608.10375 | WebFetch abs 页（提交 2026-08-11，v2 2026-09-25，ACM ICAIF，作者 Hongji Pu / Leyang Zhou）+ HTML v2 目录含 §D.3.4 Hysteresis Controller、§D.5.12 Portfolio Hysteresis | **已验证**（标题/作者/日期全匹配；ramp 与 hysteresis 公式经 arXiv html 第一方片段直引） |
| Davis & Norman (1990) | *Math. Oper. Res.* 15(4):676–713（1990-11） | WebSearch：ACM DL 著录页、SIAM、NYU Stern 原文 PDF 三源交叉 | **已验证**；RESEARCH §11 链接指向 arXiv 1010.0627（Guan 等的**后续**论文）→ F-S2-P048-1 |
| Grossman & Zhou (1993) | *Math. Finance* 3:241–276；DOI 10.1111/j.1467-9965.1993.tb00044 | WebSearch：SIAM 引文、arXiv 1710.01503、Lund Univ.、Boyd PDF 四源交叉 | **已验证**；Boyd PDF 证实其「将 Black & Jones (1987) / Black & Perold (1992) CPPI 扩展至随机 floor」——与 §3.3 证据链一致 |
| Moreira & Muir (2017) | *JF* 72(4):1611–1644；DOI 10.1111/jofi.12513 | WebSearch：T&F 引文表、Wiley 2025 Fischer Black Prize 颁奖文、NBER w22208 三源交叉 | **已验证** |
| Harvey et al. (2018) | *JPM* 45(1) Fall 2018（Harvey/Hoyle/Korgaonkar/Rattray/Sargaison/Van Hemert 六人） | WebSearch：JPM 官网期刊目录、CFA Digest、作者 Duke PDF 三源交叉 | **已验证** |
| SEC 424B2 | EDGAR 注册号 333-284538（GS Finance Corp. Momentum Builder Focus ER，2026-09-17） | WebFetch **全文**：L134 逐字命中 `ratably allocating a portion of the base index exposure to the deleverage cash position ... volatility control level of 5%`；L142 证实 momentum risk control 使用**独立** cash position | **已验证（T1，官方文件全文）** |
| §11 长尾 ~36 条（AllianzGI / Man / AQR / S&P DJI / Qlib / QuantJourney / tradeexecutor 等） | URL | 未逐条解析 | **未验证（线索级）**——与 §11 头部声明一致，不支撑决策；Step 3 建表时不得升格 |

### 18.4 发现清单（F-S2-P048-1..7）

| ID | 级别 | 发现 | 处置（落 Step 3 DESIGN） |
|---|---|---|---|
| **F-S2-P048-1** | P3 | §11 学术区 Davis & Norman (1990) 链接指向 arXiv 1010.0627（Guan 等《Asymptotics and Duality for the Davis and Norman Problem》，系**后续论文**），非原文；原文著录 *Math. Oper. Res.* 15(4):676–713 | 引用更正为原文（DOI 形态 `10.1287/moor.15.4.676` 建表时解析确认） |
| **F-S2-P048-2** | **P2** | **I4 表述错误**：「enabled=False **或** defensive_policy='none' 时输出=输入」不成立——enabled=True + policy='none' + target_vol=0.15 时 vol 缩放仍生效。精确条件应为：`not enabled` **或**（`policy='none'` **且** `target_vol is None`）。按原句写测试会因默认 `target_vol=None` 侥幸通过、显式配置时语义错误 | DESIGN 重写 I4；B3 identity 语义以此为准 |
| **F-S2-P048-3** | **P2** | **A8 与 P-059 契约冲突**：A8 要求 `CAPABILITY_BOUNDARIES` 新增 2 键，但 [tests/_scenarios_assert.py L155-170](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_assert.py#L155-L170) `assert_capability_declared` 以**精确键集相等**断言 8 键（「少一或多一都算缺口」），[test_p059_scenarios.py L121-123](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p059_scenarios.py#L121-L123) 将直接红 | DESIGN 择一：①同步修改期望集 8→10（测试面改动，须在 CHECKLIST 登记 + P-059 A10 锚点注记「随 P-048 扩展」）；②改「必含 ⊇」语义；③P-048 另建边界表 |
| **F-S2-P048-4** | P3 | **参数双宿**：`external_max_weight` 同时出现在 B1（RiskOverlayConfig 字段）与 B4（set_signal 签名）。校验发生点在 set_signal（optimizer 之前的入口层），RiskOverlayConfig 中的副本是死配置 | 择一归属（建议 set_signal 签名），删除另一处 |
| **F-S2-P048-5** | P3 | **门控三重冗余**：B5 `is not None` 门控 + U-P048-5 默认 `enabled=False` + B1 默认 `policy="none"`，三层「关」语义重叠 | DESIGN 明确单一真相源：None=未配置；提供则由 `enabled` 决定；`policy="none"` 为策略层显式恒等（受修正后 I4 约束） |
| **F-S2-P048-6** | P3 | **E8 表述有偏**：test_v5 引擎显式构造 `max_weight=1.0`（test_p044 L72）——作者以放宽上限规避冲突，而非「在 0.10 下天然通过」 | DESIGN 引用时补注 L72；论证锚定为「对默认 0.10 硬校验将破坏 target_count<10 的全部合法用例」 |
| **F-S2-P048-7** | P3 | **I2 例外未声明**：「Σ w_out ≤ Σ w_in」未像 I7 那样排除 `DeRiskPlan.weights` 预留通道 | I2 补注「预留 weights 通道除外」 |

### 18.5 复审结论

- **0 方向性推翻**：D1-D8、U-P048-1..6 全部获得独立 T1 证据支持；
- **2 P2 + 5 P3**：P2 两项（I4 规格、A8 契约冲突）必须在 Step 3 DESIGN 吸收；P3 五项为引用卫生与表述级；
- 文献验证：决策关键 6 条全部**已验证**（其中 SEC 与 arXiv 升为 T1 命中），长尾按声明保留线索级；
- 判定：**PASS（带修正项）**。可进入 Step 3。
