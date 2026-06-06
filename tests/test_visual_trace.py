"""
小样本可视化追溯工具

创建一个极简数据集（2只股票，5个交易日），手动计算预期收益，
与程序输出对比，验证全流程计算正确性。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def create_minimal_test_data(tmpdir: Path):
    """创建极简测试数据集：2只股票，5个交易日"""
    
    # 交易日历：2024-01-02 到 2024-01-08（5个交易日，跳过周末）
    trade_dates = pd.to_datetime([
        "2024-01-02", "2024-01-03", "2024-01-04", 
        "2024-01-05", "2024-01-08"
    ])
    stocks = ["STK01", "STK02"]
    
    # 交易日历
    pd.DataFrame(index=trade_dates).to_pickle(tmpdir / "trade_dates.pkl")
    
    # 价格数据（设计为可预测的收益）
    # STK01: 10 -> 11 -> 12 -> 13 -> 14 (每天+10%)
    # STK02: 20 -> 20 -> 20 -> 20 -> 20 (平盘)
    close_prices = pd.DataFrame({
        "STK01": [10.0, 11.0, 12.0, 13.0, 14.0],
        "STK02": [20.0, 20.0, 20.0, 20.0, 20.0],
    }, index=trade_dates)
    
    open_prices = pd.DataFrame({
        "STK01": [10.0, 11.0, 12.0, 13.0, 14.0],  # 开盘价=收盘价（简化）
        "STK02": [20.0, 20.0, 20.0, 20.0, 20.0],
    }, index=trade_dates)
    
    high_prices = close_prices * 1.01
    low_prices = close_prices * 0.99
    
    close_prices.to_pickle(tmpdir / "close.pkl")
    open_prices.to_pickle(tmpdir / "open.pkl")
    high_prices.to_pickle(tmpdir / "high.pkl")
    low_prices.to_pickle(tmpdir / "low.pkl")
    
    # 复权因子（无复权）
    pd.DataFrame({s: [1.0] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "stock_adj.pkl")
    
    # 停牌数据（全部正常）
    pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "suspend.pkl")
    
    # 行业数据
    pd.DataFrame({s: ["Tech"] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "industry.pkl")
    
    # ST数据（全部正常）
    pd.DataFrame({s: [False] * len(trade_dates) for s in stocks}, index=trade_dates).to_pickle(tmpdir / "st.pkl")
    
    # 因子数据：STK01因子值高（应该买入），STK02因子值低
    factor_data = pd.DataFrame({
        "STK01": [2.0, 2.0, 2.0, 2.0, 2.0],  # 高因子值
        "STK02": [1.0, 1.0, 1.0, 1.0, 1.0],  # 低因子值
    }, index=trade_dates)
    factor_data.to_pickle(tmpdir / "factor_test.pkl")
    
    return trade_dates, stocks, close_prices


def manual_calculate_expected():
    """手动计算预期收益
    
    业务逻辑：
    - 初始资金：100,000
    - 第1天收盘：信号显示STK01好，生成买入订单（次日执行）
    - 第2天开盘：买入STK01 5000股 @ 11元 = 55,000元
    - 第2天收盘：持仓市值 = 5000 * 11 = 55,000，现金 = 45,000，总价值 = 100,000
    - 第3天开盘：无操作
    - 第3天收盘：持仓市值 = 5000 * 12 = 60,000，总价值 = 105,000
    - ...
    
    注意：由于我们使用简化模型（信号直接等于因子），且再平衡触发条件需要检查
    """
    print("=" * 70)
    print("手动计算预期收益")
    print("=" * 70)
    
    initial_capital = 100_000.0
    
    # 简化假设：第1天收盘信号触发，买入STK01和STK02
    # 目标：等权重，每只50%
    # 第2天开盘买入 STK01 @ 11元, STK02 @ 20元
    buy_price_1 = 11.0
    buy_price_2 = 20.0
    target_value = initial_capital * 0.5 * 0.985  # 50%权重，预留1.5%缓冲
    quantity_1 = int((target_value / buy_price_1) / 100) * 100  # 整手
    quantity_2 = int((target_value / buy_price_2) / 100) * 100  # 整手
    
    print(f"初始资金: {initial_capital:,.2f}")
    print(f"目标持仓: STK01 {quantity_1}股 @ {buy_price_1:.2f}, STK02 {quantity_2}股 @ {buy_price_2:.2f}")
    print(f"买入金额: STK01={quantity_1 * buy_price_1:,.2f}, STK02={quantity_2 * buy_price_2:,.2f}")
    
    # 计算每日预期价值（简化，忽略成本）
    prices_1 = [11.0, 12.0, 13.0, 14.0]  # STK01第2天到第5天的价格
    prices_2 = [20.0, 20.0, 20.0, 20.0]  # STK02第2天到第5天的价格（平盘）
    cash = initial_capital - quantity_1 * buy_price_1 - quantity_2 * buy_price_2
    
    print(f"\n每日预期总价值（忽略成本）:")
    print(f"  第1天(2024-01-02): {initial_capital:,.2f} (初始)")
    
    for i, (p1, p2) in enumerate(zip(prices_1, prices_2)):
        day_value = quantity_1 * p1 + quantity_2 * p2 + cash
        prev_value = quantity_1 * (prices_1[i-1] if i > 0 else buy_price_1) + quantity_2 * (prices_2[i-1] if i > 0 else buy_price_2) + cash
        daily_return = (day_value - prev_value) / prev_value if i > 0 else 0
        print(f"  第{i+2}天: 持仓1={quantity_1 * p1:,.2f}, 持仓2={quantity_2 * p2:,.2f}, 现金={cash:,.2f}, 总价值={day_value:,.2f}, 日收益={daily_return:.2%}")
    
    final_value = quantity_1 * prices_1[-1] + quantity_2 * prices_2[-1] + cash
    total_return = (final_value - initial_capital) / initial_capital
    print(f"\n最终总价值: {final_value:,.2f}")
    print(f"总收益率: {total_return:.2%}")
    
    return {
        'initial_capital': initial_capital,
        'quantity_1': quantity_1,
        'quantity_2': quantity_2,
        'cash': cash,
        'final_value': final_value,
        'total_return': total_return,
    }


def run_engine_and_trace():
    """运行回测引擎并输出详细追溯信息"""
    print("\n" + "=" * 70)
    print("回测引擎实际运行结果")
    print("=" * 70)
    
    from core.data import DataManager
    from core.config import BacktestConfig
    from core.engine import BacktestEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        trade_dates, stocks, close_prices = create_minimal_test_data(tmpdir)
        
        # 创建配置
        from core.config import OptimizerConfig, RebalanceConfig, UniverseConfig
        config = BacktestConfig(
            data_dir=tmpdir,
            factor_files=["factor_test.pkl"],
            initial_capital=100_000.0,
            enable_pending_orders=False,  # 简化：不使用待执行队列
            adjustment_type='forward',
            optimizer=OptimizerConfig(method='equal_weight', target_count=2),  # 2只股票，各50%
            rebalance=RebalanceConfig(method='fixed', frequency='N_days', n_days=2),  # 每2天再平衡
            universe=UniverseConfig(
                exclude_suspended=False,
                exclude_limit_up=False,
                exclude_limit_down=False,
                exclude_st=False,
                check_next_day_tradable=False,
            ),
        )
        
        # 运行回测
        engine = BacktestEngine(config)
        engine.setup()
        results = engine.run()
        
        # 输出每日快照
        snapshots = engine.tracker.get_snapshots()
        trades_df = engine.executor.trade_log.get_trades_df()
        
        print(f"\n每日组合快照:")
        print(f"{'日期':<12} {'现金':>12} {'总价值':>12} {'日收益':>10} {'累计收益':>10}")
        print("-" * 60)
        
        for snap in snapshots:
            print(f"{str(snap.date)[:10]:<12} {snap.cash:>12,.2f} {snap.total_value:>12,.2f} {snap.daily_return:>10.2%} {snap.cumulative_return:>10.2%}")
        
        # 输出交易记录
        if not trades_df.empty:
            print(f"\n交易记录:")
            print(trades_df.to_string(index=False))
        else:
            print(f"\n无交易记录")
        
        # 输出持仓详情
        positions = engine.tracker.get_all_positions()
        if positions:
            print(f"\n最终持仓:")
            for stock, pos in positions.items():
                print(f"  {stock}: {pos.quantity}股, 成本={pos.avg_cost:.2f}, 市值={pos.market_value:.2f}")
        
        return {
            'snapshots': snapshots,
            'trades': trades_df,
            'positions': positions,
            'final_value': snapshots[-1].total_value if snapshots else config.initial_capital,
        }


def compare_and_verify():
    """对比手动计算和引擎输出，验证正确性"""
    print("\n" + "=" * 70)
    print("对比验证")
    print("=" * 70)
    
    expected = manual_calculate_expected()
    actual = run_engine_and_trace()
    
    print(f"\n{'='*70}")
    print("验证结果")
    print(f"{'='*70}")
    
    print(f"预期最终价值: {expected['final_value']:,.2f}")
    print(f"实际最终价值: {actual['final_value']:,.2f}")
    
    diff = actual['final_value'] - expected['final_value']
    diff_pct = diff / expected['final_value'] if expected['final_value'] > 0 else 0
    
    print(f"差异: {diff:,.2f} ({diff_pct:.2%})")
    
    if abs(diff_pct) < 0.01:  # 1%以内认为正确
        print(f"✓ 计算正确（差异<1%）")
        return True
    else:
        print(f"✗ 计算可能有误（差异>1%），需要排查")
        return False


def run_all_tests():
    """运行可视化追溯测试"""
    print("=" * 70)
    print("小样本可视化追溯测试")
    print("=" * 70)
    
    success = compare_and_verify()
    
    print(f"\n{'='*70}")
    print(f"测试结果: {'✓ 通过' if success else '✗ 失败'}")
    print(f"{'='*70}")
    
    return success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
