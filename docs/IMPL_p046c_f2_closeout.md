# IMPL：P-046c F2 收尾（Step 5 实施文档）

> **批次**: P-046c · **Step 5 实施文档** · 日期 2026-11-23
> **上游**: [DESIGN_p046c_f2_closeout](DESIGN_p046c_f2_closeout.md)（D1-D22 / I1-I12）+ [REVIEW_p046c_step3_design](REVIEW_p046c_step3_design.md)（F-4-1..F-4-3 已回填；O-4-1..O-4-3 登记）
> **代码基线**: HEAD `3495683`；pytest collect **1464**（1463 passed + 1 skipped）/ `-k p046` **78** / golden **22** / `-k p054` **120** / mypy **160·0** / black **322** / AST **22·30** / `lint-imports` **3 kept** / `uv lock --check` **0** / 文件 **158·51·19·13**
> **作者**: DeepSeek-V4.1-Flash（Step 6 复审须 reviewer ≠ author）
> **性质**: 实施指南——任务拆解、接口签名、回退点、代码骨架、插入锚点（行号 @`3495683`，改动后失效）、红→绿计划、门禁命令；**不含**已完成代码
> **外部取证**: 本步新增源码级锚点 **A27-A36**（§4；PyPI 指定版本 wheel 逐字读取）+ 跨实现对拍读数；降级链见 §4.0

---

## 0. 本文定位

| 本文已定 | 留给后续 |
|---|---|
| T1-T9 任务拆解 / 依赖序 / 提交粒度（§1） | Step 6 实施文档复审（本文不自评 PASS） |
| 接口签名 + 回退点（§2，规范硬约束） | Step 7 CHECKLIST 的 DoR/DoD |
| 逐任务代码骨架与插入锚点（§3） | Step 9 TDD 红→绿执行 |
| 社区源码锚点与对拍边界（§4） | Step 10 独立验收 |
| 低效排除表（§5，规范硬约束） | |
| 测试先行计划（§6）/ 门禁命令（§7）/ 风险回退（§8） | |
| Step 5 派生需求登记 F-5-1..F-5-3（§9） | |

---

## 1. 实施总览

### 1.1 任务与依赖

| 任务 | 内容 | 依赖 | 规模 | 目标文件 |
|---|---|---|---|---|
| **T1** | 配置：`KellyConfig` / `MaxSharpeConfig` / `OptimizerConfig.risk_budget/kelly/max_sharpe` + 4 项校验 | — | +55 行 | `core/config.py` |
| **T2** | 风险预算归一 `_risk_budget_vector` + 凸求解 `_solve_risk_budget_convex` + 3 常量 | — | +70 行 | `core/portfolio.py` |
| **T3** | `RiskParityOptimizer` 改造（diag 预判 / 预算路径 / 四条件回退 / 诊断） | T2 | +45 / −12 行 | `core/portfolio.py` |
| **T4** | `_solve_mean_variance` 增 `risk_aversion` 关键字 + `KellyOptimizer` | T1 | +8 / −2 + 40 行 | `core/portfolio.py` |
| **T5** | `MaxSharpeOptimizer`（Charnes-Cooper） | T1 | +60 行 | `core/portfolio.py` |
| **T6** | `IndustryCapResult` + `project_industry_cap` 纯函数 | — | +95 行 | `core/portfolio.py` |
| **T7** | 工厂 2 键 + 引擎接线（属性 / `_industry_tags` / 插入块 / 诊断映射） | T1/T6 | +55 行 | `portfolio.py` / `engine_v2.py` |
| **T8** | 测试 39 例（3 新文件） | T1-T7 | 新 3 文件 ~640 行 | `tests/*` |
| **T9** | 台账与文档回填（PROGRESS 主行 + 下一可用序号分节（§3.103 已被 Step 5 占用）；DESIGN/RESEARCH 状态链） | T8 | 文档 | `docs/*` |

**依赖序**：T1 → T2 → T3；T1 → T4 → T5；T6 → T7；T8 最后；T9 收尾。
（TDD 编写顺序见 §6：先红后绿；上表为「实现顺序」）

### 1.2 文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `core/config.py` | 改 | L297-L308 后插 2 配置类；L335 后插 `risk_budget`；L344 后插 `kelly/max_sharpe`；L358 后追加校验 |
| `core/portfolio.py` | 改 | L37 后加 3 常量；L586 后插预算/凸求解助手；L714 后插 Kelly/MaxSharpe；L717-L794 改造 RP；L846 后插投影；L890-L899 工厂 +2 键 |
| `core/engine_v2.py` | 改 | L65 后导入追加；L~100 模块常量；L192 后属性；L1375 映射；L1507 后插入块；L1538 后助手 |
| `tests/test_p046c_erc_budget.py` | **新建** | 14 例 |
| `tests/test_p046c_kelly_sharpe.py` | **新建** | 15 例 |
| `tests/test_p046c_industry_cap.py` | **新建** | 10 例 |

### 1.3 提交粒度

`T1`（配置）→ `T2+T3`（ERC/预算）→ `T4+T5`（Kelly/MaxSharpe）→ `T6+T7`（投影与引擎）→ `T8`（测试）→ `T9`（台账）。
每段独立 `pytest -q` 可跑；**任一段红不得进入下一段**。

---

## 2. 接口签名与回退点（规范硬约束）

| 接口 | 签名（冻结） | 位置 | 回退点 |
|---|---|---|---|
| `KellyConfig` | `@dataclass class KellyConfig(fraction: float = 0.5)` | config.py L308 后 | 删类 + `OptimizerConfig.kelly` |
| `MaxSharpeConfig` | `@dataclass class MaxSharpeConfig(risk_free_rate: float = 0.0)` | 同上 | 删类 + `OptimizerConfig.max_sharpe` |
| `OptimizerConfig.risk_budget` | `risk_budget: dict[str, float] \| None = None` | config.py L335 后 | 删字段 + 校验块 |
| `OptimizerConfig.kelly/max_sharpe` | `kelly: KellyConfig = field(default_factory=KellyConfig)`；`max_sharpe: MaxSharpeConfig = field(default_factory=MaxSharpeConfig)` | config.py L344 后 | 删两行 |
| `_risk_budget_vector` | `(selected: pd.Index, raw: Optional[Mapping[str,float]]) -> np.ndarray` | portfolio.py L586 后 | 删函数（仅 RP 调用） |
| `_solve_risk_budget_convex` | `(cov: np.ndarray, budget: np.ndarray) -> np.ndarray` | 同上 | 删函数 + RP 回退分支 |
| `_solve_mean_variance` | 既有签名 + `*, risk_aversion: Optional[float] = None`（**keyword-only，默认 None 保持 MVO/BL 逐字等价**） | portfolio.py L542-L586 | 删关键字 + Kelly 调用改回 cfg 值 |
| `KellyOptimizer.optimize_with_diagnostics` | `(factor_scores, returns=None, cov_matrix=None) -> OptimizationResult` | portfolio.py L714 后 | 删类 + 工厂一键 |
| `MaxSharpeOptimizer.optimize_with_diagnostics` | 同上 | Kelly 后 | 删类 + 工厂一键 |
| `IndustryCapResult` | `@dataclass(frozen=True)`：`weights/applied/n_groups/n_unclassified/max_group_before/max_group_after/l1_deviation` | portfolio.py L846 后 | 删 dataclass + 函数 |
| `project_industry_cap` | `(weights: pd.Series, industry: pd.Series, *, cap: float, max_weight: float) -> IndustryCapResult` | 同上 | 删函数 + 引擎插入块 |
| `build_optimizer` | 签名不变，map 增 `kelly` / `max_sharpe` 两键 | portfolio.py L890-L899 | 删 2 个 map 项 |
| 引擎诊断映射 | `_WARNING_ERROR_TYPES = {"zero_vol": "ZeroVariance", "erc_fallback": "RiskParityFallback"}` | engine_v2.py L~100 | 回退原三元表达式（zero_vol 行为逐字保持） |
| `_industry_tags` | `(date: pd.Timestamp) -> Optional[pd.Series]` | engine_v2.py `_execute_rebalance` 后 | 删方法 + 插入块 |

