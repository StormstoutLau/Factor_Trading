# DESIGN：P-046 组合优化扩展（portfolio optimization / F2）

> **批次**: P-046 · **Step 3 设计** · 日期 2026-11-20
> **判档**: **T1**（`core/portfolio.py` 语义面 + `core/config.py` 校验 + `core/engine_v2.py` 单点接线；golden 18 零重录）
> **上游**: [RESEARCH_p046](RESEARCH_p046_portfolio_optimization.md)（§10.1 Step 0 裁决 / §13.1 仓内核查 / §15 AC 27+ 条 / §16 Step 2 异构复审 **PASS 附 3 前置** R-P046-1/2/3）
> **代码证据时点**: HEAD `b5f69a7`（工作区仅 `docs/RESEARCH_p046_portfolio_optimization.md` 未跟踪，代码零 diff）
> **基座**: DeepSeek-V4.1-Flash（Step 4 设计复审须异构；Step 2 已由 GLM-5.3-Flash 完成）

---

## 1. 范围与前置

### 1.1 本批范围（P-046a 语义修复）

| # | 交付 | 落点 |
|---|---|---|
| **T1** | 约束投影修复：归一化改为 **box∩预算** 投影，`max_weight`/`min_weight` 不再被推翻 | `core/portfolio.py` `_apply_constraints` + 新增 `_scale_to_budget` |
| **T2** | 四类不可行语义（B1/B2 分型，§10.1 已裁决） | 同上 + 新增 `_precheck` |
| **T3** | 默认 `cov_method="ledoit_wolf"` 改用 sklearn `LedoitWolf`（C1） | `_ledoit_wolf_shrinkage` 删除，改 `estimate_cov` |
| **T4** | 协方差统一入口 `estimate_cov`（C3）+ PSD 兜底（G-P046-5） | `core/portfolio.py` 模块级函数 |
| **T5** | 零方差防护（G-P046-4） | `RiskParityOptimizer` |
| **T6** | 诊断载体 `OptimizationResult` + `optimize_with_diagnostics` | `core/portfolio.py` 类型层 |
| **T7** | 配置期校验 `__post_init__`（AC-C-08 改判版） | `core/config.py` L268-297 |
| **T8** | engine 单次算 Σ + 同时注入 optimizer / overlay（选项 i，§10.1） | `core/engine_v2.py` L1080-1106 |
| **T9** | 结构化诊断落账 + 异常分流 | `core/engine_v2.py` L1083-1099 |

### 1.2 明确不做（本批）

| # | 不做 | 归属 |
|---|---|---|
| N1 | BL / HRP / 行业·换手·跟踪误差约束 | P-046b（HRP 另受 U-P046-12 制约） |
| N2 | 矩阵式凯利 / 非等风险预算 | P-046c |
| N3 | 删除死配置字段（`cov_shrinkage` / `round_lot` / `industry_max_weight`） | 见 §2.3 D-3（本批仅标注，不删） |
| N4 | 修改 `config_v2`（FROZEN / TD-2） | 不做，仅记录冻结例外 |
| N5 | overlay 三层缩放公式 | P-048 已锁 |
| N6 | 订单层 `round_lot` 语义 | P-053 |

### 1.3 前置事实（E3 @`b5f69a7`，Step 2 已独立核验 R-A1..A8）

