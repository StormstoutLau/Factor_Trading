"""P-050 引擎级集成测试：F6 强平执行 / F7 换月 / F12 V3 拒绝 + golden 4 例。

golden 期望值全部闭式手算（见 ``_CASES`` 的 ``hand_derivation``），
不使用录制脚本。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from core.config import (
    AssetInfo,
    AssetType,
    BacktestConfig,
    CostConfig,
    OptimizerConfig,
    RebalanceConfig,
)
from core.engine_v2 import BacktestEngineV2
from core.engine_v3_vector import VectorBacktestEngine
from core.execution import Trade
from core.pending import OrderSide

GOLDEN_DIR = Path(__file__).parent / "golden" / "p050"
DATES = pd.date_range("2026-06-01", periods=4, freq="B")
ZERO_COST = CostConfig(
    commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
)


class _FuturesDM:
    """最小期货数据管理器：价格/因子/结算价全部内存注入。"""

    def __init__(self, prices, factors, infos, settlements=None):
        self.trade_dates = DATES
        # 期货测试常以空价格表装配，列名以因子表为准
        self.stock_codes = list(prices.columns) or list(factors.columns)
        self.n_stocks = len(self.stock_codes)
        self.returns = pd.DataFrame(0.0, index=DATES, columns=self.stock_codes)
        self._prices = prices
        self._factors = factors
        self._infos = infos
        self._settlements = settlements or {}

    def get_adj_price(self, price_type: str, adjustment_type: str) -> pd.DataFrame:
        return self._prices

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        return self._factors

    def get_data_info(self) -> dict:
        return {"source": "fake-futures"}

    def get_asset_info(self, symbol: str) -> AssetInfo:
        return self._infos.get(symbol, AssetInfo())

    def get_settlement_prices(self, date) -> dict:
        return dict(self._settlements.get(pd.Timestamp(date), {}))


class _Universe:
    def __init__(self, blocked_sell=(), blocked_dates=None):
        self._all = pd.DataFrame(True, index=DATES, columns=list(self._all_stocks))
        self._sellable = self._all.copy()
        dates = list(blocked_dates) if blocked_dates is not None else list(DATES)
        for stock in blocked_sell:
            self._sellable.loc[dates, stock] = False

    def build_masks(self) -> None:
        return None

    @property
    def buyable(self) -> pd.DataFrame:
        return self._all

    @property
    def sellable(self) -> pd.DataFrame:
        return self._sellable

    @property
    def tradable(self) -> pd.DataFrame:
        return self._all

    def get_mask_summary(self) -> dict:
        return {"source": "fake"}


class _Passthrough:
    def process(self, raw: pd.DataFrame) -> pd.DataFrame:
        return raw


class _ScoreOptimizer:
    """按因子绝对值取第一名，权重 ±1（负因子 → 做空意图）。"""

    def optimize(self, factor_scores, returns=None, cov_matrix=None) -> pd.Series:
        scores = factor_scores.dropna()
        scores = scores[scores != 0]
        if scores.empty:
            return pd.Series(dtype=float)
        top = scores.abs().nlargest(1).index[0]
        return pd.Series({top: 1.0 if scores[top] > 0 else -1.0})


class _AlwaysTrigger:
    def should_trigger(self, date, **kwargs) -> bool:
        return True


def _base_config(tmpdir: str, symbols, initial=1_000_000.0, allow_short=False) -> BacktestConfig:
    return BacktestConfig(
        data_dir=Path(tmpdir),
        output_dir=Path(tmpdir) / "output",
        factor_files=["dummy.pkl"],
        factor_weights={},
        cost=ZERO_COST,
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        optimizer=OptimizerConfig(target_count=1, round_lot=False),
        enable_pending_orders=True,
        enable_fallback=False,
        initial_capital=initial,
        futures_symbols=list(symbols),
        allow_negative_stock_positions=allow_short,
    )


def _run(tmpdir, dm, symbols, initial=1_000_000.0, allow_short=False, force_liquidation=False):
    cfg = _base_config(tmpdir, symbols, initial=initial, allow_short=allow_short)
    _Universe._all_stocks = dm.stock_codes
    engine = BacktestEngineV2(
        cfg,
        data_manager=dm,
        universe_filter=_Universe(),
        factor_pipeline=_Passthrough(),
        optimizer=_ScoreOptimizer(),
        trigger=_AlwaysTrigger(),
    )
    engine.setup()
    if not force_liquidation:
        engine._force_liquidation = lambda *args, **kwargs: None
    with patch(
        "core.engine_v2.generate_report",
        return_value={"metrics": {}, "charts": {}, "reports": {}},
    ):
        results = engine.run()
    return engine, results


def _flat_prices(columns, close, open_=None):
    open_frame = pd.DataFrame(
        {c: [open_ if open_ is not None else close[c]] * len(DATES) for c in columns},
        index=DATES,
    )
    close_frame = pd.DataFrame({c: [close[c]] * len(DATES) for c in columns}, index=DATES)
    return open_frame, close_frame


# ---------------------------------------------------------------------------
# F12：V3 拒绝
# ---------------------------------------------------------------------------


def test_f12_v3_reject():
    with pytest.raises(ValueError, match="futures_symbols"):
        VectorBacktestEngine({"futures_symbols": ["IH2406"]})
    with pytest.raises(ValueError, match="allow_negative_stock_positions"):
        VectorBacktestEngine({"allow_negative_stock_positions": True})
    # 默认配置不受影响
    VectorBacktestEngine({})


# ---------------------------------------------------------------------------
# A14：setup 期合约规格校验
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "info, match",
    [
        (AssetInfo(AssetType.FUTURE, 0.0, 0.1, expiry_date="2026-12-18"), "multiplier"),
        (AssetInfo(AssetType.FUTURE, 300.0, None, expiry_date="2026-12-18"), "margin_ratio"),
        (AssetInfo(AssetType.FUTURE, 300.0, 0.1), "expiry_date"),
        (AssetInfo(AssetType.FUTURE, 300.0, 0.1, expiry_date="2026-06-30"), "交割月"),
    ],
)
def test_setup_specs_validation(info, match, tmp_path):
    factors = pd.DataFrame({"IH2406": [1.0] * 4}, index=DATES)
    open_frame, close_frame = _flat_prices(["IH2406"], {"IH2406": 3000.0})
    dm = _FuturesDM(pd.DataFrame(), factors, {"IH2406": info})
    dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)
    _Universe._all_stocks = ["IH2406"]
    engine = BacktestEngineV2(
        _base_config(str(tmp_path), ["IH2406"]),
        data_manager=dm,
        universe_filter=_Universe(),
        factor_pipeline=_Passthrough(),
        optimizer=_ScoreOptimizer(),
        trigger=_AlwaysTrigger(),
    )
    with pytest.raises(ValueError, match=match):
        engine.setup()


# ---------------------------------------------------------------------------
# F6：强平执行 / 顺延
# ---------------------------------------------------------------------------


def _engine_with_negative_cash(tmpdir, blocked_dates=()):
    info = {"IH2406": AssetInfo(AssetType.FUTURE, 300.0, 0.1, expiry_date="2026-12-18")}
    open_frame, close_frame = _flat_prices(["IH2406"], {"IH2406": 2960.0}, open_=2960.0)
    placeholder = pd.DataFrame({"IH2406": [0.0] * len(DATES)}, index=DATES)
    dm = _FuturesDM(placeholder, pd.DataFrame(1.0, index=DATES, columns=["IH2406"]), info)
    dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)
    _Universe._all_stocks = ["IH2406"]
    cfg = _base_config(tmpdir, ["IH2406"], initial=100_000.0)
    engine = BacktestEngineV2(
        cfg,
        data_manager=dm,
        universe_filter=_Universe(blocked_sell=("IH2406",), blocked_dates=blocked_dates),
        factor_pipeline=_Passthrough(),
        optimizer=_ScoreOptimizer(),
        trigger=_AlwaysTrigger(),
    )
    engine.setup()

    trade = Trade(
        date=DATES[0],
        stock="IH2406",
        side=OrderSide.BUY,
        quantity=1,
        price=3000.0,
        amount=900_000.0,
        cost=0.0,
        net_amount=900_000.0,
        asset_type=AssetType.FUTURE,
        multiplier=300.0,
    )
    engine.tracker.execute_trade(trade)  # type: ignore[union-attr]
    return engine


def test_f6_liquidation_exec(tmp_path):
    engine = _engine_with_negative_cash(str(tmp_path))
    assert engine.tracker is not None
    assert engine.tracker.get_available_cash() == pytest.approx(10_000.0)

    engine._settle_futures(DATES[0])
    assert engine.tracker.get_available_cash() < 0
    kinds = [info.get("_kind") for info in engine._next_day_orders]
    assert kinds == ["liquidation"]

    engine._execute_next_day_orders(DATES[1], 1)
    position = engine.tracker.get_position("IH2406")
    assert position is not None and position.quantity == 0
    assert engine.tracker.get_available_cash() >= 0


def test_f6_liquidation_deferred(tmp_path):
    # 仅次日（DATES[1]）不可卖 → 强平顺延 1 日，再往后恢复可卖
    engine = _engine_with_negative_cash(str(tmp_path), blocked_dates=(DATES[1],))
    engine._settle_futures(DATES[0])
    engine._execute_next_day_orders(DATES[1], 1)

    assert engine.tracker is not None
    position = engine.tracker.get_position("IH2406")
    assert position is not None and position.quantity == 1
    assert len(engine._next_day_orders) == 1
    assert engine._next_day_orders[0]["deferred_days"] == 1

    # 次日可卖 → 完成强平（请求不丢失）
    engine._execute_next_day_orders(DATES[2], 2)
    position = engine.tracker.get_position("IH2406")
    assert position is not None and position.quantity == 0


# ---------------------------------------------------------------------------
# F7：换月（== 研究 I-P050-6 换月守恒）
# ---------------------------------------------------------------------------


def test_f7_roll(tmp_path):
    infos = {
        "IH2406": AssetInfo(
            AssetType.FUTURE,
            300.0,
            0.1,
            expiry_date="2026-06-03",
            roll_days_before_expiry=1,
            roll_target="IH2409",
        ),
        "IH2409": AssetInfo(AssetType.FUTURE, 300.0, 0.1, expiry_date="2026-09-18"),
    }
    factors = pd.DataFrame(
        {"IH2406": [1.0, 1.0, 0.0, 0.0], "IH2409": [0.0, 0.0, 1.0, 1.0]}, index=DATES
    )
    open_frame = pd.DataFrame({"IH2406": [3000.0] * 4, "IH2409": [3000.0] * 4}, index=DATES)
    close_frame = pd.DataFrame({"IH2406": [3000.0] * 4, "IH2409": [3000.0] * 4}, index=DATES)
    dm = _FuturesDM(pd.DataFrame(), factors, infos)
    dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)

    engine, _ = _run(str(tmp_path), dm, list(infos))

    assert engine.tracker is not None
    old = engine.tracker.get_position("IH2406")
    new = engine.tracker.get_position("IH2409")
    assert old is not None and old.quantity == 0
    assert new is not None and new.quantity == 1
    # 换月守恒：新旧名义相等（同一价 3000 × 300）
    assert new.notional_value == pytest.approx(1 * 3000.0 * 300.0)


# ---------------------------------------------------------------------------
# Golden：4 例闭式手算
# ---------------------------------------------------------------------------

_CLOSED_FORM = {
    "S1": {
        "nav": [1_000_000.0, 1_000_000.0, 1_015_000.0, 1_003_000.0],
        "trades": 1,
        "derivation": (
            "day1 open 1 手@3000，margin=90,000，NAV=1,000,000；"
            "day2 settle 3050 → pnl=+15,000，NAV=1,015,000；"
            "day3 settle 3010 → pnl=-12,000，NAV=1,003,000"
        ),
    },
    "S2": {
        "nav": [1_000_000.0, 1_000_000.0, 985_000.0, 997_000.0],
        "trades": 1,
        "derivation": (
            "空头 1 手@3000（股票开关关闭，期货天然双向），margin=90,000；"
            "day2 settle 3050 → pnl=-15,000；day3 settle 3010 → pnl=+12,000"
        ),
    },
    "S3": {
        "nav": [1_000_000.0, 880_000.0, 880_000.0, 880_000.0],
        "trades": 2,
        "derivation": (
            "空头 1 手@3000，r=0.9 → margin=900,000，cash=100,000；"
            "day2 settle 3400 → pnl=-120,000、margin=918,000 → cash=-38,000 <0，NAV=880,000；"
            "day3 open 3400 强平平仓 → realized=0，cash=margin=880,000"
        ),
    },
    "S4": {
        "nav": [1_000_000.0, 1_000_000.0, 1_000_000.0, 1_003_000.0],
        "trades": 3,
        "derivation": (
            "day1 open IH2406@3000；day2（06-03）触发换月 → day3 平旧开新（同价 3000，名义守恒）；"
            "day3 settle IH2409@3010 → +3,000"
        ),
    },
}


def _build_case(case_id: str, tmpdir: str):
    if case_id in ("S1", "S2"):
        info = {"IH2406": AssetInfo(AssetType.FUTURE, 300.0, 0.1, expiry_date="2026-12-18")}
        factor_value = 1.0 if case_id == "S1" else -1.0
        factors = pd.DataFrame({"IH2406": [factor_value] * 4}, index=DATES)
        open_frame = pd.DataFrame({"IH2406": [3000.0] * 4}, index=DATES)
        close_frame = pd.DataFrame({"IH2406": [3000.0, 3000.0, 3050.0, 3010.0]}, index=DATES)
        dm = _FuturesDM(pd.DataFrame(), factors, info)
        dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)
        # 期货天然双向：股票负持仓开关保持默认 False
        return _run(tmpdir, dm, ["IH2406"])

    if case_id == "S3":
        info = {"IH2406": AssetInfo(AssetType.FUTURE, 300.0, 0.9, expiry_date="2026-12-18")}
        # 因子在强平后归零：避免同一信号反复重建空头（trades 固定为 2）
        factors = pd.DataFrame({"IH2406": [-1.0, -1.0, 0.0, 0.0]}, index=DATES)
        open_frame = pd.DataFrame({"IH2406": [3000.0, 3000.0, 3400.0, 3400.0]}, index=DATES)
        close_frame = pd.DataFrame({"IH2406": [3000.0, 3400.0, 3400.0, 3400.0]}, index=DATES)
        dm = _FuturesDM(pd.DataFrame(), factors, info)
        dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)
        return _run(tmpdir, dm, ["IH2406"])

    infos = {
        "IH2406": AssetInfo(
            AssetType.FUTURE,
            300.0,
            0.1,
            expiry_date="2026-06-05",
            roll_days_before_expiry=2,
            roll_target="IH2409",
        ),
        "IH2409": AssetInfo(AssetType.FUTURE, 300.0, 0.1, expiry_date="2026-09-18"),
    }
    factors = pd.DataFrame(
        {"IH2406": [1.0, 1.0, 1.0, 1.0], "IH2409": [0.0, 0.0, 0.0, 0.0]}, index=DATES
    )
    open_frame = pd.DataFrame({"IH2406": [3000.0] * 4, "IH2409": [3000.0] * 4}, index=DATES)
    close_frame = pd.DataFrame(
        {"IH2406": [3000.0] * 4, "IH2409": [3000.0, 3000.0, 3010.0, 3010.0]}, index=DATES
    )
    dm = _FuturesDM(pd.DataFrame(), factors, infos)
    dm.get_adj_price = lambda kind, adj: (open_frame if kind == "open" else close_frame)
    return _run(tmpdir, dm, list(infos))


@pytest.mark.parametrize("case_id", sorted(_CLOSED_FORM))
def test_golden_p050(case_id, tmp_path):
    """golden 4 例：NAV 闭式值 + 交易笔数（容差 1e-6 元）。"""
    engine, results = _build_case(case_id, str(tmp_path))
    series = results["portfolio_value"]
    assert len(series) == 4
    expected = _CLOSED_FORM[case_id]
    for actual, want in zip(series.tolist(), expected["nav"]):
        assert actual == pytest.approx(want, abs=1e-6), _CLOSED_FORM[case_id]["derivation"]

    assert engine.executor is not None
    trades = engine.executor.trade_log.get_trades()
    assert len(trades) == expected["trades"]

    # 基线文件与闭式值同源（存在即校验，缺失不阻断）
    path = GOLDEN_DIR / f"{case_id}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["nav"]["last"] == pytest.approx(expected["nav"][-1], abs=1e-6)
        assert payload["trades"]["count"] == expected["trades"]
