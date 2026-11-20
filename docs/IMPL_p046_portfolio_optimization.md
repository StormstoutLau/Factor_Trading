# IMPL P-046 组合优化语义修复（P-046a · Step 5 实施文档）

> **批次**: P-046a · **Step 5 实施规格**
> **上游**: [DESIGN_p046](DESIGN_p046_portfolio_optimization.md)（含 Step 4 复审 F-D-1/2/3 已回填）+ [RESEARCH_p046](RESEARCH_p046_portfolio_optimization.md)（§10.1 裁决 / §15 AC / §16-§17 复审）
> **代码基线**: HEAD `b5f69a7`；`932 passed` / golden 18 / mypy 111 files / black `149·218`
> **作者**: DeepSeek-V4.1-Flash（Step 6 复审须异构）
> **性质**: 实施指南——函数签名、代码骨架、行号锚点（均为 @`b5f69a7`，改动后失效）、验收命令；**不含**已完成代码

---

## 1. 实施总览

### 1.1 任务与依赖

| 任务 | 内容 | 依赖 | 规模 |
|---|---|---|---|
| **T1** | `portfolio.py` 类型层：`InfeasibleConstraintError` / `OptimizationResult` / `_Feasibility` / `_precheck` / `_scale_to_budget` | — | ~90 行 |
| **T2** | `estimate_cov` 统一入口 + sklearn LW + PSD 兜底；删除 `_ledoit_wolf_shrinkage` | T1 | ~70 行（净 +30） |
| **T3** | `_apply_constraints` 改为投影；保留 `_apply_constraints_legacy` | T1 | ~25 行 |
| **T4** | 四优化器改 `optimize_with_diagnostics` + U1 分支 + MVO 注入修复（F-D-8） | T1-T3 | ~130 行 |
| **T5** | `core/config.py` `__post_init__` | — | +18 行 |
| **T6** | `engine_v2` 单次算 Σ + 注入 + 诊断分流 + **`diagnostics` 三件套扩展** | T2/T4 | +35 行（含 `diagnostics.py`） |
| **T7** | 3 个测试模块 + 5 处既有测试处置 | T1-T6 | ~330 行 |

**依赖序**：T1 → T2 → T3 → T4 → (T5 ∥ T6) → T7

### 1.2 文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `core/portfolio.py` | 改 | 主体（T1-T4）；行号锚点见各节 |
| `core/config.py` | 改 | `OptimizerConfig.__post_init__`（L297 后） |
| `core/engine_v2.py` | 改 | L1082-1099（optimize 调用 + 异常分流）、L1104-1109（overlay 注入） |
| `core/diagnostics.py` | 改 | T6 三件套：`DayErrorRecord.detail` / `record_detail` / `classify_day_error` config 分支 |
| `tests/test_p046_constraints.py` | **新建** | AC-C / AC-B1 / AC-B2 |
| `tests/test_p046_cov.py` | **新建** | AC-C-01c / PSD / NaN / EWMA |
| `tests/test_p046_engine.py` | **新建** | 选项 i / strategy 路径 / 诊断落账 / NaN 窗口 |
| `tests/test_p023_*` `test_p025_*` `test_p026_*` | 改 | 5 处 `target_count=2` 构造点显式 `max_weight` |

### 1.3 建议提交粒度

`T1+T2`（类型与协方差）→ `T3+T4`（投影与优化器）→ `T5+T6`（配置与接线）→ `T7`（测试）。每段可独立 `pytest -q` 通过；**任一段失败不得进入下一段**。

---

## 2. T1：类型层（`core/portfolio.py` 模块头，L23 后）