> 任一接口删除均**无数据迁移、无锁文件变更、无 golden 重录**；`IOptimizer` / 6 个既有优化器 / `config_v2` / `sizing.py` 零改动。

---

## 3. 逐任务实施规格

### 3.1 T1：配置（`core/config.py`）

**锚点**：`HRPConfig` 定义 L297-L308；`OptimizerConfig` L311；字段区 L322-L344；`__post_init__` L346-L358。`import math` 已存在（L10，P-046b F-4-3）。

L308 后插入：

```python
@dataclass
class KellyConfig:
    """凯利方法级配置（仅 method='kelly' 时读取）。

    ``fraction`` 是风险厌恶的单调旋钮：求解 ``max μᵀw − (1/fraction)·wᵀΣw``；
    在 ``Σw=1`` 约束下尺度不改变方向，故 ``fraction`` **不是字面仓位倍数**。
    与 pypfopt ``max_quadratic_utility`` 的 δ 关系为 ``δ = 2/fraction``
    （其目标含 δ/2 因子，A31）。
    """

    fraction: float = 0.5

    def __post_init__(self) -> None:
        if not (0.0 < self.fraction <= 1.0):
            raise ValueError(f"KellyConfig.fraction 必须在 (0,1]: {self.fraction}")


@dataclass
class MaxSharpeConfig:
    """max_sharpe 方法级配置（仅 method='max_sharpe' 时读取）。"""

    risk_free_rate: float = 0.0  # 与 μ 同频；须为有限数

    def __post_init__(self) -> None:
        if not math.isfinite(self.risk_free_rate):
            raise ValueError(
                f"MaxSharpeConfig.risk_free_rate 必须为有限数: {self.risk_free_rate}"
            )
```

L335（`risk_parity_max_iter`）后插入：

```python
    risk_budget: dict[str, float] | None = None  # 风险预算（RC 占比目标，仅 risk_parity）
```

L344（`hrp`）后插入：

```python
    kelly: KellyConfig = field(default_factory=KellyConfig)  # P-046c
    max_sharpe: MaxSharpeConfig = field(default_factory=MaxSharpeConfig)  # P-046c
```

L358（`target_count` 校验）后追加：

```python
        cap = self.industry_max_weight
        if cap is not None and not (0.0 < float(cap) <= 1.0):
            raise ValueError(f"industry_max_weight 必须在 (0,1]: {cap}")
        if self.risk_budget is not None:
            if not isinstance(self.risk_budget, dict) or not self.risk_budget:
                raise ValueError("risk_budget 必须为非空 dict[str, float]")
            if not all(isinstance(k, str) for k in self.risk_budget):
                raise ValueError("risk_budget 的键必须为资产代码字符串")
            vals = [float(v) for v in self.risk_budget.values()]
            if not all(math.isfinite(v) and v >= 0.0 for v in vals):
                raise ValueError("risk_budget 的值必须为非负有限数")
            if sum(vals) <= 0.0:
                raise ValueError("risk_budget 之和必须大于 0")
            if self.method != "risk_parity":
                raise ValueError("risk_budget 仅适用于 method='risk_parity'")
```

> `industry_max_weight` **不加** `≤max_weight` 校验（D17；config_v2 L143 规则方向性错误）。

### 3.2 T2：预算归一与凸求解（`core/portfolio.py`）

**锚点**：常量区 L32-L39；`_solve_mean_variance` 结束 L586；`MinVarianceOptimizer` 起 L589。

L39（`EWMA_LAMBDA`）后插入：

```python
# P-046c：风险预算 / 行业上限容差
_BUDGET_TOL = 1e-12
_ERC_RC_TOL = 1e-3
_INDUSTRY_CAP_TOL = 1e-9
```

L586 后插入：

```python
def _risk_budget_vector(
    selected: pd.Index, raw: Optional[Mapping[str, float]]
) -> np.ndarray:
    """风险预算归一（DESIGN D7）：缺失补剩余均分、多余丢弃、无交集等风险。"""
    n = len(selected)
    if not raw:
        return np.full(n, 1.0 / n)
    extra = sorted(set(raw) - set(selected))
    if extra:
        logger.warning("risk_budget 含未入选资产，已丢弃: %s", extra)
    hit = {k: float(v) for k, v in raw.items() if k in selected}
    if not hit:
        logger.warning("risk_budget 与选中集无交集，回退等风险预算")
        return np.full(n, 1.0 / n)
    total = sum(hit.values())
    if total > 1.0 + _BUDGET_TOL:
        raise ValueError(f"risk_budget 已指定部分之和 {total:.6f} > 1")
    missing = [c for c in selected if c not in hit]
    budget = np.zeros(n, dtype=float)
    for i, code in enumerate(selected):
        budget[i] = hit.get(code, 0.0)
    if missing:
        remain = 1.0 - total
        if remain <= 0.0:
            raise ValueError("risk_budget 未覆盖全部资产且无剩余额度")
        share = remain / len(missing)
        for i, code in enumerate(selected):
            if code not in hit:
                budget[i] = share
    elif abs(total - 1.0) > _BUDGET_TOL:
        raise ValueError(f"risk_budget 覆盖全部资产时必须合计为 1: {total:.6f}")
    if np.any(~np.isfinite(budget)) or np.any(budget <= 0.0):
        raise ValueError("risk_budget 归一后存在非正/非有限分量")
    return budget / float(budget.sum())


def _solve_risk_budget_convex(cov: np.ndarray, budget: np.ndarray) -> np.ndarray:
    """风险预算凸解（DESIGN D4）。

    ``min 0.5·wᵀΣw s.t. w≥0, bᵀlog w≥0`` —— **不得加 Σw=1**：
    n≥2 时与 ``bᵀlog w≥0`` 互斥（加权几何平均 ≤ 算术平均 = 1，
    等号仅全 1，而 Σw=n≠1）；Step 5 探针 status=infeasible 实证。
    解后归一；归一不改变 RC 比例。
    """
    n = len(budget)
    w = cp.Variable(n)
    constraints = [w >= 0, cp.sum(cp.multiply(budget, cp.log(w))) >= 0]
    problem = cp.Problem(
        cp.Minimize(0.5 * cp.quad_form(w, cp.psd_wrap(cov))), constraints
    )
    problem.solve()
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or w.value is None:
        raise RuntimeError(f"风险预算凸求解失败: solver status={problem.status}")
    values = np.clip(np.asarray(w.value, dtype=float).ravel(), 0.0, None)
    total = float(values.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise RuntimeError("风险预算凸求解产生非正/非有限权重和")
    return values / total
```

