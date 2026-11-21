"""策略生命周期状态机（P-051c，DESIGN D1-D5/D8-D11）。

纯函数、零 I/O、零 logging、无全局状态（DESIGN I1）。所有时间为调用方传入的
``YYYY-MM-DD`` 字符串（禁 ``datetime.now``）。

状态机只消费 :class:`StageEvidence` 数据，不 import ``core.oos``；唯一对外部
模块的类型依赖是 :class:`core.metrics.MetricsResult`（证据载荷）。
"""

from __future__ import annotations

import math
import numbers
import re
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

from core.metrics import MetricsResult

__all__ = [
    "LifecycleError",
    "LifecycleStage",
    "GateAction",
    "StrategyFingerprint",
    "StageEvidence",
    "ReadinessCriteria",
    "ValueCriteria",
    "GateCriteria",
    "GateDecision",
    "TransitionRecord",
    "LifecycleRecord",
    "initial_record",
    "evaluate_gate",
    "apply",
    "archive",
    "replay",
    "resolve_monitor_action",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ACTION_VALUES = ("go", "hold", "recycle", "kill")
_STAGE_VALUES = ("draft", "backtest", "paper", "gray", "live", "retired")


class LifecycleError(ValueError):
    """生命周期域错误（非法迁移 / 判据输入非法 / 版本冲突 / 归档非法）。"""


class LifecycleStage(str, Enum):
    DRAFT = "draft"
    BACKTEST = "backtest"
    PAPER = "paper"
    GRAY = "gray"
    LIVE = "live"
    RETIRED = "retired"


class GateAction(str, Enum):
    GO = "go"
    HOLD = "hold"
    RECYCLE = "recycle"
    KILL = "kill"


_GO_TARGET: dict[LifecycleStage, LifecycleStage] = {
    LifecycleStage.DRAFT: LifecycleStage.BACKTEST,
    LifecycleStage.BACKTEST: LifecycleStage.PAPER,
    LifecycleStage.PAPER: LifecycleStage.GRAY,
    LifecycleStage.GRAY: LifecycleStage.LIVE,
}  # LIVE / RETIRED 无 GO 目标（D2：live 为最高阶段、retired 终态）

# 合法迁移表（D2）：HOLD 不入表，走 apply / replay 的特判路径（F-I1）。
_LEGAL_TARGET: dict[tuple[LifecycleStage, GateAction], LifecycleStage] = {
    **{(stage, GateAction.GO): target for stage, target in _GO_TARGET.items()},
    (LifecycleStage.BACKTEST, GateAction.RECYCLE): LifecycleStage.DRAFT,
    (LifecycleStage.PAPER, GateAction.KILL): LifecycleStage.RETIRED,
    (LifecycleStage.GRAY, GateAction.KILL): LifecycleStage.PAPER,
    (LifecycleStage.LIVE, GateAction.KILL): LifecycleStage.PAPER,
}


@dataclass(frozen=True)
class StrategyFingerprint:
    """策略指纹（D8）：id + 版本 + 参数快照 + 代码 hash。"""

    strategy_id: str
    version: str
    param_snapshot: dict[str, Any]
    code_hash: str

    def __post_init__(self) -> None:
        for name in ("strategy_id", "version", "code_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise LifecycleError(f"{name} 不能为空")


@dataclass(frozen=True)
class StageEvidence:
    """阶段证据（DESIGN §3）：由 ``core.oos.to_evidence`` 生产或调用方注入。"""

    source: str  # "walk_forward" | "paper_record" | "live_account"
    metrics: Optional[MetricsResult] = None
    is_metrics: Optional[MetricsResult] = None
    window_metrics: tuple[tuple[str, MetricsResult], ...] = ()
    ic_series: Optional[pd.Series] = None
    paper_days: int = 0
    paper_trades: int = 0
    current_drawdown: Optional[float] = None  # 非负量级
    warmup_days: int = 0  # U-P051c-19：被排除的预热日数
    is_oos_decay: Optional[float] = None  # D6.3：(IS-OOS)/|IS|；None = insufficient_signal
    account_total: Optional[float] = None  # D4 capital 判据的资金来源


@dataclass(frozen=True)
class ReadinessCriteria:
    """晋级准备度判据（阈值均为经验默认值，可配置；DESIGN U-P051c-9）。"""

    oos_sharpe_min: float = 0.8
    oos_max_drawdown_max: float = 0.25
    is_oos_decay_max: float = 0.5
    paper_days_min: int = 20
    paper_trades_min: int = 50
    ic_min: float = 0.02
    ic_lookback: int = 60

    def __post_init__(self) -> None:
        for name in ("oos_sharpe_min", "is_oos_decay_max", "ic_min"):
            if not math.isfinite(float(getattr(self, name))):
                raise LifecycleError(f"{name} 必须为有限数")
        if not 0.0 < float(self.oos_max_drawdown_max) <= 1.0:
            raise LifecycleError("oos_max_drawdown_max 必须位于 (0, 1]")
        for name in ("paper_days_min", "paper_trades_min", "ic_lookback"):
            if int(getattr(self, name)) < 0:
                raise LifecycleError(f"{name} 不能为负")


@dataclass(frozen=True)
class ValueCriteria:
    """价值判据（D4 seq 10）：灰度→全量资金门槛，0 = 不启用。"""

    capital_min: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.capital_min)) or float(self.capital_min) < 0.0:
            raise LifecycleError("capital_min 必须为有限非负数")


