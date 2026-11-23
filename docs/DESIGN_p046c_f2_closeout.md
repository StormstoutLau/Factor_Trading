# DESIGN：P-046c F2 收尾（矩阵凯利 + 非等风险预算 + max_sharpe + 行业上限投影）

> **批次**: P-046c · **Step 3 DESIGN** · 日期 2026-11-23
> **判档**: **T1**（`core/portfolio.py` 求解器扩展 + `core/config.py` 配置 + `core/engine_v2.py` 单插入点 + 3 个新测试文件；全部新增能力 **opt-in**，默认 `equal_weight` 与 golden 22 预期零漂移）
> **上游**: [RESEARCH_p046c_f2_closeout](RESEARCH_p046c_f2_closeout.md)（C1-C20 / G-P046c-1..10 / E1-E7 / U1-U12 / A1-A10）；[REVIEW_p046c_step2](REVIEW_p046c_step2_research.md)（PASS + F-R2-1..4 + 2 观察）；[RESEARCH_p046c_u7_u9_supplement](RESEARCH_p046c_u7_u9_supplement.md)（E8-E12 / 社区锚点 / B4d / U9=A）；[REVIEW_p046c_step2b](REVIEW_p046c_step2b_u7u9.md)（PASS + F-R2b-1..3）
> **代码证据时点**: HEAD `3495683`（P-046b 关闭；本文件零代码变更）
> **基座**: DeepSeek-V4.1-Flash（Step 4 复审须 reviewer ≠ author）
> **本文性质**: 设计方案；Step 4 复审通过后进入 Step 5 IMPL

---

## 0. 本文定位

| 本文件已定 | 留给后续 |
|---|---|
| U-P046c-1..12 全部关闭（§1） | Step 4 设计复审（本文不自评 PASS） |
| 架构决策 D1-D22（§3） | Step 5 IMPL 的逐处代码 |
| 配置/接口签名（§4） | Step 6 IMPL 复审 |
| 五段算法规格（§5） | Step 7 CHECKLIST |
| 引擎接线（§6）/ 不变式（§7） | Step 9 TDD 落码 |
| 测试设计 39 例（§8）/ 门禁目标（§9） | |

---

## 1. 上游裁决摘要（U-P046c-1..12 全部关闭）

| U | 裁决 | 落点 |
|---|---|---|
| U1 ERC 修复方式 | **B1a 原地替换**：快速乘性路径**逐字保留** + 异常回退凸解 | D2/D3 |
| U2 `budget` 配置形态 | **扁平 `risk_budget: dict[str,float]`**（None=等风险）；缺失补剩余均分、多余丢弃 warning（精化规则见 D7） | D6/D7 |
| U3 矩阵凯利归属 | **新 `KellyOptimizer`（method="kelly"）**，复用 `_solve_mean_variance` | D8 |
| U4 凯利 fraction 语义 | `risk_aversion = 1/fraction`（与 MVO 同源） | D8 |
| U5 max_sharpe 无风险利率 | 嵌套 `MaxSharpeConfig(risk_free_rate=0.0)` | D11 |
| U6 max_sharpe upper（n·max<1） | `_upper_result` 留现金（U1-A 一致） | D21 |
| U7 行业/换手/TE scope | **B4d（用户裁决）**：行业上限本批引擎级严格投影；换手 L1 / TE 延后 P-046d | D12-D16 |
| U8 换手/TE 数据来源 | P-046d 的 `OptimizationContext`（industry/prev_weights/benchmark） | D19 + PROGRESS P-046d 行 |
| U9 `industry_max_weight` | **保字段 + 接线消费（用户裁决）**；不删除 | D12/D17 |
| U10 ERC 性能预算 | 混合：正常路径乘性（逐字不变）、异常/预算路径凸解 | D2/D3 |
| U11 诊断载体 | 复用 `message` + `warning_kind`，**不新增字段/枚举类型**；新增一个字符串取值 `"erc_fallback"` + 引擎一处映射 | D5 |
| U12 对拍边界 | 仅本地手工对拍；pypfopt 参考值**固化为测试常量**，CI 不 import 外部包 | D22 |

---

## 2. 范围与非目标

### 2.1 范围

1. `RiskParityOptimizer` 修复（P1 静默退化）+ 非等风险预算 `risk_budget`。
2. `KellyOptimizer`（method=`kelly`）+ `KellyConfig`。
3. `MaxSharpeOptimizer`（method=`max_sharpe`）+ `MaxSharpeConfig`。
4. 行业上限：`project_industry_cap` 纯函数 + 引擎单插入点 + `industry_max_weight` 接线。
5. `build_optimizer` 新增 2 个分支；`OptimizerConfig` 新字段与校验。
6. 3 个新测试文件共 **39 例**（§8 冻结）。
7. PROGRESS 新建 **P-046d** 行（换手/TE 承接，零悬空）。

### 2.2 非目标（明确不做）

| # | 不做 | 依据 |
|---|---|---|
| N1 | 换手 L1 / 跟踪误差实现 | U7/U8；P-046d（需 `OptimizationContext` + 基准数据） |
| N2 | in-solver 行业约束（改 7 个覆盖签名） | B4d；E12 改动面 1 vs 7 |
| N3 | 修改 `config_v2.py`（FROZEN/TD-2） | P-046a C-4 |
| N4 | 修改 `core/sizing.py`（P-047 对角 kelly 行为不变） | U3/A3 |
| N5 | 扩展 CLI `--optimizer-method` choices | P-046b 先例（BL/HRP 亦未扩 CLI） |
| N6 | 删除 `cov_shrinkage` / `round_lot` / `round_lot_optimize` | P-046a D-3；P-053 |
| N7 | 新运行时依赖 / pypfopt 入 CI | Q7 / U12 / I8 |
| N8 | 多阶段 DP / `PortfolioPolicy` / Registry 统一 | P-046b N6/N7 已延后 |

---

## 3. 架构决策 D1-D22

