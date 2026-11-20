"""持仓跟踪模块 - 基于Backtest_Opus_2.0架构

提供完整的持仓跟踪功能：
- 实时持仓数量跟踪
- 组合总价值计算
- 每日收益计算
- 持仓快照记录
- 风险暴露监控
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from core.config import AssetType
from core.execution import Trade
from core.futures_accounting import (
    ContractSpec,
    MarginModel,
    SettlementResult,
    apply_settlement,
    compute_settlement,
)

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓

    Attributes:
        stock: 股票/资产代码
        quantity: 持仓数量 (有符号: >0 多头, <0 空头, 0 无持仓)
        avg_cost: 平均建仓成本
        market_value: 当前市值
        unrealized_pnl: 浮动盈亏
        realized_pnl: 已实现盈亏
        margin_used: 占用保证金 (仅期货/杠杆交易)
    """

    stock: str
    quantity: float  # 现在支持 float 同时保持兼容
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float = 0.0
    # P-050 期货账目（全部默认值 → 股票路径逐位不变）
    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    notional_value: float = 0.0
    mtm_pnl: float = 0.0
    settle_base: float = 0.0

    @property
    def direction(self) -> int:
        """持仓方向: 1=多头, -1=空头, 0=无持仓"""
        if self.quantity > 1e-10:
            return 1
        elif self.quantity < -1e-10:
            return -1
        else:
            return 0

    @property
    def exposure(self) -> float:
        """风险暴露 = 名义价值（未盯市也非 0，I-P050-10）"""
        return self.notional_value

    def update_market_value(self, price: float) -> None:
        """根据最新价格更新市值和浮动盈亏

        多空盈亏计算公式:
            多头: 未实现盈亏 = quantity * (price - avg_cost)
            空头: 未实现盈亏 = quantity * (price - avg_cost)  # 负数量自动得到正确结果
            期货: 权益 = 保证金 + 相对结算基准的盯市盈亏（D1）
        """
        if self.asset_type == AssetType.FUTURE:
            mult = float(self.multiplier or 1.0)
            self.notional_value = abs(self.quantity) * price * mult
            self.mtm_pnl = (
                self.quantity * (price - self.settle_base) * mult if self.settle_base else 0.0
            )
            self.unrealized_pnl = self.mtm_pnl
            self.market_value = self.margin_used + self.mtm_pnl
            return

        self.market_value = self.quantity * price
        self.unrealized_pnl = self.quantity * (price - self.avg_cost)
        self.notional_value = abs(self.quantity) * price * float(self.multiplier or 1.0)

    def _guard_overfill(self, trade: Trade) -> None:
        """越量守卫（I-P050-9）：不静默翻负/翻多。"""
        side = trade.side.name
        if side == "SELL" and trade.quantity > max(self.quantity, 0.0) + 1e-9:
            raise ValueError(f"SELL 越量: 持有 {self.quantity}, 卖出 {trade.quantity}")
        if side == "BUY_TO_COVER" and trade.quantity > abs(min(self.quantity, 0.0)) + 1e-9:
            raise ValueError(f"BUY_TO_COVER 越量: 持有 {self.quantity}, 买入平仓 {trade.quantity}")
        if side == "SELL_SHORT" and self.quantity > 1e-9:
            raise ValueError(f"SELL_SHORT 越量: 持有多头 {self.quantity}, 开空 {trade.quantity}")
        if side == "BUY" and self.quantity < -1e-9:
            raise ValueError(f"BUY 越量: 持有空头 {self.quantity}, 买入 {trade.quantity}")

    def _execute_futures_trade(self, trade: Trade) -> None:
        """期货数量/结算基准/盈亏（现金与保证金由 tracker 负责）。"""
        side = trade.side.name
        mult = float(self.multiplier or 1.0)
        price = float(trade.price)

        if side in ("BUY", "SELL_SHORT"):
            signed = float(trade.quantity) if side == "BUY" else -float(trade.quantity)
            qty_before = self.quantity
            new_qty = qty_before + signed
            base_before = self.settle_base if abs(qty_before) > 0 else price
            if abs(new_qty) > 0:
                self.settle_base = (abs(qty_before) * base_before + abs(signed) * price) / abs(
                    new_qty
                )
            else:
                self.settle_base = 0.0
            self.quantity = new_qty
            self.avg_cost = self.settle_base
        else:
            closed = min(float(trade.quantity), abs(self.quantity))
            sign = 1.0 if self.quantity > 0 else -1.0
            self.realized_pnl += sign * closed * (price - self.settle_base) * mult - float(
                trade.cost
            )
            self.quantity += -sign * closed
            if abs(self.quantity) < 1e-12:
                self.quantity = 0.0
                self.settle_base = 0.0
                self.avg_cost = 0.0

        self.notional_value = abs(self.quantity) * price * mult
        self.mtm_pnl = (
            self.quantity * (price - self.settle_base) * mult if self.settle_base else 0.0
        )
        self.unrealized_pnl = self.mtm_pnl
        self.market_value = self.margin_used + self.mtm_pnl

    def execute_trade(self, trade: Trade):
        """执行交易，更新持仓

        Args:
            trade: 交易记录
        """
        self._guard_overfill(trade)
        self.asset_type = trade.asset_type
        if trade.multiplier:
            self.multiplier = float(trade.multiplier)

        if self.asset_type == AssetType.FUTURE:
            self._execute_futures_trade(trade)
            return

        if trade.side.name == "BUY":
            # 买入→加多仓（平空仓请使用 BUY_TO_COVER）
            total_cost = self.quantity * self.avg_cost + trade.amount
            total_quantity = self.quantity + trade.quantity
            self.avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
            self.quantity = total_quantity

        elif trade.side.name == "SELL":
            # 卖出→减多仓
            if self.quantity > 0:
                sell_proceeds = trade.quantity * self.avg_cost
                realized_pnl = trade.amount - sell_proceeds - trade.cost
                self.realized_pnl += realized_pnl
                self.quantity -= trade.quantity
                if self.quantity == 0:
                    self.avg_cost = 0
                    self.market_value = 0.0
                    self.unrealized_pnl = 0.0

        elif trade.side.name == "SELL_SHORT":
            # 开空仓
            if self.quantity <= 0:
                total_cost = abs(self.quantity) * self.avg_cost + trade.amount
                total_quantity = abs(self.quantity) + trade.quantity
                self.avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
                self.quantity -= trade.quantity  # 变成负数

        elif trade.side.name == "BUY_TO_COVER":
            # 平空仓
            if self.quantity < 0:
                cover_count = min(trade.quantity, abs(self.quantity))
                realized_pnl = cover_count * (self.avg_cost - trade.price) - trade.cost
                self.realized_pnl += realized_pnl
                self.quantity += trade.quantity
                if self.quantity == 0:
                    self.avg_cost = 0
                    self.market_value = 0.0
                    self.unrealized_pnl = 0.0

        self.notional_value = (
            abs(self.quantity) * float(trade.price) * float(self.multiplier or 1.0)
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "stock": self.stock,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "margin_used": self.margin_used,
            "direction": self.direction,
            "total_pnl": self.unrealized_pnl + self.realized_pnl,
        }


