"""OOS 绩效产出器（P-051c，DESIGN D6 / U-P051c-15/17/18/19/20）。

``evaluate_strategy`` 把「策略 + 数据」变成 ``StageEvidence``：连续回测一次，
按 WalkForward 窗口切段取 OOS/IS 指标，并算滚动 IC 与衰减。

I/O 边界见 IMPL C-2：仅 ``run_engine`` 经引擎产生临时目录 I/O，返回前销毁。
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from core.config import (
    BacktestConfig,
    CostConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.engine_v2 import BacktestEngineV2
from core.interfaces import IDataManager
from core.lifecycle import LifecycleError, StageEvidence
from core.metrics import MetricsResult, compute_metrics
from core.strategy import BacktestAdapter, Strategy
from core.walk_forward import WalkForwardSplitter

__all__ = ["OOSReport", "WindowOutcome", "run_engine", "evaluate_strategy", "to_evidence"]

MIN_CAPITAL = 1_000_000.0
DEFAULT_INITIAL_CAPITAL = 10_000_000.0
EPS_SHARPE = 0.1
MIN_IC_UNIVERSE = 10


@dataclass(frozen=True)
class WindowOutcome:
    """单窗单段（train/test）的指标或跳过原因。"""

    label: str  # "w{index}_test" / "w{index}_train"
    window_index: int
    split: str  # "test" | "train"
    metrics: Optional[MetricsResult] = None
    skipped_reason: str = ""  # "" | "window_too_short"


@dataclass(frozen=True)
class OOSReport:
    """OOS 产出报告（DESIGN D6.2）；``decay=None`` ≡ insufficient_signal。"""

    aggregate: Optional[MetricsResult]
    window_metrics: tuple[tuple[str, MetricsResult], ...]
    ic_series: pd.Series
    warmup_days: int
    decay: Optional[float]
    decay_reason: str = ""  # "" | "insufficient_signal" | "insufficient_warmup"
    skipped_windows: tuple[str, ...] = ()
    oos_dates: tuple[pd.Timestamp, ...] = ()
    initial_capital: float = DEFAULT_INITIAL_CAPITAL


class _NullCombiner:
    """满足 setup() 的 combiner 守卫（engine_v2 L243-L251）；weights 模式下永不调用。"""

    def combine(self, factors: Any, **kwargs: Any) -> Any:  # pragma: no cover - 永不调用
        return factors


def _validate_capital(initial_capital: float) -> float:
    """N-4：资金下限校验（最低佣金 5 元不得主导成本结构）。"""
    capital = float(initial_capital)
    if not np.isfinite(capital) or capital < MIN_CAPITAL:
        raise LifecycleError("资金过小：最低佣金 5 元将主导成本结构")
    return capital


def run_engine(
    dm: "IDataManager",
    weights: pd.DataFrame,
    *,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> pd.Series:
    """以目标权重跑一次完整回测，返回逐日组合价值（DESIGN D6.2 规格）。

    Raises:
        LifecycleError: ``initial_capital < 1e6``（最低佣金主导成本结构，N-4）；
            或引擎未产生快照。
    """
    capital = _validate_capital(initial_capital)
    cfg = BacktestConfig(
        output_dir=Path("."),  # 占位，下面被临时目录覆盖
        factor_files=[],
        initial_capital=capital,
        cost=CostConfig(),  # commission_min=5.0，刻意保留真实成本结构
        optimizer=OptimizerConfig(method="equal_weight", target_count=1, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        enable_pending_orders=False,
        write_manifest=False,
        invariant_mode="off",
        day_error_mode="off",
    )
    with tempfile.TemporaryDirectory(prefix="p051c_oos_") as tmp:
        cfg.output_dir = Path(tmp)
        engine = BacktestEngineV2(cfg, data_manager=dm, factor_combiner=_NullCombiner())
        engine.setup()
        engine.set_signal(weights, mode="weights")
        results = engine.run()
        pv = results.get("portfolio_value")
        if not isinstance(pv, pd.Series) or pv.empty:
            raise LifecycleError("回测未产生组合价值序列")
        return pv.astype(float).copy()


def _segment(pv: pd.Series, start: pd.Timestamp, end: pd.Timestamp, w: int) -> pd.Series:
    """D6.2 段抽取：左锚前一交易日（purge gap 末日），左界 clamp 到预热下界 ``w``。"""
    left = max(int(pv.index.searchsorted(start)) - 1, w)
    right = int(pv.index.searchsorted(end, side="right"))
    return pv.iloc[left:right] if right > left else pv.iloc[0:0]


def _cross_sectional_ic(
    frame: pd.DataFrame,
    next_returns: pd.DataFrame,
    dates: Sequence[pd.Timestamp],
) -> pd.Series:
    """横截面 rank IC（D6.4/C-10）：口径对齐 ``calculate_ic(method="spearman")``。

    ``next_ret`` 的 NaN（末日 / 停牌）先与权重交集再 dropna，最后判有效对数
    ``>= MIN_IC_UNIVERSE``（对齐 stats.py 的 dropna → 交集 → len<10 顺序）。
    """
    values: dict[pd.Timestamp, float] = {}
    for date in dates:
        if date not in frame.index or date not in next_returns.index:
            continue
        weights = frame.loc[date]
        selected = weights[weights > 0]
        if selected.empty:
            continue
        pair = pd.concat([selected, next_returns.loc[date, selected.index]], axis=1).dropna()
        if len(pair) < MIN_IC_UNIVERSE:
            continue
        ic = pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")
        if pd.notna(ic):
            values[date] = float(ic)
    return pd.Series(values, dtype=float)


def _chain_segments(segments: Sequence[pd.Series]) -> list[float]:
    """各 OOS 段按段首归一后连乘（锚点 1.0，跳过各段首点）。"""
    chained: list[float] = [1.0]
    for seg in segments:
        norm = seg.to_numpy(dtype=float) / float(seg.iloc[0])
        base = chained[-1]
        chained.extend(float(base * value) for value in norm[1:])
    return chained


def evaluate_strategy(
    dm: "IDataManager",
    strategy: Strategy,
    *,
    min_history: int,
    signal: Optional[pd.DataFrame] = None,
    tradable: Optional[pd.DataFrame] = None,
    splitter: Optional[WalkForwardSplitter] = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> OOSReport:
    """OOS 绩效产出器（D6.1-D6.4）。纯计算；唯一 I/O 经 ``run_engine``（C-2）。"""
    if int(min_history) < 1:
        raise LifecycleError("min_history 必须 >= 1")
    capital = _validate_capital(initial_capital)
    warmup = int(min_history) + 1

    dates = dm.trade_dates
    if len(dates) <= warmup:
        raise LifecycleError(f"样本不足：需要 > {warmup} 个交易日")

    base_signal = (
        pd.DataFrame(True, index=dates, columns=dm.stock_codes) if signal is None else signal
    )
    views = BacktestAdapter.views_from_data(
        dm, base_signal, tradable=tradable, history_window=warmup
    )
    adapter = BacktestAdapter(strategy)
    frame = adapter.signals_frame(views[warmup:])
    head = pd.DataFrame(0.0, index=dates[:warmup], columns=frame.columns)
    full = pd.concat([head, frame])
    if list(full.index) != list(dates):
        raise LifecycleError("权重矩阵日期与交易日历不一致")

    pv = run_engine(dm, full, initial_capital=capital)

    windows = splitter or WalkForwardSplitter(
        dates=dates, train_size=252, test_size=63, purge_gap=5
    )
    window_metrics: list[tuple[str, MetricsResult]] = []
    skipped: list[str] = []
    test_segments: list[pd.Series] = []
    oos_dates: list[pd.Timestamp] = []
    paired_sharpes: list[tuple[float, float]] = []

    for window in windows.split():
        segments: dict[str, pd.Series] = {
            "test": _segment(pv, window.test_start, window.test_end, warmup),
            "train": _segment(pv, window.train_start, window.train_end, warmup),
        }
        metrics: dict[str, Optional[MetricsResult]] = {}
        for split, seg in segments.items():
            label = f"w{window.window_index}_{split}"
            if len(seg) < 2:
                skipped.append(label)
                metrics[split] = None
                continue
            result = compute_metrics(seg.to_numpy(dtype=float))
            window_metrics.append((label, result))
            metrics[split] = result
        test_metrics = metrics["test"]
        train_metrics = metrics["train"]
        if test_metrics is not None:
            test_segments.append(segments["test"])
            oos_dates.extend(segments["test"].index[1:].tolist())
        if test_metrics is not None and train_metrics is not None:
            paired_sharpes.append(
                (float(train_metrics.sharpe_ratio), float(test_metrics.sharpe_ratio))
            )

    aggregate: Optional[MetricsResult] = None
    decay_reason = ""
    if test_segments:
        chained = _chain_segments(test_segments)
        if len(chained) >= 2:
            aggregate = compute_metrics(chained)
        else:
            decay_reason = "insufficient_warmup"
    else:
        decay_reason = "insufficient_warmup"

    decay: Optional[float] = None
    if aggregate is not None:
        if not paired_sharpes:
            decay_reason = "insufficient_signal"
        else:
            mean_is = float(np.mean([pair[0] for pair in paired_sharpes]))
            mean_oos = float(np.mean([pair[1] for pair in paired_sharpes]))
            if abs(mean_is) < EPS_SHARPE:
                decay_reason = "insufficient_signal"
            else:
                decay = (mean_is - mean_oos) / abs(mean_is)

    next_returns = dm.get_adj_price("close", "raw").pct_change().shift(-1)
    ordered_dates = tuple(sorted(set(oos_dates)))
    ic_series = _cross_sectional_ic(frame, next_returns, ordered_dates)

    return OOSReport(
        aggregate=aggregate,
        window_metrics=tuple(window_metrics),
        ic_series=ic_series,
        warmup_days=warmup,
        decay=decay,
        decay_reason=decay_reason,
        skipped_windows=tuple(skipped),
        oos_dates=ordered_dates,
        initial_capital=capital,
    )


def to_evidence(
    report: OOSReport,
    *,
    source: str,
    paper_days: int = 0,
    paper_trades: int = 0,
    current_drawdown: Optional[float] = None,
    account_total: Optional[float] = None,
) -> StageEvidence:
    """OOSReport → StageEvidence（lifecycle 的唯一输入形态）；只做字段搬运。"""
    return StageEvidence(
        source=source,
        metrics=report.aggregate,
        is_metrics=None,
        window_metrics=report.window_metrics,
        ic_series=report.ic_series,
        paper_days=int(paper_days),
        paper_trades=int(paper_trades),
        current_drawdown=current_drawdown,
        warmup_days=report.warmup_days,
        is_oos_decay=report.decay,
        account_total=account_total,
    )
