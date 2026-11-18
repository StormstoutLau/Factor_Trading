"""P-059 逐日 trace 采集（DESIGN §5 / Step 5 T2）。

零生产改动：``setup()`` 之后以 proxy 包装引擎持有的 ``executor`` / ``tracker`` /
``optimizer``（DD4，``__getattr__`` 透传其余成员）。``enabled=False`` 时**不 attach**，
引擎保持原生组件（供 I3「零行为」断言）。

DD5 日分桶：以 ``tracker.update_market_values`` 为边界；末日 ``_force_liquidation``
会二次调用（DESIGN §5.2 已证实），故同一日桶**幂等合并**（后写覆盖、成交去重）。
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from core.execution import is_valid_price
from core.pending import OrderSide
from core.sizing import estimate_buy_cash


def _date_key(date: Any) -> str:
    return pd.Timestamp(date).strftime("%Y-%m-%d")


def _order_key(order: Any) -> tuple[str, str, str, int]:
    return (
        str(order.stock),
        str(order.side.name),
        _date_key(order.create_date),
        int(order.quantity),
    )


class TraceRecorder:
    """逐日桶 + 成交/订单状态事件采集器。"""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.buckets: dict[str, dict[str, Any]] = {}
        self.fills: list[dict[str, Any]] = []
        self.created: list[dict[str, Any]] = []
        self.state_events: list[dict[str, Any]] = []
        self._engine: Any = None
        self._pending_target: dict[str, float] = {}
        self._active_prev: set[tuple[str, str, str, int]] = set()
        self._registered: set[tuple[str, str, str, int]] = set()

    # ------------------------------------------------------------------
    # 引擎挂载
    # ------------------------------------------------------------------
    def attach(self, engine: Any) -> None:
        self._engine = engine
        if not self.enabled:
            return
        engine.executor = RecordingExecutor(engine.executor, self)
        engine.tracker = RecordingTracker(engine.tracker, self)
        if engine.optimizer is not None:
            engine.optimizer = RecordingOptimizer(engine.optimizer, self)

    # ------------------------------------------------------------------
    # 事件入口（proxy 调用）
    # ------------------------------------------------------------------
    def record_target(self, weights: dict[str, float]) -> None:
        if not self.enabled:
            return
        self._pending_target = {str(k): float(v) for k, v in weights.items() if float(v) > 0.0}

    def record_trade(self, trade: Any) -> None:
        if not self.enabled:
            return
        self.fills.append(
            {
                "date": _date_key(trade.date),
                "code": str(trade.stock),
                "side": str(trade.side.name),
                "quantity": int(trade.quantity),
                "price": float(trade.price),
                "amount": float(trade.amount),
                "cost": float(trade.cost),
            }
        )

    def close_bucket(self, date: Any) -> None:
        """``update_market_values`` 之后调用；同日重复调用幂等合并。"""
        if not self.enabled:
            return
        engine = self._engine
        key = _date_key(date)
        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = {
                "date": key,
                "target_weight": {},
                "buyable": [],
                "sellable": [],
                "orders": [],
                "filled": [],
                "rejected": [],
                "cash": 0.0,
                "nav": 0.0,
                "positions": {},
            }
            self.buckets[key] = bucket

        tracker = engine.tracker
        bucket["cash"] = float(tracker.get_cash())
        bucket["nav"] = float(tracker.get_total_value())
        bucket["positions"] = {
            str(stock): int(pos.quantity)
            for stock, pos in tracker.get_all_positions().items()
            if int(pos.quantity) > 0
        }
        bucket["filled"] = [
            {k: v for k, v in fill.items() if k != "date"}
            for fill in self.fills
            if fill["date"] == key
        ]

        universe = engine.universe
        if universe is not None:
            _, _, buyable, sellable = universe.get_layer_masks(pd.Timestamp(date))
            codes = [str(code) for code in engine.dm.stock_codes]
            bucket["buyable"] = [code for code in codes if bool(buyable.get(code, False))]
            bucket["sellable"] = [code for code in codes if bool(sellable.get(code, False))]

        active = self._active_orders()
        active_map = {_order_key(order): order for order in active}

        # 目标权重：优先 optimizer 记录（scores 模式），其次 weights 模式信号行
        if self._pending_target:
            bucket["target_weight"] = dict(self._pending_target)
            self._pending_target = {}
        elif getattr(engine, "_signal_mode", "scores") == "weights":
            created_today = [o for o in active if _date_key(o.create_date) == key]
            if created_today:
                row = engine._composite_signal.loc[pd.Timestamp(date)]
                bucket["target_weight"] = {
                    str(code): float(value) for code, value in row.items() if float(value) > 0.0
                }

        # 新建订单（create_date == 当日）→ 登记，初态 retry
        for order in active:
            order_key = _order_key(order)
            if _date_key(order.create_date) != key:
                continue
            bucket["orders"].append(self._order_dict(order))
            if order_key not in self._registered:
                self._registered.add(order_key)
                self.created.append(self._order_dict(order))

        # 上一桶活跃订单：成交 / 继续挂起（retry）/ 消失（dropped）
        fill_pool = [fill for fill in self.fills if fill["date"] == key]
        for order_key in sorted(self._active_prev):
            code, side, _, _ = order_key
            matched = next(
                (fill for fill in fill_pool if fill["code"] == code and fill["side"] == side),
                None,
            )
            if matched is not None:
                fill_pool.remove(matched)
                self._event(key, order_key, "filled")
                continue
            order = active_map.get(order_key)
            if order is not None:
                self._event(key, order_key, "retry")
                bucket["rejected"].append(
                    {
                        "code": code,
                        "side": side,
                        "quantity": order_key[3],
                        "reason": self._reject_reason(order, pd.Timestamp(date), dropped=False),
                    }
                )
            else:
                self._event(key, order_key, "dropped")
                bucket["rejected"].append(
                    {
                        "code": code,
                        "side": side,
                        "quantity": order_key[3],
                        "reason": self._reject_reason(order_key, pd.Timestamp(date), dropped=True),
                    }
                )

        self._active_prev = set(active_map)

    def finalize(self) -> None:
        """run() 结束后：仍活跃的订单标记为 dropped（末日后到期）。"""
        if not self.enabled:
            return
        for order_key in sorted(self._active_prev):
            self._event("<end>", order_key, "dropped")

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _event(self, date: str, order_key: tuple[str, str, str, int], state: str) -> None:
        """订单状态事件（键含 create_date/quantity：同一 (code, side) 可能有多张订单）。"""
        code, side, create_date, quantity = order_key
        self.state_events.append(
            {
                "date": date,
                "code": code,
                "side": side,
                "create_date": create_date,
                "quantity": quantity,
                "state": state,
            }
        )

    @staticmethod
    def _order_dict(order: Any) -> dict[str, Any]:
        return {
            "code": str(order.stock),
            "side": str(order.side.name),
            "quantity": int(order.quantity),
            "create_date": _date_key(order.create_date),
        }

    def _active_orders(self) -> list[Any]:
        engine = self._engine
        orders: list[Any] = []
        if engine.pending_queue is not None:
            orders.extend(engine.pending_queue.get_pending_orders())
        for item in getattr(engine, "_next_day_orders", None) or []:
            orders.append(item["order"] if isinstance(item, dict) else item)
        return orders

    def _reject_reason(self, order: Any, date: pd.Timestamp, *, dropped: bool) -> str:
        """拒单归因（闭集内取值；dropped 视为过期/取消）。"""
        if dropped:
            return "expired"
        engine = self._engine
        code = str(order.stock)
        side = str(order.side.name)
        universe = engine.universe
        _, _, buyable, sellable = universe.get_layer_masks(date)
        if side == OrderSide.BUY.name:
            if not bool(buyable.get(code, False)):
                suspend = getattr(engine.dm, "suspend", None)
                if suspend is not None and bool(suspend.loc[date].get(code, 0) == 1):
                    return "suspended"
                st_frame = getattr(engine.dm, "st", None)
                if (
                    st_frame is not None
                    and bool(st_frame.loc[date].get(code, 0) == 1)
                    and bool(engine.cfg.universe.exclude_st)
                ):
                    return "st_blocked"
                return "limit_up"
            open_price = self._open_price(date, code)
            if open_price is None or not is_valid_price(open_price):
                return "invalid_price"
            required = estimate_buy_cash(
                open_price * int(order.quantity),
                commission_rate=engine.cfg.cost.commission_rate,
                commission_min=engine.cfg.cost.commission_min,
                slippage_pct=engine.cfg.cost.slippage_pct,
            )
            if self._cash_before(date) < required:
                return "cash_short"
            return "cash_short"
        if not bool(sellable.get(code, False)):
            suspend = getattr(engine.dm, "suspend", None)
            if suspend is not None and bool(suspend.loc[date].get(code, 0) == 1):
                return "suspended"
            return "limit_down"
        if self._position_before(date, code) <= 0:
            return "no_position"
        return "invalid_price"

    def _open_price(self, date: pd.Timestamp, code: str) -> Optional[float]:
        open_prices = getattr(self._engine.dm, "open", None)
        if open_prices is None:
            return None
        value = open_prices.loc[date].get(code)
        return None if pd.isna(value) else float(value)

    def _cash_before(self, date: pd.Timestamp) -> float:
        keys = sorted(self.buckets)
        current = date.strftime("%Y-%m-%d")
        previous = [key for key in keys if key < current]
        if not previous:
            return float(self._engine.cfg.initial_capital)
        return float(self.buckets[previous[-1]]["cash"])

    def _position_before(self, date: pd.Timestamp, code: str) -> int:
        keys = sorted(self.buckets)
        current = date.strftime("%Y-%m-%d")
        previous = [key for key in keys if key < current]
        if not previous:
            return 0
        return int(self.buckets[previous[-1]]["positions"].get(code, 0))


class _RecordingBase:
    """proxy 基类：未覆盖成员一律透传内层组件。"""

    def __init__(self, inner: Any, recorder: TraceRecorder) -> None:
        self._inner = inner
        self._recorder = recorder

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RecordingExecutor(_RecordingBase):
    def execute_order(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.execute_order(*args, **kwargs)


class RecordingTracker(_RecordingBase):
    def execute_trade(self, trade: Any) -> Any:
        result = self._inner.execute_trade(trade)
        self._recorder.record_trade(trade)
        return result

    def update_market_values(self, date: Any, prices: Any) -> Any:
        result = self._inner.update_market_values(date, prices)
        self._recorder.close_bucket(date)
        return result


class RecordingOptimizer(_RecordingBase):
    def optimize(self, *args: Any, **kwargs: Any) -> Any:
        weights = self._inner.optimize(*args, **kwargs)
        self._recorder.record_target({str(k): float(v) for k, v in weights.items()})
        return weights
