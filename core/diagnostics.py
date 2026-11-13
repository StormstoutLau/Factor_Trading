"""日级异常诊断采集（P-025）

与引擎解耦的轻量采集器：日循环 / 组合优化 / 订单执行三处统一汇入。
设计约束见 docs/DESIGN_p025_daily_loop_exception_semantics.md（D2 / D3）。

- 分类只依赖 (stage, 异常类型)，不匹配消息文本（D2）
- record 任何路径不抛错（I3）：内部兜底后降级为 logger.error
- off 模式零分配（I4）：record 首行直接返回 None
"""

from __future__ import annotations

import builtins
import logging
import sys
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# 阶段词表（D3）：本批实际产生 day_loop / rebalance / execution 三类；
# 其余值为前向兼容预留，本批不在这些粒度插桩。
STAGES = (
    "day_loop",
    "settle",
    "pending",
    "next_day",
    "rebalance",
    "factor",  # P-026 追加：因子预处理（setup 期一次性）
    "mark",
    "execution",
    "risk",
    "dump",
    "finalize",
)

# raise 模式参与抛出的类别（D1/D4：execution/solver 业务可恢复，不抛）
RAISE_CATEGORIES = frozenset({"data", "internal"})

# 判定为降级的类别（D4 的 degraded 语义）
DEGRADED_CATEGORIES = frozenset({"data", "solver", "internal"})


@dataclass(frozen=True)
class DayErrorRecord:
    """单条日级异常记录"""

    date: str
    stage: str
    category: str
    error_type: str
    message: str
    retryable: bool


def classify_day_error(stage: str, exc: BaseException) -> tuple[str, bool]:
    """按 (stage, 异常类型) 判定 (类别, 是否可重试)；不看消息文本（D2）"""
    if stage == "execution":
        return "execution", True
    if stage == "rebalance":
        if isinstance(exc, np.linalg.LinAlgError):
            return "solver", False
        if type(exc).__name__ in {"SolverError", "DCPError"}:
            # 不 import cvxpy：仅按类名识别，避免 diagnostics 依赖重求解器
            return "solver", False
        if isinstance(exc, ValueError):
            # 「…需要收益率数据或协方差矩阵」等输入不足
            return "solver", False
        return "internal", False
    if stage == "factor":
        # 因子预处理（setup 期一次性完成，无逐日重试语义；P-026 D1.3）
        if isinstance(exc, np.linalg.LinAlgError):
            return "solver", False
        if isinstance(exc, (KeyError, FileNotFoundError, ValueError)):
            return "data", False
        return "internal", False
    if isinstance(exc, (KeyError, FileNotFoundError, ValueError)):
        # day_loop 下的数据形态：缺列 / 缺键 / 日期不齐
        return "data", True
    return "internal", False


class DayErrorCollector:
    """日级异常采集器（零抛错 / 有上限 / 可去重）"""

    MAX_SAMPLES = 50
    MAX_MESSAGE = 200

    def __init__(self, mode: str = "report"):
        self._mode = mode
        self._records: list[DayErrorRecord] = []
        self._index: set[tuple[str, str, str, str, str]] = set()
        self._counts: dict[str, int] = {}
        # 按 category 计数：不受明细上限影响（F-S6-P025-2）
        self._category_counts: dict[str, int] = {}
        # 首条 raiseable 样本引用：防截断后取不到（F-S6-P025-2）
        self._first_raiseable: Optional[DayErrorRecord] = None
        self._truncated = False

    def record(self, date: Any, stage: str, exc: BaseException) -> Optional[DayErrorRecord]:
        """记录一条异常；本方法不得抛错（I3）"""
        if self._mode == "off":
            return None
        try:
            category, retryable = classify_day_error(stage, exc)
            rec = DayErrorRecord(
                date=str(date),
                stage=str(stage),
                category=category,
                error_type=type(exc).__name__,
                message=str(exc)[: self.MAX_MESSAGE],
                retryable=retryable,
            )
            self._counts[rec.stage] = self._counts.get(rec.stage, 0) + 1
            self._category_counts[rec.category] = self._category_counts.get(rec.category, 0) + 1
            if rec.category in RAISE_CATEGORIES and self._first_raiseable is None:
                self._first_raiseable = rec
            key = (rec.date, rec.stage, rec.category, rec.error_type, rec.message)
            if key in self._index:
                return rec
            if len(self._records) >= self.MAX_SAMPLES:
                self._truncated = True
                return rec
            self._records.append(rec)
            self._index.add(key)
            return rec
        except Exception:
            logger.error("日级异常采集失败（已忽略）", exc_info=True)
            return None

    def record_failure(
        self, date: Any, stage: str, reason: str, category: str = "execution"
    ) -> None:
        """记录非异常型失败（success=False）；本批无生产调用点（IMPL §9 F-S5-P025-2）"""
        if self._mode == "off":
            return
        try:
            rec = DayErrorRecord(
                date=str(date),
                stage=str(stage),
                category=str(category),
                error_type="FailureResult",
                message=str(reason)[: self.MAX_MESSAGE],
                retryable=True,
            )
            self._counts[rec.stage] = self._counts.get(rec.stage, 0) + 1
            self._category_counts[rec.category] = self._category_counts.get(rec.category, 0) + 1
            if rec.category in RAISE_CATEGORIES and self._first_raiseable is None:
                self._first_raiseable = rec
            key = (rec.date, rec.stage, rec.category, rec.error_type, rec.message)
            if key in self._index:
                return
            if len(self._records) >= self.MAX_SAMPLES:
                self._truncated = True
                return
            self._records.append(rec)
            self._index.add(key)
        except Exception:
            logger.error("日级异常采集失败（已忽略）", exc_info=True)

    def summary(self) -> dict[str, Any]:
        """结果字典载荷；off 模式最小化（I4）"""
        if self._mode == "off":
            return {"mode": "off"}
        degraded = self._truncated or any(
            self._category_counts.get(c, 0) > 0 for c in DEGRADED_CATEGORIES
        )
        return {
            "mode": self._mode,
            "degraded": degraded,
            "counts": dict(self._counts),
            "samples": [asdict(r) for r in self._records],
            "truncated": self._truncated,
        }

    def raise_if_needed(self) -> None:
        """raise 模式：首个 data/internal 错误即抛（DESIGN §10 F-S4-P025-6 裁决）"""
        if self._mode != "raise":
            return
        if not any(self._category_counts.get(c, 0) > 0 for c in RAISE_CATEGORIES):
            return
        first = self._first_raiseable
        assert first is not None  # 计数 > 0 与 first_raiseable 同步写入，恒成立
        err = RuntimeError(
            f"日级异常（{first.stage}/{first.error_type}，{first.date}）: {first.message}；"
            '需跳过该日请设 day_error_mode="report"'
        )
        err.diagnostics = self.summary()  # type: ignore[attr-defined]
        if sys.version_info >= (3, 11):
            # mypy target=3.10（pyproject L106）：名字经 getattr 取得，避免 name-defined
            raise getattr(builtins, "ExceptionGroup")("日级异常", [err])
        raise err
