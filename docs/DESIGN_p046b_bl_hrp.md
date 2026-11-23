# DESIGN：P-046b BL / HRP 优化器（组合优化扩展第二批）

> **批次**: P-046b · **Step 3 DESIGN** · 日期 2026-11-23
> **判档**: **T1**（`core/portfolio.py` / `core/config.py` / `core/engine_v2.py` 诊断分流 + 2 个新测试文件 + 1 个基准脚本；BL/HRP 均 opt-in，默认 `equal_weight` 与 golden 22 预期零漂移）
> **上游**: [RESEARCH_p046b_bl_hrp](RESEARCH_p046b_bl_hrp.md)（U-P046b-1..17 / G-P046b-1..17 / A1-A19）；[REVIEW_p046b_step2](REVIEW_p046b_step2_research.md)（PASS + F-R1..F-R7）；[RESEARCH_p046 §14.8](RESEARCH_p046_portfolio_optimization.md#L528-L558)（HRP 三细节）
> **代码证据时点**: HEAD `8f8b912`（P-055 关闭；代码面干净）
> **基座**: DeepSeek-V4.1-Flash（Step 4 复审须 reviewer ≠ author）
> **本文性质**: 设计方案，**零代码变更**；Step 4 复审通过后进入 Step 5 IMPL。

---

## 0. 本文定位

| 本文件已定 | 留给后续 |
|---|---|
| U-P046b-1..17 的裁决（§1） | Step 4 设计复审（本文不自评 PASS） |
| 架构决策 D1-D20（§3） | Step 5 IMPL 的逐处代码 |
| 配置/接口签名（§4） | Step 6 IMPL 复审 |
| BL 算法规格（§5）/ HRP 算法规格（§6） | Step 7 CHECKLIST |
| 引擎与工厂接线（§7） | Step 9 TDD 落码 |
| 遗留四项修复规格（§8） | |
| 测试设计（§10）/ 性能（§11）/ 门禁目标（§12） | |

---

## 1. 上游裁决摘要（U-P046b-1..17 全部关闭）

| U | 裁决 | 落点 |
|---|---|---|
| U-P046b-1 | **D3 扩展约束延后**（D3-B）；本批只做 BL/HRP | D1/D17 |
| U-P046b-2 | BL 先验：**等权默认 + 零先验可选 + 显式 dict**；市值先验延后（需引擎上下文） | D4 |
| U-P046b-3 | BL 观点：**显式绝对观点** + 无观点降级；因子派生观点延后 | D5 |
| U-P046b-4 | 后验协方差：**沿用原 Σ**（不替换为 posterior Σ） | D7 |
| U-P046b-5 | Ω：**默认 `diag(τPΣPᵀ)`**；Idzorek 置信度延后；τ 默认 0.05 | D6 |
| U-P046b-6 | pypfopt **不进 CI**、不加 `[research]` extra；A8 用 synthetic 闭式 | D20 |
| U-P046b-7 | HRP 退化：1 资产=1.0；簇内全零方差=簇内等权；**diag 全零=优化器层等权 1/N 特判 + `zero_vol` 诊断（F-4-1）** | D11 |
| U-P046b-8 | `_apply_constraints_legacy` **保留**（三条件未满足） | D19 |
| U-P046b-9 | `zero_vol` 用 **`warning_kind` 字段** + 引擎映射 `ZeroVariance` | D15 |
| U-P046b-10 | `estimate_cov(codes=...)`：**交集 + warning**（最小破坏） | D16 |
| U-P046b-11 | AST 唯一口径 = P-029 五目录 + `cli.py`（22） | §8.4 |
| U-P046b-12 | BL 落地：**组合（纯估计器 + 共享 MVO 求解函数）**，不继承 | D3 |
| U-P046b-13 | 工厂：**R1（`build_optimizer` 加分支）**；Registry 统一另立批 | D14 |
| U-P046b-14 | `OptimizationContext` **延后**；引擎 3 参签名不变 | D17 |
| U-P046b-15 | 性能：**报告 + `HRPConfig.max_assets` 守卫**；不设 SLO | D18 |
| U-P046b-16 | HRP 约束：**后投影近似**；严格约束/D3 归后续 | D12 |
| U-P046b-17 | 多阶段 DP：**独立 policy 层**，本批不实现；优化器保持单期纯函数 | D17 |

---

## 2. 范围与非目标

### 2.1 范围

1. `BlackLittermanOptimizer` + `black_litterman_posterior` 纯函数。
2. `HRPOptimizer` + 三纯函数（距离/叶序/递归二分）。
3. `OptimizerConfig` 嵌套 `BLConfig` / `HRPConfig`。
4. `build_optimizer` 新分支：`black_litterman` / `bl` / `hrp`。
5. `OptimizationResult.warning_kind` + 引擎 `ZeroVariance` 分流。
6. 遗留四项：`zero_vol` message、`estimate_cov` warning、`codes` 语义、AST 口径。
7. 基准脚本 `scripts/p046b_bench_optimizers.py`（手动，不进 CI）。
8. 2 个新测试文件 + 3 个既有测试文件增例。

### 2.2 非目标（明确不做）

| # | 不做 | 依据 |
|---|---|---|
| N1 | D3 行业/换手/跟踪误差约束 | U-P046b-1；D3-B |
| N2 | 矩阵式凯利 / 非等风险预算 | P-046c |
| N3 | max_sharpe / robust BL / Idzorek 置信度 | 后续批次 |
| N4 | 因子分数派生观点 | U-P046b-3；V2 延后 |
| N5 | 市值先验 + `OptimizationContext` | U-P046b-14；需引擎输入通道 |
| N6 | 多阶段 DP / `PortfolioPolicy` | U-P046b-17 |
| N7 | Registry 统一重构 | U-P046b-13 |
| N8 | 新运行时依赖 / pypfopt 入 CI | Q7 / U-P046b-6 |
| N9 | 删除 `_apply_constraints_legacy` | U-P046b-8 |
| N10 | 修改 `config_v2.py`（FROZEN/TD-2） | P-046a C-4 |

---

## 3. 架构决策 D1-D20

| ID | 决策 | 被拒替代与代价 | 依据 |
|---|---|---|---|
| **D1** | 本批只落 BL + HRP；D3/L3/max_sharpe/context/policy 不做 | 纳入 D3 会使改动面扩至引擎上下文/行业映射，scope 失控 | U1 |
| **D2** | BL 后验为**纯函数** `black_litterman_posterior(cov, prior, views, *, tau, omega)` | 把公式写进优化器类 → 无法独立测试/复用 | 松耦合 P1 |
| **D3** | BL 优化器**不继承** `MeanVarianceOptimizer`；抽出模块级 `_solve_mean_variance(μ, Σ, cfg, selected, method)`，MVO 与 BL 共用 | 继承 → 复制 cvxpy 逻辑、绑定 MVO；委托类 → 需改接口传 μ | U12 / A10 skfolio |
| **D4** | 先验：`prior="equal"`（默认）→ `Π = δΣ(1/N)`，`δ=cfg.risk_aversion`；`"zero"` → 0；`"explicit"` → `prior_returns` 必须覆盖选中资产 | 市值先验需 `dm.mktcap` 通道（延后）；硬编码 δ=25/1.2 不符合本仓口径 | U2 / A7 |
| **D5** | 观点：`views: dict[asset, float]` **绝对观点**；仅保留选中资产，缺失资产的视图 **warning 后丢弃**；无观点时后验=先验 | 相对观点需 P 矩阵非单位行，本批不做；视图缺失资产 fail-loud 会因选股变动频繁失败 | U3 |
| **D6** | Ω 默认 `diag(τ·PΣPᵀ)`；`tau=0.05`（0,1]；**不暴露** `view_confidences`；自定义 Ω 仅纯函数参数（测试/未来） | Idzorek 置信度需额外方法与参数，延后 | U5 / A3 |
| **D7** | 后验只替换 μ；**Σ 沿用原协方差**送入 MVO | posterior Σ 会引入第二套协方差口径，与 P-046a SSOT 冲突 | U4 / A7 |
| **D8** | BL 退化：K=0 返回先验；`PΣPᵀ` 任一对角 ≤0/非有限 → **`ValueError`**（fail-loud） | 抖动/静默跳过会把配置错误伪装成正常结果 | I5 |
| **D9** | HRP 拆 `correlation_distance` / `quasi_diagonal_order` / `recursive_bisection` 三纯函数；距离用 `pdist`；`linkage("single")`；`leaves_list` | 单类大函数难复用；`(N,N,N)` 广播 O(N³) 内存 | A4/A17 |
| **D10** | 递归二分按论文：保序二分、逆方差簇权重、`α=1−V₁/(V₁+V₂)`、`w×=α/(1−α)` | 等权二分不是 HRP；需外部锚 | A4 §14.8 |
| **D11** | HRP 退化：N=1→1.0；**diag 全零→优化器层等权 1/N 特判 + `warning_kind="zero_vol"`（F-4-1，α 链 0.5^depth 非均权，须特判）**；簇内全零方差→cluster_var 内部等权；部分零方差→**先过滤零方差资产，在有效子域跑 HRP 后回填 0 权重（F-S9-P046b-1）**；两簇方差和≤0→α=0.5 | 逆方差除零会产生 inf/NaN；全零 cov 是 `estimate_cov` 有效行<2 的真实生产产物 | I8 / F-4-1 |
| **D12** | HRP 约束：先出原始权重，再走既有 `_apply_constraints` **后投影**；`HRPConfig.max_assets` 默认 2000，超过则 `ValueError` | 约束风险平价是另一套凸模型，超出本批；无守卫会 OOM | U15/U16 |
| **D13** | 配置嵌套：`OptimizerConfig.bl: BLConfig` / `.hrp: HRPConfig`，各自 `__post_init__` 校验；`config_v2` 零改动 | 平铺 10+ 字段 → god object；改 `config_v2` 违约 | 松耦合 P3 / F-R1 |
| **D14** | 工厂只改 `build_optimizer` map：`black_litterman`/`bl`/`hrp`；Registry 继续休眠 | 本批接 Registry 会引入循环导入/初始化顺序风险 | U13 / A16 |
| **D15** | `OptimizationResult` 末尾新增 `warning_kind: Optional[str]=None`；零方差分支置 `"zero_vol"`；引擎映射 `error_type="ZeroVariance"` | 用 message 字符串前缀分流脆弱；新增独立异常类会改变控制流 | U9 / F-S10-P046-1 |
| **D16** | `estimate_cov`：有效行 <2 补 warning；`codes` 缺失列 warning 后丢弃（交集），docstring 同步 | KeyError 会破坏潜在调用方；reindex 补 0 与现实现不符 | U10 / F-S10-P046-3 |
| **D17** | 不引入 `OptimizationContext`；引擎 3 参调用/`IOptimizer` 2 参 Protocol 不变；D3/市值先验/DP 均延后 | 现在引入会让 4 个优化器 + 测试桩全改，收益不足 | U14/U17 |
| **D18** | 性能：新增 `scripts/p046b_bench_optimizers.py`（固定种子、无断言、不进 CI）；`HRPConfig.max_assets` 守卫；**不设 SLO** | 性能测试入 CI 会抖动判红；不记录则无法回归 | U15 / A-P046b-9 |
| **D19** | `_apply_constraints_legacy` 保留；仅 AC-C-01a 对拍使用 | 删除需三条件同时满足，本批不满足 | U8 / P-046a |
| **D20** | 零新运行时依赖；pypfopt 不装、不进 CI；A8 用 synthetic 闭式/手算 | Q7「仅对拍」；加 extra 会动锁与 CI | U6 / Q7 |

