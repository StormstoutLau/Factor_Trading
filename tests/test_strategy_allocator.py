"""
多策略动态资金分配模块测试

测试覆盖:
1. BayesianDLM 卡尔曼滤波更新
2. StrategyEvaluator 多策略评估
3. 各分配器 (Hedge, FTRL, UCB, Thompson, MeanVariance)
4. MetaPolicy 市场状态检测与参数调整
5. StrategyAllocationManager 完整流程
6. 与 MultiStrategyEngine 的集成接口
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.strategy_allocator import (
    BayesianDLM,
    StrategyEvaluator,
    HedgeAllocator,
    FTRLAllocator,
    UCBAllocator,
    ThompsonSamplingAllocator,
    MeanVarianceAllocator,
    MetaPolicy,
    StrategyAllocationManager,
    AllocationState,
)


# ============================================================
# 辅助函数
# ============================================================

def generate_strategy_returns(n_strategies: int, n_days: int, seed: int = 42) -> tuple[np.ndarray, list[datetime]]:
    """生成模拟策略收益"""
    rng = np.random.RandomState(seed)
    # 策略1: 高夏普，低波动
    # 策略2: 中等收益，中等波动
    # 策略3: 低收益，高波动（偶尔爆发）
    base_returns = np.zeros((n_days, n_strategies))
    
    if n_strategies >= 1:
        base_returns[:, 0] = rng.normal(0.001, 0.01, n_days)  # 稳健策略
    if n_strategies >= 2:
        base_returns[:, 1] = rng.normal(0.0005, 0.015, n_days)  # 中等策略
    if n_strategies >= 3:
        base_returns[:, 2] = rng.normal(0.0, 0.02, n_days)  # 高波动策略
        # 偶尔爆发
        burst_days = rng.choice(n_days, size=n_days // 10, replace=False)
        base_returns[burst_days, 2] += 0.05
    if n_strategies >= 4:
        base_returns[:, 3] = rng.normal(-0.0002, 0.008, n_days)  # 略亏策略
    if n_strategies >= 5:
        base_returns[:, 4] = base_returns[:, 0] * 0.8 + rng.normal(0, 0.005, n_days)  # 与策略1相关
    
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    return base_returns, dates


# ============================================================
# 测试 1: BayesianDLM
# ============================================================

def test_bayesian_dlm_basic():
    """测试DLM基本更新功能"""
    print("\n" + "=" * 60)
    print("测试 1: BayesianDLM 基本更新")
    print("=" * 60)
    
    dlm = BayesianDLM(
        observation_variance=0.01,
        state_variance=0.001,
        prior_mean=0.0,
        prior_variance=0.1
    )
    
    # 模拟一个正收益序列
    returns = [0.01, 0.02, 0.015, 0.01, 0.025]
    
    for i, ret in enumerate(returns):
        result = dlm.update(ret)
        print(f"  观测 {i+1}: r={ret:.4f} -> μ={result['mu']:.6f}, σ={result['sigma']:.6f}, K={result['K']:.4f}")
    
    # 验证：后验均值应向正收益偏移
    assert dlm.mu > 0, f"后验均值应为正，实际 {dlm.mu}"
    # 验证：观测越多，不确定性应降低
    assert dlm.sigma2_post < 0.1, f"后验方差应降低，实际 {dlm.sigma2_post}"
    
    # 测试预测
    pred_mu, pred_sigma = dlm.predict(n_steps=1)
    print(f"  1步预测: μ={pred_mu:.6f}, σ={pred_sigma:.6f}")
    assert pred_sigma >= np.sqrt(dlm.sigma2_post), "预测不确定性应不小于当前不确定性"
    
    # 测试置信区间
    lower, upper = dlm.get_confidence_interval(0.95)
    print(f"  95%置信区间: [{lower:.6f}, {upper:.6f}]")
    assert lower < dlm.mu < upper, "均值应在置信区间内"
    
    # 测试性能指标
    metrics = dlm.get_performance_metrics()
    print(f"  性能指标: RMSE={metrics['rmse']:.6f}, MAE={metrics['mae']:.6f}")
    
    print("  ✓ BayesianDLM 基本更新测试通过")


def test_bayesian_dlm_convergence():
    """测试DLM收敛到真实均值"""
    print("\n" + "=" * 60)
    print("测试 2: BayesianDLM 收敛性")
    print("=" * 60)
    
    true_mean = 0.02
    dlm = BayesianDLM(observation_variance=0.0001, state_variance=0.00001)
    
    n_obs = 100
    rng = np.random.RandomState(42)
    returns = rng.normal(true_mean, 0.01, n_obs)
    
    for ret in returns:
        dlm.update(ret)
    
    print(f"  真实均值: {true_mean:.4f}")
    print(f"  估计均值: {dlm.mu:.6f}")
    print(f"  估计标准差: {np.sqrt(dlm.sigma2_post):.6f}")
    
    # 估计应接近真实均值
    assert abs(dlm.mu - true_mean) < 0.005, f"估计均值 {dlm.mu} 与真实均值 {true_mean} 偏差过大"
    
    print("  ✓ BayesianDLM 收敛性测试通过")


# ============================================================
# 测试 3: StrategyEvaluator
# ============================================================

def test_strategy_evaluator():
    """测试策略评估器"""
    print("\n" + "=" * 60)
    print("测试 3: StrategyEvaluator")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 30
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(
        n_strategies=n_strategies,
        strategy_names=["稳健策略", "中等策略", "高波动策略"],
        state_variance=0.001,
        lookback_window=20
    )
    
    # 逐日更新
    for i, (ret, date) in enumerate(zip(returns, dates)):
        results = evaluator.update(ret, date)
        if i == n_days - 1:
            print(f"  最后一日更新结果:")
            for name, result in results.items():
                print(f"    {name}: μ={result['mu']:.6f}, σ={result['sigma']:.6f}")
    
    # 验证期望收益
    expected = evaluator.get_expected_returns()
    print(f"  期望收益: {expected}")
    assert len(expected) == n_strategies
    
    # 验证不确定性
    uncertainty = evaluator.get_uncertainty()
    print(f"  不确定性: {uncertainty}")
    assert all(u >= 0 for u in uncertainty)
    
    # 验证夏普估计
    sharpe = evaluator.get_sharpe_estimates()
    print(f"  夏普估计: {sharpe}")
    
    # 验证相关性矩阵
    corr = evaluator.correlation_matrix
    print(f"  相关性矩阵:\n{corr}")
    assert corr.shape == (n_strategies, n_strategies)
    assert np.allclose(np.diag(corr), 1.0), "对角线应为1"
    
    # 验证报告
    report = evaluator.get_report()
    print(f"  最佳策略: {report['summary']['best_strategy']}")
    print(f"  最差策略: {report['summary']['worst_strategy']}")
    print(f"  平均绝对相关性: {report['summary']['avg_correlation']:.4f}")
    
    print("  ✓ StrategyEvaluator 测试通过")


# ============================================================
# 测试 4-8: 各分配器
# ============================================================

def test_hedge_allocator():
    """测试Hedge分配器"""
    print("\n" + "=" * 60)
    print("测试 4: HedgeAllocator")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 50
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(n_strategies=n_strategies)
    allocator = HedgeAllocator(learning_rate=0.1, forget_factor=0.95)
    
    weights_history = []
    
    for ret, date in zip(returns, dates):
        evaluator.update(ret, date)
        weights = allocator.allocate(evaluator)
        weights_history.append(weights.copy())
        
        assert abs(np.sum(weights) - 1.0) < 1e-6, f"权重和应为1，实际 {np.sum(weights)}"
        assert all(weights >= 0), "权重应非负"
    
    final_weights = weights_history[-1]
    print(f"  最终权重: {final_weights}")
    print(f"  权重历史最后5期:\n{np.array(weights_history[-5:])}")
    
    # 验证：表现好的策略应获得更高权重
    expected_returns = evaluator.get_expected_returns()
    best_strategy = np.argmax(expected_returns)
    print(f"  最佳策略索引: {best_strategy}, 期望收益: {expected_returns[best_strategy]:.6f}")
    print(f"  最佳策略权重: {final_weights[best_strategy]:.4f}")
    
    print("  ✓ HedgeAllocator 测试通过")


def test_ftrl_allocator():
    """测试FTRL分配器"""
    print("\n" + "=" * 60)
    print("测试 5: FTRLAllocator")
    print("=" * 60)
    
    n_strategies = 4
    n_days = 50
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(n_strategies=n_strategies)
    allocator = FTRLAllocator(
        learning_rate=0.1,
        forget_factor=0.95,
        turnover_penalty=0.01,
        min_weight=0.05,
        max_weight=0.6
    )
    
    current_weights = np.ones(n_strategies) / n_strategies
    weights_history = []
    
    for ret, date in zip(returns, dates):
        evaluator.update(ret, date)
        new_weights = allocator.allocate(evaluator, current_weights=current_weights)
        weights_history.append(new_weights.copy())
        current_weights = new_weights
        
        assert abs(np.sum(new_weights) - 1.0) < 1e-6
        assert all(new_weights >= 0.05 - 1e-6), f"权重应>=0.05，实际最小 {np.min(new_weights)}"
        assert all(new_weights <= 0.6 + 1e-6), f"权重应<=0.6，实际最大 {np.max(new_weights)}"
    
    final_weights = weights_history[-1]
    print(f"  最终权重: {final_weights}")
    print(f"  权重范围: [{np.min(final_weights):.4f}, {np.max(final_weights):.4f}]")
    
    print("  ✓ FTRLAllocator 测试通过")


def test_ucb_allocator():
    """测试UCB分配器"""
    print("\n" + "=" * 60)
    print("测试 6: UCBAllocator")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 30
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(n_strategies=n_strategies)
    allocator = UCBAllocator(exploration_coeff=2.0, min_weight=0.1)
    
    weights_history = []
    
    for ret, date in zip(returns, dates):
        evaluator.update(ret, date)
        weights = allocator.allocate(evaluator)
        weights_history.append(weights.copy())
        
        assert abs(np.sum(weights) - 1.0) < 1e-6
        assert all(weights >= 0.1 - 1e-6)
    
    final_weights = weights_history[-1]
    print(f"  最终权重: {final_weights}")
    
    # UCB应给不确定性高的策略更多权重（探索）
    uncertainty = evaluator.get_uncertainty()
    print(f"  策略不确定性: {uncertainty}")
    
    print("  ✓ UCBAllocator 测试通过")


def test_thompson_sampling_allocator():
    """测试Thompson Sampling分配器"""
    print("\n" + "=" * 60)
    print("测试 7: ThompsonSamplingAllocator")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 30
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(n_strategies=n_strategies)
    allocator = ThompsonSamplingAllocator(temperature=1.0, min_weight=0.05)
    
    weights_history = []
    
    for ret, date in zip(returns, dates):
        evaluator.update(ret, date)
        weights = allocator.allocate(evaluator)
        weights_history.append(weights.copy())
        
        assert abs(np.sum(weights) - 1.0) < 1e-6
        assert all(weights >= 0.05 - 1e-6)
    
    # 多次采样应产生不同结果（随机性）
    weights_samples = []
    for _ in range(10):
        w = allocator.allocate(evaluator)
        weights_samples.append(w)
    
    weights_samples = np.array(weights_samples)
    std_per_strategy = np.std(weights_samples, axis=0)
    print(f"  10次采样权重标准差: {std_per_strategy}")
    print(f"  平均权重: {np.mean(weights_samples, axis=0)}")
    
    # 验证存在随机性
    assert any(std > 1e-6 for std in std_per_strategy), "Thompson Sampling应产生随机权重"
    
    print("  ✓ ThompsonSamplingAllocator 测试通过")


def test_mean_variance_allocator():
    """测试均值-方差分配器"""
    print("\n" + "=" * 60)
    print("测试 8: MeanVarianceAllocator")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 50
    returns, dates = generate_strategy_returns(n_strategies, n_days)
    
    evaluator = StrategyEvaluator(n_strategies=n_strategies, lookback_window=30)
    allocator = MeanVarianceAllocator(
        risk_aversion=1.0,
        min_weight=0.0,
        max_weight=1.0
    )
    
    weights_history = []
    
    for ret, date in zip(returns, dates):
        evaluator.update(ret, date)
        weights = allocator.allocate(evaluator)
        weights_history.append(weights.copy())
        
        assert abs(np.sum(weights) - 1.0) < 1e-6
        assert all(weights >= 0)
    
    final_weights = weights_history[-1]
    print(f"  最终权重: {final_weights}")
    
    # 验证协方差矩阵使用
    corr = evaluator.correlation_matrix
    print(f"  相关性矩阵:\n{corr}")
    
    print("  ✓ MeanVarianceAllocator 测试通过")


# ============================================================
# 测试 9: MetaPolicy
# ============================================================

def test_meta_policy():
    """测试元策略"""
    print("\n" + "=" * 60)
    print("测试 9: MetaPolicy")
    print("=" * 60)
    
    n_strategies = 3
    
    # 场景1: 高波动市场（策略分化，不同方向）
    print("  场景1: 高波动市场")
    evaluator_volatile = StrategyEvaluator(n_strategies=n_strategies)
    rng = np.random.RandomState(1)
    for _ in range(20):
        # 高波动且策略分化（不同方向）
        ret = np.array([
            rng.normal(0.03, 0.05),   # 策略1大幅正收益
            rng.normal(-0.02, 0.05),  # 策略2大幅负收益
            rng.normal(0.01, 0.05),   # 策略3小幅波动
        ])
        evaluator_volatile.update(ret)

    allocator = FTRLAllocator(learning_rate=0.1)
    meta = MetaPolicy(allocator, adaptation_rate=0.1)

    regime = meta.detect_regime(evaluator_volatile)
    print(f"    检测到的市场状态: {regime}")
    assert regime == "volatile", f"高波动市场应检测为volatile，实际 {regime}"

    original_eta = allocator.eta
    meta.adapt_parameters(evaluator_volatile)
    print(f"    调整前 eta: {original_eta}, 调整后 eta: {allocator.eta}")
    assert allocator.eta > original_eta, "高波动应增加学习率"

    # 场景2: 趋势市场（同向强趋势，波动适中）
    print("  场景2: 趋势市场")
    evaluator_trending = StrategyEvaluator(n_strategies=n_strategies)
    rng = np.random.RandomState(3)
    for _ in range(20):
        # 同向正收益，波动较小
        base = rng.normal(0.01, 0.005)
        ret = np.array([base + 0.005, base + 0.003, base + 0.002])
        evaluator_trending.update(ret)

    allocator2 = FTRLAllocator(learning_rate=0.1)
    meta2 = MetaPolicy(allocator2, adaptation_rate=0.1)

    regime2 = meta2.detect_regime(evaluator_trending)
    print(f"    检测到的市场状态: {regime2}")
    assert regime2 == "trending", f"趋势市场应检测为trending，实际 {regime2}"

    original_eta2 = allocator2.eta
    meta2.adapt_parameters(evaluator_trending)
    print(f"    调整前 eta: {original_eta2}, 调整后 eta: {allocator2.eta}")
    assert allocator2.eta < original_eta2, "趋势市应降低学习率"

    # 场景3: 正常市场（收益围绕0波动，无明显趋势）
    print("  场景3: 正常市场")
    evaluator_normal = StrategyEvaluator(n_strategies=n_strategies, state_variance=0.0001)
    rng = np.random.RandomState(2)
    for _ in range(50):
        ret = rng.normal(0, 0.008, n_strategies)  # 适中波动，但更多观测使DLM收敛
        evaluator_normal.update(ret)

    allocator3 = FTRLAllocator(learning_rate=0.1)
    meta3 = MetaPolicy(allocator3, adaptation_rate=0.1)

    regime3 = meta3.detect_regime(evaluator_normal)
    print(f"    检测到的市场状态: {regime3}")
    print(f"    期望收益: {evaluator_normal.get_expected_returns()}")
    print(f"    不确定性: {evaluator_normal.get_uncertainty()}")
    assert regime3 == "normal", f"正常市场应检测为normal，实际 {regime3}"

    original_eta3 = allocator3.eta
    meta3.adapt_parameters(evaluator_normal)
    print(f"    调整前 eta: {original_eta3}, 调整后 eta: {allocator3.eta}")
    assert abs(allocator3.eta - original_eta3) < 1e-10, "正常市场不应调整参数"
    
    print("  ✓ MetaPolicy 测试通过")


# ============================================================
# 测试 10: StrategyAllocationManager 完整流程
# ============================================================

def test_allocation_manager():
    """测试策略分配管理器完整流程"""
    print("\n" + "=" * 60)
    print("测试 10: StrategyAllocationManager 完整流程")
    print("=" * 60)
    
    strategy_names = ["动量策略", "价值策略", "均值回归策略", "趋势跟踪策略"]
    n_strategies = len(strategy_names)
    n_days = 100
    returns, dates = generate_strategy_returns(n_strategies, n_days, seed=2024)
    
    # 测试不同分配器
    for allocator_type in ['hedge', 'ftrl', 'ucb', 'thompson', 'mean_variance']:
        print(f"\n  分配器类型: {allocator_type}")
        
        manager = StrategyAllocationManager(
            strategy_names=strategy_names,
            allocator_type=allocator_type,
            dlm_state_variance=0.001,
            learning_rate=0.1,
            forget_factor=0.95,
            min_weight=0.05
        )
        
        # 逐日更新
        for ret, date in zip(returns, dates):
            weights = manager.update(ret, date, adapt_meta=True)
        
        final_weights = manager.get_weights()
        print(f"    最终权重:")
        for name, w in final_weights.items():
            print(f"      {name}: {w:.4f}")
        
        # 验证
        total_weight = sum(final_weights.values())
        assert abs(total_weight - 1.0) < 1e-6, f"权重和应为1，实际 {total_weight}"
        assert all(w >= 0.05 - 1e-6 for w in final_weights.values()), "权重应>=最小权重"
        
        # 验证报告
        report = manager.get_report()
        print(f"    组合累计收益: {report['portfolio_cumulative_return']:.4f}")
        print(f"    组合夏普比率: {report.get('portfolio_sharpe', 'N/A')}")
        print(f"    更新次数: {report['n_updates']}")
        
        # 验证权重历史
        assert len(manager.weight_history) == n_days, "权重历史应记录每一天"
    
    print("  ✓ StrategyAllocationManager 完整流程测试通过")


# ============================================================
# 测试 11: 权重稳定性与收敛性
# ============================================================

def test_weight_stability():
    """测试权重稳定性：在平稳环境下权重不应剧烈震荡"""
    print("\n" + "=" * 60)
    print("测试 11: 权重稳定性")
    print("=" * 60)
    
    n_strategies = 3
    n_days = 200
    
    # 平稳环境：策略1始终最好
    rng = np.random.RandomState(42)
    returns = np.zeros((n_days, n_strategies))
    returns[:, 0] = rng.normal(0.002, 0.01, n_days)  # 最好
    returns[:, 1] = rng.normal(0.000, 0.01, n_days)  # 中等
    returns[:, 2] = rng.normal(-0.001, 0.01, n_days)  # 最差
    
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    
    manager = StrategyAllocationManager(
        strategy_names=["好策略", "中策略", "差策略"],
        allocator_type='ftrl',
        learning_rate=0.05,  # 较低学习率增加稳定性
        forget_factor=1.0,   # 无遗忘
        turnover_penalty=0.02
    )
    
    weights_history = []
    for ret, date in zip(returns, dates):
        weights = manager.update(ret, date)
        weights_history.append(weights.copy())
    
    weights_history = np.array(weights_history)
    
    # 计算权重变化率
    weight_changes = np.diff(weights_history, axis=0)
    avg_change = np.mean(np.abs(weight_changes))
    max_change = np.max(np.abs(weight_changes))
    
    print(f"  平均权重变化: {avg_change:.6f}")
    print(f"  最大权重变化: {max_change:.6f}")
    
    # 最终权重：好策略应占主导
    final_weights = weights_history[-1]
    print(f"  最终权重: {final_weights}")
    assert final_weights[0] > final_weights[1], "好策略权重应大于中等策略"
    assert final_weights[0] > final_weights[2], "好策略权重应大于差策略"
    
    # 验证权重变化不过大（有换手率惩罚）
    assert avg_change < 0.1, f"平均权重变化 {avg_change} 过大，应更稳定"
    
    print("  ✓ 权重稳定性测试通过")


# ============================================================
# 测试 12: 非平稳环境适应性
# ============================================================

def test_nonstationary_adaptation():
    """测试非平稳环境下的适应性"""
    print("\n" + "=" * 60)
    print("测试 12: 非平稳环境适应性")
    print("=" * 60)
    
    n_strategies = 2
    n_days = 200
    
    # 前100天策略1好，后100天策略2好
    rng = np.random.RandomState(42)
    returns = np.zeros((n_days, n_strategies))
    returns[:100, 0] = rng.normal(0.002, 0.01, 100)
    returns[:100, 1] = rng.normal(-0.001, 0.01, 100)
    returns[100:, 0] = rng.normal(-0.001, 0.01, 100)
    returns[100:, 1] = rng.normal(0.002, 0.01, 100)
    
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    
    # 测试带遗忘因子的FTRL
    manager = StrategyAllocationManager(
        strategy_names=["策略A", "策略B"],
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.95,  # 遗忘因子帮助适应
        turnover_penalty=0.01
    )
    
    weights_history = []
    for ret, date in zip(returns, dates):
        weights = manager.update(ret, date)
        weights_history.append(weights.copy())
    
    weights_history = np.array(weights_history)
    
    # 前100天策略A权重应更高
    avg_weight_first_100 = np.mean(weights_history[:100, 0])
    # 后100天策略B权重应更高
    avg_weight_last_100 = np.mean(weights_history[100:, 1])
    
    print(f"  前100天策略A平均权重: {avg_weight_first_100:.4f}")
    print(f"  后100天策略B平均权重: {avg_weight_last_100:.4f}")
    
    assert avg_weight_first_100 > 0.5, f"前100天策略A应占主导，实际平均权重 {avg_weight_first_100}"
    assert avg_weight_last_100 > 0.5, f"后100天策略B应占主导，实际平均权重 {avg_weight_last_100}"
    
    print("  ✓ 非平稳环境适应性测试通过")


# ============================================================
# 测试 13: 集成接口测试
# ============================================================

def test_integration_with_multi_strategy_engine():
    """测试与MultiStrategyEngine的集成接口"""
    print("\n" + "=" * 60)
    print("测试 13: 与 MultiStrategyEngine 集成接口")
    print("=" * 60)
    
    # 模拟三个策略的日收益
    strategy_names = ["多头策略", "空头策略", "中性策略"]
    n_days = 60
    returns, dates = generate_strategy_returns(3, n_days, seed=99)
    
    # 创建分配管理器
    manager = StrategyAllocationManager(
        strategy_names=strategy_names,
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.95,
        turnover_penalty=0.01,
        min_weight=0.1,
        max_weight=0.7
    )
    
    # 模拟每日更新并获取权重
    daily_weights = []
    for ret, date in zip(returns, dates):
        weights = manager.update(ret, date, adapt_meta=True)
        daily_weights.append({
            'date': date,
            'weights': manager.get_weights(),
            'portfolio_return': manager.portfolio_returns[-1]
        })
    
    # 验证每日权重
    print(f"  模拟 {n_days} 天的权重分配")
    print(f"  首日权重: {daily_weights[0]['weights']}")
    print(f"  末日权重: {daily_weights[-1]['weights']}")
    
    # 验证组合收益计算
    portfolio_returns = [d['portfolio_return'] for d in daily_weights]
    cumulative_return = np.sum(portfolio_returns)
    print(f"  组合累计收益: {cumulative_return:.4f}")
    print(f"  组合日均收益: {np.mean(portfolio_returns):.6f}")
    print(f"  组合收益波动: {np.std(portfolio_returns):.6f}")
    
    # 验证报告生成
    report = manager.get_report()
    print(f"  报告包含字段: {list(report.keys())}")
    assert 'current_weights' in report
    assert 'evaluator_report' in report
    assert 'portfolio_cumulative_return' in report
    
    # 验证权重历史可用于可视化
    assert len(manager.weight_history) == n_days
    dates_from_history = [d for d, _ in manager.weight_history]
    weights_from_history = np.array([w for _, w in manager.weight_history])
    print(f"  权重历史形状: {weights_from_history.shape}")
    assert weights_from_history.shape == (n_days, 3)
    
    print("  ✓ 集成接口测试通过")


# ============================================================
# 主测试入口
# ============================================================

def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("多策略动态资金分配模块测试套件")
    print("=" * 80)
    
    test_bayesian_dlm_basic()
    test_bayesian_dlm_convergence()
    test_strategy_evaluator()
    test_hedge_allocator()
    test_ftrl_allocator()
    test_ucb_allocator()
    test_thompson_sampling_allocator()
    test_mean_variance_allocator()
    test_meta_policy()
    test_allocation_manager()
    test_weight_stability()
    test_nonstationary_adaptation()
    test_integration_with_multi_strategy_engine()
    
    print("\n" + "=" * 80)
    print("所有测试通过 ✓")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
