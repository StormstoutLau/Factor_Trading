#!/usr/bin/env python3
"""
最小化全时段回测脚本 (2020-2026)
直接运行，无Notebook开销
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path.cwd()))

from config import BacktestConfig, OptimizerConfig, RebalanceConfig, CostConfig, UniverseConfig, FactorConfig
from data import DataManager
from engine import BacktestEngine

print("="*70)
print("全时段回测 (2020-2026, 后复权)")
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

# 多头策略
print("\n【多头Top10】")
config_long = config
config_long.optimizer = OptimizerConfig(method='equal_weight', target_count=10, select_top=True)
config_long.output_dir = Path('E:/Ashare_data/output/full_backtest_2026_long')

engine_long = BacktestEngine(config_long)
engine_long.setup()
print(f"交易日: {len(engine_long.dm.trade_dates)}天")
result_long = engine_long.run()
pv_long = result_long.get('portfolio_value', pd.Series())

if len(pv_long) > 0:
    ret_long = (pv_long.iloc[-1] / pv_long.iloc[0] - 1) * 100
    print(f"总收益: {ret_long:.2f}%")
else:
    ret_long = 0
    print("回测失败")

# 空头策略
print("\n【空头Bottom10】")
config_short = config
config_short.optimizer = OptimizerConfig(method='equal_weight', target_count=10, select_top=False)
config_short.output_dir = Path('E:/Ashare_data/output/full_backtest_2026_short')

engine_short = BacktestEngine(config_short)
engine_short.setup()
result_short = engine_short.run()
pv_short = result_short.get('portfolio_value', pd.Series())

if len(pv_short) > 0:
    ret_short = (pv_short.iloc[-1] / pv_short.iloc[0] - 1) * 100
    print(f"总收益: {ret_short:.2f}%")
else:
    ret_short = 0
    print("回测失败")

# 汇总
print("\n" + "="*70)
print("【汇总】")
print(f"多头Top10: {ret_long:.2f}%")
print(f"空头Bottom10: {ret_short:.2f}%")
print(f"多空差: {ret_long - ret_short:+.2f}%")
print("="*70)
