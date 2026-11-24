"""P-061 全周期追溯采集器（DESIGN §5 / §7 / §8）。

设计要点（DD1-DD12）：

- **业务主键**：``trace_id = "{YYYY-MM-DD}|{stock}"``；
  ``order_ref = "{trace_id}|{side}|{order_seq:05d}"``（全运行递增，确定性）；
  ``fill_ref = "{order_ref}|{fill_seq}"``。
- **以 fill 为事实源**（DD2）：``trace_order`` 的 ``status/filled_qty/execute_*``
  一律由成交关联派生；引擎字段仅作过程记录。
- **默认零 I/O**（I1）：``TraceConfig.out_dir is None`` → ``enabled=False``，
  所有 hook 首行返回、``finalize`` 返回空列表。
- **纯内存追加**（I5）：仅末日末行允许覆写（``overwrite_last_day``）。
- **失败不阻断回测**（DD12）：``finalize`` 的 ``OSError`` 向外抛，由引擎捕获。

依赖边界（G11）：只 import stdlib + pandas + ``core.change_report``（同层、无引擎依赖）。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core.change_report import RESIDUAL_TOL

logger = logging.getLogger(__name__)

TRACE_SCHEMA_VERSION = "1.0"

TRACE_DAY_COLUMNS = (
    "date",
    "stock",
    "trace_id",
    "signal",
    "target_weight",
    "target_qty",
    "current_qty",
    "is_exit",
    "tradable",
    "buyable",
    "sellable",
    "position_qty",
    "position_value",
    "close_reason",
    "nav",
)
TRACE_ORDER_COLUMNS = (
    "order_ref",
    "trace_id",
    "date",
    "stock",
    "side",
    "qty",
    "filled_qty",
    "status",
    "reject_reason",
    "retry_count",
    "create_date",
    "execute_date",
    "execute_price",
    "fallback_stock",
)
TRACE_FILL_COLUMNS = (
    "fill_ref",
    "order_ref",
    "replaces_order_ref",
    "date",
    "stock",
    "side",
    "qty",
    "price",
    "amount",
    "cost",
    "net_amount",
    "multiplier",
)
TRACE_FILES = ("trace_day.csv", "trace_order.csv", "trace_fill.csv", "alignment.json")

REJECT_REASONS = frozenset(
    {
        "limit_up",
        "limit_down",
        "suspended",
        "st_blocked",
        "invalid_price",
        "cash_short",
        "no_position",
        "expired",
        "unknown",
    }
)
CLOSE_REASONS = frozenset({"rebalance", "final_liquidation", "delisted", "unknown"})
ORDER_STATUSES = frozenset(
    {
        "created",
        "retry",
        "filled",
        "executed_by_fallback",
        "cancelled",
        "expired",
        "dropped",
    }
)
SIDES = ("BUY", "SELL", "SELL_SHORT", "BUY_TO_COVER")
_LONG_SIDES = frozenset({"BUY", "BUY_TO_COVER"})


def _date_key(date: Any) -> str:
    return str(pd.Timestamp(date).strftime("%Y-%m-%d"))


def _side_name(order: Any) -> str:
    return str(getattr(getattr(order, "side", None), "name", ""))


def _order_status_name(order: Any) -> str:
    return str(getattr(getattr(order, "status", None), "name", ""))


@dataclass(frozen=True)
class TraceConfig:
    """采集配置；``out_dir=None`` → 采集器整体禁用（零 I/O）。"""

    out_dir: Path | None
    full: bool = False


def classify_reject(
    *,
    side: str,
    buyable: bool,
    sellable: bool,
    suspended: bool,
    is_st: bool,
    exclude_st: bool,
    has_price: bool,
    cash_short: bool,
    has_position: bool,
) -> str:
    """纯函数：把引擎判定布尔映射到 ``REJECT_REASONS`` 闭集（DD6）。

    两条执行路径（队列 / 次日）传同一组入参，避免词表漂移。
    """
    name = str(side)
    if name == "BUY_TO_COVER" and not has_position:
        return "no_position"
    if name in _LONG_SIDES:
        if not buyable:
            if suspended:
                return "suspended"
            if is_st and exclude_st:
                return "st_blocked"
            return "limit_up"
        if not has_price:
            return "invalid_price"
        if cash_short:
            return "cash_short"
        return "unknown"
    if not sellable:
        if suspended:
            return "suspended"
        return "limit_down"
    if not has_position:
        return "no_position"
    if not has_price:
        return "invalid_price"
    return "unknown"


class TraceCollector:
    """无状态引擎之上的内存采集器；所有方法在禁用时立即返回。"""

    def __init__(self, config: TraceConfig) -> None:
        self.config = config
        self.out_dir: Path | None = Path(config.out_dir) if config.out_dir is not None else None
        self.enabled = self.out_dir is not None

        self.trigger_events: list[dict[str, Any]] = []
        self._day_rows: dict[tuple[str, str], dict[str, Any]] = {}
        self._order_rows: dict[int, dict[str, Any]] = {}
        self._order_objects: dict[int, Any] = {}
        self._rows_by_ref: dict[str, dict[str, Any]] = {}
        self._fill_rows: list[dict[str, Any]] = []
        self._active_prev: set[int] = set()
        self._order_seq = 0
        self._fill_seq = 0
        self._unknown_reasons: Counter[str] = Counter()
        self._last_nav = 0.0
        self._last_cash = 0.0
        self._last_positions: dict[str, tuple[int, float]] = {}

    # ------------------------------------------------------------------
    # 日粒度
    # ------------------------------------------------------------------
    def on_trigger(self, date: Any, trigger: Any, triggered: bool) -> None:
        """S1：每日记录触发判定（非触发日也记录，F-14）。"""
        if not self.enabled:
            return
        self.trigger_events.append(
            {
                "date": _date_key(date),
                "trigger": type(trigger).__name__,
                "triggered": bool(triggered),
            }
        )

    def on_targets(self, date: Any, rows: Sequence[Mapping[str, Any]]) -> None:
        """S2：记录目标持仓行；``full=False`` 丢弃非目标行（T-A10）。"""
        if not self.enabled:
            return
        date_key = _date_key(date)
        for item in rows:
            stock = str(item.get("stock", ""))
            if not stock:
                continue
            target_qty = item.get("target_qty")
            is_exit = bool(item.get("is_exit", False))
            if not self.config.full and not is_exit and int(target_qty or 0) == 0:
                continue
            row = self._ensure_row(date_key, stock)
            for key in (
                "signal",
                "target_weight",
                "target_qty",
                "current_qty",
                "tradable",
                "buyable",
                "sellable",
            ):
                if key in item:
                    row[key] = item[key]
            row["is_exit"] = is_exit

    # ------------------------------------------------------------------
    # 订单
    # ------------------------------------------------------------------
    def on_order_created(self, order: Any) -> str:
        """S3：登记订单并分配确定性 ``order_seq``（不修改 order 对象）。"""
        if not self.enabled:
            return ""
        key = id(order)
        existing = self._order_rows.get(key)
        if existing is not None:
            return str(existing["order_ref"])
        self._order_seq += 1
        date_key = _date_key(order.create_date)
        stock = str(order.stock)
        side = _side_name(order)
        trace_id = f"{date_key}|{stock}"
        order_ref = f"{trace_id}|{side}|{self._order_seq:05d}"
        row: dict[str, Any] = {
            "order_ref": order_ref,
            "trace_id": trace_id,
            "date": date_key,
            "stock": stock,
            "side": side,
            "qty": int(order.quantity),
            "filled_qty": 0,
            "status": "created",
            "reject_reason": "",
            "retry_count": 0,
            "create_date": date_key,
            "execute_date": "",
            "execute_price": "",
            "fallback_stock": "",
        }
        self._order_rows[key] = row
        self._order_objects[key] = order
        self._rows_by_ref[order_ref] = row
        self._ensure_row(date_key, stock)
        return order_ref

    def order_ref(self, order: Any) -> str:
        """返回已登记订单的 ``order_ref``（未登记返回空串）。"""
        row = self._order_rows.get(id(order))
        return str(row["order_ref"]) if row is not None else ""

    def on_order_rejected(self, order: Any, reason: str) -> None:
        """S4：拒单原因（闭集外 → ``unknown``）+ collector 自计数（F-20）。"""
        if not self.enabled:
            return
        row = self._row_for(order)
        text = str(reason)
        if text not in REJECT_REASONS:
            self._unknown_reasons[text] += 1
            text = "unknown"
        row["reject_reason"] = text
        row["retry_count"] = int(row["retry_count"]) + 1
        if row["status"] not in ("filled", "executed_by_fallback"):
            row["status"] = "retry"

    def on_fill(
        self,
        trade: Any,
        order: Any | None,
        *,
        direct: bool = False,
        replaces_order_ref: str | None = None,
    ) -> None:
        """S5：成交（事实源）；``direct=True`` → ``order_ref="direct"``（DD9）。"""
        if not self.enabled:
            return
        self._fill_seq += 1
        date_key = _date_key(trade.date)
        stock = str(trade.stock)
        if order is None:
            ref = "direct"
        else:
            ref = self.order_ref(order) or self.on_order_created(order)
        side = _side_name(trade)
        row: dict[str, Any] = {
            "fill_ref": f"{ref}|{self._fill_seq}",
            "order_ref": ref,
            "replaces_order_ref": str(replaces_order_ref or ""),
            "date": date_key,
            "stock": stock,
            "side": side,
            "qty": int(trade.quantity),
            "price": float(trade.price),
            "amount": float(trade.amount),
            "cost": float(trade.cost),
            "net_amount": float(trade.net_amount),
            "multiplier": float(getattr(trade, "multiplier", 1.0)),
        }
        self._fill_rows.append(row)
        if order is not None:
            order_row = self._order_rows[id(order)]
            order_row["filled_qty"] = int(order_row["filled_qty"]) + int(trade.quantity)
            order_row["execute_date"] = date_key
            order_row["execute_price"] = float(trade.price)
            if order_row["status"] != "executed_by_fallback":
                order_row["status"] = "filled"
        if row["replaces_order_ref"]:
            original = self._rows_by_ref.get(row["replaces_order_ref"])
            if original is not None:
                original["status"] = "executed_by_fallback"
                original["fallback_stock"] = stock
                original["execute_date"] = date_key
                original["execute_price"] = float(trade.price)
        self._ensure_row(date_key, stock)

    def on_close(self, date: Any, stock: str, reason: str) -> None:
        """S6：平仓原因（闭集外 → ``unknown``）。"""
        if not self.enabled:
            return
        text = str(reason)
        if text not in CLOSE_REASONS:
            self._unknown_reasons[text] += 1
            text = "unknown"
        row = self._ensure_row(_date_key(date), str(stock))
        row["close_reason"] = text

    # ------------------------------------------------------------------
    # 日末 / 末日
    # ------------------------------------------------------------------
    def on_day_end(
        self,
        date: Any,
        active_orders: Sequence[Any],
        positions: Mapping[str, tuple[int, float]],
        cash: float,
        nav: float,
    ) -> None:
        """S7：日末快照 + 活跃订单集合差分（DD11）。"""
        if not self.enabled:
            return
        date_key = _date_key(date)
        self._last_nav = float(nav)
        self._last_cash = float(cash)
        self._last_positions = {
            str(stock): (int(qty), float(value)) for stock, (qty, value) in positions.items()
        }
        for stock in positions:
            self._ensure_row(date_key, str(stock))
        for (day, stock), row in self._day_rows.items():
            if day != date_key:
                continue
            qty, value = positions.get(stock, (0, 0.0))
            row["position_qty"] = int(qty)
            row["position_value"] = float(value)
            row["nav"] = float(nav)

        current_ids: set[int] = set()
        for order in active_orders:
            self.on_order_created(order)
            current_ids.add(id(order))
        # 消失订单终态解析：覆盖「当日创建当日取消/过期」与跨日消失两种情况
        for order_id in list(self._order_rows):
            if order_id in current_ids:
                continue
            row = self._order_rows[order_id]
            if row["status"] in ("filled", "executed_by_fallback", "cancelled", "expired"):
                continue
            row["status"] = self._terminal_status(self._order_objects.get(order_id))
        for order_id in self._active_prev & current_ids:
            active_row = self._order_rows.get(order_id)
            if active_row is not None and active_row["status"] not in (
                "filled",
                "executed_by_fallback",
            ):
                active_row["status"] = "retry"
        self._active_prev = current_ids

    def overwrite_last_day(
        self,
        date: Any,
        positions: Mapping[str, tuple[int, float]],
        cash: float,
        nav: float,
    ) -> None:
        """S8：末日强平后覆写当日行（DD10；不追加新行）。"""
        if not self.enabled:
            return
        date_key = _date_key(date)
        self._last_nav = float(nav)
        self._last_cash = float(cash)
        self._last_positions = {
            str(stock): (int(qty), float(value)) for stock, (qty, value) in positions.items()
        }
        for (day, stock), row in self._day_rows.items():
            if day != date_key:
                continue
            qty, value = positions.get(stock, (0, 0.0))
            row["position_qty"] = int(qty)
            row["position_value"] = float(value)
            row["nav"] = float(nav)

    # ------------------------------------------------------------------
    # 落盘
    # ------------------------------------------------------------------
    def finalize(
        self,
        trades_df: pd.DataFrame | None = None,
        remaining_orders: Sequence[Any] = (),
    ) -> list[Path]:
        """终扫 + 写 4 个产物（``OSError`` 上抛由引擎捕获，DD12）。"""
        if not self.enabled:
            return []
        assert self.out_dir is not None
        for order in remaining_orders:
            row = self._row_for(order)
            if row["status"] in ("filled", "executed_by_fallback"):
                continue
            row["status"] = self._terminal_status(order)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        day_rows = sorted(self._day_rows.values(), key=lambda row: (row["date"], row["stock"]))
        order_rows = sorted(
            self._order_rows.values(),
            key=lambda row: (row["create_date"], row["stock"], row["side"], row["order_ref"]),
        )
        fill_rows = sorted(
            self._fill_rows, key=lambda row: (row["date"], row["stock"], row["fill_ref"])
        )

        day_df = pd.DataFrame(day_rows, columns=list(TRACE_DAY_COLUMNS))
        order_df = pd.DataFrame(order_rows, columns=list(TRACE_ORDER_COLUMNS))
        fill_df = pd.DataFrame(fill_rows, columns=list(TRACE_FILL_COLUMNS))
        ordered_columns = {
            "trace_day.csv": list(TRACE_DAY_COLUMNS),
            "trace_order.csv": list(TRACE_ORDER_COLUMNS),
            "trace_fill.csv": list(TRACE_FILL_COLUMNS),
        }
        for name, frame in (
            ("trace_day.csv", day_df),
            ("trace_order.csv", order_df),
            ("trace_fill.csv", fill_df),
        ):
            frame.to_csv(
                self.out_dir / name,
                index=False,
                columns=ordered_columns[name],
                lineterminator="\n",
                encoding="utf-8",
                na_rep="",
            )

        alignment = self._build_alignment(fill_rows, trades_df)
        (self.out_dir / "alignment.json").write_text(
            json.dumps(alignment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return [self.out_dir / name for name in TRACE_FILES]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _ensure_row(self, date_key: str, stock: str) -> dict[str, Any]:
        key = (date_key, stock)
        row = self._day_rows.get(key)
        if row is None:
            row = {
                "date": date_key,
                "stock": stock,
                "trace_id": f"{date_key}|{stock}",
                "signal": None,
                "target_weight": None,
                "target_qty": None,
                "current_qty": None,
                "is_exit": None,
                "tradable": None,
                "buyable": None,
                "sellable": None,
                "position_qty": None,
                "position_value": None,
                "close_reason": "",
                "nav": None,
            }
            self._day_rows[key] = row
        return row

    def _row_for(self, order: Any) -> dict[str, Any]:
        self.on_order_created(order)
        return self._order_rows[id(order)]

    @staticmethod
    def _terminal_status(order: Any) -> str:
        status = _order_status_name(order) if order is not None else ""
        if status == "EXPIRED":
            return "expired"
        if status == "CANCELLED":
            return "cancelled"
        return "dropped"

    def _build_alignment(
        self, fill_rows: Sequence[Mapping[str, Any]], trades_df: pd.DataFrame | None
    ) -> dict[str, Any]:
        qty_by_side = {side: 0 for side in SIDES}
        signed: Counter[str] = Counter()
        amount_sum = 0.0
        cost_sum = 0.0
        for row in fill_rows:
            side = str(row.get("side", ""))
            qty = int(row.get("qty") or 0)
            if side in qty_by_side:
                qty_by_side[side] += qty
            signed[str(row.get("stock", ""))] += qty if side in _LONG_SIDES else -qty
            amount_sum += float(row.get("amount") or 0.0)
            cost_sum += float(row.get("cost") or 0.0)

        trades_amount_sum: float | None = None
        if trades_df is not None and not trades_df.empty and "amount" in trades_df.columns:
            trades_amount_sum = float(trades_df["amount"].sum())

        final_positions = {
            stock: qty for stock, (qty, _) in self._last_positions.items() if int(qty) != 0
        }
        stocks = set(signed) | set(final_positions)
        position_gap = max(
            (abs(signed[stock] - final_positions.get(stock, 0)) for stock in stocks),
            default=0.0,
        )
        residual_terms = [position_gap]
        if trades_amount_sum is not None:
            residual_terms.append(abs(amount_sum - trades_amount_sum))
        residual = max(residual_terms) if residual_terms else 0.0

        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "manifest": {"run_id": None, "input_fingerprint": None},
            "counts": {
                "orders": len(self._order_rows),
                "fills": len(fill_rows),
                "direct_fills": sum(1 for row in fill_rows if row.get("order_ref") == "direct"),
            },
            "reconcile": {
                "qty_by_side": qty_by_side,
                "amount_sum": amount_sum,
                "cost_sum": cost_sum,
                "trades_csv_amount_sum": (
                    trades_amount_sum if trades_amount_sum is not None else amount_sum
                ),
                "snapshots_final_nav": float(self._last_nav),
                "residual": float(residual),
                "tolerance": RESIDUAL_TOL,
            },
            "gates": {"golden": "not_run", "p059": "not_run"},
            "missing": [],
        }