@dataclass(frozen=True)
class GateCriteria:
    """判据分组（U-P051c-11）：准备度 + 价值。"""

    readiness: ReadinessCriteria = field(default_factory=ReadinessCriteria)
    value: ValueCriteria = field(default_factory=ValueCriteria)


@dataclass(frozen=True)
class GateDecision:
    """四值决策（D3/D10）。"""

    action: GateAction
    reasons: tuple[str, ...] = ()
    target: Optional[LifecycleStage] = None


@dataclass(frozen=True)
class TransitionRecord:
    """单条迁移审计记录（D9）；``at`` 由调用方传入，禁 ``datetime.now``。"""

    at: str
    action: str
    from_stage: str
    to_stage: str
    reasons: tuple[str, ...]
    fingerprint: StrategyFingerprint
    evidence_source: str = ""
    account_snapshot: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.at, str) or not _DATE_RE.match(self.at):
            raise LifecycleError(f"at 必须为 YYYY-MM-DD：{self.at!r}")
        if self.action not in _ACTION_VALUES:
            raise LifecycleError(f"未知动作：{self.action!r}")
        for name in ("from_stage", "to_stage"):
            if getattr(self, name) not in _STAGE_VALUES:
                raise LifecycleError(f"{name} 非法：{getattr(self, name)!r}")


@dataclass(frozen=True)
class LifecycleRecord:
    """策略生命周期记录：当前阶段 + 全量迁移历史。"""

    fingerprint: StrategyFingerprint
    stage: LifecycleStage
    history: tuple[TransitionRecord, ...] = ()

    def __post_init__(self) -> None:
        if self.history and self.stage.value != self.history[-1].to_stage:
            raise LifecycleError("stage 与 history 末条 to_stage 不一致")


def initial_record(fingerprint: StrategyFingerprint) -> LifecycleRecord:
    """新建记录：stage=DRAFT，history 为空。"""
    return LifecycleRecord(fingerprint=fingerprint, stage=LifecycleStage.DRAFT, history=())


def _catastrophic(stage: LifecycleStage, reason: str) -> GateDecision:
    """序 3/4 的立即定案：backtest 打回、paper/gray/live 终止。"""
    if stage == LifecycleStage.BACKTEST:
        return GateDecision(GateAction.RECYCLE, (reason,), LifecycleStage.DRAFT)
    if stage in (LifecycleStage.PAPER, LifecycleStage.GRAY, LifecycleStage.LIVE):
        return GateDecision(GateAction.KILL, (reason,), None)
    return GateDecision(GateAction.HOLD, (reason,), None)


def _ic_passes(ic_series: Optional[pd.Series], criteria: ReadinessCriteria) -> bool:
    """IC 尾部均值判据（D4 seq 8）：仅取非 NaN 尾部 ``ic_lookback`` 个。"""
    if ic_series is None or len(ic_series) == 0:
        return False
    series = ic_series.dropna()
    lookback = int(criteria.ic_lookback)
    tail = series.iloc[-lookback:] if lookback > 0 else series.iloc[0:0]
    if len(tail) == 0:
        return False
    return float(tail.mean()) >= float(criteria.ic_min)


