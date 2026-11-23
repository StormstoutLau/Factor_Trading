# IMPL：P-046b BL / HRP 优化器（Step 5 实施文档）

> **批次**: P-046b · **Step 5 实施文档** · 日期 2026-11-23
> **上游**: [DESIGN_p046b_bl_hrp](DESIGN_p046b_bl_hrp.md)（D1-D20 / I1-I12）+ [REVIEW_p046b_step3_design](REVIEW_p046b_step3_design.md)（F-4-1..F-4-8 已回填）
> **代码基线**: HEAD `8f8b912`；pytest collect **1441**（1440 passed + 1 skipped）/ `-k p046` **55** / golden **22** / mypy **159·0** / black **319** / AST **22·30**
> **作者**: DeepSeek-V4.1-Flash（Step 6 复审须 reviewer ≠ author）
> **性质**: 实施指南——任务拆解、接口签名、回退点、代码骨架、插入锚点（行号 @`8f8b912`，改动后失效）、红→绿计划、门禁命令；**不含**已完成代码
> **外部取证**: 本步新增源码级锚点 **A20-A26**（§4；PyPI 指定版本 wheel 逐字读取）；WebFetch 通道返回空 → 按规范降级到 PyPI 镜像（`uv pip install --no-deps --target`），降级链见 §4.0

---

## 0. 本文定位

| 本文已定 | 留给后续 |
|---|---|
| T1-T12 任务拆解 / 依赖序 / 提交粒度（§1） | Step 6 实施文档复审（本文不自评 PASS） |
| 接口签名 + 回退点（§2，规范硬约束） | Step 7 CHECKLIST 的 DoR/DoD |
| 逐任务代码骨架与插入锚点（§3） | Step 9 TDD 红→绿执行 |
| 社区源码锚点与对拍边界（§4） | Step 10 独立验收 |
| 低效排除表（§5，规范硬约束） | |
| 测试先行计划（§6）/ 门禁命令（§7）/ 风险回退（§8） | |

---

## 1. 实施总览

### 1.1 任务与依赖

| 任务 | 内容 | 依赖 | 规模 | 目标文件 |
|---|---|---|---|---|
| **T1** | 配置：`import math` + `BLConfig` + `HRPConfig` + `OptimizerConfig.bl/hrp` | — | +60 行 | `core/config.py` |
| **T2** | `OptimizationResult.warning_kind` + `RiskParityOptimizer` 零方差置位 | — | +8 行 | `core/portfolio.py` |
| **T3** | `black_litterman_posterior` 纯函数 + `_bl_prior` | T1 | +80 行 | `core/portfolio.py` |
| **T4** | `_solve_mean_variance` / `_upper_result` 抽取 + `MeanVarianceOptimizer` 等价重构 | T2 | +55 / −45 行 | `core/portfolio.py` |
| **T5** | `BlackLittermanOptimizer` | T1/T3/T4 | +55 行 | `core/portfolio.py` |
| **T6** | HRP 三纯函数：`correlation_distance` / `quasi_diagonal_order` / `recursive_bisection` | — | +75 行 | `core/portfolio.py` |
| **T7** | `HRPOptimizer`（含 F-4-1 全零特判、F-4-2 三分支） | T1/T2/T6 | +60 行 | `core/portfolio.py` |
| **T8** | 工厂：`black_litterman` / `bl` / `hrp` | T5/T7 | +3 行 | `core/portfolio.py` |
| **T9** | 引擎 `ZeroVariance` 分流（唯一引擎改动） | T2 | +5 行 | `core/engine_v2.py` |
| **T10** | `estimate_cov` 退化 warning + `codes` 交集 warning | — | +12 行 | `core/portfolio.py` |
| **T11** | 基准脚本（不进 CI，但须过 mypy/black，F-4-7） | T3/T6 | 新文件 ~90 行 | `scripts/p046b_bench_optimizers.py` |
| **T12** | 测试：BL 11 + HRP 9 + 既有 3 | T1-T9 | 新 2 文件 + 改 2 文件 ~430 行 | `tests/*` |

**依赖序**：T1 → T2 → (T3 ∥ T6) → T4 → T5 → T7 → T8 → T9 → T10 → T11 → T12
（T12 按 TDD 应先于实现：见 §6；上表依赖为「实现顺序」而非「编写顺序」）

### 1.2 文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `core/config.py` | 改 | L9 后 `import math`；L269 后插两个 dataclass；L300 后插两个字段 |
| `core/portfolio.py` | 改 | L22 后补 scipy 导入；L62 后加字段；L196 后插纯函数；L300 后插模块级求解器；L434-L575 区段重构 + 两个新类；L610 后工厂 |
| `core/engine_v2.py` | 改 | L1375 `error_type` 三元分流 |
| `scripts/p046b_bench_optimizers.py` | **新建** | 手动基准；无断言 |
| `tests/test_p046b_bl.py` | **新建** | 11 例 |
| `tests/test_p046b_hrp.py` | **新建** | 9 例 |
| `tests/test_p046_cov.py` | 改 | +2 例（退化 warning / codes 交集） |
| `tests/test_p046_engine.py` | 改 | +1 例；`_make_engine` 增可选 `optimizer_instance` 透传（不改既有断言） |

### 1.3 提交粒度

`T1+T2`（配置与诊断字段）→ `T3+T6`（纯函数）→ `T4+T5+T7+T8`（优化器与工厂）→ `T9+T10`（引擎与协方差）→ `T11`（基准）→ `T12`（测试）。
每段独立 `pytest -q` 可跑；**任一段红不得进入下一段**。

---

## 2. 接口签名与回退点（规范硬约束）

