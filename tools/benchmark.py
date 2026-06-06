"""
性能基准测试工具

对比不同回测引擎的性能表现。
"""

from __future__ import annotations

import sys
import time
import logging
from typing import Any, Optional
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_test_data(n_dates: int, n_stocks: int, seed: int = 42) -> dict[str, pd.DataFrame]:
    """生成测试数据

    Args:
        n_dates: 交易日数量
        n_stocks: 股票数量
        seed: 随机种子

    Returns:
        包含 close/open/high/low 的字典
    """
    np.random.seed(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
    stocks = [f"STOCK_{i:04d}" for i in range(n_stocks)]

    returns = np.random.randn(n_dates, n_stocks) * 0.02
    close = 100 * np.exp(np.cumsum(returns, axis=0))
    open_price = close * (1 + np.random.randn(n_dates, n_stocks) * 0.005)
    high = close * (1 + np.abs(np.random.randn(n_dates, n_stocks)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n_dates, n_stocks)) * 0.01)

    return {
        "close": pd.DataFrame(close, index=dates, columns=stocks),
        "open": pd.DataFrame(open_price, index=dates, columns=stocks),
        "high": pd.DataFrame(high, index=dates, columns=stocks),
        "low": pd.DataFrame(low, index=dates, columns=stocks),
    }


def benchmark_engine_v3(data: dict[str, pd.DataFrame], config: dict) -> dict[str, Any]:
    """基准测试 VectorBacktestEngine

    Args:
        data: 测试数据
        config: 引擎配置

    Returns:
        测试结果
    """
    from core.data_v3 import DataLoaderV3
    from core.engine_v3_vector import VectorBacktestEngine

    # 创建 DataLoaderV3
    dl = DataLoaderV3.from_pandas_dataframes(
        close=data["close"],
        open=data["open"],
        high=data["high"],
        low=data["low"],
    )

    # 创建引擎
    engine = VectorBacktestEngine(config)
    engine.setup(dl)

    # 运行并计时
    start = time.perf_counter()
    results = engine.run()
    elapsed = time.perf_counter() - start

    return {
        "engine": "VectorBacktestEngine (V3)",
        "elapsed_seconds": elapsed,
        "total_return": results["total_return"],
        "sharpe_ratio": results["sharpe_ratio"],
        "max_drawdown": results["max_drawdown"],
        "final_value": results["final_value"],
    }


def run_benchmark_suite():
    """运行完整的基准测试套件"""
    print("=" * 60)
    print("Factor Trading v3.0 - 性能基准测试")
    print("=" * 60)

    # 测试配置
    test_configs = [
        {"name": "小规模", "n_dates": 252, "n_stocks": 100},
        {"name": "中规模", "n_dates": 756, "n_stocks": 500},
        {"name": "大规模", "n_dates": 1250, "n_stocks": 1000},
        {"name": "超大规模", "n_dates": 2500, "n_stocks": 3000},
    ]

    engine_config = {
        "initial_capital": 10000000.0,
        "rebalance_freq": 20,
        "top_n": 50,
        "cost_rate": 0.001,
    }

    all_results = []

    for test_config in test_configs:
        name = test_config["name"]
        n_dates = test_config["n_dates"]
        n_stocks = test_config["n_stocks"]

        print(f"\n{'-' * 60}")
        print(f"测试场景: {name}")
        print(f"数据规模: {n_dates} 天 × {n_stocks} 股票")
        print(f"{'-' * 60}")

        # 生成数据
        data_start = time.perf_counter()
        data = generate_test_data(n_dates, n_stocks)
        data_elapsed = time.perf_counter() - data_start
        print(f"数据生成耗时: {data_elapsed:.4f} 秒")

        # 运行基准测试
        try:
            result = benchmark_engine_v3(data, engine_config)
            result["scenario"] = name
            result["n_dates"] = n_dates
            result["n_stocks"] = n_stocks
            all_results.append(result)

            print(f"引擎: {result['engine']}")
            print(f"回测耗时: {result['elapsed_seconds']:.4f} 秒")
            print(f"总收益率: {result['total_return']:.2%}")
            print(f"夏普比率: {result['sharpe_ratio']:.2f}")
            print(f"最大回撤: {result['max_drawdown']:.2%}")

            # 计算吞吐量
            data_points = n_dates * n_stocks
            throughput = data_points / result["elapsed_seconds"] if result["elapsed_seconds"] > 0 else 0
            print(f"吞吐量: {throughput:,.0f} 数据点/秒")

        except Exception as e:
            print(f"测试失败: {e}")
            logger.error(f"基准测试失败 ({name}): {e}")

    # 汇总报告
    print(f"\n{'=' * 60}")
    print("性能测试汇总")
    print(f"{'=' * 60}")
    print(f"{'场景':<12} {'规模':<20} {'耗时(秒)':<12} {'吞吐量':<15}")
    print("-" * 60)

    for result in all_results:
        scale = f"{result['n_dates']}×{result['n_stocks']}"
        throughput = result["n_dates"] * result["n_stocks"] / result["elapsed_seconds"]
        print(
            f"{result['scenario']:<12} {scale:<20} "
            f"{result['elapsed_seconds']:<12.4f} {throughput:>14,.0f}"
        )

    print(f"{'=' * 60}")

    return all_results


if __name__ == "__main__":
    run_benchmark_suite()