| ID | 决策 | 被拒替代与代价 | 依据 |
|---|---|---|---|
| **D1** | 本批交付五项：ERC 修复、风险预算、Kelly、MaxSharpe、行业投影；换手/TE 显式延后 | 打包三项约束会引入新数据源与目标函数接入，scope 失控 | U7 裁决 |
| **D2** | ERC **快速乘性循环逐字保留**（`target=rc.mean(); w*=target/rc`）；`risk_budget is None` 时才允许走快速路径。**零漂移范围 = 正常路径（diag 全正且 σ_p²>0）的权重**；diag 退化（含部分零方差）为**新增防护路径**（见 D3），权重与现状一致（等权）、诊断从静默新增为 `zero_vol`——现状该路径无任何测试断言（C19），不构成行为破坏 | 改写为 `w*b/pct` 会引入浮点差异，破坏「现有行为零漂移」（E7） | U1/U10；E7；Step 4 F-4-1 |
| **D3** | **diag 预判（新增防护）**：任一 `diag(Σ)≤0` 或非有限 → 等权 + `zero_vol`，**不进入循环与回退**（凸回退 `bᵀlog w≥0` 对部分零方差产生 ~10⁶ 病态解，Step 4 探针证实：Σ=diag(0.04,0.09,0) → w₃=2.69e6，必须拦截）。循环内快速路径四条件回退：① `risk_budget` 非 None；② 任一步 `RC≤0`；③ `max_iter` 耗尽未收敛；④ 收敛后 `max\|pct−1/n\| > 1e-3`。循环内 σ_p²≤0 分支保留现状（保持末次 w + zero_vol） | 删除 diag 预判会让部分零方差落入病态凸解；只修②会留下③④的静默劣化（F-R2-4） | E1/E2/E7；F-R2-4；Step 4 探针 |
| **D4** | 回退凸模型：`min 0.5·wᵀΣw s.t. w≥0, bᵀlog w ≥ 0`，解后归一，再走既有 `_apply_constraints` | 加 `Σw=1` 会引入 ν 项使 KKT 变为 `RC_i=b_iσ²+νw_i`，不再保证 RC∝b；**Step 5 F-5-1 进一步证明 n≥2 时二者直接不可行**（加权几何平均 ≤ 算术平均 = 1，等号仅全 1；探针 status=infeasible）；直接对原始解缩放会破坏约束 | A5/A7；E2 复算 5.67e-05；F-5-1 |
| **D5** | 回退诊断：`message="erc_fallback:<reason>"`、`warning_kind="erc_fallback"`；引擎由映射表 `{"zero_vol":"ZeroVariance","erc_fallback":"RiskParityFallback"}` 分流，category 仍 `optimizer` | 新增 enum/dataclass 字段违反 U11；只写日志不满足 DoD A1「诊断字段非空」；落 `InfeasibleConstraints` 属错误标签 | U11；A1 |
| **D6** | 风险预算字段命名 **`risk_budget`**（不叫 `budget`），docstring 声明「RC 占比目标 ≠ `_scale_to_budget` 的权重预算」；仅 `method="risk_parity"` 可用 | 复用 `budget` 与模块内权重预算语义撞词（F-R2-5） | F-R2-5；U2 |
| **D7** | 预算归一规则：多余键 → warning 丢弃；与选中集**无交集** → 等风险 + warning（不中断回测）；缺失键 → 均分剩余额度；覆盖全部且和≠1 → `ValueError`；已指定和>1 → `ValueError`；归一后任一分量 ≤0 → `ValueError` | 缺失补 1/n 再归一（RESEARCH 原建议）会稀释用户显式预算（例：`{A:0.5}` 在 n=50 时 A 只剩 0.338）；静默 uniform 无法观测 | §5.2 |
| **D8** | `KellyOptimizer` 复用 `_solve_mean_variance`，新增关键字 `risk_aversion: Optional[float]=None`（None→`cfg.risk_aversion`）；Kelly 传 `1/fraction`（**Step 5 F-5-2：pypfopt `max_quadratic_utility` 的 δ = 2/f，其目标含 δ/2 因子**）；**需要 returns（μ）**，缺失 → `ValueError` | 在 sizing 层做矩阵方法（B2b）无箱体/可行性语义；直解 `Σ⁻¹μ` 产生负权重/病态（E3） | U3/U4；A6；F-5-2 |
| **D9** | 嵌套 `KellyConfig(fraction=0.5)`；`0<fraction≤1` | 平铺字段进 `OptimizerConfig` 形成 god object | P-046b D13 先例 |
| **D10** | `MaxSharpeOptimizer` 用 Charnes-Cooper（与 pypfopt A1 同式）：`min yᵀΣy`，`(μ−rf)ᵀy=1`、`Σy=k≥0`、`y∈[min·k, max·k]`；`w=y/k`；`max(μ)≤rf → ValueError`；需 returns | 网格搜索 MVO（B3b）非精确、不可断言；无约束闭式在长多下不成立（E4 复算：闭式含 −0.1385） | A1；E4 |
| **D11** | 嵌套 `MaxSharpeConfig(risk_free_rate=0.0)`；非有限 → `ValueError` | 复用 `BacktestConfig.risk_free_rate`（不存在该字段）或全局常量 | U5 |
| **D12** | 行业上限 = **引擎级严格投影**：`core/portfolio.py` 新增纯函数 `project_industry_cap` + 结果 dataclass；引擎 **1 插入点** + **1 取数助手**；6 个优化器与 `IOptimizer` 零改动 | in-solver 需改 Base+6 覆盖签名与引擎传参（E12 7 vs 1）；朴素截断+归一违反上限（E5/E8） | U7/U9；E5/E8/E12 |
| **D13** | 投影语义：变量 = `weights.index ∩ industry.index` 的股票；其余列（期货）固定；`budget = Σ股票权重`；约束 `Σw=budget`、`0≤w≤max_weight`、每组 `Σ_{i∈g}w_i≤cap`；目标 `min‖w−w0‖²` | 只做组约束不管个股上限可把单票推到 cap（>max_weight）；对全组合归一（含期货）会改变期货 sleeve | §5.5 |
| **D14** | 未分类：行业标签为 **NaN 或 0**（`data.py` L444/L470 以 `fill_value=0` 填充缺失）→ 参与调整但**不计入组约束**，仍受 `max_weight`；`industry` 索引外的代码（期货）→ **固定不动**；未分类计数 warning | fail-loud 会因单票行业缺失中断回测；把 0 当普通组会在数据缺口时制造伪行业集中并可能不可行 | §5.5 |
| **D15** | 投影不可行：容量 `Σ_{g}cap + n_unclassified·max_weight < budget−tol`（且 `n_stocks·max_weight < budget−tol`）→ `InfeasibleConstraintError`；引擎在 **rebalance 阶段**捕获、落账、跳过当日再平衡 | 放行会静默违反上限；抛 `RuntimeError` 会归入 internal 且语义错 | U1-B 同构 |
| **D16** | 投影不触发（全部组和 ≤cap+tol）→ **返回原 Series（逐位不变）**，不做个股 `max_weight` 修复 | 顺带修复个股超限会让「未开行业上限」与「开了但未触发」的结果不同（违反零漂移直觉） | I1/I7 |
| **D17** | `industry_max_weight` 校验 `0<x≤1`；**不采纳** `config_v2` L143 的 `≤max_weight` 规则（行业上限通常大于个股上限；该规则方向性错误且属冻结资产） | 照抄会拒绝合法配置（cap=0.3, max_weight=0.1） | O-U9-1；C18 |
| **D18** | 工厂 map 新增 `kelly` / `max_sharpe` 两键；CLI 不扩 | 扩 CLI 需同步文档/参数测试，超出本批范围 | U3/U5；P-046b 先例 |
| **D19** | 零改动面：`config_v2.py` / `sizing.py` / `target_positions.py` / `interfaces.py` / `round_lot*` / `cov_shrinkage` | 任一改动都会扩大回归面 | I11 |
| **D20** | 观测：投影 applied 时 `logger.info`（groups/unclassified/max_group before→after/L1）；行业数据整体缺失 → **一次性** warning（`_industry_cap_warned`）；未分类 >0 → 每次投影 warning 计数 | 每日 warning 刷屏；无计数则缺失不可见 | U11 |
| **D21** | Kelly / MaxSharpe 的 upper 型沿用 `_upper_result`（各 `max_weight` + 留现金），**不追**「tangency + 现金」最优 | 与 U1-A 语义分叉会使同一配置在两种方法下现金残差口径不同 | U6 |
| **D22** | 零新运行时依赖；E4 pypfopt 参考解以**常量**固化进测试（`[0.164545,0.478144,0.345451,0,0.011859]`、Sharpe `1.38575528`），CI 不 import pypfopt | 引入 pypfopt 会改锁与 CI（P-046b U6 同判） | Q7/U12；I9 |

