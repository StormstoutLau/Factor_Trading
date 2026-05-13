#!/usr/bin/env python3
"""
全时段回测 - 修复版 (2020-2026)
后复权价格，选股10只
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path.cwd()))

from config import BacktestConfig, OptimizerConfig, RebalanceConfig, CostConfig, UniverseConfig, FactorConfig
from data import DataManager
from engine import BacktestEngine

print("="*70)
print("全时段回测 (2020-2026) - 修复版")
print("="*70)

# 基础配置
base_config = BacktestConfig(
    data_dir=Path('E:/Ashare_data/market_data'),
    close_file='stock_close.pkl',
    open_file='stock_open.pkl',
    adj_factor_file='stock_adj.pkl',
    adjustment_type='backward',  # 后复权
    factor_files=['UTR_turnover_new.pkl'],
    factor_weights={'UTR_turnover_new': 1.0},
    initial_capital=10_000_000.0,
    start_date='2020-01-23',
    end_date='2026-02-09',  # 数据实际截止日期
    rebalance=RebalanceConfig(method='fixed', frequency='monthly'),
    cost=CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001),
    universe=UniverseConfig(exclude_suspended=False, exclude_limit_up=True, exclude_limit_down=True),
    factor=FactorConfig(winsorize_method='none', standardize_method='none', fill_method='none', neutralize=False, reverse_factor=False),
    enable_pending_orders=True,
)

def run_strategy(name, select_top, target_count):
    print(f"\n{'='*70}")
    print(f"【{name}】选股: {target_count}只")
    print(f"{'='*70}")
    
    config = base_config
    config.optimizer = OptimizerConfig(method='equal_weight', target_count=target_count, select_top=select_top)
    config.output_dir = Path(f'E:/Ashare_data/output/full_backtest_2026_{name.replace(" ", "_")}')
    
    try:
        engine = BacktestEngine(config)
        engine.setup()
        
        print(f"交易日数: {len(engine.dm.trade_dates)}")
        print(f"日期范围: {engine.dm.trade_dates[0].strftime('%Y-%m-%d')} ~ {engine.dm.trade_dates[-1].strftime('%Y-%m-%d')}")
        
        # 检查因子
        if engine._composite_signal is not None:
            nan_ratio = engine._composite_signal.isna().sum().sum() / (engine._composite_signal.shape[0] * engine._composite_signal.shape[1])
            print(f"合成因子NaN比例: {nan_ratio*100:.2f}%")
            
            if nan_ratio > 0.99:
                print("错误: 因子数据几乎全部缺失!")
                return None
        
        result = engine.run()
        pv = result.get('portfolio_value', pd.Series())
        
        if len(pv) > 0:
            total_ret = (pv.iloc[-1] / pv.iloc[0] - 1) * 100
            days = len(pv)
            annual_ret = total_ret * (252 / days) if days > 0 else 0
            
            # 最大回撤
            cummax = pv.cummax()
            max_dd = ((pv - cummax) / cummax).min() * 100
            
            print(f"\n✓ 回测成功")
            print(f"  总收益率: {total_ret:.2f}%")
            print(f"  年化收益: {annual_ret:.2f}%")
            print(f"  最大回撤: {max_dd:.2f}%")
            print(f"  交易日数: {days}")
            
            return {'return': total_ret, 'annual': annual_ret, 'max_dd': max_dd, 'days': days}
        else:
            print("✗ 回测结果为空")
            return None
            
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None

# 运行两个策略
long_result = run_strategy("多头Top10", True, 10)
short_result = run_strategy("空头Bottom10", False, 10)

# 汇总
print("\n" + "="*70)
print("【汇总结果】")
print("="*70)
if long_result and short_result:
    print(f"多头Top10:    {long_result['return']:>8.2f}% (年化 {long_result['annual']:>6.2f}%)")
    print(f"空头Bottom10: {short_result['return']:>8.2f}% (年化 {short_result['annual']:>6.2f}%)")
    print(f"多空差:       {long_result['return'] - short_result['return']:>+8.2f}%")
print("="*70)