### 3.1 不变式 I1-I12

| ID | 不变式 | 验证 |
|---|---|---|
| I1 | BL 无观点时后验 = 先验（逐位） | 闭式 |
| I2 | BL 单绝对观点时，**隐含权重** `(δΣ)⁻¹post` 仅观点资产与先验权重不同；后验收益可经协方差传导到其他资产（F-R2 口径） | 闭式 + 随机 Σ |
| I3 | 默认 `Ω=τPΣPᵀ` 时 τ 消去（0.05 vs 0.5 结果一致） | 闭式 |
| I4 | `Ω→0` 时观点资产后验→Q；`Ω→∞` 时→先验 | 极限 |
| I5 | BL 后验有限、无 NaN；零观点方差 fail-loud；K=0 不进入矩阵求解 | 闭式 |
| I6 | HRP 距离链 `d` / `d̃` 与论文 Example 1-2 逐位一致（`atol=1e-4`） | golden |
| I7 | HRP 权重非负、`Σw=1`（可行域）、在 `[min,max]` 内 | 参数化 |
| I8 | HRP N=1 返回 1.0；零方差/全零不产生 NaN，走显式分支 | 退化用例 |
| I9 | 默认 `equal_weight` 与 golden 22 零漂移 | 全量 + golden |
| I10 | `build_optimizer` 未知 method 行为不变；`IOptimizer` 2 参 Protocol 不变 | 读码 + 测试 |
| I11 | BL/HRP 均 opt-in；不改变引擎 3 参调用签名 | 读码 + 测试 |
| I12 | mypy/black/AST/lint-imports/uv lock 不劣化 | 门禁 |