### 3.1 派生接口变更登记

| ID | 变更 | 理由 | 回退点 |
|---|---|---|---|
| **F-3-1** | `_solve_mean_variance` 新增关键字 `risk_aversion: Optional[float] = None` | Kelly 需覆盖 δ；默认 None 保持 MVO/BL 逐字等价 | `risk_aversion=None` 路径 |
| **F-3-2** | `OptimizationResult.warning_kind` 新增取值 `"erc_fallback"` | P1 修复的可观测性（U11 复用载体） | `warning_kind=None` 路径 |
| **F-3-3** | 引擎新增 `_industry_tags(date)` 私有助手与 `_industry_cap_warned` 属性 | 行业数据取数/一次性告警隔离在引擎 | `industry_max_weight=None` 路径 |

---

## 4. 接口与数据结构

### 4.1 配置（`core/config.py`）

```python
@dataclass
class KellyConfig:
    """凯利方法级配置（仅 method='kelly' 时读取）。"""
    fraction: float = 0.5  # (0,1]；risk_aversion = 1/fraction

@dataclass
class MaxSharpeConfig:
    """max_sharpe 方法级配置（仅 method='max_sharpe' 时读取）。"""
    risk_free_rate: float = 0.0  # 与 μ 同频；有限数

@dataclass
class OptimizerConfig:
    ...
    industry_max_weight: float | None = None  # 行业上限（引擎级严格投影，P-046c 接线）
    risk_budget: dict[str, float] | None = None  # 风险预算（RC 占比目标，仅 risk_parity）
    kelly: KellyConfig = field(default_factory=KellyConfig)  # P-046c
    max_sharpe: MaxSharpeConfig = field(default_factory=MaxSharpeConfig)  # P-046c
```

`__post_init__` 追加校验（在既有四项之后）：

1. `industry_max_weight is not None` → 必须 `0 < x ≤ 1`（不校验 `≤max_weight`，D17）。
2. `risk_budget is not None` → 非空 dict、键为 str、值为有限非负数、和 > 0、且 `method == "risk_parity"`（否则 `ValueError`）。
3. `KellyConfig.fraction` → `0 < f ≤ 1`；`MaxSharpeConfig.risk_free_rate` → `math.isfinite`。

### 4.2 组合层公开接口（`core/portfolio.py`）

```python
@dataclass(frozen=True)
class IndustryCapResult:
    """行业上限严格投影结果（P-046c B4d）。"""
    weights: pd.Series
    applied: bool
    n_groups: int
    n_unclassified: int
    max_group_before: float
    max_group_after: float
    l1_deviation: float


def project_industry_cap(
    weights: pd.Series,
    industry: pd.Series,
    *,
    cap: float,
    max_weight: float,
) -> IndustryCapResult:
    """行业上限严格投影（引擎级，min‖w−w0‖²；期货列固定不动）。

    Raises:
        ValueError: cap ∉ (0,1] 或 max_weight ∉ (0,1]。
        InfeasibleConstraintError: 组容量 + 未分类容量 < 股票预算。
        RuntimeError: 求解器非最优（非不可行类）。
    """


def _risk_budget_vector(
    selected: pd.Index, raw: Optional[Mapping[str, float]]
) -> np.ndarray:
    """风险预算归一（D7 规则）；返回长度 n、和 1、逐项 >0 的向量。"""


def _solve_risk_budget_convex(cov: np.ndarray, budget: np.ndarray) -> np.ndarray:
    """min 0.5·wᵀΣw s.t. w≥0, bᵀlog w≥0 → 归一后的 ERC 权重（D4）。"""
```