| 接口 | 签名（冻结） | 位置 | 回退点 |
|---|---|---|---|
| `BLConfig` | `@dataclass class BLConfig(prior: str="equal", prior_returns: dict[str,float]\|None=None, views: dict[str,float]\|None=None, tau: float=0.05)` | config.py L269 后 | 删除类 + `OptimizerConfig.bl` 字段（默认值无旧配置兼容问题） |
| `HRPConfig` | `@dataclass class HRPConfig(linkage: str="single", max_assets: int=2000)` | 同上 | 同上 |
| `OptimizerConfig.bl/hrp` | `bl: BLConfig = field(default_factory=BLConfig)`；`hrp: HRPConfig = field(default_factory=HRPConfig)` | config.py L300 后 | 删两行字段 |
| `warning_kind` | `warning_kind: Optional[str] = None`（`OptimizationResult` **末尾**） | portfolio.py L62 后 | 删字段 + RiskParity/HRP 置位（3 处）+ 引擎三元回退常量 |
| `black_litterman_posterior` | `(cov: pd.DataFrame, prior: pd.Series, views: Mapping[str,float], *, tau: float=0.05, omega: Optional[Sequence[float]]=None) -> pd.Series` | portfolio.py L196 后 | 删除函数（无调用即死代码） |
| `correlation_distance` | `(cov: pd.DataFrame) -> pd.DataFrame` | 同上 | 删除 |
| `quasi_diagonal_order` | `(dist: pd.DataFrame) -> list[int]` | 同上 | 删除 |
| `recursive_bisection` | `(cov: pd.DataFrame, order: Sequence[int]) -> pd.Series` | 同上 | 删除 |
| `_solve_mean_variance` | `(expected_returns: pd.Series, cov: pd.DataFrame, cfg: OptimizerConfig, selected: pd.Index, method: str, *, feas: Optional[_Feasibility]=None) -> OptimizationResult`（`feas` 为 Step 5 精化，见 §3.4） | portfolio.py L370 前 | MVO 恢复旧内联实现（T4 单提交内可切回） |
| `BlackLittermanOptimizer.optimize_with_diagnostics` | `(factor_scores: pd.Series, returns: Optional[pd.DataFrame]=None, cov_matrix: Optional[pd.DataFrame]=None) -> OptimizationResult` | portfolio.py MVO 后 | 删类 + 工厂两键 |
| `HRPOptimizer.optimize_with_diagnostics` | 同上 | RiskParity 后 | 删类 + 工厂一键 |
| `build_optimizer` | `(config: OptimizerConfig) -> BaseOptimizer`（签名不变，仅 map 增 3 键） | portfolio.py L619 | 删 3 个 map 项 |
| 引擎分流 | `error_type = "ZeroVariance" if result.warning_kind == "zero_vol" else "InfeasibleConstraints"` | engine_v2.py L1375 | 回退常量 |
| `estimate_cov` | `(returns, method="ledoit_wolf", codes=None, psd_fix=True) -> pd.DataFrame`（签名不变） | portfolio.py L199 | 回退 2 处日志行 |

> 以上任一接口删除均**无数据迁移、无锁文件变更、无 golden 重录**。

---

## 3. 逐任务实施规格

### 3.1 T1：配置（`core/config.py`）

**锚点**：导入 L9-L13（`import logging` 起）；`FactorConfig` 结束 L269；`OptimizerConfig` 字段结束 L300。

L9 后补：

```python
import math
```

L269 后（`FactorConfig` 与 `OptimizerConfig` 之间）插入：

```python
@dataclass
class BLConfig:
    """Black-Litterman 方法级配置（仅 method 为 BL 时读取）。"""

    prior: str = "equal"  # "equal" | "zero" | "explicit"
    prior_returns: dict[str, float] | None = None  # prior="explicit" 时必填
    views: dict[str, float] | None = None  # 绝对观点 {asset: 期望收益}
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

L300 后（`cov_shrinkage` 字段之后、`__post_init__` 之前）插入：

```python
    # BL / HRP 方法级配置（P-046b）
    bl: BLConfig = field(default_factory=BLConfig)
    hrp: HRPConfig = field(default_factory=HRPConfig)
```

**约束**：`OptimizerConfig.__post_init__` 四校验不动；`config_v2.py` 零改动。

### 3.2 T2：结果字段 + RiskParity 零方差（`core/portfolio.py`）

**锚点**：`OptimizationResult` L47-L62；RiskParity 循环 L526-L542；尾段 L544-L575。

L62 后加：

```python
    warning_kind: Optional[str] = None  # None | "zero_vol"（P-046b D15）
```

RiskParity 改 3 处：

```python
        zero_vol = False
        weights = np.ones(n) / n  # 初始等权重
        for _ in range(self.cfg.risk_parity_max_iter):
            portfolio_variance = float(weights @ cov.values @ weights)
            if not np.isfinite(portfolio_variance) or portfolio_variance <= 0.0:
                zero_vol = True
                break
            ...
        weights_series = pd.Series(weights, index=selected_stocks)
        applied = self._apply_constraints(weights_series, feas)
        message = "zero_vol" if zero_vol else ""
        warning_kind = "zero_vol" if zero_vol else None
```

upper 分支与正常分支的 `OptimizationResult(...)` 均追加 `warning_kind=warning_kind`，正常分支同时 `message=message`；upper 分支保留原约束 `message`，`zero_vol` 仅由 `warning_kind` 承载（引擎优先分流为 `ZeroVariance`）。
**组合情形（F-6-4）**：cov 全零且 n×max<1 同时发生时，引擎 `error_type="ZeroVariance"` **优先于** `InfeasibleConstraints`（零方差是更根本的失效原因）；`infeasible_kind="upper"` 字段仍保留供诊断。
**注意**：L535-L536 `risk_contrib <= 0` 的 break **不置** `zero_vol`（非零方差退化，既有行为不变）。

### 3.3 T3：BL 纯函数与先验（`core/portfolio.py`）

**锚点**：`estimate_cov` 结束 L228；`BaseOptimizer` 起 L231。纯函数插在 L228 后。

L17-L22 导入区调整：

```python
import math  # 新增（`_bl_prior` 的 isfinite）

from typing import Mapping, Optional, Sequence  # 原 `Optional` 行扩展
from scipy.cluster.hierarchy import leaves_list, linkage  # 新增
from scipy.spatial.distance import pdist  # 新增
```

```python
def _bl_prior(cov: pd.DataFrame, cfg: OptimizerConfig) -> pd.Series:
    n = len(cov)
    if cfg.bl.prior == "zero":
        return pd.Series(0.0, index=cov.index)
    if cfg.bl.prior == "explicit":
        raw = cfg.bl.prior_returns or {}
        extra = sorted(set(raw) - set(cov.index))
        if extra:
            logger.warning("BL 显式先验含未入选资产，已丢弃: %s", extra)  # F-4-4
        prior = pd.Series(raw, dtype=float).reindex(cov.index)
        if prior.isna().any():
            missing = list(prior.index[prior.isna()])
            raise ValueError(f"BL 显式先验缺少资产: {missing}")
        return prior
    delta = float(cfg.risk_aversion)
    if not math.isfinite(delta) or delta <= 0.0:
        raise ValueError(f"BL 先验需要 risk_aversion > 0: {delta}")
    w_eq = np.full(n, 1.0 / n)
    return pd.Series(delta * cov.to_numpy(dtype=float) @ w_eq, index=cov.index)