- `_apply_constraints`（[portfolio.py L128-L146](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L128-L146)）：clip upper → clip lower → **除式归一化**（L144），无除零防护；
- `equal_weight` / `risk_parity` 调用 `_apply_constraints`（[L187](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L187) / [L389](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L389)）；`min_variance` / `mean_variance` 走 cvxpy 硬约束 `sum(w)==1`（[L237-L241](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L237-L241) / [L306-L310](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L306-L310)），失败静默回退等权（[L247-L249](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L247-L249) / [L316-L318](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L316-L318)）；
- engine 只传 `returns`（[L1083](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1083)），overlay 独立 `np.cov`（[L1106](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1106)）；
- dataclass `OptimizerConfig` **零校验**（[config.py L268-L297](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L268-L297)）；
- 下游 `target_positions` 仅对 `Σw>1` 告警、**不做归一化**（[L89-L91](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L89-L91) / [L130](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L130)）→ B2 的残差现金天然成立。
- **额外调用点（Step 4 F-D-1）**：[strategy.py L167](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L167)（`FactorSignalStrategy`）与 [L216](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L216)（`DirectionalStrategy`）同样调用 `optimizer.optimize(scores, view.returns)`（**仅 2 参**）；docstring 明示「与引擎逐字同构」。→ 本批 `optimize` **签名冻结**；U1-B 异常将首次穿透 strategy 路径（原为静默超限），方向符合 fail-loud，须补 strategy 用例。
- **契约面（Step 4 F-D-1）**：[interfaces.py L230-L248](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L230-L248) `IOptimizer` Protocol 只约定 `optimize(signals, returns_data) -> pd.Series` → 新增的 `optimize_with_diagnostics` **不进入 Protocol**，`optimize` 保持 Series 返回（结构性子类型兼容由第 3 个默认参数保证）。
- **MVO 注入缺陷（IMPL 期发现，F-D-8）**：`MeanVarianceOptimizer` 在 `returns is not None` 时**无条件重估并覆盖**传入的 `cov_matrix`（[L286-L289](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L286-L289)）；`returns is None` 分支则**未对注入协方差做 reindex**（[L290-L293](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L290-L293)）。选项 i 落地**必须**修此分支，否则引擎注入的 Σ 被静默丢弃（实施细节见 IMPL §4.4）。

---

## 2. 设计决策

### 2.1 D-R1（答 R-P046-1）：AC-C-01 拆为「隔离验证 + 对拍 + 零重录」

**问题**：C1 使收缩系数由 `α≡0` 变为非零 → `risk_parity`/`min_variance`/`mean_variance` 输出必然变化，原 AC-C-01「可行域内与 `b5f69a7` 逐位相同」不可能对这三个 method 成立。

**裁决**：不选「重录快照」（违 A5 禁录制），改为三条可证伪断言：

| 编号 | 断言 | 实现方式（禁录制合规） |
|---|---|---|
| **AC-C-01a** | `cov_method="sample"` 下，四 method 在可行域内的输出与旧实现**逐位相同**（`abs=1e-12`） | 以 `_apply_constraints_legacy`（§9 R1）为对照实现，**运行期双跑比较**，不硬编码向量 |
| **AC-C-01b** | golden 18 零重录 | `-k golden` 18 passed |
| **AC-C-01c** | `ledoit_wolf` 下 `estimate_cov` 与 `sklearn.covariance.LedoitWolf().fit(X).covariance_` **逐位相等**；另加 2×2 手算闭式一例（推导写入测试 docstring） | 对拍 + 闭式 |

**理由**：约束修复的正确性由 AC-C-01a 单独隔离（sample 口径不经过 C1）；C1 的正确性由 AC-C-01c 对拍锁定（不依赖硬编码期望值）；golden 由 AC-C-01b 锁定。三者互不污染。

### 2.2 D-R2（答 R-P046-2）：诊断用「新方法 + 结果对象」，`optimize` 保留为薄包装

**问题**：`optimize` 返回 `pd.Series`，无结构化诊断载体；全仓测试与调用点均按 Series 消费。

**裁决**：

```python
@dataclass(frozen=True)
class OptimizationResult:
    weights: pd.Series
    method: str
    n_selected: int
    max_weight: float
    min_weight: float
    infeasible_kind: Optional[Literal["upper", "lower", "empty", "config"]] = None
    cash_residual: float = 0.0
    message: str = ""
```

| 变更 | 说明 |
|---|---|
| `BaseOptimizer.optimize_with_diagnostics(...) -> OptimizationResult` | **新增抽象方法**，四个子类实现 |
| `BaseOptimizer.optimize(...) -> pd.Series` | 改为**基类具体方法**：`return self.optimize_with_diagnostics(...).weights` |
| 既有子类的 `optimize` 实现 | 重命名为 `optimize_with_diagnostics`，返回结果对象 |
| engine | 改调 `optimize_with_diagnostics`，读 `infeasible_kind` / `cash_residual` 落诊断 |

**兼容性**：外部若 overrides `optimize` 仍优先（grep 确认无此情况）；所有既有测试零改动即可通过。**不采用**「`optimize` 加 `with_diagnostics` 参数」——会引入 `Union` 返回类型，mypy 需 overload，收益低于成本。**不采用**实例属性 `last_result`——破坏无状态复用。

**先例**：P-048 `OverlayResult`（[risk_overlay.py L106-L122](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L106-L122)）同构。

