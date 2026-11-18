"""P-059 断言原语（DESIGN §6 / Step 5 T3）。

全部为**闭式比较**（禁录制）：期望值来自场景声明，本模块只做对齐与口径检查。
十条原语：shape / states / reasons / mask / cash / price / target bounds /
target deviation / capability / dirty-input，另有 ``assert_scenario`` 组合入口。
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable

import pandas as pd

from _scenarios_capability import CAPABILITY_BOUNDARIES
from _scenarios_builder import ScenarioRun
from _scenarios_spec import BUCKET_KEYS, ORDER_STATES, REASONS, ScenarioSpec

MONEY_ATOL = 1e-6


def _date_key(date: Any) -> str:
    return pd.Timestamp(date).strftime("%Y-%m-%d")


def _exempt(run: ScenarioRun, date: str, code: str, side: str) -> bool:
    return (date, code, side) in set(run.spec.expected.exempt)


def assert_trace_shape(run: ScenarioRun) -> None:
    """I13：桶数 == 交易日数，日期严格递增，10 键齐备。"""
    expected = [_date_key(d) for d in run.trade_dates]
    actual = sorted(run.trace.buckets)
    assert len(actual) == len(
        expected
    ), f"{run.spec.scenario_id}: 桶数 {len(actual)} != 交易日数 {len(expected)}"
    assert actual == expected, f"{run.spec.scenario_id}: 桶日期与交易日不一致"
    for key, bucket in run.trace.buckets.items():
        missing = [name for name in BUCKET_KEYS if name not in bucket]
        assert not missing, f"{run.spec.scenario_id}: 桶 {key} 缺键 {missing}"


def assert_order_states_closed(run: ScenarioRun) -> None:
    """订单终态 ⊆ {filled, retry, dropped}，且同一订单不得同时 filled 与 dropped。

    订单身份 = (code, side, create_date, quantity)：同一 (code, side) 的旧订单被
    ``cancel_orders`` 取消（dropped）后，新订单再成交（filled）是合法序列。
    """
    created = {
        (o["code"], o["side"], o["create_date"], int(o["quantity"])) for o in run.trace.created
    }
    terminal: dict[tuple[str, str, str, int], set[str]] = {}
    for event in run.trace.state_events:
        assert (
            event["state"] in ORDER_STATES
        ), f"{run.spec.scenario_id}: 订单状态越界 {event['state']}"
        key = (
            event["code"],
            event["side"],
            event["create_date"],
            int(event["quantity"]),
        )
        if key not in created:
            continue
        terminal.setdefault(key, set()).add(event["state"])
    for key, seen in terminal.items():
        assert (
            not {"filled", "dropped"} <= seen
        ), f"{run.spec.scenario_id}: 订单 {key} 同时出现 filled 与 dropped"


def assert_reasons_closed(run: ScenarioRun) -> None:
    """拒单 reason ⊆ 闭集 10 项。"""
    for bucket in run.trace.buckets.values():
        for item in bucket["rejected"]:
            assert (
                item["reason"] in REASONS
            ), f"{run.spec.scenario_id}: {bucket['date']} 拒单 reason 越界 {item['reason']}"


def assert_mask_semantics(run: ScenarioRun) -> None:
    """成交必须落在当日对应方向的可交易掩码内（豁免项除外）。"""
    for fill in run.trace.fills:
        if _exempt(run, fill["date"], fill["code"], fill["side"]):
            continue
        bucket = run.trace.buckets.get(fill["date"])
        assert bucket is not None, f"{run.spec.scenario_id}: 成交日 {fill['date']} 无桶"
        allowed = bucket["buyable"] if fill["side"] == "BUY" else bucket["sellable"]
        assert fill["code"] in allowed, (
            f"{run.spec.scenario_id}: {fill['date']} {fill['side']} {fill['code']} "
            f"不在掩码内（成交价 {fill['price']}）"
        )


def assert_cash_non_negative(run: ScenarioRun, atol: float = 1e-6) -> None:
    for key, bucket in run.trace.buckets.items():
        assert bucket["cash"] >= -atol, f"{run.spec.scenario_id}: {key} 现金为负 {bucket['cash']}"


def assert_price_legal(run: ScenarioRun, atol: float = 1e-6) -> None:
    """成交价必须落在当日涨跌停带内（无涨跌幅限制日与豁免项跳过）。"""
    no_limit = run.masks["no_limit"]
    limit_up = run.masks["limit_up"]
    limit_down = run.masks["limit_down"]
    for fill in run.trace.fills:
        if _exempt(run, fill["date"], fill["code"], fill["side"]):
            continue
        date = pd.Timestamp(fill["date"])
        if date not in limit_up.index:
            continue
        if fill["code"] not in limit_up.columns:
            continue
        if bool(no_limit.loc[date].get(fill["code"], False)):
            continue
        up = limit_up.loc[date].get(fill["code"])
        down = limit_down.loc[date].get(fill["code"])
        if pd.isna(up) or pd.isna(down):
            continue
        price = float(fill["price"])
        tol = max(atol, abs(price) * 1e-9)
        assert float(down) - tol <= price <= float(up) + tol, (
            f"{run.spec.scenario_id}: {fill['date']} {fill['code']} 成交价 {price} "
            f"越界 [{float(down)}, {float(up)}]"
        )


def assert_target_weight_bounds(run: ScenarioRun, max_weight: float, atol: float = 1e-9) -> None:
    """每只目标权重 ∈ [0, max_weight]（权重和 > 1 由现金闸门兜底，见 S10）。"""
    for bucket in run.trace.buckets.values():
        for code, weight in bucket["target_weight"].items():
            assert (
                -atol <= weight <= max_weight + atol
            ), f"{run.spec.scenario_id}: {bucket['date']} {code} 目标权重越界 {weight}"


def assert_target_deviation(run: ScenarioRun, tol: float) -> None:
    """实际持仓市值权重与目标权重偏离 ≤ tol（仅在有目标权重的桶上检查）。"""
    for key, bucket in run.trace.buckets.items():
        targets = bucket["target_weight"]
        if not targets:
            continue
        nav = bucket["nav"]
        if nav <= 0:
            continue
        close_row = run.engine.dm.close.loc[pd.Timestamp(key)]
        for code, target in targets.items():
            quantity = bucket["positions"].get(code, 0)
            actual = quantity * float(close_row.get(code, 0.0)) / nav
            assert abs(actual - target) <= tol, (
                f"{run.spec.scenario_id}: {key} {code} 实际权重 {actual:.6f} "
                f"偏离目标 {target:.6f} 超过 {tol}"
            )


def assert_capability_declared() -> None:
    """能力边界声明必须为 DESIGN §10 的 8 键全量（少一或多一都算缺口）。"""
    expected = {
        "timeframe",
        "intraday_auction",
        "intraday_halt",
        "delist_period_no_limit",
        "expiry_basis",
        "alpha_claim",
        "execution_price",
        "limit_price_rounding",
    }
    actual = set(CAPABILITY_BOUNDARIES)
    assert (
        actual == expected
    ), f"能力边界键不一致：缺少 {expected - actual}，多余 {actual - expected}"


def assert_dirty_input_raises(call: Callable[[], Any], *, expect: type[BaseException]) -> None:
    """脏输入守卫：非法声明必须抛指定异常。"""
    try:
        call()
    except expect:
        return
    raise AssertionError(f"脏输入未抛 {expect.__name__}")


def _match_fills(run: ScenarioRun, expected: Iterable[Any]) -> None:
    actual = list(run.trace.fills)
    for want in expected:
        found = None
        for fill in actual:
            if (
                fill["date"] == want.date
                and fill["code"] == want.code
                and fill["side"] == want.side
                and int(fill["quantity"]) == int(want.quantity)
                and math.isclose(fill["price"], want.price, abs_tol=want.price_atol)
            ):
                found = fill
                break
        assert found is not None, (
            f"{run.spec.scenario_id}: 期望成交缺失 {want.date} {want.side} "
            f"{want.code} {want.quantity}@{want.price}"
        )
        actual.remove(found)
    assert not actual, f"{run.spec.scenario_id}: 存在未声明成交 {actual}"


def assert_scenario(spec: ScenarioSpec, run: ScenarioRun) -> None:
    """组合入口：全部原语 + 场景声明期望。"""
    expected = spec.expected
    assert_trace_shape(run)
    assert_order_states_closed(run)
    assert_reasons_closed(run)
    assert_mask_semantics(run)
    assert_cash_non_negative(run)
    assert_price_legal(run)
    assert_target_weight_bounds(run, max_weight=1.0)

    _match_fills(run, expected.fills)

    for date, code, side in expected.no_fill:
        assert not any(
            fill["date"] == date and fill["code"] == code and fill["side"] == side
            for fill in run.trace.fills
        ), f"{spec.scenario_id}: 不应成交却成交 {date} {side} {code}"

    for want in expected.order_states:
        hit = any(
            event["date"] == want.date
            and event["code"] == want.code
            and event["side"] == want.side
            and event["state"] == want.state
            for event in run.trace.state_events
        )
        assert hit, (
            f"{spec.scenario_id}: 期望订单状态缺失 {want.date} {want.side} "
            f"{want.code} -> {want.state}"
        )

    for date, code, flag in expected.buyable:
        bucket = run.trace.buckets[date]
        actual = code in bucket["buyable"]
        assert (
            actual is flag
        ), f"{spec.scenario_id}: {date} {code} buyable 期望 {flag} 实际 {actual}"

    for date, code, flag in expected.sellable:
        bucket = run.trace.buckets[date]
        actual = code in bucket["sellable"]
        assert (
            actual is flag
        ), f"{spec.scenario_id}: {date} {code} sellable 期望 {flag} 实际 {actual}"

    for date, nav in expected.nav_days:
        actual = float(run.trace.buckets[date]["nav"])
        assert math.isclose(
            actual, nav, abs_tol=max(MONEY_ATOL, abs(nav) * 1e-9)
        ), f"{spec.scenario_id}: {date} NAV 期望 {nav} 实际 {actual}"

    if expected.final_cash is not None:
        assert math.isclose(
            run.final_cash,
            expected.final_cash,
            abs_tol=max(MONEY_ATOL, abs(expected.final_cash) * 1e-9),
        ), f"{spec.scenario_id}: 期末现金期望 {expected.final_cash} 实际 {run.final_cash}"
    if expected.final_nav is not None:
        assert math.isclose(
            run.final_nav,
            expected.final_nav,
            abs_tol=max(MONEY_ATOL, abs(expected.final_nav) * 1e-9),
        ), f"{spec.scenario_id}: 期末净值期望 {expected.final_nav} 实际 {run.final_nav}"
    if expected.final_positions is not None:
        assert run.final_positions == dict(expected.final_positions), (
            f"{spec.scenario_id}: 期末持仓期望 {dict(expected.final_positions)} "
            f"实际 {run.final_positions}"
        )

    if expected.cash_identity:
        _assert_cash_identity(run)


def _assert_cash_identity(run: ScenarioRun) -> None:
    close = pd.DataFrame(run.spec.close, index=run.spec.dates, columns=list(run.spec.codes))
    for key, bucket in run.trace.buckets.items():
        market_value = sum(
            quantity * float(close.loc[pd.Timestamp(key), code])
            for code, quantity in bucket["positions"].items()
        )
        total = float(bucket["cash"]) + market_value
        assert math.isclose(
            total, float(bucket["nav"]), abs_tol=max(MONEY_ATOL, abs(total) * 1e-9)
        ), f"{run.spec.scenario_id}: {key} 账目恒等失败 cash+MV={total} nav={bucket['nav']}"