---

## 4. 配置与接口设计

### 4.1 `core/config.py`：嵌套配置

```python
@dataclass
class BLConfig:
    """Black-Litterman 方法级配置（仅 method 为 BL 时读取）。"""

    prior: str = "equal"  # "equal" | "zero" | "explicit"
    prior_returns: dict[str, float] | None = None  # prior="explicit" 时必填
    views: dict[str, float] | None = None  # 绝对观点 {asset: 期望超额收益}
    tau: float = 0.05  # (0, 1]

    def __post_init__(self) -> None:
        if self.prior not in {"equal", "zero", "explicit"}:
            raise ValueError(f"BLConfig.prior 非法: {self.prior!r}")
        if not (0.0 < self.tau <= 1.0):
            raise ValueError(f"BLConfig.tau 必须在 (0,1]: {self.tau}")
        if self.prior == "explicit" and not self.prior_returns:
            raise ValueError("BLConfig.prior='explicit' 时必须提供 prior_returns")
        for name, mapping in (("prior_returns", self.prior_returns), ("views", self.views)):
            if mapping is None:
                continue
            if not all(isinstance(k, str) for k in mapping):
                raise ValueError(f"BLConfig.{name} 的键必须为资产代码字符串")
            if not all(math.isfinite(float(v)) for v in mapping.values()):
                raise ValueError(f"BLConfig.{name} 的值必须为有限数")


@dataclass
class HRPConfig:
    """HRP 方法级配置（仅 method 为 hrp 时读取）。"""

    linkage: str = "single"  # P-046b 仅支持 single
    max_assets: int = 2000  # 距离矩阵守卫

    def __post_init__(self) -> None:
        if self.linkage != "single":
            raise ValueError(f"HRPConfig.linkage P-046b 仅支持 'single': {self.linkage!r}")
        if self.max_assets < 1:
            raise ValueError(f"HRPConfig.max_assets 必须 >= 1: {self.max_assets}")
```

`OptimizerConfig` 末尾追加：

```python
    bl: BLConfig = field(default_factory=BLConfig)
    hrp: HRPConfig = field(default_factory=HRPConfig)
```

- `__post_init__` 原四校验**不变**；嵌套配置自行校验。
- `config_v2.py` 零改动（FROZEN/TD-2，F-R1）。
- `math` **未**在 `core/config.py` 导入（Step 4 复审定案，F-4-3）：Step 5 须补 `config.py` 的 `import math`；`portfolio.py` 须补 `import math` 与 `typing.Mapping`/`Sequence`（§4.3/§5.1 使用）。

### 4.2 `core/portfolio.py`：结果字段

```python
@dataclass(frozen=True)
class OptimizationResult:
    ...
    message: str = ""
    warning_kind: Optional[str] = None  # None | "zero_vol"
```

- 新字段置于末尾且带默认值，既有位置参数构造（`portfolio.py` 内 9 处）**不改**。
- 仅 `RiskParityOptimizer` 零方差分支与 `HRPOptimizer` diag 全零特判分支（§6.4，F-4-1）置 `"zero_vol"`；其他分支保持 `None`。

### 4.3 公开纯函数