### 2.3 D-R3（答 R-P046-3）：可行性预检前置到「选股后、求解前」

**问题**：min_var/mvo 在 U1-A 时 `sum(w)==1` 必 infeasible → 静默回退等权 → 再被归一化二次破坏。数值上碰巧等价，但浪费求解、依赖巧合、诊断语义混杂。

**裁决**：新增 `_precheck(n, cfg) -> _Feasibility`，在**四 method 的选股完成后、任何求解/约束之前**调用：

```python
@dataclass(frozen=True)
class _Feasibility:
    kind: Optional[str]          # None | "upper" | "lower" | "empty"
    budget: float                # Σw 目标：1.0（可行）或 n*m（upper）
```

| kind | 触发（`atol=1e-12`） | 动作 |
|---|---|---|
| `"empty"` | `n == 0` | 返回空 Series + warning（既有语义），`cash_residual=1.0` |
| `"lower"` | `n*m0 > 1 + atol` | **抛 `InfeasibleConstraintError`**，不产生任何权重 |
| `"upper"` | `n*m < 1 - atol` | B2：按 method 分支（§4.1 表），`budget = n*m` |
| `None` | `n*m0-tol ≤ 1 ≤ n*m+tol` | 正常求解，投影到 `{Σw=1, m0≤w≤m}` |

**配套**：cvxpy 路径不再有「infeasible → 回退等权」分支（§4.1 表），该分支删除；剩余求解失败（DCPError / 非 PSD / solver error）统一归 **G-P046-5**，行为=抛出 → engine 既有 except 语义（§6.2）。

### 2.4 其余决策

| ID | 决策 | 理由 |
|---|---|---|
| **D-1** | 异常类型 `InfeasibleConstraintError(ValueError)` | AC-B1-05 需可辨识；继承 ValueError 保持既有 `except ValueError` 兼容 |
| **D-2** | 配置期 `__post_init__` 只校验「静态可判」项（`0<m≤1`、`m0≥0`、`m0<m`、`target_count≥1`）；`n·m0>1` 属运行时 | 配置期不知道实际 n（§15.2.3） |
| **D-3** | 死配置字段**不删除**，仅加 deprecated 注释并登记归属（`cov_shrinkage`→随 C1 失效、`industry_max_weight`→P-046b、`round_lot`→P-053） | 删除字段会破坏既有 JSON 反序列化与 `test_config_v2`；P3 技术债不必在 T1 批做 API 破坏 |
| **D-4** | `_apply_constraints_legacy` 保留为私有方法（仅供 AC-C-01a 对照） | §6.2 回退点既有约定；不对外导出 |
| **D-5** | 投影算法用**二分缩放**（§4.2），不用 iterative clip-normalize | 后者不保证收敛/不超限；二分在单调性下确定性收敛，且可闭式验证 |
| **D-6** | 本批 `estimate_cov` 输出**恒保证 PSD**（特征值截断） | G-P046-5 根治点前移；overlay 同时受益 |
| **D-7** | `cov_shrinkage` 字段本批**零消费维持**，不接入 `estimate_cov` | C1 由 sklearn 自算，接入手工收缩会二次失真 |

---

## 3. 类型模型与接口

### 3.1 协方差统一入口

```python
def estimate_cov(
    returns: pd.DataFrame,
    method: str = "ledoit_wolf",
    codes: Optional[pd.Index] = None,
    psd_fix: bool = True,
) -> pd.DataFrame:
    """唯一协方差入口：optimizer 与 overlay 共用（C3 / G-P046-6）。

    - method ∈ COV_ESTIMATORS（sample / ledoit_wolf / ewma），未知 → ValueError
    - NaN：先 dropna(how="any")；有效行 < 2 → 回退 sample + warning（不抛）
    - ledoit_wolf：sklearn.covariance.LedoitWolf().fit(X).covariance_（默认中心化）
    - psd_fix：eigh 截断特征值至 >= 0 后重建
    - codes：非 None 时 reindex（缺失列补 0，保持 PSD）
    """
```

- `_ledoit_wolf_shrinkage`（L33-64）**删除**；`COV_ESTIMATORS` 三档保留但 `ledoit_wolf` 指向 sklearn 实现。
- `_ewma_covariance` 保留（未在 G-P046-3 范围），输出同样过 `psd_fix`。
- **不引入** `cov_shrinkage` 参数（D-7）。

