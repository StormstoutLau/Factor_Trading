"""动态股票池快照（P-012 D5 / T-8）。

- 落盘格式 CSV + JSON（IMPL F-I3；``pyarrow`` 未声明）；
- 默认目录 ``data_dir/universe``，随 ``data_dir`` 解析（F-I10）；
- 任一 CSV 缺失 → ``status="uncorrected"`` + 单次 warning + 空快照；
- ``manifest.json`` 缺失 → ``manifest=None``，报告 ``data_version="unknown"``。

本模块只依赖 pandas，不 import 引擎（避免循环依赖）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


@dataclass
class UniverseSnapshot:
    """list_date / delist / manifest 的只读快照。"""

    list_date: pd.Series = field(default_factory=lambda: pd.Series(dtype="datetime64[ns]"))
    delist: pd.DataFrame = field(default_factory=pd.DataFrame)
    manifest: Optional[dict[str, Any]] = None
    status: str = "uncorrected"


def load_universe_snapshot(data_dir: Path, universe_dir: Path | None = None) -> UniverseSnapshot:
    """加载快照；两 CSV 齐 → corrected，否则 uncorrected（不中断）。"""
    directory = Path(universe_dir) if universe_dir is not None else Path(data_dir) / "universe"
    list_path = directory / "list_date.csv"
    delist_path = directory / "delist.csv"
    manifest_path = directory / "manifest.json"

    manifest: Optional[dict[str, Any]] = None
    if manifest_path.exists():
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = raw if isinstance(raw, dict) else None
        except (OSError, json.JSONDecodeError):
            logger.warning(f"universe manifest 读取失败: {manifest_path}")

    if not list_path.exists() or not delist_path.exists():
        logger.warning(
            f"未找到 universe 快照（{list_path} / {delist_path}），"
            "survivorship 降级为 uncorrected"
        )
        return UniverseSnapshot(manifest=manifest, status="uncorrected")

    list_frame = pd.read_csv(list_path, dtype={"stock": str})
    list_series = pd.Series(
        pd.to_datetime(list_frame["list_date"], errors="coerce").to_numpy(),
        index=list_frame["stock"].astype(str),
        dtype="datetime64[ns]",
    ).dropna()

    delist = pd.read_csv(delist_path, dtype={"stock": str})
    if "delist_date" in delist.columns:
        delist["delist_date"] = pd.to_datetime(delist["delist_date"], errors="coerce")
    if "delist_return" in delist.columns:
        delist["delist_return"] = pd.to_numeric(delist["delist_return"], errors="coerce")

    return UniverseSnapshot(
        list_date=list_series, delist=delist, manifest=manifest, status="corrected"
    )


def listing_mask(dates: pd.DatetimeIndex, codes: pd.Index, snap: UniverseSnapshot) -> pd.DataFrame:
    """True = 当日已上市且未退市；缺失字段按「不限制」处理。"""
    mask = pd.DataFrame(True, index=dates, columns=codes, dtype=bool)
    if snap.status != "corrected":
        return mask

    delist_map: dict[str, pd.Timestamp] = {}
    if snap.delist is not None and not snap.delist.empty and "delist_date" in snap.delist:
        for stock, delist_date in zip(snap.delist["stock"], snap.delist["delist_date"]):
            parsed = pd.to_datetime(delist_date, errors="coerce")
            if pd.notna(parsed):
                delist_map[str(stock)] = pd.Timestamp(parsed)

    for code in codes:
        if code in snap.list_date.index:
            start = pd.Timestamp(snap.list_date.loc[code])
            mask.loc[mask.index < start, code] = False
        end = delist_map.get(str(code))
        if end is not None:
            mask.loc[mask.index >= end, code] = False
    return mask