def black_litterman_posterior(
    cov: pd.DataFrame,
    prior: pd.Series,
    views: Mapping[str, float],
    *,
    tau: float = 0.05,
    omega: Optional[Sequence[float]] = None,
) -> pd.Series:
    """绝对观点 BL 后验收益（Woodbury，纯函数；DESIGN §5.3）。"""
    if not (0.0 < tau <= 1.0):
        raise ValueError(f"BL tau 必须在 (0,1]: {tau}")
    sigma = cov.to_numpy(dtype=float)
    n = len(cov)
    if sigma.shape != (n, n):
        raise ValueError(f"BL cov 必须为方阵: {sigma.shape}")
    pi = prior.reindex(cov.index).to_numpy(dtype=float)
    if not np.all(np.isfinite(pi)):
        raise ValueError("BL prior 缺少 cov 资产或含非有限值")
    if not views:  # K=0：不进入矩阵求解（D8）
        return pd.Series(pi, index=cov.index)
    unknown = sorted(set(views) - set(cov.index))
    if unknown:
        raise ValueError(f"BL 观点含未知资产: {unknown}")
    positions = {a: i for i, a in enumerate(cov.index)}
    k = len(views)
    p = np.zeros((k, n))
    q = np.empty(k)
    for i, (asset, value) in enumerate(views.items()):
        p[i, positions[asset]] = 1.0
        q[i] = float(value)
    if omega is None:
        var = np.diag(p @ sigma @ p.T)
        if np.any(~np.isfinite(var)) or np.any(var <= 0.0):
            raise ValueError("BL 观点组合方差为零/非有限，无法构造 Ω")
        omega_vec = tau * var
    else:
        omega_vec = np.asarray(omega, dtype=float)
        if (
            omega_vec.shape != (k,)
            or np.any(~np.isfinite(omega_vec))
            or np.any(omega_vec <= 0.0)
        ):
            raise ValueError("BL omega 必须为 K 个正有限数")
    a = tau * p @ sigma @ p.T + np.diag(omega_vec)
    post = pi + tau * sigma @ p.T @ np.linalg.solve(a, q - p @ pi)
    if not np.all(np.isfinite(post)):
        raise ValueError("BL 后验产生非有限值")
    return pd.Series(post, index=cov.index)
```

### 3.4 T4：共享 MVO 求解器（`core/portfolio.py`）

**锚点**：`MinVarianceOptimizer` 起 L370；`MeanVarianceOptimizer` L434-L502。

**Step 5 精化（对 DESIGN §4.5 的签名增量）**：新增关键字 `feas: Optional[_Feasibility] = None`。原因：MVO 现有顺序是「先 `_precheck` → upper 早退 → 再算 μ/Σ」；若把可行域判定完全移入求解器，upper + 非法协方差的边界行为会改变（旧路径不触碰 Σ）。传 `feas` 保持**逐位等价**。差异已登记 F-5-1（§9）。

在 `MinVarianceOptimizer` 前（L370 前）插入：

```python
def _upper_result(cfg: OptimizerConfig, selected: pd.Index, method: str) -> OptimizationResult:
    """U1-A 上限型唯一解：各 m + 留现金（与既有三个优化器消息逐字一致）。"""
    n = len(selected)
    weights = pd.Series(cfg.max_weight, index=selected)
    residual = 1.0 - float(weights.sum())
    return OptimizationResult(
        weights,
        method,
        n,
        cfg.max_weight,
        cfg.min_weight,
        infeasible_kind="upper",
        cash_residual=residual,
        message=(
            f"约束不可行(U1-A): method={method}, n={n}, "
            f"max_weight={cfg.max_weight}, min_weight={cfg.min_weight}, "
            f"sum_max={n * cfg.max_weight:.12f} < 1, "
            f"required_max_weight>=1/n={1.0 / n:.12f}, cash_residual={residual:.12f}"
        ),
    )


def _solve_mean_variance(
    expected_returns: pd.Series,
    cov: pd.DataFrame,
    cfg: OptimizerConfig,
    selected: pd.Index,
    method: str,
    *,
    feas: Optional[_Feasibility] = None,
) -> OptimizationResult:
    """可行域判定 + cvxpy MVO（MVO / BL 共用；DESIGN §4.5）。"""
    n = len(selected)
    if feas is None:
        feas = _precheck(n, cfg, method)
    if feas.kind == "empty":
        return OptimizationResult(
            pd.Series(dtype=float),
            method,
            0,
            cfg.max_weight,
            cfg.min_weight,
            infeasible_kind="empty",
            cash_residual=1.0,
            message=f"约束不可行(U1-C): method={method}, n=0（空集）",
        )
    if feas.is_upper:
        return _upper_result(cfg, selected, method)

    w = cp.Variable(n)
    portfolio_return = expected_returns.values @ w
    portfolio_variance = cp.quad_form(w, cov.values)
    objective = cp.Maximize(portfolio_return - cfg.risk_aversion * portfolio_variance)
    constraints = [cp.sum(w) == 1, w >= cfg.min_weight, w <= cfg.max_weight]
    problem = cp.Problem(objective, constraints)
    problem.solve()
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or w.value is None:
        raise RuntimeError(f"均值方差优化失败: solver status={problem.status}")
    weights = pd.Series(w.value, index=selected)
    return OptimizationResult(
        weights,
        method,
        n,
        cfg.max_weight,
        cfg.min_weight,
        cash_residual=max(0.0, 1.0 - float(weights.sum())),
    )
```

`MeanVarianceOptimizer.optimize_with_diagnostics` 改为（L444-L502 整段替换）：

```python
        if returns is None and cov_matrix is None:
            raise ValueError("均值方差优化需要收益率数据或协方差矩阵")
        selected_stocks = self._select(factor_scores)
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "mean_variance")
        if feas.kind == "empty":
            return self._empty_result("mean_variance")
        if feas.is_upper:
            return _upper_result(self.cfg, selected_stocks, "mean_variance")
        if returns is not None:
            expected_returns = returns[selected_stocks].mean()
        else:
            expected_returns = pd.Series(0.0, index=selected_stocks)
        cov = self._cov_for(selected_stocks, returns, cov_matrix)
        return _solve_mean_variance(
            expected_returns, cov, self.cfg, selected_stocks, "mean_variance", feas=feas
        )
