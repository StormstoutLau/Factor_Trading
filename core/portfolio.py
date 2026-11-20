"""组合优化模块 - 基于Backtest_Opus_2.0架构

提供多种组合优化策略：
- 等权重优化
- 最小方差优化
- 均值方差优化（马科维茨）
- 风险平价优化
- 整手数优化

P-046a：约束语义修复（投影替代 clip→归一）+ 协方差单一入口（``estimate_cov``）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cvxpy as cp
import numpy as np
import pandas as pd
from scipy import linalg, stats
from sklearn.covariance import LedoitWolf

from core.config import OptimizerConfig

logger = logging.getLogger(__name__)

# 可行性判定容差（U1-B/U1-A 边界）
_FEAS_TOL = 1e-12
# 投影短路容差（DESIGN §4.2 F-D-3）
_SCALE_TOL = 1e-12
# 投影终态断言容差（AC-C-03）
_SCALE_ASSERT_TOL = 1e-9

EWMA_LAMBDA = 0.94


class InfeasibleConstraintError(ValueError):
    """权重约束不可行（U1-B 下限型 / U1-D 配置矛盾）。

    继承 ``ValueError`` 以兼容既有 ``except`` 语义；引擎侧按类名单独分流为
    ``config`` 类别（见 ``core.diagnostics.classify_day_error``）。
    """


@dataclass(frozen=True)
class OptimizationResult:
    """优化结果 + 结构化诊断（DESIGN D-R2）。

    ``weights`` 为唯一可执行产物；其余字段仅在 ``infeasible_kind`` 非 ``None``
    或数值失败时用于诊断落账。
    """

    weights: pd.Series
    method: str
    n_selected: int
    max_weight: float
    min_weight: float
    infeasible_kind: Optional[str] = None  # None | "upper" | "empty" | "lower"
    cash_residual: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class _Feasibility:
    """``_precheck`` 结果：可行 / 上限型不可行 / 空集。"""

    kind: str  # "ok" | "upper" | "empty"
    budget: float = 1.0

    @property
    def is_upper(self) -> bool:
        return self.kind == "upper"


def _precheck(n: int, cfg: OptimizerConfig, method: str) -> _Feasibility:
    """U1 分型（DESIGN §2.3）。

    ``n`` 必须为「选股后真实标的数」；``method`` 仅用于诊断消息（AC-B1-01）。
    上限型不抛（可留现金），下限型抛（违 I-P046-2 无杠杆）。
    """
    if n == 0:
        return _Feasibility("empty", 0.0)
    sum_max = n * cfg.max_weight
    sum_min = n * cfg.min_weight
    if sum_min > 1.0 + _FEAS_TOL:  # U1-B：下限和不可满足
        raise InfeasibleConstraintError(
            f"约束不可行(U1-B): method={method}, n={n}, max_weight={cfg.max_weight}, "
            f"min_weight={cfg.min_weight}, sum_min={sum_min:.12f} > 1, "
            f"required_max_weight<=1/n={1.0 / n:.12f}, sum_max={sum_max:.12f}"
        )
    if sum_max < 1.0 - _FEAS_TOL:  # U1-A：上限型，留现金
        return _Feasibility("upper", sum_max)
    return _Feasibility("ok", 1.0)


def _clip_series(weights: pd.Series, lower: float, upper: float, factor: float) -> pd.Series:
    return (weights.astype(float) * factor).clip(lower=lower, upper=upper)


def _scale_to_budget(
    weights: pd.Series,
    lower: float,
    upper: float,
    budget: float = 1.0,
    tol: float = _SCALE_TOL,
    max_iter: int = 60,
) -> pd.Series:
    """把 ``weights`` 在 ``[lower, upper]`` 内缩放到 ``sum == budget``。

    二分求缩放因子 λ：``clip(λ·w, lower, upper)`` 单调不减。短路条件
    （``|Σclip(1·w) − budget| ≤ tol``）直接返回，保证与旧路径逐位一致（AC-C-01a）。
    """
    if len(weights) == 0:
        return weights
    raw = weights.astype(float)
    total_raw = float(raw.sum())
    if not np.isfinite(total_raw) or total_raw <= 0.0:
        # 退化输入：以等权为基准重建，避免除零（I3）
        raw = pd.Series(1.0, index=raw.index)

    direct = _clip_series(raw, lower, upper, 1.0)
    if abs(float(direct.sum()) - budget) <= tol:
        return direct

    if float(direct.sum()) < budget:  # 需放大：doubling 求上界
        lo_lam, hi_lam = 1.0, 2.0
        for _ in range(max_iter):
            if float(_clip_series(raw, lower, upper, hi_lam).sum()) >= budget:
                break
            lo_lam, hi_lam = hi_lam, hi_lam * 2.0
    else:  # 需缩小
        lo_lam, hi_lam = 0.0, 1.0

    for _ in range(max_iter):
        mid = 0.5 * (lo_lam + hi_lam)
        if float(_clip_series(raw, lower, upper, mid).sum()) < budget:
            lo_lam = mid
        else:
            hi_lam = mid

    scaled = _clip_series(raw, lower, upper, 0.5 * (lo_lam + hi_lam))
    deviation = abs(float(scaled.sum()) - budget)
    if deviation > _SCALE_ASSERT_TOL:
        raise RuntimeError(
            f"权重投影未收敛: |Σw - {budget:.6f}| = {deviation:.3e} > {_SCALE_ASSERT_TOL:.0e}"
        )
    return scaled


def _cov_sample(x: np.ndarray) -> np.ndarray:
    """样本协方差（行 < 2 时返回零矩阵，避免 NaN）。"""
    n_assets = x.shape[1]
    if x.shape[0] < 2:
        return np.zeros((n_assets, n_assets))
    return np.cov(x, rowvar=False, ddof=1)


def _cov_ledoit_wolf(x: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf 收缩（sklearn 实现，identity 目标，DESIGN §5.2 C1）。"""
    n_assets = x.shape[1]
    if x.shape[0] < 2:
        return np.zeros((n_assets, n_assets))
    return np.asarray(LedoitWolf().fit(x).covariance_, dtype=float)


