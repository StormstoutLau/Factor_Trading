#!/usr/bin/env python3
"""演示程序 - 生成合成数据并运行完整回测

这个演示验证了整个端到端的流程，不需要真实数据。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ======================================================================
# 合成数据生成
# ======================================================================

def generate_synthetic_data(
    n_stocks: int = 200,
    n_days: int = 500,
    data_dir: str = "demo_data",
    seed: int = 42,
):
    """创建逼真的A股数据
    
    Args:
        n_stocks: 股票数量
        n_days: 交易天数
        data_dir: 数据目录
        seed: 随机种子
        
    Returns:
        数据路径
    """
    rng = np.random.default_rng(seed)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    # 日期索引：交易日（约250天/年）
    dates = pd.bdate_range("2022-01-04", periods=n_days, freq="B")

    # 股票代码
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]

    # --- 价格模拟（带漂移的几何布朗运动） ---
    initial_prices = rng.uniform(5, 100, n_stocks)
    daily_mu = rng.uniform(-0.0002, 0.0005, n_stocks)
    daily_sigma = rng.uniform(0.015, 0.04, n_stocks)

    log_returns = rng.normal(
        daily_mu[None, :], daily_sigma[None, :], (n_days, n_stocks)
    )
    # 限制在A股日涨跌幅±10%
    log_returns = np.clip(log_returns, -0.098, 0.098)

    cum_returns = np.cumsum(log_returns, axis=0)
    close_arr = initial_prices[None, :] * np.exp(cum_returns)

    # 从收盘价生成OHLC
    noise = rng.uniform(0.995, 1.005, (n_days, n_stocks))
    open_arr = np.roll(close_arr, 1, axis=0) * noise  # 前一日收盘价 * 噪声
    open_arr[0] = initial_prices
    high_arr = np.maximum(open_arr, close_arr) * rng.uniform(1.0, 1.02, (n_days, n_stocks))
    low_arr = np.minimum(open_arr, close_arr) * rng.uniform(0.98, 1.0, (n_days, n_stocks))

    # --- 复权因子（模拟几次除权除息事件） ---
    adj = np.ones((n_days, n_stocks))
    for s in range(n_stocks):
        # 随机除权除息日期
        n_events = rng.integers(0, 3)
        event_days = rng.choice(range(50, n_days), size=n_events, replace=False) if n_events > 0 else []
        for d in sorted(event_days):
            factor = rng.uniform(0.90, 0.98)
            adj[d:, s] *= factor
    # 标准化使最新adj = 1
    adj = adj / adj[-1:]

    # --- 停牌映射 ---
    suspend = np.zeros((n_days, n_stocks), dtype=int)
    for s in range(n_stocks):
        # 随机停牌块
        n_blocks = rng.integers(0, 4)
        for _ in range(n_blocks):
            start = rng.integers(10, n_days - 20)
            length = rng.integers(1, 10)
            suspend[start:start + length, s] = 1

    # --- 行业映射（中信一级：约30个行业） ---
    industry_codes = rng.integers(1, 31, n_stocks)
    industry = np.broadcast_to(industry_codes[None, :], (n_days, n_stocks)).copy().astype(float)

    # --- ST映射 ---
    st = np.zeros((n_days, n_stocks), dtype=int)
    st_stocks = rng.choice(n_stocks, size=max(1, n_stocks // 20), replace=False)
    for s in st_stocks:
        start = rng.integers(0, n_days // 2)
        st[start:, s] = 1

    # --- 市值数据 ---
    mktcap = np.zeros((n_days, n_stocks))
    for s in range(n_stocks):
        base_mktcap = rng.uniform(1e9, 1e11)  # 10亿到1000亿
        mktcap[:, s] = base_mktcap * (close_arr[:, s] / close_arr[0, s])

    # --- 因子1：价值因子（模拟EP = 收益/价格） ---
    # 均值回归因子，具有一定预测能力
    value_factor = rng.normal(0, 1, (n_days, n_stocks))
    for t in range(1, n_days):
        value_factor[t] = 0.95 * value_factor[t - 1] + 0.05 * rng.normal(0, 1, n_stocks)
    # 添加与未来收益的小相关性以增加真实感
    future_ret = np.roll(log_returns, -5, axis=0)
    value_factor += 0.3 * future_ret  # 前瞻信号泄漏用于演示

    # --- 因子2：动量因子（过去20日收益） ---
    momentum_factor = np.zeros((n_days, n_stocks))
    for t in range(20, n_days):
        momentum_factor[t] = log_returns[t - 20:t].sum(axis=0)

    # --- 保存所有数据为pkl ---
    def save_df(name, arr):
        df = pd.DataFrame(arr, index=dates[:len(arr)], columns=codes)
        df.to_pickle(data_path / name)

    save_df("close.pkl", close_arr)
    save_df("open.pkl", open_arr)
    save_df("high.pkl", high_arr)
    save_df("low.pkl", low_arr)
    save_df("adj.pkl", adj)
    save_df("suspend.pkl", suspend)
    save_df("industry.pkl", industry)
    save_df("st.pkl", st)
    save_df("mktcap.pkl", mktcap)
    save_df("factor_value.pkl", value_factor)
    save_df("factor_momentum.pkl", momentum_factor)

    print(f"合成数据生成完成: {n_stocks}只股票 × {n_days}天 → {data_path}/")
    return data_path


# ======================================================================
# 运行回测
# ======================================================================

def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 1. 生成数据
    data_dir = generate_synthetic_data(
        n_stocks=200, 
        n_days=500, 
        data_dir="D:/Coding/Factor_Trading_v3.0/demo_data"
    )

    # 2. 配置回测
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import (
        BacktestConfig, CostConfig, UniverseConfig, 
        FactorConfig, OptimizerConfig, RebalanceConfig
    )

    config = BacktestConfig(
        data_dir=data_dir,
        output_dir=Path("D:/Coding/Factor_Trading_v3.0/demo_output"),
        close_file="close.pkl",
        open_file="open.pkl",
        high_file="high.pkl",
        low_file="low.pkl",
        adj_factor_file="adj.pkl",
        suspend_file="suspend.pkl",
        industry_file="industry.pkl",
        st_file="st.pkl",
        mktcap_file="mktcap.pkl",
        factor_files=["factor_value.pkl", "factor_momentum.pkl"],
        factor_weights={"factor_value": 0.6, "factor_momentum": 0.4},
        cost=CostConfig(
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            slippage_pct=0.001,
        ),
        universe=UniverseConfig(
            exclude_suspended=True,
            exclude_limit_up=True,
            exclude_limit_down=True,
            check_next_day_tradable=True,
        ),
        factor=FactorConfig(
            winsorize_method="mad",
            winsorize_n=5.0,
            neutralize=True,
            standardize_method="zscore",
            fill_method="median",
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",     # 从简单开始，可改为'min_variance', 'mvo', 'risk_parity'
            max_weight=0.05,
            target_count=30,
            select_top=True,
            round_lot=True,
            cov_method="ledoit_wolf",
            cov_lookback=60,
        ),
        rebalance=RebalanceConfig(
            method="fixed",
            frequency="monthly",
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=True,
        max_pending_days_buy=5,
        max_pending_days_sell=10,
        enable_fallback=True,
        max_fallback_depth=10,
    )

    # 3. 运行回测
    from engine import BacktestEngine

    engine = BacktestEngine(config)
    engine.setup()
    results = engine.run()

    # 4. 输出结果摘要
    metrics = results['performance_metrics']
    
    print("\n" + "="*60)
    print("回测结果摘要")
    print("="*60)
    print(f"累计收益率: {metrics.get('total_return', 0):.2%}")
    print(f"年化收益率: {metrics.get('annual_return', 0):.2%}")
    print(f"年化波动率: {metrics.get('annual_volatility', 0):.2%}")
    print(f"夏普比率: {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    print(f"胜率: {metrics.get('win_rate', 0):.2%}")
    print(f"总交易次数: {metrics.get('total_trades', 0)}")
    print(f"换手率: {metrics.get('turnover_rate', 0):.2%}")
    
    if results.get('additional_info', {}).get('pending_order_stats'):
        pending_stats = results['additional_info']['pending_order_stats']
        print(f"\n待执行订单统计:")
        print(f"  总订单数: {pending_stats.get('total_orders', 0)}")
        print(f"  执行订单数: {pending_stats.get('executed_orders', 0)}")
        print(f"  过期订单数: {pending_stats.get('expired_orders', 0)}")
        print(f"  平均重试次数: {pending_stats.get('avg_retry_count', 0):.2f}")

    print("\n完成！请查看 ./demo_output/ 目录获取报告和图表。")
    return results


if __name__ == "__main__":
    main()
