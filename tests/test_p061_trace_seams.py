"""P-061 seam 集成验收（T-B01..B15，真实 engine + 合成数据）。

统一入口：``_scenarios_builder.build_scenario``（P-059 DD3）；本文件不新增夹具生成器。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _scenarios_builder import ScenarioRun, build_scenario
from _scenarios_spec import ExpectedBlock, ScenarioSpec

A = "000001"
B = "000002"
C = "000003"
NO_COST = {
    "commission_rate": 0.0,
    "commission_min": 0.0,
    "stamp_tax_rate": 0.0,
    "slippage_pct": 0.0,
}


def _dates(n: int = 5) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n)


def _grid(n: int, m: int, value: float) -> np.ndarray:
    return np.full((n, m), float(value))


def _spec(
    scenario_id: str,
    *,
    dates: pd.DatetimeIndex,
    codes: tuple[str, ...],
    close: np.ndarray,
    open_: np.ndarray | None = None,
    suspend: np.ndarray | None = None,
    st: np.ndarray | None = None,
    signal: np.ndarray | None = None,
    config: dict[str, Any] | None = None,
    universe_extra: dict[str, Any] | None = None,
) -> ScenarioSpec:
    return ScenarioSpec(
        scenario_id=scenario_id,
        title=scenario_id,
        layer="L5",
        gaps=("P061",),
        dates=dates,
        codes=codes,
        close=close,
        open=open_,
        suspend=suspend,
        st=st,
        factors={"factor_alpha": np.ones_like(close)},
        signal=signal,
        config=config or {},
        universe_extra=universe_extra or {},
        expected=ExpectedBlock(),
    )


def _trace_dir(run: ScenarioRun) -> Path:
    return Path(run.engine.cfg.audit_trace_dir)


def _csv(run: ScenarioRun, name: str) -> pd.DataFrame:
    return pd.read_csv(_trace_dir(run) / name, dtype=str, keep_default_na=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inject_buy_spec(
    scenario_id: str,
    *,
    cash: float,
    open_prices: np.ndarray,
    config: dict[str, Any] | None = None,
    universe_extra: dict[str, Any] | None = None,
) -> ScenarioSpec:
    dates = _dates(len(open_prices))
    base_config: dict[str, Any] = {"no_rebalance": True, "cost": dict(NO_COST)}
    base_config.update(config or {})
    if "inject_orders" not in base_config:
        base_config["inject_orders"] = [
            {"code": A, "side": "BUY", "quantity": 100, "path": "queue"}
        ]
    return _spec(
        scenario_id,
        dates=dates,
        codes=(A,),
        close=open_prices.copy(),
        open_=open_prices,
        config={**base_config, "initial_capital": cash},
        universe_extra=universe_extra,
    )


def _run_basic(tmp_path: Path, name: str = "basic") -> ScenarioRun:
    root = tmp_path / name
    prices = _grid(5, 1, 10.0)
    spec = _inject_buy_spec(
        f"P061-{name}",
        cash=100_000.0,
        open_prices=prices,
        config={"audit_trace_dir": root / "audit", "write_manifest": True},
    )
    return build_scenario(spec, root)


def test_t_b01_same_cfg_pair_run_is_zero_behavior(tmp_path: Path) -> None:
    """T-B01 | 同 cfg 对跑：三 CSV sha256 一致；开启产 4 文件；指纹必异。"""
    prices = _grid(5, 1, 10.0)
    root_off = tmp_path / "off"
    root_on = tmp_path / "on"
    spec_off = _inject_buy_spec(
        "P061-B01-off",
        cash=100_000.0,
        open_prices=prices,
        config={"write_manifest": True},
    )
    spec_on = _inject_buy_spec(
        "P061-B01-on",
        cash=100_000.0,
        open_prices=prices,
        config={"write_manifest": True, "audit_trace_dir": root_on / "audit"},
    )
    run_off = build_scenario(spec_off, root_off)
    run_on = build_scenario(spec_on, root_on)

    for name in ("trades.csv", "portfolio_snapshots.csv", "pending_order_events.csv"):
        assert _sha256(root_off / "out" / name) == _sha256(root_on / "out" / name), name

    trace_files = ("trace_day.csv", "trace_order.csv", "trace_fill.csv", "alignment.json")
    assert all((root_on / "audit" / name).is_file() for name in trace_files)
    assert not (root_off / "audit").exists()

    manifest_off = json.loads((root_off / "out" / "manifest.json").read_text(encoding="utf-8"))
    manifest_on = json.loads((root_on / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_off["input_fingerprint"] != manifest_on["input_fingerprint"]
    assert "audit_trace_dir" in manifest_on["config"]
    assert _trace_dir(run_on) == root_on / "audit"


def test_t_b02_trace_fill_matches_trades_csv(tmp_path: Path) -> None:
    """T-B02 | trace_fill 行数/金额和 == trades.csv。"""
    run = _run_basic(tmp_path)
    fills = _csv(run, "trace_fill.csv")
    trades = pd.read_csv(run.root / "out" / "trades.csv")
    assert len(fills) == len(trades)
    assert fills["qty"].astype(int).sum() == int(trades["quantity"].sum())
    assert float(fills["amount"].astype(float).sum()) == pytest.approx(
        float(trades["amount"].sum()), abs=1e-9
    )


def test_t_b03_matches_recorder_buckets(tmp_path: Path) -> None:
    """T-B03 | 与测试侧 TraceRecorder 日桶对拍：positions / nav / fills 逐日一致。"""
    run = _run_basic(tmp_path)
    day = _csv(run, "trace_day.csv")
    fills = _csv(run, "trace_fill.csv")
    for date, bucket in run.trace.buckets.items():
        rows = day[day["date"] == date]
        assert not rows.empty, f"{date}: trace_day 缺行"
        assert float(rows.iloc[0]["nav"]) == pytest.approx(bucket["nav"], abs=1e-6)
        positions = {
            str(row["stock"]): int(row["position_qty"])
            for row in rows.to_dict("records")
            if int(row["position_qty"] or 0) != 0
        }
        assert positions == dict(bucket["positions"]), date
        assert int((fills["date"] == date).sum()) == len(bucket["filled"]), date


def test_t_b04_s1_records_every_day(tmp_path: Path) -> None:
    """T-B04 | 20 交易日 × N_days=5：每日 1 条 S1；触发日 1/6/11/16。"""
    root = tmp_path / "b04"
    prices = _grid(20, 1, 10.0)
    spec = _spec(
        "P061-B04",
        dates=_dates(20),
        codes=(A,),
        close=prices,
        config={
            "audit_trace_dir": root / "audit",
            "cost": dict(NO_COST),
            "rebalance": {"method": "fixed", "frequency": "N_days", "n_days": 5},
        },
    )
    run = build_scenario(spec, root)
    events = run.engine._trace.trigger_events
    assert len(events) == 20
    assert all(event["trigger"] == "FixedIntervalTrigger" for event in events)
    triggered = [index for index, event in enumerate(events) if event["triggered"]]
    assert triggered == [0, 5, 10, 15]


def test_t_b05_three_reject_reasons_are_distinguishable(tmp_path: Path) -> None:
    """T-B05 | 涨停 / 停牌 / ST 三因可区分。"""
    root = tmp_path / "b05"
    dates = _dates(5)
    close = _grid(5, 3, 10.0)
    open_prices = close.copy()
    open_prices[1, 2] = 11.0  # C：次日开盘 = 前收 ×1.1 → 涨停
    close[1, 2] = 11.0
    suspend = np.zeros((5, 3), dtype=int)
    suspend[1:, 0] = 1  # A：次日起停牌
    st = np.zeros((5, 3), dtype=int)
    st[1:, 1] = 1  # B：次日起 ST
    spec = _spec(
        "P061-B05",
        dates=dates,
        codes=(A, B, C),
        close=close,
        open_=open_prices,
        suspend=suspend,
        st=st,
        signal=_grid(5, 3, 0.3),
        config={
            "audit_trace_dir": root / "audit",
            "cost": dict(NO_COST),
            "universe": {"exclude_st": True},
        },
    )
    run = build_scenario(spec, root)
    orders = _csv(run, "trace_order.csv")
    reasons = {row["stock"]: row["reject_reason"] for row in orders.to_dict("records")}
    assert reasons[A] == "suspended"
    assert reasons[B] == "st_blocked"
    assert reasons[C] == "limit_up"


def test_t_b06_cash_short_retries_then_fills(tmp_path: Path) -> None:
    """T-B06 | 首日 cash_short 且仍活跃；次日价格回落后成交 filled。"""
    root = tmp_path / "b06"
    open_prices = np.array([[10.0], [9.5], [9.5], [9.5], [9.5]])
    spec = _inject_buy_spec(
        "P061-B06",
        cash=1004.0,
        open_prices=open_prices,
        config={
            "audit_trace_dir": root / "audit",
            "cost": {
                "commission_rate": 0.0003,
                "commission_min": 5.0,
                "stamp_tax_rate": 0.001,
                "slippage_pct": 0.001,
            },
        },
    )
    run = build_scenario(spec, root)
    orders = _csv(run, "trace_order.csv")
    row = orders.iloc[0]
    assert row["reject_reason"] == "cash_short"
    assert int(row["retry_count"]) >= 1
    assert row["status"] == "filled"
    assert int(row["filled_qty"]) == 100


def test_t_b07_sell_without_position_is_cancelled_or_no_position(tmp_path: Path) -> None:
    """T-B07 | 卖出无持仓 → 队列路径 cancelled + no_position。"""
    root = tmp_path / "b07"
    prices = _grid(5, 1, 10.0)
    spec = _spec(
        "P061-B07",
        dates=_dates(5),
        codes=(A,),
        close=prices,
        open_=prices,
        config={
            "no_rebalance": True,
            "audit_trace_dir": root / "audit",
            "cost": dict(NO_COST),
            "inject_orders": [{"code": A, "side": "SELL", "quantity": 100, "path": "queue"}],
        },
    )
    run = build_scenario(spec, root)
    orders = _csv(run, "trace_order.csv")
    row = orders.iloc[0]
    assert row["reject_reason"] == "no_position"
    assert row["status"] in ("cancelled", "dropped")


def test_t_b08_expiry_uses_collector_retry_count(tmp_path: Path) -> None:
    """T-B08 | max_pending_days_buy=2：第 3 日 expired；collector retry_count=2。"""
    root = tmp_path / "b08"
    dates = _dates(5)
    suspend = np.zeros((5, 1), dtype=int)
    suspend[1:, 0] = 1
    spec = _spec(
        "P061-B08",
        dates=dates,
        codes=(A,),
        close=_grid(5, 1, 10.0),
        suspend=suspend,
        signal=_grid(5, 1, 0.5),
        config={
            "audit_trace_dir": root / "audit",
            "cost": dict(NO_COST),
            "max_pending_days_buy": 2,
        },
    )
    run = build_scenario(spec, root)
    orders = _csv(run, "trace_order.csv")
    row = orders.iloc[0]
    assert row["status"] == "expired"
    assert int(row["retry_count"]) == 2


def test_t_b09_fallback_dual_registration(tmp_path: Path) -> None:
    """T-B09 | 执行失败触发 fallback → 双登记（replaces_order_ref + executed_by_fallback）。"""
    from _scenarios_builder import _write_fixtures, build_config
    from core.engine_v2 import BacktestEngineV2

    root = tmp_path / "b09"
    prices = _grid(5, 2, 10.0)
    spec = _spec(
        "P061-B09",
        dates=_dates(5),
        codes=(A, B),
        close=prices,
        signal=_grid(5, 2, 0.5),
        config={
            "audit_trace_dir": root / "audit",
            "cost": dict(NO_COST),
            "enable_fallback": True,
        },
    )
    _write_fixtures(spec, root)
    cfg = build_config(spec, root)
    engine = BacktestEngineV2(cfg)
    engine.setup()

    class _FailFirstBuy:
        """代理执行器：A 的买入返回失败（其余透传），以触发 fallback 分支。"""

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        def execute_order(self, *args: Any, **kwargs: Any) -> Any:
            stock = args[0]
            side = args[1]
            if str(stock) == A and getattr(side, "name", "") == "BUY":
                return False, None
            return self._inner.execute_order(*args, **kwargs)

    engine.executor = _FailFirstBuy(engine.executor)
    engine.run()

    trace_root = root / "audit"
    fills = pd.read_csv(trace_root / "trace_fill.csv", dtype=str, keep_default_na=False)
    replaced = fills[fills["replaces_order_ref"] != ""]
    assert not replaced.empty, fills.to_dict("records")
    replacement = replaced.iloc[0]
    assert replacement["stock"] == B

    orders = pd.read_csv(trace_root / "trace_order.csv", dtype=str, keep_default_na=False)
    original = orders[orders["order_ref"] == replacement["replaces_order_ref"]].iloc[0]
    assert original["status"] == "executed_by_fallback"
    assert original["fallback_stock"] == B


def test_t_b10_final_liquidation_marks_direct_fill(tmp_path: Path) -> None:
    """T-B10 | 末日强平：order_ref="direct" + close_reason=final_liquidation。"""
    run = _run_basic(tmp_path)
    fills = _csv(run, "trace_fill.csv")
    direct = fills[fills["order_ref"] == "direct"]
    assert len(direct) == 1
    last_date = max(run.trace.buckets)
    day = _csv(run, "trace_day.csv")
    last_rows = day[day["date"] == last_date]
    assert set(last_rows["close_reason"]) == {"final_liquidation"}


def test_t_b11_delisted_settlement_amount(tmp_path: Path) -> None:
    """T-B11 | 退市结算：close_reason=delisted；金额 = last_close×(1+return)×qty。"""
    root = tmp_path / "b11"
    prices = _grid(5, 1, 10.0)
    spec = _inject_buy_spec(
        "P061-B11",
        cash=100_000.0,
        open_prices=prices,
        config={"audit_trace_dir": root / "audit"},
        universe_extra={
            "delist_rows": [{"stock": A, "delist_date": "2024-01-04", "delist_return": -0.1}]
        },
    )
    run = build_scenario(spec, root)
    fills = _csv(run, "trace_fill.csv")
    direct = fills[fills["order_ref"] == "direct"]
    assert len(direct) == 1
    assert float(direct.iloc[0]["amount"]) == pytest.approx(10.0 * 0.9 * 100)

    day = _csv(run, "trace_day.csv")
    delisted = day[day["close_reason"] == "delisted"]
    assert not delisted.empty
    assert delisted.iloc[0]["stock"] == A


def test_t_b12_last_day_overwrite_matches_snapshots(tmp_path: Path) -> None:
    """T-B12 | trace_day 末行 = snapshots 末行（强平后）且持仓归零。"""
    run = _run_basic(tmp_path)
    day = _csv(run, "trace_day.csv")
    snapshots = pd.read_csv(run.root / "out" / "portfolio_snapshots.csv")
    last_date = str(pd.Timestamp(snapshots["date"].iloc[-1]).strftime("%Y-%m-%d"))
    last_rows = day[day["date"] == last_date]
    assert not last_rows.empty
    assert float(last_rows.iloc[0]["nav"]) == pytest.approx(
        float(snapshots["total_value"].iloc[-1]), abs=1e-6
    )
    assert all(int(value or 0) == 0 for value in last_rows["position_qty"])


def test_t_b13_event_bus_and_trace_coexist(tmp_path: Path) -> None:
    """T-B13 | event_log_path + audit_trace_dir 同开：seq 连续、trace 完整。"""
    root = tmp_path / "b13"
    prices = _grid(5, 1, 10.0)
    spec = _inject_buy_spec(
        "P061-B13",
        cash=100_000.0,
        open_prices=prices,
        config={
            "audit_trace_dir": root / "audit",
            "event_log_path": root / "events.jsonl",
        },
    )
    run = build_scenario(spec, root)
    lines = [
        json.loads(line)
        for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seqs = [int(item["seq"]) for item in lines]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
    types = {item["type"] for item in lines}
    assert "engine.run_started" in types
    assert "engine.run_finished" in types
    assert (_trace_dir(run) / "alignment.json").is_file()


def test_t_b14_zero_fill_run_still_writes_four_files(tmp_path: Path) -> None:
    """T-B14 | 零成交 + 存活 cash_short 订单：4 文件生成；终态 expired。

    该订单（创建日距末日 6 个自然日 > max_pending_days_buy=5）在末日日内
    ``_process_pending_orders`` 末尾的 ``mark_expired`` 处置为 EXPIRED，
    由最后一次日末差分落终态；run 末终扫（PENDING → dropped）的直接断言在 T-A04。
    """
    root = tmp_path / "b14"
    prices = _grid(5, 1, 10.0)
    spec = _inject_buy_spec(
        "P061-B14",
        cash=500.0,
        open_prices=prices,
        config={"audit_trace_dir": root / "audit"},
    )
    run = build_scenario(spec, root)
    for name in ("trace_day.csv", "trace_order.csv", "trace_fill.csv", "alignment.json"):
        assert (_trace_dir(run) / name).is_file()
    fills = _csv(run, "trace_fill.csv")
    assert fills.empty
    alignment = json.loads((_trace_dir(run) / "alignment.json").read_text(encoding="utf-8"))
    assert alignment["counts"]["fills"] == 0
    orders = _csv(run, "trace_order.csv")
    assert orders.iloc[0]["status"] == "expired"


def test_t_b15_manifest_contract_and_stable_fingerprint(tmp_path: Path) -> None:
    """T-B15 | manifest 含新字段；同版本两次构建指纹相同。"""
    root = tmp_path / "b15"
    prices = _grid(5, 1, 10.0)

    def run_once() -> dict[str, Any]:
        spec = _inject_buy_spec(
            "P061-B15",
            cash=100_000.0,
            open_prices=prices,
            config={"write_manifest": True, "audit_trace_dir": root / "audit"},
        )
        build_scenario(spec, root)
        return json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))

    first = run_once()
    second = run_once()
    assert "audit_trace_dir" in first["config"]
    assert "audit_trace_full" in first["config"]
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["run_id"] != second["run_id"]