### 3.2 优化器接口

```python
class BaseOptimizer:
    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        raise NotImplementedError

    def optimize(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> pd.Series:
        return self.optimize_with_diagnostics(factor_scores, returns, cov_matrix).weights
```

四个子类：`EqualWeightOptimizer` / `MinVarianceOptimizer` / `MeanVarianceOptimizer` / `RiskParityOptimizer` 均实现 `optimize_with_diagnostics`。

### 3.3 配置校验

```python
def __post_init__(self) -> None:
    if not (0.0 < self.max_weight <= 1.0):
        raise ValueError(f"max_weight 必须 ∈ (0, 1]，当前 {self.max_weight}")
    if self.min_weight < 0.0:
        raise ValueError(f"min_weight 必须 >= 0，当前 {self.min_weight}")
    if self.min_weight >= self.max_weight:
        raise ValueError(f"min_weight({self.min_weight}) 必须 < max_weight({self.max_weight})")
    if self.target_count < 1:
        raise ValueError(f"target_count 必须 >= 1，当前 {self.target_count}")
```

**冻结例外**：`config_v2.OptimizerConfig`（FROZEN / TD-2）不参与等价性验收；其 `cov_method` Literal 双向不一致（缺 `ewma`、多 `shrunk`）仅记录，不改。

---

## 4. 分支矩阵与算法

### 4.1 四 method × 四型（唯一决策表）

| 条件 | `equal_weight` | `risk_parity` | `min_variance` / `mean_variance` |
|---|---|---|---|
| **可行** | `1/n` → 二分投影（无变化） | 乘性迭代 → 二分投影 | cvxpy `Σ=1` + box |
| **U1-A** | clip → 各 `m`，`Σ=n·m`，不归一化 | clip → `Σmin(w_i,m)`，不归一化 | **直接输出各 `m`（跳过求解）**，见 §4.3 |
| **U1-B** | `raise InfeasibleConstraintError` | 同左 | 同左 |
| **U1-C** | 空 Series + warning | 同左 | 同左（预检拦截，避免 cvxpy 空问题） |
| **数值失败** | — | 零方差 → `scale=1` + `reason="zero_vol"` | PSD/DCP → 抛出（G-P046-5） |

> **可行行（Step 4 F-D-2）**：`min_variance` / `mean_variance` 的**可行分支直接返回 solver 原始输出**（沿用旧实现 `pd.Series(w.value, index=selected_stocks)`），**不追加** `_scale_to_budget` / 二次 clip；否则 AC-C-01a 的对照基准失真。cvxpy 的边界容差来自 solver 本身（实测 OSQP 违反 ≤6e-21，§17.1 D-A5），若未来加后处理须另立 AC。
>
> **n 口径（F-D-6）**：`_precheck` 的 `n = len(selected_stocks)`，按 method 各自选股结果取，**不得**用 `cfg.target_count`。

### 4.2 二分缩放投影（D-5）

```python
def _scale_to_budget(
    w: pd.Series, lo: float, hi: float, budget: float = 1.0,
    tol: float = 1e-12, max_iter: int = 60,
) -> pd.Series:
    """保持 w 的相对比例，二分求 s 使 Σ clip(s·w_i, lo, hi) == budget。

    单调性：f(s) = Σ clip(s·w_i, lo, hi) 在 s>0 上单调不减 → 二分必收敛。
    可行性前提：n·lo <= budget <= n·hi（由 _precheck 保证；违反 → 抛 RuntimeError）。
    """
```

- **短路（Step 4 F-D-3）**：进入二分前先判 `|w.clip(lo, hi).sum() − budget| ≤ tol` → **直接返回 `w.clip(lo, hi)`**（不二分）。该分支是 AC-C-01a「可行域内逐位相同」的**契约来源**（等权 `w=1/n` 在可行域必然命中，不引入任何浮点改动）；
- 上界用 doubling 扩张（`s ← 2s` 直至 `f(s) ≥ budget`，最多 60 次）；`f(0) = n·lo ≤ budget` 与 `f(∞) = n·hi ≥ budget` 由 `_precheck` 保证有解；
- 终态再 `clip(lo, hi)`，并断言 `|Σw − budget| <= 1e-9`；
- 等权输入 `w=1/n`、可行域 → `s=1`（AC-C-01a 的逐位相同即依赖此性质）。

