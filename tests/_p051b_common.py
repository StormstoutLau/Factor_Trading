# tests/_p051b_common.py（下划线前缀：不匹配 test_*.py，不被 pytest 收集）
from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import MarketView, StrategyState

DATES = pd.bdate_range("2024-01-02", periods=140)
CODES = ["000001", "600000", "000002"]


def make_view(
    *,
    closes: np.ndarray,
    prices: dict[str, float] | None = None,
    positions: dict[str, float] | None = None,
    with_history: bool = True,
    codes: list[str] | None = None,
) -> tuple[MarketView, StrategyState]:
    codes = CODES if codes is None else codes
    frame = pd.DataFrame(closes, index=DATES[: len(closes)], columns=codes)
    history = (
        {
            "close": frame,
            "high": frame * 1.05,
            "low": frame * 0.95,
        }
        if with_history
        else None
    )
    date = frame.index[-1]
    price_map = (
        prices if prices is not None else {code: float(frame[code].iloc[-1]) for code in codes}
    )
    view = MarketView(
        date=date,
        signal=pd.Series(1.0, index=codes),
        tradable=pd.Series(True, index=codes),
        prices=pd.Series(price_map, dtype=float),
        returns=None,
        history=history,
    )
    state = StrategyState(as_of=str(date.date()), positions=positions or {}, extras={})
    return view, state
