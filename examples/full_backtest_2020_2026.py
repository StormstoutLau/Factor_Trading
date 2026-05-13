"""
全时段回测脚本 (2020-2026)
多头Top10 vs 空头Bottom10，后复权价格
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

# 导入项目模块
from config import BacktestConfig, OptimizerConfig, RebalanceConfig, CostConfig, UniverseConfig, FactorConfig
from engine import BacktestEngine

print("="*70)
print("【全时段回测】多头(Top10) vs 空头(Bottom10) - 后复权价格")
print("="*70)

def run_full_backtest_2026(strategy_name, select_top_value, target_count_value, 
                           start_date='2020-01-23', end_date='2026-02-09'):
    """
    运行全时段回测（2020-2026，后复权）
    """
    print(f"\n{'='*70}")
    print(f"策略: {strategy_name} | 选股: {target_count_value}只 | 区间: {start_date} ~ {end_date}")
    print(f"{'='*70}")
    
    config_full = BacktestConfig(
        data_dir=Path('E:/Ashare_data/market_data'),
        output_dir=Path(f'E:/Ashare_data/output/full_backtest_2026_{strategy_name.replace(" ", "_")}'),
        close_file='stock_close.pkl',
        open_file='stock_open.pkl',
        adj_factor_file='stock_adj.pkl',
        adjustment_type='backward',  # 【后复权】
        factor_files=['UTR_turnover_new.pkl'],
        factor_weights={'UTR_turnover_new': 1.0},
        initial_capital=10_000_000.0,
        start_date=start_date,
        end_date=end_date,
        optimizer=OptimizerConfig(
            method='equal_weight', 
            target_count=target_count_value,
            select_top=select_top_value
        ),
        rebalance=RebalanceConfig(method='fixed', frequency='monthly'),
        cost=CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001),
        universe=UniverseConfig(exclude_suspended=False, exclude_limit_up=True, exclude_limit_down=True),
        factor=FactorConfig(winsorize_method='none', standardize_method='none', fill_method='none', neutralize=False, reverse_factor=False),
        enable_pending_orders=True,
    )
    
    engine_full = BacktestEngine(config_full)
    engine_full.setup()
    
    print(f"  交易日数: {len(engine_full.dm.trade_dates)}")
    print(f"  初始资金: {config_full.initial_capital:,.0f}元")
    print(f"  选股数量: {target_count_value}只")
    print(f"  日期范围: {engine_full.dm.trade_dates[0].strftime('%Y-%m-%d')} ~ {engine_full.dm.trade_dates[-1].strftime('%Y-%m-%d')}")
    
    # 运行回测
    result = engine_full.run()
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

# 运行回测
if __name__ == "__main__":
    # 1. 多头策略 (Top 10)
    result_long_top10 = run_full_backtest_2026(
        "多头Top10", 
        select_top_value=True,
        target_count_value=10
    )

    # 2. 空头策略 (Bottom 10)
    result_short_bottom10 = run_full_backtest_2026(
        "空头Bottom10",
        select_top_value=False,
        target_count_value=10
    )

    # 汇总结果
    print("\n" + "="*70)
    print("【全时段回测结果汇总 (2020-2026, 后复权)】")
    print("="*70)

    if result_long_top10 and result_short_bottom10:
        print(f"\n{'策略':<20} {'总收益率':>12} {'年化收益':>12} {'最大回撤':>12} {'交易天数':>10}")
        print("-"*70)
        print(f"{result_long_top10['name']:<20} {result_long_top10['total_return']:>11.2f}% {result_long_top10['annual_return']:>11.2f}% {result_long_top10['max_drawdown']:>11.2f}% {result_long_top10['days']:>10}")
        print(f"{result_short_bottom10['name']:<20} {result_short_bottom10['total_return']:>11.2f}% {result_short_bottom10['annual_return']:>11.2f}% {result_short_bottom10['max_drawdown']:>11.2f}% {result_short_bottom10['days']:>10}")
        
        # 计算超额收益
        excess = result_long_top10['total_return'] - result_short_bottom10['total_return']
        print(f"\n多头 - 空头 = {excess:+.2f}%")

    print("\n" + "="*70)
    print("全时段回测完成 (2020-2026, 后复权)")
    print("="*70)