### 4.3 min_var/mvo 在 U1-A 的唯一解

预算固定 `Σw = n·m`、每项上界 `w_i ≤ m` ⇒ 对 `i=1..n` 求和得 `Σw_i ≤ n·m`，等号成立 ⇒ 每个不等式都取等 ⇒ `w_i = m`（∀i）。故 U1-A 下 min_var/mvo 的**可行域是单点**，与目标函数无关。

- 因此直接返回 `w_i = m`（跳过 cvxpy），`infeasible_kind="upper"`、`cash_residual=1−n·m`；
- 该结果与 equal_weight 的 U1-A 输出**同值**（等权亦为各 `m`）；
- 与 risk_parity 的 U1-A 输出**不同**（后者保留相对比例，`Σ ≤ n·m`）；
- 新增 **AC-B2-08** 固化此性质。

### 4.4 零方差防护（G-P046-4）

`RiskParityOptimizer` 迭代前：`portfolio_vol = sqrt(wᵀΣw)`；若 `<= 1e-18` 或非有限 → 返回等权 + `OptimizationResult(message="zero_vol")`，不再产生 `NaN`（现状 F-P046-4）。

---

## 5. 协方差统一入口与 overlay

### 5.1 选项 i 接线（§10.1 已裁决）

engine 在构造 `returns_data` 后**只算一次**：

```python
cov = estimate_cov(returns_data, method=cfg.cov_method)
result = optimizer.optimize_with_diagnostics(tradable_stocks, returns_data, cov_matrix=cov)
...
overlay = apply_overlay(..., cov=cov)     # 替代 L1106 的 np.cov
```

- optimizer 内部按选中 `codes` 以 `.loc` 截取 `cov`（**与 `b5f69a7` 一致**：缺失码触发 `KeyError` → 引擎既有 `except` 记录并跳过当日；**不做 `fillna(0)`**，以免伪造零协方差。Step 6 F-E-6 反向修正原「reindex 缺失补 0」措辞）；
- overlay 消费同一矩阵（P-048 公式不变，仅输入来源改变）；
- `cov_lookback` 语义不变（L1071 窗口构造不变）。

### 5.2 S15 场景安全性

P-048 S15 用 `target_vol=None` → σ 不参与缩放 ⇒ 输入来源改变**不影响**既有 S15 数值（RESEARCH §6.3 已判）。golden 18 中 crossing 场景同理由 AC-C-01b 锁定。

---

## 6. engine 接线

### 6.1 计算点

| 行 | 变更 |
|---|---|
| L1071-L1081 | 不变（窗口与 `returns_data` 构造） |
| L1083 | 改调 `optimize_with_diagnostics(..., cov_matrix=cov)` |
| L1087-L1099 | `except InfeasibleConstraintError` → 记录 + emit + `return`（numeric_skip）；`except Exception` 保持既有 |
| L1101-L1119 | overlay 改用 `cov`（删 L1106 `np.cov`） |

### 6.2 错误分流（AC-B1-05）

| 异常来源 | 时点 | 处置 |
|---|---|---|
| U1-D 配置矛盾 | `OptimizerConfig.__post_init__`（engine 之前） | 冒泡，启动即失败 |
| U1-B 运行时不可行 | `optimize_with_diagnostics` 内 | engine 捕获 → 诊断 + emit ERROR + 当日跳过（numeric_skip） |
| 数值失败（PSD/DCP/solver） | cvxpy | 同上（与 G-P046-5 合并） |

> **I-P046-6 语义边界（R-P046-9）**：「不得静默」= 必须 `diagnostics.record` + `emit(ERROR)`。engine 现状 L1087-1099 已具备该行为，本批只增加结构化字段，不新增「静默」路径。

### 6.3 诊断落账

`infeasible_kind` / `n_selected` / `max_weight` / `min_weight` / `cash_residual` / `message` 写入既有 `diagnostics.record(...)`（签名以 Step 5 E3 复核为准，不臆造）。

---

## 7. 不变式（本批必须维持）

