"""P-052 A 组：审计事件与 payload 约定（A1-A6）。"""

from __future__ import annotations

import inspect

import pytest

from core.compliance import build_audit_payload
from core.event_log import AUDIT_EVENT_TYPES, EventLog, EventType


def _log(tmp_path) -> EventLog:
    return EventLog(log_path=tmp_path / "events.jsonl")


def test_a1_audit_constants_and_frozenset(tmp_path):
    """A1：8 常量值与 AUDIT_EVENT_TYPES 一致。"""
    expected = {
        "audit.intent",
        "audit.risk_decision",
        "audit.order",
        "audit.fill",
        "audit.cancel",
        "audit.reconcile",
        "audit.kill",
        "audit.circuit",
    }
    assert len(AUDIT_EVENT_TYPES) == 8
    assert AUDIT_EVENT_TYPES == expected
    values = {
        EventType.AUDIT_INTENT,
        EventType.AUDIT_RISK_DECISION,
        EventType.AUDIT_ORDER,
        EventType.AUDIT_FILL,
        EventType.AUDIT_CANCEL,
        EventType.AUDIT_RECONCILE,
        EventType.AUDIT_KILL,
        EventType.AUDIT_CIRCUIT,
    }
    assert values == expected


def test_a2_append_signature_unchanged():
    """A2（I12）：EventLog.append 签名不变。"""
    params = list(inspect.signature(EventLog.append).parameters)
    assert params == ["self", "event_type", "payload", "source"]


def test_a3_audit_events_replay(tmp_path):
    """A3：audit.* 事件可读取回放。"""
    log = _log(tmp_path)
    log.append(EventType.AUDIT_INTENT, {"symbol": "AAA"}, source="test")
    log.append(EventType.AUDIT_FILL, {"symbol": "AAA"}, source="test")
    intent_entries = log.read(event_type=EventType.AUDIT_INTENT)
    assert len(intent_entries) == 1
    assert intent_entries[0].payload == {"symbol": "AAA"}
    assert intent_entries[0].type in AUDIT_EVENT_TYPES


def test_a4_seq_monotonic(tmp_path):
    """A4（I6）：seq 单调递增。"""
    log = _log(tmp_path)
    entries = [log.append(EventType.AUDIT_ORDER, {"i": i}) for i in range(3)]
    seqs = [e.seq for e in entries]
    assert seqs == sorted(seqs)
    assert seqs == [1, 2, 3]


def test_a5_build_audit_payload_injects_keys():
    """A5：build_audit_payload 强制注入 operator/time_source。"""
    payload = build_audit_payload(operator="ops", time_source="local", action="BUY")
    assert payload["operator"] == "ops"
    assert payload["time_source"] == "local"
    assert payload["action"] == "BUY"


def test_a6_duplicate_key_rejected():
    """A6：重复传入 operator/time_source 被拒绝（Python 绑定 TypeError 或被守卫拦截）。"""
    for dup_key in ("operator", "time_source"):
        with pytest.raises((ValueError, TypeError)):
            build_audit_payload(operator="ops", time_source="local", **{dup_key: "x"})