```python
def black_litterman_posterior(
    cov: pd.DataFrame,
    prior: pd.Series,
    views: Mapping[str, float],
    *,
    tau: float = 0.05,
    omega: Optional[Sequence[float]] = None,
) -> pd.Series:
    """绝对观点 BL 后验收益（纯函数，Woodbury 形式）。

    - views 为空 → 返回 prior（按 cov.index 对齐）；
    - omega 为空 → diag(tau * diag(P Σ Pᵀ))；
    - 未知资产/零观点方差/非有限 → ValueError；
    - 不修改输入，不持有状态。
    """


def correlation_distance(cov: pd.DataFrame) -> pd.DataFrame:
    """两级距离的第一级 d_ij = sqrt(0.5*(1-ρ_ij))，返回与 cov 同标签的方阵。"""


def quasi_diagonal_order(dist: pd.DataFrame) -> list[int]:
    """pdist → linkage(single) → leaves_list，返回叶序位置列表。

    N<2 不调用 linkage（scipy 对空/单点距离矩阵抛 ``ValueError``，F-4-6）：
    N=1 → ``[0]``；N=0 → 空表。
    """


def recursive_bisection(cov: pd.DataFrame, order: Sequence[int]) -> pd.Series:
    """按 paper §14.8 的保序二分返回原始权重（未施加箱体约束），索引为 cov.index。"""
```

### 4.4 优化器类

```python
class BlackLittermanOptimizer(BaseOptimizer):
    """BL 后验 + 共享 MVO 求解（组合，不继承 MeanVarianceOptimizer）。"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult: ...


class HRPOptimizer(BaseOptimizer):
    """HRP：距离 → 叶序 → 递归二分 → 既有箱体投影。"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult: ...
```

### 4.5 共享 MVO 求解函数（关键重构）

```python
def _solve_mean_variance(
    expected_returns: pd.Series,
    cov: pd.DataFrame,
    cfg: OptimizerConfig,
    selected: pd.Index,
    method: str,
) -> OptimizationResult:
    """可行域判定 + cvxpy MVO；method 用于结果标识（mean_variance / black_litterman）。"""
```

- `MeanVarianceOptimizer.optimize_with_diagnostics` 改为：算 μ → 调 `_solve_mean_variance(..., "mean_variance")`；行为与现有逐位一致。
- `BlackLittermanOptimizer`：算 posterior μ → 调 `_solve_mean_variance(..., "black_litterman")`。
- 不改变 `BaseOptimizer.optimize` / `IOptimizer` 2 参签名。

---

## 5. BL 算法规格

### 5.1 先验构造（优化器内）

```python
def _bl_prior(cov: pd.DataFrame, cfg: OptimizerConfig) -> pd.Series:
    n = len(cov)
    if cfg.bl.prior == "zero":
        return pd.Series(0.0, index=cov.index)
    if cfg.bl.prior == "explicit":
        prior = pd.Series(cfg.bl.prior_returns, dtype=float).reindex(cov.index)
        if prior.isna().any():
            missing = list(prior.index[prior.isna()])
            raise ValueError(f"BL 显式先验缺少资产: {missing}")
        return prior
    # equal
    delta = float(cfg.risk_aversion)
    if not math.isfinite(delta) or delta <= 0.0:
        raise ValueError(f"BL 先验需要 risk_aversion > 0: {delta}")
    w_eq = np.full(n, 1.0 / n)
    return pd.Series(delta * cov.to_numpy(dtype=float) @ w_eq, index=cov.index)
```

- `prior="equal"` 是**等权市场组合代理**，不是市值先验；市值先验归未来 `PriorProvider` + context。
- δ 复用 `OptimizerConfig.risk_aversion`（默认 1.0）；不硬编码 25/1.2。
- `prior="explicit"` 时 `prior_returns` **多出的**非选中资产：`logger.warning` 后丢弃（与 §5.2 观点过滤对称，F-4-4）。

### 5.2 观点过滤

```python
raw_views = cfg.bl.views or {}
views = {k: float(v) for k, v in raw_views.items() if k in selected}
dropped = sorted(set(raw_views) - set(views))
if dropped:
    logger.warning("BL 观点资产未入选，已丢弃: %s", dropped)
```

- 纯函数仍对未知资产 fail-loud；过滤在优化器层完成，避免选股变动导致整日失败。

### 5.3 后验公式（Woodbury）

给定 `P`（K×N，绝对观点每行一个 1）、`Q`（K）、`Ω=diag(ω)`：

```text
post = Π + τ Σ Pᵀ (τ P Σ Pᵀ + Ω)⁻¹ (Q − P Π)
```

实现：

```python
sigma = cov.to_numpy(dtype=float)
pi = prior.reindex(cov.index).to_numpy(dtype=float)
p = np.zeros((k, n))
q = np.empty(k)
for i, (asset, value) in enumerate(views.items()):
    p[i, positions[asset]] = 1.0
    q[i] = value
if omega is None:
    var = np.diag(p @ sigma @ p.T)
    if np.any(~np.isfinite(var)) or np.any(var <= 0.0):
        raise ValueError("BL 观点组合方差为零/非有限，无法构造 Ω")
    omega_vec = tau * var
else:
    omega_vec = np.asarray(omega, dtype=float)
    if omega_vec.shape != (k,) or np.any(~np.isfinite(omega_vec)) or np.any(omega_vec <= 0.0):
        raise ValueError("BL omega 必须为 K 个正有限数")
a = tau * p @ sigma @ p.T + np.diag(omega_vec)
post = pi + tau * sigma @ p.T @ np.linalg.solve(a, q - p @ pi)
if not np.all(np.isfinite(post)):
    raise ValueError("BL 后验产生非有限值")
return pd.Series(post, index=cov.index)
```