> `cp.psd_wrap` 在 cvxpy 1.9.1 可用（本仓运行时；Step 5 探针已实跑）。

### 3.3 T3：`RiskParityOptimizer` 改造（L717-L794）

保留 `_precheck` / `_cov_for` / `_apply_constraints` / upper 分支结构；替换 L736-L756 的计算段为（L758-L765 归一与诊断见下一段，**两段不重叠**——F-6-1 修正）：

```python
        cov_values = cov.to_numpy(dtype=float)
        diag = np.diag(cov_values)
        zero_vol = False
        fallback_reason: Optional[str] = None

        if np.any(~np.isfinite(diag)) or np.any(diag <= 0.0):
            # D3 diag 预判：部分/全零方差走等权（与现状权重一致），不进凸回退
            zero_vol = True
            weights = np.ones(n) / n
        elif self.cfg.risk_budget is not None:
            budget = _risk_budget_vector(selected_stocks, self.cfg.risk_budget)
            weights = _solve_risk_budget_convex(cov_values, budget)
            fallback_reason = "risk_budget"
        else:
            weights = np.ones(n) / n
            converged = False
            for _ in range(self.cfg.risk_parity_max_iter):
                portfolio_variance = float(weights @ cov_values @ weights)
                if not np.isfinite(portfolio_variance) or portfolio_variance <= 0.0:
                    zero_vol = True
                    break
                portfolio_vol = np.sqrt(portfolio_variance)
                marginal_contrib = cov_values @ weights / portfolio_vol
                risk_contrib = weights * marginal_contrib
                if np.any(risk_contrib <= 0.0):
                    fallback_reason = "negative_rc"
                    break
                target_risk_contrib = risk_contrib.mean()
                weights_new = weights * target_risk_contrib / risk_contrib
                if np.max(np.abs(weights_new - weights)) < self.cfg.risk_parity_tol:
                    weights = weights_new
                    converged = True
                    break
                weights = weights_new
            if not zero_vol and fallback_reason is None and not converged:
                fallback_reason = "max_iter"   # F-4-2：zero_vol break 不误判 max_iter
            if not zero_vol and fallback_reason is None:
                pvar = float(weights @ cov_values @ weights)
                if not np.isfinite(pvar) or pvar <= 0.0:
                    fallback_reason = "rc_mismatch"
                else:
                    pct = weights * (cov_values @ weights) / pvar
                    if np.max(np.abs(pct - 1.0 / n)) > _ERC_RC_TOL:
                        fallback_reason = "rc_mismatch"
            if fallback_reason is not None:
                weights = _solve_risk_budget_convex(cov_values, np.full(n, 1.0 / n))
```

L758-L765 的归一与诊断改为：

```python
        total = float(weights.sum())
        if np.isfinite(total) and total > 0.0:
            weights = weights / total

        weights_series = pd.Series(weights, index=selected_stocks)
        applied = self._apply_constraints(weights_series, feas)
        if zero_vol:
            message, warning_kind = "zero_vol", "zero_vol"
        elif fallback_reason is not None:
            message = f"erc_fallback:{fallback_reason}"
            warning_kind = "erc_fallback"
        else:
            message, warning_kind = "", None
```

upper 分支的 return 保持原样（`message=` 分支不覆盖 upper 消息，`warning_kind=warning_kind`）。

**零漂移判据**：正常路径（diag 全正、σ_p²>0、`risk_budget is None`）的循环体与现状逐字相同（`target_risk_contrib = risk_contrib.mean()` 未改写）；E7 equicorr 与 60×20 sample 必须 `message==""`。

### 3.4 T4：`_solve_mean_variance` 关键字 + `KellyOptimizer`

L542-L550 签名追加 keyword-only：

```python
    *,
    feas: Optional[_Feasibility] = None,
    risk_aversion: Optional[float] = None,
) -> OptimizationResult:
```

L572 目标函数改为：

```python
    lam = cfg.risk_aversion if risk_aversion is None else float(risk_aversion)
    if not math.isfinite(lam) or lam <= 0.0:
        raise ValueError(f"risk_aversion 必须为正有限数: {lam}")
    objective = cp.Maximize(portfolio_return - lam * portfolio_variance)
```

L714（`BlackLittermanOptimizer` 结束）后插入：

```python
class KellyOptimizer(BaseOptimizer):
    """矩阵式凯利（opt-in；组合层，非 sizing 层对角近似）。

    目标 ``max μᵀw − (1/fraction)·wᵀΣw``，复用 ``_solve_mean_variance`` 的
    长多/箱体/upper/empty 语义。与 ``SizingConfig.method="kelly"``
    （P-047 逐标的 μ/σ² 缩放）**层次不同**，两者可独立启用。
    """

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        if returns is None:
            raise ValueError("凯利优化需要收益率数据（μ）")
        selected = self._select(factor_scores)
        n = len(selected)
        feas = _precheck(n, self.cfg, "kelly")
        if feas.kind == "empty":
            return self._empty_result("kelly")
        if feas.is_upper:
            return _upper_result(self.cfg, selected, "kelly")
        expected = returns[selected].mean()
        cov = self._cov_for(selected, returns, cov_matrix)
        return _solve_mean_variance(
            expected,
            cov,
            self.cfg,
            selected,
            "kelly",
            feas=feas,
            risk_aversion=1.0 / self.cfg.kelly.fraction,
        )
```

### 3.5 T5：`MaxSharpeOptimizer`

Kelly 后插入：