新增两个优化器类（与既有类同签名）：

```python
class KellyOptimizer(BaseOptimizer):          # method="kelly"
class MaxSharpeOptimizer(BaseOptimizer):      # method="max_sharpe"
```

`build_optimizer` map 追加：`"kelly": KellyOptimizer`、`"max_sharpe": MaxSharpeOptimizer`。

### 4.3 引擎接口（`core/engine_v2.py`）

```python
# __init__ 追加
self._industry_cap_warned: bool = False

# 新私有方法
def _industry_tags(self, date: pd.Timestamp) -> Optional[pd.Series]:
    """行业标签；整体缺失/日期缺失 → 一次性 warning 并返回 None。"""
```

插入点（[engine L1507](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1507) 后 / L1508 前，见 §6）。

---

## 5. 算法规格

### 5.1 ERC 快速路径 + 凸回退（D2/D3/D4）

```
输入：cov (n×n, PSD), cfg, selected
1. if any(diag(cov) <= 0 or not finite):            # D3 diag 预判（新增防护，拦病态凸解）
       zero_vol = True; weights = 1/n               # 权重与现状一致（等权），不进入循环与回退
2. elif cfg.risk_budget is not None:
       b = _risk_budget_vector(selected, cfg.risk_budget)
       weights = _solve_risk_budget_convex(cov, b); reason = "risk_budget"
3. else:
       weights = 1/n; converged = False; reason = None
       for _ in range(max_iter):                    # ← 与现状逐字一致
           σ² = wᵀΣw; if σ²<=0 or not finite: zero_vol=True; break   # 保持末次 w（现状语义）
           rc = w * (Σw)/sqrt(σ²); if any(rc<=0): reason="negative_rc"; break
           t = rc.mean(); w_new = w * t / rc
           if max|w_new−w| < tol: weights=w_new; converged=True; break
           weights = w_new
       if not zero_vol and reason is None and not converged: reason = "max_iter"
       if not zero_vol and reason is None:          # 收敛后质量闸门
           pct = w*(Σw)/σ²; if max|pct−1/n| > 1e-3: reason="rc_mismatch"
       if reason: weights = _solve_risk_budget_convex(cov, 1/n)
4. weights /= weights.sum()（有限且 >0 时）
5. applied = _apply_constraints(Series(weights, selected), feas)   # 与现状一致
6. message = "zero_vol" | f"erc_fallback:{reason}" | ""
   warning_kind = "zero_vol" | "erc_fallback" | None
```

- `_solve_risk_budget_convex`：`cp.Variable(n)`；`cp.Minimize(0.5*quad_form(w, Σ))`；约束 `w>=0`、`sum(multiply(b, log(w))) >= 0`；status ∈ {OPTIMAL, OPTIMAL_INACCURATE} 且值有限，否则 `RuntimeError`；负值截断后归一。
- 快速路径**不改一行表达式**（含 `target=rc.mean()`），保证 E7 零漂移。

### 5.2 风险预算归一（D7）

```
raw=None → 均匀 1/n
extra = raw.keys − selected → warning 丢弃
hit = raw ∩ selected
hit 为空 → warning + 均匀 1/n（不中断回测）
total = Σ hit.values
total > 1+tol → ValueError
missing = selected − hit
  missing 非空: remain = 1−total; remain<=0 → ValueError; 均分 remain
  missing 为空: |total−1|>tol → ValueError
归一后任一 b_i<=0 或非有限 → ValueError
b /= b.sum()
```

### 5.3 矩阵凯利（D8/D9）

```
selected = _select(scores); n; feas = _precheck(...)
empty → _empty_result; upper → _upper_result
returns is None → ValueError("凯利优化需要收益率数据")
μ = returns[selected].mean(); Σ = _cov_for(selected, returns, cov_matrix)
_solve_mean_variance(μ, Σ, cfg, selected, "kelly", feas=feas,
                     risk_aversion=1.0/cfg.kelly.fraction)
```

- `δ = 1/fraction`；`fraction=1` → 与 MVO（δ=1）逐位同解；`fraction=0.5` → δ=2。
- 与 `SizingConfig.method="kelly"`（对角近似）层次不同：**组合层 = 矩阵式；sizing 层 = 对角缩放**，docstring 双处声明（sizing 侧不改代码，仅在 Kelly 类 docstring 中说明）。

### 5.4 max_sharpe（D10/D11）

```
feas: empty → _empty_result; upper → _upper_result
returns is None → ValueError("max_sharpe 需要收益率数据")
μ = returns[selected].mean(); rf = cfg.max_sharpe.risk_free_rate
max(μ) <= rf → ValueError（与 pypfopt A1 L244-L247 同口径）
Σ = _cov_for(...)
y,k = cp.Variable(n), cp.Variable()
min quad_form(y, Σ)
s.t. (μ−rf)@y == 1; sum(y) == k; k >= 0;
     y >= cfg.min_weight*k; y <= cfg.max_weight*k
status 非最优 / k<=0 / 非有限 → RuntimeError
w = round(y.value/k.value, 16) + 0.0      # 对齐 pypfopt L292 反变换
```

### 5.5 行业上限严格投影（D12-D16）

