"""
完整因子回测演示 - 一年期月度调仓
=====================================

回测流程:
1. 生成一年期合成数据（约252个交易日）
2. 上个月底计算因子 → 下个月初调仓
3. 完整展开：因子计算 → 异常值处理 → 过滤 → 组合构造 → 调仓 → 收益计算

每一步都有详细的日志输出，描述实际动作。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("FullBacktestDemo")

# 导入项目模块
from config import BacktestConfig, CostConfig, UniverseConfig, FactorConfig, OptimizerConfig, RebalanceConfig
from data import DataManager
from factor import FactorPipeline, FactorCombiner
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig, get_balanced_config
from portfolio import build_optimizer
from rebalance import build_trigger
from execution import ExecutionSimulator
from pending import PendingOrderQueue, PendingOrder, OrderSide
from tracker import PositionTracker
from analytics import PerformanceAnalyzer


# ============================================================
# 步骤1: 生成一年期合成数据
# ============================================================

def generate_one_year_data(
    n_stocks: int = 100,
    start_date: str = "2024-01-02",
    end_date: str = "2024-12-31",
    seed: int = 42
) -> dict[str, Any]:
    """
    生成一年期合成A股数据
    
    实际动作:
    - 生成约252个交易日的日期序列（排除周末）
    - 为每只股票生成开盘价、收盘价、最高价、最低价
    - 生成复权因子、停牌状态、ST标记、行业分类、市值数据
    - 生成两个因子：价值因子（PE倒数）和动量因子（20日收益率）
    """
    np.random.seed(seed)
    
    logger.info("=" * 70)
    logger.info("【步骤1】生成一年期合成数据")
    logger.info("=" * 70)
    
    # 生成交易日历（排除周末）
    dates = pd.bdate_range(start=start_date, end=end_date)
    n_days = len(dates)
    logger.info(f"  → 生成交易日历: {start_date} 至 {end_date}, 共 {n_days} 个交易日")
    
    # 生成股票代码（模拟A股）
    stock_codes = [f"{i:06d}.SH" if i % 2 == 0 else f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]
    logger.info(f"  → 生成股票池: {n_stocks} 只股票")
    
    # 生成行业分类
    industries = ['电子', '医药', '金融', '消费', '能源', '地产', '科技', '制造']
    industry_map = {code: np.random.choice(industries) for code in stock_codes}
    industry_df = pd.DataFrame({code: [industry_map[code]] * n_days for code in stock_codes}, index=dates)
    logger.info(f"  → 生成行业分类: {len(industries)} 个行业")
    
    # 生成ST标记（约5%的股票是ST）
    st_stocks = set(np.random.choice(stock_codes, size=max(1, n_stocks // 20), replace=False))
    st_data = np.zeros((n_days, n_stocks))
    for i, code in enumerate(stock_codes):
        if code in st_stocks:
            # ST状态持续一段时间
            start_st = np.random.randint(0, n_days // 2)
            end_st = np.random.randint(start_st + 10, n_days)
            st_data[start_st:end_st, i] = 1
    st_df = pd.DataFrame(st_data, index=dates, columns=stock_codes)
    logger.info(f"  → 生成ST标记: {len(st_stocks)} 只ST股票")
    
    # 生成停牌数据（约3%的交易日有停牌）
    suspend_data = np.zeros((n_days, n_stocks))
    for i in range(n_stocks):
        n_suspend = np.random.poisson(3)
        for _ in range(n_suspend):
            start_sus = np.random.randint(0, max(1, n_days - 5))
            duration = np.random.randint(1, 6)
            suspend_data[start_sus:min(start_sus + duration, n_days), i] = 1
    suspend_df = pd.DataFrame(suspend_data, index=dates, columns=stock_codes)
    total_suspend = suspend_df.sum().sum()
    logger.info(f"  → 生成停牌数据: 共 {int(total_suspend)} 个停牌日")
    
    # 生成价格数据（带趋势和波动）
    close_data = np.zeros((n_days, n_stocks))
    open_data = np.zeros((n_days, n_stocks))
    high_data = np.zeros((n_days, n_stocks))
    low_data = np.zeros((n_days, n_stocks))
    
    for i in range(n_stocks):
        # 初始价格 10-100元
        initial_price = np.random.uniform(10, 100)
        # 日收益率：均值0.0002，标准差0.02
        daily_returns = np.random.normal(0.0002, 0.02, n_days)
        # 价格序列
        prices = initial_price * np.cumprod(1 + daily_returns)
        close_data[:, i] = prices
        # 开盘价 = 收盘价 * (1 + 小幅随机)
        open_data[:, i] = prices * (1 + np.random.normal(0, 0.005, n_days))
        # 最高价/最低价
        high_data[:, i] = np.maximum(open_data[:, i], close_data[:, i]) * (1 + np.random.uniform(0, 0.01, n_days))
        low_data[:, i] = np.minimum(open_data[:, i], close_data[:, i]) * (1 - np.random.uniform(0, 0.01, n_days))
    
    close_df = pd.DataFrame(close_data, index=dates, columns=stock_codes)
    open_df = pd.DataFrame(open_data, index=dates, columns=stock_codes)
    high_df = pd.DataFrame(high_data, index=dates, columns=stock_codes)
    low_df = pd.DataFrame(low_data, index=dates, columns=stock_codes)
    logger.info(f"  → 生成价格数据: 开/高/低/收")
    
    # 复权因子（缓慢增长）
    adj_data = np.ones((n_days, n_stocks))
    for i in range(n_stocks):
        adj_data[:, i] = np.cumprod(1 + np.random.normal(0, 0.001, n_days))
    adj_df = pd.DataFrame(adj_data, index=dates, columns=stock_codes)
    logger.info(f"  → 生成复权因子")
    
    # 市值数据（亿元）
    mktcap_data = np.zeros((n_days, n_stocks))
    for i in range(n_stocks):
        base_cap = np.random.uniform(50, 500)  # 50-500亿
        mktcap_data[:, i] = base_cap * (1 + np.cumsum(np.random.normal(0, 0.001, n_days)))
    mktcap_df = pd.DataFrame(mktcap_data, index=dates, columns=stock_codes)
    logger.info(f"  → 生成市值数据: 50-500亿元")
    
    # 生成价值因子（EP = 1/PE，低PE = 高价值）
    # 价值因子 = 随机 + 与市值负相关（小市值价值更高）
    factor_value = np.zeros((n_days, n_stocks))
    for t in range(n_days):
        for i in range(n_stocks):
            base_value = np.random.normal(0.05, 0.02)  # EP约5%
            size_penalty = (mktcap_data[t, i] - 200) / 500 * 0.01  # 大市值价值略低
            factor_value[t, i] = base_value - size_penalty + np.random.normal(0, 0.005)
    factor_value_df = pd.DataFrame(factor_value, index=dates, columns=stock_codes)
    logger.info(f"  → 生成价值因子 (EP)")
    
    # 生成动量因子（20日收益率）
    factor_momentum = np.zeros((n_days, n_stocks))
    for t in range(20, n_days):
        for i in range(n_stocks):
            # 20日收益率
            mom = (close_data[t, i] / close_data[t-20, i] - 1)
            factor_momentum[t, i] = mom + np.random.normal(0, 0.01)
    # 前20天用随机值填充
    factor_momentum[:20, :] = np.random.normal(0, 0.05, (20, n_stocks))
    factor_momentum_df = pd.DataFrame(factor_momentum, index=dates, columns=stock_codes)
    logger.info(f"  → 生成动量因子 (20日收益率)")
    
    logger.info(f"  ✓ 数据生成完成: {n_days} 天 × {n_stocks} 只股票")
    
    return {
        'dates': dates,
        'stock_codes': stock_codes,
        'close': close_df,
        'open': open_df,
        'high': high_df,
        'low': low_df,
        'adj': adj_df,
        'suspend': suspend_df,
        'st': st_df,
        'industry': industry_df,
        'mktcap': mktcap_df,
        'factor_value': factor_value_df,
        'factor_momentum': factor_momentum_df,
    }


def save_data_to_pkl(data: dict[str, Any], data_dir: Path) -> None:
    """保存数据到pkl文件"""
    data_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_save = {
        'close.pkl': 'close',
        'open.pkl': 'open',
        'high.pkl': 'high',
        'low.pkl': 'low',
        'stock_adj.pkl': 'adj',
        'suspend.pkl': 'suspend',
        'st.pkl': 'st',
        'industry.pkl': 'industry',
        'mktcap.pkl': 'mktcap',
        'factor_value.pkl': 'factor_value',
        'factor_momentum.pkl': 'factor_momentum',
    }
    
    for filename, key in files_to_save.items():
        filepath = data_dir / filename
        data[key].to_pickle(filepath)
    
    logger.info(f"  ✓ 数据已保存到: {data_dir}")


# ============================================================
# 步骤2-7: 完整回测流程
# ============================================================

class DetailedBacktestEngine:
    """
    详细的回测引擎，每一步都输出实际动作
    
    回测逻辑:
    - 上个月底计算因子信号
    - 下个月初（第一个交易日）开盘调仓
    - 使用开盘价执行交易
    """
    
    def __init__(self, config: BacktestConfig, data_dir: Path):
        self.cfg = config
        self.data_dir = data_dir
        
        # 初始化各模块
        logger.info("\n" + "=" * 70)
        logger.info("【步骤2】初始化回测引擎各模块")
        logger.info("=" * 70)
        
        # 数据管理器
        logger.info("  → 初始化 DataManager（懒加载策略）")
        self.dm = DataManager(config)
        
        # 股票池过滤器
        logger.info("  → 初始化 UniverseFilter")
        filter_config = get_balanced_config()
        self.universe = UniverseFilter(self.dm, filter_config)
        
        # 因子处理管道
        logger.info("  → 初始化 FactorPipeline")
        self.pipeline = FactorPipeline(self.dm, config.factor)
        
        # 因子合成器
        logger.info("  → 初始化 FactorCombiner")
        self.combiner = FactorCombiner(config.factor_files, config.factor_weights)
        
        # 组合优化器
        logger.info(f"  → 初始化 Optimizer（方法: {config.optimizer.method}）")
        self.optimizer = build_optimizer(config.optimizer)
        
        # 再平衡触发器（月度）
        logger.info(f"  → 初始化 Trigger（频率: {config.rebalance.frequency}）")
        self.trigger = build_trigger(config.rebalance, self.dm.trade_dates)
        
        # 交易执行模拟器
        logger.info("  → 初始化 ExecutionSimulator")
        self.executor = ExecutionSimulator(config.cost)
        
        # 持仓跟踪器
        logger.info("  → 初始化 PositionTracker")
        self.tracker = PositionTracker(len(self.dm.stock_codes), config.initial_capital)
        
        # 待执行订单队列
        logger.info("  → 初始化 PendingOrderQueue")
        self.pending_queue = PendingOrderQueue(
            max_pending_days_buy=config.max_pending_days_buy,
            max_pending_days_sell=config.max_pending_days_sell
        )
        
        # 状态变量
        self._last_rebalance_date: pd.Timestamp | None = None
        self._current_weights: pd.Series | None = None
        self._next_day_orders: list[dict] = []  # 次日开盘执行的订单
        
        logger.info("  ✓ 所有模块初始化完成")
    
    def setup(self) -> None:
        """预计算所有数据"""
        logger.info("\n" + "=" * 70)
        logger.info("【步骤3】预计算数据")
        logger.info("=" * 70)
        
        # 构建过滤掩码
        logger.info("  → 构建股票池过滤掩码...")
        self.universe.build_masks()
        mask_summary = self.universe.get_mask_summary()
        logger.info(f"    - 可买入覆盖率: {mask_summary['buyable_coverage']:.1%}")
        logger.info(f"    - 可卖出覆盖率: {mask_summary['sellable_coverage']:.1%}")
        logger.info(f"    - 可交易覆盖率: {mask_summary['tradable_coverage']:.1%}")
        
        # 加载因子数据
        logger.info("  → 加载因子数据...")
        self.raw_factors = {}
        for factor_file in self.cfg.factor_files:
            factor_name = factor_file.replace('.pkl', '')
            factor_data = self.dm.load_factor(factor_file)
            self.raw_factors[factor_name] = factor_data
            logger.info(f"    - 加载因子: {factor_name}, 形状: {factor_data.shape}")
        
        # 预计算因子（每个月底计算一次）
        logger.info("  → 预计算月度因子信号...")
        self.monthly_signals = self._precompute_monthly_signals()
        logger.info(f"    - 共计算 {len(self.monthly_signals)} 个月的因子信号")
        
        logger.info("  ✓ 预计算完成")
    
    def _precompute_monthly_signals(self) -> dict[pd.Timestamp, pd.Series]:
        """
        预计算每个月底的因子信号
        
        实际动作:
        1. 找到每个月的最后一个交易日
        2. 对该月的因子数据进行去极值、填充、标准化处理
        3. 多因子合成得到综合因子得分
        4. 返回每个月底的因子得分序列
        """
        monthly_signals = {}
        
        # 找到每个月的最后一个交易日
        month_ends = []
        for i, date in enumerate(self.dm.trade_dates):
            if i == len(self.dm.trade_dates) - 1 or date.month != self.dm.trade_dates[i + 1].month:
                month_ends.append(date)
        
        logger.info(f"    - 找到 {len(month_ends)} 个月底交易日")
        
        for month_end in month_ends:
            # 获取该日期的可交易掩码
            if month_end not in self.universe.tradable.index:
                continue
            
            tradable_mask = self.universe.tradable.loc[month_end]
            
            # 处理每个因子
            processed_factors = {}
            for factor_name, factor_data in self.raw_factors.items():
                if month_end not in factor_data.index:
                    continue
                
                # 获取该日期的因子值
                raw_factor = factor_data.loc[[month_end]]
                
                # 因子处理管道
                processed = self.pipeline.process(raw_factor, tradable_mask)
                processed_factors[factor_name] = processed.loc[month_end]
            
            # 多因子合成
            if processed_factors:
                combined = self.combiner.combine(processed_factors)
                monthly_signals[month_end] = combined
        
        return monthly_signals
    
    def run(self) -> dict[str, Any]:
        """
        执行回测主循环
        
        实际动作:
        1. 遍历每个交易日
        2. 如果是月初第一个交易日，执行上月底生成的调仓订单（开盘价）
        3. 如果是月底最后一个交易日，计算因子信号并生成下月调仓订单
        4. 更新持仓市值（收盘价）
        """
        logger.info("\n" + "=" * 70)
        logger.info("【步骤4-7】执行回测主循环")
        logger.info("=" * 70)
        
        trade_dates = self.dm.trade_dates
        n_days = len(trade_dates)
        
        logger.info(f"  → 回测期间: {trade_dates[0].strftime('%Y-%m-%d')} 至 {trade_dates[-1].strftime('%Y-%m-%d')}")
        logger.info(f"  → 总交易日: {n_days}")
        
        # 识别月初和月末
        month_starts = []
        month_ends = []
        for i, date in enumerate(trade_dates):
            if i == 0 or date.month != trade_dates[i-1].month:
                month_starts.append(date)
            if i == len(trade_dates) - 1 or date.month != trade_dates[i+1].month:
                month_ends.append(date)
        
        logger.info(f"  → 月初交易日: {len(month_starts)} 个")
        logger.info(f"  → 月末交易日: {len(month_ends)} 个")
        
        # 回测主循环
        for i, date in enumerate(trade_dates):
            is_month_start = date in month_starts
            is_month_end = date in month_ends
            
            # 获取当日价格数据
            open_prices = self.dm.open.loc[date] if date in self.dm.open.index else None
            close_prices = self.dm.close.loc[date] if date in self.dm.close.index else None
            
            if open_prices is None or close_prices is None:
                continue
            
            # ==========================================
            # 步骤4: 执行调仓（月初第一个交易日开盘）
            # ==========================================
            if is_month_start and i > 0:
                self._execute_rebalance_at_open(date, i, open_prices, close_prices)
            
            # ==========================================
            # 步骤5: 计算因子信号（月末最后一个交易日收盘后）
            # ==========================================
            if is_month_end:
                self._compute_factor_signal(date, i, close_prices)
            
            # ==========================================
            # 步骤6: 更新持仓市值（每日收盘）
            # ==========================================
            self.tracker.update_market_values(date, close_prices)
            
            # 打印进度（每月第一天）
            if is_month_start:
                snapshot = self.tracker._snapshots[-1] if self.tracker._snapshots else None
                if snapshot:
                    logger.info(f"  [{date.strftime('%Y-%m-%d')}] 净值: {snapshot.total_value:,.0f}, "
                              f"累计收益: {snapshot.cumulative_return:.2%}, "
                              f"持仓: {len([p for p in snapshot.positions.values() if p.quantity > 0])} 只")
        
        logger.info("  ✓ 回测主循环完成")
        
        # 生成结果
        return self._generate_results()
    
    def _compute_factor_signal(self, date: pd.Timestamp, date_index: int, close_prices: pd.Series) -> None:
        """
        步骤5: 月末计算因子信号
        
        实际动作:
        1. 获取当日可交易股票掩码
        2. 对原始因子进行去极值处理（MAD方法）
        3. 缺失值填充（中位数）
        4. 标准化处理（Z-score）
        5. 多因子加权合成
        6. 使用组合优化器生成目标权重
        7. 计算目标持仓数量（考虑整手数100股）
        8. 生成买卖订单，存入_next_day_orders等待下月初执行
        """
        logger.info(f"\n  --- {date.strftime('%Y-%m-%d')} 月末因子计算 ---")
        
        # 1. 获取可交易掩码
        tradable_mask = self.universe.tradable.loc[date] if date in self.universe.tradable.index else None
        if tradable_mask is None:
            logger.warning("    无有效可交易掩码，跳过")
            return
        
        buyable_stocks = tradable_mask[tradable_mask].index.tolist()
        logger.info(f"    → 可交易股票: {len(buyable_stocks)} 只")
        
        # 2-5. 因子处理与合成
        processed_factors = {}
        for factor_name, factor_data in self.raw_factors.items():
            if date not in factor_data.index:
                continue
            
            raw_factor = factor_data.loc[[date]]
            
            # 异常值处理（去极值）
            logger.info(f"    → [{factor_name}] MAD去极值处理 (n={self.cfg.factor.winsorize_n})")
            processed = self.pipeline.process(raw_factor, tradable_mask)
            processed_factors[factor_name] = processed.loc[date]
        
        # 多因子合成
        if not processed_factors:
            logger.warning("    无有效因子数据，跳过")
            return
        
        logger.info(f"    → 多因子合成 (方法: {self.cfg.factor.combine_method})")
        combined_signal = self.combiner.combine(processed_factors)
        
        # 只保留可交易股票
        combined_signal = combined_signal[combined_signal.index.isin(buyable_stocks)].dropna()
        logger.info(f"    → 合成后有效信号: {len(combined_signal)} 只")
        
        # 6. 组合优化
        logger.info(f"    → 组合优化 (方法: {self.cfg.optimizer.method}, 目标: {self.cfg.optimizer.target_count} 只)")
        
        # 获取收益率数据用于风险模型
        returns_data = None
        if date_index >= self.cfg.optimizer.cov_lookback:
            start_idx = max(0, date_index - self.cfg.optimizer.cov_lookback)
            returns_slice = self.dm.returns.iloc[start_idx:date_index]
            returns_data = returns_slice[combined_signal.index.intersection(returns_slice.columns)]
        
        target_weights = self.optimizer.optimize(combined_signal, returns_data)
        
        if len(target_weights) == 0:
            logger.warning("    → 优化器未返回有效权重，跳过本次调仓")
            return
        
        logger.info(f"    → 优化后选中: {len(target_weights)} 只股票")
        logger.info(f"    → 最大权重: {target_weights.max():.2%}, 最小权重: {target_weights.min():.2%}")
        
        # 7. 计算目标持仓数量（整手数）
        total_value = self.tracker.get_total_value()
        target_quantities = {}
        
        for stock, weight in target_weights.items():
            if stock in close_prices and close_prices[stock] > 0:
                target_value = weight * total_value
                target_qty = int(target_value / close_prices[stock] / 100) * 100
                if target_qty > 0:
                    target_quantities[stock] = target_qty
        
        logger.info(f"    → 目标持仓计算完成: {len(target_quantities)} 只 (整手数优化)")
        
        # 8. 生成调仓订单
        self._generate_rebalance_orders(date, target_quantities, close_prices)
    
    def _generate_rebalance_orders(self, date: pd.Timestamp, target_quantities: dict, close_prices: pd.Series) -> None:
        """
        生成再平衡订单
        
        实际动作:
        1. 对比当前持仓和目标持仓
        2. 对需要卖出的股票生成SELL订单
        3. 对需要买入的股票生成BUY订单
        4. 订单存入_next_day_orders，等待下月初开盘执行
        """
        current_positions = self.tracker.get_all_positions()
        
        sell_orders = []
        buy_orders = []
        
        # 卖出当前持仓中不在目标中的股票
        for stock, position in current_positions.items():
            if stock not in target_quantities or target_quantities[stock] < position.quantity:
                sell_qty = position.quantity
                if stock in target_quantities:
                    sell_qty = position.quantity - target_quantities[stock]
                if sell_qty > 0:
                    sell_orders.append({
                        'stock': stock,
                        'side': OrderSide.SELL,
                        'quantity': sell_qty,
                        'create_date': date
                    })
        
        # 买入目标持仓中需要增加的股票
        for stock, target_qty in target_quantities.items():
            current_qty = current_positions.get(stock, None)
            current_qty = current_qty.quantity if current_qty else 0
            
            if target_qty > current_qty:
                buy_qty = target_qty - current_qty
                buy_orders.append({
                    'stock': stock,
                    'side': OrderSide.BUY,
                    'quantity': buy_qty,
                    'create_date': date
                })
        
        # 存入次日订单队列
        self._next_day_orders = sell_orders + buy_orders
        
        logger.info(f"    → 生成调仓订单: {len(sell_orders)} 笔卖出, {len(buy_orders)} 笔买入")
        logger.info(f"    → 订单将在下月初开盘时执行")
    
    def _execute_rebalance_at_open(self, date: pd.Timestamp, date_index: int, 
                                    open_prices: pd.Series, close_prices: pd.Series) -> None:
        """
        步骤4: 月初开盘执行调仓
        
        实际动作:
        1. 遍历_next_day_orders中的订单
        2. 使用开盘价执行卖出订单（先卖后买，释放资金）
        3. 使用开盘价执行买入订单
        4. 计算交易成本（佣金、印花税、滑点）
        5. 更新持仓和现金
        """
        if not self._next_day_orders:
            return
        
        logger.info(f"\n  --- {date.strftime('%Y-%m-%d')} 月初调仓执行 ---")
        
        # 先执行卖出订单（释放资金）
        sell_executed = 0
        for order_info in self._next_day_orders:
            if order_info['side'] == OrderSide.SELL:
                stock = order_info['stock']
                if stock in open_prices and open_prices[stock] > 0:
                    success, trade = self.executor.execute_order(
                        stock=stock,
                        side=OrderSide.SELL,
                        quantity=order_info['quantity'],
                        date=date,
                        open_price=open_prices[stock],
                        close_price=close_prices.get(stock)
                    )
                    if success and trade:
                        self.tracker.execute_trade(trade)
                        sell_executed += 1
        
        # 再执行买入订单
        buy_executed = 0
        for order_info in self._next_day_orders:
            if order_info['side'] == OrderSide.BUY:
                stock = order_info['stock']
                if stock in open_prices and open_prices[stock] > 0:
                    success, trade = self.executor.execute_order(
                        stock=stock,
                        side=OrderSide.BUY,
                        quantity=order_info['quantity'],
                        date=date,
                        open_price=open_prices[stock],
                        close_price=close_prices.get(stock)
                    )
                    if success and trade:
                        self.tracker.execute_trade(trade)
                        buy_executed += 1
        
        logger.info(f"    → 卖出执行: {sell_executed} 笔, 买入执行: {buy_executed} 笔")
        logger.info(f"    → 当前现金: {self.tracker.get_cash():,.0f}")
        
        # 清空订单队列
        self._next_day_orders = []
        self._last_rebalance_date = date
    
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        logger.info("\n" + "=" * 70)
        logger.info("【步骤8】生成回测结果")
        logger.info("=" * 70)
        
        snapshots = self.tracker.get_snapshots()
        trades_df = self.executor.trade_log.get_trades_df()
        
        # 性能分析
        analyzer = PerformanceAnalyzer()
        analyzer.set_data(snapshots, trades_df)
        metrics = analyzer.calculate_performance_metrics()
        
        logger.info("  → 回测性能指标:")
        logger.info(f"    - 累计收益率: {metrics.get('total_return', 0):.2%}")
        logger.info(f"    - 年化收益率: {metrics.get('annual_return', 0):.2%}")
        logger.info(f"    - 年化波动率: {metrics.get('annual_volatility', 0):.2%}")
        logger.info(f"    - 夏普比率: {metrics.get('sharpe_ratio', 0):.3f}")
        logger.info(f"    - 最大回撤: {metrics.get('max_drawdown', 0):.2%}")
        logger.info(f"    - 胜率: {metrics.get('win_rate', 0):.2%}")
        logger.info(f"    - 总交易次数: {metrics.get('total_trades', 0)}")
        logger.info(f"    - 换手率: {metrics.get('turnover_rate', 0):.2%}")
        
        return {
            'snapshots': snapshots,
            'trades_df': trades_df,
            'metrics': metrics,
            'tracker': self.tracker,
            'executor': self.executor
        }


# ============================================================
# 主程序
# ============================================================

def main():
    """主函数：运行完整的一年期因子回测"""
    
    logger.info("\n" + "=" * 70)
    logger.info("Factor Trading v3.0 - 完整因子回测演示")
    logger.info("策略: 价值+动量双因子 | 月度调仓 | 等权重优化")
    logger.info("=" * 70)
    
    # 设置路径
    data_dir = Path("./demo_data_full")
    output_dir = Path("./demo_output_full")
    
    # ============================================================
    # 步骤1: 生成数据
    # ============================================================
    data = generate_one_year_data(
        n_stocks=100,
        start_date="2024-01-02",
        end_date="2024-12-31",
        seed=42
    )
    save_data_to_pkl(data, data_dir)
    
    # ============================================================
    # 步骤2: 创建配置
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("【配置】创建回测配置")
    logger.info("=" * 70)
    
    config = BacktestConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        
        # 因子配置
        factor_files=['factor_value.pkl', 'factor_momentum.pkl'],
        factor_weights={'factor_value': 0.6, 'factor_momentum': 0.4},
        
        # 交易成本
        cost=CostConfig(
            commission_rate=0.0003,    # 万三佣金
            commission_min=5.0,        # 最低5元
            stamp_tax_rate=0.001,      # 千分之一印花税（卖出）
            slippage_pct=0.001         # 千分之一滑点
        ),
        
        # 股票池过滤
        universe=UniverseConfig(
            exclude_suspended=True,
            exclude_limit_up=True,
            exclude_limit_down=True,
            exclude_st=True,
            check_next_day_tradable=True
        ),
        
        # 因子处理
        factor=FactorConfig(
            winsorize_method='mad',      # MAD去极值
            winsorize_n=5.0,
            fill_method='median',        # 中位数填充
            standardize_method='zscore', # Z-score标准化
            combine_method='weighted_sum',
            factor_weights={'factor_value': 0.6, 'factor_momentum': 0.4}
        ),
        
        # 组合优化
        optimizer=OptimizerConfig(
            method='equal_weight',       # 等权重
            target_count=20,             # 持有20只股票
            max_weight=0.10,             # 最大10%
            round_lot=True               # 整手数
        ),
        
        # 再平衡（月度）
        rebalance=RebalanceConfig(
            method='fixed',
            frequency='monthly'          # 每月调仓
        ),
        
        # 回测参数
        initial_capital=10_000_000.0,    # 1000万初始资金
        enable_pending_orders=True,
        max_pending_days_buy=5,
        max_pending_days_sell=10
    )
    
    logger.info("  → 因子文件: factor_value.pkl (60%), factor_momentum.pkl (40%)")
    logger.info("  → 交易成本: 佣金万三(最低5元) + 印花税千一(卖出) + 滑点千一")
    logger.info("  → 股票池过滤: 排除停牌/涨停/跌停/ST")
    logger.info("  → 因子处理: MAD去极值 → 中位数填充 → Z-score标准化")
    logger.info("  → 组合优化: 等权重, 目标20只, 最大权重10%, 整手数")
    logger.info("  → 调仓频率: 月度（月底计算因子，月初开盘调仓）")
    logger.info("  → 初始资金: 10,000,000 元")
    
    # ============================================================
    # 步骤3-8: 运行回测
    # ============================================================
    engine = DetailedBacktestEngine(config, data_dir)
    engine.setup()
    results = engine.run()
    
    # ============================================================
    # 步骤9: 保存结果
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("【步骤9】保存回测结果")
    logger.info("=" * 70)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存交易记录
    trades_df = results['trades_df']
    trades_path = output_dir / "trades.csv"
    trades_df.to_csv(trades_path, index=False, encoding='utf-8-sig')
    logger.info(f"  → 交易记录已保存: {trades_path} ({len(trades_df)} 笔)")
    
    # 保存持仓快照
    snapshots_df = results['tracker'].get_snapshots_df()
    snapshots_path = output_dir / "snapshots.csv"
    snapshots_df.to_csv(snapshots_path, index=False, encoding='utf-8-sig')
    logger.info(f"  → 持仓快照已保存: {snapshots_path} ({len(snapshots_df)} 天)")
    
    # 生成报告
    analyzer = PerformanceAnalyzer()
    analyzer.set_data(results['snapshots'], trades_df)
    report_data = analyzer.generate_report(output_dir)
    logger.info(f"  → 回测报告已保存到: {output_dir}")
    
    # ============================================================
    # 最终总结
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("回测完成！")
    logger.info("=" * 70)
    logger.info(f"输出目录: {output_dir.absolute()}")
    logger.info(f"  - trades.csv: 交易记录")
    logger.info(f"  - snapshots.csv: 每日持仓快照")
    logger.info(f"  - performance_chart.png: 净值曲线")
    logger.info(f"  - monthly_returns_heatmap.png: 月度收益热图")
    logger.info(f"  - performance_report.txt: 文本报告")
    logger.info(f"  - performance_metrics.csv: 指标CSV")
    
    return results


if __name__ == "__main__":
    results = main()