```python
from dataclasses import dataclass
from typing import Any, Literal, Optional

from sklearn.covariance import LedoitWolf

__all__ = [
    "COV_ESTIMATORS", "estimate_cov", "InfeasibleConstraintError",
    "OptimizationResult", "BaseOptimizer", "EqualWeightOptimizer",
    "MinVarianceOptimizer", "MeanVarianceOptimizer", "RiskParityOptimizer",
    "build_optimizer", "round_lot_optimize",
]

_FEAS_TOL = 1e-12


class InfeasibleConstraintError(ValueError):
    """约束系统不可行（U1-B 运行时 / U1-D 配置期）。继承 ValueError 保持既有捕获兼容。"""


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


@dataclass(frozen=True)
class _Feasibility:
    kind: Optional[str]          # None | "upper" | "lower" | "empty"
    budget: float = 1.0

    @property
    def is_upper(self) -> bool:
        return self.kind == "upper"


def _precheck(n: int, cfg: OptimizerConfig, method: str) -> _Feasibility:
    """U1 分型（DESIGN §2.3）。n 必须为「选股后真实标的数」；method 用于诊断消息（AC-B1-01）。"""
    if n == 0:
        return _Feasibility("empty", 1.0)
    sum_max = n * cfg.max_weight
    sum_min = n * cfg.min_weight
    if sum_min > 1.0 + _FEAS_TOL:            # U1-B：下限不可满足
        raise InfeasibleConstraintError(
            f"约束不可行(U1-B): method={method}, n={n}, max_weight={cfg.max_weight}, "
            f"min_weight={cfg.min_weight}, sum_min={sum_min:.12f} > 1, "
            f"required_max_weight<=1/n={1.0 / n:.12f}, sum_max={sum_max:.12f}"
        )
    if sum_max < 1.0 - _FEAS_TOL:            # U1-A：上限不可满足
        return _Feasibility("upper", sum_max)
    return _Feasibility(None, 1.0)


def _scale_to_budget(
    w: pd.Series, lo: float, hi: float, budget: float = 1.0,
    tol: float = 1e-12, max_iter: int = 60,
) -> pd.Series:
    """保持相对比例，二分 s 使 Σ clip(s·w, lo, hi) == budget（DESIGN §4.2）。"""
    if len(w) == 0:
        return w
    base = w.clip(lower=lo, upper=hi)
    if abs(float(base.sum()) - budget) <= tol:          # F-D-3 短路（AC-C-01a 契约）
        return base
    w_pos = w[w > 0]
    if w_pos.empty:
        return base
    s_hi = 1.0
    # doubling：f(s) = Σ clip(s·w, lo, hi) 单调不减
    for _ in range(max_iter):
        f = float((w_pos * s_hi).clip(lower=lo, upper=hi).sum()
                  + (len(w) - len(w_pos)) * lo)
        if f >= budget:
            break
        s_hi *= 2.0
    s_lo = 0.0
    for _ in range(max_iter):
        s_mid = 0.5 * (s_lo + s_hi)
        f = float((w_pos * s_mid).clip(lower=lo, upper=hi).sum()
                  + (len(w) - len(w_pos)) * lo)
        if f < budget:
            s_lo = s_mid
        else:
            s_hi = s_mid
    out = (w * s_hi).clip(lower=lo, upper=hi)
    # 非正分量固定为 lo，不参与缩放
    out[w <= 0] = lo
    return out
```

> **落笔注意**：`_scale_to_budget` 的 `f(s)` 计算须与 `downstream clip` 完全同式，否则终态断言 `|Σ−budget|≤1e-9` 失败；若 `w` 全为 0 → 走短路返回 `lo` 全填（`n·lo ≤ budget`）。

---

## 3. T2：协方差统一入口（替换 L26-L64）

### 3.1 删除与新增

- **删除** `_ledoit_wolf_shrinkage`（L33-L64）整函数；
- `COV_ESTIMATORS` 保留键，值改为「接收 ndarray」的函数：

