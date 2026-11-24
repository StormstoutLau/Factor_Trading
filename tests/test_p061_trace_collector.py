"""P-061 采集器单元验收（T-A01..A10，oracle: contract / closed-form / state / boundary）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from core.execution import Trade
from core.pending import OrderSide, create_pending_order
from core.trace import (
    CLOSE_REASONS,
    REJECT_REASONS,
    TRACE_DAY_COLUMNS,
    TRACE_FILL_COLUMNS,
    TRACE_ORDER_COLUMNS,
    TRACE_SCHEMA_VERSION,
    TraceCollector,
    TraceConfig,
    classify_reject,
)

DATE = pd.Timestamp("2024-01-02")
DATE2 = pd.Timestamp("2024-01-03")
A = "000001"
B = "000002"
C = "000003"


def _order(stock: str, side: str, qty: int, date: pd.Timestamp = DATE) -> Any:
    return create_pending_order(stock, OrderSide[side], qty, date)


def _trade(
    stock: str,
    side: str,
    qty: int,
    price: float,
    *,
    date: pd.Timestamp = DATE,
    amount: float | None = None,
) -> Trade:
    gross = qty * price if amount is None else amount
    return Trade(
        date=date,
        stock=stock,
        side=OrderSide[side],
        quantity=qty,
        price=price,
        amount=gross,
        cost=6.0,
        net_amount=-gross - 6.0,
    )


def _collector(tmp_path: Path, *, full: bool = False) -> TraceCollector:
    return TraceCollector(TraceConfig(out_dir=tmp_path / "trace", full=full))


def _read(tmp_path: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(tmp_path / "trace" / name, dtype=str, keep_default_na=False)


def _status_by_ref(frame: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {row["order_ref"]: row for row in frame.to_dict("records")}


def test_t_a01_disabled_collector_is_zero_io(tmp_path: Path) -> None:
    """T-A01 | oracle=contract：out_dir=None → enabled=False、零文件、调用全无害。"""
    collector = TraceCollector(TraceConfig(out_dir=None))
    assert collector.enabled is False
    order = _order(A, "BUY", 100)
    collector.on_trigger(DATE, object(), True)
    collector.on_targets(DATE, [{"stock": A, "target_qty": 100}])
    collector.on_order_created(order)
    collector.on_order_rejected(order, "limit_up")
    collector.on_fill(_trade(A, "BUY", 100, 10.0), order)
    collector.on_close(DATE, A, "rebalance")
    collector.on_day_end(DATE, [order], {A: (100, 1000.0)}, 1000.0, 1000.0)
    collector.overwrite_last_day(DATE, {}, 1000.0, 1000.0)
    assert collector.finalize() == []
    assert not (tmp_path / "trace").exists()


def test_t_a02_order_seq_is_unique_and_stable(tmp_path: Path) -> None:
    """T-A02 | oracle=closed-form：同日同票多单唯一且稳定；两次构造结果相同。"""
    refs_first = []
    collector = _collector(tmp_path)
    for _ in range(3):
        refs_first.append(collector.on_order_created(_order(A, "BUY", 100)))
    refs_first.append(collector.on_order_created(_order(A, "SELL", 100)))

    refs_second = []
    other = TraceCollector(TraceConfig(out_dir=tmp_path / "trace2"))
    for _ in range(3):
        refs_second.append(other.on_order_created(_order(A, "BUY", 100)))
    refs_second.append(other.on_order_created(_order(A, "SELL", 100)))

    assert len(set(refs_first)) == 4
    assert refs_first == refs_second
    assert refs_first[0].endswith("|BUY|00001")
    assert refs_first[3].endswith("|SELL|00004")


def test_t_a03_classify_reject_closed_set() -> None:
    """T-A03 | oracle=cross-check：8 组分支 → 闭集内确定值（与 _scenarios_trace 词表对拍）。"""
    groups: list[tuple[dict[str, Any], str]] = [
        (dict(side="BUY", buyable=False), "limit_up"),
        (dict(side="SELL", sellable=False), "limit_down"),
        (dict(side="BUY", buyable=False, suspended=True), "suspended"),
        (dict(side="BUY", buyable=False, is_st=True, exclude_st=True), "st_blocked"),
        (dict(side="BUY", has_price=False), "invalid_price"),
        (dict(side="BUY", cash_short=True), "cash_short"),
        (dict(side="SELL", has_position=False), "no_position"),
        (dict(side="BUY"), "unknown"),
    ]
    for overrides, expected in groups:
        params: dict[str, Any] = {
            "side": "BUY",
            "buyable": True,
            "sellable": True,
            "suspended": False,
            "is_st": False,
            "exclude_st": False,
            "has_price": True,
            "cash_short": False,
            "has_position": True,
        }
        params.update(overrides)
        result = classify_reject(**params)
        assert result == expected, f"{overrides} → {result}（期望 {expected}）"
        assert result in REJECT_REASONS


def test_t_a04_day_end_diff_three_states(tmp_path: Path) -> None:
    """T-A04 | oracle=state：filled / retry / expired 三态 + run 末终扫 dropped（F-10）。"""
    collector = _collector(tmp_path)
    order_a = _order(A, "BUY", 100)
    order_b = _order(B, "BUY", 100)
    order_c = _order(C, "BUY", 100)
    collector.on_day_end(DATE, [order_a, order_b, order_c], {}, 1000.0, 1000.0)

    collector.on_fill(_trade(A, "BUY", 100, 10.0, date=DATE2), order_a)
    order_c.mark_expired(DATE2)
    collector.on_day_end(DATE2, [order_b], {}, 1000.0, 1000.0)
    collector.finalize()

    rows = _status_by_ref(_read(tmp_path, "trace_order.csv"))
    assert rows[collector.order_ref(order_a)]["status"] == "filled"
    assert rows[collector.order_ref(order_b)]["status"] == "retry"
    assert rows[collector.order_ref(order_c)]["status"] == "expired"

    # run 末终扫（F-10）：仍 PENDING 的存活单经 finalize(remaining_orders) 落 dropped
    collector.finalize(remaining_orders=[order_b])
    rows = _status_by_ref(_read(tmp_path, "trace_order.csv"))
    assert rows[collector.order_ref(order_b)]["status"] == "dropped"


def test_t_a05_fallback_dual_registration(tmp_path: Path) -> None:
    """T-A05 | oracle=state：fill 记 replaces_order_ref；原单 executed_by_fallback。"""
    collector = _collector(tmp_path)
    original = _order(A, "BUY", 100)
    fallback = _order(B, "BUY", 100)
    original_ref = collector.on_order_created(original)
    collector.on_order_created(fallback)
    collector.on_fill(
        _trade(B, "BUY", 100, 10.0),
        fallback,
        replaces_order_ref=original_ref,
    )
    collector.finalize()

    fills = _read(tmp_path, "trace_fill.csv")
    assert fills.iloc[0]["replaces_order_ref"] == original_ref
    assert fills.iloc[0]["order_ref"] == collector.order_ref(fallback)

    rows = _status_by_ref(_read(tmp_path, "trace_order.csv"))
    assert rows[original_ref]["status"] == "executed_by_fallback"
    assert rows[original_ref]["fallback_stock"] == B


def test_t_a06_direct_fill_sentinel(tmp_path: Path) -> None:
    """T-A06 | oracle=boundary：direct 哨兵 → order_ref="direct"、orders≠fills 不报错。"""
    collector = _collector(tmp_path)
    collector.on_fill(_trade(A, "SELL", 100, 10.0), None, direct=True)
    collector.finalize()

    fills = _read(tmp_path, "trace_fill.csv")
    assert fills.iloc[0]["order_ref"] == "direct"
    alignment = collector.finalize()  # 幂等：重复落盘不抛异常
    assert len(alignment) == 4
    import json

    payload = json.loads((tmp_path / "trace" / "alignment.json").read_text(encoding="utf-8"))
    assert payload["counts"]["direct_fills"] == 1
    assert payload["counts"]["orders"] == 0
    assert payload["counts"]["fills"] == 1


def test_t_a07_overwrite_last_day_replaces_not_appends(tmp_path: Path) -> None:
    """T-A07 | oracle=boundary：末日覆写 = 覆盖非追加，值等于后传值。"""
    collector = _collector(tmp_path)
    collector.on_day_end(DATE, [], {A: (100, 1000.0)}, 1000.0, 2000.0)
    collector.overwrite_last_day(DATE, {A: (0, 0.0)}, 3000.0, 3100.0)
    collector.finalize()

    day = _read(tmp_path, "trace_day.csv")
    assert len(day) == 1
    row = day.iloc[0]
    assert row["stock"] == A
    assert int(row["position_qty"]) == 0
    assert float(row["nav"]) == pytest.approx(3100.0)


def test_t_a08_finalize_contract(tmp_path: Path) -> None:
    """T-A08 | oracle=contract：4 文件、列序/表头精确、schema_version=1.0。"""
    collector = _collector(tmp_path)
    order = _order(A, "BUY", 100)
    collector.on_targets(
        DATE,
        [
            {
                "stock": A,
                "signal": 1.5,
                "target_weight": 1.0,
                "target_qty": 100,
                "current_qty": 0,
                "is_exit": False,
                "tradable": True,
                "buyable": True,
                "sellable": True,
            }
        ],
    )
    collector.on_order_created(order)
    collector.on_fill(_trade(A, "BUY", 100, 10.0), order)
    collector.on_close(DATE, A, "rebalance")
    collector.on_day_end(DATE, [], {A: (100, 1000.0)}, 4.0, 1004.0)
    written = collector.finalize()

    assert {path.name for path in written} == {
        "trace_day.csv",
        "trace_order.csv",
        "trace_fill.csv",
        "alignment.json",
    }
    assert list(_read(tmp_path, "trace_day.csv").columns) == list(TRACE_DAY_COLUMNS)
    assert list(_read(tmp_path, "trace_order.csv").columns) == list(TRACE_ORDER_COLUMNS)
    assert list(_read(tmp_path, "trace_fill.csv").columns) == list(TRACE_FILL_COLUMNS)

    import json

    payload = json.loads((tmp_path / "trace" / "alignment.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == TRACE_SCHEMA_VERSION == "1.0"
    assert payload["reconcile"]["qty_by_side"] == {
        "BUY": 100,
        "SELL": 0,
        "SELL_SHORT": 0,
        "BUY_TO_COVER": 0,
    }
    assert payload["reconcile"]["residual"] == pytest.approx(0.0)
    assert CLOSE_REASONS == {"rebalance", "final_liquidation", "delisted", "unknown"}


def test_t_a09_alignment_residual_closed_form(tmp_path: Path) -> None:
    """T-A09 | oracle=closed-form：残差 0；篡改 SELL 金额 +1 → 残差 > 1e-8。"""

    def build(root: Path, sell_amount: float) -> dict[str, Any]:
        collector = TraceCollector(TraceConfig(out_dir=root))
        buy = _order(A, "BUY", 100)
        sell = _order(A, "SELL", 40)
        collector.on_order_created(buy)
        collector.on_order_created(sell)
        collector.on_fill(_trade(A, "BUY", 100, 10.0, amount=1000.0), buy)
        collector.on_fill(_trade(A, "SELL", 40, 12.0, amount=sell_amount), sell)
        trades = pd.DataFrame({"amount": [1000.0, 480.0]})
        collector.on_day_end(DATE, [], {A: (60, 720.0)}, 3000.0, 3720.0)
        collector.finalize(trades_df=trades)
        import json

        return json.loads((root / "alignment.json").read_text(encoding="utf-8"))

    clean = build(tmp_path / "clean", 480.0)
    assert clean["reconcile"]["residual"] == pytest.approx(0.0)

    tampered = build(tmp_path / "tampered", 481.0)
    assert tampered["reconcile"]["residual"] > 1e-8


def test_t_a10_full_flag_rowset(tmp_path: Path) -> None:
    """T-A10 | oracle=boundary：full=False 1 行；full=True 2 行（含非目标）。"""
    rows = [
        {"stock": A, "signal": 1.5, "target_qty": 100, "is_exit": False},
        {"stock": B, "signal": 0.5, "target_qty": 0, "is_exit": False},
    ]
    narrow = _collector(tmp_path, full=False)
    narrow.on_targets(DATE, rows)
    narrow.finalize()
    assert len(_read(tmp_path, "trace_day.csv")) == 1

    wide = _collector(tmp_path, full=True)
    wide.on_targets(DATE, rows)
    wide.finalize()
    day = _read(tmp_path, "trace_day.csv")
    assert len(day) == 2
    non_target = day[day["stock"] == B].iloc[0]
    assert int(non_target["target_qty"]) == 0
    assert float(non_target["signal"]) == pytest.approx(0.5)
