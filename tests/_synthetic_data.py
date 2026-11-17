"""P-042 合成数据夹具（B4）：生成完整的最小 pkl 数据集。

仅测试使用；不写 ``universe/``（缺失走降级快照，不参与指纹）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.config import BacktestConfig

FACTOR_FILE = "factor_value.pkl"


def build_synthetic_dataset(
    tmp_path: Path,
    n_dates: int = 20,
    n_stocks: int = 5,
    seed: int = 42,
) -> Path:
    """写入价格 / 辅助 / 因子 pkl，返回数据目录。"""
    rng = np.random.default_rng(seed)
    data_dir = Path(tmp_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    codes = [f"S{i:03d}" for i in range(n_stocks)]

    returns = rng.normal(0.0, 0.01, size=(n_dates, n_stocks))
    close = 10.0 * np.exp(np.cumsum(returns, axis=0))
    close_df = pd.DataFrame(close, index=dates, columns=codes)
    open_df = close_df * (1.0 + rng.normal(0.0, 0.002, size=close_df.shape))
    high_df = pd.DataFrame(
        np.maximum(close_df.values, open_df.values) * 1.005, index=dates, columns=codes
    )
    low_df = pd.DataFrame(
        np.minimum(close_df.values, open_df.values) * 0.995, index=dates, columns=codes
    )
    adj_df = pd.DataFrame(1.0, index=dates, columns=codes)
    zero_df = pd.DataFrame(0, index=dates, columns=codes)
    industry_df = pd.DataFrame(
        np.tile(np.arange(n_stocks) % 4, (n_dates, 1)), index=dates, columns=codes
    )
    mktcap_df = pd.DataFrame(
        rng.uniform(1e9, 1e10, size=(n_dates, n_stocks)), index=dates, columns=codes
    )

    # 因子：3 个月度截面，首日故意晚于交易日首日（验证 asof 对齐）
    factor_dates = pd.DatetimeIndex([dates[5], dates[12], dates[-1]])
    factor_df = pd.DataFrame(
        rng.normal(0.0, 1.0, size=(len(factor_dates), n_stocks)),
        index=factor_dates,
        columns=codes,
    )

    files = {
        "close.pkl": close_df,
        "open.pkl": open_df,
        "high.pkl": high_df,
        "low.pkl": low_df,
        "stock_adj.pkl": adj_df,
        "suspend.pkl": zero_df,
        "st.pkl": zero_df,
        "industry.pkl": industry_df,
        "mktcap.pkl": mktcap_df,
        FACTOR_FILE: factor_df,
    }
    for name, frame in files.items():
        frame.to_pickle(data_dir / name)
    return data_dir


def build_synthetic_config(data_dir: Path) -> BacktestConfig:
    """返回指向合成数据的配置（因子 + 市值均显式开启）。"""
    return BacktestConfig(
        data_dir=Path(data_dir),
        factor_files=[FACTOR_FILE],
        mktcap_file="mktcap.pkl",
    )