```python
def _psd_project(cov: np.ndarray) -> np.ndarray:
    """对称化 + 特征值截断到 >= 0（G-P046-5 兜底）。"""
    sym = 0.5 * (cov + cov.T)
    vals, vecs = np.linalg.eigh(sym)
    vals = np.clip(vals, 0.0, None)
    return (vecs * vals) @ vecs.T


def _lw_cov(values: np.ndarray) -> np.ndarray:
    return LedoitWolf().fit(values).covariance_


def _sample_cov(values: np.ndarray) -> np.ndarray:
    return np.cov(values, rowvar=False) if values.shape[1] > 1 else np.array([[values.var(ddof=1)]])


def estimate_cov(
    returns: pd.DataFrame,
    method: str = "ledoit_wolf",
    codes: Optional[pd.Index] = None,
    psd_fix: bool = True,
) -> pd.DataFrame:
    """唯一协方差入口（C3 / G-P046-6）。NaN 走 listwise；有效行 <2 → 回退 sample。"""
    if method not in ("sample", "ledoit_wolf", "ewma"):
        raise ValueError(f"未知 cov_method: {method!r}；合法值: {sorted(COV_ESTIMATORS)}")
    clean = returns.dropna(how="any")
    if len(clean) < 2:
        logger.warning(f"estimate_cov: 有效样本 {len(clean)} < 2，回退 sample")
        clean = returns.fillna(0.0)
    vals = clean.to_numpy(dtype=float)
    if method == "ewma":
        cov = _ewma_covariance(clean).to_numpy()
    else:
        cov = {"sample": _sample_cov, "ledoit_wolf": _lw_cov}[method](vals)
    if psd_fix:
        cov = _psd_project(np.asarray(cov, dtype=float))
    out = pd.DataFrame(cov, index=clean.columns, columns=clean.columns)
    if codes is not None:
        out = out.reindex(index=codes, columns=codes).fillna(0.0)
        if psd_fix:
            out = pd.DataFrame(_psd_project(out.to_numpy()), index=out.index, columns=out.columns)
    return out
```

- `_ewma_covariance`（L67-L95）**保留原样**（仅被 `estimate_cov` 调用）。
- `COV_ESTIMATORS` 若仍被外部引用（grep: 仅 portfolio 内），改为 `frozenset({"sample", "ledoit_wolf", "ewma"})` 或保留 dict 映射 ndarray 函数；**Step 5 先 grep 全仓引用再定**。

### 3.2 自检

```powershell
.venv\Scripts\python.exe -c "import pandas as pd,numpy as np; from core.portfolio import estimate_cov; r=pd.DataFrame(np.random.default_rng(0).normal(0,.02,(60,5))); c=estimate_cov(r); print(np.linalg.eigvalsh(c.values).min(), abs(c.values-c.values.T).max())"
```

期望：最小特征值 `>= -1e-15`、对称差 `0.0`。

---

## 4. T3：约束投影（替换 L128-L146）

```python
    def _apply_constraints(self, weights: pd.Series, feas: Optional[_Feasibility] = None) -> pd.Series:
        """box∩预算 投影（DESIGN §4.2）。feas=None 视为可行域、budget=1。"""
        if len(weights) == 0:
            return weights
        if feas is not None and feas.is_upper:
            # B2：只截断、不归一化（AC-B2-01/02）
            return weights.clip(lower=self.cfg.min_weight, upper=self.cfg.max_weight)
        return _scale_to_budget(weights, self.cfg.min_weight, self.cfg.max_weight, budget=1.0)

    def _apply_constraints_legacy(self, weights: pd.Series) -> pd.Series:
        """@b5f69a7 旧实现，仅供 AC-C-01a 对照（不对外）。"""
        w = weights.clip(upper=self.cfg.max_weight)
        w = w.clip(lower=self.cfg.min_weight)
        return w / w.sum()
```

> **注意**：`_apply_constraints` 现有调用点仅 L187 / L389。改签名带默认值，不影响。

---

## 5. T4：四优化器

### 5.1 基类（L110-L126）

```python
    def optimize_with_diagnostics(
        self, factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        raise NotImplementedError("子类必须实现 optimize_with_diagnostics")

    def optimize(
        self, factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> pd.Series:
        return self.optimize_with_diagnostics(factor_scores, returns, cov_matrix).weights
```

### 5.2 公共辅助

```python
    def _result(self, w: pd.Series, n: int, feas: _Feasibility, msg: str = "") -> OptimizationResult:
        total = float(w.sum())
        return OptimizationResult(
            weights=w, method=type(self).__name__, n_selected=n,
            max_weight=self.cfg.max_weight, min_weight=self.cfg.min_weight,
            infeasible_kind=feas.kind, cash_residual=max(0.0, 1.0 - total), message=msg,
        )
```