- **禁止** `np.linalg.inv(sigma)`；只解 K×K。
- K=0 直接返回 `prior`，不进入 `solve`。
- `omega` 参数仅用于测试/未来，不暴露到 `BLConfig`。

### 5.4 单位与诊断

- `views` / `prior_returns` 单位 = **与 `returns_data` 同周期**的期望收益（日频回测即日频）；不自动年化。
- 结果 `method="black_litterman"`；`n_selected/max/min/cash_residual` 沿用 MVO 语义。
- 若上层约束不可行（`n×max_weight<1`），由 `_solve_mean_variance` 返回 `infeasible_kind="upper"`，BL 透传。
- 后验 μ 不写入 `message`（避免日志膨胀）；纯函数可由测试直接断言。

---

## 6. HRP 算法规格

### 6.1 第一级距离

```python
vol = np.sqrt(np.clip(np.diag(sigma), 0.0, None))
denom = np.outer(vol, vol)
corr = np.divide(sigma, denom, out=np.zeros_like(sigma), where=denom > 0.0)
np.fill_diagonal(corr, 1.0)
corr = np.clip(corr, -1.0, 1.0)
dist = np.sqrt(0.5 * (1.0 - corr))
```

- 零方差资产：与其他资产 corr=0，distance=`sqrt(0.5)`；对角 1 → 0。
- 返回 `pd.DataFrame(dist, index=cov.index, columns=cov.columns)`。

### 6.2 第二级距离 + 叶序

```python
condensed = pdist(dist.to_numpy(dtype=float), metric="euclidean")
z = linkage(condensed, method="single")
order = [int(i) for i in leaves_list(z)]
```

- 论文 `d̃` = 对 D 的**列/行向量**取欧氏距离；`pdist(D)` 正是行向量两两欧氏距离。
- N=1 → `order=[0]`；N=0 → 空列表。
- **禁止** `(N,N,N)` 广播；`pdist` 为 O(N²) 内存。

### 6.3 递归二分

```text
w = ones(N)
def split(lo, hi):
    if hi - lo <= 1: return
    mid = lo + (hi - lo) // 2
    v1 = cluster_var(cov_ord[lo:mid, lo:mid])
    v2 = cluster_var(cov_ord[mid:hi, mid:hi])
    alpha = 0.5 if (v1 + v2) <= 0 else 1.0 - v1 / (v1 + v2)
    w[lo:mid] *= alpha
    w[mid:hi] *= 1.0 - alpha
    split(lo, mid); split(mid, hi)
```

`cluster_var`：

```text
diag = np.diag(sub)
inv = np.divide(1.0, diag, out=np.zeros_like(diag), where=diag > 0.0)  # 避免 1/0 RuntimeWarning（F-4-5）
if inv.sum() <= 0: w = ones/len
else: w = inv / inv.sum()
v = w @ sub @ w
return 0.0 if (not finite or v <= 0) else v
```

- 与论文 §14.8 细节 3 一致：逆方差簇权重、`α` 拆分、保序二分。
- 返回 `pd.Series(weights_original_order, index=cov.index)`；`weights_original_order[order] = w`。

### 6.4 退化与约束

| 情形 | 行为 |
|---|---|
| N=0 | `_empty_result("hrp")` |
| N=1 | 权重 `[1.0]` |
| **diag 全零**（`estimate_cov` 有效行 <2 的真实产物，F-4-1） | **优化器层特判：等权 1/N**（跳过聚类），置 `warning_kind="zero_vol"` + `message="zero_vol"`（与 RiskParity 零方差回退同构，引擎 → `ZeroVariance`） |
| 簇内全零方差（部分资产的 diag 全零） | `cluster_var` 内部逆方差权重向量取等权（α 拆分链不变）；对应资产终权重 0 |
| 部分零方差 | **先按 `diag>0` 且有限过滤，在有效子域跑 HRP，再回填 0 权重**（F-S9-P046b-1；实测 diag(0,.09,.16) → `[0.0, 0.64, 0.36]`，Σw=1、无 NaN；若直接在含零方差资产的 Σ 上跑 α 链会得 `[0.64, 0.0, 0.36]`，与「零权重视为 0」语义不符） |
| 两簇方差和 ≤0 | `α=0.5`（注意：α 链的叶权重为 0.5^depth，**非**全局均权——故 diag 全零必须在优化器层特判，F-4-1） |
| `n > cfg.hrp.max_assets` | `ValueError("HRP 资产数 ... 超过 max_assets ...")` |
| **upper（n×max<1）** | `infeasible_kind="upper"` + `cash_residual` + message（RiskParity L551-567 同构模板，method="hrp"），F-4-2 |
| **lower（n×min>1）** | `_precheck` 抛 `InfeasibleConstraintError` **原样向上**（不捕获；引擎按异常类归类 `config`），F-4-2 |
| 约束 | 原始权重走 `_apply_constraints` **后投影**；上限型只截断留现金 |
| `linkage != "single"` | 配置期 `ValueError`（P-046b 仅 single） |

- HRP 的约束是**后投影近似**，会改变层次/风险平价性质；模块 docstring 与 DESIGN 必须显式声明，不得宣称支持 D3。
- `max_assets` 守卫在距离矩阵之前触发，避免 OOM。

---

