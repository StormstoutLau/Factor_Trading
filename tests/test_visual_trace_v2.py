"""
小样本可视化追溯工具 V2 - 详细诊断版

输出每一步的详细计算过程，便于排查问题。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_data(tmpdir: Path):
    """创建极简测试数据集：2只股票，5个交易日"""
    trade_dates = pd.to_datetime([
        "2024-01-02", "2024-01-03", "2024-01-04", 
        "2024-01-05", "2024-01-08"
    ])
    stocks = ["STK01", "STK02"]
    
    pd.DataFrame(index=trade_dates).to_pickle(tmpdir / "trade_dates.pkl")
    
    close_prices = pd.DataFrame({
        "STK01": [10.0, 11.0, 12.0, 13.0, 14.0],
        "STK02": [20.0, 20.0, 20.0, 20.0, 20.0],
    }, index=trade_dates)
    
    open_prices = pd.DataFrame({
        "STK01": [10.0, 11.0, 12.0, 13.0, 14.0],
        "STK02": [20.0, 20.0, 20.0, 20.0, 20.0],
    }, index=trade_dates)
    
    close_prices.to_pickle(tmpdir / "close.pkl")
    open_prices.to_pickle(tmpdir / "open.pkl")
    (close_prices * 1.01).to_pickle(tmpdir / "high.pkl")
    (close_prices * 0.99).to_pickle(tmpdir / "low.pkl")
    
    pd.DataFrame({s: [1.0] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "stock_adj.pkl")
    pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "suspend.pkl")
    pd.DataFrame({s: ["Tech"] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "industry.pkl")
    pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "st.pkl")
    
    factor_data = pd.DataFrame({
        "STK01": [2.0, 2.0, 2.0, 2.0, 2.0],
        "STK02": [1.0, 1.0, 1.0, 1.0, 1.0],
    }, index=trade_dates)
    factor_data.to_pickle(tmpdir / "factor_test.pkl")
    
    return trade_dates, stocks, close_prices, open_prices


def run_detailed_trace():
    """运行详细追溯"""
    print("=" * 80)
    print("小样本详细追溯诊断")
    print("=" * 80)
    
    from core.data import DataManager
    from core.config import BacktestConfig, OptimizerConfig, RebalanceConfig, UniverseConfig
    from core.engine import BacktestEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        trade_dates, stocks, close_prices, open_prices = create_test_data(tmpdir)
        
        config = BacktestConfig(
            data_dir=tmpdir,
            factor_files=["factor_test.pkl"],
            initial_capital=100_000.0,
            enable_pending_orders=False,
            adjustment_type='forward',
            optimizer=OptimizerConfig(method='equal_weight', target_count=2),
            rebalance=RebalanceConfig(method='fixed', frequency='N_days', n_days=2),
            universe=UniverseConfig(
                exclude_suspended=False,
                exclude_limit_up=False,
                exclude_limit_down=False,
                exclude_st=False,
                check_next_day_tradable=False,
            ),
        )
        
        engine = BacktestEngine(config)
        engine.setup()
        
        print("\n【价格数据】")
        print(close_prices.to_string())
        
        print("\n【因子数据】")
        print(engine.dm.load_factor("factor_test.pkl").to_string())
        
        # 手动执行每一天，输出详细日志
        print("\n" + "=" * 80)
        print("逐日执行追溯")
        print("=" * 80)
        
        dm = engine.dm
        tracker = engine.tracker
        executor = engine.executor
        
        for i, date in enumerate(dm.trade_dates):
            print(f"\n{'='*60}")
            print(f"日期: {date.strftime('%Y-%m-%d')} (索引 {i})")
            print(f"{'='*60}")
            
            # 1. 执行次日订单
            engine._execute_next_day_orders(date, i)
            
            # 2. 检查再平衡
            should_rebalance = engine.trigger.should_trigger(date)
            print(f"  再平衡触发: {should_rebalance}")
            
            if should_rebalance:
                # 获取信号
                signal = engine._composite_signal.loc[date]
                print(f"  信号值: STK01={signal.get('STK01', 'N/A'):.2f}, STK02={signal.get('STK02', 'N/A'):.2f}")
                
                # 获取可交易掩码
                buyable = engine.universe.buyable.loc[date] if hasattr(engine.universe, 'buyable') else None
                if buyable is not None:
                    print(f"  可买入掩码: STK01={buyable.get('STK01', True)}, STK02={buyable.get('STK02', True)}")
                
                # 执行再平衡
                engine._execute_rebalance(date, i)
            
            # 3. 更新市值
            close_today = dm.get_adj_price('close', config.adjustment_type).loc[date]
            tracker.update_market_values(date, close_today)
            
            # 输出当日状态
            print(f"  当日收盘后状态:")
            print(f"    现金: {tracker.get_cash():,.2f}")
            print(f"    总市值: {tracker.get_total_value():,.2f}")
            positions = tracker.get_all_positions()
            if positions:
                for stock, pos in positions.items():
                    print(f"    持仓 {stock}: {pos.quantity}股, 市值={pos.market_value:,.2f}")
            else:
                print(f"    持仓: 无")
        
        # 最后一日强制平仓
        print(f"\n{'='*60}")
        print("最后交易日强制平仓")
        print(f"{'='*60}")
        engine._force_liquidation(dm.trade_dates[-1], len(dm.trade_dates) - 1)
        
        # 最终状态（_force_liquidation已更新市值）
        print(f"\n最终状态:")
        print(f"  现金: {tracker.get_cash():,.2f}")
        print(f"  总市值: {tracker.get_total_value():,.2f}")
        
        # 交易记录
        trades_df = executor.trade_log.get_trades_df()
        if not trades_df.empty:
            print(f"\n【交易记录汇总】")
            print(trades_df.to_string(index=False))
            
            total_cost = trades_df['cost'].sum()
            print(f"\n总交易成本: {total_cost:,.2f}")
        
        # 手动验证
        print(f"\n{'='*80}")
        print("手动验证计算")
        print(f"{'='*80}")
        
        # 根据交易记录手动计算
        # 第1次: 买入STK01 4900股 @ 11 = 53900, 成本70.07, 现金=100000-53970.07=46029.93
        # 第2次: 卖出STK01 800股 @ 13 = 10400, 成本25.80, 现金=46029.93+10374.20=56404.13
        #        买入STK02 2400股 @ 20 = 48000, 成本62.40, 现金=56404.13-48062.40=8341.73
        # 第3次: 卖出STK01 4100股 @ 14 = 57400, 成本132.02, 现金=8341.73+57267.98=65609.71
        #        卖出STK02 2400股 @ 20 = 48000, 成本110.40, 现金=65609.71+47889.60=113499.31
        
        print("预期最终现金: ~113,499.31")
        print(f"实际最终现金: {tracker.get_cash():,.2f}")
        print(f"差异: {tracker.get_cash() - 113499.31:,.2f}")


def run_all_tests():
    run_detailed_trace()
    print(f"\n{'='*80}")
    print("追溯完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    run_all_tests()
