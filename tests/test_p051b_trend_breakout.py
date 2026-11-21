"""P-051b T 组：trend_breakout 突破/跌破分支。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from _p051b_common import DATES
from core.strategy import MarketView, StrategyState


def _view(close, high, low, price, *, positions=None):
    idx = DATES[: len(close)]
    code = ["000001"]
    close_frame = pd.DataFrame({"000001": close}, index=idx)
    history = {
        "close": close_frame,
        "high": pd.DataFrame({"000001": high}, index=idx),
        "low": pd.DataFrame({"000001": low}, index=idx),
    }
    view = MarketView(
        date=idx[-1],
        signal=pd.Series(1.0, index=code),
        tradable=pd.Series(True, index=code),
        prices=pd.Series({"000001": price}, dtype=float),
        returns=None,
        history=history,
    )
    state = StrategyState(as_of=str(idx[-1].date()), positions=positions or {}, extras={})
    return view, state


def _run(view, state):
    from strategies.trend import TrendBreakoutConfig, TrendBreakoutStrategy

    return TrendBreakoutStrategy(TrendBreakoutConfig()).generate_signals(view, state)


def test_t1_breakout_enters():
    close = np.full(60, 10.0)
    view, state = _view(close, np.full(60, 10.0), np.full(60, 9.0), 11.0)
    assert _run(view, state).to_dict() == {"000001": 1.0}


def test_t2_below_channel_high_rejects():
    close = np.full(60, 10.0)
    view, state = _view(close, np.full(60, 11.0), np.full(60, 9.0), 10.5)
    assert _run(view, state).empty


def test_t3_holding_exits_below_channel_low():
    close = np.full(60, 10.0)
    view, state = _view(close, np.full(60, 10.0), np.full(60, 9.0), 8.5, positions={"000001": 0.5})
    assert _run(view, state).empty


def test_t4_holding_keeps_above_channel_low():
    close = np.full(60, 10.0)
    view, state = _view(close, np.full(60, 10.0), np.full(60, 9.0), 9.5, positions={"000001": 0.5})
    assert _run(view, state).to_dict() == {"000001": 1.0}


def test_t5_pure_function():
    close = np.full(60, 10.0)
    view, state = _view(close, np.full(60, 10.0), np.full(60, 9.0), 11.0)
    pd.testing.assert_series_equal(_run(view, state), _run(view, state))
