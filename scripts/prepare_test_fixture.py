#!/usr/bin/env python3
"""生成测试夹具（data/test_ashare，7 个 pkl）

边界（RESEARCH_ci_test_env R2）：
- 只生成 tests/ 现行校验所需的最小字段（7 个 pkl），不生成 st/mktcap/factor。
- 不复用 examples/demo.py::generate_synthetic_data：后者会产生变动复权因子
  （违反 test_03_adj_factor_identity 的 adj≡1.0 断言），且日期起点固定 2022-01-04。
- 不读外部数据源（prepare_test_data.py 依赖 E:\\Ashare_data，仅作本地真实数据重建）。

用法：
    python scripts/prepare_test_fixture.py                    # 生成 baseline 到默认目录
    python scripts/prepare_test_fixture.py --out-dir <dir>     # 指定目录
    python scripts/prepare_test_fixture.py --force             # 覆盖已有 pkl
    python scripts/prepare_test_fixture.py --profile biased    # 生成偏差夹具（6 股 × 60 日）

profile：
    baseline（默认）—— data/test_ashare，7 个 pkl，逐字节稳定（27 项既有数据测试依赖）。
    biased        —— data/test_fixture_biased，8 个 pkl（含 st）+ universe/{list_date,delist}.csv
                     + manifest.json；提供非 1 复权 / ST / 板块 / 退市 / 停牌样本。

退出码：0 成功；1 参数非法；2 目标已存在且未 --force。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "test_ashare"
DEFAULT_BIASED_DIR = REPO_ROOT / "data" / "test_fixture_biased"

BIASED_CODES = ("000001", "300001", "688001", "830001", "430001", "600001")
BIASED_DAYS = 60

TARGET_FILES = (
    "close.pkl",
    "open.pkl",
    "high.pkl",
    "low.pkl",
    "stock_adj.pkl",
    "suspend.pkl",
    "industry.pkl",
)

BIASED_EXTRA_FILES = ("st.pkl",)

MIN_STOCKS = 31  # strict test_04 取 col_idx=30
MIN_DAYS = 51  # strict test_04 取 day_idx=50


def _resolve_out_dir(raw: str) -> Path:
    """相对路径按仓库根解析（不按 cwd），绝对路径原样返回。"""
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def existing_targets(out_dir: Path, extra: tuple[str, ...] = ()) -> list[Path]:
    """返回 out_dir 下已存在的目标 pkl（只读）。"""
    return [out_dir / name for name in TARGET_FILES + extra if (out_dir / name).exists()]


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


def generate_biased_fixture(out_dir: Path, seed: int = 42, start: str = "2024-01-02") -> list[Path]:
    """生成偏差夹具（6 股 × 60 日 + universe 快照），返回写入路径列表。"""
    rng = np.random.default_rng(seed)
    n_days = BIASED_DAYS
    n_stocks = len(BIASED_CODES)
    dates = pd.bdate_range(start, periods=n_days)
    codes = list(BIASED_CODES)

    log_ret = rng.normal(0.0, 0.012, (n_days, n_stocks))
    log_ret = np.clip(log_ret, -0.04, 0.04)
    log_ret[0] = 0.0
    close = 20.0 * np.exp(np.cumsum(log_ret, axis=0))

    # 300001 第 31 个交易日（0-based 30）10 送 10：原始价减半、adj 由 1 → 2
    split_idx = 30
    close[split_idx:, 1] *= 0.5

    noise = rng.uniform(0.997, 1.003, (n_days, n_stocks))
    open_ = np.roll(close, 1, axis=0) * noise
    open_[0] = close[0] * rng.uniform(0.997, 1.003, n_stocks)
    high = np.maximum(open_, close) * rng.uniform(1.0, 1.015, (n_days, n_stocks))
    low = np.minimum(open_, close) * rng.uniform(0.985, 1.0, (n_days, n_stocks))

    adj = np.ones((n_days, n_stocks))
    adj[split_idx:, 1] = 2.0
    adj[:, 2] = 1.0 + 0.01 * np.arange(n_days)  # 688001 逐日递增

    st = np.zeros((n_days, n_stocks), dtype=int)
    st[20:41, 5] = 1  # 600001 在 20~40 为 ST

    suspend = np.zeros((n_days, n_stocks), dtype=int)
    suspend[10:13, 3] = 1  # 830001 停牌 10~12

    frames = {
        "close.pkl": close,
        "open.pkl": open_,
        "high.pkl": high,
        "low.pkl": low,
        "stock_adj.pkl": adj,
        "suspend.pkl": suspend,
        "industry.pkl": np.ones((n_days, n_stocks), dtype=int),
        "st.pkl": st,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, arr in frames.items():
        path = out_dir / name
        pd.DataFrame(arr, index=dates, columns=codes).to_pickle(path)
        written.append(path)

    universe_dir = out_dir / "universe"
    universe_dir.mkdir(parents=True, exist_ok=True)
    list_date_path = universe_dir / "list_date.csv"
    delist_path = universe_dir / "delist.csv"
    pd.DataFrame({"stock": ["430001"], "list_date": [dates[15].strftime("%Y-%m-%d")]}).to_csv(
        list_date_path, index=False
    )
    pd.DataFrame(
        {
            "stock": ["000001"],
            "delist_date": [dates[50].strftime("%Y-%m-%d")],
            "delist_return": [-0.10],
        }
    ).to_csv(delist_path, index=False)

    digest = hashlib.sha256()
    for path in sorted(written) + [list_date_path, delist_path]:
        digest.update(path.read_bytes())
    manifest = {
        "source": "fixture",
        "rows": int(n_days * n_stocks),
        "sha256": digest.hexdigest(),
        "schema_version": "1.0",
    }
    (universe_dir / "manifest.json").write_text(
        pd.Series(manifest).to_json(force_ascii=False, indent=2), encoding="utf-8"
    )
    return written + [list_date_path, delist_path, universe_dir / "manifest.json"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成测试夹具（baseline: data/test_ashare；biased: data/test_fixture_biased）"
    )
    parser.add_argument(
        "--profile",
        choices=("baseline", "biased"),
        default="baseline",
        help="夹具 profile（默认 baseline，逐字节不变）",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="输出目录；相对路径按仓库根解析（默认按 profile 选择）",
    )
    parser.add_argument("--n-stocks", type=int, default=50, help="股票数（下限 31）")
    parser.add_argument("--n-days", type=int, default=100, help="交易日数（下限 51）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--start", default="2024-01-02", help="起始日期（ISO）")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 pkl")
    args = parser.parse_args(argv)

    try:
        pd.bdate_range(args.start, periods=1)
    except (ValueError, TypeError) as exc:
        print(f"error: invalid --start: {exc}", file=sys.stderr)
        return 1

    if args.profile == "baseline":
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
        out_dir = _resolve_out_dir(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
        existing = existing_targets(out_dir)
        generator = lambda: generate_fixture(  # noqa: E731
            out_dir, args.n_stocks, args.n_days, args.seed, args.start
        )
    else:
        out_dir = _resolve_out_dir(args.out_dir) if args.out_dir else DEFAULT_BIASED_DIR
        existing = existing_targets(out_dir, BIASED_EXTRA_FILES)
        generator = lambda: generate_biased_fixture(out_dir, args.seed, args.start)  # noqa: E731

    if existing and not args.force:
        print(
            f"error: fixture already exists in {out_dir}; use --force to overwrite:",
            file=sys.stderr,
        )
        for path in existing:
            print(f"  {path.name}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    written = generator()
    elapsed = time.perf_counter() - started

    print(f"fixture written to {out_dir} in {elapsed:.3f}s")
    for path in written:
        if path.suffix == ".pkl":
            df = pd.read_pickle(path)
            print(f"  {path.name}: {df.shape}")
        else:
            print(f"  {path.relative_to(out_dir)}")
    total_bytes = sum(path.stat().st_size for path in written)
    print(f"  total bytes: {total_bytes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
