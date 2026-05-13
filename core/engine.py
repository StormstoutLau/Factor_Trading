"""回测引擎核心 - 基于Backtest_Opus_2.0架构

⚠️  DEPRECATED: 此模块已弃用，请使用 engine_v2.py 中的 BacktestEngineV2。
    BacktestEngineV2 提供了完整的依赖注入支持，更易于测试和维护。

这是Factor Trading v3.0的核心回测引擎，集成了所有模块：
- 完整的待执行订单管理
- 多种组合优化策略
- 灵活的因子处理管道
- 真实市场约束模拟
- 详细的性能分析
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from analytics import generate_report
from config import BacktestConfig
from data import DataManager
from execution import ExecutionSimulator
from factor import FactorCombiner, FactorPipeline
from pending import OrderSide, PendingOrderQueue, create_pending_order, select_fallback_stocks
from portfolio import build_optimizer
from rebalance import build_trigger
from tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎核心

    .. deprecated::
        使用 :class:`BacktestEngineV2` 替代。
        此类保留仅用于向后兼容。

    单策略回测引擎，支持完整的待执行订单管理。
    """

    def __init__(self, config: BacktestConfig):
        """初始化回测引擎

        Args:
            config: 回测配置
        """
        import warnings
        warnings.warn(
            "BacktestEngine is deprecated, use BacktestEngineV2 from engine_v2",
            DeprecationWarning,
            stacklevel=2
        )
        self.cfg = config
        
        # 核心组件
        self.dm: Optional[DataManager] = None
        self.universe: Optional[UniverseFilter] = None
        self.pipeline: Optional[FactorPipeline] = None
        self.combiner: Optional[FactorCombiner] = None
        self.optimizer = None
        self.trigger = None
        self.executor: Optional[ExecutionSimulator] = None
        self.tracker: Optional[PositionTracker] = None
        self.pending_queue: Optional[PendingOrderQueue] = None
        
        # 预计算数据
        self._composite_signal: Optional[pd.DataFrame] = None
        self._returns_matrix: Optional[np.ndarray] = None
        
        logger.info("回测引擎初始化完成")
    
    def setup(self):
        """设置回测引擎"""
        t0 = time.perf_counter()
        
        logger.info("开始设置回测引擎...")
        
        # 1. 数据管理器
        logger.info("加载数据...")
        self.dm = DataManager(self.cfg)
        
        # 2. 股票池过滤器
        logger.info("构建股票池过滤器...")
        self.universe = UniverseFilter(self.dm, self.cfg.universe)
        self.universe.build_masks()
        
        # 3. 因子处理管道
        logger.info("设置因子处理管道...")
        self.pipeline = FactorPipeline(self.dm, self.cfg.factor)
        self.combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        self._precompute_factors()
        
        # 4. 组合优化器
        self.optimizer = build_optimizer(self.cfg.optimizer)
        
        # 5. 再平衡触发器
        self.trigger = build_trigger(self.cfg.rebalance, self.dm.trade_dates)
        
        # 6. 交易执行模拟器
        self.executor = ExecutionSimulator(self.cfg.cost)
        
        # 7. 持仓跟踪器
        self.tracker = PositionTracker(self.dm.n_stocks, self.cfg.initial_capital)
        
        # 8. 待执行订单队列
        if self.cfg.enable_pending_orders:
            self.pending_queue = PendingOrderQueue(
                max_pending_days_buy=self.cfg.max_pending_days_buy,
                max_pending_days_sell=self.cfg.max_pending_days_sell
            )
        
        # 9. 预计算收益率矩阵
        self._returns_matrix = self.dm.returns.values
        
        elapsed = time.perf_counter() - t0
        logger.info(f"回测引擎设置完成，耗时: {elapsed:.2f}秒")
    
    def _precompute_factors(self):
        """预计算因子数据（简化版）"""
        # 只处理第一个因子（简化）
        fname = self.cfg.factor_files[0]
        logger.info(f"加载因子: {fname}")
        
        # 直接加载原始因子
        raw = self.dm.load_factor(fname)
        logger.info(f"  因子形状: {raw.shape}, NaN: {raw.isna().sum().sum() / (raw.shape[0] * raw.shape[1]):.2%}")
        
        # 直接使用原始因子作为复合信号（跳过处理和合成）
        self._composite_signal = raw.fillna(0)  # 简单填充NaN
        
        logger.info(f"✓ 因子加载完成: {self._composite_signal.shape}")
        logger.info(f"  合成信号NaN: {self._composite_signal.isna().sum().sum() / (self._composite_signal.shape[0] * self._composite_signal.shape[1]):.2%}")
    
    def run(self) -> dict[str, Any]:
        """运行回测
        
        Returns:
            回测结果
        """
        if self.dm is None:
            raise RuntimeError("请先调用setup()方法")
        
        t0 = time.perf_counter()
        logger.info("开始回测...")
        
        # 主循环
        last_date_index = len(self.dm.trade_dates) - 1
        for i, date in enumerate(self.dm.trade_dates):
            try:
                self._process_trading_day(date, i)
                
                # 【修复B2】最后交易日强制平仓
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
        
        # 生成报告
        return self._generate_results()
    
    def _force_liquidation(self, date: pd.Timestamp, date_index: int):
        """最后交易日强制平仓
        
        【修复B2】在回测最后一天，将所有持仓按收盘价卖出
        
        Args:
            date: 最后交易日
            date_index: 日期索引
        """
        logger.info(f"最后交易日强制平仓: {date}")
        
        positions = self.tracker.get_all_positions()
        if not positions:
            logger.info("无持仓需要平仓")
            return
        
        # 获取收盘价
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
            
            # 执行卖出
            success, trade = self.executor.execute_order(
                stock, OrderSide.SELL, position.quantity, date, close_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                liquidated_count += 1
                logger.info(f"强制平仓: {stock} {position.quantity}股 @ {close_price:.2f}")
        
        # 【修复】强制平仓后更新市值（持仓已清空）
        self.tracker.update_market_values(date, close_prices)
        
        logger.info(f"强制平仓完成: {liquidated_count}只股票")
    
    def _process_trading_day(self, date: pd.Timestamp, date_index: int):
        """处理单个交易日
        
        Args:
            date: 交易日期
            date_index: 日期索引
        """
        logger.debug(f"处理交易日: {date}")
        
        # 【方案B】先执行前一交易日生成的次日订单（使用当日开盘价）
        if hasattr(self, '_next_day_orders') and self._next_day_orders:
            self._execute_next_day_orders(date, date_index)
        
        # 1. 处理待执行订单（pending_queue）
        if self.pending_queue:
            self._process_pending_orders(date, date_index)
        
        # 2. 检查是否需要再平衡
        should_rebalance = self.trigger.should_trigger(
            date, 
            signal=self._composite_signal.loc[date] if date_index < len(self._composite_signal) else None,
            portfolio_value=self.tracker.get_total_value()
        )
        
        if should_rebalance:
            logger.info(f"触发再平衡: {date}")
            self._execute_rebalance(date, date_index)
        
        # 3. 更新持仓市值（使用复权价格）
        close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
        self.tracker.update_market_values(date, close_prices)
    
    def _process_pending_orders(self, date: pd.Timestamp, date_index: int):
        """处理待执行订单
        
        Args:
            date: 交易日期
            date_index: 日期索引
        """
        if not self.pending_queue:
            return
        
        # 获取待执行订单
        pending_orders = self.pending_queue.get_pending_orders()
        
        if not pending_orders:
            return
        
        logger.debug(f"处理{len(pending_orders)}个待执行订单")
        
        # 获取价格数据（使用复权价格）
        open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
        close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date] if date_index < len(self.dm.returns) else None
        
        # 获取可交易掩码
        buyable_mask = self.universe.buyable.loc[date]
        sellable_mask = self.universe.sellable.loc[date]
        
        executed_orders = []
        
        for order in pending_orders:
            # 检查是否可交易
            if order.side == OrderSide.BUY:
                if not buyable_mask.get(order.stock, False):
                    continue  # 无法买入
            else:  # SELL
                if not sellable_mask.get(order.stock, False):
                    continue  # 无法卖出
            
            # 获取价格
            if order.stock not in open_prices:
                continue
            
            open_price = open_prices[order.stock]
            close_price = close_prices[order.stock] if close_prices is not None and order.stock in close_prices else None
            
            # 执行订单
            success, trade = self.executor.execute_pending_order(
                order, date, open_price, close_price
            )
            
            if success and trade:
                # 更新持仓
                self.tracker.execute_trade(trade)
                
                # 标记订单已执行
                self.pending_queue.mark_executed(order, date, trade.price)
                
                executed_orders.append(order)
                
                logger.debug(f"待执行订单执行成功: {order.stock} {order.side.name}")
            else:
                # 买入失败，尝试备选替补
                if order.side == OrderSide.BUY and self.cfg.enable_fallback:
                    fallback_success = self._try_fallback_order(order, date, date_index)
                    if fallback_success:
                        executed_orders.append(order)
        
        # 清理已执行的订单
        # 注意：这里不立即清理，让pending_queue自己管理
        for order in executed_orders:
            pass
        
        # 标记过期订单
        self.pending_queue.mark_expired(date)
    
    def _try_fallback_order(self, original_order: PendingOrder, 
                           date: pd.Timestamp, date_index: int) -> bool:
        """尝试备选替补订单
        
        Args:
            original_order: 原始订单
            date: 交易日期
            date_index: 日期索引
            
        Returns:
            是否成功
        """
        if not self.pending_queue or date_index >= len(self._composite_signal):
            return False
        
        # 获取当日因子信号
        daily_signal = self._composite_signal.iloc[date_index]
        
        # 选择备选股票
        excluded_stocks = [original_order.stock]
        fallback_stocks = select_fallback_stocks(
            daily_signal, excluded_stocks, self.cfg.max_fallback_depth
        )
        
        if not fallback_stocks:
            return False
        
        # 获取可交易掩码
        buyable_mask = self.universe.buyable.loc[date]
        
        for fallback_stock in fallback_stocks:
            if not buyable_mask.get(fallback_stock, False):
                continue
            
            # 获取价格（使用复权价格）
            open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
            if fallback_stock not in open_prices:
                continue
            
            open_price = open_prices[fallback_stock]
            
            # 创建备选订单
            fallback_order = create_pending_order(
                fallback_stock, OrderSide.BUY, original_order.quantity, date
            )
            fallback_order.fallback_stock = original_order.stock
            
            # 执行备选订单
            success, trade = self.executor.execute_pending_order(
                fallback_order, date, open_price
            )
            
            if success and trade:
                # 更新持仓
                self.tracker.execute_trade(trade)
                
                # 标记原订单已执行（通过备选）
                self.pending_queue.mark_executed(original_order, date, trade.price)
                original_order.fallback_stock = fallback_stock
                
                logger.info(f"备选订单执行成功: {fallback_stock} 替代 {original_order.stock}")
                return True
        
        return False
    
    def _execute_rebalance(self, date: pd.Timestamp, date_index: int):
        """执行再平衡
        
        Args:
            date: 交易日期
            date_index: 日期索引
        """
        if date_index >= len(self._composite_signal):
            return
        
        # 1. 取消过期待执行订单
        if self.pending_queue:
            # 确保只取消存在于composite_signal中的股票
            available_stocks = set(self._composite_signal.columns)
            for stock in self._composite_signal.columns:
                self.pending_queue.cancel_orders(stock, date)
        
        # 2. 获取因子信号
        daily_signal = self._composite_signal.iloc[date_index]
        
        # 3. 过滤可交易股票
        tradable_mask = self.universe.tradable.loc[date]
        tradable_stocks = daily_signal[tradable_mask].dropna()
        
        if len(tradable_stocks) == 0:
            logger.warning(f"日期 {date} 没有可交易股票")
            return
        
        # 4. 组合优化
        try:
            # 获取收益率数据（用于风险模型）
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
            
            # 执行优化
            target_weights = self.optimizer.optimize(
                tradable_stocks, returns_data
            )
            
            logger.debug(f"优化得到{len(target_weights)}只股票的目标权重")
            
        except Exception as e:
            logger.error(f"组合优化失败: {e}")
            return
        
        # 5. 计算目标持仓
        current_value = self.tracker.get_total_value()
        target_positions = {}
        
        for stock, weight in target_weights.items():
            target_value = weight * current_value
            current_position = self.tracker.get_position(stock)
            current_quantity = current_position.quantity if current_position else 0
            
            # 获取价格（使用复权价格）
            try:
                adj_close = self.dm.get_adj_price('close', self.cfg.adjustment_type)
                if stock in adj_close.columns and date_index < len(adj_close):
                    # 使用更可靠的方式获取价格
                    close_price = adj_close.iloc[date_index, adj_close.columns.get_loc(stock)]
                else:
                    logger.warning(f"股票 {stock} 的价格数据不可用")
                    continue
            except (KeyError, IndexError) as e:
                logger.warning(f"获取股票 {stock} 价格时出错: {e}")
                continue
                
            # 【修复1】添加NaN检查，防止int()转换错误
            if close_price is None or pd.isna(close_price) or close_price <= 0:
                logger.debug(f"股票 {stock} 的价格无效: {close_price}")
                continue
            
            # 计算目标数量（考虑整手数）
            # 【修复2】添加NaN检查，防止除零或NaN转换错误
            # 【修复B3-2】预留价格变动和成本缓冲（约1.5%）
            buffered_target_value = target_value * 0.985  # 预留1.5%缓冲应对次日价格变动和成本
            price_ratio = buffered_target_value / close_price
            if pd.isna(price_ratio) or np.isinf(price_ratio):
                logger.debug(f"股票 {stock} 的价格比率无效: target_value={target_value}, close_price={close_price}")
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
        
        # 6. 生成交易订单（延迟到次日开盘执行）
        self._generate_rebalance_orders(date, target_positions, date_index)
    
    def _generate_rebalance_orders(self, date: pd.Timestamp, target_positions: dict[str, dict], date_index: int):
        """生成再平衡订单（方案B：加入待执行队列，次日开盘执行）
        
        Args:
            date: 交易日期
            target_positions: 目标持仓字典
            date_index: 日期索引
        """
        for stock, position_info in target_positions.items():
            current_qty = position_info['current_quantity']
            target_qty = position_info['target_quantity']
            
            if current_qty == target_qty:
                continue
            
            trade_qty = target_qty - current_qty
            
            if trade_qty > 0:
                # 买入订单
                order = create_pending_order(stock, OrderSide.BUY, trade_qty, date)
                if self.pending_queue:
                    self.pending_queue.add_order(order)
                    logger.debug(f"买入订单加入待执行队列: {stock}, 数量: {trade_qty}")
                else:
                    # 无待执行队列时，延迟到次日开盘执行
                    self._execute_order_next_open(order, date, date_index)
            else:
                # 卖出订单
                order = create_pending_order(stock, OrderSide.SELL, -trade_qty, date)
                if self.pending_queue:
                    self.pending_queue.add_order(order)
                    logger.debug(f"卖出订单加入待执行队列: {stock}, 数量: {-trade_qty}")
                else:
                    # 无待执行队列时，延迟到次日开盘执行
                    self._execute_order_next_open(order, date, date_index)
    
    def _execute_order_next_open(self, order, date: pd.Timestamp, date_index: int):
        """延迟到次日开盘执行订单（方案B）
        
        将订单存储到实例变量中，在下一个交易日开盘时执行
        
        Args:
            order: 订单
            date: 订单生成日期
            date_index: 当前日期索引
        """
        # 确保有存储待执行订单的属性
        if not hasattr(self, '_next_day_orders'):
            self._next_day_orders = []
        
        # 存储订单和相关信息，供下一个交易日执行
        self._next_day_orders.append({
            'order': order,
            'create_date': date,
            'create_date_index': date_index
        })
        logger.debug(f"订单标记为次日开盘执行: {order.stock} {order.side.name} {order.quantity}股")
    
    def _execute_next_day_orders(self, date: pd.Timestamp, date_index: int):
        """执行前一交易日生成的次日订单（使用当日开盘价）
        
        Args:
            date: 当前交易日期（执行日期）
            date_index: 当前日期索引
        """
        if not hasattr(self, '_next_day_orders') or not self._next_day_orders:
            return
        
        logger.info(f"执行次日开盘订单: {len(self._next_day_orders)}个订单, 日期: {date}")
        
        # 获取当日开盘价（使用复权价格）
        try:
            open_prices = self.dm.get_adj_price('open', self.cfg.adjustment_type).loc[date]
        except KeyError:
            logger.warning(f"日期 {date} 没有开盘价数据")
            return
        
        # 获取可交易掩码
        buyable_mask = self.universe.buyable.loc[date] if hasattr(self.universe, 'buyable') else None
        sellable_mask = self.universe.sellable.loc[date] if hasattr(self.universe, 'sellable') else None
        
        executed_count = 0
        failed_orders = []
        
        for order_info in self._next_day_orders:
            order = order_info['order']
            
            # 检查是否可交易
            if order.side == OrderSide.BUY:
                if buyable_mask is not None and not buyable_mask.get(order.stock, True):
                    logger.warning(f"股票 {order.stock} 当日不可买入，跳过")
                    failed_orders.append(order_info)
                    continue
            else:  # SELL
                if sellable_mask is not None and not sellable_mask.get(order.stock, True):
                    logger.warning(f"股票 {order.stock} 当日不可卖出，跳过")
                    failed_orders.append(order_info)
                    continue
            
            # 获取开盘价
            if order.stock not in open_prices:
                logger.warning(f"股票 {order.stock} 缺少开盘价数据")
                failed_orders.append(order_info)
                continue
            
            open_price = open_prices[order.stock]
            
            # 检查价格有效性
            if open_price is None or pd.isna(open_price) or open_price <= 0:
                logger.warning(f"股票 {order.stock} 开盘价无效: {open_price}")
                failed_orders.append(order_info)
                continue
            
            # 【修复B3】买入时检查资金是否充足
            if order.side == OrderSide.BUY:
                required_cash = order.quantity * open_price * 1.002  # 预留0.2%成本缓冲
                if self.tracker.get_cash() < required_cash:
                    logger.warning(f"资金不足: 需要{required_cash:.2f}, 可用{self.tracker.get_cash():.2f}, 跳过买入{order.stock}")
                    failed_orders.append(order_info)
                    continue
            
            # 执行交易（使用开盘价）
            success, trade = self.executor.execute_order(
                order.stock, order.side, order.quantity, date, open_price
            )
            
            if success and trade:
                self.tracker.execute_trade(trade)
                executed_count += 1
                logger.debug(f"次日订单执行成功: {order.stock} {order.side.name} {order.quantity}股 @ {open_price}")
            else:
                logger.warning(f"次日订单执行失败: {order.stock} {order.side.name} {order.quantity}股")
                failed_orders.append(order_info)
        
        # 更新待执行订单列表（保留失败的订单供后续处理）
        self._next_day_orders = failed_orders
        
        if executed_count > 0:
            logger.info(f"次日开盘订单执行完成: 成功{executed_count}个, 失败{len(failed_orders)}个")
    
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果
        
        Returns:
            回测结果字典
        """
        # 获取快照和交易记录
        snapshots = self.tracker.get_snapshots()
        trades_df = self.executor.trade_log.get_trades_df()
        
        # 生成性能分析报告
        output_dir = self.cfg.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_data = generate_report(snapshots, trades_df, output_dir)
        
        # 添加额外信息
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
        
        # 保存交易记录
        if not trades_df.empty:
            trades_path = output_dir / "trades.csv"
            trades_df.to_csv(trades_path, index=False, encoding='utf-8-sig')
            logger.info(f"交易记录已保存: {trades_path}")
        
        # 保存持仓快照
        if snapshots:
            snapshots_df = self.tracker.get_snapshots_df()
            snapshots_path = output_dir / "portfolio_snapshots.csv"
            snapshots_df.to_csv(snapshots_path, index=False, encoding='utf-8-sig')
            logger.info(f"持仓快照已保存: {snapshots_path}")
        
        # 保存待执行订单事件日志
        if self.pending_queue:
            pending_log_df = self.pending_queue.get_event_log()
            if not pending_log_df.empty:
                pending_log_path = output_dir / "pending_order_events.csv"
                pending_log_df.to_csv(pending_log_path, index=False, encoding='utf-8-sig')
                logger.info(f"待执行订单事件日志已保存: {pending_log_path}")
        
        # 合并结果
        # 【修复3】添加 portfolio_value 到返回结果
        portfolio_value_series = pd.Series()
        if snapshots:
            snapshots_df = self.tracker.get_snapshots_df()
            if 'total_value' in snapshots_df.columns and 'date' in snapshots_df.columns:
                portfolio_value_series = snapshots_df.set_index('date')['total_value']
                logger.info(f"✓ 组合价值序列已生成: {len(portfolio_value_series)} 个数据点")
        
        results = {
            'portfolio_value': portfolio_value_series,  # 新增
            'performance_metrics': report_data['metrics'],
            'charts': report_data['charts'],
            'reports': report_data['reports'],
            'additional_info': additional_info
        }
        
        logger.info("回测结果生成完成")
        return results
