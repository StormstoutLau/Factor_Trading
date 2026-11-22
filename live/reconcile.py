"""三级对账 + parity 评估与连续降级（P-053 D7）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:  # F-I4：运行期零内部依赖（LedgerSnapshot 仅注解；未用的 FillRecord import 已删）
    from live.ledger import LedgerSnapshot


class BreakLevel(str, Enum):
    OK = "ok"
    DUST = "dust"
    MISSED = "missed"
    UNRESOLVED = "unresolved"


_SEVERITY = {
    BreakLevel.OK: 0,
    BreakLevel.DUST: 1,
    BreakLevel.MISSED: 2,
    BreakLevel.UNRESOLVED: 3,
}


@dataclass(frozen=True)
class ReconcileConfig:
    dust_pct: float = 0.001
    dust_abs_quantity: float = 100.0
    cash_dust_pct_nav: float = 0.0001
    cash_dust_abs: float = 1.0


@dataclass(frozen=True)
class ParityConfig:
    cash_pct_nav: float = 0.0001
    weight_l1: float = 1e-4
    slippage_bps_liquid: float = 10.0
    slippage_bps_illiquid: float = 30.0
    fill_rate_min: float = 0.95
    degrade_days: int = 2


@dataclass(frozen=True)
class Break:
    kind: str  # position | cash | missing_fill | extra_fill
    asset: str
    local: float
    remote: float
    delta: float
    level: BreakLevel
    note: str = ""


@dataclass(frozen=True)
class ReconcileReport:
    as_of: float
    breaks: tuple[Break, ...]
    level: BreakLevel
    checked: int


@dataclass(frozen=True)
class ParityReport:
    cash_delta_pct_nav: float
    weight_l1: float
    slippage_bps: float
    fill_rate: float
    breaches: tuple[str, ...]


def classify_quantity(
    delta: float, remote: float, *, config: ReconcileConfig, explained: bool
) -> BreakLevel:
    if abs(delta) <= 1e-12:
        return BreakLevel.OK
    if abs(delta) <= max(config.dust_abs_quantity, config.dust_pct * abs(remote)):
        return BreakLevel.DUST
    if explained:
        return BreakLevel.MISSED
    return BreakLevel.UNRESOLVED


def reconcile_positions(
    local: dict[str, float],
    remote: dict[str, float],
    *,
    config: ReconcileConfig,
    nav: float = 0.0,
    explained: frozenset[str] = frozenset(),
) -> ReconcileReport:
    breaks: list[Break] = []
    for asset in sorted(set(local) | set(remote)):
        lo, ro = local.get(asset, 0.0), remote.get(asset, 0.0)
        level = classify_quantity(lo - ro, ro, config=config, explained=asset in explained)
        if level is not BreakLevel.OK:
            breaks.append(Break("position", asset, lo, ro, lo - ro, level))
    return ReconcileReport(
        0.0, tuple(breaks), overall_level_breaks(breaks), len(set(local) | set(remote))
    )


def reconcile_cash(
    local: float, remote: float, *, config: ReconcileConfig, nav: float
) -> ReconcileReport:
    delta = local - remote
    if abs(delta) <= 1e-12:
        level = BreakLevel.OK
    elif abs(delta) <= max(config.cash_dust_abs, config.cash_dust_pct_nav * abs(nav)):
        level = BreakLevel.DUST
    else:
        level = BreakLevel.UNRESOLVED
    breaks = () if level is BreakLevel.OK else (Break("cash", "CASH", local, remote, delta, level),)
    return ReconcileReport(0.0, breaks, level, 1)


def reconcile_fills(local_keys: set[str], remote_keys: set[str]) -> ReconcileReport:
    breaks: list[Break] = []
    for key in sorted(remote_keys - local_keys):  # 柜台有、本地缺 → 可补录
        breaks.append(Break("missing_fill", key, 0.0, 1.0, -1.0, BreakLevel.MISSED, key))
    for key in sorted(local_keys - remote_keys):  # 本地有、柜台无 → 入账缺口
        breaks.append(Break("extra_fill", key, 1.0, 0.0, 1.0, BreakLevel.UNRESOLVED, key))
    return ReconcileReport(
        0.0, tuple(breaks), overall_level_breaks(breaks), len(local_keys | remote_keys)
    )


def overall_level(reports: Iterable[ReconcileReport]) -> BreakLevel:
    worst = BreakLevel.OK
    for rep in reports:
        if _SEVERITY[rep.level] > _SEVERITY[worst]:
            worst = rep.level
    return worst


def overall_level_breaks(breaks: Iterable[Break]) -> BreakLevel:
    worst = BreakLevel.OK
    for brk in breaks:
        if _SEVERITY[brk.level] > _SEVERITY[worst]:
            worst = brk.level
    return worst


def evaluate_parity(
    paper: LedgerSnapshot,
    live: LedgerSnapshot,
    *,
    nav: float,
    slippage_bps: float,
    fill_rate: float,
    liquid: bool,
    config: ParityConfig,
) -> ParityReport:
    nav = max(abs(nav), 1e-9)
    cash_pct = abs(paper.cash - live.cash) / nav
    pw = {p.asset: p.quantity * p.avg_cost / nav for p in paper.positions}
    lw = {p.asset: p.quantity * p.avg_cost / nav for p in live.positions}
    l1 = sum(abs(pw.get(a, 0.0) - lw.get(a, 0.0)) for a in set(pw) | set(lw))
    breaches: list[str] = []
    if cash_pct > config.cash_pct_nav:
        breaches.append("cash")
    if l1 > config.weight_l1:
        breaches.append("weight")
    if slippage_bps > (config.slippage_bps_liquid if liquid else config.slippage_bps_illiquid):
        breaches.append("slippage")
    if fill_rate < config.fill_rate_min:
        breaches.append("fill_rate")
    return ParityReport(cash_pct, l1, slippage_bps, fill_rate, tuple(breaches))


def should_degrade(reports: Sequence[tuple[str, ParityReport]], *, config: ParityConfig) -> bool:
    """按日升序取尾部连续 breach 天数(ID)，≥ degrade_days 即降级（F-D8）。

    F-R5-9（Step 10）：改为**仅尾部连续**语义（与 docstring 一致）——历史中段的
    2 连不再闩锁 True，中断（clean 日）后重新计数。
    """
    streak = 0
    for _day, rep in sorted(reports, key=lambda item: item[0]):
        if rep.breaches:
            streak += 1
        else:
            streak = 0
    return streak >= config.degrade_days
