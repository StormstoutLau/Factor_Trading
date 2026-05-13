#!/usr/bin/env python3
"""
单策略回测 - 2020-2026 全时段
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path.cwd()))

from config import BacktestConfig, OptimizerConfig, RebalanceConfig, CostConfig, UniverseConfig, FactorConfig
from engine import BacktestEngine

print("="*70)
print("全时段回测 (2020-2026)")
print("="*70)

# 配置
config = BacktestConfig(
    data_dir=Path('E:/Ashare_data/market_data'),
    output_dir=Path('E:/Ashare_data/output/full_backtest_2026'),
    close_file='stock_close.pkl',
    open_file='stock_open.pkl',
    adj_factor_file='stock_adj.pkl',
    adjustment_type='backward',
    factor_files=['UTR_turnover_new.pkl'],
    factor_weights={'UTR_turnover_new': 1.0},
    initial_capital=10_000_000.0,
    start_date='2020-01-23',
    end_date='2026-02-09',
    optimizer=OptimizerConfig(method='equal_weight', target_count=10, select_top=True),
    rebalance=RebalanceConfig(method='fixed', frequency='monthly'),
    cost=CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001),
    universe=UniverseConfig(exclude_suspended=False, exclude_limit_up=True, exclude_limit_down=True),
    factor=FactorConfig(winsorize_method='none', standardize_method='none', fill_method='none', neutralize=False, reverse_factor=False),
    enable_pending_orders=True,
)

print("\n【多头Top10】初始化引擎...")
engine = BacktestEngine(config)

print("设置引擎...")
engine.setup()

print(f"交易日数: {len(engine.dm.trade_dates)}")
print(f"日期范围: {engine.dm.trade_dates[0]} ~ {engine.dm.trade_dates[-1]}")

# 检查因子
nan_ratio = engine._composite_signal.isna().sum().sum() / (engine._composite_signal.shape[0] * engine._composite_signal.shape[1])
print(f"合成信号NaN比例: {nan_ratio*100:.2f}%")

print("\n开始回测...")
result = engine.run()

pv = result.get('portfolio_value', pd.Series())
print(f"\n回测完成!")
print(f"组合价值序列长度: {len(pv)}")

if len(pv) > 0:
    total_return = (pv.iloc[-1] / pv.iloc[0] - 1) * 100
    days = len(pv)
    annual_return = total_return * (252 / days)
    
    # 最大回撤
    cummax = pv.cummax()
    max_drawdown = ((pv - cummax) / cummax).min() * 100
    
    # 【新增】年化波动率
    daily_returns = pv.pct_change().dropna()
    annual_volatility = daily_returns.std() * np.sqrt(252) * 100
    
    print(f"\n【结果】")
    print(f"  起始净值: {pv.iloc[0]:,.0f}")
    print(f"  结束净值: {pv.iloc[-1]:,.0f}")
    print(f"  总收益率: {total_return:.2f}%")
    print(f"  年化收益: {annual_return:.2f}%")
    print(f"  年化波动: {annual_volatility:.2f}%")  # 【新增】
    print(f"  最大回撤: {max_drawdown:.2f}%")
    print(f"  交易日数: {days}")
    
    # 保存结果
    result_df = pd.DataFrame({
        'date': pv.index,
        'portfolio_value': pv.values
    })
    result_df.to_csv('E:/Ashare_data/output/full_backtest_2026/long_top10_results.csv', index=False)
    print(f"\n结果已保存!")
else:
    print("回测失败: 无组合价值数据")
