"""TradingGateway：submit 八步固定序 + 回报/对账编排（P-053 D10）。"""

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
        persisted = self._store.entries()
        if persisted and not self._ledger.entries():  # 崩溃恢复：重建运行账本（F-I10）
            self._ledger = Ledger.resume(persisted, initial_cash=self._ledger.initial_cash)
        day = local_day(
            self._clock(), tz=(self._calendar.tz if self._calendar else "Asia/Shanghai")
        )
        for rec in self._store.load_orders():  # F-R5-2：先装载本地订单，远程回报方可回放
            self._orders.setdefault(rec.client_order_id, rec)
        if cap.autonomous:  # 恢复序（SSE）：先成交报告 → 再订单状态
            self._throttle_query(self._clock())
            for report in self._adapter.query_trades(day=day):
                self._ledger.apply_fill(FillRecord(**asdict(report)))
            self._throttle_query(self._clock())
            for order_report in self._adapter.query_orders(day=day):
                self._apply_order_report(order_report, ts=self._clock(), from_query=True)
        self.reconcile(ts=self._clock())  # F-I15：不留死赋值

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
        rec = from_request(request, ts=ts)
        try:  # ⑦
            ack = self._adapter.submit(request)
        except ChannelRejected as exc:
            self._ledger.release(ref=coid, ts=ts)
            self._gate.on_order_result(rejected=True, ts=ts)
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
        self._store.upsert_order(rec)
        self._audit(EventType.AUDIT_ORDER, coid, "accepted", state=rec.state.value, ts=ts)
        self._store.append_outbox(
            event_id=uuid.uuid4().hex,
            event_type=EventType.AUDIT_ORDER,
            payload=coid,
            ts=ts,
        )
        return SubmitResult(True, coid, rec.state, decision=decision)

    # ---------- 回报 ----------

    def poll(self, *, ts: float | None = None) -> list[LedgerEntry]:
        """回报驱动：drain → 入账（FILL）或状态推进（REPORT）；返回本轮新增分录（D-5/F-I14）。"""
        now = self._clock() if ts is None else ts
        applied: list[LedgerEntry] = []
        for report in self._adapter.drain_reports():
            if isinstance(report, FillReport):
                mark = len(self._ledger.entries())
                if self._ledger.apply_fill(FillRecord(**asdict(report)), ts=report.ts):
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
        self._orders[report.client_order_id] = updated
        self._store.upsert_order(updated)
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
            if self._ledger.apply_fill(FillRecord(**asdict(report)), ts=report.ts):
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

    def cancel(self, client_order_id: str, *, ts: float) -> bool:
        rec = self._orders.get(client_order_id)
        if rec is None or rec.is_terminal:
            return False
        allowed, reason = check_rate(
            self._cancel_ledger, ts, self._cancel_config or self._rate_config
        )
        if not allowed:
            return False
        try:
            self._adapter.cancel(client_order_id)
        except ChannelRejected:
            return False
        except ChannelUnavailable:  # F-I7：流控未受理，不迁移状态
            return False
        self._cancel_ledger = record(self._cancel_ledger, ts, True)
        self._orders[client_order_id] = transition(rec, state=OrderState.PENDING_CANCEL, ts=ts)
        self._store.upsert_order(self._orders[client_order_id])
        self._audit(EventType.AUDIT_CANCEL, client_order_id, "requested", ts=ts)
        return True

    def cancel_all(self, *, ts: float) -> int:
        bridge = getattr(self._adapter, "bridge", None)
        if bridge is not None:
            return self._gate.cancel_all(bridge, ts=ts)
        count = 0
        for coid, rec in list(self._orders.items()):
            if not rec.is_terminal and self.cancel(coid, ts=ts):
                count += 1
        return count

    # ---------- 对账与人工确认 ----------

    def reconcile(self, *, ts: float, nav: float = 0.0) -> ReconcileReport:
        if not self._adapter.capability.autonomous:  # F-I6：半自动通道人工对账不入网关
            self._audit(EventType.AUDIT_RECONCILE, "-", "manual_channel", ts=ts)
            return ReconcileReport(ts, (), BreakLevel.OK, 0)
        self._throttle_query(ts)  # F-I8/F-I14：query_positions 受查询桶
        snapshot = self._ledger.snapshot()
        local = {p.asset: p.quantity for p in snapshot.positions}
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
        self._store.upsert_order(updated)
        self._audit(
            EventType.AUDIT_ORDER, client_order_id, "confirmed", state=updated.state.value, ts=ts
        )
        return updated

    # ---------- 内部 ----------

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