```
输入：weights（全组合，可能含期货）、industry（当日标签 Series）、cap、max_weight

stocks = [c for c in weights.index if c in industry.index]      # 期货不在其中 → 固定
若 stocks 为空 → 原样返回（applied=False）
raw = weights.loc[stocks].astype(float)
非有限 / budget=Σraw <= 0 → warning + 原样返回
labels = industry.reindex(stocks)
unclassified = labels.isna() | (labels == 0)                    # D14
groups = 有序唯一标签（排除 unclassified）
before = {g: Σ raw[g]}；max_before = max(before.values)（无组→0）
若 max_before <= cap + 1e-9 → 原样返回（applied=False）        # D16 逐位不变
容量 = len(groups)*cap + n_unclassified*max_weight
若 budget > 容量 + 1e-9 或 budget > len(stocks)*max_weight + 1e-9
    → InfeasibleConstraintError（含 budget/capacity/cap/n_groups/n_unclassified）
w = cp.Variable(len(stocks))
min sum_squares(w − raw.values)
s.t. sum(w) == budget; w >= 0; w <= max_weight; 每组 sum(w[mask_g]) <= cap
status INFEASIBLE* → InfeasibleConstraintError；其它非最优 → RuntimeError
out = weights.copy(); out.loc[stocks] = clip(w.value, 0, max_weight)   # 期货逐位不变
after = {...}; L1 = Σ|w−raw|
返回 IndustryCapResult(applied=True, ...)
```

---

## 6. 引擎接线（D12/D15/D20）

插入位置：[engine_v2.py L1507](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1507)（股票负权截断）之后、[L1508 `build_target_positions`](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1508-L1517) 之前——即**所有**权重变换（optimizer → sizing → overlay → 股票截断）之后、整手落地之前。

```python
        # P-046c B4d：行业上限（引擎级严格投影；期货/现金不受影响）
        industry_cap = self.cfg.optimizer.industry_max_weight
        if industry_cap is not None:
            industry_tags = self._industry_tags(date)
            if industry_tags is not None:
                try:
                    projection = project_industry_cap(
                        target_weights, industry_tags,
                        cap=industry_cap, max_weight=self.cfg.optimizer.max_weight,
                    )
                except InfeasibleConstraintError as exc:
                    self._diagnostics.record(date, "rebalance", exc)
                    self._emit(EventType.ERROR, {...行业上限投影不可行...})
                    logger.error("行业上限投影不可行: %s", exc)
                    return
                target_weights = projection.weights
                if projection.applied:
                    logger.info(
                        "行业上限投影: groups=%d unclassified=%d max_group %.4f→%.4f L1=%.4f",
                        projection.n_groups, projection.n_unclassified,
                        projection.max_group_before, projection.max_group_after,
                        projection.l1_deviation,
                    )
```

- 导入追加：`from core.portfolio import InfeasibleConstraintError, project_industry_cap`。
- 诊断映射改为常量表（保持 `zero_vol` 行为逐字不变）：

```python
_WARNING_ERROR_TYPES = {"zero_vol": "ZeroVariance", "erc_fallback": "RiskParityFallback"}
# error_type=_WARNING_ERROR_TYPES.get(result.warning_kind, "InfeasibleConstraints")
```

- `_industry_tags`：`table = getattr(self.dm, "industry", None)`；`None` 或 `date not in table.index` → 一次性 warning（`_industry_cap_warned`）+ 返回 `None`。
- 语义声明（docstring）：行业上限为**后投影**（与 P-046b D12 HRP 箱体后投影同构），不宣称 in-solver 最优；期货 sleeve 与现金残差不受影响；整手取整后组和可轻微超 cap（与 `max_weight` 同性质，不计违反）。

---

## 7. 不变式 I1-I12

| ID | 不变式 | 验证 |
|---|---|---|
| I1 | 默认 `equal_weight` 与 golden **22 零重录**；`industry_max_weight=None` 路径零行为变更 | 全量 + golden |
| I2 | 负相关两资产（σ=[0.2,0.3], ρ=−0.9）返回 `[0.6,0.4]`（±1e-4），RC 各 0.5（±1e-3），`message` 非空且 `warning_kind="erc_fallback"` | 新用例 |
| I3 | 五资产随机 SPD（seed=1）ERC RC 各 0.2（±1e-3），权重非等权 | 新用例 |
| I4 | 预算 ERC：RC 比例与 `b` 误差 <1e-3；`b` 归一、非负、逐项 >0 | 新用例 + E2 |
| I5 | Kelly：`w≥−1e-12`、`Σw=1±1e-8`、无 NaN；**内部解**（闭式 w>0 构型）与 `w=Σ⁻¹(μ−ν1)/(2λ)` 差 <1e-8（**精化**：`Σw=1` 恒活跃，原「Σ⁻¹μ 归一 <1e-10」不成立） | 新用例 |
| I6 | MaxSharpe：E4 参考解 <1e-6、Sharpe <1e-6；**内部解**（对角 Σ）与 `w∝Σ⁻¹(μ−rf)` 差 <1e-8 | 新用例 |
| I7 | 投影：各组和 ≤cap+1e-9；`Σw=budget±1e-9`；**期货列逐位不变**；未触发时返回原 Series 逐位不变 | 新用例 |
| I8 | 换手/TE 零实现，PROGRESS 有 **P-046d** 行 + 触发条件（零悬空） | 台账核对 |
| I9 | 零新运行时依赖；pypfopt/skfolio 不 import、不进 CI | `git status` + grep |
| I10 | 门禁不劣化（§9 全数字） | 全量 |
| I11 | `config_v2.py` / `sizing.py` / `target_positions.py` / `interfaces.py` 零 diff | `git diff --stat` |
| I12 | **正常路径**（diag 全正、σ_p²>0）诊断语义逐字保留（`upper` / `empty` / `lower` 消息与字段、快速路径空 message）；diag 退化为新增防护（D3），无既有断言破坏 | 既有用例全绿 |

---

## 8. 测试设计（39 例冻结）

### 8.1 `tests/test_p046c_erc_budget.py`（14 例）

