"""P-052 K 组：三级 kill switch + 故障决策（K1-K14）。"""

from __future__ import annotations

import pytest

from core.safety import (
    FaultAction,
    FaultType,
    KillAction,
    KillCommand,
    KillLevel,
    allows,
    apply_command,
    decide_fault,
    default_fault_policy,
    effective_kill,
    from_dict,
    initial_kill_state,
    to_dict,
)


def _cmd(level: KillLevel, key: str = "", active: bool = True, **kwargs) -> KillCommand:
    return KillCommand(
        level=level,
        key=key,
        active=active,
        reason=kwargs.get("reason", "test"),
        operator=kwargs.get("operator", "tester"),
        ts=kwargs.get("ts", 1.0),
        blocked_actions=kwargs.get("blocked_actions", (KillAction.OPEN,)),
    )


def test_k1_empty_state_allows_all():
    """K1：空状态不阻断。"""
    state = initial_kill_state()
    decision = effective_kill(state, "ACC", "STRAT")
    assert decision.blocked is False
    assert allows(decision, KillAction.OPEN) is True
    assert allows(decision, KillAction.CLOSE) is True


def test_k2_global_kill_blocks():
    """K2：GLOBAL 生效。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.GLOBAL))
    decision = effective_kill(state, "ACC", "STRAT")
    assert decision.blocked is True
    assert decision.level is KillLevel.GLOBAL


def test_k3_account_kill_blocks():
    """K3：ACCOUNT 生效（按 account_id 匹配）。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.ACCOUNT, "ACC"))
    assert effective_kill(state, "ACC", "STRAT").blocked is True
    assert effective_kill(state, "OTHER", "STRAT").blocked is False


def test_k4_strategy_kill_blocks():
    """K4：STRATEGY 生效（按 strategy_id 匹配）。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.STRATEGY, "STRAT"))
    assert effective_kill(state, "ACC", "STRAT").blocked is True
    assert effective_kill(state, "ACC", "OTHER").blocked is False


def test_k5_global_overrides_account():
    """K5：GLOBAL > ACCOUNT。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.ACCOUNT, "ACC", reason="acct"))
    state, _ = apply_command(state, _cmd(KillLevel.GLOBAL, "", reason="global"))
    decision = effective_kill(state, "ACC", "STRAT")
    assert decision.level is KillLevel.GLOBAL
    assert decision.reason == "global"


def test_k6_account_overrides_strategy():
    """K6：ACCOUNT > STRATEGY。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.STRATEGY, "STRAT", reason="st"))
    state, _ = apply_command(state, _cmd(KillLevel.ACCOUNT, "ACC", reason="acct"))
    decision = effective_kill(state, "ACC", "STRAT")
    assert decision.level is KillLevel.ACCOUNT
    assert decision.reason == "acct"


def test_k7_low_level_disable_does_not_clear_high_level():
    """K7（I3）：低层 disable 不解除高层。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.GLOBAL, "", reason="global"))
    state, _ = apply_command(state, _cmd(KillLevel.STRATEGY, "STRAT", active=False))
    decision = effective_kill(state, "ACC", "STRAT")
    assert decision.blocked is True
    assert decision.level is KillLevel.GLOBAL


def test_k8_same_key_overwrites():
    """K8：同 (level,key) 覆盖，不累积。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.ACCOUNT, "ACC", active=True))
    state, _ = apply_command(state, _cmd(KillLevel.ACCOUNT, "ACC", active=False))
    assert len(state.entries) == 1
    assert state.entries[0].active is False
    assert effective_kill(state, "ACC", "STRAT").blocked is False


def test_k9_blocked_actions_can_include_close():
    """K9：blocked_actions 含 CLOSE 时阻断平仓。"""
    actions = (KillAction.OPEN, KillAction.CLOSE)
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.GLOBAL, blocked_actions=actions))
    decision = effective_kill(state, "ACC", "STRAT")
    assert allows(decision, KillAction.OPEN) is False
    assert allows(decision, KillAction.CLOSE) is False


def test_k10_allows_three_actions():
    """K10：allows 三类动作按 blocked_actions 判定。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.GLOBAL))
    decision = effective_kill(state, "ACC", "STRAT")
    assert allows(decision, KillAction.OPEN) is False
    assert allows(decision, KillAction.CLOSE) is True
    assert allows(decision, KillAction.CANCEL) is True


def test_k11_serialization_roundtrip():
    """K11：to_dict/from_dict 往返一致。"""
    state, _ = apply_command(initial_kill_state(), _cmd(KillLevel.ACCOUNT, "ACC"))
    restored = from_dict(to_dict(state))
    assert restored == state
    raw = to_dict(state)
    assert raw["entries"][0]["level"] == "account"
    assert raw["entries"][0]["blocked_actions"] == ["open"]


def test_k12_unknown_enum_raises():
    """K12：未知枚举值抛 ValueError。"""
    with pytest.raises(ValueError):
        from_dict({"entries": [{"level": "galaxy", "key": ""}]})
    with pytest.raises(ValueError):
        from_dict({"entries": [{"level": "global", "blocked_actions": ["nuke"]}]})


def test_k13_decide_fault_disconnect_boundary():
    """K13：断线 attempts<3 重试，达到 3 次升级。"""
    policy = default_fault_policy()
    for attempts in (0, 1, 2):
        assert decide_fault(policy, FaultType.DISCONNECT, attempts) == (FaultAction.RETRY,)
    assert decide_fault(policy, FaultType.DISCONNECT, 3) == (
        FaultAction.PAUSE_NEW,
        FaultAction.RECONCILE,
    )


def test_k14_decide_fault_restart_and_reject():
    """K14：柜台重启 0 次直接全撤；拒单 1 次升级到暂停新增。"""
    policy = default_fault_policy()
    assert decide_fault(policy, FaultType.COUNTER_RESTART, 0) == (
        FaultAction.CANCEL_ALL,
        FaultAction.RECONCILE,
        FaultAction.HALT,
    )
    assert decide_fault(policy, FaultType.REJECT, 0) == (FaultAction.RETRY,)
    assert decide_fault(policy, FaultType.REJECT, 1) == (FaultAction.PAUSE_NEW,)
    assert decide_fault(policy, FaultType.PARTIAL_FILL, 0) == (FaultAction.RECONCILE,)
