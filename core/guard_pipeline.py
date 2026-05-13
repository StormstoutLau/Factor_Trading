"""
Guard Pipeline — 前置安全检查管道

借鉴 OpenAlice 设计:
- 订单到达执行器前，通过可配置的 guard chain 进行安全检查
- Guards 本身不接触账户，只检查 GuardContext
- 支持动态启用/禁用，可配置参数

Guards:
- MaxPositionGuard: 单票持仓上限检查
- CooldownGuard: 调仓冷却期检查
- DrawdownGuard: 回撤止损检查
- SymbolWhitelistGuard: 交易标的白名单
- TurnoverGuard: 日换手率上限检查
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardContext:
    """Guard 检查的上下文"""

    # 当前操作
    action: str  # 'BUY' | 'SELL'
    symbol: str
    quantity: float
    price: float
    order_value: float

    # 账户状态
    current_positions: dict[str, float]  # symbol -> quantity
    current_weights: dict[str, float]  # symbol -> weight
    portfolio_value: float
    cash: float

    # 历史状态
    trade_history: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)

    # 配置参数（guard 可能需要）
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardResult:
    """Guard 检查结果"""

    passed: bool
    guard_name: str
    message: str = ""
    severity: str = "error"  # 'error' | 'warning'


class Guard(ABC):
    """Guard 基类"""

    def __init__(self, name: str, enabled: bool = True, config: Optional[dict[str, Any]] = None):
        self.name = name
        self.enabled = enabled
        self.config = config or {}

    @abstractmethod
    def check(self, ctx: GuardContext) -> GuardResult:
        """执行检查，返回结果"""
        pass

    def __call__(self, ctx: GuardContext) -> GuardResult:
        if not self.enabled:
            return GuardResult(passed=True, guard_name=self.name, message="Guard disabled")
        return self.check(ctx)


# ==================== Concrete Guards ====================


class MaxPositionGuard(Guard):
    """
    单票持仓上限检查

    防止单只股票持仓超过组合的一定比例
    """

    def __init__(self, max_weight: float = 0.1, enabled: bool = True):
        super().__init__("MaxPositionGuard", enabled, {"max_weight": max_weight})
        self.max_weight = max_weight

    def check(self, ctx: GuardContext) -> GuardResult:
        if ctx.action != "BUY":
            return GuardResult(passed=True, guard_name=self.name)

        current_weight = ctx.current_weights.get(ctx.symbol, 0.0)
        new_value = current_weight * ctx.portfolio_value + ctx.order_value
        new_weight = new_value / ctx.portfolio_value if ctx.portfolio_value > 0 else 0

        if new_weight > self.max_weight:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Position weight for {ctx.symbol} would exceed "
                f"{self.max_weight:.1%} (current={current_weight:.1%}, "
                f"new={new_weight:.1%})",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


class CooldownGuard(Guard):
    """
    调仓冷却期检查

    防止对同一只股票过于频繁交易
    """

    def __init__(self, cooldown_days: int = 5, enabled: bool = True):
        super().__init__("CooldownGuard", enabled, {"cooldown_days": cooldown_days})
        self.cooldown_days = cooldown_days

    def check(self, ctx: GuardContext) -> GuardResult:
        if not ctx.trade_history:
            return GuardResult(passed=True, guard_name=self.name)

        cutoff = datetime.now() - timedelta(days=self.cooldown_days)

        recent_trades = [
            t
            for t in ctx.trade_history
            if t.get("symbol") == ctx.symbol and t.get("timestamp", datetime.min) > cutoff
        ]

        if recent_trades:
            last_trade = max(recent_trades, key=lambda t: t.get("timestamp", datetime.min))
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Cooldown active for {ctx.symbol}: "
                f"last trade {last_trade.get('timestamp')} "
                f"(cooldown={self.cooldown_days} days)",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


class DrawdownGuard(Guard):
    """
    回撤止损检查

    当组合回撤超过阈值时，禁止新开仓（只允许平仓）
    """

    def __init__(self, max_drawdown: float = 0.15, enabled: bool = True):
        super().__init__("DrawdownGuard", enabled, {"max_drawdown": max_drawdown})
        self.max_drawdown = max_drawdown

    def check(self, ctx: GuardContext) -> GuardResult:
        if ctx.action != "BUY" or not ctx.equity_curve:
            return GuardResult(passed=True, guard_name=self.name)

        # Calculate current drawdown
        values = [v for _, v in ctx.equity_curve]
        if not values:
            return GuardResult(passed=True, guard_name=self.name)

        peak = max(values)
        current = values[-1]
        drawdown = (peak - current) / peak if peak > 0 else 0

        if drawdown > self.max_drawdown:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Max drawdown exceeded: {drawdown:.1%} > {self.max_drawdown:.1%}. "
                "New positions blocked.",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


class SymbolWhitelistGuard(Guard):
    """
    交易标的白名单

    只允许交易白名单内的股票
    """

    def __init__(self, whitelist: Optional[list[str]] = None, enabled: bool = False):
        super().__init__("SymbolWhitelistGuard", enabled)
        self.whitelist = set(whitelist or [])

    def check(self, ctx: GuardContext) -> GuardResult:
        if not self.enabled or not self.whitelist:
            return GuardResult(passed=True, guard_name=self.name)

        if ctx.symbol not in self.whitelist:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Symbol {ctx.symbol} not in whitelist",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


class TurnoverGuard(Guard):
    """
    日换手率上限检查

    防止单日交易过于频繁
    """

    def __init__(self, max_daily_turnover: float = 0.5, enabled: bool = True):
        super().__init__("TurnoverGuard", enabled, {"max_daily_turnover": max_daily_turnover})
        self.max_daily_turnover = max_daily_turnover

    def check(self, ctx: GuardContext) -> GuardResult:
        today = datetime.now().date()

        daily_turnover = sum(
            t.get("value", 0)
            for t in ctx.trade_history
            if t.get("timestamp", datetime.min).date() == today
        )

        new_turnover = daily_turnover + ctx.order_value
        turnover_ratio = new_turnover / ctx.portfolio_value if ctx.portfolio_value > 0 else 0

        if turnover_ratio > self.max_daily_turnover:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Daily turnover would exceed {self.max_daily_turnover:.1%}: "
                f"{turnover_ratio:.1%}",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


class MinCashGuard(Guard):
    """
    最低现金保留检查

    确保交易后保留最低现金比例
    """

    def __init__(self, min_cash_ratio: float = 0.05, enabled: bool = True):
        super().__init__("MinCashGuard", enabled, {"min_cash_ratio": min_cash_ratio})
        self.min_cash_ratio = min_cash_ratio

    def check(self, ctx: GuardContext) -> GuardResult:
        if ctx.action != "BUY":
            return GuardResult(passed=True, guard_name=self.name)

        remaining_cash = ctx.cash - ctx.order_value
        min_cash = ctx.portfolio_value * self.min_cash_ratio

        if remaining_cash < min_cash:
            return GuardResult(
                passed=False,
                guard_name=self.name,
                message=f"Insufficient cash reserve: remaining={remaining_cash:,.0f}, "
                f"required={min_cash:,.0f}",
                severity="error",
            )

        return GuardResult(passed=True, guard_name=self.name)


# ==================== Guard Pipeline ====================


class GuardPipeline:
    """
    Guard 管道

    串联多个 Guard，按顺序执行检查
    任一 Guard 失败则整个管道失败
    """

    def __init__(self, guards: Optional[list[Guard]] = None):
        self.guards = guards or []

    def add(self, guard: Guard) -> GuardPipeline:
        """添加 Guard（链式调用）"""
        self.guards.append(guard)
        return self

    def check(self, ctx: GuardContext) -> list[GuardResult]:
        """
        执行所有 Guard 检查

        Returns:
            所有 Guard 的结果列表
        """
        results = []
        for guard in self.guards:
            result = guard(ctx)
            results.append(result)
            # 严重错误时提前终止
            if not result.passed and result.severity == "error":
                logger.warning(f"Guard blocked: {result.guard_name} - {result.message}")
                break
        return results

    def is_allowed(self, ctx: GuardContext) -> bool:
        """快速检查是否允许执行"""
        results = self.check(ctx)
        return all(r.passed for r in results)

    def get_blocking_reasons(self, ctx: GuardContext) -> list[str]:
        """获取所有阻止原因"""
        results = self.check(ctx)
        return [r.message for r in results if not r.passed]

    @classmethod
    def default(cls) -> GuardPipeline:
        """创建默认 Guard 管道"""
        return cls([
            MaxPositionGuard(max_weight=0.1),
            DrawdownGuard(max_drawdown=0.15),
            MinCashGuard(min_cash_ratio=0.05),
            TurnoverGuard(max_daily_turnover=0.5),
        ])

    @classmethod
    def conservative(cls) -> GuardPipeline:
        """创建保守风格 Guard 管道"""
        return cls([
            MaxPositionGuard(max_weight=0.05),
            DrawdownGuard(max_drawdown=0.10),
            CooldownGuard(cooldown_days=10),
            MinCashGuard(min_cash_ratio=0.10),
            TurnoverGuard(max_daily_turnover=0.3),
        ])

    @classmethod
    def aggressive(cls) -> GuardPipeline:
        """创建激进风格 Guard 管道"""
        return cls([
            MaxPositionGuard(max_weight=0.2),
            DrawdownGuard(max_drawdown=0.25),
            MinCashGuard(min_cash_ratio=0.02),
            TurnoverGuard(max_daily_turnover=1.0),
        ])


# ==================== Integration Helper ====================


def create_guard_context_from_engine(
    engine: Any,
    action: str,
    symbol: str,
    quantity: float,
    price: float,
) -> GuardContext:
    """
    从回测引擎创建 GuardContext

    便于在 engine.py 中集成 GuardPipeline
    """
    tracker = getattr(engine, "tracker", None)
    config = getattr(engine, "config", None)

    positions = {}
    weights = {}
    portfolio_value = getattr(engine, "current_capital", 0)
    cash = portfolio_value

    if tracker:
        positions = {
            s: p.quantity for s, p in getattr(tracker, "positions", {}).items()
        }
        portfolio_value = getattr(tracker, "portfolio_value", portfolio_value)
        cash = getattr(tracker, "cash", cash)

        # Calculate weights
        if portfolio_value > 0:
            for s, qty in positions.items():
                # Approximate weight using current price
                weights[s] = qty * price / portfolio_value

    # Ensure reasonable defaults if engine lacks full state
    if portfolio_value <= 0:
        portfolio_value = 10_000_000.0  # Default assumption
    if cash <= 0:
        cash = portfolio_value

    return GuardContext(
        action=action,
        symbol=symbol,
        quantity=quantity,
        price=price,
        order_value=quantity * price,
        current_positions=positions,
        current_weights=weights,
        portfolio_value=portfolio_value,
        cash=cash,
        trade_history=getattr(engine, "trade_history", []),
        equity_curve=getattr(engine, "equity_curve", []),
        config=config.__dict__ if config else {},
    )