| # | 用例 | 构型/断言 |
|---|---|---|
| A1 | `test_erc_negative_corr_two_asset_recovers_inverse_vol` | Σ=[[0.04,−0.054],[−0.054,0.09]]；`[0.6,0.4]`±1e-4；RC≈0.5±1e-3 |
| A2 | `test_erc_negative_corr_emits_fallback_diagnostic` | 同上；`message.startswith("erc_fallback:")`、`warning_kind=="erc_fallback"` |
| A3 | `test_erc_five_asset_random_spd_rc_equal` | §5.1 共享 S5（§8.4）；RC 各 0.2±1e-3；`max|w−0.2|>0.1` |
| A4 | `test_erc_equicorr_fast_path_zero_drift` | E7 等相关（vols 0.2-0.4, ρ=0.3）；`message==""`、`warning_kind is None`；权重≈`[0.282638,0.226110,0.188425,0.161507,0.141319]`±1e-5 |
| A5 | `test_erc_sample_cov_fast_path_rc_equal` | E7 样本 20A（seed=2026）；RC 各 0.05±1e-3；message 空 |
| A6 | `test_erc_max_iter_exhausted_falls_back` | **等相关构型**（vols=0.2-0.4、ρ=0.3；等权 RC 全正、一步 max\|Δw\|=0.1415）+ `risk_parity_max_iter=1, tol=1e-12`；message `erc_fallback:max_iter`；RC 仍 0.2±1e-3（**F-S9-P046c-1**：原 S5 构型等权起点 RC 含负分量 −0.0064，条件②先于③触发，Step 9 改用等相关构型隔离③） |
| A7 | `test_erc_partial_zero_variance_keeps_equal_weight_zero_vol` | Σ=diag(0.04,0.09,0.0)，max=1.0（σ_p²=0.0144>0，现状静默等权）；D3 diag 预判 → 权重 `[1/3]*3`（与现状一致）+ `warning_kind=="zero_vol"`（新增防护诊断，C19 证无既有断言） |
| A8 | `test_erc_budget_matches_target_rc` | S5 + b=[0.4,0.3,0.15,0.1,0.05]；RC≈b±1e-3 |
| A9 | `test_erc_budget_extra_keys_dropped` | b 含未知代码；caplog 有 warning；结果正常 |
| A10 | `test_erc_budget_missing_filled_with_remainder` | 5A 指定 2 只和 0.7；其余各 0.1；指定者 RC≈0.4/0.3±1e-3 |
| A11 | `test_erc_budget_all_covered_must_sum_one` | 全覆盖且和 0.9 → `ValueError` |
| A12 | `test_erc_budget_negative_rejected` | 负预算 → `ValueError`（配置期） |
| A13 | `test_erc_budget_no_match_uniform_fallback` | 预算键全部不在选中集；warning；RC 各 0.2 |
| A14 | `test_optimizer_config_rejects_bad_industry_cap_and_budget_method` | cap=0/1.5 → `ValueError`；`method="equal_weight"`+risk_budget → `ValueError` |

### 8.2 `tests/test_p046c_kelly_sharpe.py`（15 例）

| # | 用例 | 构型/断言 |
|---|---|---|
| B1 | `test_kelly_50a_long_only_invariants` | E3 50A（seed=7）；w≥−1e-12、Σw=1±1e-8、无 NaN |
| B2 | `test_kelly_box_free_matches_closed_form` | 对角 Σ=diag(linspace(0.2,0.4,5)²)、μ=[0.08..0.03]、fraction=0.5、max=1.0；闭环 <1e-8 |
| B3 | `test_kelly_fraction_maps_to_risk_aversion` | fraction=1 与 `_solve_mean_variance(δ=1)` 逐位；fraction=0.5 与 δ=2 逐位 |
| B4 | `test_kelly_config_fraction_bounds` | 0 / 1.5 → `ValueError` |
| B5 | `test_kelly_upper_result` | n=5、max=0.1 → 各 0.1、cash 0.5、`infeasible_kind="upper"` |
| B6 | `test_kelly_empty_result` | 空 scores → `infeasible_kind="empty"` |
| B7 | `test_kelly_requires_returns` | returns=None + cov 注入 → `ValueError` |
| B8 | `test_kelly_factory` | `build_optimizer(optimizer).__class__ is KellyOptimizer` |
| B9 | `test_max_sharpe_matches_pypfopt_reference` | S5+μ=[0.08..0.03]+rf=0.02+max=0.6 → `[0.164545,0.478144,0.345451,0.0,0.011859]`±1e-6；Sharpe 1.385755±1e-6 |
| B10 | `test_max_sharpe_box_free_closed_form` | 对角 Σ+rf=0.02+max=1.0 → 闭式 `[0.555741,0.237116,0.123498,0.060489,0.023156]`±1e-8 |
| B11 | `test_max_sharpe_rejects_no_excess_return` | max(μ)≤rf → `ValueError` |
| B12 | `test_max_sharpe_upper_result` | n=5、max=0.1 → upper 语义 |
| B13 | `test_max_sharpe_requires_returns` | returns=None → `ValueError` |
| B14 | `test_max_sharpe_config_rf_validation` | `risk_free_rate=nan` → `ValueError` |
| B15 | `test_max_sharpe_factory` | 工厂类名 + 未知 method 报错集含新键 |

### 8.3 `tests/test_p046c_industry_cap.py`（10 例）