def _cov_ewma(x: np.ndarray, lambda_param: float = EWMA_LAMBDA) -> np.ndarray:
    """EWMA 协方差（向量化实现，与旧逐 bar 循环等价）。"""
    n_periods, n_assets = x.shape
    if n_periods < 1:
        return np.zeros((n_assets, n_assets))
    weights = np.array(
        [(1 - lambda_param) * lambda_param ** (n_periods - 1 - i) for i in range(n_periods)]
    )
    weights = weights / weights.sum()
    weighted_mean = np.sum(x * weights[:, None], axis=0)
    diff = x - weighted_mean
    return np.asarray((diff * weights[:, None]).T @ diff, dtype=float)


# 协方差估计器（键集为公开契约，A12）
COV_ESTIMATORS = {
    "sample": _cov_sample,
    "ledoit_wolf": _cov_ledoit_wolf,
    "ewma": _cov_ewma,
}


def _psd_project(cov: np.ndarray) -> np.ndarray:
    """对称化 + 负特征值截断（I8：输出必为 PSD）。"""
    sym = 0.5 * (cov + cov.T)
    values, vectors = np.linalg.eigh(sym)
    values = np.clip(values, 0.0, None)
    projected = (vectors * values) @ vectors.T
    return np.asarray(0.5 * (projected + projected.T), dtype=float)


def estimate_cov(
    returns: pd.DataFrame,
    method: str = "ledoit_wolf",
    codes: Optional[list[str]] = None,
    psd_fix: bool = True,
) -> pd.DataFrame:
    """协方差**唯一入口**（DESIGN §5.1 选项 i）。

    - ``codes`` 非空时先按列截取；
    - NaN 行 listwise 删除；有效行 < 2 时以 0 填充（退化输入，无 NaN 输出）；
    - 输出对称 + PSD（``psd_fix=True``）；
    - 未知 ``method`` 抛 ``ValueError``（含合法值集）。
    """
    if method not in COV_ESTIMATORS:
        raise ValueError(f"未知协方差估计方法: {method!r}；合法值: {sorted(COV_ESTIMATORS)}")
    if codes is not None:
        returns = returns.loc[:, [c for c in codes if c in returns.columns]]

    x = returns.to_numpy(dtype=float)
    if x.size == 0:
        return pd.DataFrame(np.zeros((0, 0)), index=returns.columns, columns=returns.columns)

    valid = ~np.isnan(x).any(axis=1)
    x_use = x[valid] if int(valid.sum()) >= 2 else np.nan_to_num(x, nan=0.0)

    cov = np.atleast_2d(COV_ESTIMATORS[method](x_use))
    cov = 0.5 * (cov + cov.T)
    if psd_fix:
        cov = _psd_project(cov)
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)


