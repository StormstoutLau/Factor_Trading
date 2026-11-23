"""P-046b BL / HRP 优化器手动基准（无断言、不写文件、不进 CI）。

用法：``.venv\\Scripts\\python.exe scripts/p046b_bench_optimizers.py``
口径：DESIGN §11 / IMPL §3.11；固定 seed，打印耗时供人工回归对比。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.portfolio import (
    black_litterman_posterior,
    correlation_distance,
    estimate_cov,
    quasi_diagonal_order,
    recursive_bisection,
)

SIZES = (50, 200, 500)
N_OBS = 60
SEED = 42
N_VIEWS = 5


def _make_returns(n_assets: int, n_obs: int = N_OBS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = rng.normal(0.0, 0.01, size=(n_obs, n_assets))
    return pd.DataFrame(data, columns=[f"S{i:04d}" for i in range(n_assets)])


def _bench_cov(returns: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    cov = estimate_cov(returns, method="sample")
    return cov, time.perf_counter() - start


def _bench_hrp(cov: pd.DataFrame) -> float:
    start = time.perf_counter()
    dist = correlation_distance(cov)
    order = quasi_diagonal_order(dist)
    weights = recursive_bisection(cov, order)
    _ = float(weights.sum())
    return time.perf_counter() - start


def _bench_bl(cov: pd.DataFrame) -> float:
    n = len(cov)
    w_eq = np.full(n, 1.0 / n)
    prior = pd.Series(3.0 * cov.to_numpy(dtype=float) @ w_eq, index=cov.index)
    views = {str(cov.index[i]): float(prior.iloc[i]) + 0.01 for i in range(min(N_VIEWS, n))}
    start = time.perf_counter()
    post = black_litterman_posterior(cov, prior, views)
    _ = float(post.sum())
    return time.perf_counter() - start


def main() -> None:
    print(f"P-046b bench: sizes={SIZES}, n_obs={N_OBS}, seed={SEED}, views={N_VIEWS}")
    for n_assets in SIZES:
        returns = _make_returns(n_assets)
        cov, t_cov = _bench_cov(returns)
        t_hrp = _bench_hrp(cov)
        t_bl = _bench_bl(cov)
        print(f"N={n_assets:>4}  cov={t_cov:8.4f}s  hrp={t_hrp:8.4f}s  bl={t_bl:8.4f}s")


if __name__ == "__main__":
    main()
