"""股票池快照生成脚本（P-012 D5 / T-10）。

默认**离线**：只读本地 ``list_date.csv`` / ``delist.csv`` 并重写 ``manifest.json``。
网络刷新必须显式 ``--refresh``（Tushare 优先，AKShare 回退）；无 token / 无网络时
退出码 0 并打印 ``--from-csv`` 替代路径，不写空文件冒充成功。

用法::

    python scripts/fetch_universe.py --recompute-hash
    python scripts/fetch_universe.py --from-csv path/to/csv_dir
    python scripts/fetch_universe.py --refresh
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
DEFAULT_UNIVERSE_DIR = Path("data/universe")

logger = logging.getLogger(__name__)


def _sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _count_rows(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def write_manifest(directory: Path, source: str) -> int:
    """读本地 CSV 并重写 manifest；CSV 缺失时不写文件、返回 0。"""
    list_path = directory / "list_date.csv"
    delist_path = directory / "delist.csv"
    if not list_path.exists() or not delist_path.exists():
        print(
            f"[skip] 未找到 {list_path} / {delist_path}；"
            "请用 --from-csv <目录> 导入本地 CSV，或 --refresh 联网生成"
        )
        return 0

    payload = {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "rows": _count_rows(list_path) + _count_rows(delist_path),
        "sha256": _sha256([list_path, delist_path]),
        "schema_version": SCHEMA_VERSION,
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] manifest 已写入: {directory / 'manifest.json'} (rows={payload['rows']})")
    return 0


def copy_from_csv(source_dir: Path, directory: Path) -> int:
    """从本地目录导入两个 CSV，再重写 manifest。"""
    if not source_dir.is_dir():
        print(f"[skip] --from-csv 目录不存在: {source_dir}")
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("list_date.csv", "delist.csv"):
        origin = source_dir / name
        if not origin.exists():
            print(f"[skip] 缺少 {origin}")
            return 0
        shutil.copy2(origin, directory / name)
    return write_manifest(directory, source="from-csv")


def refresh(directory: Path) -> int:
    """显式联网刷新：Tushare 优先，AKShare 回退；失败不写空文件。"""
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        try:
            import tushare as ts  # type: ignore[import-not-found]

            pro = ts.pro_api(token)
            frame = pro.stock_basic(
                exchange="",
                list_status="L,D,P",
                fields="ts_code,symbol,name,list_date,delist_date",
            )
            return _write_from_frame(frame, directory, source="tushare")
        except Exception as exc:  # noqa: BLE001 - 网络/SDK 失败均回退
            print(f"[warn] Tushare 拉取失败，回退 AKShare: {exc}")

    try:
        import akshare as ak  # type: ignore[import-not-found]

        sh = ak.stock_info_sh_delist()
        sz = ak.stock_info_sz_delist()
        import pandas as pd

        frame = pd.concat([sh, sz], ignore_index=True)
        return _write_from_frame(frame, directory, source="akshare")
    except ImportError:
        print(
            "[skip] 未安装 tushare/akshare 或未设置 TUSHARE_TOKEN；"
            "可改用 --from-csv <目录> 提供本地 CSV 后 --recompute-hash"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            f"[skip] AKShare 拉取失败: {exc}；"
            "可改用 --from-csv <目录> 提供本地 CSV 后 --recompute-hash"
        )
        return 0


def _write_from_frame(frame, directory: Path, source: str) -> int:
    """把外部行情元数据转成 list_date.csv / delist.csv。"""
    import pandas as pd

    if frame is None or len(frame) == 0:
        print("[skip] 外部数据为空，不写文件")
        return 0

    columns = {str(col): col for col in frame.columns}
    code_col = next(
        (columns[key] for key in ("symbol", "代码", "公司代码", "证券代码") if key in columns),
        None,
    )
    list_col = next(
        (columns[key] for key in ("list_date", "上市日期", "上市时间") if key in columns),
        None,
    )
    delist_col = next(
        (columns[key] for key in ("delist_date", "终止上市日期", "退市日期") if key in columns),
        None,
    )
    if code_col is None or list_col is None:
        print("[skip] 外部数据缺少代码/上市日期列，不写文件")
        return 0

    codes = frame[code_col].astype(str).str.split(".").str[-1].str.zfill(6)
    list_dates = pd.to_datetime(frame[list_col], errors="coerce")
    list_rows = pd.DataFrame({"stock": codes, "list_date": list_dates}).dropna(subset=["list_date"])
    list_rows["list_date"] = list_rows["list_date"].dt.strftime("%Y-%m-%d")

    delist_rows = pd.DataFrame(columns=["stock", "delist_date", "delist_return"])
    if delist_col is not None:
        delisted = pd.to_datetime(frame[delist_col], errors="coerce")
        mask = delisted.notna()
        delist_rows = pd.DataFrame(
            {
                "stock": codes[mask],
                "delist_date": delisted[mask].dt.strftime("%Y-%m-%d"),
                "delist_return": float("nan"),
            }
        )

    directory.mkdir(parents=True, exist_ok=True)
    list_rows.to_csv(directory / "list_date.csv", index=False)
    delist_rows.to_csv(directory / "delist.csv", index=False)
    return write_manifest(directory, source=source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="股票池快照生成（默认离线）")
    parser.add_argument(
        "--universe-dir",
        type=Path,
        default=DEFAULT_UNIVERSE_DIR,
        help=f"快照输出目录（默认 {DEFAULT_UNIVERSE_DIR}）",
    )
    parser.add_argument(
        "--recompute-hash",
        action="store_true",
        help="离线：读本地 CSV 重算 sha256/rows 并重写 manifest",
    )
    parser.add_argument(
        "--from-csv",
        type=Path,
        default=None,
        help="从指定目录复制 list_date.csv / delist.csv 后再重写 manifest",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="显式联网刷新（Tushare 优先 / AKShare 回退）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    directory: Path = args.universe_dir

    if args.refresh:
        return refresh(directory)
    if args.from_csv is not None:
        return copy_from_csv(args.from_csv, directory)
    # 默认离线：等价 --recompute-hash
    return write_manifest(directory, source="local")


if __name__ == "__main__":
    sys.exit(main())