```python
class MaxSharpeOptimizer(BaseOptimizer):
    """最大夏普（Charnes-Cooper 变换；对齐 pypfopt 1.5.5，A30）。

    变换：``y = k·w, k = 1/((μ−rf)ᵀw)``；求解
    ``min yᵀΣy s.t. (μ−rf)ᵀy=1, Σy=k≥0, y∈[min·k, max·k]``，再 ``w=y/k``。
    """

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        if returns is None:
            raise ValueError("max_sharpe 需要收益率数据（μ）")
        selected = self._select(factor_scores)
        n = len(selected)
        feas = _precheck(n, self.cfg, "max_sharpe")
        if feas.kind == "empty":
            return self._empty_result("max_sharpe")
        if feas.is_upper:
            return _upper_result(self.cfg, selected, "max_sharpe")
        expected = returns[selected].mean()
        rf = float(self.cfg.max_sharpe.risk_free_rate)
        if float(expected.max()) <= rf:
            raise ValueError(
                "max_sharpe 要求至少一个资产期望收益高于无风险利率: "
                f"max(mu)={float(expected.max()):.6f} <= rf={rf:.6f}"
            )
        cov = self._cov_for(selected, returns, cov_matrix)
        excess = expected.to_numpy(dtype=float) - rf
        y = cp.Variable(n)
        k = cp.Variable()
        constraints = [
            excess @ y == 1,
            cp.sum(y) == k,
            k >= 0,
            y >= self.cfg.min_weight * k,
            y <= self.cfg.max_weight * k,
        ]
        problem = cp.Problem(
            cp.Minimize(cp.quad_form(y, cp.psd_wrap(cov.to_numpy(dtype=float)))),
            constraints,
        )
        problem.solve()
        if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or k.value is None:
            raise RuntimeError(f"max_sharpe 求解失败: solver status={problem.status}")
        k_val = float(k.value)
        if not np.isfinite(k_val) or k_val <= 0.0:
            raise RuntimeError(f"max_sharpe 反变换分母非法: k={k_val}")
        values = np.round(np.asarray(y.value, dtype=float).ravel() / k_val, 16) + 0.0
        weights = pd.Series(values, index=selected)
        return OptimizationResult(
            weights,
            "max_sharpe",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(weights.sum())),
        )
```

### 3.6 T6：行业上限投影（L846 后）

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
    """行业上限严格投影（引擎级；期货列固定不动）。

    ``min ‖w−w0‖² s.t. Σw=budget, 0≤w≤max_weight, Σ_{i∈g}w_i≤cap``。
    行业标签 NaN 或 0（``data.py`` 缺失填充）→ 未分类（参与调整但不计入组，
    仍受 max_weight）；不在 ``industry`` 索引的代码（期货）→ 原值保留。
    """
```

函数体按 DESIGN §5.5 实现；关键判定：

```python
    stocks = [c for c in weights.index if c in industry.index]
    ...
    labels = industry.reindex(stocks)
    is_unclassified = labels.isna() | labels.eq(0)
    ...
    if max_before <= float(cap) + _INDUSTRY_CAP_TOL:
        return IndustryCapResult(weights, False, len(groups), n_unclassified,
                                 max_before, max_before, 0.0)
    capacity = len(groups) * float(cap) + n_unclassified * float(max_weight)
    if budget > capacity + _INDUSTRY_CAP_TOL or (
        budget > len(stocks) * float(max_weight) + _INDUSTRY_CAP_TOL
    ):
        raise InfeasibleConstraintError(...)
    ...
    if problem.status in (cp.INFEASIBLE, cp.INFEASIBLE_INACCURATE):
        raise InfeasibleConstraintError(...)
```

返回值 `out = weights.copy(); out.loc[stocks] = np.clip(w.value, 0.0, max_weight)`——期货列**逐位不变**；`l1_deviation = Σ|w−w0|`。

### 3.7 T7：工厂与引擎接线

**工厂**（L890-L899）：

```python
        "kelly": KellyOptimizer,
        "max_sharpe": MaxSharpeOptimizer,
```

**引擎**（`core/engine_v2.py`）：

1. 导入（**L65**，现有 `from core.portfolio import OptimizationResult, build_optimizer, estimate_cov`）追加 `InfeasibleConstraintError, project_industry_cap`。
2. 模块常量（`_optimize_with_diagnostics` 之后）：

```python
_WARNING_ERROR_TYPES = {"zero_vol": "ZeroVariance", "erc_fallback": "RiskParityFallback"}
```

3. `__init__`（**L192** `_unclosed_positions` 后，F-6-2 修正行号）：`self._industry_cap_warned: bool = False`。
4. L1375 的 `error_type` 三元改为：

```python
                        error_type=_WARNING_ERROR_TYPES.get(
                            result.warning_kind or "", "InfeasibleConstraints"
                        ),
```

5. L1507（股票负权截断）后 / L1508（`build_target_positions`）前插入：

```python
        # P-046c B4d：行业上限（引擎级严格投影；期货/现金不受影响）
        industry_cap = self.cfg.optimizer.industry_max_weight
        if industry_cap is not None:
            industry_tags = self._industry_tags(date)
            if industry_tags is not None:
                try:
                    projection = project_industry_cap(
                        target_weights,
                        industry_tags,
                        cap=industry_cap,
                        max_weight=self.cfg.optimizer.max_weight,
                    )
                except InfeasibleConstraintError as exc:
                    self._diagnostics.record(date, "rebalance", exc)
                    self._emit(
                        EventType.ERROR,
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "stage": "rebalance",
                            "error_type": type(exc).__name__,
                            "message": str(exc)[: self._diagnostics.MAX_MESSAGE],
                        },
                    )
                    logger.error("行业上限投影不可行: %s", exc)
                    return
                target_weights = projection.weights
                if projection.applied:
                    logger.info(
                        "行业上限投影: groups=%d unclassified=%d max_group %.4f→%.4f L1=%.4f",
                        projection.n_groups,
                        projection.n_unclassified,
                        projection.max_group_before,
                        projection.max_group_after,
                        projection.l1_deviation,
                    )
```

6. `_execute_rebalance` 之后加助手：

```python
    def _industry_tags(self, date: pd.Timestamp) -> Optional[pd.Series]:
        """行业标签（P-046c）；整体缺失/日期缺失 → 一次性 warning 并返回 None。"""
        dm = self.dm
        table = getattr(dm, "industry", None) if dm is not None else None
        if table is None or date not in table.index:
            if not self._industry_cap_warned:
                logger.warning(
                    "industry_max_weight 已配置但行业数据不可用（date=%s），跳过行业上限",
                    date,
                )
                self._industry_cap_warned = True
            return None
        return table.loc[date]
