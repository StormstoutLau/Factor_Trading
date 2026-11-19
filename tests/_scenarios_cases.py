"""P-059 场景注册表（DESIGN §8 / Step 5 T4-T5、T9）。

17 条单一来源：S01-S14 必做（覆盖 L1-L7 全部 7 层）+ E01-E03 扩展
+ S15（P-048 风险 overlay 端到端，共 18 条）。
全部 ``expected`` 为**手算闭式值**（A2，禁录制）；关键推导写在各自 ``title``/``gaps``
与下方注释中。金额单位：元。

口径统一（除 S09 外）：
- ``initial_capital = 100_000``，``cost = 0``（佣金/印花/滑点全零）→ 便于整数现金核对；
- 目标股数 = ``floor(w * 100000 * 0.985 / price / 100) * 100``（target_positions L130-134）；
- 非末日的「末日强平」在最后交易日按收盘价全部卖出（零成本 → 现金回到 100_000）。

``gaps`` 口径（**Step 8 回写** F-S8-P059-1）：与 DESIGN §8「覆盖」列逐条对齐；
S08 的 X3 为外部规则锚不入场景码（DESIGN §8 保留注记）。
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from _scenarios_spec import (
    ExpectedBlock,
    FillExpectation,
    Metamorphic,
    OrderStateExpectation,
    ScenarioSpec,
)

A = "000001"
B = "600000"
C = "601398"

NO_COST: Dict[str, Any] = {
    "commission_rate": 0.0,
    "commission_min": 0.0,
    "stamp_tax_rate": 0.0,
    "slippage_pct": 0.0,
}


def _bd(n: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def _d(index: pd.DatetimeIndex, i: int) -> str:
    return index[i].strftime("%Y-%m-%d")


def _grid(rows: int, cols: int, value: float = 10.0) -> np.ndarray:
    return np.full((rows, cols), float(value))


def _ohlc_consistent(open_prices: np.ndarray, close_prices: np.ndarray) -> tuple:
    """由 open/close 生成自洽 high/low（避免 high < open 的脏 bar）。"""
    high = np.maximum(open_prices, close_prices)
    low = np.minimum(open_prices, close_prices)
    return high, low


def _fills(*rows: tuple) -> tuple:
    return tuple(FillExpectation(*row) for row in rows)


def _cases() -> List[ScenarioSpec]:
    cases: List[ScenarioSpec] = []

    # ------------------------------------------------------------------
    # S01 L4 涨停买不进 + 次日重试（默认 scores → equal_weight 全链路）
    # d0 目标 0.5/0.5 → 各 4900 股；d1 A 开盘 11.0 = 涨停 → 拒单；
    # d2 A 回到 10.0 → 补成交；d4 末日按收盘价清仓。
    # ------------------------------------------------------------------
    d = _bd(5)
    close = _grid(5, 2, 10.0)
    open_p = _grid(5, 2, 10.0)
    open_p[:, 0] = [10.0, 11.0, 10.0, 10.0, 10.0]
    factor = _grid(5, 2, 1.0)
    factor[:, 0] = 2.0
    cases.append(
        ScenarioSpec(
            scenario_id="S01",
            title="涨停买不进并在次日重试成交",
            layer="L4",
            gaps=("G9",),
            dates=d,
            codes=(A, B),
            close=close,
            open=open_p,
            high=np.maximum(open_p, close),
            low=np.minimum(open_p, close),
            factors={"factor_alpha": factor},
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), B, "BUY", 4900, 10.0),
                    (_d(d, 2), A, "BUY", 4900, 10.0),
                    (_d(d, 4), A, "SELL", 4900, 10.0),
                    (_d(d, 4), B, "SELL", 4900, 10.0),
                ),
                no_fill=((_d(d, 1), A, "BUY"),),
                order_states=(
                    OrderStateExpectation(_d(d, 1), A, "BUY", "retry"),
                    OrderStateExpectation(_d(d, 2), A, "BUY", "filled"),
                    OrderStateExpectation(_d(d, 1), B, "BUY", "filled"),
                ),
                buyable=((_d(d, 1), A, False), (_d(d, 2), A, True)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S02 L4 跌停卖不出：d0 全仓买入 A → d1 目标归零卖出 → d2 开盘 9.0 = 跌停拒单，
    # 再平衡刷新取消旧卖单并重建（B 为惰性标的，保证 tradable 非空不被提前返回）
    # → d3 开盘 9.0 可卖（跌停 8.1）成交。
    # 现金：100000 - 9800*10 = 2000；NAV d2 = 2000 + 9800*9 = 90200。
    # ------------------------------------------------------------------
    d = _bd(5)
    a_close = np.array([10.0, 10.0, 9.0, 9.0, 9.0])
    b_close = np.full(5, 10.0)
    close = np.column_stack([a_close, b_close])
    open_p = close.copy()
    signal = np.zeros((5, 2))
    signal[0, 0] = 1.0
    cases.append(
        ScenarioSpec(
            scenario_id="S02",
            title="跌停卖不出并顺延至下一可卖日",
            layer="L4",
            gaps=("BZ9", "G13"),
            dates=d,
            codes=(A, B),
            close=close,
            open=open_p,
            high=np.maximum(open_p, close),
            low=np.minimum(open_p, close),
            factors={"factor_alpha": _grid(5, 2, 1.0)},
            signal=signal,
            config={"cost": dict(NO_COST), "rebalance": {"frequency": "daily"}},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 9800, 10.0),
                    (_d(d, 3), A, "SELL", 9800, 9.0),
                ),
                no_fill=((_d(d, 2), A, "SELL"),),
                order_states=(OrderStateExpectation(_d(d, 2), A, "SELL", "dropped"),),
                sellable=((_d(d, 2), A, False), (_d(d, 3), A, True)),
                nav_days=((_d(d, 2), 90_200.0), (_d(d, 4), 90_200.0)),
                final_cash=90_200.0,
                final_nav=90_200.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(1.5),),
        )
    )

    # ------------------------------------------------------------------
    # S03 L4 一字板三日（独立 OHLC）：d1=11.0 / d2=12.1 / d3=13.31 均为涨停，
    # d4 开板 12.5（带内）成交 4900 股；末日 12.5 清仓 → 100000。
    # ------------------------------------------------------------------
    d = _bd(5)
    close = np.array([[10.0], [11.0], [12.1], [13.31], [12.5]])
    open_p = close.copy()
    cases.append(
        ScenarioSpec(
            scenario_id="S03",
            title="一字板连续涨停后开板成交（独立 OHLC）",
            layer="L4",
            gaps=("G3", "G9"),
            dates=d,
            codes=(A,),
            close=close,
            open=open_p,
            high=close.copy(),
            low=close.copy(),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 0.5),
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 4), A, "BUY", 4900, 12.5),
                    (_d(d, 4), A, "SELL", 4900, 12.5),
                ),
                buyable=(
                    (_d(d, 1), A, False),
                    (_d(d, 2), A, False),
                    (_d(d, 3), A, False),
                    (_d(d, 4), A, True),
                ),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S04 L1 停牌 2 日后复牌：d1/d2 suspend=1 → 拒单且 NAV 保持 100000；
    # d3 复牌成交 9800 股；d4 清仓。
    # ------------------------------------------------------------------
    d = _bd(5)
    suspend = np.zeros((5, 1), dtype=int)
    suspend[1:3, 0] = 1
    cases.append(
        ScenarioSpec(
            scenario_id="S04",
            title="停牌期间订单挂起且 NAV 不变",
            layer="L1",
            gaps=("BZ14", "G16"),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            suspend=suspend,
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 1.0),
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 3), A, "BUY", 9800, 10.0),
                    (_d(d, 4), A, "SELL", 9800, 10.0),
                ),
                no_fill=((_d(d, 1), A, "BUY"), (_d(d, 2), A, "BUY")),
                order_states=(
                    OrderStateExpectation(_d(d, 1), A, "BUY", "retry"),
                    OrderStateExpectation(_d(d, 2), A, "BUY", "retry"),
                    OrderStateExpectation(_d(d, 3), A, "BUY", "filled"),
                ),
                nav_days=((_d(d, 1), 100_000.0), (_d(d, 2), 100_000.0)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(3.0), Metamorphic.r3_shift(7)),
        )
    )

    # ------------------------------------------------------------------
    # S05 L4 主板 ST 涨跌幅 5%（2026-07-06 前）：d1 开盘 10.5 = 10*1.05 拒单，
    # d2 开盘 10.5 < 11.025 可买 → 成交 4900 股。
    # ------------------------------------------------------------------
    d = _bd(5)
    close = np.array([[10.0], [10.5], [10.5], [10.5], [10.5]])
    open_p = close.copy()
    cases.append(
        ScenarioSpec(
            scenario_id="S05",
            title="主板 ST 5% 涨跌幅边界（2026-07-06 前）",
            layer="L4",
            gaps=("G6",),
            dates=d,
            codes=(A,),
            close=close,
            open=open_p,
            high=close.copy(),
            low=close.copy(),
            st=np.ones((5, 1), dtype=int),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 0.5),
            config={"cost": dict(NO_COST), "universe": {"exclude_st": False}},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 2), A, "BUY", 4900, 10.5),
                    (_d(d, 4), A, "SELL", 4900, 10.5),
                ),
                no_fill=((_d(d, 1), A, "BUY"),),
                buyable=((_d(d, 1), A, False), (_d(d, 2), A, True)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r2_inert("601988"),),
        )
    )

    # ------------------------------------------------------------------
    # S06 L4 IPO 前 5 个交易日无涨跌幅：600000 于 d0 上市，d1 开盘 13.0
    # （> 10% 带）仍可买入；d5 恢复 10%（13*1.1=14.3 为涨停）→ buyable=False。
    # ------------------------------------------------------------------
    d = _bd(7)
    close_6 = _grid(7, 1, 13.0)
    close_6[0, 0] = 10.0
    open_6 = close_6.copy()
    open_6[5, 0] = 14.3
    cases.append(
        ScenarioSpec(
            scenario_id="S06",
            title="IPO 前 5 日无涨跌幅、第 6 日恢复",
            layer="L4",
            gaps=("BZ11", "G14"),
            dates=d,
            codes=(B,),
            close=close_6,
            open=open_6,
            high=np.maximum(open_6, close_6),
            low=np.minimum(open_6, close_6),
            factors={"factor_alpha": _grid(7, 1, 1.0)},
            signal=_grid(7, 1, 0.5),
            universe_extra={"list_rows": [{"stock": B, "list_date": _d(d, 0)}]},
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), B, "BUY", 4900, 13.0),
                    (_d(d, 6), B, "SELL", 4900, 13.0),
                ),
                buyable=((_d(d, 1), B, True), (_d(d, 5), B, False)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S07 L5 退市清算：d3 退市（delist_return=-0.5）→ 清算价 10*0.5=5.0，
    # 9800 股回款 49000；期末现金 = 2000 + 49000 = 51000。
    # ------------------------------------------------------------------
    d = _bd(5)
    cases.append(
        ScenarioSpec(
            scenario_id="S07",
            title="退市按 delist_return 清算且持仓归零",
            layer="L5",
            gaps=("BZ13", "G16"),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 1.0),
            universe_extra={
                "delist_rows": [{"stock": A, "delist_date": _d(d, 3), "delist_return": -0.5}]
            },
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 9800, 10.0),
                    (_d(d, 3), A, "SELL", 9800, 5.0),
                ),
                exempt=((_d(d, 3), A, "SELL"),),
                final_cash=51_000.0,
                final_nav=51_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S08 L4 T+1 结构性约束：d1 买入成交当日不能卖出（卖单 d1 创建、d2 成交）。
    # ------------------------------------------------------------------
    d = _bd(5)
    signal_8 = np.zeros((5, 1))
    signal_8[0, 0] = 1.0
    cases.append(
        ScenarioSpec(
            scenario_id="S08",
            title="T+1：建仓日不可卖出、次日可卖",
            layer="L4",
            gaps=("G13",),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=signal_8,
            config={"cost": dict(NO_COST), "rebalance": {"frequency": "daily"}},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 9800, 10.0),
                    (_d(d, 2), A, "SELL", 9800, 10.0),
                ),
                no_fill=((_d(d, 1), A, "SELL"),),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S09 L5 小额最低佣金（G4 修复后的队列路径侧）：现金 1004 < 1000+5+1=1006
    # → 整单拒绝、不成交、现金不变（次日路径对拍见 g4_cash_parity）。
    # ------------------------------------------------------------------
    d = _bd(5)
    cases.append(
        ScenarioSpec(
            scenario_id="S09",
            title="小额订单最低佣金导致整单拒绝（队列路径）",
            layer="L5",
            gaps=("BZ10", "G4"),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            config={
                "initial_capital": 1004.0,
                "no_rebalance": True,
                "inject_orders": [{"code": A, "side": "BUY", "quantity": 100}],
            },
            expected=ExpectedBlock(
                final_cash=1004.0,
                final_nav=1004.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r2_inert("601988"),),
        )
    )

    # ------------------------------------------------------------------
    # S10 L3 权重和 > 1：注入 0.8/0.8 → 各 7800 股（78000 元）；
    # d1 仅 A 成交（现金 22000），B 因现金不足持续 retry 至 d4 过期。
    # ------------------------------------------------------------------
    d = _bd(5)
    cases.append(
        ScenarioSpec(
            scenario_id="S10",
            title="权重和大于 1 时现金闸门夹紧（仅首单成交）",
            layer="L3",
            gaps=("BZ5", "G12"),
            dates=d,
            codes=(A, B),
            close=_grid(5, 2, 10.0),
            factors={"factor_alpha": _grid(5, 2, 1.0)},
            config={
                "cost": dict(NO_COST),
                "inject_weights": {A: 0.8, B: 0.8},
            },
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 7800, 10.0),
                    (_d(d, 4), A, "SELL", 7800, 10.0),
                ),
                no_fill=((_d(d, 1), B, "BUY"), (_d(d, 4), B, "BUY")),
                order_states=(OrderStateExpectation(_d(d, 1), B, "BUY", "retry"),),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S11 L1 脏输入守卫：close 含 NaN → 构建前即 ValueError（不进入引擎）。
    # ------------------------------------------------------------------
    d = _bd(3)
    dirty = _grid(3, 1, 10.0)
    dirty[1, 0] = np.nan
    cases.append(
        ScenarioSpec(
            scenario_id="S11",
            title="脏输入（NaN 价格）在构建期快速失败",
            layer="L1",
            gaps=("BZ1", "G10"),
            dates=d,
            codes=(A,),
            close=dirty,
            factors={"factor_alpha": _grid(3, 1, 1.0)},
            config={"expect_build_error": "ValueError"},
            expected=ExpectedBlock(fills=(), final_cash=None),
            kind="raises",
        )
    )

    # ------------------------------------------------------------------
    # S12 L2 全标的不可交易（停牌）：再平衡早退、零订单、NAV 不变。
    # ------------------------------------------------------------------
    d = _bd(5)
    cases.append(
        ScenarioSpec(
            scenario_id="S12",
            title="全标的停牌时无订单产生",
            layer="L2",
            gaps=("BZ14", "G9"),
            dates=d,
            codes=(A, B),
            close=_grid(5, 2, 10.0),
            suspend=np.ones((5, 2), dtype=int),
            factors={"factor_alpha": _grid(5, 2, 1.0)},
            signal=_grid(5, 2, 0.5),
            config={"cost": dict(NO_COST), "rebalance": {"frequency": "daily"}},
            expected=ExpectedBlock(
                nav_days=tuple((_d(d, i), 100_000.0) for i in range(5)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S13 L6 止损/止盈同 bar 双触发：入场 100，次 bar low=88（≤90）且 high=110
    # （≥105）→ 优先级 SL → stop_loss。
    # ------------------------------------------------------------------
    d = _bd(2)
    cases.append(
        ScenarioSpec(
            scenario_id="S13",
            title="止损与止盈同 bar 双触发时止损优先",
            layer="L6",
            gaps=("BZ15", "G17"),
            dates=d,
            codes=(A,),
            close=np.array([[100.0], [105.0]]),
            factors={"factor_alpha": _grid(2, 1, 1.0)},
            kind="stops",
            stop_case={
                "config": {"stop_loss_pct": 0.10, "take_profit_pct": 0.05},
                "bars": [
                    {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0},
                    {"open": 100.0, "high": 110.0, "low": 88.0, "close": 105.0},
                ],
                "expect": [("hold", ""), ("exit", "stop_loss")],
            },
            expected=ExpectedBlock(fills=()),
        )
    )

    # ------------------------------------------------------------------
    # S14 L7 空信号 → 全清仓：d0 1/3 各 3200 股（96000）；d1 目标归零卖出；
    # d2 三笔卖单成交 → 现金 100000。
    # ------------------------------------------------------------------
    d = _bd(5)
    signal_14 = np.zeros((5, 3))
    signal_14[0, :] = 1.0 / 3.0
    cases.append(
        ScenarioSpec(
            scenario_id="S14",
            title="目标权重归零时全部清仓",
            layer="L7",
            gaps=("BZ6", "G18"),
            dates=d,
            codes=(A, B, C),
            close=_grid(5, 3, 10.0),
            factors={"factor_alpha": _grid(5, 3, 1.0)},
            signal=signal_14,
            config={"cost": dict(NO_COST), "rebalance": {"frequency": "daily"}},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 3200, 10.0),
                    (_d(d, 1), B, "BUY", 3200, 10.0),
                    (_d(d, 1), C, "BUY", 3200, 10.0),
                    (_d(d, 2), A, "SELL", 3200, 10.0),
                    (_d(d, 2), B, "SELL", 3200, 10.0),
                    (_d(d, 2), C, "SELL", 3200, 10.0),
                ),
                no_fill=((_d(d, 1), A, "SELL"),),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r3_shift(7),),
        )
    )

    # ------------------------------------------------------------------
    # E01 L4 涨跌停价不做 0.01 舍入：前收 10.03 → 涨停 11.033（≠11.03）。
    # ------------------------------------------------------------------
    d = _bd(2)
    cases.append(
        ScenarioSpec(
            scenario_id="E01",
            title="涨跌停价浮点直乘不舍入",
            layer="L4",
            gaps=("G6",),
            dates=d,
            codes=(A,),
            close=_grid(2, 1, 10.03),
            factors={"factor_alpha": _grid(2, 1, 1.0)},
            kind="limit_price",
            stop_case={"prev_close": 10.03, "expected_up": 11.033},
            expected=ExpectedBlock(fills=()),
        )
    )

    # ------------------------------------------------------------------
    # E02 L4 长假日期缺口：d0 挂单在 13 个自然日后的首个交易日 d1 仍按开盘执行
    # （队列路径先执行后 mark_expired；次日路径相反 —— 差异已登记能力边界）。
    # ------------------------------------------------------------------
    d = pd.DatetimeIndex(["2024-01-02", "2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18"])
    cases.append(
        ScenarioSpec(
            scenario_id="E02",
            title="长假日期缺口后首个交易日按开盘执行挂单",
            layer="L4",
            gaps=("BZ18",),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 1.0),
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 9800, 10.0),
                    (_d(d, 4), A, "SELL", 9800, 10.0),
                ),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # E03 L5 复权因子变更日：raw 估值 NAV 恒 100000（连续）；
    # 且 d2 起限价参考价按 adj 调整（10*1/2=5 → 涨停 5.5）→ buyable=False。
    # ------------------------------------------------------------------
    d = _bd(5)
    adj = np.array([[1.0], [1.0], [2.0], [2.0], [2.0]])
    cases.append(
        ScenarioSpec(
            scenario_id="E03",
            title="复权因子变更日 NAV 连续且限价参考价随 adj 调整",
            layer="L5",
            gaps=("BZ12", "G15"),
            dates=d,
            codes=(A,),
            close=_grid(5, 1, 10.0),
            adj=adj,
            factors={"factor_alpha": _grid(5, 1, 1.0)},
            signal=_grid(5, 1, 0.5),
            config={"cost": dict(NO_COST)},
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 4900, 10.0),
                    (_d(d, 4), A, "SELL", 4900, 10.0),
                ),
                buyable=((_d(d, 1), A, True), (_d(d, 2), A, False)),
                nav_days=tuple((_d(d, i), 100_000.0) for i in range(5)),
                final_cash=100_000.0,
                final_nav=100_000.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r1_scale(2.0),),
        )
    )

    # ------------------------------------------------------------------
    # S15 L2 风险 overlay：DD 腿端到端 + 引擎接线（P-048；target_vol=None → 只验 DD 腿）
    # 三项时序口径（缺一必红）：
    #   ① 整手数量按**订单创建日收盘价**；
    #   ② 成交价 = **次日 open**；
    #   ③ rebalance(d) 只见 nav(0..d-1)（rebalance 在 L508，nav append 在 L512）。
    # 手算（cost=0，initial=100_000，value_buffer=0.985）：
    #   d0 close 10.00 → floor(1.0*100000*0.985/10/100)*100 = 9800 股（BUY 单，d1 执行）
    #   d1 open 10.00 成交 9800 → 现金 2000；收盘 10.50 → NAV 104,900（running peak）
    #   d2 rebalance 见 nav=[100000, 104900] → DD=0；收盘 10.00 → NAV 100,000
    #   d3 rebalance 见 nav=[100000, 104900, 100000]
    #      DD = 4900/104900 = 4.6711% → t = (0.046711-0.02)/(0.08-0.02) = 0.445186
    #      scale_dd = 1 - 0.445186 = 0.554814
    #      total_value = 2000 + 9800*9.20 = 92,160
    #      目标 = floor(0.554814*92160*0.985/9.20/100)*100 = floor(54.744)*100 = 5400 股
    #      → SELL 4400（d4 开盘成交）；收盘 9.20 → NAV = 2000+9800*9.20 = 92,160
    #   d4 rebalance 见 nav=[...,92160]：DD = 1-92160/104900 = 12.145% ≥ 8% → scale=0
    #      → SELL 5400（d5 开盘成交）；期末持仓归零
    #   d5 rebalance：持仓 0 + 目标 0 → 无新订单（避免与末日强平双写，F-S6-P059-6）
    #      收盘 NAV = 42,480 + 5,400*9.20 = 92,160 → 末日无持仓可强平
    # ------------------------------------------------------------------
    d = _bd(6)
    s15_close = np.array([[10.00], [10.50], [10.00], [9.20], [9.20], [9.20]])
    s15_open = np.array([[10.00], [10.00], [10.50], [10.00], [9.20], [9.20]])
    s15_high, s15_low = _ohlc_consistent(s15_open, s15_close)
    cases.append(
        ScenarioSpec(
            scenario_id="S15",
            title="风险 overlay DD 腿：ramp 减仓后深度回撤清仓",
            layer="L2",
            gaps=("G-P048-2",),
            dates=d,
            codes=(A,),
            close=s15_close,
            open=s15_open,
            high=s15_high,
            low=s15_low,
            factors={"factor_alpha": _grid(6, 1, 1.0)},
            signal=_grid(6, 1, 1.0),
            config={
                "cost": dict(NO_COST),
                # builder 默认 N_days=len(dates) → 必须显式 daily，否则只再平衡一次
                "rebalance": {"frequency": "daily"},
                # 缩短 cov 回看（本场景 target_vol=None，vol 腿不参与）
                "optimizer": {"cov_lookback": 2},
                "risk_overlay": {
                    "enabled": True,
                    "target_vol": None,
                    "defensive_policy": "cash_scaling",
                    "dd_soft": 0.02,
                    "dd_hard": 0.08,
                    "b_min": 0.0,
                    "scale_floor": 0.0,
                    "dd_hysteresis": False,
                },
            },
            expected=ExpectedBlock(
                fills=_fills(
                    (_d(d, 1), A, "BUY", 9800, 10.00),
                    (_d(d, 4), A, "SELL", 4400, 9.20),
                    (_d(d, 5), A, "SELL", 5400, 9.20),
                ),
                nav_days=(
                    (_d(d, 1), 104_900.0),
                    (_d(d, 2), 100_000.0),
                    (_d(d, 3), 92_160.0),
                    (_d(d, 4), 92_160.0),
                ),
                final_cash=92_160.0,
                final_nav=92_160.0,
                final_positions={},
            ),
            metamorphic=(Metamorphic.r2_inert("601988"),),
        )
    )

    return cases


SCENARIOS: dict[str, ScenarioSpec] = {spec.scenario_id: spec for spec in _cases()}

# 单一来源自检（导入期即暴露重复/遗漏）
assert len(SCENARIOS) == 18, f"场景数应为 18，实际 {len(SCENARIOS)}"
assert {spec.layer for spec in SCENARIOS.values()} == {
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "L7",
}, "层级覆盖不全"
