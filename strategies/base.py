"""策略模板公共工具（P-051b）。

契约（DESIGN §3.3 / D10）：
- 无 I/O、无 logging、无全局状态；
- 契约不满足一律 ``StrategyConfigError``（``ValueError`` 子类，fail-fast）；
- 权重非负、行和 ≤ 1；``scale_to_one`` 只在行和 > 1 时缩放（空仓合法）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields
from typing import Any, TypeVar, cast

import pandas as pd

from core.strategy import MarketView

__all__ = [
    "StrategyConfigError",
    "build_config",
    "equal_weight",
    "require_history",
    "require_keys",
    "scale_to_one",
]

T = TypeVar("T")


class StrategyConfigError(ValueError):
    """模板参数或视图契约不满足（fail-fast，不静默降级）。"""


def require_keys(history: Mapping[str, pd.DataFrame], keys: Sequence[str], *, name: str) -> None:
    """校验 ``history`` 键集。"""
    missing = [key for key in keys if key not in history]
    if missing:
        raise StrategyConfigError(f"{name}: history 缺少键 {missing}")


def require_history(
    view: MarketView,
    min_rows: int,
    *,
    name: str,
    keys: Sequence[str] = ("close",),
) -> dict[str, pd.DataFrame]:
    """校验并返回 ``history``（缺失 / 缺键 / 行数不足 → fail-fast）。"""
    history = view.history
    if history is None:
        raise StrategyConfigError(
            f"{name}: history is None（需 views_from_data(history_window>0)）"
        )
    require_keys(history, keys, name=name)
    rows = len(history[keys[0]])
    if rows < min_rows:
        raise StrategyConfigError(f"{name}: history 行数 {rows} < 最小窗长 {min_rows}")
    return history


def equal_weight(codes: Sequence[str]) -> pd.Series:
    """等权 ``1/n``；``n=0`` → 空 Series（dtype=float）。"""
    unique = list(dict.fromkeys(str(code) for code in codes))
    if not unique:
        return pd.Series(dtype=float)
    weight = 1.0 / len(unique)
    return pd.Series(weight, index=unique, dtype=float)


def scale_to_one(weights: pd.Series) -> pd.Series:
    """非负校验 + 行和 > 1 时缩放（保证 ≤ 1）。"""
    if weights.empty:
        return pd.Series(dtype=float)
    values = weights.astype(float)
    if bool((values < 0).any()):
        raise StrategyConfigError("权重不得为负")
    total = float(values.sum())
    if total > 1.0:
        values = values * (1.0 / total)
    return values


def build_config(
    cls: type[T],
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, Any],
) -> T:
    """``config`` 展开 + ``overrides`` 覆盖 → dataclass 实例；未知键 fail-fast。"""
    merged: dict[str, Any] = dict(config) if config is not None else {}
    merged.update(dict(overrides))
    known = {item.name for item in fields(cls)}  # type: ignore[arg-type]
    unknown = sorted(set(merged) - known)
    if unknown:
        raise StrategyConfigError(f"{cls.__name__}: 未知配置键 {unknown}")
    return cast(T, cls(**merged))