```

**等价性判据**：`test_p046_constraints` / `test_p025_day_error_diagnostics` / golden 22 零漂移；消息格式逐字沿用（`_upper_result` 与旧 MVO f-string 同格式）。
**MinVariance 处置（F-6-3）**：`MinVarianceOptimizer` 本批**零改动**（含其 upper 分支内联消息）；`_upper_result` 仅 MVO / BL / HRP 消费——MinVariance 目标函数为纯 min variance（无 μ 项），不共用 `_solve_mean_variance`。

### 3.5 T5：`BlackLittermanOptimizer`

插在 `MeanVarianceOptimizer` 后（L502 后）、`RiskParityOptimizer` 前。

```python
class BlackLittermanOptimizer(BaseOptimizer):
    """BL 后验 + 共享 MVO 求解（组合，不继承 MeanVarianceOptimizer）。"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        if returns is None and cov_matrix is None:
            raise ValueError("Black-Litterman 优化需要收益率数据或协方差矩阵")
        selected = self._select(factor_scores)
        n = len(selected)
        feas = _precheck(n, self.cfg, "black_litterman")
        if feas.kind == "empty":
            return self._empty_result("black_litterman")
        if feas.is_upper:  # upper 早退：不计算 Σ/后验（保持 lazy 语义）
            return _upper_result(self.cfg, selected, "black_litterman")

        cov = self._cov_for(selected, returns, cov_matrix)
        prior = _bl_prior(cov, self.cfg)
        raw = self.cfg.bl.views or {}
        views = {k: float(v) for k, v in raw.items() if k in selected}
        dropped = sorted(set(raw) - set(views))
        if dropped:
            logger.warning("BL 观点资产未入选，已丢弃: %s", dropped)
        posterior = black_litterman_posterior(cov, prior, views, tau=self.cfg.bl.tau)
        return _solve_mean_variance(
            posterior, cov, self.cfg, selected, "black_litterman", feas=feas
        )
```

### 3.6 T6：HRP 三纯函数

插在 BL 纯函数之后（同 L228 后区段）。

```python
def correlation_distance(cov: pd.DataFrame) -> pd.DataFrame:
    """第一级距离 d_ij = sqrt(0.5*(1-ρ_ij))（López de Prado 2016）。"""
    sigma = cov.to_numpy(dtype=float)
    n = len(cov)
    if sigma.shape != (n, n):
        raise ValueError(f"correlation_distance 需要方阵: {sigma.shape}")
    vol = np.sqrt(np.clip(np.diag(sigma), 0.0, None))
    denom = np.outer(vol, vol)
    corr = np.divide(sigma, denom, out=np.zeros_like(sigma), where=denom > 0.0)
    np.fill_diagonal(corr, 1.0)
    corr = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(0.5 * (1.0 - corr))
    return pd.DataFrame(dist, index=cov.index, columns=cov.columns)


def quasi_diagonal_order(dist: pd.DataFrame) -> list[int]:
    """pdist(d) → linkage(single) → leaves_list；N<2 不调用 scipy（F-4-6）。"""
    n = len(dist)
    if n < 2:
        return list(range(n))
    condensed = pdist(dist.to_numpy(dtype=float), metric="euclidean")
    z = linkage(condensed, method="single")
    return [int(i) for i in leaves_list(z)]


def recursive_bisection(cov: pd.DataFrame, order: Sequence[int]) -> pd.Series:
    """保序递归二分（逆方差簇权重 + α=1−V₁/(V₁+V₂)）。"""
    sigma = cov.to_numpy(dtype=float)
    n = len(cov)
    if n != len(order):
        raise ValueError(f"order 长度 {len(order)} 与资产数 {n} 不一致")
    ordered = sigma[np.ix_(list(order), list(order))]
    w = np.ones(n)

    def _cluster_var(idx: list[int]) -> float:
        sub = ordered[np.ix_(idx, idx)]
        diag = np.diag(sub)
        inv = np.divide(1.0, diag, out=np.zeros_like(diag), where=diag > 0.0)  # F-4-5
        if inv.sum() <= 0.0:
            inner = np.full(len(idx), 1.0 / len(idx))
        else:
            inner = inv / inv.sum()
        v = float(inner @ sub @ inner)
        return 0.0 if (not np.isfinite(v) or v <= 0.0) else v

    def _split(lo: int, hi: int) -> None:
        if hi - lo <= 1:
            return
        mid = lo + (hi - lo) // 2
        v1 = _cluster_var(list(range(lo, mid)))
        v2 = _cluster_var(list(range(mid, hi)))
        alpha = 0.5 if (v1 + v2) <= 0.0 else 1.0 - v1 / (v1 + v2)
        w[lo:mid] *= alpha
        w[mid:hi] *= 1.0 - alpha
        _split(lo, mid)
        _split(mid, hi)

    _split(0, n)
    out = np.empty(n)
    out[list(order)] = w
    return pd.Series(out, index=cov.index)
```

### 3.7 T7：`HRPOptimizer`

插在 `RiskParityOptimizer` 后（L575 后）。

```python
class HRPOptimizer(BaseOptimizer):
    """HRP：距离 → 叶序 → 递归二分 → 既有箱体投影（后投影近似，DESIGN D12）。"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        if returns is None and cov_matrix is None:
            raise ValueError("HRP 优化需要收益率数据或协方差矩阵")
        selected = self._select(factor_scores)
        n = len(selected)
        feas = _precheck(n, self.cfg, "hrp")
        if feas.kind == "empty":
            return self._empty_result("hrp")
        if feas.is_upper:
            return _upper_result(self.cfg, selected, "hrp")
        if n > self.cfg.hrp.max_assets:
            # 配置期守卫：用 InfeasibleConstraintError（ValueError 子类）→ 引擎归类 config
            raise InfeasibleConstraintError(
                f"HRP 资产数 {n} 超过 max_assets={self.cfg.hrp.max_assets}"
            )

        cov = self._cov_for(selected, returns, cov_matrix)
        diag = np.diag(cov.to_numpy(dtype=float))
        valid = np.isfinite(diag) & (diag > 0.0)
        if not valid.any():
            # F-4-1：全零/非有限 diag → 等权特判（α 链非均权）
            raw = pd.Series(1.0 / n, index=selected)
            zero_vol = True
        else:
            # F-S9-P046b-1：先过滤零方差资产，在有效子域上 HRP 后回填 0 权重
            sub_cov = cov.loc[selected[valid], selected[valid]]
            dist = correlation_distance(sub_cov)
            order = quasi_diagonal_order(dist)
            sub_w = recursive_bisection(sub_cov, order)
            raw = pd.Series(0.0, index=selected)
            raw.loc[sub_w.index] = sub_w.to_numpy()
            zero_vol = False
        applied = self._apply_constraints(raw, feas)
        return OptimizationResult(
            applied,
            "hrp",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(applied.sum())),
            message="zero_vol" if zero_vol else "",
            warning_kind="zero_vol" if zero_vol else None,
        )