| ID | 不变式 | 验证 |
|---|---|---|
| I1 | `Σw ≤ 1 + 1e-12`（永不满仓超限） | AC-C-02 |
| I2 | `-1e-12 ≤ w_i ≤ m + 1e-9`（无负、无超上限） | AC-C-03 |
| I3 | 无 `NaN`/`inf`（含 `Σw_raw=0`） | AC-C-04 |
| I4 | 幂等 + 确定性（无随机、无时钟） | AC-C-05/06 |
| I5 | 不可行必有结构化诊断 | AC-C-07 |
| I6 | 引擎不得把配置错误降级为静默跳过 | AC-B1-05 |
| I7 | golden 18 零重录 | AC-C-01b |
| I8 | `estimate_cov` 输出对称半正定 | 新增 `test_p046_cov_psd` |

---

## 8. AC 映射与测试计划

### 8.1 测试文件

| 文件 | 覆盖 |
|---|---|
| `tests/test_p046_constraints.py`（新建） | AC-C-01a..09、AC-B1-01..06、AC-B2-01..08、AC-B3（不适用则标记 skip 理由） |
| `tests/test_p046_cov.py`（新建） | AC-C-01c、PSD、NaN、EWMA、`estimate_cov` 未知 method |
| `tests/test_p046_engine.py`（新建） | 选项 i 单次计算（monkeypatch 计数）、U1-B 分流、诊断落账 |

命名遵循 `test_u1_ac_<选项>_<编号>_<简述>`（§15.6）。

### 8.2 既有测试处置（U-P046-5 / AC-B1-06）

| 文件 | 位置 | 处置 |
|---|---|---|
| `test_p023_quality_guardrails.py` | L128 | 显式 `max_weight=0.5`（n=2 可行）或改断言 |
| `test_p025_day_error_diagnostics.py` | L178 / L259 / L300 | L178 显式 `max_weight`；L259/L300 断言若只看计数/异常则不动，Step 5 逐条核对 |
| `test_p026_silent_exception_governance.py` | L229 | 同上 |

**原则**：只改「测试配置」使其表达意图，不改断言语义；若某断言确实依赖旧超限行为，须在 CHECKLIST 登记为「语义修正」。

### 8.3 门禁

**Step 9 实测（2026-11-20）**：全量 **987 passed**（932 + 55；collect 偏移 +14 见 CHECKLIST F-S9-P046-1）；`-k golden` **18 passed 零重录**；mypy **111 files 0 issue**；black `core tests` **152**、全仓 **221**（均 0 reformatted）；`tests/*.py` **109**；AST `except Exception` core 外 **26**（基线 22 口径不可复现，F-S9-P046-2；本批 core 外零 diff）、core **30**；`uv lock --check` exit **0**。

---

## 9. 风险与回退

| ID | 风险 | 回退/缓解 |
|---|---|---|
| R1 | 投影改动导致数值漂移 | `_apply_constraints_legacy` 保留（D-4），AC-C-01a 双跑对照 |
| R2 | C1 使 risk_parity/min_var/mvo 输出变化 | 由 AC-C-01c 对拍锁定；不改 golden |
| R3 | `__post_init__` 打红既有非法配置用例 | Step 5 全量跑后逐条登记；若确有测试依赖非法配置，改为「期望 ValueError」 |
| R4 | `estimate_cov` 的 NaN 处理改变有效样本 | 先 dropna(how="any") 与 `returns.cov()` 的 pairwise 不同 → 在 README/注释标注；AC 断言「不抛、PSD」而非「与旧样本协方差逐位相同」 |
| R5 | engine 诊断接口签名不符 | Step 5 以 E3 复核为准，不改 `diagnostics` 模块 |
| R6 | U1-A 下 min_var/mvo 退化为等权是否可接受 | 数学必然（§4.3）；若产品不接受，唯一替代是 U1-A 改走 B1/B3（竞品 pypfopt 为求解期 infeasible，E8）→ 需用户另裁 |

---

## 10. 未决与后续批次

| ID | 内容 | 归属 |
|---|---|---|
| U-P046-12 | HRP 无一手原文（E13） | P-046b 前须用户裁决（降级接口预留 / 取许可以 riskfolio-lib 为实现参照） |
| U-P046-14 | `estimate_cov` 的 NaN 口径由 pairwise 改 listwise 是否需在 config 暴露开关 | 本批不加开关（YAGNI）；若 Step 4 认为必要再议 |
| U-P046-15 | 是否新增 P-059 S16「约束不可行」场景 | Step 2 建议加；本 DESIGN 暂列 Step 5 可选，由 Step 4 复审确认 |
| 后续 | BL / HRP / D3 / L3-1 / L3-2 | P-046b / P-046c |