### 5.3 EqualWeight（L152-L189 → 改名）

保留 L168-L181 选股逻辑，之后：

```python
        feas = _precheck(len(selected_stocks), self.cfg, "equal_weight")
        weights = pd.Series(1.0 / len(selected_stocks), index=selected_stocks)
        weights = self._apply_constraints(weights, feas)
        return self._result(weights, len(selected_stocks), feas)
```

空集分支（L172-L174）改为 `return OptimizationResult(pd.Series(dtype=float), type(self).__name__, 0, self.cfg.max_weight, self.cfg.min_weight, "empty", 1.0)`。

### 5.4 MinVariance（L195-L254）

在 L218 选股后、L220 取协方差前插入：

```python
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "min_variance")
        if feas.kind == "empty":
            return OptimizationResult(pd.Series(dtype=float), type(self).__name__, 0, ...)
        if feas.is_upper:                      # AC-B2-08：可行域单点 → 各 m
            w = pd.Series(self.cfg.max_weight, index=selected_stocks)
            return self._result(w, n, feas, msg="upper_infeasible_equal_cap")
```

协方差取用统一为：

```python
        if cov_matrix is None:
            assert returns is not None
            cov_matrix = estimate_cov(returns[selected_stocks], self.cfg.cov_method)
        else:
            cov_matrix = cov_matrix.loc[selected_stocks, selected_stocks]
```

求解后（L247-L249）**删除回退**：

```python
        if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(f"最小方差求解失败: status={problem.status}")
        return self._result(pd.Series(w.value, index=selected_stocks), n, feas)
```

### 5.5 MeanVariance（L260-L323，含 F-D-8 修复）

同 5.4 插入预检，但 **method 实参必须为 `"mean_variance"`**（AC-B1-01 要求消息含真实 method，Step 6 F-E-1）：

```python
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "mean_variance")
```

**协方差与预期收益分支必须重写**（原 L286-L293 会覆盖注入 Σ）：

```python
        if returns is not None:
            expected_returns = returns[selected_stocks].mean()
        else:
            expected_returns = pd.Series(0.0, index=selected_stocks)
        if cov_matrix is None:
            assert returns is not None
            cov_matrix = estimate_cov(returns[selected_stocks], self.cfg.cov_method)
        else:
            cov_matrix = cov_matrix.loc[selected_stocks, selected_stocks]
```

求解后删除回退（L316-L318），改为 `raise RuntimeError(...)`；成功返回 `self._result(pd.Series(w.value, index=selected_stocks), n, feas)`。

> **行为变化登记**：原「非最优 → 等权」改为抛出 → engine 记录 + emit + 当日跳过。方向与 G-P046-5 一致；若 T7 发现既有测试依赖等权回退，须在 CHECKLIST 记为语义修正（不得恢复静默回退）。

### 5.6 RiskParity（L329-L391）

选股后插入预检；`u1_b` 由 `_precheck` 抛；`u1_a` 走「迭代 → 只截断」：

```python
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "risk_parity")
        if feas.kind == "empty":
            return OptimizationResult(pd.Series(dtype=float), ...)
        if cov_matrix is None:
            assert returns is not None
            cov_matrix = estimate_cov(returns[selected_stocks], self.cfg.cov_method)
        else:
            cov_matrix = cov_matrix.loc[selected_stocks, selected_stocks]

        w0 = np.ones(n) / n
        vol0 = float(np.sqrt(w0 @ cov_matrix.values @ w0))
        if not np.isfinite(vol0) or vol0 <= 1e-18:      # G-P046-4
            w = pd.Series(1.0 / n, index=selected_stocks)
            return self._result(self._apply_constraints(w, feas), n, feas, msg="zero_vol")
```

迭代循环内保留 L366-L382，但**删除 L385 的归一化**（交给投影）；末尾：

```python
        weights_series = pd.Series(weights, index=selected_stocks)
        weights_series = self._apply_constraints(weights_series, feas)
        return self._result(weights_series, n, feas)
```

