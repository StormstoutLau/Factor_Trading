"""回测引擎核心 V2 - 插拔式架构

基于依赖注入的解耦设计，所有组件通过接口交互。
支持Mock测试、模块替换和独立升级。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.analytics import generate_report
from core.config import BacktestConfig
from core.data import DataManager
from core.execution import ExecutionSimulator
from core.factor import FactorCombiner, FactorPipeline
from core.interfaces import (
    IDataManager,
    IExecutionSimulator,
    IFactorCombiner,
    IFactorPipeline,
    IOptimizer,
    IPendingOrderQueue,
    IPositionTracker,
    IRebalanceTrigger,
    IUniverseFilter,
)
from core.pending import (
    OrderSide,
    PendingOrderQueue,
    create_pending_order,
    select_fallback_stocks,
)
from core.portfolio import build_optimizer
from core.rebalance import build_trigger
from core.tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter

logger = logging.getLogger(__name__)


class BacktestEngineV2:
    """回测引擎 V2 - 插拔式架构
    
    通过依赖注入实现完全解耦，支持：
    - 独立测试各模块（使用Mock对象）
    - 运行时替换组件实现
    - 第三方模块接入
    
    Example:
        # 方式1: 使用默认组件
        engine = BacktestEngineV2(config)
        engine.setup()
        
        # 方式2: 注入自定义组件
        engine = BacktestEngineV2(
            config,
            data_manager=MyDataManager(config),
            optimizer=MyOptimizer(config.optimizer),
        )
        engine.setup()
        
        # 方式3: 完全自定义
        engine = BacktestEngineV2(
            config,
            data_manager=mock_dm,
            universe_filter=mock_universe,
            factor_pipeline=mock_pipeline,
            optimizer=mock_optimizer,
            trigger=mock_trigger,
            executor=mock_executor,
            tracker=mock_tracker,
        )
        results = engine.run()
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        data_manager: Optional[IDataManager] = None,
        universe_filter: Optional[IUniverseFilter] = None,
        factor_pipeline: Optional[IFactorPipeline] = None,
        factor_combiner: Optional[IFactorCombiner] = None,
        optimizer: Optional[IOptimizer] = None,
        trigger: Optional[IRebalanceTrigger] = None,
        executor: Optional[IExecutionSimulator] = None,
        tracker: Optional[IPositionTracker] = None,
        pending_queue: Optional[IPendingOrderQueue] = None,
    ):
        """初始化回测引擎
        
        Args:
            config: 回测配置
            data_manager: 数据管理器（可选，默认DataManager）
            universe_filter: 股票池过滤器（可选，默认UniverseFilter）
            factor_pipeline: 因子处理管道（可选，默认FactorPipeline）
            factor_combiner: 因子合成器（可选，默认FactorCombiner）
            optimizer: 组合优化器（可选，默认build_optimizer）
            trigger: 再平衡触发器（可选，默认build_trigger）
            executor: 执行模拟器（可选，默认ExecutionSimulator）
            tracker: 持仓跟踪器（可选，默认PositionTracker）
            pending_queue: 待执行订单队列（可选，默认PendingOrderQueue）
        """
        self.cfg = config
        
        # 注入的组件（或None，由setup创建）
        self._injected_dm = data_manager
        self._injected_universe = universe_filter
        self._injected_pipeline = factor_pipeline
        self._injected_combiner = factor_combiner
        self._injected_optimizer = optimizer
        self._injected_trigger = trigger
        self._injected_executor = executor
        self._injected_tracker = tracker
        self._injected_pending_queue = pending_queue
        
        # 实际使用的组件（setup后填充）
        self.dm: Optional[IDataManager] = None
        self.universe: Optional[IUniverseFilter] = None
        self.pipeline: Optional[IFactorPipeline] = None
        self.combiner: Optional[IFactorCombiner] = None
        self.optimizer: Optional[IOptimizer] = None
        self.trigger: Optional[IRebalanceTrigger] = None
        self.executor: Optional[IExecutionSimulator] = None
        self.tracker: Optional[IPositionTracker] = None
        self.pending_queue: Optional[IPendingOrderQueue] = None
        
        # 预计算数据
        self._composite_signal: Optional[pd.DataFrame] = None
        self._returns_matrix: Optional[np.ndarray] = None
        
        logger.info("回测引擎V2初始化完成")
    
    def setup(self):
        """设置回测引擎
        
        根据注入的组件或创建默认组件。
        """
        t0 = time.perf_counter()
        logger.info("开始设置回测引擎V2...")
        
        # 1. 数据管理器
        if self._injected_dm is not None:
            self.dm = self._injected_dm
            logger.info("使用注入的数据管理器")
        else:
            logger.info("创建默认数据管理器...")
            self.dm = DataManager(self.cfg)
        
        # 2. 股票池过滤器
        if self._injected_universe is not None:
            self.universe = self._injected_universe
            logger.info("使用注入的股票池过滤器")
        else:
            logger.info("创建默认股票池过滤器...")
            self.universe = UniverseFilter(self.dm, self.cfg.universe)
        self.universe.build_masks()
        
        # 3. 因子处理管道
        if self._injected_pipeline is not None:
            self.pipeline = self._injected_pipeline
            logger.info("使用注入的因子处理管道")
        else:
            logger.info("创建默认因子处理管道...")
            self.pipeline = FactorPipeline(self.dm, self.cfg.factor)
        
        # 4. 因子合成器
        if self._injected_combiner is not None:
            self.combiner = self._injected_combiner
            logger.info("使用注入的因子合成器")
        else:
            self.combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        self._precompute_factors()
        
        # 5. 组合优化器
        if self._injected_optimizer is not None:
            self.optimizer = self._injected_optimizer
            logger.info("使用注入的组合优化器")
        else:
            self.optimizer = build_optimizer(self.cfg.optimizer)
        
        # 6. 再平衡触发器
        if self._injected_trigger is not None:
            self.trigger = self._injected_trigger
            logger.info("使用注入的再平衡触发器")
        else:
            self.trigger = build_trigger(self.cfg.rebalance, self.dm.trade_dates)
        
        # 7. 交易执行模拟器
        if self._injected_executor is not None:
            self.executor = self._injected_executor
            logger.info("使用注入的执行模拟器")
        else:
            self.executor = ExecutionSimulator(self.cfg.cost)
        
        # 8. 持仓跟踪器
        if self._injected_tracker is not None:
            self.tracker = self._injected_tracker
            logger.info("使用注入的持仓跟踪器")
        else:
            self.tracker = PositionTracker(self.dm.n_stocks, self.cfg.initial_capital)
        
        # 9. 待执行订单队列
        if self._injected_pending_queue is not None:
            self.pending_queue = self._injected_pending_queue
            logger.info("使用注入的待执行订单队列")
        elif self.cfg.enable_pending_orders:
            self.pending_queue = PendingOrderQueue(
                max_pending_days_buy=self.cfg.max_pending_days_buy,
                max_pending_days_sell=self.cfg.max_pending_days_sell
            )
        
        # 10. 预计算收益率矩阵
        self._returns_matrix = self.dm.returns.values
        
        elapsed = time.perf_counter() - t0
        logger.info(f"回测引擎V2设置完成，耗时: {elapsed:.2f}秒")
    
    def _precompute_factors(self):
        """预计算因子数据"""
        # 只处理第一个因子（简化）
        if not self.cfg.factor_files:
            logger.warning("未指定因子文件")
            return
        
        fname = self.cfg.factor_files[0]
        logger.info(f"加载因子: {fname}")
        
        raw = self.dm.load_factor(fname)
        logger.info(f"  因子形状: {raw.shape}, NaN: {raw.isna().sum().sum() / (raw.shape[0] * raw.shape[1]):.2%}")
        
        # 使用管道处理因子（如果可用）
        if self.pipeline is not None:
            processed = self.pipeline.process(raw)
        else:
            processed = raw
        
        # 简单填充NaN
        self._composite_signal = processed.fillna(0)
        
        logger.info(f"✓ 因子加载完成: {self._composite_signal.shape}")
    
    def run(self) -> dict[str, Any]:
        """运行回测"""
        if self.dm is None:
            raise RuntimeError("请先调用setup()方法")
        
        t0 = time.perf_counter()
        logger.info("开始回测...")
        
        last_date_index = len(self.dm.trade_dates) - 1
        for i, date in enumerate(self.dm.trade_dates):
            try:
                self._process_trading_day(date, i)
                
                if i == last_date_index:
                    self._force_liquidation(date, i)
                    
            except Exception as e:
                logger.error(f"处理交易日 {date} 时发生错误: {e}")
                continue
        
        # 清理过期订单
        if self.pending_queue:
            self.pending_queue.mark_expired(self.dm.trade_dates[-1])
        
        elapsed = time.perf_counter() - t0
        logger.info(f"回测完成，总耗时: {elapsed:.2f}秒")
        
        return self._generate_results()
    
    def _process_trading_day(self, date: pd.Timestamp, date_index: int):
        """处理单个交易日"""
        logger.debug(f"处理交易日: {date}")
        
        # 执行次日订单
        if hasattr(self, '_next_day_orders') and self._next_day_orders:
            self._execute_next_day_orders(date, date_index)
        
        # 处理待执行订单
        if self.pending_queue:
            self._process_pending_orders(date, date_index)
        
        # 检查再平衡
        should_rebalance = self.trigger.should_trigger(
            date,
            signal=self._composite_signal.loc[date] if date_index < len(self._composite_signal) else None,
            portfolio_value=self.tracker.get_total_value()
        )
        
        if should_rebalance:
            logger.info(f"触发再平衡: {date}")
            self._execute_rebalance(date, date_index)
        
        # 更新持仓市值
        close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
        self.tracker.update_market_values(date, close_prices)
    
    def _force_liquidation(self, date: pd.Timestamp, date_index: int):
        """最后交易日强制平仓"""
        logger.info(f"最后交易日强制平仓: {date}")
        
        positions = self.tracker.get_all_positions()
        if not positions:
            logger.info("无持仓需要平仓")
            return
        
        try:
            close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
        except KeyError:
            logger.warning(f"最后交易日 {date} 无收盘价数据")
            return
        
        liquidated_count = 0
        for stock, position in list(positions.items()):
            if position.quantity <= 0:
                continue
            
            if stock not in close_prices:
                continue
            
            close_price = close_prices[stock]
            if pd.isna(close_price) or close_price <= 0:
                continue
            
            success, trade = self.executor.execute_order(
                stock, OrderSide.SELL, position.quantity, date, close_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                liquidated_count += 1
                logger.info(f"强制平仓: {stock} {position.quantity}股 @ {close_price:.2f}")
        
        self.tracker.update_market_values(date, close_prices)
        logger.info(f"强制平仓完成: {liquidated_count}只股票")
    
    def _process_pending_orders(self, date: pd.Timestamp, date_index: int):
        """处理待执行订单"""
        if not self.pending_queue:
            return
        
        pending_orders = self.pending_queue.get_pending_orders()
        if not pending_orders:
            return
        
        logger.debug(f"处理{len(pending_orders)}个待执行订单")
        
        open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
        close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date] if date_index < len(self.dm.returns) else None
        
        buyable_mask = self.universe.buyable.loc[date]
        sellable_mask = self.universe.sellable.loc[date]
        
        executed_orders = []
        
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
            close_price = close_prices[order.stock] if close_prices is not None and order.stock in close_prices else None
            
            success, trade = self.executor.execute_pending_order(
                order, date, open_price, close_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                self.pending_queue.mark_executed(order, date, trade.price)
                executed_orders.append(order)
                logger.debug(f"待执行订单执行成功: {order.stock} {order.side.name}")
            else:
                if order.side == OrderSide.BUY and self.cfg.enable_fallback:
                    fallback_success = self._try_fallback_order(order, date, date_index)
                    if fallback_success:
                        executed_orders.append(order)
        
        self.pending_queue.mark_expired(date)
    
    def _try_fallback_order(self, original_order, date: pd.Timestamp, date_index: int) -> bool:
        """尝试备选替补订单"""
        if not self.pending_queue or date_index >= len(self._composite_signal):
            return False
        
        daily_signal = self._composite_signal.iloc[date_index]
        
        excluded_stocks = [original_order.stock]
        fallback_stocks = select_fallback_stocks(
            daily_signal, excluded_stocks, self.cfg.max_fallback_depth
        )
        
        if not fallback_stocks:
            return False
        
        buyable_mask = self.universe.buyable.loc[date]
        
        for fallback_stock in fallback_stocks:
            if not buyable_mask.get(fallback_stock, False):
                continue
            
            open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
            if fallback_stock not in open_prices:
                continue
            
            open_price = open_prices[fallback_stock]
            
            fallback_order = create_pending_order(
                fallback_stock, OrderSide.BUY, original_order.quantity, date
            )
            fallback_order.fallback_stock = original_order.stock
            
            success, trade = self.executor.execute_pending_order(
                fallback_order, date, open_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                self.pending_queue.mark_executed(original_order, date, trade.price)
                original_order.fallback_stock = fallback_stock
                
                logger.info(f"备选订单执行成功: {fallback_stock} 替代 {original_order.stock}")
                return True
        
        return False
    
    def _execute_rebalance(self, date: pd.Timestamp, date_index: int):
        """执行再平衡"""
        if date_index >= len(self._composite_signal):
            return
        
        # 取消过期订单
        if self.pending_queue:
            available_stocks = set(self._composite_signal.columns)
            for stock in available_stocks:
                self.pending_queue.cancel_orders(stock, date)
        
        # 获取因子信号
        daily_signal = self._composite_signal.iloc[date_index]
        
        # 过滤可交易股票
        tradable_mask = self.universe.tradable.loc[date]
        tradable_stocks = daily_signal[tradable_mask].dropna()
        
        if len(tradable_stocks) == 0:
            logger.warning(f"日期 {date} 没有可交易股票")
            return
        
        # 组合优化
        try:
            if date_index >= self.cfg.optimizer.cov_lookback:
                start_idx = date_index - self.cfg.optimizer.cov_lookback
                end_idx = date_index
                returns_data = pd.DataFrame(
                    self._returns_matrix[start_idx:end_idx],
                    index=self.dm.trade_dates[start_idx:end_idx],
                    columns=self.dm.stock_codes
                )
            else:
                returns_data = None
            
            target_weights = self.optimizer.optimize(
                tradable_stocks, returns_data
            )
            
            logger.debug(f"优化得到{len(target_weights)}只股票的目标权重")
            
        except Exception as e:
            logger.error(f"组合优化失败: {e}")
            return
        
        # 计算目标持仓
        current_value = self.tracker.get_total_value()
        target_positions = {}
        
        for stock, weight in target_weights.items():
            target_value = weight * current_value
            current_position = self.tracker.get_position(stock)
            current_quantity = current_position.quantity if current_position else 0
            
            try:
                adj_close = self.dm.get_adj_price('close', self.cfg.adjustment_type)
                if stock in adj_close.columns and date_index < len(adj_close):
                    close_price = adj_close.iloc[date_index, adj_close.columns.get_loc(stock)]
                else:
                    continue
            except (KeyError, IndexError):
                continue
            
            if close_price is None or pd.isna(close_price) or close_price <= 0:
                continue
            
            buffered_target_value = target_value * 0.985
            price_ratio = buffered_target_value / close_price
            if pd.isna(price_ratio) or np.isinf(price_ratio):
                continue
            
            if self.cfg.optimizer.round_lot:
                target_quantity = int(price_ratio / 100) * 100
            else:
                target_quantity = int(price_ratio)
            
            target_positions[stock] = {
                'current_quantity': current_quantity,
                'target_quantity': target_quantity,
                'price': close_price,
                'weight': weight
            }
        
        # 生成交易订单
        self._generate_rebalance_orders(date, target_positions, date_index)
    
    def _generate_rebalance_orders(self, date: pd.Timestamp, target_positions: dict, date_index: int):
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
                    self._execute_order_next_open(order, date, date_index)
            else:
                order = create_pending_order(stock, OrderSide.SELL, -trade_qty, date)
                if self.pending_queue:
                    self.pending_queue.add_order(order)
                else:
                    self._execute_order_next_open(order, date, date_index)
    
    def _execute_order_next_open(self, order, date: pd.Timestamp, date_index: int):
        """延迟到次日开盘执行订单"""
        if not hasattr(self, '_next_day_orders'):
            self._next_day_orders = []
        
        self._next_day_orders.append({
            'order': order,
            'create_date': date,
            'create_date_index': date_index
        })
        logger.debug(f"订单标记为次日开盘执行: {order.stock} {order.side.name} {order.quantity}股")
    
    def _execute_next_day_orders(self, date: pd.Timestamp, date_index: int):
        """执行次日开盘订单"""
        if not hasattr(self, '_next_day_orders') or not self._next_day_orders:
            return
        
        logger.info(f"执行次日开盘订单: {len(self._next_day_orders)}个订单, 日期: {date}")
        
        try:
            open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
        except KeyError:
            logger.warning(f"日期 {date} 没有开盘价数据")
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
            
            if order.side == OrderSide.BUY:
                required_cash = order.quantity * open_price * 1.002
                if self.tracker.get_cash() < required_cash:
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
            logger.info(f"次日开盘订单执行完成: 成功{executed_count}个, 失败{len(failed_orders)}个")
    
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        snapshots = self.tracker.get_snapshots()
        trades_df = self.executor.trade_log.get_trades_df()
        
        output_dir = self.cfg.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_data = generate_report(snapshots, trades_df, output_dir)
        
        additional_info = {
            'config': {
                'initial_capital': self.cfg.initial_capital,
                'optimizer_method': self.cfg.optimizer.method,
                'rebalance_method': self.cfg.rebalance.method,
                'enable_pending_orders': self.cfg.enable_pending_orders
            },
            'data_info': self.dm.get_data_info() if self.dm else {},
            'universe_summary': self.universe.get_mask_summary() if self.universe else {},
            'pending_order_stats': self.pending_queue.get_order_stats() if self.pending_queue else {},
            'execution_stats': self.executor.get_execution_stats()
        }
        
        if not trades_df.empty:
            trades_path = output_dir / "trades.csv"
            trades_df.to_csv(trades_path, index=False, encoding='utf-8-sig')
            logger.info(f"交易记录已保存: {trades_path}")
        
        if snapshots:
            snapshots_df = self.tracker.get_snapshots_df()
            snapshots_path = output_dir / "portfolio_snapshots.csv"
            snapshots_df.to_csv(snapshots_path, index=False, encoding='utf-8-sig')
            logger.info(f"持仓快照已保存: {snapshots_path}")
        
        if self.pending_queue:
            pending_log_df = self.pending_queue.get_event_log()
            if not pending_log_df.empty:
                pending_log_path = output_dir / "pending_order_events.csv"
                pending_log_df.to_csv(pending_log_path, index=False, encoding='utf-8-sig')
                logger.info(f"待执行订单事件日志已保存: {pending_log_path}")
        
        portfolio_value_series = pd.Series()
        if snapshots:
            snapshots_df = self.tracker.get_snapshots_df()
            if 'total_value' in snapshots_df.columns and 'date' in snapshots_df.columns:
                portfolio_value_series = snapshots_df.set_index('date')['total_value']
                logger.info(f"✓ 组合价值序列已生成: {len(portfolio_value_series)} 个数据点")
        
        results = {
            'portfolio_value': portfolio_value_series,
            'performance_metrics': report_data['metrics'],
            'charts': report_data['charts'],
            'reports': report_data['reports'],
            'additional_info': additional_info
        }
        
        logger.info("回测结果生成完成")
        return results