def evaluate_gate(
    record: LifecycleRecord,
    evidence: StageEvidence,
    criteria: GateCriteria,
) -> GateDecision:
    """四值决策（D4 顺序 + D5 source 门 + D10 语义）。纯函数，无 now()。

    序 0-4 立即返回；序 5-12 评估完整判据表后返回（DESIGN F-I6）。
    """
    stage = record.stage
    if stage == LifecycleStage.RETIRED:
        return GateDecision(GateAction.HOLD, ("retired",), None)

    if stage == LifecycleStage.PAPER and evidence.source != "paper_record":
        return GateDecision(GateAction.HOLD, ("evidence_source",), None)

    metrics = evidence.metrics
    if metrics is None:
        return GateDecision(GateAction.HOLD, ("no_evidence",), None)

    readiness = criteria.readiness
    sharpe = float(metrics.sharpe_ratio)
    drawdown = float(metrics.max_drawdown)
    if sharpe < 0.0:
        return _catastrophic(stage, "oos_sharpe_negative")
    if drawdown > 2.0 * float(readiness.oos_max_drawdown_max):
        return _catastrophic(stage, "drawdown_catastrophic")

    reasons: list[str] = []
    if sharpe < float(readiness.oos_sharpe_min):
        reasons.append("oos_sharpe")
    if drawdown > float(readiness.oos_max_drawdown_max):
        reasons.append("oos_max_drawdown")

    if evidence.is_oos_decay is None:
        reasons.append("insufficient_signal")
    elif float(evidence.is_oos_decay) > float(readiness.is_oos_decay_max):
        reasons.append("is_oos_decay")

    if not _ic_passes(evidence.ic_series, readiness):
        reasons.append("ic")

    if stage == LifecycleStage.PAPER:
        if int(evidence.paper_days) < int(readiness.paper_days_min):
            reasons.append("paper_days")
        if int(evidence.paper_trades) < int(readiness.paper_trades_min):
            reasons.append("paper_trades")

    if stage == LifecycleStage.GRAY and float(criteria.value.capital_min) > 0.0:
        total = evidence.account_total
        if (
            total is None
            or not math.isfinite(float(total))
            or float(total) < float(criteria.value.capital_min)
        ):
            reasons.append("capital")

    if not reasons:
        target = _GO_TARGET.get(stage)
        if target is None:  # LIVE：已是最高阶段，无 GO 目标
            return GateDecision(GateAction.HOLD, ("no_go_target",), None)
        return GateDecision(GateAction.GO, (), target)

    if stage == LifecycleStage.BACKTEST:
        return GateDecision(GateAction.RECYCLE, tuple(reasons), LifecycleStage.DRAFT)
    return GateDecision(GateAction.HOLD, tuple(reasons), None)


def _transition(
    at: str,
    action: GateAction,
    from_stage: LifecycleStage,
    to_stage: LifecycleStage,
    reasons: Sequence[str],
    fingerprint: StrategyFingerprint,
) -> TransitionRecord:
    return TransitionRecord(
        at=at,
        action=action.value,
        from_stage=from_stage.value,
        to_stage=to_stage.value,
        reasons=tuple(reasons),
        fingerprint=fingerprint,
    )


def _validate_at(at: str) -> None:
    if not isinstance(at, str) or not _DATE_RE.match(at):
        raise LifecycleError(f"at 必须为 YYYY-MM-DD：{at!r}")


def _recycle_version(record: LifecycleRecord, new_version: Optional[str]) -> str:
    version = (new_version or "").strip()
    if not version:
        raise LifecycleError("RECYCLE 必须提供新的 version")
    seen = {transition.fingerprint.version for transition in record.history}
    seen.add(record.fingerprint.version)
    if version in seen:
        raise LifecycleError(f"RECYCLE 新版本与历史版本重复：{version}")
    return version


def apply(
    record: LifecycleRecord,
    decision: GateDecision,
    *,
    at: str,
    new_version: Optional[str] = None,
) -> LifecycleRecord:
    """落迁移：GO 一步 / HOLD 原地 / RECYCLE 回 draft / KILL（paper 一步、gray|live 两步）。"""
    _validate_at(at)
    if record.history and at < record.history[-1].at:
        raise LifecycleError(f"at 早于上一条记录：{at} < {record.history[-1].at}")

    stage = record.stage
    if stage == LifecycleStage.RETIRED:
        raise LifecycleError("retired 为终态")

    action = decision.action
    if action == GateAction.HOLD:
        if decision.target is not None:
            raise LifecycleError("HOLD 决策不得指定目标阶段")
        entry = _transition(at, action, stage, stage, decision.reasons, record.fingerprint)
        return LifecycleRecord(
            fingerprint=record.fingerprint, stage=stage, history=record.history + (entry,)
        )

    if action == GateAction.GO and stage == LifecycleStage.LIVE:
        raise LifecycleError("live 为最高阶段")

    target = _LEGAL_TARGET.get((stage, action))
    if target is None:
        raise LifecycleError(f"非法迁移: {stage.value} --{action.value}--> ?")
    if decision.target is not None and decision.target != target:
        raise LifecycleError(
            f"目标阶段与合法迁移不符: {action.value} 从 {stage.value} 应到 "
            f"{target.value}，实际 {decision.target.value}"
        )

    if action == GateAction.RECYCLE:
        fingerprint = replace(record.fingerprint, version=_recycle_version(record, new_version))
        entry = _transition(at, action, stage, target, decision.reasons, fingerprint)
        return LifecycleRecord(
            fingerprint=fingerprint, stage=target, history=record.history + (entry,)
        )

    if action == GateAction.KILL:
        if stage == LifecycleStage.PAPER:
            entry = _transition(at, action, stage, target, decision.reasons, record.fingerprint)
            return LifecycleRecord(
                fingerprint=record.fingerprint,
                stage=target,
                history=record.history + (entry,),
            )
        demote = _transition(
            at, action, stage, LifecycleStage.PAPER, ("kill_trigger",), record.fingerprint
        )
        retire = _transition(
            at,
            action,
            LifecycleStage.PAPER,
            LifecycleStage.RETIRED,
            decision.reasons,
            record.fingerprint,
        )
        return LifecycleRecord(
            fingerprint=record.fingerprint,
            stage=LifecycleStage.RETIRED,
            history=record.history + (demote, retire),
        )

    entry = _transition(at, action, stage, target, decision.reasons, record.fingerprint)
    return LifecycleRecord(
        fingerprint=record.fingerprint, stage=target, history=record.history + (entry,)
    )


