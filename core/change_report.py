"""六层归因：层 dump 与两次运行差分（P-012 D6 / T-2）。

本模块只做数据结构、写盘与校验，**不 import engine**（避免循环依赖）。
层文件格式见 DESIGN_p012 §6.1；差分报告契约见 §6.2。
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

SCHEMA_VERSION = "1.0"
RESIDUAL_TOL = 1e-8

LAYER_FILES = (
    "L1_limit_mask.csv",
    "L2_tradable.csv",
    "L3_target_positions.json",
    "L4_orders.json",
    "L5_fills.json",
    "L6_nav.csv",
)

NAV_COLUMNS = ("date", "cash", "market_value", "total_value")


class MissingLayerError(FileNotFoundError):
    """层文件缺失，残差无法计算。"""


def _fmt_date(value: Any) -> str:
    return str(pd.Timestamp(value).strftime("%Y-%m-%d"))


@dataclass
class LayerDiff:
    """单层差分结果。"""

    layer: str
    changed: int = 0
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "changed": self.changed,
            "added": self.added[:5],
            "removed": self.removed[:5],
        }


@dataclass
class NavDiff:
    """净值差分。"""

    before: float
    after: float
    diff: float


@dataclass
class ChangeReport:
    """两次运行的六层差分报告。"""

    before_run: str
    after_run: str
    nav: NavDiff
    layers: list[LayerDiff]
    nav_recomputed: float
    residual: float
    attribution_complete: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "before_run": self.before_run,
            "after_run": self.after_run,
            "nav": {
                "before": self.nav.before,
                "after": self.nav.after,
                "diff": self.nav.diff,
            },
            "layers": [layer.to_dict() for layer in self.layers],
            "nav_recomputed": self.nav_recomputed,
            "residual": self.residual,
            "attribution_complete": self.attribution_complete,
        }


class LayerDumper:
    """按日记录六层快照。

    ``out_dir=None`` 时**完全禁用**：不建目录、不写文件、零 I/O（DESIGN I8）。
    """

    def __init__(self, out_dir: Path | str | None):
        self.out_dir: Optional[Path] = Path(out_dir) if out_dir else None
        self._l1: list[dict[str, Any]] = []
        self._l2: list[dict[str, Any]] = []
        self._l3: dict[str, list[str]] = {}
        self._l4: dict[str, list[dict[str, Any]]] = {}
        self._l6: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return self.out_dir is not None

    def setup(self) -> None:
        if self.enabled:
            assert self.out_dir is not None
            self.out_dir.mkdir(parents=True, exist_ok=True)

    def record_targets(self, date: Any, stocks: Iterable[str]) -> None:
        """记录 L3 目标持仓（仅目标数量 > 0 的标的）。"""
        if not self.enabled:
            return
        self._l3[_fmt_date(date)] = sorted(str(stock) for stock in stocks)

    def record_orders(self, date: Any, orders: Iterable[Any]) -> None:
        """记录 L4 订单（当日创建）。"""
        if not self.enabled:
            return
        rows: list[dict[str, Any]] = []
        for order in orders:
            side = getattr(order, "side", None)
            rows.append(
                {
                    "stock": str(getattr(order, "stock", "")),
                    "side": getattr(side, "name", str(side)),
                    "qty": int(getattr(order, "quantity", 0)),
                    "reason": str(getattr(order, "reason", "rebalance")),
                }
            )
        if rows:
            self._l4.setdefault(_fmt_date(date), []).extend(rows)

    def dump_day(
        self,
        date: Any,
        limit_buy: Optional[pd.Series],
        limit_sell: Optional[pd.Series],
        buyable: Optional[pd.Series],
        sellable: Optional[pd.Series],
        nav: dict[str, float],
    ) -> None:
        """记录单日 L1/L2（仅受限单元格）与 L6。"""
        if not self.enabled:
            return
        day = _fmt_date(date)

        if limit_buy is not None:
            for stock, can_buy in limit_buy.items():
                can_sell = bool(limit_sell.get(stock, True)) if limit_sell is not None else True
                if not bool(can_buy) or not can_sell:
                    self._l1.append(
                        {
                            "date": day,
                            "stock": str(stock),
                            "can_buy": bool(can_buy),
                            "can_sell": can_sell,
                        }
                    )

        if buyable is not None:
            for stock, ok_buy in buyable.items():
                ok_sell = bool(sellable.get(stock, True)) if sellable is not None else True
                if not bool(ok_buy) or not ok_sell:
                    self._l2.append(
                        {
                            "date": day,
                            "stock": str(stock),
                            "buyable": bool(ok_buy),
                            "sellable": ok_sell,
                        }
                    )

        self._l6.append(
            {
                "date": day,
                "cash": float(nav.get("cash", 0.0)),
                "market_value": float(nav.get("market_value", 0.0)),
                "total_value": float(nav.get("total_value", 0.0)),
            }
        )

    def finalize(self, trades_df: Optional[pd.DataFrame] = None) -> None:
        """落盘六层文件（未启用时零 I/O）。"""
        if not self.enabled:
            return
        assert self.out_dir is not None
        self.setup()

        pd.DataFrame(self._l1, columns=["date", "stock", "can_buy", "can_sell"]).to_csv(
            self.out_dir / "L1_limit_mask.csv", index=False
        )
        pd.DataFrame(self._l2, columns=["date", "stock", "buyable", "sellable"]).to_csv(
            self.out_dir / "L2_tradable.csv", index=False
        )
        (self.out_dir / "L3_target_positions.json").write_text(
            json.dumps(self._l3, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.out_dir / "L4_orders.json").write_text(
            json.dumps(self._l4, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        fills: dict[str, list[dict[str, Any]]] = {}
        if trades_df is not None and not trades_df.empty:
            for row in trades_df.to_dict("records"):
                side = row["side"]
                if hasattr(side, "name"):
                    side = side.name
                fills.setdefault(_fmt_date(row["date"]), []).append(
                    {
                        "stock": str(row["stock"]),
                        "side": str(side),
                        "qty": int(row["quantity"]),
                        "price": float(row["price"]),
                        "cost": float(row["cost"]),
                    }
                )
        (self.out_dir / "L5_fills.json").write_text(
            json.dumps(fills, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        pd.DataFrame(self._l6, columns=list(NAV_COLUMNS)).to_csv(
            self.out_dir / "L6_nav.csv", index=False
        )


def _require(path: Path) -> Path:
    if not path.exists():
        raise MissingLayerError(f"缺少层文件: {path}")
    return path


def _read_long(path: Path, value_columns: tuple[str, ...]) -> dict[tuple[str, str], tuple]:
    df = pd.read_csv(path)
    result: dict[tuple[str, str], tuple] = {}
    for row in df.to_dict("records"):
        key = (str(row["date"]), str(row["stock"]))
        result[key] = tuple(bool(row[column]) for column in value_columns)
    return result


def _diff_long(
    layer: str,
    before: dict[tuple[str, str], tuple],
    after: dict[tuple[str, str], tuple],
    default: tuple,
) -> LayerDiff:
    changed = 0
    added: list[str] = []
    removed: list[str] = []
    for key in set(before) | set(after):
        if before.get(key, default) != after.get(key, default):
            changed += 1
            label = f"{key[0]}:{key[1]}"
            if key not in before:
                added.append(label)
            elif key not in after:
                removed.append(label)
    return LayerDiff(layer, changed, sorted(added), sorted(removed))


def _read_json(path: Path) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return raw


def _diff_sets(layer: str, before: set, after: set) -> LayerDiff:
    return LayerDiff(
        layer,
        changed=len(before ^ after),
        added=sorted(str(item) for item in after - before),
        removed=sorted(str(item) for item in before - after),
    )


def _flatten_targets(data: dict) -> set[tuple[str, str]]:
    return {(str(day), str(stock)) for day, stocks in data.items() for stock in stocks}


def _flatten_rows(data: dict, keys: tuple[str, ...]) -> dict[tuple, int]:
    counts: dict[tuple, int] = {}
    for day, rows in data.items():
        for row in rows:
            key = [str(day)]
            for name in keys:
                value = row.get(name)
                if isinstance(value, float):
                    value = round(value, 6)
                key.append(value)
            item = tuple(key)  # type: ignore[arg-type]
            counts[item] = counts.get(item, 0) + 1
    return counts


def _diff_counters(layer: str, before: dict[tuple, int], after: dict[tuple, int]) -> LayerDiff:
    left = Counter(before)
    right = Counter(after)
    changed = sum((left - right).values()) + sum((right - left).values())
    added = [":".join(str(part) for part in key) for key in (right - left)]
    removed = [":".join(str(part) for part in key) for key in (left - right)]
    return LayerDiff(layer, changed, sorted(added), sorted(removed))


def _read_nav(path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(path)
    return [
        {
            "date": str(row["date"]),
            "cash": float(row["cash"]),
            "market_value": float(row["market_value"]),
            "total_value": float(row["total_value"]),
        }
        for row in df.to_dict("records")
    ]


def _diff_nav(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> LayerDiff:
    before_map = {row["date"]: row for row in before}
    after_map = {row["date"]: row for row in after}
    changed = 0
    added: list[str] = []
    removed: list[str] = []
    for day in set(before_map) | set(after_map):
        left = before_map.get(day)
        right = after_map.get(day)
        if left is None:
            changed += 1
            added.append(day)
        elif right is None:
            changed += 1
            removed.append(day)
        else:
            if (
                abs(left["cash"] - right["cash"]) > 1e-9
                or abs(left["market_value"] - right["market_value"]) > 1e-9
                or abs(left["total_value"] - right["total_value"]) > 1e-9
            ):
                changed += 1
    return LayerDiff("L6_nav", changed, sorted(added), sorted(removed))


def _cash_flow(fills: dict) -> float:
    flow = 0.0
    for rows in fills.values():
        for row in rows:
            amount = float(row["price"]) * int(row["qty"])
            cost = float(row.get("cost", 0.0))
            side = str(row.get("side", "")).upper()
            if side.startswith("B"):
                flow -= amount + cost
            else:
                flow += amount - cost
    return flow


def compare_runs(before_dir: Path | str, after_dir: Path | str) -> ChangeReport:
    """对比两次运行的六层 dump，返回 ChangeReport。

    ``nav_recomputed`` = 末行市值 + (首行现金 + L5 现金流)；
    ``residual`` = |nav_recomputed - 末行 total_value|，检验 L5→L6 现金一致性。
    """
    before = Path(before_dir)
    after = Path(after_dir)

    paths = {}
    for layer_file in LAYER_FILES:
        paths[layer_file] = (_require(before / layer_file), _require(after / layer_file))

    l1 = _diff_long(
        "L1_limit_mask",
        _read_long(paths["L1_limit_mask.csv"][0], ("can_buy", "can_sell")),
        _read_long(paths["L1_limit_mask.csv"][1], ("can_buy", "can_sell")),
        default=(True, True),
    )
    l2 = _diff_long(
        "L2_tradable",
        _read_long(paths["L2_tradable.csv"][0], ("buyable", "sellable")),
        _read_long(paths["L2_tradable.csv"][1], ("buyable", "sellable")),
        default=(True, True),
    )
    l3 = _diff_sets(
        "L3_target_positions",
        _flatten_targets(_read_json(paths["L3_target_positions.json"][0])),
        _flatten_targets(_read_json(paths["L3_target_positions.json"][1])),
    )
    l4 = _diff_counters(
        "L4_orders",
        _flatten_rows(_read_json(paths["L4_orders.json"][0]), ("stock", "side", "qty")),
        _flatten_rows(_read_json(paths["L4_orders.json"][1]), ("stock", "side", "qty")),
    )
    l5 = _diff_counters(
        "L5_fills",
        _flatten_rows(_read_json(paths["L5_fills.json"][0]), ("stock", "side", "qty", "price")),
        _flatten_rows(_read_json(paths["L5_fills.json"][1]), ("stock", "side", "qty", "price")),
    )
    before_nav = _read_nav(paths["L6_nav.csv"][0])
    after_nav = _read_nav(paths["L6_nav.csv"][1])
    l6 = _diff_nav(before_nav, after_nav)

    layers = [l1, l2, l3, l4, l5, l6]

    first_cash = after_nav[0]["cash"] if after_nav else 0.0
    last_market_value = after_nav[-1]["market_value"] if after_nav else 0.0
    last_total_value = after_nav[-1]["total_value"] if after_nav else 0.0
    nav_recomputed = (
        last_market_value + first_cash + _cash_flow(_read_json(paths["L5_fills.json"][1]))
    )
    residual = abs(nav_recomputed - last_total_value)

    counts = {layer.layer: layer.changed for layer in layers}
    chain = (
        ("L6_nav", "L5_fills"),
        ("L5_fills", "L4_orders"),
        ("L4_orders", "L3_target_positions"),
        ("L3_target_positions", "L2_tradable"),
        ("L2_tradable", "L1_limit_mask"),
    )
    attribution_complete = all(
        not (counts[upper] > 0 and counts[lower] == 0) for upper, lower in chain
    )

    nav_before = before_nav[-1]["total_value"] if before_nav else 0.0
    nav_after = last_total_value

    return ChangeReport(
        before_run=str(before),
        after_run=str(after),
        nav=NavDiff(before=nav_before, after=nav_after, diff=nav_after - nav_before),
        layers=layers,
        nav_recomputed=nav_recomputed,
        residual=residual,
        attribution_complete=attribution_complete,
    )