```

**部分零方差实现细化（F-S9-P046b-1）**：若直接在含零方差资产的 Σ 上跑 α 链，零方差资产会获得满权重（实测 `diag(0,.09,.16)` → `[0.64,0,0.36]`），与 DESIGN D11「零权重视为 0」语义不符；故实现改为先按 `diag>0` 且有限过滤、在有效子域跑 HRP、再回填 0（实测 `[0,0.64,0.36]`，Σw=1、无 NaN、`warning_kind=None`）。

**F-4-2 三分支**：`empty` → `_empty_result`；`upper` → `_upper_result`（`infeasible_kind="upper"` + message）；`lower` → `_precheck` 内 `InfeasibleConstraintError` 原样上抛。

### 3.8 T8：工厂

L619-L625 `optimizer_map` 增：

```python
        "black_litterman": BlackLittermanOptimizer,
        "bl": BlackLittermanOptimizer,
        "hrp": HRPOptimizer,
```

未知 method 的 `ValueError` 消息不变（sorted 自动含新键；既有测试只匹配 `"合法值"`）。

### 3.9 T9：引擎 `ZeroVariance` 分流

**锚点**：engine_v2.py L1370-L1384；唯一改动 L1375。

```python
                        error_type=(
                            "ZeroVariance"
                            if result.warning_kind == "zero_vol"
                            else "InfeasibleConstraints"
                        ),
```

触发条件（L1370）不变；`category`/`retryable` 不变；`_optimize_with_diagnostics` 签名不变。

### 3.10 T10：`estimate_cov`（`core/portfolio.py` L199-L228）

L214-L215 替换：

```python
    if codes is not None:
        missing = [c for c in codes if c not in returns.columns]
        if missing:
            logger.warning("estimate_cov: codes 缺失列已丢弃: %s", missing)
        returns = returns.loc[:, [c for c in codes if c in returns.columns]]