## 7. 引擎与工厂接线

### 7.1 `build_optimizer`

```python
optimizer_map = {
    ...,
    "black_litterman": BlackLittermanOptimizer,
    "bl": BlackLittermanOptimizer,
    "hrp": HRPOptimizer,
}
```

- 未知 method 仍抛 `ValueError`，消息含合法值集。
- 不调用 `PluginRegistry`；Registry 统一另立批（D14）。
- `black_litterman`/`bl` 同义；`hrp` 单一。

### 7.2 引擎 `zero_vol` 分流（唯一引擎改动）

```python
error_type = (
    "ZeroVariance"
    if result.warning_kind == "zero_vol"
    else "InfeasibleConstraints"
)
```

- 触发条件仍为 `result.infeasible_kind is not None or result.message`。
- `category` 保持 `"optimizer"`；`retryable=False`。
- 不改 `_optimize_with_diagnostics` 签名（D17）。

### 7.3 不做

- 不引入 `OptimizationContext`；不传 `market_weights/current_weights/benchmark/industry`。
- 不做 D3 约束、不做多阶段 policy、不改 `IOptimizer` Protocol。

---

## 8. 遗留四项修复规格

### 8.1 F-S10-P046-1：`zero_vol`

`RiskParityOptimizer` 零方差分支：

```python
zero_vol = False
for _ in range(...):
    portfolio_variance = float(weights @ cov.values @ weights)
    if not np.isfinite(portfolio_variance) or portfolio_variance <= 0.0:
        zero_vol = True
        break
    ...
# 归一后
message = "zero_vol" if zero_vol else ""
warning_kind = "zero_vol" if zero_vol else None
```

- 行为不变（等权、不崩、无 NaN）；仅新增诊断字段。
- 引擎映射见 §7.2；新增测试见 §10。

### 8.2 F-S10-P046-2：`estimate_cov` 退化 warning

```python
valid = ~np.isnan(x).any(axis=1)
n_valid = int(valid.sum())
if n_valid < 2:
    logger.warning(
        "estimate_cov: 有效行 < 2（%d），以零填充并沿用 method=%s；结果为退化协方差",
        n_valid,
        method,
    )
    x_use = np.nan_to_num(x, nan=0.0)
else:
    x_use = x[valid]
```

- 输出不变（仍走选定 method + `psd_fix`）；仅补日志。
- 测试用 `caplog` 断言 warning 文本。

### 8.3 F-S10-P046-3：`codes` 语义

```python
if codes is not None:
    missing = [c for c in codes if c not in returns.columns]
    if missing:
        logger.warning("estimate_cov: codes 缺失列已丢弃: %s", missing)
    returns = returns.loc[:, [c for c in codes if c in returns.columns]]
```

- docstring 改为「缺失码 warning 后丢弃（交集）」，不再写 reindex 补 0。
- 当前零生产调用方，风险低；新增测试锁定语义。

### 8.4 F-S9-P046-2：AST 口径

- 唯一基线命令（P-029，可重放）：

```powershell
$py -c "import ast,pathlib;r=pathlib.Path('.');s=[p for d in ['agents','filter','scripts','batch_backtest','strategy_evaluation'] for p in (r/d).rglob('*.py')]+[r/'cli.py'];print(sum(1 for p in s if p.exists() for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='Exception'))"
```

- 预期 **22**；本批不新增裸 `except Exception`。
- 全仓「core 外」口径另表登记，不与 22 混用。

---

## 9. 兼容性与回退

| 面 | 保证 | 回退 |
|---|---|---|
| `OptimizationResult` | 新字段在末尾 + 默认值；位置参数构造不变 | 删除 `warning_kind` + 引擎映射（单点） |
| `OptimizerConfig` | 嵌套字段有默认值；`config_v2` 零改动 | 删除 `bl/hrp` 字段（不影响旧配置） |
| `MeanVarianceOptimizer` | 抽 `_solve_mean_variance` 后行为逐位一致；golden 22 | 保留旧实现为私有方法一个提交内可切回 |
| `build_optimizer` | 仅新增分支；未知 method 行为不变 | 删除 3 个 map 项 |
| `estimate_cov` | 仅 warning/docstring；数值不变 | 回退日志行 |
| 引擎 | 仅 `error_type` 映射；签名不变 | 回退三元表达式 |
| 依赖 | 零新增；pypfopt 不装 | 无 |

---

## 10. 测试设计

### 10.1 新文件 `tests/test_p046b_bl.py`（11 例）

| # | 用例 | 断言要点 |
|---|---|---|
| 1 | `test_bl_no_views_equals_prior` | 空 views → 后验==prior（`1e-12`） |
| 2 | `test_bl_single_view_closed_form` | 手算 `post = π + τΣe_i/(τΣ_ii+Ω)(Q−π_i)`，`Ω=τΣ_ii` |
| 3 | `test_bl_single_view_implied_weights_only_view_asset` | `(δΣ)⁻¹post` 非观点资产与先验权重差 `<1e-10`；观点资产差 `>1e-8`（F-R2） |
| 4 | `test_bl_tau_cancels_with_default_omega` | τ=0.05 vs 0.5 后验一致 |
| 5 | `test_bl_omega_limits` | Ω→0 观点资产→Q；Ω→∞→prior |
| 6 | `test_bl_zero_view_variance_raises` | 零方差资产观点 → `ValueError` |
| 7 | `test_bl_explicit_prior_missing_asset_raises` | 显式先验缺选中资产 → `ValueError` |
| 8 | `test_bl_views_missing_asset_filtered` | 未入选观点 warning + 丢弃，不崩 |
| 9 | `test_bl_optimizer_not_mean_variance_subclass` | `isinstance(opt, BaseOptimizer)` 且 **not** `isinstance(opt, MeanVarianceOptimizer)` |
| 10 | `test_bl_upper_infeasible_passthrough` | `n×max<1` → `infeasible_kind="upper"` + cash_residual |
| 11 | `test_build_optimizer_bl_aliases` | `black_litterman` / `bl` 均返回 BL 实例；未知 method 仍 `ValueError` |