> **注意**：U1-A 时 `_apply_constraints(..., feas)` 只截断不归一 → `Σw = Σmin(w_i,m) ≤ n·m`，符合 AC-B2-03。

### 5.7 其他

- `round_lot_optimize`（L394-L424）**不改**（零调用，G-P046-7 归 P-053）。
- `build_optimizer`（L426-L447）**不改**。

---

## 6. T5：配置校验（`core/config.py`，L297 后）

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

> **不触碰** `config_v2`（FROZEN / TD-2）；`cov_shrinkage` 字段保留并加 `# deprecated: C1 后由 sklearn 自算`。

---

## 7. T6：engine 接线（`core/engine_v2.py`）

### 7.1 L1082-L1099

```python
                cov = None
                if returns_data is not None and len(returns_data) >= 2:
                    cov = estimate_cov(returns_data, method=self.cfg.optimizer.cov_method)
                result = optimizer.optimize_with_diagnostics(tradable_stocks, returns_data, cov)
                target_weights = result.weights
                if result.infeasible_kind is not None or result.message:
                    # diagnostics 需先扩展三件套，见本节末「diagnostics 集成」（F-E-2）
                    self._diagnostics.record_detail(
                        date, "rebalance_optimizer",
                        category="config" if result.infeasible_kind == "lower" else "optimizer",
                        error_type="InfeasibleConstraints",
                        message=result.message or str(result.infeasible_kind),
                        retryable=False,
                        infeasible_kind=result.infeasible_kind,
                        method=result.method,
                        n_selected=result.n_selected,
                        max_weight=result.max_weight,
                        min_weight=result.min_weight,
                        cash_residual=result.cash_residual,
                    )
                logger.debug(f"优化得到{len(target_weights)}只股票的目标权重")
            except InfeasibleConstraintError as e:
                ...  # 与 except Exception 同体：record + emit + return（numeric_skip）
            except Exception as e:
                ...  # 原样保留
```

#### diagnostics 集成三件套（Step 6 F-E-2，**实施前必做**）

`core/diagnostics.py` 现状：`DayErrorRecord` 为 **frozen dataclass、6 个固定字段**（L46-L55）；`record(date, stage, exc)` 只收异常（L102）；`record_failure(date, stage, reason)` 只收字符串（L133）。→ `record_detail` 不存在，须按下述三件补齐：

1. **字段**：`DayErrorRecord` 增 `detail: Optional[dict[str, Any]] = None`（frozen + 默认值，构造向后兼容；`_index` 去重键（date/stage/category/error_type/message）**不含**该字段 → 去重语义不变）。
2. **方法**：新增 `record_detail(self, date, stage, *, category: str, error_type: str, message: str, retryable: bool = False, **detail: Any) -> Optional[DayErrorRecord]`；内部与 `record` 同构——`mode == "off"` 提前 `return None`、整体 `try/except` 包裹（**零抛错**，I3）、`MAX_SAMPLES` 截断、`_category_counts[category] += 1`。
3. **分类**：`classify_day_error` 的 `stage == "rebalance"` 分支**最前**插入（沿 [L65-L67](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L65-L67) 类名识别先例，**不 import** `core.portfolio`，避免环）：
   ```python
           if type(exc).__name__ == "InfeasibleConstraintError":
               return "config", False
   ```
   否则 `InfeasibleConstraintError`（`ValueError` 子类）会被既有 `rebalance + ValueError → ("solver", False)` 规则**误分类为 solver**。

> **类别说明**：`"optimizer"` 为新类别，`_category_counts` 为 dict 天然容纳；Step 9 须确认既有测试不存在「类别集合硬编码」断言。
> **禁止**：用日志文本承载诊断字段（§15.6）。

### 7.2 L1104-L1109（overlay 复用同一 Σ）

```python
            if cov is not None and len(returns_data.columns) >= 2:
                cov_codes = [str(code) for code in returns_data.columns]
            else:
                cov, cov_codes = None, []
```

删除 L1106 的 `np.atleast_2d(np.cov(...))`。`returns_data` 在 `weights` 模式下为 `None`（L1068），保持 `cov=None` 分支不变。

