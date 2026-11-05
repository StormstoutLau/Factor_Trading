#!/usr/bin/env python3
"""生成测试夹具（data/test_ashare，7 个 pkl）

边界（RESEARCH_ci_test_env R2）：
- 只生成 tests/ 现行校验所需的最小字段（7 个 pkl），不生成 st/mktcap/factor。
- 不复用 examples/demo.py::generate_synthetic_data：后者会产生变动复权因子
  （违反 test_03_adj_factor_identity 的 adj≡1.0 断言），且日期起点固定 2022-01-04。
- 不读外部数据源（prepare_test_data.py 依赖 E:\\Ashare_data，仅作本地真实数据重建）。

用法：
    python scripts/prepare_test_fixture.py                    # 生成到默认目录
    python scripts/prepare_test_fixture.py --out-dir <dir>     # 指定目录
    python scripts/prepare_test_fixture.py --force             # 覆盖已有 pkl

退出码：0 成功；1 参数非法；2 目标已存在且未 --force。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "test_ashare"

TARGET_FILES = (
    "close.pkl",
    "open.pkl",
    "high.pkl",
    "low.pkl",
    "stock_adj.pkl",
    "suspend.pkl",
    "industry.pkl",
)

MIN_STOCKS = 31  # strict test_04 取 col_idx=30
MIN_DAYS = 51  # strict test_04 取 day_idx=50


def _resolve_out_dir(raw: str) -> Path:
    """相对路径按仓库根解析（不按 cwd），绝对路径原样返回。"""
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def existing_targets(out_dir: Path) -> list[Path]:
    """返回 out_dir 下已存在的目标 pkl（只读）。"""
    return [out_dir / name for name in TARGET_FILES if (out_dir / name).exists()]


def generate_fixture(
    out_dir: Path,
    n_stocks: int = 50,
    n_days: int = 100,
    seed: int = 42,
    start: str = "2024-01-02",
) -> list[Path]:
    """生成 7 个 pkl 并返回写入路径列表（不含覆盖检查）。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_days)
    codes = [f"{i:06d}" for i in range(1, n_stocks + 1)]

    # 价格：GBM 对数收益，clip ±5%（低于 limit_up_threshold 0.095）
    mu = rng.uniform(0.0, 0.0008, n_stocks)
    sigma = rng.uniform(0.012, 0.030, n_stocks)
    log_ret = rng.normal(mu, sigma, (n_days, n_stocks))
    log_ret = np.clip(log_ret, -0.05, 0.05)
    log_ret[0] = 0.0
    p0 = rng.uniform(8.0, 60.0, n_stocks)
    close = p0 * np.exp(np.cumsum(log_ret, axis=0))

    # OHLC 自洽（high >= max(o,c)，low <= min(o,c)）
    noise = rng.uniform(0.995, 1.005, (n_days, n_stocks))
    open_ = np.roll(close, 1, axis=0) * noise
    open_[0] = close[0] * rng.uniform(0.995, 1.005, n_stocks)
    high = np.maximum(open_, close) * rng.uniform(1.0, 1.02, (n_days, n_stocks))
    low = np.minimum(open_, close) * rng.uniform(0.98, 1.0, (n_days, n_stocks))

    frames = {
        "close.pkl": close,
        "open.pkl": open_,
        "high.pkl": high,
        "low.pkl": low,
        "stock_adj.pkl": np.ones_like(close),
        "suspend.pkl": np.zeros((n_days, n_stocks), dtype=int),
        "industry.pkl": np.ones((n_days, n_stocks), dtype=int),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, arr in frames.items():
        path = out_dir / name
        pd.DataFrame(arr, index=dates, columns=codes).to_pickle(path)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成 data/test_ashare 测试夹具（7 个 pkl，CI 与本地可复现）"
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="输出目录；相对路径按仓库根解析（默认 %(default)s）",
    )
    parser.add_argument("--n-stocks", type=int, default=50, help="股票数（下限 31）")
    parser.add_argument("--n-days", type=int, default=100, help="交易日数（下限 51）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--start", default="2024-01-02", help="起始日期（ISO）")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 pkl")
    args = parser.parse_args(argv)

    if args.n_stocks < MIN_STOCKS:
        print(
            f"error: --n-stocks must be >= {MIN_STOCKS} (got {args.n_stocks})",
            file=sys.stderr,
        )
        return 1
    if args.n_days < MIN_DAYS:
        print(
            f"error: --n-days must be >= {MIN_DAYS} (got {args.n_days})",
            file=sys.stderr,
        )
        return 1
    try:
        pd.bdate_range(args.start, periods=1)
    except (ValueError, TypeError) as exc:
        print(f"error: invalid --start: {exc}", file=sys.stderr)
        return 1

    out_dir = _resolve_out_dir(args.out_dir)
    existing = existing_targets(out_dir)
    if existing and not args.force:
        print(
            f"error: fixture already exists in {out_dir}; use --force to overwrite:",
            file=sys.stderr,
        )
        for path in existing:
            print(f"  {path.name}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    written = generate_fixture(out_dir, args.n_stocks, args.n_days, args.seed, args.start)
    elapsed = time.perf_counter() - started

    print(f"fixture written to {out_dir} in {elapsed:.3f}s")
    for path in written:
        df = pd.read_pickle(path)
        print(f"  {path.name}: {df.shape}")
    total_bytes = sum(path.stat().st_size for path in written)
    print(f"  total bytes: {total_bytes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