### 10.2 新文件 `tests/test_p046b_hrp.py`（9 例）

| # | 用例 | 断言要点 |
|---|---|---|
| 1 | `test_hrp_distance_matches_paper_example` | 论文 `d` / `d̃` 逐位（`atol=1e-4`） |
| 2 | `test_hrp_single_linkage_leaves_order` | `linkage(single)` 合并表 + `leaves=[2,0,1]` |
| 3 | `test_hrp_recursive_bisection_closed_form` | 3 资产按测试内独立复算 α；Σw=1 |
| 4 | `test_hrp_single_asset` | N=1 → `[1.0]` |
| 5 | `test_hrp_zero_variance_no_nan` | diag 全零 → 优化器特判**等权 1/N** + `warning_kind="zero_vol"`；部分零方差 → **先过滤子域 → 有效子域 HRP → 回填 0**（F-S9-P046b-1），零方差资产权重 0；均无 NaN、Σw=1（F-4-1） |
| 6 | `test_hrp_max_assets_guard` | `max_assets=2` + 3 资产 → `ValueError` |
| 7 | `test_hrp_box_constraints` | `max_weight` 生效；n×max<1 → `infeasible_kind="upper"` + message 非空 + `cash_residual>0`；n×min>1 → 抛 `InfeasibleConstraintError`（F-4-2） |
| 8 | `test_hrp_method_name` | `result.method == "hrp"` |
| 9 | `test_build_optimizer_hrp` | map 分支 + 未知 method 不变 |

### 10.3 既有测试增例（3 例）

| 文件 | 用例 | 断言 |
|---|---|---|
| `tests/test_p046_cov.py` | `test_estimate_cov_degenerate_warns` | 有效行<2 → `caplog` 含 warning；输出仍无 NaN |
| `tests/test_p046_cov.py` | `test_estimate_cov_codes_missing_warns` | 缺失 code 被丢弃 + warning；返回列=交集 |
| `tests/test_p046_engine.py` | `test_zero_vol_records_zero_variance` | 假优化器返回 `warning_kind="zero_vol"` → 诊断 `error_type="ZeroVariance"` |

### 10.4 不改既有断言

- `test_p046_constraints.py` 的 `METHODS` 列表**不加入** BL/HRP（避免参数化语义混淆）；新增用例独立文件。
- `golden 22` 零重录；`-k p054` 120 零回归。
- 不新增 skip/xfail；pypfopt 不参与测试。

---

## 11. 性能与高维设计

| 项 | 设计 |
|---|---|
| BL 后验 | Woodbury：`O(N²K + K³)`；禁止 `inv(Σ)`；K=0 短路 |
| BL 观点 | 绝对观点 K 通常远小于 N；K=N 时退化 O(N³)，文档声明 |
| HRP 距离 | `pdist` + `squareform`；O(N²) 内存；禁止 `(N,N,N)` 广播 |
| HRP 聚类 | `linkage(single)` 官方实现 O(N²)；`leaves_list` 线性 |
| 递归二分 | 每层 `O(N²)` 子矩阵切片，总 `O(N² log N)` 量级；N≤2000 守卫 |
| 全维协方差 | **不改**引擎 SSOT；既有瓶颈登记；未来「先选股后估协方差」独立批（LW 子集化会改数值，A18） |
| 基准 | `scripts/p046b_bench_optimizers.py`：seed 固定、N=50/200/500、T=60；打印 cov/HRP/BL 耗时与内存估算；**无断言、不进 CI**；脚本位于 CI mypy 路径（`tests.yml` L46 含 `scripts`）与 `black --check .` 范围 → **须通过 mypy 0 error 与 black**（F-4-7） |
| SLO | **不设**；仅报告（与 R8/U-P055-4 口径一致） |

---

## 12. 门禁目标（Step 7 冻结）

| 项 | 基线（P-055 关闭） | P-046b 目标 |
|---|---|---|
| pytest 全量 | 1440 passed / 1 skipped | **≥1463**（+23：BL 11 + HRP 9 + 既有 3；collect **1464**） |
| `-k p046` | 55 | **≥78** |
| `-k golden` | 22 | **22 零重录** |
| mypy | 159 files / 0 | **160**（+`scripts/p046b_bench_optimizers.py`）/ 0 |
| black | 319 | **322**（+2 测试 +1 脚本） |
| `tests/*.py` | 156 | **158** |
| `core/*.py` | 51 | **51**（不新增 core 模块） |
| `live/**/*.py` | 19 | **19** |
| `services/*.py` | 13 | **13** |
| AST `except Exception` | core 外 22（P-029）/ core 30 | **22 / 30**（不新增裸 except） |
| `lint-imports` | 3 kept | **3 kept** |
| `uv lock --check` | 0 | **0**（零新依赖） |
| `-k p054` | 120 | **120** |

> 若 Step 9 实际 collect 数偏移，按 RULE-1 登记 `F-S9-P046b-*`，Step 7 目标可机械修正；不得改既有断言。