def _json_safe(value: Any) -> Any:
    """递归归一为 JSON 原生类型，并校验 float 有限（I10）。"""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if not math.isfinite(number):
            raise LifecycleError("归档含 NaN/Inf")
        return number
    if value is None or isinstance(value, str):
        return value
    raise LifecycleError(f"归档含不可序列化类型: {type(value).__name__}")


def archive(record: LifecycleRecord, account: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """归档快照（D9）：JSON 往返稳定、无 NaN/Inf（I10）。"""
    payload: dict[str, Any] = {
        "schema_version": 1,
        "fingerprint": _json_safe(asdict(record.fingerprint)),
        "final_stage": record.stage.value,
        "history": [
            {
                "at": entry.at,
                "action": entry.action,
                "from_stage": entry.from_stage,
                "to_stage": entry.to_stage,
                "reasons": list(entry.reasons),
                "fingerprint": _json_safe(asdict(entry.fingerprint)),
                "evidence_source": entry.evidence_source,
                "account_snapshot": (
                    _json_safe(dict(entry.account_snapshot))
                    if entry.account_snapshot is not None
                    else None
                ),
            }
            for entry in record.history
        ],
        "account": _json_safe(dict(account)) if account is not None else None,
        "unresolved": [
            {"at": entry.at, "reasons": list(entry.reasons)}
            for entry in record.history
            if entry.action == GateAction.HOLD.value
        ],
    }
    return payload


def _coerce_action(action: str) -> GateAction:
    try:
        return GateAction(action)
    except ValueError as exc:
        raise LifecycleError(f"未知动作：{action!r}") from exc


def replay(records: Sequence[TransitionRecord]) -> tuple[LifecycleStage, ...]:
    """重放校验（D11/I9）：逐条核 from_stage 与当前一致，返回各步 to_stage。"""
    current = LifecycleStage.DRAFT
    walked: list[LifecycleStage] = []
    for entry in records:
        if entry.from_stage != current.value:
            raise LifecycleError(
                f"重放链断裂: 期望 from_stage={current.value}，实际 {entry.from_stage}"
            )
        action = _coerce_action(entry.action)
        if action == GateAction.HOLD:
            if entry.to_stage != entry.from_stage:
                raise LifecycleError("hold 记录必须 from_stage == to_stage")
        else:
            target = _LEGAL_TARGET.get((current, action))
            if target is None:
                raise LifecycleError(f"非法迁移: {current.value} --{action.value}--> ?")
            if entry.to_stage != target.value:
                raise LifecycleError(
                    f"迁移目标不符: {current.value} --{action.value}--> 应为 "
                    f"{target.value}，实际 {entry.to_stage}"
                )
        current = LifecycleStage(entry.to_stage)
        walked.append(current)
    return tuple(walked)


def resolve_monitor_action(overall_level: str, stage: LifecycleStage) -> GateAction:
    """监控级别 → 动作（D10）：入参字符串，不 import agents。"""
    if not isinstance(overall_level, str):
        raise LifecycleError(f"未知监控级别: {overall_level!r}")
    level = overall_level.strip().lower()
    if level not in ("green", "yellow", "red"):
        raise LifecycleError(f"未知监控级别: {overall_level!r}")
    if not isinstance(stage, LifecycleStage):
        raise LifecycleError(f"未知阶段: {stage!r}")
    if stage == LifecycleStage.RETIRED:
        raise LifecycleError("retired 无监控动作")
    if level in ("green", "yellow"):
        return GateAction.HOLD
    if stage in (LifecycleStage.PAPER, LifecycleStage.GRAY, LifecycleStage.LIVE):
        return GateAction.KILL
    if stage == LifecycleStage.BACKTEST:
        return GateAction.RECYCLE
    return GateAction.HOLD
