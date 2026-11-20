"""波动率原语（P-051a）。

设计依据：``docs/DESIGN_p051a_sizing_wiring.md`` D2/D3。

契约：
- 纯函数：无 I/O、无 logging、无随机、无全局状态；
- 仅 ``numpy`` / ``pandas``；异常仅 ``ValueError``（参数/形状非法）；
- 输入 Series → 返回 Series；输入 DataFrame → 返回 DataFrame；
- NaN 一律传播，禁止静默补 0 或 skipna 跳过（D3 F-D3）。

窗口口径（O-P051a-3）：``estimate_volatility`` 的窗口**含当日**
``[t-lookback+1, t]``；与引擎内部 Σ 窗口（不含当日，防前视）不同口径，
策略层接线时须显式对齐。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["TRADING_DAYS", "estimate_volatility", "atr"]

TRADING_DAYS = 252  # A 股年化惯例；不声称一手文献（U-P051a-6）


def _require_positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError(f"{name} 必须为正整数: {value!r}")
    return int(value)


def estimate_volatility(
    returns: pd.Series | pd.DataFrame,
    *,
    lookback: int = 60,
    annualize: bool = True,
    periods: int = TRADING_DAYS,
) -> pd.Series | pd.DataFrame:
    """滚动样本波动率（``ddof=1``）。

    - 输出点 ``t`` 使用行 ``[t-lookback+1, t]``（含当日）；
    - 窗口行数不足 **或窗口内含任一 NaN** → NaN；
    - ``annualize=True`` 时 ``× sqrt(periods)``。
    """
    lookback = _require_positive_int("lookback", lookback)
    periods = _require_positive_int("periods", periods)

    is_series = isinstance(returns, pd.Series)
    frame = returns.to_frame() if is_series else returns
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"returns 必须为 Series 或 DataFrame: {type(returns)!r}")

    rolling = frame.rolling(window=lookback, min_periods=lookback)
    values = rolling.std(ddof=1).where(rolling.count() == lookback)
    if annualize:
        values = values * np.sqrt(float(periods))
    return values.iloc[:, 0] if is_series else values


def atr(
    high: pd.Series | pd.DataFrame,
    low: pd.Series | pd.DataFrame,
    close: pd.Series | pd.DataFrame,
    *,
    period: int = 14,
) -> pd.Series | pd.DataFrame:
    """Wilder ATR（标准口径，D3）。

    ``TR[0] = H-L``；``TR[t] = max(H-L, |H-C_prev|, |L-C_prev|)``；
    ``ATR[period-1] = mean(TR[0..period-1])``（**skipna=False**，任一 NaN → NaN）；
    ``ATR[t] = (ATR[t-1]*(period-1) + TR[t]) / period``；
    前 ``period-1`` 个 bar 为 NaN。
    """
    period = _require_positive_int("period", period)

    is_series = isinstance(high, pd.Series)
    if is_series != isinstance(low, pd.Series) or is_series != isinstance(close, pd.Series):
        raise ValueError("high/low/close 必须同为 Series 或同为 DataFrame")

    h = high.to_frame() if is_series else high
    lo = low.to_frame() if is_series else low
    c = close.to_frame() if is_series else close
    if not isinstance(h, pd.DataFrame) or h.shape != lo.shape or h.shape != c.shape:
        raise ValueError(
            f"high/low/close 形状必须一致: {getattr(h, 'shape', None)}/"
            f"{getattr(lo, 'shape', None)}/{getattr(c, 'shape', None)}"
        )
    if not (h.index.equals(lo.index) and h.index.equals(c.index)):
        raise ValueError("high/low/close 索引必须一致")

    prev_close = c.shift(1).to_numpy(dtype=float)
    high_arr = h.to_numpy(dtype=float)
    low_arr = lo.to_numpy(dtype=float)
    hl = high_arr - low_arr
    tr = np.maximum(np.maximum(np.abs(high_arr - prev_close), np.abs(low_arr - prev_close)), hl)
    if len(tr) > 0:
        tr[0] = hl[0]  # 首日无 C_prev（H/L 为 NaN 时仍为 NaN）

    out = np.full(tr.shape, np.nan, dtype=float)
    if len(tr) >= period:
        out[period - 1] = tr[:period].mean(axis=0)  # numpy mean：NaN → NaN（skipna=False）
        for t in range(period, len(tr)):
            out[t] = (out[t - 1] * (period - 1) + tr[t]) / period

    values = pd.DataFrame(out, index=h.index, columns=h.columns)
    return values.iloc[:, 0] if is_series else values