> **S15 安全**：`target_vol=None` 时 overlay 不读 σ，数值不变（RESEARCH §6.3）。

---

## 8. T7：测试

### 8.1 新建用例（最小集）

| 文件 | 用例 | AC |
|---|---|---|
| `test_p046_constraints.py` | `test_ac_c_01a_sample_identical_to_legacy[4 method]` | AC-C-01a |
| | `test_ac_c_02_total_weight_le_one` / `test_ac_c_03_box_bounds`（参数化 `min_weight>0`） | C-02/03 |
| | `test_ac_c_04_no_nan_on_zero_raw` / `test_ac_c_05_idempotent` / `test_ac_c_06_deterministic` | C-04..06 |
| | `test_ac_c_07_diagnostics_on_infeasible` | C-07 |
| | `test_ac_c_08_config_validation`（非法配置逐条抛） | C-08 |
| | `test_ac_c_09_selection_snapshot`（等权 `min()` + 零值过滤快照不变） | C-09 |
| | `test_ac_b1_01_error_message_fields` / `test_ac_b1_02_u1b_raises[4 method]` | B1-01/02 |
| | `test_ac_b1_03_boundary_feasible` / `test_ac_b1_04_message_distinct` | B1-03/04 |
| | `test_ac_b2_01_upper_residual` / `test_ac_b2_02_equal_weight_cap` / `test_ac_b2_03_erc_relative` / `test_ac_b2_04_u1b_not_b2` | B2-01..04 |
| | `test_ac_b2_05_diag_fields` / `test_ac_b2_06_residual_synonym` / `test_ac_b2_07_target_positions_cash` / `test_ac_b2_08_minvar_degenerates` | B2-05..08 |
| `test_p046_cov.py` | `test_ac_c_01c_matches_sklearn_ledoitwolf` + `test_lw_2x2_closed_form` | C-01c |
| | `test_psd_projection_non_psd_input` / `test_nan_listwise` / `test_unknown_method_raises` | I8 |
| | `test_ewma_symmetric_psd` | I8（EWMA 路） |
| | `test_near_singular_cov_solver_bounds`（F-D-2） | C-03 |
| `test_p046_engine.py` | `test_cov_computed_once`（monkeypatch `estimate_cov` 计数 == 1） | AC-C-10 |
| | `test_engine_u1b_config_category`（U1-B 经引擎 → 记录 + ERROR + 跳过，`category=="config"`） | B1-05 |
| | `test_engine_u1a_diag_recorded`（U1-A 经引擎 → `record_detail` 落账，`category=="optimizer"`，`infeasible_kind` 入 `DayErrorRecord.detail`） | B2-05 / F-S7-P046-1 |
| | `test_strategy_path_u1b_propagates`（F-D-1） | B1-05 |
| | `test_window_with_nan`（F-D-5） | R4 |
| | `test_optimizer_diag_recorded`（optimizer 层 `OptimizationResult` 字段齐备） | C-07 |
| | `test_p026_record_compat`（`test_p026` record 断言不因 `detail` 字段失败） | F-D-7 |

> **collect 目标（Step 8 对齐 CHECKLIST B1）**：constraints 展开 **27** = AC-C-01a×4 + AC-C-02..07/09×7 + AC-C-08×1 + AC-B1-01×1 + AC-B1-02×4 + AC-B1-03×1 + AC-B1-04×1 + AC-B2-01..08×8；cov **7**；engine **7**；合计 **41**（932 + 41 = **973**，与 CHECKLIST §5 同源）。`test_ac_b1_05_engine_not_silent` 的测试物在 engine 模块（`test_engine_u1b_config_category`），计数归 B12。参数化实现若致 collect 偏移，按 CHECKLIST D1 登记 `F-S9-P046-*`，不得回改 CHECKLIST。

### 8.2 既有测试处置（AC-B1-06）

| 文件:行 | 现状 | 改法 |
|---|---|---|
| `test_p023_quality_guardrails.py:128` | `target_count=2`，默认 `max_weight=0.1` | 显式 `max_weight=0.5`（n=2 可行，断言原意保留） |
| `test_p025_day_error_diagnostics.py:178` | 同上 | 同上 |
| `same:259` / `same:300` | `min_variance` 路径 | 先跑，仅在断言依赖旧超限时改配置；否则不动 |
| `test_p026_silent_exception_governance.py:229` | 同上 | 同上 |