```

L221-L222 替换：

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

docstring 第 2-3 行改为「`codes` 非空时取交集并在缺失时 warning；有效行 <2 时 warning + 零填充」。输出数值不变。

### 3.11 T11：基准脚本 `scripts/p046b_bench_optimizers.py`

- 结构：`main() -> None`；`_make_cov(n, t, seed) -> pd.DataFrame`；三段计时（`time.perf_counter`）。
- 规模：N=50/200/500，T=60；seed=42。
- 打印：`cov`（`estimate_cov`）、`hrp`（`correlation_distance` + `quasi_diagonal_order` + `recursive_bisection`）、`bl`（`black_litterman_posterior`，K=5 绝对观点）。
- **无断言、不写文件、不进 CI**；但须过 `black --check .` 与 CI mypy（F-4-7）；全函数带类型标注、无裸 `except Exception`。

### 3.12 T12：测试（详见 §6）

---

## 4. 社区源码证据锚点（A20-A26）与对拍边界

### 4.0 取证降级链（规范要求显式记录）

| 通道 | 结果 |
|---|---|
| 目标：`raw.githubusercontent.com` / `cdn.jsdelivr.net` 直抓 | **失败**（WebFetch「local crawler returned empty」，2 域 2 次） |
| 备用：PyPI 镜像 wheel（`uv pip install --no-deps --target %TEMP%\p046b_pkgs`） | **成功**：`pyportfolioopt==1.5.5` / `skfolio==1.14.4` / `riskfolio-lib==7.4.1` |
| 本地事实 | 逐字读取上述源码 + 运行时对拍（§4.2） |
| 未取证声明 | GitHub 仓库 commit hash 未取（wheel 为 PyPI 发布物，版本号可解析）；不引「master 分支」结论 |

### 4.1 锚点表（源码级，T1）

| ID | 来源（版本可解析） | 文件 / 行 | 逐字要点 | 用途 |
|---|---|---|---|---|
| **A20** | PyPortfolioOpt **1.5.5**（PyPI） | `pypfopt/black_litterman.py` L346-L356 | `default_omega` → `np.diag(np.diag(tau * P @ cov_matrix @ P.T))` | 支撑 D6 默认 Ω |
| **A20b** | 同上 | L400-L408 | `_tau_sigma_P = tau*Σ@P.T`；`_A = P@_tau_sigma_P + omega`；`b = Q - P@pi`；`post = pi + _tau_sigma_P @ np.linalg.solve(_A, b)`；L403 注释「Solve the linear system Ax = b to avoid inversion」 | 支撑 D2/§5.3 Woodbury + 禁 `inv(Σ)` |
| **A20c** | 同上 | L277-L278 | `pi == "equal"` → `np.ones((n,1))/n`（**平直收益**，非 δΣw） | 命名分歧登记（§4.3） |
| **A20d** | 同上 | L229-L235 | 观点资产不在 universe → `raise ValueError("Providing a view on an asset not in the universe")` | 与本仓 D5「warning 后丢弃」分歧 |
| **A20e** | 同上 | L430-L453 | `raw = solve(risk_aversion*Σ, posterior); w = raw/raw.sum()` | 支撑 I2/F-R2 隐含权重测试 |
| **A21** | PyPortfolioOpt **1.5.5** | `pypfopt/hierarchical_portfolio.py` L77-L140 | `_get_cluster_var`：`weights = 1/np.diag(cov_slice)`；`_get_quasi_diag`：`to_tree(link, rd=False).pre_order()`；`_raw_hrp_allocation`：二分 + `alpha = 1 - v1/(v1+v2)` | 支撑 D10/I6；叶序等价性 |
| **A21b** | 同上 | L165-L168 | `matrix = sqrt(clip((1-corr)/2,0,1))`；`dist = squareform(matrix)`；`linkage(dist, method)` → **squareform，非 pdist(d)** | 第二级距离分歧（§4.3） |
| **A22** | skfolio **1.14.4** | `prior/_black_litterman.py` L246-L254、L277-L285 | 默认 Ω 同式；`posterior_mu = prior_mu + _v @ solve(_a,_b) + rf`；`posterior_cov = Σ + τΣ − _v @ solve(_a, _v.T)` | 支撑 Woodbury；后验 Σ 分歧（D7） |
| **A23** | skfolio **1.14.4** | `cluster/_hierarchical.py` L189-L197；`seriation/_hierarchical.py` L127-L132；`optimization/hierarchical/_seriation/_hrp.py` L485-L524 | `squareform(X)` → `linkage`；`leaves_list(linkage)`；零/非有限风险 → `raise OptimizationError`；`alpha = 1 − left/(left+right)`；约束在**拆分因子**层施加 | 退化/约束分歧（D11/D12） |
| **A24** | Riskfolio-Lib **7.4.1** | `src/HCPortfolio.py` L381-L382、L433-L506、L239-L243 | `squareform(dist)` → `linkage`；`alpha_1 = 1 − left/(left+right)`；MV 下 `inv_risk = 1/power(risk,2)`，无零风险守卫 | 第二级距离分歧；零方差无守卫佐证 |
| **A25** | pypfopt 1.5.5 × pandas **3.0.3**（本仓运行时） | `hierarchical_portfolio.py` L120/L138-L139 | `w = pd.Series(1, ...)` 为 int64 → `w[cluster] *= alpha` 抛 `TypeError: Invalid value '[0.29906542]' for dtype 'int64'` | **pypfopt 只能手工对拍、不得进 CI**（Q7 强化） |
| **A26** | scipy **1.17.1**（本仓） | `leaves_list` vs `to_tree(...).pre_order()` | 论文 Example 实测两者相等（`True`） | 叶序口径闭合（F-R3） |

### 4.2 跨实现对拍读数（本次实跑）

| 项 | pypfopt 1.5.5 实测 | 本仓设计口径 | 结论 |
|---|---|---|---|
| BL 后验（E2 设定，τ=0.05） | `[0.0905, 0.116375, 0.15775]` | 同值（E2/§3.3 闭式） | **逐位一致** |
| BL τ=0.5 | 同 `[0.0905, 0.116375, 0.15775]` | 同值 | **τ 消去成立** |
| BL 隐含权重 `(δΣ)⁻¹post`（δ=3） | `[0.579167, 0.3, 0.2]` | 同值 | **仅观点资产位移**（F-R2） |
| HRP 3×3（E2 协方差矩阵）叶序 | `[1,0,2]` | `[1,0,2]` | 小样本两者重合（无法区分第二级口径；论文 Example 为 `[2,0,1]`，见 RESEARCH §4.1） |
| HRP 随机 6×6（seed=7）叶序 | `squareform(d)` → `[5,2,1,3,0,4]` | `pdist(d)` → `[5,1,2,3,0,4]` | **分歧** |
| HRP 随机 6×6 权重 max\|Δ\| | — | — | **0.0152**（不可作逐位对拍） |

### 4.3 与本仓设计的分歧登记（有意为之）

| 面 | 本仓（DESIGN/IMPL） | 社区实现 | 裁决依据 |
|---|---|---|---|
| 第二级距离 | `pdist(d)`（论文 d̃） | pypfopt/skfolio/Riskfolio 均 `squareform(d)` | 题干要求实现论文三细节；A4 §14.8 |
| `prior="equal"` | `Π = δΣ(1/N)`（等权市场均衡代理） | pypfopt `pi="equal"` = `1/N` 平直收益；skfolio 默认 `EquilibriumMu`（δΣw_mkt） | D4；对拍须向 pypfopt 传**显式 π 数组** |
| 后验协方差 | 沿用原 Σ | pypfopt `bl_cov`；skfolio 替换 posterior covariance | D7（Σ 单一真值源） |
| 未知观点资产 | 优化器层 warning 后丢弃 | pypfopt 抛 `ValueError`；skfolio `raise_if_group_missing=True` | D5（选股变动不整日失败） |
| 零方差 | 显式等权/零权分支（F-4-1） | pypfopt 无守卫（1/0）；skfolio 抛 `OptimizationError` | D11；`estimate_cov` 退化是生产路径 |
| HRP 约束 | 出权重后 `_apply_constraints` 后投影 | skfolio 在拆分因子层约束 | D12；后投影简单可测，偏差在 docstring 声明 |
| linkage | 固定 `single` | skfolio 默认 Ward | 论文 single；`HRPConfig` 仅 single |

> **对拍边界（Step 9/10 必须遵守）**：与 pypfopt 的自动对拍只允许覆盖 **(a) BL 后验公式（显式 π/Ω 输入）**、**(b) 第一级距离 d**、**(c) 给定叶序下的 α 拆分**；**禁止**断言叶序/权重与社区实现逐位相等（§4.2 已证分歧）。pypfopt 不得加入依赖或 CI（A25 + Q7）。

---

## 5. 低效排除表（规范硬约束，非空）

| 候选方案 | 排除原因 | 采用方案 |
|---|---|---|
| `np.linalg.inv(Σ)` 求后验 | O(N³) + 数值不稳定；N=1000 实测 0.294 s vs Woodbury 0.011 s（RESEARCH §14） | K×K `solve`（同 A20b 注释） |
| `(N,N,N)` 广播算二级距离 | N=1000 约 8 GB 峰值 | `pdist` O(N²) 内存 |
| 用 cvxpy 解 HRP | 层次算法有闭式递归，凸求解徒增依赖与失败面 | `recursive_bisection` 纯函数 |
| 把 pypfopt 设为运行时依赖/对拍入口 | pandas 3.0 不兼容（A25）；Q7 仅对拍；锁与 CI 成本 | 仅手工对拍，不装依赖 |
| 逐资产 Python 循环算 vol/corr | N=2000 时解释器开销主导 | numpy 向量化 |
| `DataFrame.apply` 算簇方差 | 每层全表重建，O(N² log N) 常数大 | `np.ix_` 切片 |
| 每个优化器各自 `estimate_cov` | 重复全维估计（0.426 s/次，N=1000） | 引擎单次 Σ 注入（P-046a SSOT） |
| 先选股后估协方差（全批改造） | LW 子集化改变数值（A18：shrinkage 0.9248 vs 1.0） | 本批不改，另立批 |
| `optimal_leaf_ordering` | 额外 O(N² log N) 且论文不要求；会改变叶序 | 不启用 |
| 递归函数返回新数组 | 每层复制 O(N²) 内存 | 预分配 `w` + 索引区间 |
| 以 `message` 前缀分流零方差 | 字符串匹配脆弱 | `warning_kind` 字段 |

---

## 6. 测试先行计划（红 → 绿）

### 6.1 红态（先写）

**顺序**：先写 `tests/test_p046b_bl.py` / `tests/test_p046b_hrp.py` 与 3 个增例 → 运行：

```powershell
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest tests/test_p046b_bl.py tests/test_p046b_hrp.py -q
```

**预期红读数**：`ImportError: cannot import name 'black_litterman_posterior'`（或 `AttributeError`），收集失败/全红；记录 README 式输出到 Step 9 日志。

### 6.2 用例映射（23 例）

| 文件 | # | 用例 | 断言要点 | 对应设计 |
|---|---|---|---|---|
| `test_p046b_bl.py` | 1 | `test_bl_no_views_equals_prior` | K=0 → 后验==prior（`1e-12`） | I1 |
| | 2 | `test_bl_single_view_closed_form` | `post = π + Σe_i(Q−π_i)/(2Σ_ii)`（Ω=τΣ_ii） | A20b |
| | 3 | `test_bl_single_view_implied_weights_only_view_asset` | 随机 5×5（seed=42）：非观点资产 `<1e-10`、观点资产 `>1e-8` | I2/F-R2 |
| | 4 | `test_bl_tau_cancels_with_default_omega` | τ=0.05 vs 0.5 一致 | I3 |
| | 5 | `test_bl_omega_limits` | Ω→0 → Q；Ω→∞ → prior | I4 |
| | 6 | `test_bl_zero_view_variance_raises` | 零方差 cov + 观点 → `ValueError` | I5/D8 |
| | 7 | `test_bl_explicit_prior_missing_asset_raises` | 显式先验缺选中资产 → `ValueError` | D4 |
| | 8 | `test_bl_views_missing_asset_filtered` | `caplog` warning + 权重正常（Σ≤1） | D5 |
| | 9 | `test_bl_optimizer_not_mean_variance_subclass` | `isinstance(BaseOptimizer)` 且 **not** MVO | D3 |
| | 10 | `test_bl_upper_infeasible_passthrough` | `n×max<1` → `infeasible_kind="upper"` + cash | F-4-2 |
| | 11 | `test_build_optimizer_bl_aliases` | `black_litterman` / `bl` 均 BL；bogus → `ValueError` | D14 |
| `test_p046b_hrp.py` | 1 | `test_hrp_distance_matches_paper_example` | `d` 与 `pdist(d)=d̃` 逐位（`1e-4`） | I6 |
| | 2 | `test_hrp_single_linkage_leaves_order` | `Z` 合并距离 + `leaves=[2,0,1]` | I6 |
| | 3 | `test_hrp_recursive_bisection_closed_form` | 测试内独立复算 α；Σw=1 | I7 |
| | 4 | `test_hrp_single_asset` | N=1 → `[1.0]` | I8 |
| | 5 | `test_hrp_zero_variance_no_nan` | 全零 → 等权 1/N + `warning_kind`；部分零 → **先过滤子域 → 有效子域 HRP → 回填 0**（F-S9-P046b-1），零权资产；无 NaN | F-4-1 |
| | 6 | `test_hrp_max_assets_guard` | `max_assets=2` + 3 资产 → `ValueError` | D18 |
| | 7 | `test_hrp_box_constraints` | upper 字段/message；lower 抛 `InfeasibleConstraintError` | F-4-2 |
| | 8 | `test_hrp_method_name` | `method == "hrp"` | D14 |
| | 9 | `test_build_optimizer_hrp` | 工厂分支 + bogus 行为不变 | D14 |
| `test_p046_cov.py` | +1 | `test_estimate_cov_degenerate_warns` | 有效行<2 → `caplog` warning；输出无 NaN | F-S10-P046-2 |
| | +2 | `test_estimate_cov_codes_missing_warns` | 缺失 code 丢弃 + warning；列=交集 | F-S10-P046-3 |
| `test_p046_engine.py` | +1 | `test_zero_vol_records_zero_variance` | 注入假优化器（`warning_kind="zero_vol"`）→ `error_type=="ZeroVariance"`、`category=="optimizer"` | F-S10-P046-1 |

### 6.3 既有断言保护

- `test_p046_constraints.py` 的 `METHODS` **不加入** BL/HRP。
- golden 22 零重录；`-k p054` 120 零回归；不新增 skip/xfail。
- `test_p046_engine.py` 既有用例零改动；仅 `_make_engine` 增可选透传（向后兼容）：

```python
def _make_engine(
    root, *, optimizer: OptimizerConfig, risk_overlay=None, day_error_mode="record",
    event_bus=None, optimizer_instance=None,
):
    ...
    engine = BacktestEngineV2(cfg, optimizer=optimizer_instance, event_bus=event_bus)
