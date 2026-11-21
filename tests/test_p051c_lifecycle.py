"""P-051c L/G/R 组：生命周期状态机（14 + 10 + 5 = 29 条）。"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from core.lifecycle import (
    GateAction,
    GateCriteria,
    GateDecision,
    LifecycleError,
    LifecycleRecord,
    LifecycleStage,
    StageEvidence,
    StrategyFingerprint,
    TransitionRecord,
    ValueCriteria,
    apply,
    archive,
    evaluate_gate,
    initial_record,
    replay,
    resolve_monitor_action,
)
from core.metrics import MetricsResult

DRAFT = LifecycleStage.DRAFT
BACKTEST = LifecycleStage.BACKTEST
PAPER = LifecycleStage.PAPER
GRAY = LifecycleStage.GRAY
LIVE = LifecycleStage.LIVE
RETIRED = LifecycleStage.RETIRED

GO = GateAction.GO
HOLD = GateAction.HOLD
RECYCLE = GateAction.RECYCLE
KILL = GateAction.KILL


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _fp(version: str = "1.0.0") -> StrategyFingerprint:
    return StrategyFingerprint(
        strategy_id="mom", version=version, param_snapshot={"lookback": 5}, code_hash="abc123"
    )


def _metrics(sharpe: float = 1.5, drawdown: float = 0.10) -> MetricsResult:
    return MetricsResult(
        total_return=0.10,
        annual_return=0.12,
        annual_volatility=0.08,
        sharpe_ratio=sharpe,
        max_drawdown=drawdown,
        final_value=1.10,
        n_periods=60,
        risk_free_rate=0.03,
    )


def _evidence(**overrides: object) -> StageEvidence:
    payload: dict[str, object] = {
        "source": "walk_forward",
        "metrics": _metrics(),
        "ic_series": pd.Series([0.10] * 60),
        "is_oos_decay": 0.10,
        "paper_days": 30,
        "paper_trades": 60,
    }
    payload.update(overrides)
    return StageEvidence(**payload)  # type: ignore[arg-type]


def _to_stage(stage: LifecycleStage) -> LifecycleRecord:
    """从 draft 沿 GO 链推进到目标阶段。"""
    path = {
        DRAFT: [],
        BACKTEST: [BACKTEST],
        PAPER: [BACKTEST, PAPER],
        GRAY: [BACKTEST, PAPER, GRAY],
        LIVE: [BACKTEST, PAPER, GRAY, LIVE],
    }[stage]
    record = initial_record(_fp())
    for index, target in enumerate(path):
        record = apply(record, GateDecision(GO, (), target), at=f"2026-01-{index + 2:02d}")
    return record


# ---------------------------------------------------------------------------
# L 组：状态机迁移（14）
# ---------------------------------------------------------------------------


def test_l1_four_stage_go_chain():
    record = _to_stage(LIVE)
    assert record.stage is LIVE
    assert len(record.history) == 4
    assert all(entry.action == "go" for entry in record.history)
    assert [entry.to_stage for entry in record.history] == ["backtest", "paper", "gray", "live"]


def test_l2_live_go_raises():
    record = _to_stage(LIVE)
    with pytest.raises(LifecycleError, match="live 为最高阶段"):
        apply(record, GateDecision(GO, (), None), at="2026-02-01")


def test_l3_hold_stays_in_place_and_records():
    record = _to_stage(BACKTEST)
    updated = apply(record, GateDecision(HOLD, ("paper_days",), None), at="2026-02-01")
    assert updated.stage is BACKTEST
    entry = updated.history[-1]
    assert entry.action == "hold"
    assert entry.from_stage == entry.to_stage == "backtest"
    assert entry.reasons == ("paper_days",)
    with pytest.raises(LifecycleError, match="HOLD"):
        apply(record, GateDecision(HOLD, (), BACKTEST), at="2026-02-01")


def test_l4_recycle_requires_new_version():
    record = _to_stage(BACKTEST)
    updated = apply(
        record, GateDecision(RECYCLE, ("oos_sharpe",), DRAFT), at="2026-02-01", new_version="1.0.1"
    )
    assert updated.stage is DRAFT
    assert updated.fingerprint.version == "1.0.1"
    assert updated.fingerprint.code_hash == record.fingerprint.code_hash
    assert updated.history[-1].action == "recycle"


def test_l5_recycle_without_version_raises():
    record = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError, match="version"):
        apply(record, GateDecision(RECYCLE, ("oos_sharpe",), DRAFT), at="2026-02-01")


def test_l6_recycle_duplicate_version_raises():
    record = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError, match="重复"):
        apply(
            record,
            GateDecision(RECYCLE, ("oos_sharpe",), DRAFT),
            at="2026-02-01",
            new_version="1.0.0",
        )
    recycled = apply(record, GateDecision(RECYCLE, (), DRAFT), at="2026-02-01", new_version="1.0.1")
    recycled = apply(recycled, GateDecision(GO, (), BACKTEST), at="2026-02-02")
    with pytest.raises(LifecycleError, match="重复"):
        apply(
            recycled,
            GateDecision(RECYCLE, (), DRAFT),
            at="2026-02-03",
            new_version="1.0.0",
        )


def test_l7_illegal_transitions_raise():
    draft = initial_record(_fp())
    with pytest.raises(LifecycleError, match="非法迁移"):
        apply(draft, GateDecision(KILL, (), None), at="2026-02-01")
    with pytest.raises(LifecycleError, match="非法迁移"):
        apply(draft, GateDecision(RECYCLE, (), DRAFT), at="2026-02-01", new_version="2.0.0")
    backtest = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError, match="非法迁移"):
        apply(backtest, GateDecision(KILL, (), None), at="2026-02-01")


def test_l8_retired_is_terminal():
    record = _to_stage(PAPER)
    retired = apply(record, GateDecision(KILL, ("oos_sharpe_negative",), None), at="2026-02-01")
    assert retired.stage is RETIRED
    decision = evaluate_gate(retired, _evidence(), GateCriteria())
    assert decision.action is HOLD
    assert decision.reasons == ("retired",)
    with pytest.raises(LifecycleError, match="终态"):
        apply(retired, GateDecision(HOLD, (), None), at="2026-02-02")
    # D10 监控映射（纯字符串入参，零 agents 依赖）
    assert resolve_monitor_action("green", LIVE) is HOLD
    assert resolve_monitor_action("yellow", PAPER) is HOLD
    assert resolve_monitor_action("red", PAPER) is KILL
    assert resolve_monitor_action("red", BACKTEST) is RECYCLE
    assert resolve_monitor_action("red", DRAFT) is HOLD
    with pytest.raises(LifecycleError):
        resolve_monitor_action("red", RETIRED)
    with pytest.raises(LifecycleError):
        resolve_monitor_action("purple", PAPER)


def test_l9_kill_from_paper_one_record():
    record = _to_stage(PAPER)
    retired = apply(record, GateDecision(KILL, ("oos_sharpe_negative",), None), at="2026-02-01")
    assert len(retired.history) == len(record.history) + 1
    entry = retired.history[-1]
    assert (entry.from_stage, entry.to_stage) == ("paper", "retired")
    assert entry.reasons == ("oos_sharpe_negative",)


def test_l10_kill_from_gray_two_records():
    record = _to_stage(GRAY)
    retired = apply(record, GateDecision(KILL, ("drawdown_catastrophic",), None), at="2026-02-01")
    assert len(retired.history) == len(record.history) + 2
    demote, retire = retired.history[-2], retired.history[-1]
    assert (demote.from_stage, demote.to_stage) == ("gray", "paper")
    assert demote.reasons == ("kill_trigger",)
    assert (retire.from_stage, retire.to_stage) == ("paper", "retired")
    assert retire.reasons == ("drawdown_catastrophic",)
    assert demote.at == retire.at == "2026-02-01"


def test_l11_kill_from_live_two_records():
    record = _to_stage(LIVE)
    retired = apply(record, GateDecision(KILL, ("drawdown_catastrophic",), None), at="2026-02-01")
    assert retired.stage is RETIRED
    assert (retired.history[-2].from_stage, retired.history[-2].to_stage) == ("live", "paper")
    assert (retired.history[-1].from_stage, retired.history[-1].to_stage) == ("paper", "retired")


def test_l12_at_validation():
    record = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError):
        apply(record, GateDecision(HOLD, (), None), at="2026-01-01")
    with pytest.raises(LifecycleError):
        apply(record, GateDecision(HOLD, (), None), at="2026/02/01")


def test_l13_record_contracts():
    record = initial_record(_fp())
    assert record.stage is DRAFT
    assert record.history == ()
    backtest = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError, match="history"):
        LifecycleRecord(fingerprint=_fp(), stage=LIVE, history=backtest.history)
    with pytest.raises(LifecycleError):
        StrategyFingerprint(strategy_id="", version="1.0.0", param_snapshot={}, code_hash="x")


def test_l14_deterministic():
    record = _to_stage(BACKTEST)
    evidence = _evidence()
    assert evaluate_gate(record, evidence, GateCriteria()) == evaluate_gate(
        record, evidence, GateCriteria()
    )
    first = apply(record, GateDecision(HOLD, ("ic",), None), at="2026-02-01")
    second = apply(record, GateDecision(HOLD, ("ic",), None), at="2026-02-01")
    assert first == second


# ---------------------------------------------------------------------------
# G 组：判据评估（10）
# ---------------------------------------------------------------------------


def test_g1_negative_sharpe_recycles_or_kills():
    criteria = GateCriteria()
    backtest = evaluate_gate(_to_stage(BACKTEST), _evidence(metrics=_metrics(-0.5)), criteria)
    assert backtest.action is RECYCLE
    assert backtest.target is DRAFT
    assert backtest.reasons == ("oos_sharpe_negative",)
    paper = evaluate_gate(
        _to_stage(PAPER), _evidence(source="paper_record", metrics=_metrics(-0.5)), criteria
    )
    assert paper.action is KILL
    assert paper.reasons == ("oos_sharpe_negative",)


def test_g2_low_sharpe_backtest_recycles():
    decision = evaluate_gate(
        _to_stage(BACKTEST), _evidence(metrics=_metrics(sharpe=0.3)), GateCriteria()
    )
    assert decision.action is RECYCLE
    assert "oos_sharpe" in decision.reasons


def test_g3_drawdown_over_limit_holds():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", metrics=_metrics(drawdown=0.30)),
        GateCriteria(),
    )
    assert decision.action is HOLD
    assert "oos_max_drawdown" in decision.reasons


def test_g4_drawdown_catastrophic_kills():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", metrics=_metrics(drawdown=0.60)),
        GateCriteria(),
    )
    assert decision.action is KILL
    assert decision.reasons == ("drawdown_catastrophic",)


def test_g5_decay_over_limit_holds():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", is_oos_decay=0.9),
        GateCriteria(),
    )
    assert decision.action is HOLD
    assert "is_oos_decay" in decision.reasons


def test_g6_decay_none_insufficient_signal():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", is_oos_decay=None),
        GateCriteria(),
    )
    assert decision.action is HOLD
    assert "insufficient_signal" in decision.reasons


def test_g7_ic_below_threshold_holds():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", ic_series=pd.Series([0.001] * 60)),
        GateCriteria(),
    )
    assert decision.action is HOLD
    assert "ic" in decision.reasons


def test_g8_paper_days_and_trades_hold():
    decision = evaluate_gate(
        _to_stage(PAPER),
        _evidence(source="paper_record", paper_days=19, paper_trades=49),
        GateCriteria(),
    )
    assert decision.action is HOLD
    assert "paper_days" in decision.reasons
    assert "paper_trades" in decision.reasons


def test_g9_source_gate_holds():
    decision = evaluate_gate(_to_stage(PAPER), _evidence(source="walk_forward"), GateCriteria())
    assert decision.action is HOLD
    assert decision.reasons == ("evidence_source",)


def test_g10_capital_gate_holds():
    criteria = GateCriteria(value=ValueCriteria(capital_min=1_000_000.0))
    blocked = evaluate_gate(_to_stage(GRAY), _evidence(account_total=None), criteria)
    assert blocked.action is HOLD
    assert "capital" in blocked.reasons
    low = evaluate_gate(_to_stage(GRAY), _evidence(account_total=500_000.0), criteria)
    assert low.action is HOLD
    passed = evaluate_gate(_to_stage(GRAY), _evidence(account_total=2_000_000.0), criteria)
    assert passed.action is GO
    assert passed.target is LIVE


# ---------------------------------------------------------------------------
# R 组：归档与重放（5）
# ---------------------------------------------------------------------------


def test_r1_archive_structure():
    payload = archive(_to_stage(GRAY), {"total": 10_000_000.0})
    assert set(payload) == {
        "schema_version",
        "fingerprint",
        "final_stage",
        "history",
        "account",
        "unresolved",
    }
    assert payload["schema_version"] == 1
    assert payload["final_stage"] == "gray"
    assert len(payload["history"]) == 3
    assert payload["fingerprint"]["strategy_id"] == "mom"


def test_r2_archive_json_roundtrip():
    payload = archive(_to_stage(GRAY), {"total": 10_000_000.0, "cash": 1_000_000.0})
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload


def test_r3_archive_rejects_nan():
    record = _to_stage(BACKTEST)
    with pytest.raises(LifecycleError, match="NaN"):
        archive(record, {"total": float("nan")})
    with pytest.raises(LifecycleError, match="NaN"):
        archive(record, {"total": float("inf")})


def test_r4_replay_prefix_converges_with_hold():
    record = _to_stage(BACKTEST)
    record = apply(record, GateDecision(HOLD, ("paper_days",), None), at="2026-02-01")
    record = apply(record, GateDecision(GO, (), PAPER), at="2026-02-02")
    walked = replay(record.history)
    assert walked[-1] is PAPER
    assert len(walked) == 3
    for size in range(1, len(record.history) + 1):
        assert replay(record.history[:size]) == walked[:size]


def test_r5_replay_broken_chain_raises():
    record = _to_stage(BACKTEST)
    broken = (
        TransitionRecord(
            at="2026-02-01",
            action="go",
            from_stage="paper",
            to_stage="gray",
            reasons=(),
            fingerprint=_fp(),
        ),
    )
    with pytest.raises(LifecycleError, match="重放链断裂"):
        replay(broken)
    wrong_target = (
        TransitionRecord(
            at="2026-02-01",
            action="go",
            from_stage="draft",
            to_stage="live",
            reasons=(),
            fingerprint=_fp(),
        ),
    )
    with pytest.raises(LifecycleError, match="迁移目标不符"):
        replay(wrong_target)
    bad_hold = (
        TransitionRecord(
            at="2026-02-01",
            action="hold",
            from_stage="draft",
            to_stage="backtest",
            reasons=(),
            fingerprint=_fp(),
        ),
    )
    with pytest.raises(LifecycleError, match="hold"):
        replay(bad_hold)
    assert len(record.history) == 1