---

## 13. Step 4 复审包（给 reviewer 的最小核对清单）

1. **U1-U17 关闭一致性**：§1 的 17 项裁决是否与 D1-D20/§4-§8 一一对应，有无悬空项。
2. **BL 数学**：Woodbury 公式、`Ω=diag(τPΣPᵀ)`、K=0、零方差、τ 消去、单观点“隐含权重仅观点资产”（F-R2）是否自洽；`prior="equal"` 的 `δΣ(1/N)` 是否明确区别于市值先验。
3. **BL 组合**：`_solve_mean_variance` 抽取后 MeanVariance 行为是否逐位不变；BL 不继承 MVO；结果 `method` 正确。
4. **HRP 论文一致性**：两级距离、single linkage、保序二分 α、逆方差簇权重；`pdist` 用法；N=1/零方差/全零退化。
5. **配置**：嵌套 `BLConfig/HRPConfig` 校验；`config_v2` 零改动；旧配置默认值兼容。
6. **诊断**：`warning_kind` 字段位置/默认值；引擎 `ZeroVariance` 分流；既有 `InfeasibleConstraints` 路径不变。
7. **遗留四项**：`estimate_cov` warning/codes 语义；AST P-029 口径 22；`_apply_constraints_legacy` 保留。
8. **范围控制**：无 D3/context/Registry/多阶段/因子观点夹带；无新依赖。
9. **性能**：Woodbury/`pdist`/`max_assets` 守卫；基准脚本不设 SLO、不进 CI。
10. **可测性**：§10 用例是否每条都可机械断言；是否触碰既有断言/golden。

---

## 14. 状态链

- **2026-11-23**：Step 1 调研（[RESEARCH_p046b](RESEARCH_p046b_bl_hrp.md)）+ 架构/性能补充（§14）+ 外部锚 A1-A19。
- **2026-11-23**：Step 2 异构复审 PASS（[REVIEW_p046b_step2](REVIEW_p046b_step2_research.md)）；F-R1..F-R7 已回写。
- **2026-11-23**：**Step 3 DESIGN 落盘（本文）**——U-P046b-1..17 全部关闭；D1-D20；I1-I12；BL/HRP 算法规格；配置/接口签名；遗留四项修复；测试映射；门禁目标。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 4 异构复审 PASS**（[REVIEW_p046b_step3_design](REVIEW_p046b_step3_design.md)，GLM-5.3-Flash ≠ 作者）——2 P2 + 6 P3 当轮全修并已落字本文：F-4-1 diag 全零等权特判 + `zero_vol`（§1/§4.2/D11/§6.4/§10.2#5）、F-4-2 HRP `_precheck` 三分支（§6.4/§10.2#7）、F-4-3 `import math` 定案（§4.1）、F-4-4 explicit 先验多余资产 warning（§5.1）、F-4-5 `np.divide`（§6.3）、F-4-6 叶序 N<2 守卫（§4.3）、F-4-7 bench 脚本 mypy/black 义务（§11）。门禁目标 §12 **维持不变**。
- **2026-11-23**：**Step 5 IMPL**（[IMPL_p046b_bl_hrp](IMPL_p046b_bl_hrp.md)）——T1-T12；A20-A26 源码锚点；对拍边界 F-5-3；F-5-1..F-5-4。
- **2026-11-23**：**Step 6 IMPL 复审 PASS**（[REVIEW_p046b_step5_impl](REVIEW_p046b_step5_impl.md)）——16/16 锚点机械核验；4 P3 全修。
- **2026-11-23**：**Step 7 CHECKLIST**（[CHECKLIST_p046b_bl_hrp](CHECKLIST_p046b_bl_hrp.md)）——70 项 DoR/DoD；门禁目标冻结（与本文 §12 一致）。
- **2026-11-23**：**Step 8 一致性复审 PASS**（[CHECKLIST_p046b §12](CHECKLIST_p046b_bl_hrp.md)，GLM-5.3-Flash ≠ 作者）——机械校验器 78/78；D1-D20→T1-T12→CHECKLIST 无悬空；H1 回填 ✅。
- **2026-11-23**：**Step 9 TDD PASS**——红态 2 收集错误（`ImportError: BLConfig/HRPConfig`）→ 绿态全量 **1463 passed + 1 skipped**（collect 1464）/ `-k p046` **78** / golden **22** / `-k p054` **120** / mypy **160·0** / black **322** / AST **22·30** / `lint-imports` **3 kept** / `uv lock` **0** / 文件计数 **158·51·19·13**。**F-S9-P046b-1（P3）**：HRP 部分零方差改为「先过滤子域 → 有效子域 HRP → 回填 0」，实测 `[0,0.64,0.36]`（旧 α 链 `[0.64,0,0.36]` 会让零方差资产得满权重）；已回写 D11/§6.4 与 IMPL §3.7；门禁零漂移。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046b §14](CHECKLIST_p046b_bl_hrp.md)，审计基座 GLM-5.3-Flash ≠ 作者）——Phase 0-4 全过；门禁独立重放全绿；数值探针 6/6（BL Woodbury ≡ 显式逆矩阵 2.78e-17）；**0 P0-P2 + 1 观察 O-R5-P046b-1**（upper+全零组合语义差异，与 F-6-4/upper 早退设计一致，不改码）。
- **H5 已执行并批次关闭（2026-11-23）**：提交 `f272638` + CI run `45163412591` 四 job 全绿；CHECKLIST 70/70。**P-046b 批次关闭（Step 1-10 全通过）**。
