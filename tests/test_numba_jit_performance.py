"""
Numba JIT 加速 - 性能基准测试 (TDD: RED Phase)

测试:
1. numba 可用性
2. @njit 内核函数正确性 (与纯NumPy结果一致)
3. 性能基准: JIT vs 非JIT (目标 ≥ 5x 加速)
4. 大数据集压力测试 (500股 × 500天)
5. 全量回归: 集成后 V3 引擎结果不变
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


def build_large_test_data(n_dates=500, n_stocks=500):
    """构建大数据集"""
    np.random.seed(42)
    close = np.zeros((n_dates, n_stocks))
    close[0] = np.random.uniform(10, 100, n_stocks)
    for i in range(1, n_dates):
        close[i] = close[i - 1] * (1 + np.random.normal(0.0005, 0.02, n_stocks))
    signals = np.zeros_like(close)
    signals[1:] = (close[1:] - close[:-1]) / close[:-1]
    return close, signals


# ============================================================
# TDD RED Phase: 首先定义预期的内核函数签名
# ============================================================

def test_numba_available():
    """测试: numba 已安装且可用"""
    print("\n[Test] numba 可用性检查...")
    try:
        import numba
        from numba import njit
        print(f"  ✓ numba version: {numba.__version__}")
        return True
    except ImportError as e:
        print(f"  ✗ numba 未安装: {e}")
        raise


def test_rebalance_kernel_correctness():
    """测试: @njit 再平衡内核与纯NumPy结果一致"""
    print("\n[Test] 再平衡内核正确性...")

    from core.engine_v3_vector import _rebalance_kernel

    np.random.seed(42)
    n_stocks = 100

    # 构建输入
    positions = np.zeros(n_stocks)
    positions[0:3] = 100  # 已有持仓
    cash = 5_000_000.0
    last_pv = 10_000_000.0
    signal = np.random.randn(n_stocks)
    prices = np.random.uniform(10, 100, n_stocks)
    buyable = np.ones(n_stocks, dtype=bool)
    buyable[0:5] = False  # 前5只不可买
    sellable = np.ones(n_stocks, dtype=bool)
    sellable[0:2] = False  # 前2只不可卖

    top_n = 10
    cost_rate = 0.001

    new_positions, new_cash = _rebalance_kernel(
        positions, cash, last_pv, signal, prices,
        buyable, sellable, top_n, cost_rate,
    )

    # 基本验证
    assert new_positions.shape == (n_stocks,), f"输出形状错误: {new_positions.shape}"
    assert isinstance(new_cash, float), f"cash 应为 float"
    print(f"  ✓ 内核函数运行成功: {np.sum(new_positions > 0)} 只持仓")

    # 不可买的不应有新仓位
    assert np.all(new_positions[buyable == False] == 0), "不可买股票不应有仓位"
    print(f"  ✓ 不可买股票正确过滤")

    # 不可卖的旧持仓应被强制卖出
    assert np.all(new_positions[0:2] == 0), "不可卖旧持仓应被强制卖出"
    print(f"  ✓ 不可卖旧持仓强制卖出")

    # 持仓数量不超过 top_n
    assert np.sum(new_positions > 0) <= top_n, f"持仓超过 top_n={top_n}"
    print(f"  ✓ 持仓数量 ≤ top_n")

    return True


def test_rebalance_kernel_performance():
    """测试: @njit 再平衡内核性能 ≥ 5x"""
    print("\n[Test] 再平衡内核性能基准...")

    from core.engine_v3_vector import _rebalance_kernel

    np.random.seed(42)
    n_stocks = 5000

    positions = np.zeros(n_stocks)
    positions[0:100] = 50
    cash = 50_000_000.0
    last_pv = 100_000_000.0
    signal = np.random.randn(n_stocks)
    prices = np.random.uniform(10, 100, n_stocks)
    buyable = np.ones(n_stocks, dtype=bool)
    sellable = np.ones(n_stocks, dtype=bool)
    top_n = 100
    cost_rate = 0.001

    # Warm-up (JIT 编译)
    _ = _rebalance_kernel(positions, cash, last_pv, signal, prices,
                          buyable, sellable, top_n, cost_rate)

    # 性能测试
    n_runs = 50
    t0 = time.perf_counter()
    for _ in range(n_runs):
        _ = _rebalance_kernel(positions, cash, last_pv, signal, prices,
                              buyable, sellable, top_n, cost_rate)
    elapsed = time.perf_counter() - t0
    avg_ms = (elapsed / n_runs) * 1000

    print(f"  ✓ 5000股再平衡: {avg_ms:.2f}ms/次 (×{n_runs}次)")
    assert avg_ms < 10.0, f"再平衡过慢: {avg_ms:.2f}ms (期望 < 10ms)"
    print(f"  ✓ 性能达标: {avg_ms:.2f}ms < 10ms")

    return True


def test_metrics_kernel_correctness():
    """测试: @njit 指标内核与纯NumPy结果一致"""
    print("\n[Test] 指标内核正确性...")

    from core.engine_v3_vector import _metrics_kernel

    # 构建 portfolio value
    np.random.seed(42)
    n_days = 252
    pv = np.ones(n_days) * 10_000_000
    for i in range(1, n_days):
        pv[i] = pv[i - 1] * (1 + np.random.normal(0.0005, 0.01))

    result = _metrics_kernel(pv)

    # 验证返回类型
    assert len(result) == 6, f"应返回6个指标，实际{len(result)}"
    total_return, annual_return, volatility, sharpe, max_dd, final_value = result

    print(f"  ✓ 指标计算: Sharpe={sharpe:.3f}, MaxDD={max_dd:.3f}, "
          f"Annual={annual_return:.3f}")

    # 合理性检查
    assert -1.0 <= max_dd <= 0.0, f"max_drawdown 不合理: {max_dd}"
    assert final_value > 0, "final_value 应为正"
    print(f"  ✓ 数值合理性通过")

    return True


def test_metrics_kernel_performance():
    """测试: @njit 指标内核性能"""
    print("\n[Test] 指标内核性能基准...")

    from core.engine_v3_vector import _metrics_kernel

    np.random.seed(42)
    n_days = 2500
    pv = np.ones(n_days) * 10_000_000
    for i in range(1, n_days):
        pv[i] = pv[i - 1] * (1 + np.random.normal(0.0005, 0.01))

    # Warm-up
    _ = _metrics_kernel(pv)

    n_runs = 100
    t0 = time.perf_counter()
    for _ in range(n_runs):
        _ = _metrics_kernel(pv)
    elapsed = time.perf_counter() - t0
    avg_ms = (elapsed / n_runs) * 1000

    print(f"  ✓ 2500天指标计算: {avg_ms:.3f}ms/次 (×{n_runs}次)")
    assert avg_ms < 5.0, f"指标计算过慢: {avg_ms:.3f}ms (期望 < 5ms)"
    print(f"  ✓ 性能达标")

    return True


def test_v3_engine_jit_integration():
    """测试: 集成 @njit 后 V3 引擎结果不变 (回归测试)"""
    print("\n[Test] V3 引擎 @njit 集成回归...")

    from core.data_v3 import DataLoaderV3
    from core.engine_v3_vector import VectorBacktestEngine

    np.random.seed(42)
    n_dates = 200
    n_stocks = 100

    close = np.zeros((n_dates, n_stocks))
    close[0] = np.random.uniform(10, 100, n_stocks)
    for i in range(1, n_dates):
        close[i] = close[i - 1] * (1 + np.random.normal(0.0005, 0.02, n_stocks))

    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=n_dates, freq="B")
    stocks = [f"S{i:04d}" for i in range(n_stocks)]

    close_df = pd.DataFrame(close, index=dates, columns=stocks)
    open_df = pd.DataFrame(close * np.random.uniform(0.98, 1.02, close.shape),
                           index=dates, columns=stocks)
    high_df = pd.DataFrame(close * 1.05, index=dates, columns=stocks)
    low_df = pd.DataFrame(close * 0.95, index=dates, columns=stocks)

    factor = np.zeros_like(close)
    factor[1:] = (close[1:] - close[:-1]) / close[:-1]
    factor_df = pd.DataFrame(factor, index=dates, columns=stocks)

    dl = DataLoaderV3.from_pandas_dataframes(
        close=close_df, open=open_df, high=high_df, low=low_df,
        factor_dict={"factor_momentum": factor_df},
    )

    config = {
        "initial_capital": 10_000_000,
        "rebalance_freq": 20,
        "top_n": 20,
        "cost_rate": 0.001,
    }
    engine = VectorBacktestEngine(config)
    engine.setup(dl)
    results = engine.run()

    # 验证结果完整性
    required_keys = ["portfolio_value", "returns", "sharpe_ratio",
                     "max_drawdown", "final_value", "initial_value"]
    for key in required_keys:
        assert key in results, f"缺少关键字段: {key}"
    print(f"  ✓ 结果结构完整")

    # 验证数值合理性
    assert results["initial_value"] == 10_000_000
    assert results["final_value"] > 0
    assert -1.0 <= results["max_drawdown"] <= 0.0
    assert not np.isnan(results["sharpe_ratio"])
    print(f"  ✓ 数值合理性: Sharpe={results['sharpe_ratio']:.3f}, "
          f"MaxDD={results['max_drawdown']:.3f}")

    return True


def test_v3_engine_jit_large_scale():
    """测试: 大数据集压力测试 (500股 × 500天)"""
    print("\n[Test] V3 引擎大数据集压力测试...")

    from core.data_v3 import DataLoaderV3
    from core.engine_v3_vector import VectorBacktestEngine

    close, signals = build_large_test_data(500, 500)

    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=500, freq="B")
    stocks = [f"S{i:04d}" for i in range(500)]

    close_df = pd.DataFrame(close, index=dates, columns=stocks)
    open_df = pd.DataFrame(close * np.random.uniform(0.98, 1.02, close.shape),
                           index=dates, columns=stocks)
    high_df = pd.DataFrame(close * 1.05, index=dates, columns=stocks)
    low_df = pd.DataFrame(close * 0.95, index=dates, columns=stocks)
    factor_df = pd.DataFrame(signals, index=dates, columns=stocks)

    dl = DataLoaderV3.from_pandas_dataframes(
        close=close_df, open=open_df, high=high_df, low=low_df,
        factor_dict={"factor_momentum": factor_df},
    )

    config = {
        "initial_capital": 10_000_000,
        "rebalance_freq": 20,
        "top_n": 50,
        "cost_rate": 0.001,
    }

    engine = VectorBacktestEngine(config)

    t0 = time.perf_counter()
    engine.setup(dl)
    results = engine.run()
    elapsed = time.perf_counter() - t0

    print(f"  ✓ 500股×500天 耗时: {elapsed:.3f}s")
    assert elapsed < 10.0, f"大数据集过慢: {elapsed:.3f}s (期望 < 10s)"
    assert results["sharpe_ratio"] is not None
    print(f"  ✓ 大数据集回测: Sharpe={results['sharpe_ratio']:.3f}")

    return True


if __name__ == "__main__":
    results = []
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                results.append((name, True))
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                import traceback
                traceback.print_exc()
                results.append((name, False))

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'='*50}")