class BaseOptimizer:
    """组合优化器基类"""

    def __init__(self, config: OptimizerConfig):
        """初始化优化器

        Args:
            config: 优化器配置
        """
        self.cfg = config
        logger.info(f"{self.__class__.__name__} 初始化完成")

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        """执行组合优化并返回结构化结果（D-R2）。子类必须实现。"""
        raise NotImplementedError("子类必须实现optimize_with_diagnostics方法")

    def optimize(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> pd.Series:
        """执行组合优化（薄包装，签名冻结以兼容 ``IOptimizer`` Protocol）"""
        return self.optimize_with_diagnostics(factor_scores, returns, cov_matrix).weights

    def _empty_result(self, method: str) -> OptimizationResult:
        return OptimizationResult(
            pd.Series(dtype=float),
            method,
            0,
            self.cfg.max_weight,
            self.cfg.min_weight,
            infeasible_kind="empty",
            cash_residual=1.0,
            message=f"约束不可行(U1-C): method={method}, n=0（空集）",
        )

    def _select(self, factor_scores: pd.Series) -> pd.Index:
        if self.cfg.select_top:
            return factor_scores.nlargest(self.cfg.target_count).index
        return factor_scores.nsmallest(self.cfg.target_count).index

    def _apply_constraints(
        self, weights: pd.Series, feas: Optional[_Feasibility] = None
    ) -> pd.Series:
        """应用权重约束（投影，DESIGN §4）。

        - 上限型（U1-A）：只截断，不归一 → ``Σw = Σmin(w_i, m) < 1``，残差留现金；
        - 可行：二分缩放至 ``Σw == 1`` 且不越界。
        """
        if feas is None:
            feas = _precheck(len(weights), self.cfg, self.__class__.__name__)
        if feas.kind == "empty" or len(weights) == 0:
            return weights.iloc[0:0]
        if feas.is_upper:
            return weights.clip(lower=self.cfg.min_weight, upper=self.cfg.max_weight)
        return _scale_to_budget(
            weights, lower=self.cfg.min_weight, upper=self.cfg.max_weight, budget=1.0
        )

    def _apply_constraints_legacy(self, weights: pd.Series) -> pd.Series:
        """旧实现（clip→clip→归一），仅供 AC-C-01a 对拍，**生产禁用**。"""
        weights = weights.clip(upper=self.cfg.max_weight)
        weights = weights.clip(lower=self.cfg.min_weight)
        return weights / weights.sum()

    def _cov_for(
        self,
        selected: pd.Index,
        returns: Optional[pd.DataFrame],
        cov_matrix: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        """取选中子集协方差：注入优先（``.loc`` 截取），否则走单一入口。"""
        if cov_matrix is not None:
            return cov_matrix.loc[selected, selected]
        assert returns is not None
        return estimate_cov(returns[selected], method=self.cfg.cov_method)


class EqualWeightOptimizer(BaseOptimizer):
    """等权重优化器"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        """等权重分配"""
        valid_scores = factor_scores.dropna()
        valid_scores = valid_scores[valid_scores != 0]

        if len(valid_scores) == 0:
            logger.warning("没有有效的因子得分，返回空权重")
            return self._empty_result("equal_weight")

        target_count = min(self.cfg.target_count, len(valid_scores))
        if self.cfg.select_top:
            selected_stocks = valid_scores.nlargest(target_count).index
        else:
            selected_stocks = valid_scores.nsmallest(target_count).index

        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "equal_weight")
        raw = pd.Series(1.0 / n, index=selected_stocks)
        weights = self._apply_constraints(raw, feas)

        if feas.is_upper:
            residual = 1.0 - float(weights.sum())
            return OptimizationResult(
                weights,
                "equal_weight",
                n,
                self.cfg.max_weight,
                self.cfg.min_weight,
                infeasible_kind="upper",
                cash_residual=residual,
                message=(
                    f"约束不可行(U1-A): method=equal_weight, n={n}, "
                    f"max_weight={self.cfg.max_weight}, min_weight={self.cfg.min_weight}, "
                    f"sum_max={n * self.cfg.max_weight:.12f} < 1, "
                    f"required_max_weight>=1/n={1.0 / n:.12f}, cash_residual={residual:.12f}"
                ),
            )
        return OptimizationResult(
            weights,
            "equal_weight",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(weights.sum())),
        )


class MinVarianceOptimizer(BaseOptimizer):
    """最小方差优化器"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        """最小方差优化"""
        if returns is None and cov_matrix is None:
            raise ValueError("最小方差优化需要收益率数据或协方差矩阵")

        selected_stocks = self._select(factor_scores)
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "min_variance")
        if feas.kind == "empty":
            return self._empty_result("min_variance")
        if feas.is_upper:
            # 可行域为单点 Σw=n·m 且 w_i<=m → 唯一解各 m（DESIGN §4.3 / AC-B2-08）
            weights = pd.Series(self.cfg.max_weight, index=selected_stocks)
            residual = 1.0 - float(weights.sum())
            return OptimizationResult(
                weights,
                "min_variance",
                n,
                self.cfg.max_weight,
                self.cfg.min_weight,
                infeasible_kind="upper",
                cash_residual=residual,
                message=(
                    f"约束不可行(U1-A): method=min_variance, n={n}, "
                    f"max_weight={self.cfg.max_weight}, min_weight={self.cfg.min_weight}, "
                    f"sum_max={n * self.cfg.max_weight:.12f} < 1, "
                    f"required_max_weight>=1/n={1.0 / n:.12f}, cash_residual={residual:.12f}"
                ),
            )

        cov = self._cov_for(selected_stocks, returns, cov_matrix)

        w = cp.Variable(n)
        objective = cp.Minimize(cp.quad_form(w, cov.values))
        constraints = [
            cp.sum(w) == 1,
            w >= self.cfg.min_weight,
            w <= self.cfg.max_weight,
        ]
        problem = cp.Problem(objective, constraints)
        problem.solve()

        if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or w.value is None:
            raise RuntimeError(f"最小方差优化失败: solver status={problem.status}")

        weights = pd.Series(w.value, index=selected_stocks)
        return OptimizationResult(
            weights,
            "min_variance",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(weights.sum())),
        )


class MeanVarianceOptimizer(BaseOptimizer):
    """均值方差优化器（马科维茨）"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        """均值方差优化"""
        if returns is None and cov_matrix is None:
            raise ValueError("均值方差优化需要收益率数据或协方差矩阵")

        selected_stocks = self._select(factor_scores)
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "mean_variance")
        if feas.kind == "empty":
            return self._empty_result("mean_variance")
        if feas.is_upper:
            # 同上：单点解各 m（AC-B2-08）
            weights = pd.Series(self.cfg.max_weight, index=selected_stocks)
            residual = 1.0 - float(weights.sum())
            return OptimizationResult(
                weights,
                "mean_variance",
                n,
                self.cfg.max_weight,
                self.cfg.min_weight,
                infeasible_kind="upper",
                cash_residual=residual,
                message=(
                    f"约束不可行(U1-A): method=mean_variance, n={n}, "
                    f"max_weight={self.cfg.max_weight}, min_weight={self.cfg.min_weight}, "
                    f"sum_max={n * self.cfg.max_weight:.12f} < 1, "
                    f"required_max_weight>=1/n={1.0 / n:.12f}, cash_residual={residual:.12f}"
                ),
            )

        # F-D-8：注入协方差优先，**不得**被 returns 重估覆盖
        if returns is not None:
            expected_returns = returns[selected_stocks].mean()
        else:
            expected_returns = pd.Series(0.0, index=selected_stocks)
        cov = self._cov_for(selected_stocks, returns, cov_matrix)

        w = cp.Variable(n)
        portfolio_return = expected_returns.values @ w
        portfolio_variance = cp.quad_form(w, cov.values)
        objective = cp.Maximize(portfolio_return - self.cfg.risk_aversion * portfolio_variance)
        constraints = [
            cp.sum(w) == 1,
            w >= self.cfg.min_weight,
            w <= self.cfg.max_weight,
        ]
        problem = cp.Problem(objective, constraints)
        problem.solve()

        if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or w.value is None:
            raise RuntimeError(f"均值方差优化失败: solver status={problem.status}")

        weights = pd.Series(w.value, index=selected_stocks)
        return OptimizationResult(
            weights,
            "mean_variance",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(weights.sum())),
        )


class RiskParityOptimizer(BaseOptimizer):
    """风险平价优化器"""

    def optimize_with_diagnostics(
        self,
        factor_scores: pd.Series,
        returns: Optional[pd.DataFrame] = None,
        cov_matrix: Optional[pd.DataFrame] = None,
    ) -> OptimizationResult:
        """风险平价优化"""
        if returns is None and cov_matrix is None:
            raise ValueError("风险平价优化需要收益率数据或协方差矩阵")

        selected_stocks = self._select(factor_scores)
        n = len(selected_stocks)
        feas = _precheck(n, self.cfg, "risk_parity")
        if feas.kind == "empty":
            return self._empty_result("risk_parity")

        cov = self._cov_for(selected_stocks, returns, cov_matrix)

        weights = np.ones(n) / n  # 初始等权重
        for _ in range(self.cfg.risk_parity_max_iter):
            portfolio_variance = float(weights @ cov.values @ weights)
            if not np.isfinite(portfolio_variance) or portfolio_variance <= 0.0:
                # 零方差退化：保持等权，避免除零产生 NaN（I3）
                break
            portfolio_vol = np.sqrt(portfolio_variance)
            marginal_contrib = cov.values @ weights / portfolio_vol
            risk_contrib = weights * marginal_contrib
            if np.any(risk_contrib <= 0.0):
                break
            target_risk_contrib = risk_contrib.mean()
            weights_new = weights * target_risk_contrib / risk_contrib
            if np.max(np.abs(weights_new - weights)) < self.cfg.risk_parity_tol:
                weights = weights_new
                break
            weights = weights_new

        total = float(weights.sum())
        if np.isfinite(total) and total > 0.0:
            weights = weights / total

        weights_series = pd.Series(weights, index=selected_stocks)
        applied = self._apply_constraints(weights_series, feas)

        if feas.is_upper:
            residual = 1.0 - float(applied.sum())
            return OptimizationResult(
                applied,
                "risk_parity",
                n,
                self.cfg.max_weight,
                self.cfg.min_weight,
                infeasible_kind="upper",
                cash_residual=residual,
                message=(
                    f"约束不可行(U1-A): method=risk_parity, n={n}, "
                    f"max_weight={self.cfg.max_weight}, min_weight={self.cfg.min_weight}, "
                    f"sum_max={n * self.cfg.max_weight:.12f} < 1, "
                    f"required_max_weight>=1/n={1.0 / n:.12f}, cash_residual={residual:.12f}"
                ),
            )
        return OptimizationResult(
            applied,
            "risk_parity",
            n,
            self.cfg.max_weight,
            self.cfg.min_weight,
            cash_residual=max(0.0, 1.0 - float(applied.sum())),
        )


def round_lot_optimize(
    weights: pd.Series, prices: pd.Series, total_value: float, lot_size: int = 100
) -> pd.Series:
    """整手数优化

    Args:
        weights: 目标权重
        prices: 股票价格
        total_value: 总资金
        lot_size: 整手数大小（A股为100）

    Returns:
        整手数优化后的权重
    """
    # 计算每只股票的目标投资金额
    target_values = weights * total_value

    # 计算每只股票的目标股数
    target_shares = target_values / prices

    # 调整为整手数（向下取整到最近的100股整数倍）
    rounded_shares = np.floor(target_shares / lot_size) * lot_size

    # 计算实际投资金额
    actual_values = rounded_shares * prices

    # 重新计算权重
    actual_weights = actual_values / actual_values.sum()

    return actual_weights


def build_optimizer(config: OptimizerConfig) -> BaseOptimizer:
    """构建优化器

    Args:
        config: 优化器配置

    Returns:
        优化器实例
    """
    optimizer_map = {
        "equal_weight": EqualWeightOptimizer,
        "min_variance": MinVarianceOptimizer,
        "mean_variance": MeanVarianceOptimizer,  # 与 CLI / config_v2 词表对齐（P-025 D6）
        "mvo": MeanVarianceOptimizer,
        "risk_parity": RiskParityOptimizer,
    }

    if config.method not in optimizer_map:
        raise ValueError(f"未知优化方法: {config.method!r}；合法值: {sorted(optimizer_map)}")
    return optimizer_map[config.method](config)