```

### 3.8 T8 / T9

T8 见 §6；T9 为 PROGRESS 主行 + 下一可用序号分节 + DESIGN/RESEARCH 状态链回填（Step 9 完成后）。

---

## 4. 社区源码证据锚点与对拍边界

### 4.0 取证降级链

| 通道 | 结果 |
|---|---|
| 主通道：PyPI 指定版本 wheel（`%TEMP%\p046b_pkgs`，P-046b 已落） | **成功**：pypfopt 1.5.5 / skfolio 1.14.4 / riskfolio-lib 7.4.1 源码逐字读取 |
| 数值对拍：pypfopt 1.5.5（venv 直接 import 临时路径） | **成功**（§4.2） |
| 数值对拍：riskfolio-lib 7.4.1 | **失败**：`ModuleNotFoundError: No module named 'arch'`（riskfolio 可选依赖；**不安装**，零新依赖）→ 降级为源码级锚点 |
| 数值对拍：skfolio 1.14.4 | 未执行：其协方差由 `prior_estimator` 从收益样本估计，与注入 Σ 口径不同；仅源码级锚点 |
| 未取证声明 | GitHub commit hash 未取（wheel 为 PyPI 发布物）；不引「master 分支」结论 |

### 4.1 锚点表（源码级，T1）

| ID | 来源（版本可解析） | 文件 / 行 | 逐字要点 | 用途 |
|---|---|---|---|---|
| **A27** | skfolio **1.14.4** | `optimization/convex/_risk_budgeting.py` L30-L41 | `min Risk(w) s.t. budgetᵀlog(w) ≥ 0, 1ᵀw = s, Aw ≤ s·b, w ≥ 0` | D4 模型形状（**尺度为自由变量**） |
| **A27b** | 同上 | L653-L666 | `w = cp.Variable(n)`；`factor = cp.Variable()`；`constraints = [risk_budget @ cp.log(w) * self._scale_constraints >= 0]` | **不钉死 Σw=1** 的直接证据 |
| **A27c** | 同上 | L640-L650 | `risk_budget=None → np.ones(n)`；`np.where(risk_budget == 0, 1e-10, risk_budget)` | 零预算处置分歧（本仓 ValueError） |
| **A28** | Riskfolio-Lib **7.4.1** | `src/Portfolio.py` L3465-L3493（`rp_optimization` docstring） | `min φ(w) s.t. bᵀlog(w) ≥ c, μw ≥ μ̄, Aw ≤ b, w ≥ 0` | D4 第二源码锚点（无 Σw=1） |
| **A28b** | 同上 | L3626、L4333-L4335 | `k = cp.Variable((1,1))`；`cp.sum(w) * 1000 == k * 1000` | 尺度由变量 k 承载（Sharpe 时更明显） |
| **A28c** | 同上 | L1991-L1995、L2145-L2157 | `kelly : None / "approx" / "exact"`；approx = `mu @ w − 0.5·g²`；exact = `mean(log(1 + r·w))` | 凯利实现谱系（本仓取 approx 家族） |
| **A29** | skfolio **1.14.4** | `optimization/convex/_mean_risk.py` L152-L155 | `risk_aversion : Risk aversion factor λ ... only used for MAXIMIZE_UTILITY` | 风险厌恶参数语义 |
| **A29b** | 同上 | L1554-L1560 | `MAXIMIZE_UTILITY`：`Maximize(expected_return − risk_aversion·risk ...)` | D8 效用函数同式 |
| **A29c** | 同上 | L1561-L1575 | `MAXIMIZE_RATIO` + `np.max(mu) − risk_free_rate ≤ 0` → `ValueError` | D10 退化守卫同口径 |
| **A30** | PyPortfolioOpt **1.5.5** | `efficient_frontier/efficient_frontier.py` L253-L292 | `objective = quad_form(w, Σ)`；`(μ−rf)ᵀw == 1`；`sum(w) == k`；`k ≥ 0`；约束按 k 缩放；`weights = (w/k).round(16) + 0.0` | D10 变换逐式对齐 |
| **A31** | PyPortfolioOpt **1.5.5** | `objective_functions.py` L140-L163 | `quadratic_utility: μ − ½δ·wᵀΣw`；`risk_aversion` 为 cp.Parameter；`δ>0` 校验（L312-L313） | Kelly 的 δ/2 因子与 λ=δ/2 换算 |
| **A32** | PyPortfolioOpt **1.5.5** | `base_optimizer.py` L366-L403 | `add_sector_constraints`：`cp.sum(w[is_sector]) <= sector_upper` / `>= sector_lower` | 行业上限社区口径（in-solver） |
| **A33** | skfolio **1.14.4** | `optimization/convex/_base.py` L392-L409 | `groups` 定义资产组；`left_inequality/right_inequality` 即 `A·w ≤ b` | 组约束矩阵口径 |
| **A34** | Riskfolio-Lib **7.4.1** | `src/ConstraintsFunctions.py` L34-L69 | `assets_constraints` 生成 `Aw ≤ B` | 组约束矩阵口径（第二源） |
| **A35** | PyPortfolioOpt **1.5.5** | `objective_functions.py` L168-L183、L186-L202 | `transaction_cost = k·‖w−w_prev‖₁`；`ex_ante_tracking_error=(w−w_b)ᵀΣ(w−w_b)` | P-046d 边界（本批**不实现**） |
| **A36** | Riskfolio-Lib **7.4.1** | `src/Portfolio.py` L109-L111 | `kindbench`（True=基准权重组合 / False=指数） | P-046d TE 输入口径 |

### 4.2 跨实现对拍读数（本步实跑）

| 项 | 外部实现 | 本仓口径 | 结论 |
|---|---|---|---|
| max_sharpe（S5 + μ5 + rf=0.02 + max=0.6） | pypfopt 1.5.5：`[0.16454505, 0.47814413, 0.34545144, 0, 0.01185938]` | Charnes-Cooper 同式：max\|diff\| = **5.55e-17** | **逐位一致** |
| 预算 ERC（b=[0.4,0.3,0.15,0.1,0.05]，S5） | — | `min 0.5wᵀΣw s.t. w≥0, bᵀlog w≥0` → RC max\|diff\| = **5.67e-05** | 与 E2 复算一致 |
| 同上**加** `Σw=1` | — | cvxpy `status=infeasible` | **D4 强化证据**（F-5-1） |
| riskfolio `rp_optimization` 数值对拍 | 不可执行（缺 `arch`） | — | 降级为源码锚点（A28/A28b） |

> **F-5-1（D4 论证强化）**：DESIGN D4 原以 KKT 中 `ν` 项说明「加 Σw=1 会破坏 RC∝b」；Step 5 探针进一步证明 **n≥2 时 `bᵀlog w ≥ 0` 与 `Σw=1` 直接不可行**（加权几何平均 ≤ 算术平均 = 1，等号仅全 1）。落地判据：`_solve_risk_budget_convex` 禁止加 Σw=1，且 Step 9 用例 A8 以 RC 误差 <1e-3 机械验证。

### 4.3 与本仓设计的分歧登记（有意为之）

| 面 | 本仓（DESIGN/IMPL） | 社区实现 | 裁决依据 |
|---|---|---|---|
| 风险预算尺度 | 无 `Σw` 约束，解后归一 | skfolio `1ᵀw=s`（s 自由）；riskfolio `sum(w)=k`（k 自由） | D4；本仓归一后等价 |
| 零风险预算 | `b_i=0 → ValueError` | skfolio 将 0 夹到 `1e-10` | 本仓要求全正预算（D7；O-4-2 观察） |
| 凯利形式 | 二次效用 `max μᵀw − λwᵀΣw`（λ=1/f） | riskfolio `"exact"` = `mean(log(1+r·w))` | 本批取 approx 家族（A28c）；exact 需情景数据，延后 |
| 行业上限 | 引擎级**严格投影**（后处理） | 三家均 in-solver 线性约束（A32-A34） | B4d：E8 精确 + E12 改动面 1 vs 7；docstring 声明非 in-solver 最优 |
| 行业上限小样本 | 无组约束时 early no-op（逐位不变） | in-solver 恒生效 | D16；零漂移优先 |
| max_sharpe upper | `_upper_result`（各 max + 现金） | pypfopt 有 `weight_bounds` 但**无 upper 型不可行语义**（其 `Σw=1` 经 k 变换恒成立，不留现金） | U6；与 U1-A 一致 |

> **对拍边界（Step 9/10 必须遵守）**：pypfopt 自动对拍仅覆盖 **max_sharpe（给定 Σ/μ/rf/箱体）**；不得把 pypfopt 加入依赖或 CI。ERC 对拍以 skfolio/riskfolio **公式形状**为准（源码锚点），数值以 cvxpy 独立重解为准（E1/E2）。

### 4.4 学术锚点（B 级，书目级；未取全文，仅佐证不替代源码锚点）

| ID | 文献 | 支撑点 | 使用边界 |
|---|---|---|---|
| **B9** | Spinu, F. (2013). *An Algorithm for Computing Risk Parity Weights*. SSRN 2297383. | 风险预算的凸形式 `min ½wᵀΣw s.t. bᵀlog w ≥ c` 及唯一性 | 支撑 D4 模型形状；数值仍以 A27/A28 + 本仓探针为准 |
| **B10** | Charnes, A., Cooper, W. W. (1962). *Programming with Linear Fractional Functionals*. Naval Research Logistics Quarterly 9(3-4). | 线性分式规划 → 凸变换（max_sharpe 的 `y=kw` 来源） | 支撑 D10；实现逐式对齐 A30 |
| **B11** | Boyd, S., Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press, §8.1（投影到凸集）. | 「最近点投影」定义与唯一性（严格凸二次目标 + 凸可行域） | 支撑 D12/D13 的 `min‖w−w0‖²` 投影语义；无对应开源实现可锚 |
| **B12** | MacLean, L. C., Thorp, E. O., Ziemba, W. T. (2011). *The Kelly Capital Growth Investment Criterion: Theory and Practice*. World Scientific. | 凯利准则的期望对数增长目标与分数凯利 | 支撑 D8 的目标族谱；本批取二次近似（A28c） |
| **B13** | Maillard, S., Roncalli, T., Teïletche, J. (2010). *The Properties of Equally Weighted Risk Contribution Portfolios*. JPM 36(4). | ERC 解存在性/唯一性（正定 Σ、w>0） | 支撑 I3；退化分支（零方差）由 D3 显式处理 |
| **B14** | Roncalli, T. (2013). *Introduction to Risk Parity and Budgeting*. Chapman & Hall/CRC. | 风险预算向量 b 与 log-barrier 的等价性 | 支撑 D4/D7；riskfolio docstring 直接引用（A28） |
| **B15** | Jagannathan, R., Ma, T. (2003). *Risk Reduction in Large Portfolios: Why Imposing the Wrong Constraints Helps*. JF 58(4). | 约束（含行业上限/长多）作为收缩、降低估计误差 | 支撑 B4d 的「约束有益」定位（不作为实现断言） |

> **口径**：A 级 = 本轮逐字读取 wheel 源码（可复现行号）；B 级 = 标准书目，**未取全文**，不得单独支撑实现决策；实现决策至少需 A 级 + 本地探针双证（本批：A27-A36 + §4.2 读数 + E1-E8）。

---

## 5. 低效排除表（规范硬约束，非空）

| 候选方案 | 排除原因 | 采用方案 |
|---|---|---|
| `Σ⁻¹μ` 直接归一作凯利 | 50A 实测 22 个负权重、`max\|w\|=13.36`、cond 3.78e3（E3）；裁剪会破坏最优性 | 带箱体的凸 QP（`_solve_mean_variance`） |
| 乘性迭代直接扩非均匀预算 | E2 实测产生负权重（`[-1.52, -0.07]`） | 非均匀预算直走凸解（D3） |
| 凸 ERC 加 `Σw=1` | n≥2 时与 `bᵀlog w≥0` **不可行**（F-5-1 实证） | 只加 `w≥0`，解后归一 |
| 行业上限后处理「截断+归一」 | E5/E8：组和 0.5154>0.4、+0.0905/+0.0709 违反 | 严格 QP 投影 |
| 行业上限改 7 个优化器签名（in-solver） | E12 改动面 7 vs 1；EW/RP/HRP 无目标函数 | 引擎级单插入点 |
| 每次投影前查全表行业 | `dm.industry` 懒加载 + 全表 reindex 成本 | `table.loc[date]` 一次 |
| cap 未绑定时仍解 QP | 每日 cvxpy 开销无收益 | early no-op（逐位返回原 Series） |
| 用 `np.linalg.inv` 求 max_sharpe 闭式 | 长多下闭式含负权重（E4 复算 −0.1385） | Charnes-Cooper QP |
| 把 riskfolio/skfolio 设为依赖做对拍 | 缺 `arch` 等可选依赖；改锁与 CI | 源码锚点 + 手工对拍 |
| 每日记录行业投影为 `warning_kind` 新枚举 | 污染诊断词表（U11） | `logger.info` 四数 + 不新增字段 |
| 按组 Python 循环逐资产求和 | G×N 次解释器循环 | 布尔索引 + `cp.sum(w[mask])` |
| `weights.apply` 逐值 clip | O(N) 解释器开销 | numpy 向量化 |

---

## 6. 测试先行计划（红 → 绿）

### 6.1 红态（先写）

先落 3 个测试文件，运行：

```powershell
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest tests/test_p046c_erc_budget.py tests/test_p046c_kelly_sharpe.py tests/test_p046c_industry_cap.py -q
```

**预期红读数**：`ImportError: cannot import name 'KellyOptimizer'`（或 `project_industry_cap` / `KellyConfig`）→ 收集失败；记录到 Step 9 日志。

### 6.2 用例映射（39 例）

| 文件 | # | 用例 | 断言要点 | 对应设计 |
|---|---|---|---|---|
| `test_p046c_erc_budget.py` | 1 | `test_erc_negative_corr_two_asset_recovers_inverse_vol` | `[0.6,0.4]`±1e-4；RC≈0.5±1e-3 | I2 |
| | 2 | `test_erc_negative_corr_emits_fallback_diagnostic` | `message.startswith("erc_fallback:")`；`warning_kind=="erc_fallback"` | D3/D5 |
| | 3 | `test_erc_five_asset_random_spd_rc_equal` | S5；RC 各 0.2±1e-3；`max\|w−0.2\|>0.1` | I3 |
| | 4 | `test_erc_equicorr_fast_path_zero_drift` | 等相关；`message==""`；权重参考 ±1e-5 | D2 |
| | 5 | `test_erc_sample_cov_fast_path_rc_equal` | 20A；RC 各 0.05±1e-3；message 空 | I12 |
| | 6 | `test_erc_max_iter_exhausted_falls_back` | 等相关构型 + max_iter=1, tol=1e-12；`erc_fallback:max_iter`；RC 仍 0.2（**F-S9-P046c-1**：S5 等权起点负 RC 使②先于③触发，改用等相关构型） | D3③ |
| | 7 | `test_erc_partial_zero_variance_keeps_equal_weight_zero_vol` | diag(0.04,0.09,0)；`[1/3]*3`；`zero_vol` | D3/F-4-1 |
| | 8 | `test_erc_budget_matches_target_rc` | b=[0.4,0.3,0.15,0.1,0.05]；RC≈b±1e-3 | I4 |
| | 9 | `test_erc_budget_extra_keys_dropped` | 未知键 warning；结果正常 | D7 |
| | 10 | `test_erc_budget_missing_filled_with_remainder` | 指定 2 只和 0.7；其余各 0.1 | D7 |
| | 11 | `test_erc_budget_all_covered_must_sum_one` | 全覆盖和 0.9 → `ValueError` | D7 |
| | 12 | `test_erc_budget_negative_rejected` | 负预算 → `ValueError`（配置期） | D7/T1 |
| | 13 | `test_erc_budget_no_match_uniform_fallback` | 键全不匹配；warning；RC 各 0.2 | D7 |
| | 14 | `test_optimizer_config_rejects_bad_industry_cap_and_budget_method` | cap=0/1.5；`equal_weight`+risk_budget → `ValueError` | D17/T1 |
| `test_p046c_kelly_sharpe.py` | 1 | `test_kelly_50a_long_only_invariants` | E3 50A；`w≥−1e-12`、Σw=1±1e-8、无 NaN | I5 |
| | 2 | `test_kelly_box_free_matches_closed_form` | 对角 Σ、fraction=0.5、max=1 → 闭式 ±1e-8 | I5 |
| | 3 | `test_kelly_fraction_maps_to_risk_aversion` | f=1 与 λ=1 等价；f=0.5 与 λ=2 等价 | D8 |
| | 4 | `test_kelly_config_fraction_bounds` | 0/1.5 → `ValueError` | D9 |
| | 5 | `test_kelly_upper_result` | n=5、max=0.1 → 各 0.1 + cash 0.5 | D21 |
| | 6 | `test_kelly_empty_result` | 空 scores → `empty` | D8 |
| | 7 | `test_kelly_requires_returns` | returns=None → `ValueError` | D8 |
| | 8 | `test_kelly_factory` | 工厂类名 | D18 |
| | 9 | `test_max_sharpe_matches_pypfopt_reference` | E4 参考 ±1e-6；Sharpe 1.385755±1e-6 | I6/A30 |
| | 10 | `test_max_sharpe_box_free_closed_form` | 对角 Σ、rf=0.02、max=1 → 闭式 ±1e-8 | I6 |
| | 11 | `test_max_sharpe_rejects_no_excess_return` | max(μ)≤rf → `ValueError` | D10 |
| | 12 | `test_max_sharpe_upper_result` | n=5、max=0.1 → upper | D21 |
| | 13 | `test_max_sharpe_requires_returns` | returns=None → `ValueError` | D10 |
| | 14 | `test_max_sharpe_config_rf_validation` | `nan` → `ValueError` | D11 |
| | 15 | `test_max_sharpe_factory` | 工厂类名 + 未知 method 报错集含新键 | D18 |
| `test_p046c_industry_cap.py` | 1 | `test_projection_n100_hits_cap_exactly` | E8 100/10/0.12；cap 精确、Σ=1、L2=0.1522±1e-3 | I7 |
| | 2 | `test_projection_n500_hits_cap_exactly` | E8 500/20/0.08；L2=0.1244±1e-3 | I7 |
| | 3 | `test_projection_noop_when_caps_binding_free` | 逐位相等、`applied is False` | D16 |
| | 4 | `test_projection_infeasible_raises` | 2 组 cap=0.2、budget=1 → `InfeasibleConstraintError` | D15 |
| | 5 | `test_projection_unclassified_stocks_excluded` | 0/NaN 各 1 只；`n_unclassified==2`；组和 ≤cap | D14 |
| | 6 | `test_projection_empty_and_zero_budget_noop` | 空/零预算 → 原样 | §5.5 |
| | 7 | `test_projection_preserves_non_stock_columns` | 期货 `IF0001` 逐位不变 | D13/I7 |
| | 8 | `test_projection_enforces_max_weight` | max=0.3、w0 含 0.5 → 解后 ≤0.3 | D13 |
| | 9 | `test_engine_applies_industry_cap` | 4 股/3 行业、max=0.5、cap=0.4；捕获权重 A 组 0.4、B/C 0.3 | D12/T7 |
| | 10 | `test_engine_industry_cap_none_is_noop` | 同构型 `None` → `[0.25]*4` | I1 |

### 6.3 固定构型（测试常量，同 DESIGN §8.4）

```
S5：rng=default_rng(1)；m~N(0,1)^(5,5)；S=diag(linspace(0.15,0.35,5))@(m@m.T/5+0.01I)@diag(...)
μ5=[0.08,0.06,0.05,0.04,0.03]；rf=0.02；max_weight=0.6（max_sharpe 参考）
E7 等相关：vols=linspace(0.2,0.4,5)、ρ=0.3；scores=arange(5,0,-1)
E7 样本 20A：rng=default_rng(2026)；X=0.7·N(0,0.01)^(60,1)+N(0,0.008)^(60,20)
E3 50A：rng=default_rng(7)；S50=m@m.T/50+1e-4I；μ50~N(0.05,0.02)^50
对角构型：Σ=diag(linspace(0.2,0.4,5)²)
```

### 6.4 O-4-1 联测探针（**不计入 39 例**，Step 9 手工执行）

Step 9 额外执行一次性脚本（不入库、不进 pytest）：构造 `sizing.vol_target` 放大权重 + `industry_max_weight` 绑定 → 验证投影把个别超 `max_weight` 的权重压回，且组和 ≤cap；读数记入 Step 9 日志。目的：闭合 Step 4 O-4-1，不改变门禁数字。

---

## 7. 门禁命令与预期

```powershell
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q          # 1502 passed / 1 skipped（collect 1503）
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q -k p046  # 117 passed
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q -k golden # 22 passed（零重录）
$env:MPLBACKEND='Agg'; .venv\Scripts\python.exe -m pytest -q -k p054  # 120 passed
.venv\Scripts\python.exe -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples live services  # 160 files / 0
.venv\Scripts\python.exe -m black --check .                            # 325 files
.venv\Scripts\python.exe -c "import ast,pathlib;r=pathlib.Path('.');s=[p for d in ['agents','filter','scripts','batch_backtest','strategy_evaluation'] for p in (r/d).rglob('*.py')]+[r/'cli.py'];print(sum(1 for p in s if p.exists() for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='Exception'))"  # 22（core 30）
lint-imports                                                          # 3 kept
uv lock --check                                                       # exit 0
```

| 指标 | 基线 @`3495683` | P-046c 目标 |
|---|---|---|
| collect / 全量 | 1464 / 1463+1 | **1503 / 1502+1** |
| `-k p046` | 78 | **117** |
| golden | 22 | **22（零重录）** |
| `-k p054` | 120 | **120** |
| mypy | 160·0 | **160·0** |
| black | 322 | **325**（+3 测试文件） |
| AST | 22·30 | **22·30** |
| lint / lock | 3 kept / 0 | **3 kept / 0** |
| 文件计数 | 158·51·19·13 | **161·51·19·13** |

---

## 8. 风险与回退

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 凸 ERC 在个别协方差上 `OPTIMAL_INACCURATE` 且 RC 偏差 >1e-3 | 中 | A8 失败 | 状态接受 INACCURATE；RC 断言失败时收紧求解器参数或改用 CLARABEL 显式指定（不改模型） |
| `labels == 0` 在 object 列产生 FutureWarning | 低 | 告警噪声 | 用 `labels.isna() \| labels.eq(0)`（`eq` 不比字符串/整数混合） |
| 引擎 mock DM 无 `industry` 属性 | 中 | 新引擎用例失败 | `getattr(dm, "industry", None)` 已兜底；测试显式提供 DataFrame |
| 投影 `cp.sum_squares` 在 N=5000 变慢 | 低 | 回测慢 | opt-in；E8 500→0.022s；不设 SLO（D20/§10） |
| `np.round(..., 16)` 在 max_sharpe 反变换引入 -0.0 | 低 | 断言边界 | `+ 0.0` 归零（A30 同式）+ 断言用 `>= -1e-12` |
| 新增配置字段破坏旧 JSON 回灌 | 低 | 配置加载失败 | 全部带默认值；`risk_budget/kelly/max_sharpe` 可选 |
| 工厂新增键影响未知 method 报错集 | 中 | 既有断言（若有）失败 | 既有断言是 `ValueError` 且未列举键集；`-k p046` 回归验证 |
| 测试红态因导入顺序阻塞其它用例 | 低 | 收集失败 | 红态仅跑新 3 文件；全量在绿后 |

---

## 9. 派生需求登记（Step 5）

| ID | 派生需求 | 理由 | 落点 |
|---|---|---|---|
| **F-5-1** | D4 论证强化：`Σw=1` 与 `bᵀlog w≥0` 对 n≥2 **不可行**（非仅 KKT 失真） | Step 5 探针 `status=infeasible` | DESIGN D4 注记 + §3.2 docstring |
| **F-5-2** | Kelly `fraction` 与 pypfopt δ 的换算登记：`λ=1/f`，pypfopt `δ=2λ=2/f` | 防 Step 6 误判「fraction 语义错误」 | DESIGN D8 注记 + `KellyConfig` docstring |
| **F-5-3** | riskfolio 数值对拍降级（缺 `arch`）；ERC 仅源码锚点 + cvxpy 独立重解 | 零新依赖约束 | §4.0/§4.2 已记录 |

---

## 10. 状态链

- **2026-11-23**：Step 5 IMPL 落盘（本文）——T1-T9 任务拆解；接口签名 14 项 + 回退点；源码级锚点 A27-A36 + 学术锚点 B9-B15；跨实现读数（pypfopt max_sharpe **5.55e-17**；`Σw=1` 不可行）；低效排除 12 行；39 例红→绿计划；门禁命令与目标（1503/117/22/120/160·0/325/22·30/3 kept/0/161·51·19·13）；派生需求 F-5-1..F-5-3；零代码变更 / 未提交。
- **2026-11-23**：**Step 6 异构复审 PASS**（[REVIEW_p046c_step5_impl](REVIEW_p046c_step5_impl.md)，GLM-5.3-Flash ≠ 作者）——规范两大硬约束全过（版本可解析 + 12 新符号 grep **0 冲突**）；锚点 **16/16** 机械命中；D↔T↔39 例无悬空；门禁算术复核全过；骨架缩进正确（fallback 重算在 else 内，不覆盖预算解）；**3 P3 当轮全修**：F-6-1（§3.3 行号区间重叠 L736-L764→L736-L756）、F-6-2（引擎行号精度：导入 L65 / 属性 L192）、F-6-3（`labels.eq(0)` 统一）+ 2 观察当轮措辞修正（T9 序号 / pypfopt upper 措辞）；门禁目标维持不变；本文修订已落字；零代码变更 / 未提交。
- **下一步**：Step 7 CHECKLIST（A-J 组，实测列 0 预填）。
- **2026-11-23**：**Step 7 CHECKLIST 落盘**（[CHECKLIST_p046c_f2_closeout](CHECKLIST_p046c_f2_closeout.md)）——80 项（A 8 / B 9 / C 7 / D 7 / E 7 / F 9 / G 8 / H 10 / I 9 / J 6）；T1-T9 全部有验收项；门禁目标冻结与本文 §7 一致；实测列 0 预填（77/2/1，RULE-1）；零代码变更 / 未提交。
- **2026-11-23**：**Step 8 一致性复审 PASS**——机械校验器 v3 **124/124**（初跑 v1 117/124：4 校验器正则/切分误报 + 2 文档 P3 当轮修——本文 §3.3 L278 补 `# F-4-2：zero_vol break 不误判 max_iter` 标签注释、CK N7 补「不进 CI、不装依赖」；复跑 v2 122/124：1 连写正则误报 + 1 CK 用例引用缺口当轮修——CK A1/A3/A4 补用例 B4/A14）；J1/J5 回填 ✅；详见 [CHECKLIST_p046c_f2_closeout §14](CHECKLIST_p046c_f2_closeout.md)。零代码变更 / 未提交。
- **2026-11-23**：**Step 9 TDD PASS**——T1-T7 全部落码（`config.KellyConfig/MaxSharpeConfig/risk_budget/kelly/max_sharpe` + 校验；`portfolio._risk_budget_vector/_solve_risk_budget_convex/RP 改造/KellyOptimizer/MaxSharpeOptimizer/IndustryCapResult/project_industry_cap/工厂 2 键`；`engine_v2._WARNING_ERROR_TYPES/_industry_cap_warned/_industry_tags/插入块`）；红态 2 收集错误 → 绿态 **39 passed**；门禁全命中（1502+1 / 117 / 22 / 120 / 160·0 / 325 / 161·51·19·13 / 22·30 / 3 kept / 0）；派生 **F-S9-P046c-1**（本表 §6.2 A6 注记）；O-4-1 探针闭合；详见 [CHECKLIST_p046c_f2_closeout §15](CHECKLIST_p046c_f2_closeout.md)。未提交。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS**（[CHECKLIST_p046c_f2_closeout §16](CHECKLIST_p046c_f2_closeout.md)，GLM-5.3-Flash ≠ 实施者）——门禁独立重放 10/10 全绿；T1-T7 落码对 D1-D22 分组核验全过；探针独立重写重放 8/8；**0 P0-P2 + 1 观察 O-R5-P046c-1**。未提交，待用户授权（J6）。
- **2026-11-23**：**用户授权提交 + 批次关闭**——`6ac07eb`（16 files +4011/−27）+ CI run `45187900624` 四 job 全绿；CHECKLIST **80/80 ✅**；T1-T9 全部完成（T8/T9 台账随 Step 9/10 回写）。
- **P-046c 批次关闭（Step 1-10 全通过）**。
