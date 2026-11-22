from __future__ import annotations

from typing import Protocol

from live.channel import (
    ChannelAdapter,
    ChannelCapability,
    ChannelRejected,
    ChannelState,
    ChannelUnavailable,
    FillReport,
    OrderReport,
    PositionReport,
    SubmitAck,
)
from live.orders import OrderRequest, OrderState

# 迅投/CTP 48-55 → FIX 9 值（RESEARCH §3.2 官方字典；Step 6 F-I7 复核）：
# 51 已报待撤 / 52 部成待撤（复合态：撤单进行中且有部分成交 → PENDING_CANCEL，
# filled_quantity 由回报承载）/ 53 部撤 / 54 已撤 / 55 部成。
_CTP_STATUS = {
    "48": OrderState.PENDING_NEW,
    "49": OrderState.PENDING_NEW,
    "50": OrderState.NEW,
    "51": OrderState.PENDING_CANCEL,
    "52": OrderState.PENDING_CANCEL,
    "53": OrderState.CANCELED,
    "54": OrderState.CANCELED,
    "55": OrderState.PARTIALLY_FILLED,
}


class CtpTransport(Protocol):
    def send_order(self, request: OrderRequest) -> dict: ...
    def cancel_order(self, client_order_id: str) -> dict: ...
    def req_qry_orders(self, day: str) -> list[dict]: ...
    def req_qry_trades(self, day: str) -> list[dict]: ...
    def req_qry_positions(self) -> list[dict]: ...
    def subscribe(self) -> None: ...


class CtpChannelAdapter(ChannelAdapter):
    def __init__(self, transport: CtpTransport | None = None) -> None:
        self._transport = transport
        self.state = ChannelState.DISCONNECTED
        self.capability = ChannelCapability(
            channel_id="ctp",
            venue="ctp",
            account_level="cash",
            products=("future", "option"),
            supports_client_order_id=True,  # F-R5-1：coid ↔ OrderRef 映射（原 False 与网关能力门互斥）
            supports_cancel=True,
            supports_query_orders=True,
            supports_query_trades=True,
            supports_query_positions=True,
            autonomous=True,
            report_registered=True,
            max_submit_per_sec=10.0,  # 受 FTD 6/s 共享约束（P-054 D9）
            max_submit_per_day=20000,
            max_cancel_per_sec=10.0,  # 受 FTD 6/s 共享约束（P-054 D9）
            max_query_per_sec=1.0,  # 查询 1 笔/秒
        )
        self._refs: dict[str, tuple[str, str, str]] = {}

    def _require(self) -> CtpTransport:
        if self._transport is None:
            raise ChannelUnavailable("ctp transport not injected")
        return self._transport

    def connect(self) -> None:
        self._require().subscribe()
        self.state = ChannelState.CONNECTED

    def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED

    def submit(self, request: OrderRequest) -> SubmitAck:
        reply = self._require().send_order(request)
        code = str(reply.get("error_id", "0"))
        if code in ("-2", "-3"):
            # -2/-3 = 请求级流控（未送达柜台，RESEARCH §3.2）→ 可重试，不计柜台拒单（F-I7）
            raise ChannelUnavailable(f"ctp flow control {code}: {reply.get('error_msg', '')}")
        if code not in ("0", ""):  # 非 0 一律柜台拒单（F-I7：原只拦 -2/-3）
            raise ChannelRejected(code, str(reply.get("error_msg", "")))
        ref = str(reply["order_ref"])
        self._refs[request.client_order_id] = (  # F-R5-5：coid ↔ (FrontID, SessionID, OrderRef)
            str(reply.get("front_id", "")),
            str(reply.get("session_id", "")),
            ref,
        )
        return SubmitAck(request.client_order_id, ref, OrderState.PENDING_NEW, 0.0)

    def cancel(self, client_order_id: str) -> None:
        reply = self._require().cancel_order(client_order_id)
        code = str(reply.get("error_id", "0"))
        if code in ("-2", "-3"):
            raise ChannelUnavailable(f"ctp flow control {code}: {reply.get('error_msg', '')}")
        if code not in ("0", ""):
            raise ChannelRejected(code, str(reply.get("error_msg", "")))

    def query_orders(self, *, day: str) -> list[OrderReport]:
        by_ref = {ref: coid for coid, (_f, _s, ref) in self._refs.items()}  # F-R5-5 反查
        return [
            OrderReport(
                client_order_id=by_ref.get(str(row["order_ref"]), str(row["client_order_id"])),
                broker_order_id=str(row["order_ref"]),
                state=_CTP_STATUS.get(str(row["order_status"]), OrderState.UNKNOWN),
                filled_quantity=float(row.get("volume_traded", 0.0)),
                avg_price=float(row.get("price_traded", 0.0)),
                ts=float(row["ts"]),
                code=str(row.get("status_msg", "")),
                reason="",
            )
            for row in self._require().req_qry_orders(day)
        ]

    def query_trades(self, *, day: str) -> list[FillReport]:
        return [FillReport(**row) for row in self._require().req_qry_trades(day)]

    def query_positions(self) -> list[PositionReport]:
        return [
            PositionReport(asset=row["instrument_id"], quantity=float(row["volume"]))
            for row in self._require().req_qry_positions()
        ]