| # | 用例 | 构型/断言 |
|---|---|---|
| C1 | `test_projection_n100_hits_cap_exactly` | E8 N=100/G=10/cap=0.12（seed=400）：max_group=0.12±1e-9、Σ=1±1e-9、L2=0.1522±1e-3 |
| C2 | `test_projection_n500_hits_cap_exactly` | E8 N=500/G=20/cap=0.08（seed=800）：0.08±1e-9、L2=0.1244±1e-3 |
| C3 | `test_projection_noop_when_caps_binding_free` | 10 组等权 0.1、cap=0.2 → 返回逐位相等、`applied is False` |
| C4 | `test_projection_infeasible_raises` | 2 组 cap=0.2、budget=1 → `InfeasibleConstraintError` |
| C5 | `test_projection_unclassified_stocks_excluded` | 1 只标签 0、1 只 NaN → `n_unclassified==2`；组和 ≤cap；Σ 保持 |
| C6 | `test_projection_empty_and_zero_budget_noop` | 空 Series / 全零预算 → 原样、`applied is False` |
| C7 | `test_projection_preserves_non_stock_columns` | weights 含期货 `IF0001`（不在 industry 索引）→ 其值逐位不变 |
| C8 | `test_projection_enforces_max_weight` | `max_weight=0.3`、w0 含 0.5 单票（行业超限）→ 解后 max≤0.3+1e-9（个股上限在投影内生效） |
| C9 | `test_engine_applies_industry_cap` | 4 股/3 行业（A:2, B:1, C:1）、`max_weight=0.5`、cap=0.4、equal_weight；monkeypatch `build_target_positions` 捕获权重 → A 组和 0.4±1e-9、B/C 各 0.3（Step 4 探针证实解 [0.2,0.2,0.3,0.3]） |
| C10 | `test_engine_industry_cap_none_is_noop` | 同构型（`max_weight=0.5`）`industry_max_weight=None` → 捕获权重 `[0.25]*4` |

### 8.4 固定构型（测试常量）

```
S5（A1/A3/A6/A8、B9）：rng=default_rng(1)；m~N(0,1)^(5,5)；
    S = diag(linspace(0.15,0.35,5)) @ (m@m.T/5 + 0.01I) @ diag(...)
μ5 = [0.08, 0.06, 0.05, 0.04, 0.03]；rf=0.02；max_weight=0.6（B9）
E7 等相关：vols=linspace(0.2,0.4,5)、ρ=0.3；scores=arange(5,0,-1)
E7 样本 20A：rng=default_rng(2026)；X = 0.7·N(0,0.01)^(60,1) + N(0,0.008)^(60,20)；scores=linspace(3,1,20)
E3 50A：rng=default_rng(7)；S50=m@m.T/50+1e-4 I；μ50~N(0.05,0.02)^50
对角构型（B2/B10）：Σ=diag(linspace(0.2,0.4,5)²)，μ5 同上
```

> 说明：E4 的 μ 在 RESEARCH §15 未单独登记，本轮以 μ5 复算得到 pypfopt 参考解与 Sharpe **逐位命中**（1.3857552798）——该构型由此确证并在此固化。

---

## 9. 门禁目标（Step 9 冻结）

| 指标 | 基线 @`3495683` | P-046c 目标 |
|---|---|---|
| pytest collect | 1464 | **1503**（+39） |
| pytest 全量 | 1463 passed + 1 skipped | **1502 passed + 1 skipped** |
| `-k p046` | 78 | **117**（+39） |
| `-k golden` | 22（零重录） | **22（零重录）** |
| `-k p054` | 120 | **120** |
| mypy | 160 files · 0 | **160 · 0**（无新 core 文件） |
| black `--check .` | 322 | **325**（+3 测试文件） |
| AST `except Exception` | core 外 22 / core 30 | **22 / 30** |
| `lint-imports` | 3 kept | **3 kept** |
| `uv lock --check` | 0 | **0** |
| 文件计数 | 158 · 51 · 19 · 13 | **161 · 51 · 19 · 13** |

门禁命令沿用 P-046b Step 10 口径，不新增脚本。

---

## 10. 性能与守卫

| 路径 | 参考读数 | 说明 |
|---|---|---|
| ERC 快速路径 | 原实现同量级 | 逐字保留，无退化 |
| ERC 凸回退 | N=50 0.02-0.14s / N=200 0.13-0.35s / N=500 0.91-0.96s（E2；单次测量、机器相关） | 仅负 RC / 不收敛 / RC 失配 / 预算路径触发 |
| Kelly / MaxSharpe | 与 MVO 同一 QP 量级（N=50 亚秒） | opt-in |
| 行业投影 | N=100 0.015s / N=500 0.021-0.022s（E8 复算） | opt-in；每日至多一次 |
| 不设 SLO | P-046b D18 同判 | 不入 CI 计时断言 |

---

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| R1 回退改变负相关组合的 RP 输出 | 有意为之（P1 修复）；诊断 `erc_fallback:*`；A1-A3 覆盖 |
| R2 投影在 cap 绑定时改变权重 | 严格投影最小 L2 偏离；`applied/L1` 日志；未绑定逐位不变 |
| R3 行业标签 0 语义（`data.py` 缺失填充） | D14 明确为未分类 + 每次 warning 计数；不伪造行业 |
| R4 投影内 `w≤max_weight` 与 weights 直出策略冲突 | 仅 cap 绑定触发；不可行时显式 config 错误；文档声明 |
| R5 pypfopt 参考值随求解器版本漂移 | 容差 1e-6（E4 复算 1e-17 量级余量）；CI 不 import |
| R6 预算键随选股变化失效 | 无交集 → 等风险 + warning（不中断）；覆盖不全 → 剩余均分 |

---

## 12. 未决项登记

**（无）**。U-P046c-1..12 全部关闭；Step 2/2b 遗留观察处置：

| 观察 | 处置 |
|---|---|
| O-U7-1 行业缺失 / 期货 sleeve / 现金残差语义 | D13/D14/D15 + §5.5 显式规则 |
| O-U9-1 校验与旧配置兼容 | D17（`0<x≤1`；不采纳 config_v2 反向规则） |
| F-R2-5 kelly/budget 命名消歧 | D6（`risk_budget`）+ D8 docstring 层次声明 |
| I4 正权重闭式限定 | I5 精化为「内部解闭式」；E4 实证闭式含负权重 → 箱体绑定时只对拍数值解 |
| O-R2b-1 pydantic warning 时机 | 本批 U9=A 不消费 deprecated 语义，无需动作 |

---

## 13. 对 Step 5 IMPL / Step 7 CHECKLIST 的输入

