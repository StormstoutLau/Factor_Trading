"""实盘安全闸门：kill → circuit → rate → guard，全程审计与落盘。

fail-closed（D-G2）：任一检查异常 → ``allowed=False``。本类不自动平仓（D-G9/D12）。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace

from core.circuit_breaker import (
    CircuitConfig,
    CircuitDecision,
    CircuitSnapshot,
    CircuitState,
    allows_close,
    allows_open,
    evaluate_circuit,
)
from core.compliance import (
    RateLedger,
    RateLimitConfig,
    build_audit_payload,
    check_rate,
    day_key,
    ledger_from_dict,
    ledger_to_dict,
    record,
)
from core.event_log import EventType, IEventBus
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext, GuardPipeline
from core.live_bridge import LiveTradingBridge
from core.safety import (
    FaultPolicy,
    KillAction,
    KillCommand,
    KillDecision,
    KillEntry,
    KillLevel,
    KillState,
    allows,
    apply_command,
    effective_kill,
    from_dict,
    initial_kill_state,
    to_dict,
)
from live.safety_store import SafetyStateStore

logger = logging.getLogger(__name__)

_SOURCE = "live.safety_gate"


@dataclass(frozen=True)
class SafetyDecision:
    """一次事前检查的结论。"""

    allowed: bool
    action: str
    reasons: tuple[str, ...] = ()
    decision_id: str = ""
    kill_level: KillLevel | None = None
    circuit_state: CircuitState = CircuitState.NORMAL


class SafetyGate:
    """组合 kill/circuit/rate/guard 的发单前闸门（单实例单写者）。"""

    def __init__(
        self,
        *,
        event_log: IEventBus,
        store: SafetyStateStore,
        rate_config: RateLimitConfig,
        circuit_config: CircuitConfig,
        fault_policy: FaultPolicy,
        pipeline: GuardPipeline | None = None,
        operator: str = "system",
    ) -> None:
        self._event_log = event_log
        self._store = store
        self._rate_config = rate_config
        self._circuit_config = circuit_config
        self._fault_policy = fault_policy
        self._pipeline = pipeline or GuardPipeline.live_safe()
        self._operator = operator
        self._kill: KillState = initial_kill_state()
        self._ledger = RateLedger()
        self._snapshot = CircuitSnapshot()
        self._consecutive_rejects = 0
        self._equity_day = ""
        self._account_id = ""
        self._strategy_id = ""
        self._restore()

    # ---------- 属性 ----------

    @property
    def kill_decision(self) -> KillDecision:
        return effective_kill(self._kill, self._account_id, self._strategy_id)

    @property
    def circuit_decision(self) -> CircuitDecision:
        return evaluate_circuit(self._circuit_config, self._snapshot)

    # ---------- 核心：事前检查 ----------

    def pre_trade_check(
        self,
        intent: OrderIntent,
        ctx: GuardContext,
        *,
        account_id: str,
        strategy_id: str,
        ts: float,
        time_source: str = "local",
    ) -> SafetyDecision:
        """kill → circuit → rate → guard；任一阻断即返回并写 ``audit.risk_decision``。

        方向由 ``intent.action`` 推导（property，execution_policy.py L87-100）：
        BUY/SELL_SHORT=开、SELL/BUY_TO_COVER=平——kill 按 ``allows(OPEN/CLOSE)``、
        circuit 按 ``allows_open/close`` 分流（Step 6 F-I1：默认 kill 与 DERISK_ONLY
        均不得阻断平仓）。account_id/strategy_id 显式传参（F-D2）；价格/市值类输入
        以 ctx 为准（OrderIntent 无 price 字段，execution_policy.py L71-75）。
        """
        decision_id = uuid.uuid4().hex
        action = intent.action
        self._account_id = account_id
        self._strategy_id = strategy_id
        circuit = self.circuit_decision
        if action == "HOLD":
            self._audit_decision(
                decision_id,
                True,
                action,
                account_id,
                strategy_id,
                None,
                circuit,
                ("hold",),
                time_source,
            )
            return SafetyDecision(
                allowed=True,
                action=action,
                reasons=("hold",),
                decision_id=decision_id,
                circuit_state=circuit.state,
            )

        kill = self.kill_decision
        reasons: list[str] = []
        allowed = True
        # 方向分流（Step 6 F-I1）：由 intent.action 推导（execution_policy.py L87-100 property）
        # BUY/SELL_SHORT = 开仓方向；SELL/BUY_TO_COVER = 平仓方向。
        # 默认 kill（blocked_actions=(OPEN,)）只停开仓；DERISK_ONLY 放行平仓；HALTED 全停。
        is_open_direction = action in ("BUY", "SELL_SHORT")
        kill_action = KillAction.OPEN if is_open_direction else KillAction.CLOSE
        circuit_ok = allows_open(circuit) if is_open_direction else allows_close(circuit)
        if kill.blocked and not allows(kill, kill_action):
            allowed = False
            reasons.append(f"kill:{kill.level.value}" if kill.level else "kill")
        elif not circuit_ok:
            allowed = False
            reasons.append(f"circuit:{circuit.reason}")
        else:
            rate_ok, rate_reason = check_rate(self._ledger, ts, self._rate_config)
            if not rate_ok:
                allowed = False
                reasons.append(f"rate:{rate_reason}")
            else:
                try:
                    guard_reasons = self._pipeline.get_blocking_reasons(self._refresh_ctx(ctx))
                except Exception as exc:  # D-G2：实盘 fail-closed
                    logger.warning(f"Guard 检查异常（已阻断）: {exc}")
                    allowed = False
                    reasons.append(f"guard_error:{exc}")
                else:
                    if guard_reasons:
                        allowed = False
                        reasons.extend(guard_reasons)

        if allowed:
            self._ledger = record(self._ledger, ts, is_cancel=False)
            self._persist()

        self._audit_decision(
            decision_id,
            allowed,
            action,
            account_id,
            strategy_id,
            kill.level,
            circuit,
            tuple(reasons),
            time_source,
        )
        return SafetyDecision(
            allowed=allowed,
            action=action,
            reasons=tuple(reasons),
            decision_id=decision_id,
            kill_level=kill.level,
            circuit_state=circuit.state,
        )

    # ---------- S1 kill ----------

    def gate_kill(
        self, level: KillLevel, key: str, active: bool, reason: str, *, ts: float
    ) -> KillEntry:
        """更新 kill 状态 → 落盘 → ``audit.kill``。"""
        command = KillCommand(
            level=level,
            key=key,
            active=active,
            reason=reason,
            operator=self._operator,
            ts=ts,
            blocked_actions=(KillAction.OPEN,),
        )
        self._kill, entry = apply_command(self._kill, command)
        self._persist()
        self._event_log.append(
            EventType.AUDIT_KILL,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                level=level.value,
                key=key,
                active=active,
                reason=reason,
                blocked_actions=[a.value for a in entry.blocked_actions],
            ),
            source=_SOURCE,
        )
        return entry

    # ---------- S3 熔断 ----------

    def update_equity(self, equity: float, *, ts: float) -> CircuitDecision:
        """喂入账户权益并重评熔断（D-4 新增；按日切基准）。"""
        day = day_key(ts)
        snapshot = self._snapshot
        if snapshot.day_start_equity <= 0 or self._equity_day != day:
            snapshot = replace(snapshot, day_start_equity=equity, peak_equity=equity, equity=equity)
            self._equity_day = day
        else:
            snapshot = replace(
                snapshot, equity=equity, peak_equity=max(snapshot.peak_equity, equity)
            )
        self._snapshot = snapshot
        self._persist()
        return self.circuit_decision

    def on_order_result(self, *, rejected: bool, ts: float) -> CircuitDecision:
        """更新连续拒单 → 重评熔断 → ``audit.circuit``。

        ``ts`` 预留（F-I5）：审计事件时间由 ``EventLogEntry.ts`` 承载，payload 不重复携带。
        """
        self._consecutive_rejects = self._consecutive_rejects + 1 if rejected else 0
        self._snapshot = replace(self._snapshot, consecutive_rejects=self._consecutive_rejects)
        decision = self.circuit_decision
        self._persist()
        self._event_log.append(
            EventType.AUDIT_CIRCUIT,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                state=decision.state.value,
                reason=decision.reason,
                alerts=list(decision.alerts),
                consecutive_rejects=self._consecutive_rejects,
            ),
            source=_SOURCE,
        )
        return decision

    # ---------- S1 一键撤单 ----------

    def cancel_all(self, bridge: LiveTradingBridge, *, ts: float) -> int:
        """调 ``cancel_orders(None)`` 撤全部未成交（D-G7；F-D1 按实际 API）。"""
        cancelled = int(bridge.cancel_orders(None))
        self._event_log.append(
            EventType.AUDIT_CANCEL,
            build_audit_payload(
                operator=self._operator,
                time_source="local",
                scope="all",
                cancelled_count=cancelled,
                ts=ts,
            ),
            source=_SOURCE,
        )
        return cancelled

    # ---------- 内部 ----------

    def _refresh_ctx(self, ctx: GuardContext) -> GuardContext:
        """用台账刷新日计数（C-7）。"""
        return replace(
            ctx,
            daily_order_count=max(ctx.daily_order_count, self._ledger.daily_orders),
            daily_cancel_count=max(ctx.daily_cancel_count, self._ledger.daily_cancels),
        )

    def _audit_decision(
        self,
        decision_id: str,
        allowed: bool,
        action: str,
        account_id: str,
        strategy_id: str,
        kill_level: KillLevel | None,
        circuit: CircuitDecision,
        reasons: tuple[str, ...],
        time_source: str,
    ) -> None:
        self._event_log.append(
            EventType.AUDIT_RISK_DECISION,
            build_audit_payload(
                operator=self._operator,
                time_source=time_source,
                decision_id=decision_id,
                allowed=allowed,
                action=action,
                account_id=account_id,
                strategy_id=strategy_id,
                kill_level=kill_level.value if kill_level else None,
                circuit_state=circuit.state.value,
                reasons=list(reasons),
            ),
            source=_SOURCE,
        )

    def _restore(self) -> None:
        """逐段容错恢复（C-3）；损坏段回落默认，不整文件丢弃。"""
        data = self._store.load()
        if not data:
            return
        kill_raw = data.get("kill")
        if isinstance(kill_raw, dict):
            try:
                self._kill = from_dict(kill_raw)
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(f"kill 状态恢复失败，回落空状态: {exc}")
        ledger_raw = data.get("ledger")
        if isinstance(ledger_raw, dict):
            try:
                self._ledger = ledger_from_dict(ledger_raw)
            except (ValueError, TypeError) as exc:
                logger.warning(f"速率台账恢复失败，回落空台账: {exc}")
        circuit_raw = data.get("circuit")
        if isinstance(circuit_raw, dict):
            rejects = circuit_raw.get("consecutive_rejects")
            if isinstance(rejects, int) and rejects >= 0:
                self._consecutive_rejects = rejects
            raw_day = circuit_raw.get("day_start_equity", 0.0)
            raw_peak = circuit_raw.get("peak_equity", 0.0)
            raw_eq = circuit_raw.get("equity", 0.0)
            # F-I3：恢复权益基准，跨重启同日不重置（update_equity 按 equity_day 判日切）
            self._snapshot = CircuitSnapshot(
                day_start_equity=float(raw_day) if isinstance(raw_day, (int, float)) else 0.0,
                peak_equity=float(raw_peak) if isinstance(raw_peak, (int, float)) else 0.0,
                equity=float(raw_eq) if isinstance(raw_eq, (int, float)) else 0.0,
                consecutive_rejects=self._consecutive_rejects,
            )
        day = data.get("equity_day")
        if isinstance(day, str):
            self._equity_day = day

    def _persist(self) -> None:
        self._store.save(
            {
                "kill": to_dict(self._kill),
                "ledger": ledger_to_dict(self._ledger),
                "circuit": {
                    "consecutive_rejects": self._consecutive_rejects,
                    "day_start_equity": self._snapshot.day_start_equity,
                    "peak_equity": self._snapshot.peak_equity,
                    "equity": self._snapshot.equity,
                },
                "equity_day": self._equity_day,
            }
        )