@dataclass
class PortfolioSnapshot:
    """组合快照类"""

    date: pd.Timestamp
    cash: float
    total_value: float
    positions: dict[str, Position]
    daily_return: float
    cumulative_return: float

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "date": self.date,
            "cash": self.cash,
            "total_value": self.total_value,
            "position_count": len([p for p in self.positions.values() if p.quantity > 0]),
            "daily_return": self.daily_return,
            "cumulative_return": self.cumulative_return,
            "positions": {
                stock: pos.to_dict() for stock, pos in self.positions.items() if pos.quantity > 0
            },
        }


class PositionTracker:
    """持仓跟踪器

    负责跟踪持仓变化、计算组合价值和收益。
    """

    def __init__(
        self,
        n_stocks: int,
        initial_capital: float,
        allow_negative_stock_positions: bool = False,
    ):
        """初始化持仓跟踪器

        Args:
            n_stocks: 股票总数
            initial_capital: 初始资金
            allow_negative_stock_positions: 股票负持仓研究模式（默认关，P-050）
        """
        self.n_stocks = n_stocks
        self.initial_capital = initial_capital
        self._allow_negative_stock = bool(allow_negative_stock_positions)
        self._contract_specs: dict[str, ContractSpec] = {}

        # 当前持仓
        self._positions: dict[str, Position] = {}

        # 现金
        self._cash = initial_capital

        # 组合快照历史
        self._snapshots: list[PortfolioSnapshot] = []

        # 前一日总价值（用于计算日收益）
        self._prev_total_value = initial_capital

        # 累计收益
        self._cumulative_return = 0.0

        logger.info("持仓跟踪器初始化完成")

    def set_contract_specs(self, specs: Mapping[str, ContractSpec]) -> None:
        """注入期货合约规格（引擎 setup 调用；空字典 = 纯股票路径）。"""
        self._contract_specs = dict(specs)

    def execute_trade(self, trade: Trade):
        """执行交易，更新持仓

        Args:
            trade: 交易记录
        """
        stock = trade.stock

        if stock not in self._positions:
            self._positions[stock] = Position(
                stock=stock,
                quantity=0,
                avg_cost=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                asset_type=trade.asset_type,
                multiplier=trade.multiplier,
            )
        position = self._positions[stock]

        if trade.asset_type == AssetType.FUTURE:
            self._apply_futures_cash(trade, position)
        else:
            self._apply_stock_cash(trade)

        position.execute_trade(trade)

        logger.debug(
            f"执行交易: {trade.stock} {trade.side.name} {trade.quantity}股, 现金: {self._cash:.2f}"
        )

    def _apply_stock_cash(self, trade: Trade) -> None:
        """股票现金（开关关闭时与既有两分支逐位一致）。"""
        side = trade.side.name
        if side == "BUY":
            self._cash -= trade.net_amount
        elif side == "SELL":
            self._cash += trade.net_amount
        elif side == "SELL_SHORT" and self._allow_negative_stock:
            self._cash += trade.net_amount
        elif side == "BUY_TO_COVER" and self._allow_negative_stock:
            self._cash -= trade.amount + trade.cost

    def _apply_futures_cash(self, trade: Trade, position: Position) -> None:
        """期货现金与保证金：开仓扣保证金；平仓释放保证金 + 结算后盈亏 − 费用。"""
        side = trade.side.name
        mult = float(trade.multiplier or 1.0)
        qty_before = float(position.quantity)

        if side in ("BUY", "SELL_SHORT"):
            spec = self._contract_specs.get(trade.stock)
            ratio = float(getattr(spec, "margin_ratio", 0.0) or 0.0)
            margin_add = abs(float(trade.quantity)) * float(trade.price) * mult * ratio
            position.margin_used += margin_add
            self._cash -= margin_add + float(trade.cost)
            return

        if abs(qty_before) < 1e-12:
            raise ValueError(f"{trade.stock} 无期货持仓，无法平仓 {trade.quantity}")
        closed = min(abs(float(trade.quantity)), abs(qty_before))
        released = position.margin_used * (closed / abs(qty_before))
        position.margin_used -= released
        if abs(position.margin_used) < 1e-9:
            position.margin_used = 0.0
        sign = 1.0 if qty_before > 0 else -1.0
        realized = sign * closed * (float(trade.price) - float(position.settle_base)) * mult
        self._cash += released + realized - float(trade.cost)

    def update_market_values(self, date: pd.Timestamp, prices: pd.Series):
        """更新持仓市值

        Args:
            date: 日期
            prices: 价格数据
        """
        for stock, position in self._positions.items():
            if stock not in prices:
                continue
            price = prices[stock]
            if not pd.notna(price) or price <= 0:
                continue
            if position.asset_type == AssetType.FUTURE:
                if abs(position.quantity) > 1e-12:
                    position.update_market_value(price)
                continue
            if position.quantity > 0 or (self._allow_negative_stock and position.quantity < 0):
                position.update_market_value(price)

        # 记录组合快照
        self._take_snapshot(date)

    def _take_snapshot(self, date: pd.Timestamp):
        """记录组合快照

        Args:
            date: 日期
        """
        total_value = self.get_total_value()

        # 计算日收益
        daily_return = (total_value - self._prev_total_value) / self._prev_total_value

        # 计算累计收益
        self._cumulative_return = (total_value - self.initial_capital) / self.initial_capital

        # 创建快照（P-011 F-S9-1）：逐 Position 复制，避免快照与实时持仓共享可变对象，
        # 否则快照的 market_value/quantity 会被后续调仓、行情更新与强制平仓改写。
        snapshot = PortfolioSnapshot(
            date=date,
            cash=self._cash,
            total_value=total_value,
            positions={stock: replace(position) for stock, position in self._positions.items()},
            daily_return=daily_return,
            cumulative_return=self._cumulative_return,
        )

        self._snapshots.append(snapshot)
        self._prev_total_value = total_value

        logger.debug(f"记录组合快照: {date}, 总价值: {total_value:.2f}, 日收益: {daily_return:.2%}")

    def get_position(self, stock: str) -> Optional[Position]:
        """获取指定股票的持仓

        Args:
            stock: 股票代码

        Returns:
            持仓信息
        """
        return self._positions.get(stock)

    def get_all_positions(self) -> dict[str, Position]:
        """获取所有持仓

        Returns:
            所有持仓信息
        """
        return {
            stock: pos
            for stock, pos in self._positions.items()
            if pos.quantity > 0
            or pos.asset_type == AssetType.FUTURE
            and abs(pos.quantity) > 1e-12
            or (self._allow_negative_stock and pos.quantity < 0)
        }

    def get_total_value(self) -> float:
        """获取组合总价值

        Returns:
            现金 + 持仓市值
        """
        position_value = sum(pos.market_value for pos in self._positions.values())
        return self._cash + position_value

    def get_available_cash(self) -> float:
        """可用资金（P-050 D1：期货为已扣保证金后的余额）。"""
        return self._cash

    def get_total_cash(self) -> float:
        """总现金 = 可用资金 + Σ 占用保证金。"""
        return self._cash + sum(pos.margin_used for pos in self._positions.values())

    def get_cash(self) -> float:
        """获取现金余额

        Returns:
            现金余额
        """
        return self._cash

    def get_position_weights(self, prices: pd.Series) -> pd.Series:
        """获取持仓权重

        Args:
            prices: 价格数据

        Returns:
            持仓权重序列
        """
        total_value = self.get_total_value()
        if total_value <= 0:
            return pd.Series()

        weights = {}
        for stock, position in self._positions.items():
            if position.asset_type == AssetType.FUTURE:
                if abs(position.quantity) > 1e-12:
                    weights[stock] = position.notional_value / total_value
                continue
            if position.quantity > 0 or (self._allow_negative_stock and position.quantity < 0):
                weights[stock] = position.market_value / total_value

        return pd.Series(weights)

    def get_sector_exposure(self, industry_data: pd.Series) -> dict[str, float]:
        """获取行业暴露

        Args:
            industry_data: 行业数据

        Returns:
            行业暴露字典
        """
        sector_exposure: dict[str, float] = {}
        total_value = self.get_total_value()

        if total_value <= 0:
            return sector_exposure

        for stock, position in self._positions.items():
            if stock not in industry_data:
                continue
            if position.asset_type == AssetType.FUTURE:
                if abs(position.quantity) < 1e-12:
                    continue
                value = position.notional_value
            elif position.quantity > 0 or (self._allow_negative_stock and position.quantity < 0):
                value = position.market_value
            else:
                continue
            sector = industry_data[stock]
            if sector not in sector_exposure:
                sector_exposure[sector] = 0.0
            sector_exposure[sector] += value / total_value

        return sector_exposure

    def get_snapshots(self) -> list[PortfolioSnapshot]:
        """获取所有组合快照

        Returns:
            组合快照列表
        """
        return self._snapshots.copy()

    def get_snapshots_df(self) -> pd.DataFrame:
        """获取组合快照DataFrame

        Returns:
            组合快照DataFrame
        """
        if not self._snapshots:
            return pd.DataFrame(
                columns=[
                    "date",
                    "cash",
                    "total_value",
                    "position_count",
                    "daily_return",
                    "cumulative_return",
                ]
            )

        data = []
        for snapshot in self._snapshots:
            data.append(
                {
                    "date": snapshot.date,
                    "cash": snapshot.cash,
                    "total_value": snapshot.total_value,
                    "position_count": len(
                        [p for p in snapshot.positions.values() if p.quantity > 0]
                    ),
                    "daily_return": snapshot.daily_return,
                    "cumulative_return": snapshot.cumulative_return,
                }
            )

        return pd.DataFrame(data)

    def get_performance_metrics(self) -> dict[str, Any]:
        """获取性能指标

        Returns:
            性能指标字典
        """
        if not self._snapshots:
            return {}

        # 提取收益率序列
        daily_returns = [s.daily_return for s in self._snapshots if not pd.isna(s.daily_return)]
        cumulative_returns = [s.cumulative_return for s in self._snapshots]

        if not daily_returns:
            return {}

        # 计算性能指标
        total_return = cumulative_returns[-1] if cumulative_returns else 0

        # 年化收益率（假设252个交易日）
        n_days = len(daily_returns)
        annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0

        # 年化波动率
        annual_volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0

        # 夏普比率（假设无风险利率为0）
        sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0

        # 最大回撤
        cumulative_values = [1 + r for r in cumulative_returns]
        peak = np.maximum.accumulate(cumulative_values)
        drawdown = (peak - cumulative_values) / peak
        max_drawdown = np.max(drawdown) if drawdown.size > 0 else 0

        # 当前持仓统计
        current_positions = self.get_all_positions()
        position_count = len(current_positions)

        # 总盈亏
        total_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in current_positions.values())

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "annual_volatility": annual_volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "current_value": self.get_total_value(),
            "current_cash": self._cash,
            "position_count": position_count,
            "total_pnl": total_pnl,
            "trading_days": n_days,
        }

    def settle(
        self,
        date: pd.Timestamp,
        settlements: Mapping[str, float],
        specs: Optional[Mapping[str, ContractSpec]] = None,
        fallback_prices: Optional[Mapping[str, float]] = None,
        margin_model: Optional[MarginModel] = None,
    ) -> Optional[SettlementResult]:
        """逐日结算（P-050 D2）：盈亏净额入可用资金，重算保证金，重置结算基准。

        Args:
            date: 结算日
            settlements: 当日结算价（权威来源）
            specs: 合约规格；None 用注入的 ``set_contract_specs``
            fallback_prices: 结算价缺失时的回退价（收盘价 proxy）
            margin_model: 保证金模型（默认交易所最低保证金率）

        Returns:
            结算结果；无期货规格或无持仓 → ``None``（股票零开销）；不产生快照。
        """
        spec_map = self._contract_specs if specs is None else specs
        if not spec_map:
            return None

        has_futures = any(
            pos.asset_type == AssetType.FUTURE and abs(pos.quantity) > 1e-12
            for pos in self._positions.values()
        )
        if not has_futures:
            return None

        fallbacks = fallback_prices or {}
        effective: dict[str, float] = {}
        proxy_used = False
        for symbol, position in self._positions.items():
            if position.asset_type != AssetType.FUTURE or abs(position.quantity) < 1e-12:
                continue
            price = settlements.get(symbol)
            if price is None or not pd.notna(price) or float(price) <= 0:
                price = fallbacks.get(symbol)
                if price is None or not pd.notna(price) or float(price) <= 0:
                    continue
                proxy_used = True
            effective[symbol] = float(price)

        result = compute_settlement(self._positions, effective, spec_map, margin_model)
        result = replace(result, date=pd.Timestamp(date), proxy_used=proxy_used)

        margin_prev = sum(pos.margin_used for pos in self._positions.values())
        self._cash, _ = apply_settlement(self._cash, margin_prev, result)

        for symbol, margin in result.margin_after.items():
            pos = self._positions.get(symbol)
            settlement = result.settlements_used.get(symbol)
            if pos is None or settlement is None:
                continue
            pos.settle_base = settlement
            pos.avg_cost = settlement
            pos.margin_used = margin
            pos.mtm_pnl = 0.0
            pos.unrealized_pnl = 0.0
            pos.market_value = margin

        logger.info(
            f"结算 {pd.Timestamp(date).date()}: pnl={result.total_pnl:.2f}, "
            f"margin_delta={result.margin_delta:.2f}, proxy={proxy_used}"
        )
        return result

    def validate_positions(self, prices: pd.Series) -> list[str]:
        """验证持仓数据的一致性

        Args:
            prices: 价格数据

        Returns:
            验证错误列表
        """
        errors = []

        # 检查现金是否为负
        if self._cash < 0:
            errors.append(f"现金余额为负: {self._cash:.2f}")

        # 检查持仓数量是否合理
        for stock, position in self._positions.items():
            if position.asset_type == AssetType.FUTURE:
                if abs(position.quantity) < 1e-12:
                    continue
                expected = position.margin_used + position.mtm_pnl
                if abs(position.market_value - expected) > 1e-6:
                    errors.append(f"{stock}期货权益错误: {position.market_value} vs {expected}")
                continue

            if position.quantity < 0 and not self._allow_negative_stock:
                errors.append(f"{stock}持仓数量为负: {position.quantity}")

            if position.avg_cost <= 0 and position.quantity > 0:
                errors.append(f"{stock}平均成本异常: {position.avg_cost}")

            if stock in prices and position.quantity > 0:
                expected_market_value = position.quantity * prices[stock]
                if abs(position.market_value - expected_market_value) > 0.01:
                    errors.append(
                        f"{stock}市值计算错误: {position.market_value} vs {expected_market_value}"
                    )

        return errors

    def reset(self, initial_capital: float):
        """重置持仓跟踪器

        Args:
            initial_capital: 初始资金
        """
        self._positions.clear()
        self._cash = initial_capital
        self._snapshots.clear()
        self._prev_total_value = initial_capital
        self._cumulative_return = 0.0

        logger.info("持仓跟踪器已重置")