### 8.3 必须记录的行为变化

1. `ledoit_wolf` 不再等价 sample → 依赖 `cov_method="ledoit_wolf"` 的 min_var/mvo 数值会变（AC-C-01c 已锁）；
2. min_var/mvo 求解失败由「静默等权」改为「抛出 → 引擎记录跳过」；
3. U1-A 下 min_var/mvo 输出各 `m`（可能使既有测试的持仓数不变、权重变）；
4. `OPTIMAL_INACCURATE` 由「`!= OPTIMAL` 视为失败 → 回退等权」改为「视为成功、直接返回」（F-E-4）；
5. min_var/mvo 空选股由「cvxpy 报错 → 引擎跳过」改为「返回空结果 + `infeasible_kind="empty"`」（F-E-7）；
6. `estimate_cov` 在有效行 `< 2` 时以 `fillna(0.0)` 补零后算 sample（F-E-5：退化输入语义，与 DESIGN §3.1「回退 sample」同向；伪样本方差为 0，由 `psd_fix` 保 PSD）。

---

## 9. 验收命令（逐段执行）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_p046_constraints.py tests/test_p046_cov.py tests/test_p046_engine.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q -k golden      # 期望 18 passed
.venv\Scripts\python.exe -m mypy core tests
.venv\Scripts\python.exe -m black --check --line-length 100 core tests
```

门禁（**终态目标**，Step 8 与 CHECKLIST D1-D4 对齐；原「932 + Δ」作废）：全量 **973 passed**（= 932 + 41）；`-k golden` **18 零重录**；mypy **111 files 0 error**；black `core tests` **152**、全仓 **221** 均 0 reformatted；`tests/*.py` **109**。

---

## 10. 回退点

| 回退点 | 方式 |
|---|---|
| R1 投影引入漂移 | `_apply_constraints_legacy` 保留；`_apply_constraints` 单点改回即可 |
| R2 C1 数值争议 | `estimate_cov` 的 `ledoit_wolf` 分支可临时指回 sample（仅调试，不得提交） |
| R3 配置校验打红用例 | 单测改为 `pytest.raises(ValueError)`；不得删校验 |
| 整体 | 按 §1.3 分段提交，任一段可 `git revert <commit>` |

---

## 11. 与 DESIGN 的偏差登记

| # | 偏差 | 理由 |
|---|---|---|
| **F-D-8** | `MeanVarianceOptimizer` 协方差注入分支重写（DESIGN 原未覆盖） | 原实现会**丢弃**引擎注入的 Σ（L286-L289 无条件重估），选项 i 失效 |
| **F-D-9** | 求解失败由等权回退改为抛 `RuntimeError` | DESIGN §4.1「数值失败→抛出」；原回退是 F-P046-1 的放大器 |
| F-D-10 | `_apply_constraints` 增可选参数 `feas` | 保持默认调用兼容；避免改动 4 处签名 |
| F-D-11 | `diagnostics` 扩展**三件套**（`detail` 字段 / `record_detail` 方法 / `classify_day_error` 的 config 分支） | §15.6 禁止依赖日志文本；`InfeasibleConstraintError` 是 `ValueError` 子类，不补分类会误归 solver（Step 6 F-E-2） |
| F-E-8 | `_psd_project` 对已 PSD 矩阵的特征重建引入 ~1e-18 浮点差 | 远小于 AC-C-01a 的 1e-12；若需逐位严格，sample 分支可跳过投影（默认不跳，保 PSD 不变量 I8） |
| F-E-9 | `apply_overlay` 的 `cov` 参数契约是 `ndarray` + `codes` 序列 | T6 传 `cov.to_numpy()` 与 `[str(c) for c in cov.columns]`，见 §7.2 |

---

## 12. 低效排除表（Step 5 工具契约要求非空）

| 排除方案 | 不采用的理由 |
|---|---|
| iterative clip-normalize 循环 | 不保证收敛、可能反复越界（正是 F-P046-1 的成因）；改用二分缩放 |
| 每个 method 各自估计协方差 | 违反 C3 单一入口，且复活 overlay 双口径（G-P046-6） |
| 为 `cov_shrinkage` / `round_lot` 补运行时消费 | P3 死配置；本批只标注归属（D-3），不做 API 破坏 |
| 在 ERC 乘性迭代**内部**加归一化/投影 | 破坏迭代不动点；归一化只在循环结束后一次 |
| 用日志文本承载 `infeasible_kind` 等字段 | §15.6 明禁（不可断言、易漂移） |
| 为 U1-A 增加 `on_infeasible` 配置开关 | U-P046-10 已裁决「不加开关」（YAGNI） |
| 引入 `pypfopt` 作运行时依赖 | Q7/N1：仅对拍，不设依赖 |
| 对 min_var/mvo 在 U1-A 下仍调用 cvxpy | 可行域是单点（§5.4 证明），求解无信息量且徒增失败面 |

---

## 13. 执行记录（Step 9，2026-11-20，DeepSeek-V4.1-Flash）

### 13.1 落码与骨架的对应

| 任务 | 文件 | 与 §2-§7 骨架的差异 |
|---|---|---|
| T1-T4 | `core/portfolio.py`（全量重写） | 按骨架实现；`_cov_sample`/`_cov_ledoit_wolf`/`_cov_ewma` 抽为模块级函数供 `COV_ESTIMATORS` 查表；mypy 修复 3 处 `no-any-return`（`np.asarray(..., dtype=float)`） |
| T5 | `core/config.py` | 按 §6 实现；`cov_shrinkage` 注释改「已废弃（P-046a），零消费」 |
| T6a | `core/diagnostics.py` | 按 §15.6 三件套实现；`summary()` 不新增 `category_counts` 键（保持既有契约） |
| T6b | `core/engine_v2.py` | 按 §7.2 接线；新增模块级 `_optimize_with_diagnostics`（兼容仅实现 2 参 `optimize` 的注入桩） |
| T7 | 3 个新测试模块 | 见 §8.1；实测 collect **55**（≠ 计划 41，F-S9-P046-1） |

### 13.2 既有测试处置（实际 2 处）

| 文件 | 改动 | 性质 |
|---|---|---|
| `tests/test_p031_strategy_engine_accounting.py` L73 | `OptimizerConfig(..., max_weight=1.0)` | **语义修正**：原断言依赖旧 U1-A 归一化把 `2×0.1` 抬到 `0.5`；新语义各 `0.1`、残差留现金 |
| `tests/test_p048_overlay_engine.py` `test_enabled_scales_weights` | σ 改由 sklearn `LedoitWolf` 独立复算，删除 `approx(0.3004, abs=5e-3)` | **语义修正**（G-P046-6 修复的合法后果）：overlay 复用引擎单一 Σ，单资产时 LW 退化为 ddof=0 有偏样本协方差 |

其余 3 个 `target_count=2` 构造点（`test_p023:128` / `test_p025:178,259,300` / `test_p026:229`）断言不依赖权重数值，**零改动**（F-S9-P046-3）。

### 13.3 门禁读数（终态）

全量 **987 passed**（932+55）；`-k golden` **18 passed** 且 `tests/golden/` 零 diff；mypy **111 files 0 issue**；black **152 · 221**（0 reformatted）；`tests/*.py` **109**；AST `except Exception` core 外 **26**（基线 22 口径不可复现，F-S9-P046-2）、core **30**；`uv lock --check` exit **0**。

### 13.4 未触发项

R1/R2/R3 与整体 revert 均未触发；`_apply_constraints_legacy` 与 `COV_ESTIMATORS` 三键保留；`config_v2.py` / `interfaces.py` / `risk_overlay.py` / `target_positions.py` / `tests/golden/` / `tests/_scenarios_*.py` 零 diff。

### 13.5 状态

代码与测试**未提交**（未获用户授权）；Step 10 异构终审 + 授权提交 + CI。
