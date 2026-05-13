"""
多策略并行回测引擎 - 支持多头/空头/中性三种策略同时执行
===========================================================

核心设计思路:
1. 数据层共享: DataManager、UniverseFilter、FactorPipeline 只初始化一次，所有策略共享
2. 策略层隔离: 每个策略有独立的 Optimizer、Trigger、ExecutionSimulator、PositionTracker
3. 向量化计算: 因子处理使用 numpy/pandas 向量化操作，避免 Python 循环
4. 并行化执行: 使用 multiprocessing 并行运行三种策略的回测循环

三种策略定义:
- 多头(Long): select_top=True, 买入因子得分最高的股票
- 空头(Short): select_top=False, 卖出因子得分最低的股票（或买入得分最低的股票做空）
- 中性(Neutral): 同时做多高分股票 + 做空低分股票，市场中性
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from analytics import PerformanceAnalyzer, generate_report
from config import BacktestConfig, OptimizerConfig
from data import DataManager
from execution import ExecutionSimulator
from factor import FactorCombiner, FactorPipeline
from pending import OrderSide, PendingOrderQueue, create_pending_order
from portfolio import BaseOptimizer, EqualWeightOptimizer, build_optimizer
from rebalance import BaseTrigger, build_trigger
from tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter
from agents.strategy_allocator import StrategyAllocationManager

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """策略配置
    
    定义单个策略的配置参数
    """
    name: str = "long"                       # 策略名称: long | short | neutral
    direction: str = "long"                  # 方向: long | short | both
    select_top: bool = True                  # True=选高分, False=选低分
    initial_capital: float = 10_000_000.0    # 初始资金
    target_count: int = 20                   # 目标持股数
    
    # 中性策略特有参数
    long_weight: float = 0.5                 # 多头部分权重
    short_weight: float = 0.5                # 空头部分权重


class StrategyEngine:
    """单策略回测引擎
    
    基于原始的 BacktestEngine 改造，支持独立运行一个策略。
    与多策略引擎共享数据，但拥有独立的执行和跟踪组件。
    """
    
    def __init__(self, 
                 strategy_config: StrategyConfig,
                 base_config: BacktestConfig,
                 data_manager: DataManager,
                 universe_filter: UniverseFilter,
                 composite_signal: pd.DataFrame):
        """初始化策略引擎
        
        Args:
            strategy_config: 策略配置
            base_config: 基础回测配置
            data_manager: 数据管理器（共享）
            universe_filter: 股票池过滤器（共享）
            composite_signal: 复合因子信号（共享，已预处理）
        """
        self.strategy_cfg = strategy_config
        self.base_cfg = base_config
        
        # 共享组件（只读，不修改）
        self.dm = data_manager
        self.universe = universe_filter
        self._composite_signal = composite_signal
        
        # 独立组件（每个策略一份）
        self.optimizer = self._build_strategy_optimizer()
        self.trigger = build_trigger(base_config.rebalance, self.dm.trade_dates)
        self.executor = ExecutionSimulator(base_config.cost)
        self.tracker = PositionTracker(self.dm.n_stocks, strategy_config.initial_capital)
        
        if base_config.enable_pending_orders:
            self.pending_queue = PendingOrderQueue(
                max_pending_days_buy=base_config.max_pending_days_buy,
                max_pending_days_sell=base_config.max_pending_days_sell
            )
        else:
            self.pending_queue = None
        
        # 状态变量
        self._next_day_orders: list[dict] = []
        self._returns_matrix = self.dm.returns.values
        
        logger.info(f"[{strategy_config.name}] 策略引擎初始化完成")
    
    def _build_strategy_optimizer(self) -> BaseOptimizer:
        """构建策略专用优化器
        
        根据策略方向调整优化器配置:
        - 多头: select_top=True, 选高分股票
        - 空头: select_top=False, 选低分股票
        - 中性: 分别构建多头和空头优化器
        """
        # 复制基础配置并修改
        opt_cfg = OptimizerConfig(
            method=self.base_cfg.optimizer.method,
            max_weight=self.base_cfg.optimizer.max_weight,
            min_weight=self.base_cfg.optimizer.min_weight,
            target_count=self.strategy_cfg.target_count,
            select_top=self.strategy_cfg.select_top,
            round_lot=self.base_cfg.optimizer.round_lot,
            cov_method=self.base_cfg.optimizer.cov_method,
            cov_lookback=self.base_cfg.optimizer.cov_lookback
        )
        return build_optimizer(opt_cfg)
    
    def run(self) -> dict[str, Any]:
        """运行策略回测
        
        Returns:
            回测结果
        """
        t0 = time.perf_counter()
        logger.info(f"[{self.strategy_cfg.name}] 开始回测...")
        
        # 主循环
        for i, date in enumerate(self.dm.trade_dates):
            try:
                self._process_trading_day(date, i)
            except Exception as e:
                logger.error(f"[{self.strategy_cfg.name}] 处理交易日 {date} 时发生错误: {e}")
                continue
        
        # 清理过期订单
        if self.pending_queue:
            self.pending_queue.mark_expired(self.dm.trade_dates[-1])
        
        elapsed = time.perf_counter() - t0
        logger.info(f"[{self.strategy_cfg.name}] 回测完成，耗时: {elapsed:.2f}秒")
        
        return self._generate_results()
    
    def _process_trading_day(self, date: pd.Timestamp, date_index: int):
        """处理单个交易日"""
        # 执行次日订单
        if self._next_day_orders:
            self._execute_next_day_orders(date, date_index)
        
        # 处理待执行订单
        if self.pending_queue:
            self._process_pending_orders(date, date_index)
        
        # 检查再平衡
        should_rebalance = self.trigger.should_trigger(
            date,
            signal=self._composite_signal.loc[date] if date in self._composite_signal.index else None,
            portfolio_value=self.tracker.get_total_value()
        )
        
        if should_rebalance:
            logger.info(f"[{self.strategy_cfg.name}] 触发再平衡: {date}")
            self._execute_rebalance(date, date_index)
        
        # 更新持仓市值
        close_prices = self.dm.get_adj_price('close', self.base_cfg.adjustment_type).loc[date]
        self.tracker.update_market_values(date, close_prices)
    
    def _execute_rebalance(self, date: pd.Timestamp, date_index: int):
        """执行再平衡"""
        if date not in self._composite_signal.index:
            return
        
        # 获取因子信号
        daily_signal = self._composite_signal.loc[date]
        
        # 过滤可交易股票
        tradable_mask = self.universe.tradable.loc[date] if date in self.universe.tradable.index else None
        if tradable_mask is not None:
            tradable_stocks = daily_signal[tradable_mask].dropna()
        else:
            tradable_stocks = daily_signal.dropna()
        
        if len(tradable_stocks) == 0:
            logger.warning(f"[{self.strategy_cfg.name}] 日期 {date} 没有可交易股票")
            return
        
        # 中性策略：分别计算多头和空头
        if self.strategy_cfg.direction == "both":
            self._execute_neutral_rebalance(date, date_index, tradable_stocks)
        else:
            self._execute_directional_rebalance(date, date_index, tradable_stocks)
    
    def _execute_directional_rebalance(self, date: pd.Timestamp, date_index: int, 
                                       tradable_stocks: pd.Series):
        """执行方向性策略再平衡（多头或空头）"""
        # 组合优化
        try:
            if date_index >= self.base_cfg.optimizer.cov_lookback:
                start_idx = date_index - self.base_cfg.optimizer.cov_lookback
                returns_data = pd.DataFrame(
                    self._returns_matrix[start_idx:date_index],
                    index=self.dm.trade_dates[start_idx:date_index],
                    columns=self.dm.stock_codes
                )
            else:
                returns_data = None
            
            target_weights = self.optimizer.optimize(tradable_stocks, returns_data)
            
        except Exception as e:
            logger.error(f"[{self.strategy_cfg.name}] 组合优化失败: {e}")
            return
        
        # 计算目标持仓
        self._generate_orders(date, date_index, target_weights)
    
    def _execute_neutral_rebalance(self, date: pd.Timestamp, date_index: int,
                                   tradable_stocks: pd.Series):
        """执行中性策略再平衡
        
        同时做多高分股票和做空低分股票
        """
        # 多头部分：选高分
        long_optimizer = EqualWeightOptimizer(OptimizerConfig(
            method=self.base_cfg.optimizer.method,
            target_count=self.strategy_cfg.target_count,
            select_top=True,
            max_weight=self.base_cfg.optimizer.max_weight
        ))
        
        # 空头部分：选低分
        short_optimizer = EqualWeightOptimizer(OptimizerConfig(
            method=self.base_cfg.optimizer.method,
            target_count=self.strategy_cfg.target_count,
            select_top=False,
            max_weight=self.base_cfg.optimizer.max_weight
        ))
        
        try:
            if date_index >= self.base_cfg.optimizer.cov_lookback:
                start_idx = date_index - self.base_cfg.optimizer.cov_lookback
                returns_data = pd.DataFrame(
                    self._returns_matrix[start_idx:date_index],
                    index=self.dm.trade_dates[start_idx:date_index],
                    columns=self.dm.stock_codes
                )
            else:
                returns_data = None
            
            long_weights = long_optimizer.optimize(tradable_stocks, returns_data)
            short_weights = short_optimizer.optimize(tradable_stocks, returns_data)
            
            # 合并权重：多头为正，空头为负
            combined_weights = pd.Series(0.0, index=tradable_stocks.index)
            for stock, w in long_weights.items():
                combined_weights[stock] = w * self.strategy_cfg.long_weight
            for stock, w in short_weights.items():
                combined_weights[stock] = -w * self.strategy_cfg.short_weight
            
            target_weights = combined_weights
            
        except Exception as e:
            logger.error(f"[{self.strategy_cfg.name}] 中性策略优化失败: {e}")
            return
        
        # 生成订单
        self._generate_orders(date, date_index, target_weights)
    
    def _generate_orders(self, date: pd.Timestamp, date_index: int, 
                        target_weights: pd.Series):
        """生成交易订单"""
        current_value = self.tracker.get_total_value()
        
        # 获取收盘价
        adj_close = self.dm.get_adj_price('close', self.base_cfg.adjustment_type)
        
        target_positions = {}
        for stock, weight in target_weights.items():
            target_value = weight * current_value
            current_position = self.tracker.get_position(stock)
            current_quantity = current_position.quantity if current_position else 0
            
            try:
                if stock in adj_close.columns and date in adj_close.index:
                    close_price = adj_close.loc[date, stock]
                else:
                    continue
            except (KeyError, IndexError):
                continue
            
            if close_price is None or pd.isna(close_price) or close_price <= 0:
                continue
            
            price_ratio = target_value / close_price
            if pd.isna(price_ratio) or np.isinf(price_ratio):
                continue
            
            if self.base_cfg.optimizer.round_lot:
                target_quantity = int(abs(price_ratio) / 100) * 100 * (1 if weight >= 0 else -1)
            else:
                target_quantity = int(price_ratio)
            
            target_positions[stock] = {
                'current_quantity': current_quantity,
                'target_quantity': target_quantity,
                'price': close_price,
                'weight': weight
            }
        
        # 生成订单
        self._generate_rebalance_orders(date, target_positions)
    
    def _generate_rebalance_orders(self, date: pd.Timestamp, target_positions: dict):
        """生成再平衡订单"""
        for stock, position_info in target_positions.items():
            current_qty = position_info['current_quantity']
            target_qty = position_info['target_quantity']
            
            if current_qty == target_qty:
                continue
            
            trade_qty = target_qty - current_qty
            
            if trade_qty > 0:
                order = create_pending_order(stock, OrderSide.BUY, trade_qty, date)
                if self.pending_queue:
                    self.pending_queue.add_order(order)
                else:
                    self._execute_order_next_open(order, date)
            elif trade_qty < 0:
                order = create_pending_order(stock, OrderSide.SELL, abs(trade_qty), date)
                if self.pending_queue:
                    self.pending_queue.add_order(order)
                else:
                    self._execute_order_next_open(order, date)
    
    def _execute_order_next_open(self, order, date: pd.Timestamp):
        """延迟到次日开盘执行"""
        self._next_day_orders.append({
            'order': order,
            'create_date': date
        })
    
    def _execute_next_day_orders(self, date: pd.Timestamp, date_index: int):
        """执行次日开盘订单"""
        if not self._next_day_orders:
            return
        
        try:
            open_prices = self.dm.get_adj_price('open', self.base_cfg.adjustment_type).loc[date]
        except KeyError:
            return
        
        buyable_mask = self.universe.buyable.loc[date] if hasattr(self.universe, 'buyable') else None
        sellable_mask = self.universe.sellable.loc[date] if hasattr(self.universe, 'sellable') else None
        
        executed_count = 0
        failed_orders = []
        
        for order_info in self._next_day_orders:
            order = order_info['order']
            
            if order.side == OrderSide.BUY:
                if buyable_mask is not None and not buyable_mask.get(order.stock, True):
                    failed_orders.append(order_info)
                    continue
            else:
                if sellable_mask is not None and not sellable_mask.get(order.stock, True):
                    failed_orders.append(order_info)
                    continue
            
            if order.stock not in open_prices:
                failed_orders.append(order_info)
                continue
            
            open_price = open_prices[order.stock]
            
            if open_price is None or pd.isna(open_price) or open_price <= 0:
                failed_orders.append(order_info)
                continue
            
            success, trade = self.executor.execute_order(
                order.stock, order.side, order.quantity, date, open_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                executed_count += 1
            else:
                failed_orders.append(order_info)
        
        self._next_day_orders = failed_orders
        
        if executed_count > 0:
            logger.info(f"[{self.strategy_cfg.name}] 次日开盘订单: 成功{executed_count}个")
    
    def _process_pending_orders(self, date: pd.Timestamp, date_index: int):
        """处理待执行订单"""
        if not self.pending_queue:
            return
        
        pending_orders = self.pending_queue.get_pending_orders()
        if not pending_orders:
            return
        
        try:
            open_prices = self.dm.get_adj_price('open', self.base_cfg.adjustment_type).loc[date]
            close_prices = self.dm.get_adj_price('close', self.base_cfg.adjustment_type).loc[date]
        except KeyError:
            return
        
        buyable_mask = self.universe.buyable.loc[date]
        sellable_mask = self.universe.sellable.loc[date]
        
        for order in pending_orders:
            if order.side == OrderSide.BUY:
                if not buyable_mask.get(order.stock, False):
                    continue
            else:
                if not sellable_mask.get(order.stock, False):
                    continue
            
            if order.stock not in open_prices:
                continue
            
            open_price = open_prices[order.stock]
            close_price = close_prices[order.stock] if order.stock in close_prices else None
            
            success, trade = self.executor.execute_pending_order(
                order, date, open_price, close_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                self.pending_queue.mark_executed(order, date, trade.price)
        
        self.pending_queue.mark_expired(date)
    
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        snapshots = self.tracker.get_snapshots()
        trades_df = self.executor.trade_log.get_trades_df()
        
        # 性能分析
        analyzer = PerformanceAnalyzer()
        analyzer.set_data(snapshots, trades_df)
        metrics = analyzer.calculate_performance_metrics()
        
        return {
            'strategy_name': self.strategy_cfg.name,
            'snapshots': snapshots,
            'trades_df': trades_df,
            'metrics': metrics,
            'tracker': self.tracker,
            'executor': self.executor
        }


class MultiStrategyEngine:
    """多策略并行回测引擎
    
    同时运行多头、空头、中性三种策略，共享数据层，并行执行策略层。
    """
    
    def __init__(self, base_config: BacktestConfig):
        """初始化多策略引擎
        
        Args:
            base_config: 基础回测配置
        """
        self.cfg = base_config
        
        # 共享数据层（只初始化一次）
        logger.info("=" * 70)
        logger.info("【多策略引擎】初始化共享数据层")
        logger.info("=" * 70)
        
        t0 = time.perf_counter()
        
        # 1. 数据管理器
        logger.info("  → 加载数据...")
        self.dm = DataManager(base_config)
        
        # 2. 股票池过滤器
        logger.info("  → 构建股票池过滤器...")
        self.universe = UniverseFilter(self.dm, base_config.universe)
        self.universe.build_masks()
        
        # 3. 因子处理与合成
        logger.info("  → 预计算因子信号...")
        self._composite_signal = self._precompute_factors()
        
        elapsed = time.perf_counter() - t0
        logger.info(f"  ✓ 共享数据层初始化完成，耗时: {elapsed:.2f}秒")
        
        # 策略配置
        self.strategy_configs = self._create_strategy_configs()
    
    def _precompute_factors(self) -> pd.DataFrame:
        """预计算因子信号（向量化）"""
        # 加载所有因子
        raw_factors = {}
        for fname in self.cfg.factor_files:
            raw = self.dm.load_factor(fname)
            key = fname.replace(".pkl", "")
            raw_factors[key] = raw
        
        # 创建因子处理管道
        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        # 逐日处理因子（向量化）
        processed_factors = {}
        for factor_name, factor_data in raw_factors.items():
            processed = pipeline.process(factor_data)
            processed_factors[factor_name] = processed
        
        # 合成因子
        composite = combiner.combine(processed_factors)
        
        return composite
    
    def _create_strategy_configs(self, weights: Optional[np.ndarray] = None) -> list[StrategyConfig]:
        """创建三种策略的配置

        Args:
            weights: 资金分配权重 (3,)，如果为None则平均分配
        """
        if weights is None:
            weights = np.ones(3) / 3

        capitals = weights * self.cfg.initial_capital

        return [
            StrategyConfig(
                name="多头策略",
                direction="long",
                select_top=True,
                initial_capital=capitals[0],
                target_count=self.cfg.optimizer.target_count
            ),
            StrategyConfig(
                name="空头策略",
                direction="short",
                select_top=False,
                initial_capital=capitals[1],
                target_count=self.cfg.optimizer.target_count
            ),
            StrategyConfig(
                name="中性策略",
                direction="both",
                select_top=True,
                initial_capital=capitals[2],
                target_count=self.cfg.optimizer.target_count,
                long_weight=0.5,
                short_weight=0.5
            )
        ]
    
    def run_sequential(self) -> dict[str, dict[str, Any]]:
        """串行运行所有策略
        
        Returns:
            各策略回测结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("【多策略引擎】串行执行三种策略")
        logger.info("=" * 70)
        
        results = {}
        total_time = time.perf_counter()
        
        for strategy_cfg in self.strategy_configs:
            engine = StrategyEngine(
                strategy_config=strategy_cfg,
                base_config=self.cfg,
                data_manager=self.dm,
                universe_filter=self.universe,
                composite_signal=self._composite_signal
            )
            results[strategy_cfg.name] = engine.run()
        
        total_elapsed = time.perf_counter() - total_time
        logger.info(f"\n  ✓ 所有策略回测完成，总耗时: {total_elapsed:.2f}秒")
        
        return results
    
    def run_parallel(self, n_workers: int = 3) -> dict[str, dict[str, Any]]:
        """并行运行所有策略
        
        Args:
            n_workers: 并行工作进程数
            
        Returns:
            各策略回测结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("【多策略引擎】并行执行三种策略")
        logger.info("=" * 70)
        
        total_time = time.perf_counter()
        
        # 准备参数
        args_list = [
            (strategy_cfg, self.cfg, self.dm, self.universe, self._composite_signal)
            for strategy_cfg in self.strategy_configs
        ]
        
        # 并行执行
        with mp.Pool(processes=min(n_workers, len(self.strategy_configs))) as pool:
            strategy_results = pool.map(_run_strategy_worker, args_list)
        
        # 整理结果
        results = {}
        for strategy_cfg, result in zip(self.strategy_configs, strategy_results):
            results[strategy_cfg.name] = result
        
        total_elapsed = time.perf_counter() - total_time
        logger.info(f"\n  ✓ 所有策略回测完成，总耗时: {total_elapsed:.2f}秒")
        
        return results
    
    def run_vectorized(self,
                       enable_dynamic_allocation: bool = False,
                       allocator_type: str = 'ftrl',
                       allocator_kwargs: Optional[dict] = None) -> dict[str, Any]:
        """向量化运行所有策略（最高效）

        三种策略共享同一个回测循环，只在组合优化阶段区分方向。
        这是最高效的方式，因为数据IO和因子计算只执行一次。

        Args:
            enable_dynamic_allocation: 是否启用动态资金分配
            allocator_type: 分配器类型 ('hedge', 'ftrl', 'ucb', 'thompson', 'mean_variance')
            allocator_kwargs: 分配器额外参数

        Returns:
            包含各策略回测结果和分配权重的字典
        """
        logger.info("\n" + "=" * 70)
        if enable_dynamic_allocation:
            logger.info("【多策略引擎】向量化执行三种策略（动态资金分配）")
            logger.info(f"  分配器: {allocator_type}")
        else:
            logger.info("【多策略引擎】向量化执行三种策略（固定资金分配）")
        logger.info("=" * 70)

        total_time = time.perf_counter()

        # 初始化动态分配器
        allocator = None
        if enable_dynamic_allocation:
            allocator_kwargs = allocator_kwargs or {}
            allocator = StrategyAllocationManager(
                strategy_names=["多头策略", "空头策略", "中性策略"],
                allocator_type=allocator_type,
                **allocator_kwargs
            )

        # 初始化三个策略引擎
        engines = {}
        for strategy_cfg in self.strategy_configs:
            engines[strategy_cfg.name] = StrategyEngine(
                strategy_config=strategy_cfg,
                base_config=self.cfg,
                data_manager=self.dm,
                universe_filter=self.universe,
                composite_signal=self._composite_signal
            )

        # 跟踪每日各策略收益（用于动态分配）
        strategy_daily_returns = {name: [] for name in engines.keys()}
        prev_values = {name: engine.tracker.get_total_value() for name, engine in engines.items()}

        # 共享回测循环
        for i, date in enumerate(self.dm.trade_dates):
            # 1. 执行次日订单（所有策略）
            for engine in engines.values():
                if engine._next_day_orders:
                    engine._execute_next_day_orders(date, i)

            # 2. 处理待执行订单（所有策略）
            for engine in engines.values():
                if engine.pending_queue:
                    engine._process_pending_orders(date, i)

            # 3. 检查再平衡（所有策略）
            for engine in engines.values():
                should_rebalance = engine.trigger.should_trigger(
                    date,
                    signal=engine._composite_signal.loc[date] if date in engine._composite_signal.index else None,
                    portfolio_value=engine.tracker.get_total_value()
                )

                if should_rebalance:
                    logger.info(f"[{engine.strategy_cfg.name}] 触发再平衡: {date}")
                    engine._execute_rebalance(date, i)

            # 4. 更新持仓市值（所有策略）
            close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
            for engine in engines.values():
                engine.tracker.update_market_values(date, close_prices)

            # 5. 计算各策略当日收益（用于动态分配）
            if enable_dynamic_allocation and i > 0:
                daily_returns = []
                for name, engine in engines.items():
                    current_value = engine.tracker.get_total_value()
                    prev_value = prev_values[name]
                    if prev_value > 0:
                        daily_ret = (current_value - prev_value) / prev_value
                    else:
                        daily_ret = 0.0
                    strategy_daily_returns[name].append(daily_ret)
                    daily_returns.append(daily_ret)
                    prev_values[name] = current_value

                # 更新动态分配权重
                if i >= 10:  # 至少需要10天数据才开始动态调整
                    weights = allocator.update(
                        np.array(daily_returns),
                        date=pd.Timestamp(date).to_pydatetime(),
                        adapt_meta=True
                    )
                    logger.info(f"  [{date}] 动态权重: {dict(zip(engines.keys(), weights.round(4)))}")

        # 生成结果
        results = {}
        for name, engine in engines.items():
            results[name] = engine._generate_results()

        total_elapsed = time.perf_counter() - total_time
        logger.info(f"\n  ✓ 所有策略回测完成，总耗时: {total_elapsed:.2f}秒")

        output = {
            'strategy_results': results,
            'total_elapsed': total_elapsed,
        }

        if enable_dynamic_allocation and allocator:
            output['allocation_manager'] = allocator
            output['weight_history'] = allocator.weight_history
            output['final_weights'] = allocator.get_weights()

        return output

    def run_with_dynamic_allocation(self,
                                    allocator_type: str = 'ftrl',
                                    allocator_kwargs: Optional[dict] = None,
                                    warm_up_days: int = 30) -> dict[str, Any]:
        """运行动态资金分配的多策略回测

        流程:
        1. 先用固定资金运行 warm_up_days 天，收集策略收益历史
        2. 之后每日根据策略表现动态调整资金权重
        3. 权重变化通过调整目标持仓市值实现（不实际转移资金，仅调整再平衡时的目标）

        Args:
            allocator_type: 分配器类型
            allocator_kwargs: 分配器参数
            warm_up_days: 预热期天数

        Returns:
            回测结果字典
        """
        logger.info("\n" + "=" * 70)
        logger.info("【多策略引擎】动态资金分配回测")
        logger.info(f"  分配器: {allocator_type}, 预热期: {warm_up_days}天")
        logger.info("=" * 70)

        total_time = time.perf_counter()

        # 初始化分配器
        allocator_kwargs = allocator_kwargs or {}
        allocator = StrategyAllocationManager(
            strategy_names=["多头策略", "空头策略", "中性策略"],
            allocator_type=allocator_type,
            **allocator_kwargs
        )

        # 初始化策略引擎（初始平均分配）
        engines = {}
        for strategy_cfg in self.strategy_configs:
            engines[strategy_cfg.name] = StrategyEngine(
                strategy_config=strategy_cfg,
                base_config=self.cfg,
                data_manager=self.dm,
                universe_filter=self.universe,
                composite_signal=self._composite_signal
            )

        strategy_names = list(engines.keys())
        n_strategies = len(strategy_names)

        # 跟踪每日净值
        nav_history = {name: [] for name in strategy_names}
        prev_values = {name: engine.tracker.get_total_value() for name, engine in engines.items()}

        # 主回测循环
        for i, date in enumerate(self.dm.trade_dates):
            # 1. 执行次日订单
            for engine in engines.values():
                if engine._next_day_orders:
                    engine._execute_next_day_orders(date, i)

            # 2. 处理待执行订单
            for engine in engines.values():
                if engine.pending_queue:
                    engine._process_pending_orders(date, i)

            # 3. 检查再平衡
            for engine in engines.values():
                should_rebalance = engine.trigger.should_trigger(
                    date,
                    signal=engine._composite_signal.loc[date] if date in engine._composite_signal.index else None,
                    portfolio_value=engine.tracker.get_total_value()
                )

                if should_rebalance:
                    engine._execute_rebalance(date, i)

            # 4. 更新市值
            close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
            for engine in engines.values():
                engine.tracker.update_market_values(date, close_prices)

            # 5. 记录净值并计算收益
            daily_returns = []
            for name in strategy_names:
                current_value = engines[name].tracker.get_total_value()
                nav_history[name].append(current_value)

                if i > 0 and prev_values[name] > 0:
                    daily_ret = (current_value - prev_values[name]) / prev_values[name]
                else:
                    daily_ret = 0.0
                daily_returns.append(daily_ret)
                prev_values[name] = current_value

            # 6. 预热期后启动动态分配
            if i >= warm_up_days:
                weights = allocator.update(
                    np.array(daily_returns),
                    date=pd.Timestamp(date).to_pydatetime(),
                    adapt_meta=True
                )

                # 调整各策略的目标资金规模（通过修改strategy_cfg的initial_capital影响再平衡）
                # 注意：这里不实际转移资金，而是影响下一次再平衡时的目标权重
                total_value = sum(engines[name].tracker.get_total_value() for name in strategy_names)
                for j, name in enumerate(strategy_names):
                    target_capital = total_value * weights[j]
                    # 调整策略引擎的可用资金（通过tracker的cash调整）
                    engines[name].tracker.cash = target_capital - (
                        engines[name].tracker.get_total_value() - engines[name].tracker.get_cash()
                    )

                if i % 20 == 0 or i == len(self.dm.trade_dates) - 1:
                    logger.info(f"  [{date}] 权重: {dict(zip(strategy_names, weights.round(4)))}")

        # 生成结果
        results = {}
        for name, engine in engines.items():
            results[name] = engine._generate_results()

        # 计算组合收益
        portfolio_values = []
        for i in range(len(self.dm.trade_dates)):
            daily_total = sum(nav_history[name][i] for name in strategy_names)
            portfolio_values.append(daily_total)

        portfolio_returns = np.diff(portfolio_values) / portfolio_values[:-1]

        total_elapsed = time.perf_counter() - total_time
        logger.info(f"\n  ✓ 动态分配回测完成，总耗时: {total_elapsed:.2f}秒")

        return {
            'strategy_results': results,
            'portfolio_values': portfolio_values,
            'portfolio_returns': portfolio_returns,
            'portfolio_cumulative_return': (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0],
            'portfolio_sharpe': float(np.mean(portfolio_returns) / (np.std(portfolio_returns) + 1e-8)),
            'allocation_manager': allocator,
            'weight_history': allocator.weight_history,
            'final_weights': allocator.get_weights(),
            'nav_history': nav_history,
            'total_elapsed': total_elapsed,
        }


def _run_strategy_worker(args) -> dict[str, Any]:
    """策略工作进程函数
    
    用于 multiprocessing 并行执行
    """
    strategy_cfg, base_cfg, dm, universe, composite_signal = args
    
    # 在每个进程中重新初始化日志
    logging.basicConfig(level=logging.INFO)
    
    engine = StrategyEngine(
        strategy_config=strategy_cfg,
        base_config=base_cfg,
        data_manager=dm,
        universe_filter=universe,
        composite_signal=composite_signal
    )
    
    return engine.run()
