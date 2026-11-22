"""TradingGateway：submit 八步固定序 + 回报/对账编排（P-053 D10 / P-054 D8-D11）。"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable

from core.compliance import (
    RateLedger,
    RateLimitConfig,
    build_audit_payload,
    check_rate,
    record,
)
from core.event_log import EventType, IEventBus
from core.execution_policy import OrderIntent
from core.guard_pipeline import GuardContext
from live.channel import (
    CapabilityError,
    ChannelAdapter,
    ChannelLimits,
    ChannelRejected,
    ChannelState,
    ChannelUnavailable,
    FillReport,
    OrderReport,
    require_capability,
    resolve_limits,
)
from live.corporate_actions import CorporateAction, attribute_break
from live.events import OutboxEventType, fill_event, order_event
from live.flow_control import CancelResult, FtdBudget, OrderFlowBudget
from live.ledger import Ledger, LedgerEntry
from live.ledger_store import LedgerStore
from live.orders import (
    FillRecord,
    OrderRecord,
    OrderRequest,
    OrderState,
    OrderTransitionError,
    from_request,
    make_client_order_id,
    transition,
)
from live.query_scheduler import QueryScheduler
from live.reconcile import (
    BreakLevel,
    ParityConfig,
    ReconcileConfig,
    ReconcileReport,
    reconcile_positions,
)
from live.safety_gate import SafetyDecision, SafetyGate
from live.session_calendar import Calendar, can_submit, local_day, session_phase

_SOURCE = "live.gateway"


@dataclass(frozen=True)
class SubmitResult:
    accepted: bool
    client_order_id: str
    state: OrderState
    decision: SafetyDecision | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class CancelAllReport:
    """D-1：落 gateway（依赖 CancelResult）；flow_control 不 import gateway。"""

    requested: int
    submitted: int
    deferred: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]


class TradingGateway:
    def __init__(
        self,
        *,
        adapter: ChannelAdapter,
        gate: SafetyGate,
        ledger: Ledger,
        store: LedgerStore,
        event_log: IEventBus,
        calendar: Calendar | None = None,
        reconcile_config: ReconcileConfig | None = None,
        parity_config: ParityConfig | None = None,
        actions: tuple[CorporateAction, ...] = (),
        rate_config: RateLimitConfig | None = None,
        grace_seconds: float = 60.0,
        operator: str = "system",
        clock: Callable[[], float] = time.time,
        cost_buffer: float = 0.005,  # IMPL D-1：§5 表要求可配
        ftd_budget: FtdBudget | None = None,
        order_flow_budget: OrderFlowBudget | None = None,
        scheduler: QueryScheduler | None = None,
    ) -> None:
        self._adapter = adapter
        self._gate = gate
        self._ledger = ledger
        self._store = store
        self._event_log = event_log
        self._calendar = calendar
        self._reconcile_config = reconcile_config or ReconcileConfig()
        self._parity_config = parity_config or ParityConfig()
        self._actions = actions
        self._rate_config = rate_config or RateLimitConfig()
        self._grace_seconds = grace_seconds
        self._operator = operator
        self._clock = clock
        self._cost_buffer = cost_buffer
        self._ftd = ftd_budget
        self._order_flow = order_flow_budget
        self._scheduler = scheduler
        self._recovery_state = "incomplete"
        self._orders: dict[str, OrderRecord] = {}
        self._limits: ChannelLimits | None = None
        self._submit_ledger = RateLedger()
        self._cancel_ledger = RateLedger()
        self._query_ledger = RateLedger()
        self._query_config: RateLimitConfig | None = None  # start() 按 resolve_limits 填（F-I8）
        self._submit_config: RateLimitConfig | None = None  # start() 按 resolve_limits 填（F-R5-4）
        self._cancel_config: RateLimitConfig | None = None  # 同上：撤单桶亦取三方最小

    # ---------- 生命周期 ----------

    def start(self) -> None:
        if self._adapter.capability.account_level != "cash":
            raise CapabilityError("ledger supports cash accounts only (D15)")
        self._adapter.connect()
        self._limits = resolve_limits(
            self._adapter.capability,
            internal_per_sec=self._rate_config.max_per_second,
            internal_per_day=self._rate_config.max_per_day,
        )
        self._query_config = RateLimitConfig(
            max_per_second=int(max(1, round(self._limits.query_per_sec))),
            max_per_day=self._rate_config.max_per_day,  # 无查询日上限证据，保守沿用（F-I8）
        )
        self._submit_config = RateLimitConfig(  # F-R5-4：委托桶接三方最小（D11 双层）
            max_per_second=max(1, int(round(self._limits.submit_per_sec))),
            max_per_day=min(self._rate_config.max_per_day, self._limits.submit_per_day),
        )
        self._cancel_config = RateLimitConfig(  # F-R5-4：撤单桶取 min(内部, 通道撤单上限)
            max_per_second=max(
                1, min(self._rate_config.max_per_second, int(round(self._limits.cancel_per_sec)))
            ),
            max_per_day=self._rate_config.max_per_day,  # 无通道/监管撤单日上限证据，沿用内部
        )
        cap = self._adapter.capability
        if cap.autonomous:  # F-I6：半自动通道无查询能力，跳过远程恢复
            require_capability(cap, need=frozenset({"query_trades", "query_orders"}))
        self._ledger.attach_store(self._store)  # F-I10：接线（否则分录不落库）
        setter = getattr(
            self._store, "set_meta", None
        )  # reader 基准：快照 cash = initial − Σ（F-A1）
        if setter is not None:
            setter("initial_cash", repr(self._ledger.initial_cash))
        persisted = self._store.entries()
        if persisted and not self._ledger.entries():  # 崩溃恢复：重建运行账本（F-I10）
            self._ledger = Ledger.resume(persisted, initial_cash=self._ledger.initial_cash)
        day = local_day(
            self._clock(), tz=(self._calendar.tz if self._calendar else "Asia/Shanghai")
        )
        for rec in self._store.load_orders():  # F-R5-2：先装载本地订单，远程回报方可回放
            self._orders.setdefault(rec.client_order_id, rec)
        if cap.autonomous:  # 恢复序（SSE）：先成交报告 → 再订单状态；失败 fail-closed
            try:
                self._run_query(lambda: self._adapter.query_trades(day=day), replay="trades")
                self._run_query(lambda: self._adapter.query_orders(day=day), replay="orders")
            except ChannelUnavailable:
                self._set_recovery("failed")
                raise
        try:
            self.reconcile(ts=self._clock())  # F-I15：不留死赋值
        except ChannelUnavailable:  # Q6：positions 失败 → 降级可用
            self._set_recovery("degraded_positions")
        else:
            self._set_recovery("complete")

    def shutdown(self) -> None:
        try:
            self._adapter.disconnect()
        finally:
            self._store.close()

    # ---------- 生成 ----------

    def submit(
        self,
        intent: OrderIntent,
        request: OrderRequest,
        ctx: GuardContext,
        *,
        account_id: str,
        strategy_id: str,
        ts: float,
    ) -> SubmitResult:
        self._validate_args(intent, request, ctx, account_id, strategy_id)

        if self._adapter.state is ChannelState.HALTED:  # ①
            return SubmitResult(
                False,
                request.client_order_id,
                OrderState.REJECTED,
                reasons=("channel_halted",),
            )
        if self._calendar is not None:  # ②
            phase = session_phase(ts, calendar=self._calendar)
            if not can_submit(phase, order_type=request.order_type):
                return SubmitResult(
                    False,
                    request.client_order_id,
                    OrderState.REJECTED,
                    reasons=("session_closed",),
                )

        if self._adapter.capability.autonomous:  # ③ F-I6
            need = {"client_order_id", "cancel", "query_orders"}
        else:  # 半自动：无撤单/查询能力，订单清单 + 人工确认
            need = {"client_order_id"}
        require_capability(self._adapter.capability, need=frozenset(need))
        if request.side in ("SELL_SHORT", "BUY_TO_COVER"):
            raise CapabilityError("cash account cannot short (D15)")
        allowed, reason = check_rate(
            self._submit_ledger, ts, self._submit_config or self._rate_config
        )
        if not allowed:
            return SubmitResult(
                False, request.client_order_id, OrderState.REJECTED, reasons=(f"rate_{reason}",)
            )

        decision = self._gate.pre_trade_check(  # ④
            intent, ctx, account_id=account_id, strategy_id=strategy_id, ts=ts
        )
        if not decision.allowed:
            return SubmitResult(
                False,
                request.client_order_id,
                OrderState.REJECTED,
                decision=decision,
                reasons=decision.reasons,
            )

        coid = request.client_order_id or make_client_order_id(  # ⑤
            strategy_id=strategy_id,
            account_id=account_id,
            asset=request.asset,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            signal_ts=request.signal_ts,
        )
        request = replace(request, client_order_id=coid)
        if request.side == "BUY":  # ⑥
            base_price = request.price if request.price is not None else ctx.price
            self._ledger.reserve(
                ref=coid,
                amount=base_price * request.quantity * (1.0 + self._cost_buffer),
                ts=ts,
            )

        # ⑦ P-054 D9/D18：预算在 pre_trade_check 之后、adapter 之前（本地拒绝不耗槽）
        budget = self._reserve_flow(ts, cancel=False)
        if not budget.allowed:
            self._ledger.release(ref=coid, ts=ts)
            self._audit(
                EventType.AUDIT_ORDER,
                coid,
                "rate_denied",
                reason=budget.reason,
                retry_after_ms=budget.retry_after_ms,
                ts=ts,
            )
            return SubmitResult(
                False, coid, OrderState.REJECTED, reasons=(f"rate_{budget.reason}",)
            )

        rec = from_request(request, ts=ts)
        try:  # ⑧
            ack = self._adapter.submit(request)
        except ChannelRejected as exc:
            # D9「发送即计」：请求已送达柜台，拒单不退还预算槽位
            self._ledger.release(ref=coid, ts=ts)
            self._gate.on_order_result(rejected=True, ts=ts)
            rejected = transition(rec, state=OrderState.REJECTED, ts=ts, reject_code=exc.code)
            self._orders[coid] = rejected
            self._store.upsert_order_with_events(
                rejected, [order_event(rejected, OutboxEventType.ORDER_REJECTED, ts=ts)]
            )
            self._audit(
                EventType.AUDIT_ORDER,
                coid,
                "rejected",
                code=exc.code,
                reason=exc.reason,
                ts=ts,
            )
            return SubmitResult(False, coid, OrderState.REJECTED, reasons=(exc.code,))
        except ChannelUnavailable as exc:  # F-I7：请求级未受理不计拒单
            self._release_flow(ts, cancel=False)
            self._ledger.release(ref=coid, ts=ts)
            self._audit(EventType.AUDIT_ORDER, coid, "unavailable", reason=str(exc), ts=ts)
            return SubmitResult(
                False,
                coid,
                OrderState.PENDING_NEW,
                reasons=("channel_unavailable",),
            )

        self._submit_ledger = record(self._submit_ledger, ts, False)
        rec = transition(
            rec, state=ack.state, ts=ts, broker_order_id=ack.broker_order_id
        )  # ⑧（F-I5：同态回填 broker id）
        self._gate.on_order_result(rejected=False, ts=ts)  # F-I9：成功 ack 重置拒单计数
        self._orders[coid] = rec
        self._store.upsert_order_with_events(
            rec, [order_event(rec, OutboxEventType.ORDER_ACCEPTED, version=1, ts=ts)]
        )
        self._audit(EventType.AUDIT_ORDER, coid, "accepted", state=rec.state.value, ts=ts)
        return SubmitResult(True, coid, rec.state, decision=decision)

    # ---------- 回报 ----------

    def poll(self, *, ts: float | None = None) -> list[LedgerEntry]:
        """回报驱动：drain → 入账（FILL）或状态推进（REPORT）；返回本轮新增分录（D-5/F-I14）。"""
        now = self._clock() if ts is None else ts
        applied: list[LedgerEntry] = []
        for report in self._adapter.drain_reports():
            if isinstance(report, FillReport):
                mark = len(self._ledger.entries())
                if self._apply_fill(report):
                    self._audit(
                        EventType.AUDIT_FILL,
                        report.client_order_id,
                        "fill",
                        fill_key=report.fill_key,
                        ts=report.ts,
                    )
                    applied.extend(self._ledger.entries()[mark:])
                continue
            self._apply_order_report(report, ts=now)
        return applied

    def _apply_order_report(
        self, report: OrderReport, *, ts: float, from_query: bool = False
    ) -> None:
        rec = self._orders.get(report.client_order_id)
        if rec is None:
            return
        if (
            rec.state is OrderState.UNKNOWN and not from_query
        ):  # F-I16：drain 帧不迁出 UNKNOWN（I9）
            self._audit(
                EventType.AUDIT_ORDER,
                report.client_order_id,
                "ignored_transition",
                from_state=rec.state.value,
                to_state=report.state.value,
                ts=ts,
            )
            return
        try:
            updated = transition(
                rec,
                state=report.state,
                ts=report.ts,
                filled_quantity=report.filled_quantity,
                avg_price=report.avg_price,
                reject_code=report.code,
                reject_reason=report.reason,
                broker_order_id=report.broker_order_id or None,
            )
        except OrderTransitionError:
            self._audit(
                EventType.AUDIT_ORDER,
                report.client_order_id,
                "ignored_transition",
                from_state=rec.state.value,
                to_state=report.state.value,
                ts=ts,
            )
            return
        if updated is rec:  # O-I2：同态不写库、不发事件
            return
        self._orders[report.client_order_id] = updated
        if updated.state is OrderState.CANCELED:
            event_type = OutboxEventType.ORDER_CANCELED
        elif updated.state is OrderState.REJECTED:
            event_type = OutboxEventType.ORDER_REJECTED
        else:
            event_type = OutboxEventType.ORDER_STATUS
        self._store.upsert_order_with_events(updated, [order_event(updated, event_type, ts=ts)])
        self._audit(
            EventType.AUDIT_ORDER,
            report.client_order_id,
            "transition",
            state=updated.state.value,
            ts=ts,
        )
        if updated.state is OrderState.REJECTED:
            self._gate.on_order_result(rejected=True, ts=ts)
            self._ledger.release(ref=report.client_order_id, ts=ts)
        else:
            self._gate.on_order_result(rejected=False, ts=ts)  # F-I9：非拒单迁移重置计数
            if updated.state is OrderState.CANCELED:
                self._ledger.release(ref=report.client_order_id, ts=ts)

    def _apply_fill(self, report: FillReport) -> bool:
        """fill 只发 ``fill.applied``（F-I3①）；事件与两分录同事务（I3/I17）。"""
        fill = FillRecord(**asdict(report))
        entry_ids = [f"fill:{fill.fill_key}"]
        if fill.fee:
            entry_ids.append(f"fee:{fill.fill_key}")
        event = fill_event(fill, ts=report.ts, entry_ids=entry_ids)
        return self._ledger.apply_fill(fill, ts=report.ts, outbox_events=[event])

    def _run_query(self, fn, *, replay: str) -> None:
        """启动恢复：查询走 scheduler（D8）；回放 fill 带事件（O-I3）。"""
        if self._scheduler is not None:
            result = self._scheduler.run(fn)
        else:
            self._throttle_query(self._clock())
            result = fn()
        if replay == "trades":
            for report in result:
                self._apply_fill(report)
        else:
            for order_report in result:
                self._apply_order_report(order_report, ts=self._clock(), from_query=True)

    def _throttle_query(self, ts: float) -> None:
        """查询桶独立限流：先 check 后 record（F-I8；daily_orders = 当日查询数）。"""
        cfg = self._query_config or self._rate_config
        allowed, reason = check_rate(self._query_ledger, ts, cfg)
        if not allowed:
            raise ChannelUnavailable(f"query rate limited: {reason}")
        self._query_ledger = record(self._query_ledger, ts, is_cancel=False)

    def ingest_fills(self, reports: Iterable[FillReport]) -> list[LedgerEntry]:
        """Terminal/人工回填入口（F-I12）：import_fills 产出经此入账并审计（E2E ③）。"""
        applied: list[LedgerEntry] = []
        for report in reports:
            mark = len(self._ledger.entries())
            if self._apply_fill(report):
                self._audit(
                    EventType.AUDIT_FILL,
                    report.client_order_id,
                    "fill",
                    fill_key=report.fill_key,
                    ts=report.ts,
                )
                applied.extend(self._ledger.entries()[mark:])
        return applied

    # ---------- 撤单 ----------

    def cancel_ex(self, client_order_id: str, *, ts: float) -> CancelResult:
        """显式撤单（D11/G15）：not_found/terminal → 限流 → FTD → order-flow → adapter。"""
        rec = self._orders.get(client_order_id)
        if rec is None:
            return CancelResult(False, "not_found")
        if rec.is_terminal:
            return CancelResult(False, "terminal")
        allowed, reason = check_rate(
            self._cancel_ledger, ts, self._cancel_config or self._rate_config
        )
        if not allowed:
            return self._cancel_rejected(rec, ts, f"rate_{reason}")
        if self._ftd is not None:
            ftd = self._ftd.try_reserve(ts, cancel=True)
            if not ftd.allowed:
                return self._cancel_rejected(rec, ts, "rate_ftd", ftd.retry_after_ms)
        if self._order_flow is not None:
            flow = self._order_flow.try_reserve(ts, kind="cancel")
            if not flow.allowed:
                if self._ftd is not None:
                    self._ftd.release(cancel=True)
                return self._cancel_rejected(rec, ts, "rate_order_flow", flow.retry_after_ms)
        try:
            self._adapter.cancel(client_order_id)
        except ChannelRejected as exc:
            self._release_flow(ts, cancel=True)
            return self._cancel_rejected(rec, ts, "rejected", code=exc.code)
        except ChannelUnavailable:
            self._release_flow(ts, cancel=True)
            return self._cancel_rejected(rec, ts, "unsupported")
        self._cancel_ledger = record(self._cancel_ledger, ts, True)
        updated = transition(rec, state=OrderState.PENDING_CANCEL, ts=ts)
        self._orders[client_order_id] = updated
        self._store.upsert_order_with_events(
            updated, [order_event(updated, OutboxEventType.ORDER_STATUS, ts=ts)]
        )
        self._audit(EventType.AUDIT_CANCEL, client_order_id, "requested", ts=ts)
        return CancelResult(True)

    def _cancel_rejected(
        self, rec: OrderRecord, ts: float, reason: str, retry_after_ms: int = 0, **fields
    ) -> CancelResult:
        """撤单拒绝：显式事件 + AUDIT_CANCEL（I9）；版本 +1 保证 event_id 唯一（I5）。"""
        bumped = replace(rec, event_version=rec.event_version + 1, updated_ts=ts)
        self._orders[rec.client_order_id] = bumped
        event = order_event(
            bumped,
            OutboxEventType.ORDER_CANCEL_REJECTED,
            ts=ts,
            reason=reason,
        )
        self._store.upsert_order_with_events(bumped, [event])
        self._audit(
            EventType.AUDIT_CANCEL,
            rec.client_order_id,
            "rejected",
            reason=reason,
            retry_after_ms=retry_after_ms,
            **fields,
        )
        return CancelResult(False, reason, retry_after_ms)

    def cancel(self, client_order_id: str, *, ts: float) -> bool:
        return self.cancel_ex(client_order_id, ts=ts).accepted

    def cancel_all(self, *, ts: float) -> int:
        bridge = getattr(self._adapter, "bridge", None)
        if bridge is not None:
            return self._gate.cancel_all(bridge, ts=ts)
        return self.cancel_all_ex(ts=ts).submitted

    def cancel_all_ex(self, *, ts: float) -> CancelAllReport:
        open_ids = [coid for coid, rec in self._orders.items() if not rec.is_terminal]
        submitted = 0
        deferred: list[str] = []
        rejected: list[tuple[str, str]] = []
        for coid in open_ids:
            result = self.cancel_ex(coid, ts=ts)
            if result.accepted:
                submitted += 1
            elif result.reason in ("rate_ftd", "rate_order_flow"):
                deferred.append(coid)
            else:
                rejected.append((coid, result.reason))
        return CancelAllReport(
            requested=len(open_ids),
            submitted=submitted,
            deferred=tuple(deferred),
            rejected=tuple(rejected),
        )

    # ---------- 对账与人工确认 ----------

    def reconcile(self, *, ts: float, nav: float = 0.0) -> ReconcileReport:
        if not self._adapter.capability.autonomous:  # F-I6：半自动通道人工对账不入网关
            self._audit(EventType.AUDIT_RECONCILE, "-", "manual_channel", ts=ts)
            return ReconcileReport(ts, (), BreakLevel.OK, 0)
        snapshot = self._ledger.snapshot()
        local = {p.asset: p.quantity for p in snapshot.positions}
        if self._scheduler is not None:  # Q7：巡检与启动恢复共用同一调度器（D8）
            remote = {
                r.asset: r.quantity
                for r in self._scheduler.run(lambda: self._adapter.query_positions())
            }
        else:
            self._throttle_query(ts)  # F-I8/F-I14：query_positions 受查询桶
            remote = {r.asset: r.quantity for r in self._adapter.query_positions()}
        explained: frozenset[str] = frozenset()  # F-I13：精确归因交给 attribute_break
        report = reconcile_positions(
            local, remote, config=self._reconcile_config, nav=nav, explained=explained
        )
        report = replace(
            report,
            breaks=tuple(attribute_break(b, actions=self._actions) for b in report.breaks),
        )
        self._audit(
            EventType.AUDIT_RECONCILE,
            "-",
            report.level.value,
            checked=report.checked,
            ts=ts,
        )
        if report.level.value == "unresolved":
            self._adapter.state = ChannelState.HALTED
        return report

    def pending_unconfirmed(self) -> list[OrderRecord]:
        return [
            r
            for r in self._orders.values()
            if r.state in (OrderState.PENDING_NEW, OrderState.UNKNOWN)
            and self._clock() - r.created_ts > self._grace_seconds
        ]

    def confirm(self, client_order_id: str, *, state: OrderState, ts: float) -> OrderRecord:
        rec = self._orders[client_order_id]
        updated = transition(rec, state=state, ts=ts)
        self._orders[client_order_id] = updated
        self._store.upsert_order_with_events(
            updated, [order_event(updated, OutboxEventType.ORDER_STATUS, ts=ts)]
        )
        self._audit(
            EventType.AUDIT_ORDER, client_order_id, "confirmed", state=updated.state.value, ts=ts
        )
        return updated

    # ---------- 内部 ----------

    def _reserve_flow(self, ts: float, *, cancel: bool):
        """FTD → order-flow 顺序 reserve（D9）；本地失败由调用方退还。"""
        decision = None
        if self._ftd is not None:
            decision = self._ftd.try_reserve(ts, cancel=cancel)
            if not decision.allowed:
                return decision
        if self._order_flow is not None:
            flow = self._order_flow.try_reserve(ts, kind="cancel" if cancel else "submit")
            if not flow.allowed:
                if self._ftd is not None:
                    self._ftd.release(cancel=cancel)
                return flow
        from live.flow_control import Decision

        return decision or Decision(True)

    def _release_flow(self, ts: float, *, cancel: bool) -> None:
        if self._ftd is not None:
            self._ftd.release(cancel=cancel)
        if self._order_flow is not None:
            self._order_flow.release(kind="cancel" if cancel else "submit")

    def _set_recovery(self, state: str) -> None:
        self._recovery_state = state
        setter = getattr(self._store, "set_meta", None)
        if setter is not None:
            setter("recovery_state", state)
            setter("recovery_ts", str(self._clock()))

    def _audit(self, event_type: str, ref: str, action: str, **fields) -> None:
        payload = build_audit_payload(
            operator=self._operator,
            time_source="local",
            client_order_id=ref,
            action=action,
            **fields,  # source 只写 entry 级（F-I17）
        )
        self._event_log.append(event_type, payload, source=_SOURCE)

    def _validate_args(self, intent, request, ctx, account_id, strategy_id) -> None:
        """request ↔ intent ↔ kwargs 一致性（F-D2：fail-closed，adapter 零调用）。"""
        problems = []
        if request.asset != intent.asset:
            problems.append("asset")
        if str(request.asset_type) != str(intent.asset_type):
            problems.append("asset_type")
        if request.side != intent.action:
            problems.append("side")
        if abs(request.quantity - intent.abs_trade_quantity) > 1e-9:
            problems.append("quantity")
        if request.account_id != account_id:
            problems.append("account_id")
        if request.strategy_id != strategy_id:
            problems.append("strategy_id")
        if request.order_type == "limit" and request.price is None:
            problems.append("price")
        if problems:
            raise ValueError("inconsistent order args: " + ", ".join(problems))