```

- 新引擎用例注入假优化器：

```python
class _FakeZeroVol:
    cfg = OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0)

    def optimize_with_diagnostics(self, factor_scores, returns=None, cov_matrix=None):
        w = pd.Series(0.5, index=factor_scores.index[:2])
        return OptimizationResult(w, "fake", 2, 1.0, 0.0, message="zero_vol", warning_kind="zero_vol")
```

- **数据前置校验**：所有优化器在 `_precheck` 之前先校验「`returns`/`cov_matrix` 不可同时为空」，故 upper/lower 用例须传 `returns` 或 `cov_matrix`（与既有 `test_p046_constraints` 一致）。
- 零方差/零权重断言统一用 `optimize_with_diagnostics(...)`（`optimize()` 仅返回 `weights`，读不到 `warning_kind`）。

### 6.4 绿态判据

```powershell
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q          # 1463 passed / 1 skipped（collect 1464）
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q -k p046  # 78 passed
```

---

## 7. 门禁与验收命令（@Step 9/10 实测）

| 项 | 命令（PowerShell 5） | 目标读数 |
|---|---|---|
| pytest 全量 | `$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q` | **1463 passed / 1 skipped**（collect **1464**） |
| `-k p046` | 同上 `-k p046` | **78** |
| `-k golden` | 同上 `-k golden` | **22** 零重录 |
| `-k p054` | 同上 `-k p054` | **120** |
| black | `.venv\Scripts\python.exe -m black --check .` | **322 unchanged** |
| mypy（CI 同款） | 见 `.github/workflows/tests.yml` L46：`python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples live services` | **160 source files / 0** |
| AST P-029 | `.venv\Scripts\python.exe -c "import ast,pathlib;r=pathlib.Path('.');s=[p for d in ['agents','filter','scripts','batch_backtest','strategy_evaluation'] for p in (r/d).rglob('*.py')]+[r/'cli.py'];print(sum(1 for p in s if p.exists() for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='Exception'))"` | **22**（core 30） |
| lint-imports | `lint-imports` | **3 kept** |
| uv lock | `uv lock --check` | exit **0**（零新依赖） |
| 文件计数 | `tests/*.py` / `core/*.py` / `live/**/*.py` / `services/*.py` | **158 / 51 / 19 / 13** |

> 若 Step 9 实际 collect 偏移，按 RULE-1 登记 `F-S9-P046b-*`；目标可机械修正，**不得改既有断言**。

---

## 8. 风险与回退

| 风险 | 概率 | 影响 | 缓解 / 回退 |
|---|---|---|---|
| `_solve_mean_variance` 抽取改变 MVO 边界行为 | 中 | 既有 U1-A/U1-B 用例红 | 保留 `feas` 入参保持 lazy 顺序（§3.4/F-5-1）；出错则 T4 单提交回退旧内联 |
| HRP `pdist` 与社区 `squareform` 分歧被发现当作 bug | 中 | 复审争议 | §4.2/§4.3 已登记有意分歧 + 对拍边界；DESIGN 已复审 PASS |
| `estimate_cov` 全零 → HRP 生产路径 | 高 | NaN/inf | F-4-1 等权特判 + `warning_kind`；测试 #5 锁定 |
| 新增方法进入 sorted 词表破坏消息断言 | 低 | 未知-method 用例红 | 既有测试只匹配 `"合法值"`（test_p025 L291） |
| bench 脚本 mypy/black 拖红 | 中 | 门禁 160/322 不达 | 脚本函数全标注、无裸 except；先跑 `black`/`mypy scripts/...` |
| pandas/numpy 版本差异影响协方差数值 | 低 | 测试抖动 | 断言用解析式/容差，不录制数值 |
| 零方差 detail 改变既有 diagnostics 汇总 | 低 | `test_zero_variance_window` 红 | `counts` 按 stage 键、`optimizer` 不进 degraded/raise（§4 Step 4 已核实） |

---

## 9. 状态链

- **2026-11-23**：Step 3 DESIGN（[DESIGN_p046b](DESIGN_p046b_bl_hrp.md)）；Step 4 复审 PASS（[REVIEW_p046b_step3_design](REVIEW_p046b_step3_design.md)，2 P2 + 6 P3 全修）。
- **2026-11-23**：**Step 5 IMPL 落盘（本文）**——T1-T12；接口签名 + 回退点；低效排除表 11 行；源码级锚点 A20-A26；跨实现对拍（BL 逐位一致 / HRP 第二级距离分歧）；测试 23 例红→绿计划；门禁命令。**零代码变更 / 未提交**。
- **本步登记**：
  - **F-5-1**：`_solve_mean_variance` 增 `feas` 关键字（DESIGN §4.5 签名的兼容精化；保 MVO upper 早退 lazy 语义，避免边界行为漂移）。
  - **F-5-2**：HRP `max_assets` 守卫抛 `InfeasibleConstraintError`（DESIGN D18 的 `ValueError` 子类）→ 引擎归类 `config` 而非 `solver`，语义更准且不改变 `pytest.raises(ValueError)` 契约。
  - **F-5-3**：对拍边界成文——与 pypfopt 仅对 BL 后验/第一级 d/给定叶序 α 对拍，**禁止**叶序/权重逐位断言（§4.2 实测 max|Δ|=0.0152）。
  - **F-5-4**（Step 6 复审补登，F-6-1）：派生接口 `_upper_result(cfg, selected, method)`——三优化器 upper 消息去重的模块级函数；DESIGN §4.5 未声明、行为与既有内联逐字等同；`MinVarianceOptimizer` 保持零改动（F-6-3）。
- **2026-11-23**：**Step 6 实施文档复审 PASS**（[REVIEW_p046b_step5_impl](REVIEW_p046b_step5_impl.md)，GLM-5.3-Flash ≠ 作者）——版本核验表 3 包 METADATA 全 T1 命中；锚点行号机械核验 **16/16**；签名可实现性 14 项 + 无命名冲突；**0 P1 / 0 P2 / 4 P3 当轮全修**（F-6-1 派生接口 `_upper_result` 补登 F-5-4 / F-6-2 回退点措辞 / F-6-3 MinVariance 零改动声明 / F-6-4 upper+zero_vol 组合优先级）；门禁目标不变。
- **2026-11-23**：**Step 7 CHECKLIST 落盘**（[CHECKLIST_p046b_bl_hrp](CHECKLIST_p046b_bl_hrp.md)）——70 项（A 8 / B 10 / C 11 / D 9 / E 12 / F 6 / G 9 / H 5），每项 DoR/DoD/证据出口；实测列 0 预填；门禁目标冻结（1464 / 1463 / 78 / 22 / 120 / 160 / 322 / 158 / 51 / 19 / 13 / 22·30 / 3 kept / 0）。**零代码变更**。
- **2026-11-23**：**Step 8 一致性复审 PASS**（[CHECKLIST_p046b §12](CHECKLIST_p046b_bl_hrp.md)，GLM-5.3-Flash ≠ 作者）——机械校验器 **78/78**；D↔T↔CHECKLIST 无悬空；F-5-1..F-5-4 派生需求登记核对通过；H1 回填 ✅。
- **2026-11-23**：**Step 9 TDD PASS**——先红后绿：红态 `tests/test_p046b_bl.py` / `tests/test_p046b_hrp.py` 收集失败 `ImportError: cannot import name 'BLConfig'/'HRPConfig'`（2 errors）；绿态定向 **40 passed**、全量 **1463 passed + 1 skipped**（collect **1464**）、`-k p046` **78** / golden **22** / `-k p054` **120**；门禁 mypy **160·0** / black **322 unchanged**（4 个本批文件格式化后复跑）/ AST **22·30** / `lint-imports` **3 kept** / `uv lock` **0** / 文件计数 **158·51·19·13**；bench N=50/200/500 实跑通过（补 `sys.path` 引导，与 `p055_bench_e2e.py` 同惯例）。
- **本步登记**：
  - **F-S9-P046b-1（P3，实现细化）**：HRP 部分零方差改为「先按 `diag>0` 且有限过滤 → 有效子域 HRP → 回填 0 权重」。理由：直接跑 α 链会让零方差资产得满权重（实测 `[0.64,0,0.36]`），与 D11「零权重视为 0」不符；细化后 `[0,0.64,0.36]`、Σw=1、无 NaN、`warning_kind=None`。已回写 DESIGN D11/§6.4 与本文件 §3.7/§6.2#5；`test_hrp_zero_variance_no_nan` 通过。
  - collect 精确 **1464**（1441 + 23），**无偏移**，无需 F-S9 收集偏移登记。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046b §14](CHECKLIST_p046b_bl_hrp.md)，审计基座 GLM-5.3-Flash ≠ 作者）——Phase 0-4 全过；门禁独立重放全绿（1463+1 / 78 / 22 / 120 / 160·0 / 322 / 22·30 / 3 kept / 0 / 158·51·19·13）；数值探针 6/6；**0 P0-P2 + 1 观察 O-R5-P046b-1**（不改码）。
- **下一步**：H5 提交与 CI（须用户明确授权；CI 四 job 全绿后批次关闭）。