1. **改动面**：`core/config.py`（2 配置类 + 4 字段 + 校验）、`core/portfolio.py`（2 优化器 + 3 私有函数 + 1 dataclass + 1 kwarg + map 2 键）、`core/engine_v2.py`（1 属性 + 1 助手 + 1 插入块 + 1 映射表）、`tests/` 3 新文件。
2. **红→绿顺序**：配置契约 → ERC 回退 → 预算 → Kelly → MaxSharpe → 投影 → 引擎接线；每步先红后绿。
3. **CHECKLIST 组**：A 配置契约 / B ERC / C 预算 / D Kelly / E MaxSharpe / F 投影 / G 引擎接线 / H 不变式与零漂移 / I 门禁 / J 文档与台账。
4. **Step 4 复审重点**：D2 零漂移是否真逐字；D4 为何无 `Σw=1`（KKT 推导）；D10 约束缩放是否与 pypfopt 等价；D14 的 0/NaN 语义；D17 与 config_v2 分叉的理由；§9 门禁算术（1464+39 / 78+39 / 322+3）。

---

## 14. 状态链

- **2026-11-23**：Step 3 DESIGN 落盘（本文）——U-P046c-1..12 全部关闭；D1-D22 / I1-I12；39 例测试冻结；门禁目标 1503 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13；零代码变更 / 未提交。
- **2026-11-23**：**Step 4 异构复审 PASS**（[REVIEW_p046c_step3_design](REVIEW_p046c_step3_design.md)，GLM-5.3-Flash ≠ 作者）——D4 KKT / D10 pypfopt 等价 / D14 fill_value=0 语义 / 门禁算术（含 mypy CI 范围不含 tests）/ 39 例编号独立成立；**新证据**：部分零方差凸回退病态解（Σ=diag(0.04,0.09,0) → w₃=2.69e6）；**1 P2 + 2 P3 当轮全修**：F-4-1（D2/D3/I12 零漂移范围限定为正常路径权重；diag 退化为新增防护，权重一致+诊断新增）、F-4-2（伪代码 zero_vol 误判 max_iter → 加 `not zero_vol` 前置）、F-4-3（C8/C9/C10 补显式 max_weight：0.3/0.5/0.5，探针证实解 [0.2,0.2,0.3,0.3]）+ 3 观察（O-4-1 联测例转 IMPL / O-4-2 零预算从严 / O-4-3 容差注记）；门禁目标维持不变；本文修订已落字；零代码变更 / 未提交。
- **下一步**：Step 5 IMPL（DESIGN §13 红→绿顺序；O-4-1 联测例登记于 IMPL）。
- **2026-11-23**：**Step 5 IMPL 落盘**（[IMPL_p046c_f2_closeout](IMPL_p046c_f2_closeout.md)）——T1-T9 / 接口 14 项 + 回退点 / 源码锚点 A27-A36 / 低效排除 12 行 / 39 例映射 / 门禁命令；派生 **F-5-1**（D4 强化：`Σw=1` 与 `bᵀlog w≥0` 对 n≥2 不可行，探针实证）、**F-5-2**（Kelly δ=2/f 换算）、**F-5-3**（riskfolio 数值对拍降级：缺 `arch`）；跨实现读数 pypfopt max_sharpe **5.55e-17**；零代码变更 / 未提交。
- **下一步**：Step 6 IMPL 异构复审（reviewer ≠ DeepSeek-V4.1-Flash）。
- **2026-11-23**：**Step 6 复审 PASS + Step 7 CHECKLIST 落盘**——[REVIEW_p046c_step5_impl](REVIEW_p046c_step5_impl.md)：锚点 16/16、门禁算术全过、3 P3 全修；[CHECKLIST_p046c_f2_closeout](CHECKLIST_p046c_f2_closeout.md)：**80 项**（A 8 / B 9 / C 7 / D 7 / E 7 / F 9 / G 8 / H 10 / I 9 / J 6），实测列 0 预填（77 `[待 Step 9]` + 2 `[待 Step 8]` + 1 `[待 Step 10]`）；门禁目标冻结 1503 / 1502+1 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13。
- **2026-11-23**：**Step 8 一致性复审 PASS**——机械校验器 v3 **124/124**（[CHECKLIST_p046c_f2_closeout §14](CHECKLIST_p046c_f2_closeout.md)）；初跑 v1 117/124 定性为 4 校验器正则/切分误报 + 2 文档 P3 当轮修（IMPL §3.3 F-4-2 标签注释 / CK N7 措辞）+ 1 跟随；复跑 v2 122/124 再修 1 用例引用缺口（CK A1/A3/A4 补用例 B4/A14）；J1/J5 回填 ✅；reviewer **GLM-5.3-Flash** ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash。
- **2026-11-23**：**Step 9 TDD PASS**——红态 2 收集错误 → 绿态 **39 passed**（14/15/10）；门禁全命中 **1503（1502+1）/ 117 / 22 / 120 / 160·0 / 325 / 161·51·19·13 / 22·30 / 3 kept / 0**；派生 **F-S9-P046c-1**（§8.1 A6 构型改等相关，S5 等权起点负 RC 使②先于③触发）；O-4-1 探针：sizing/overlay 腿 clip≤1 实测不放大、外部权重 0.4→0.3 压回；实测列 79 ✅ + J6；详见 [CHECKLIST_p046c_f2_closeout §15](CHECKLIST_p046c_f2_closeout.md)。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046c_f2_closeout §16](CHECKLIST_p046c_f2_closeout.md)，GLM-5.3-Flash ≠ 实施者）——门禁独立重放 **10/10 全绿**；代码 vs DESIGN 对齐 D1-D22 分组核验全过；探针独立重写重放 **8/8**（R1a 逐位复现 RESEARCH E1 原值）；**0 P0-P2 + 1 观察 O-R5-P046c-1**。
- **2026-11-23**：**用户授权提交 + 批次关闭**——`6ac07eb`（16 files +4011/−27）+ CI run `45187900624` 四 job 全绿；CHECKLIST **80/80 ✅**；本文 D1-D22 全部落地并经 Step 10 对齐核验。
- **P-046c 批次关闭（Step 1-10 全通过）**。
