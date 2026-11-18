"""P-059 场景声明数据契约（DESIGN §4 / Step 5 T1）。

本模块只放**纯数据**：不含流程、不含断言、不读文件、不写文件。
唯一执行入口是 ``_scenarios_builder.build_scenario``（DESIGN DD3），
pytest 与 ``scripts/verify_scenario.py`` 共用同一入口。

字段口径（与 DESIGN §4 的差异已登记为 IMPL 发现）：
- ``DayBucket`` 实为 **10 键**（DESIGN §4.3 表格 10 行，正文「9 键」为笔误）；
- 新增 ``signal`` / ``signal_mode``（weights 模式逐日目标权重注入，复用 ``engine.set_signal``）；
- 新增 ``kind``（backtest / raises / stops / limit_price 四种场景形态）；
- ``ExpectedBlock`` 新增 ``buyable`` / ``sellable`` / ``nav_days`` / ``exempt`` 四个只读期望，
  用于锁定掩码与 NAV 连续性（DESIGN §6 断言原语的输入）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

# 订单 reason 闭集（DESIGN §4.4）：新增项须同步本元组与断言。
REASONS: Tuple[str, ...] = (
    "limit_up",
    "limit_down",
    "suspended",
    "st_blocked",
    "cash_short",
    "t1_locked",
    "invalid_price",
    "no_position",
    "expired",
    "filled",
)

# 订单终态闭集（DESIGN §4.5）。
ORDER_STATES: Tuple[str, ...] = ("filled", "retry", "dropped")

# 逐日桶键（DESIGN §4.3 表格 = 10 键）。
BUCKET_KEYS: Tuple[str, ...] = (
    "date",
    "target_weight",
    "buyable",
    "sellable",
    "orders",
    "filled",
    "rejected",
    "cash",
    "nav",
    "positions",
)

SCENARIO_KINDS: Tuple[str, ...] = ("backtest", "raises", "stops", "limit_price")


@dataclass(frozen=True)
class FillExpectation:
    """一笔**必须发生**的成交（日期为成交日）。"""

    date: str
    code: str
    side: str  # "BUY" | "SELL"
    quantity: int
    price: float
    price_atol: float = 1e-6


@dataclass(frozen=True)
class OrderStateExpectation:
    """某日收盘后某订单的终态（filled / retry / dropped）。"""

    date: str
    code: str
    side: str
    state: str


@dataclass(frozen=True)
class ExpectedBlock:
    """闭式期望（A2：全部为手算值，禁录制）。"""

    fills: Tuple[FillExpectation, ...] = ()
    no_fill: Tuple[Tuple[str, str, str], ...] = ()  # (date, code, side)
    order_states: Tuple[OrderStateExpectation, ...] = ()
    buyable: Tuple[Tuple[str, str, bool], ...] = ()  # (date, code, expected)
    sellable: Tuple[Tuple[str, str, bool], ...] = ()  # (date, code, expected)
    nav_days: Tuple[Tuple[str, float], ...] = ()  # (date, nav)
    final_cash: Optional[float] = None
    final_nav: Optional[float] = None
    final_positions: Optional[Mapping[str, int]] = None
    # (date, code, side)：清算/退市结算等豁免「价格合法 / 掩码语义」的成交
    exempt: Tuple[Tuple[str, str, str], ...] = ()
    cash_identity: bool = True


@dataclass(frozen=True)
class Metamorphic:
    """变质关系声明（DESIGN §7 / DD6）。"""

    kind: str  # "scale" | "inert" | "shift"
    k: float = 1.0
    code: str = ""
    days: int = 0

    @classmethod
    def r1_scale(cls, k: float) -> "Metamorphic":
        return cls(kind="scale", k=k)

    @classmethod
    def r2_inert(cls, code: str) -> "Metamorphic":
        return cls(kind="inert", code=code)

    @classmethod
    def r3_shift(cls, days: int) -> "Metamorphic":
        return cls(kind="shift", days=days)


@dataclass(frozen=True, eq=False)
class ScenarioSpec:
    """单场景声明。

    ``close`` 必须给出；``open``/``high``/``low`` 为 ``None`` 时复用 ``close``
    （此时 ``ohlc_synthetic=True``，仅允许用于不依赖 OHLC 分离的场景）。
    """

    scenario_id: str
    title: str
    layer: str  # L1..L7
    gaps: Tuple[str, ...]  # 关联缺口编号（G*/BZ*）
    dates: pd.DatetimeIndex
    codes: Tuple[str, ...]
    close: np.ndarray
    open: Optional[np.ndarray] = None
    high: Optional[np.ndarray] = None
    low: Optional[np.ndarray] = None
    adj: Optional[np.ndarray] = None
    suspend: Optional[np.ndarray] = None
    st: Optional[np.ndarray] = None
    factors: Mapping[str, np.ndarray] = field(default_factory=dict)
    universe_extra: Mapping[str, Any] = field(default_factory=dict)
    config: Mapping[str, Any] = field(default_factory=dict)
    expected: ExpectedBlock = field(default_factory=ExpectedBlock)
    metamorphic: Tuple[Metamorphic, ...] = ()
    kind: str = "backtest"
    signal: Optional[np.ndarray] = None
    signal_mode: str = "weights"
    stop_case: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ohlc_independent(self) -> bool:
        """True = 场景显式提供了独立 OHLC（非 close 复用）。"""
        return self.open is not None or self.high is not None or self.low is not None
