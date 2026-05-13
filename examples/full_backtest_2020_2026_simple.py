"""
简化版全时段回测脚本 (2020-2026)
直接使用DataManager加载的因子数据，跳过FactorPipeline
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path.cwd()))

from config import BacktestConfig, OptimizerConfig, RebalanceConfig, CostConfig, UniverseConfig, FactorConfig
from data import DataManager
from engine import BacktestEngine

print("="*70)
print("【简化版全时段回测】多头(Top10) vs 空头(Bottom10) - 后复权")
print("="*70)

def run_simplified_backtest(strategy_name, select_top_value, target_count_value):
    """简化版回测 - 使用DataManager直接加载的因子"""
    print(f"\n{'='*70}")
    print(f"策略: {strategy_name} | 选股: {target_count_value}只")
    print(f"{'='*70}")
    
    config = BacktestConfig(
        data_dir=Path('E:/Ashare_data/market_data'),
        output_dir=Path(f'E:/Ashare_data/output/full_backtest_2026_{strategy_name.replace(" ", "_")}'),
        close_file='stock_close.pkl',
        open_file='stock_open.pkl',
        adj_factor_file='stock_adj.pkl',
        adjustment_type='backward',  # 【后复权】
        factor_files=['UTR_turnover_new.pkl'],
        factor_weights={'UTR_turnover_new': 1.0},
        initial_capital=10_000_000.0,
        start_date='2020-01-23',
        end_date='2026-02-09',  # 价格数据实际截止日期
        optimizer=OptimizerConfig(
            method='equal_weight', 
            target_count=target_count_value,
            select_top=select_top_value
        ),
        rebalance=RebalanceConfig(method='fixed', frequency='monthly'),
        cost=CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001),
        universe=UniverseConfig(exclude_suspended=False, exclude_limit_up=True, exclude_limit_down=True),
        # 【关键】禁用所有因子预处理
        factor=FactorConfig(
            winsorize_method='none',
            standardize_method='none', 
            fill_method='none',
            neutralize=False,
            reverse_factor=False
        ),
        enable_pending_orders=True,
    )
    
    print("初始化DataManager...")
    dm = DataManager(config)
    print(f"  交易日数: {len(dm.trade_dates)}")
    print(f"  日期范围: {dm.trade_dates[0].strftime('%Y-%m-%d')} ~ {dm.trade_dates[-1].strftime('%Y-%m-%d')}")
    
    # 直接加载因子数据（已通过对齐处理）
    print("加载因子数据...")
    raw_factor = dm.load_factor('UTR_turnover_new.pkl')
    print(f"  因子形状: {raw_factor.shape}")
    print(f"  NaN比例: {raw_factor.isna().sum().sum() / (raw_factor.shape[0] * raw_factor.shape[1]) * 100:.2f}%")
    
    # 检查因子是否有效
    if raw_factor.isna().all().all():
        print("错误: 因子数据全部为NaN!")
        return None
    
    # 创建全True的可交易掩码（简化处理）
    tradable_mask = pd.DataFrame(True, index=raw_factor.index, columns=raw_factor.columns)
    
    # 手动设置复合信号（跳过FactorPipeline）
    from factor import FactorCombiner
    combiner = FactorCombiner(['UTR_turnover_new.pkl'], {'UTR_turnover_new': 1.0})
    processed = {'UTR_turnover_new': raw_factor}
    composite_signal = combiner.combine(processed)
    
    print(f"  复合信号形状: {composite_signal.shape}")
    print(f"  复合信号NaN比例: {composite_signal.isna().sum().sum() / (composite_signal.shape[0] * composite_signal.shape[1]) * 100:.2f}%")
    
    # 初始化回测引擎
    print("初始化BacktestEngine...")
    engine = BacktestEngine(config)
    engine.dm = dm
    
    # 手动设置关键组件
    from filter import UniverseFilter
    from portfolio import build_optimizer
    from rebalance import build_trigger
    from execution import ExecutionSimulator
    from tracker import PositionTracker
    from pending import PendingOrderQueue
    
    engine.universe = UniverseFilter(dm, config.universe)
    engine.pipeline = None  # 不使用pipeline
    engine.combiner = combiner
    engine._composite_signal = composite_signal
    engine._returns_matrix = dm.returns.values
    engine.optimizer = build_optimizer(config.optimizer)
    engine.trigger = build_trigger(config.rebalance, engine.optimizer)
    engine.executor = ExecutionSimulator(config.cost)
    engine.tracker = PositionTracker(config.initial_capital)
    engine.pending_queue = PendingOrderQueue(
        max_pending_days_buy=config.max_pending_days_buy,
        max_pending_days_sell=config.max_pending_days_sell
    )
    
    print("运行回测...")
    result = engine.run()
    portfolio_value = result.get('portfolio_value', pd.Series())
    
    if len(portfolio_value) > 0:
        total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
        days = len(portfolio_value)
        annual_return = total_return * (252 / days) if days > 0 else 0
        
        # 计算最大回撤
        cummax = portfolio_value.cummax()
        drawdown = (portfolio_value - cummax) / cummax
        max_drawdown = drawdown.min() * 100
        
        print(f"\n  回测完成!")
        print(f"     起始净值: {portfolio_value.iloc[0]:,.0f}")
        print(f"     结束净值: {portfolio_value.iloc[-1]:,.0f}")
        print(f"     总收益率: {total_return:.2f}%")
        print(f"     年化收益: {annual_return:.2f}%")
        print(f"     最大回撤: {max_drawdown:.2f}%")
        print(f"     交易日数: {days}")
        
        return {
            'portfolio': portfolio_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'days': days,
            'name': strategy_name
        }
    else:
        print(f"  回测结果为空")
        return None

if __name__ == "__main__":
    # 1. 多头策略 (Top 10)
    result_long = run_simplified_backtest(
        "多头Top10", 
        select_top_value=True,
        target_count_value=10
    )

    # 2. 空头策略 (Bottom 10)
    result_short = run_simplified_backtest(
        "空头Bottom10",
        select_top_value=False,
        target_count_value=10
    )

    # 汇总结果
    print("\n" + "="*70)
    print("【全时段回测结果汇总 (2020-2026, 后复权)】")
    print("="*70)

    if result_long and result_short:
        print(f"\n{'策略':<20} {'总收益率':>12} {'年化收益':>12} {'最大回撤':>12} {'交易天数':>10}")
        print("-"*70)
        print(f"{result_long['name']:<20} {result_long['total_return']:>11.2f}% {result_long['annual_return']:>11.2f}% {result_long['max_drawdown']:>11.2f}% {result_long['days']:>10}")
        print(f"{result_short['name']:<20} {result_short['total_return']:>11.2f}% {result_short['annual_return']:>11.2f}% {result_short['max_drawdown']:>11.2f}% {result_short['days']:>10}")
        
        excess = result_long['total_return'] - result_short['total_return']
        print(f"\n多头 - 空头 = {excess:+.2f}%")

    print("\n" + "="*70)
    print("全时段回测完成 (2020-2026, 后复权)")
    print("="*70)
