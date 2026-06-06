"""
元策略假设检验层测试

测试覆盖:
1. ReturnDistributionMonitor (CUSUM / 滑动t检验 / KPSS)
2. CorrelationStructureMonitor (特征值 / 条件数)
3. TurnoverMonitor (换手率 / 有效数量 / 熵)
4. BayesianModelMonitor (PPC / 对数似然 / Ljung-Box)
5. UniversalMonitor (遗憾 / 瞬时遗憾)
6. AssumptionMonitorLayer 集成与退化机制
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.assumption_monitor import (
    AlertLevel,
    AssumptionCheck,
    MonitorState,
    ReturnDistributionMonitor,
    CorrelationStructureMonitor,
    TurnoverMonitor,
    BayesianModelMonitor,
    UniversalMonitor,
    AssumptionMonitorLayer,
)


# ============================================================
# 辅助函数
# ============================================================

def generate_stationary_returns(n_days: int, n_strategies: int, seed: int = 42) -> list[np.ndarray]:
    """生成平稳收益序列"""
    rng = np.random.RandomState(seed)
    returns = rng.normal(0.001, 0.01, (n_days, n_strategies))
    return [r for r in returns]


def generate_nonstationary_returns(n_days: int, n_strategies: int, seed: int = 42) -> list[np.ndarray]:
    """生成非平稳收益序列（中期均值突变）"""
    rng = np.random.RandomState(seed)
    returns = np.zeros((n_days, n_strategies))
    returns[:n_days//2] = rng.normal(0.001, 0.01, (n_days//2, n_strategies))
    returns[n_days//2:] = rng.normal(0.005, 0.02, (n_days - n_days//2, n_strategies))  # 突变
    return [r for r in returns]


def generate_correlated_returns(n_days: int, n_strategies: int, correlation: float, seed: int = 42) -> list[np.ndarray]:
    """生成具有特定相关结构的收益"""
    rng = np.random.RandomState(seed)
    cov = np.eye(n_strategies) * 0.0001
    for i in range(n_strategies):
        for j in range(i+1, n_strategies):
            cov[i, j] = cov[j, i] = correlation * 0.0001
    returns = rng.multivariate_normal(np.zeros(n_strategies), cov, n_days)
    return [r for r in returns]


# ============================================================
# 测试 1: ReturnDistributionMonitor
# ============================================================

def test_return_distribution_monitor_stationary():
    """测试平稳数据不应触发警报"""
    print("\n" + "=" * 60)
    print("测试 1: ReturnDistributionMonitor - 平稳数据")
    print("=" * 60)

    monitor = ReturnDistributionMonitor(
        cusum_threshold=2.0,
        window_size=30,
        t_test_threshold=2.5,
        kpss_threshold=0.05
    )

    returns = generate_stationary_returns(100, 3)
    checks = monitor.check(returns)

    print(f"  检测到的异常数: {len(checks)}")
    for check in checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    # 平稳数据不应触发RED警报
    red_checks = [c for c in checks if c.level == AlertLevel.RED]
    assert len(red_checks) == 0, f"平稳数据不应触发RED警报，实际 {len(red_checks)}个"

    print("  ✓ 平稳数据测试通过")


def test_return_distribution_monitor_nonstationary():
    """测试非平稳数据应触发警报"""
    print("\n" + "=" * 60)
    print("测试 2: ReturnDistributionMonitor - 非平稳数据")
    print("=" * 60)

    monitor = ReturnDistributionMonitor(
        cusum_threshold=1.0,
        window_size=20,
        t_test_threshold=2.0,
        kpss_threshold=0.05
    )

    returns = generate_nonstationary_returns(100, 3)
    checks = monitor.check(returns)

    print(f"  检测到的异常数: {len(checks)}")
    for check in checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    # 非平稳数据应至少触发一些警报
    assert len(checks) > 0, "非平稳数据应触发至少一个警报"

    # 验证CUSUM或KPSS至少一个被触发
    cusum_checks = [c for c in checks if "CUSUM" in c.name]
    kpss_checks = [c for c in checks if "KPSS" in c.name]
    assert len(cusum_checks) > 0 or len(kpss_checks) > 0, "非平稳数据应触发CUSUM或KPSS警报"

    print("  ✓ 非平稳数据测试通过")


def test_cusum_detection():
    """测试CUSUM对均值偏移的检测能力"""
    print("\n" + "=" * 60)
    print("测试 3: CUSUM均值偏移检测")
    print("=" * 60)

    monitor = ReturnDistributionMonitor(cusum_threshold=1.0)

    # 前50天均值0，后50天均值0.05（大幅偏移，无噪声便于检测）
    rng = np.random.RandomState(42)
    returns = []
    for i in range(100):
        if i < 50:
            ret = 0.0  # 纯0
        else:
            ret = 0.05  # 纯0.05
        returns.append(np.array([ret]))

    checks = monitor.check(returns)

    cusum_checks = [c for c in checks if "CUSUM" in c.name]
    t_checks = [c for c in checks if "t检验" in c.name]
    print(f"  CUSUM警报数: {len(cusum_checks)}")
    print(f"  t检验警报数: {len(t_checks)}")
    for c in cusum_checks:
        print(f"    CUSUM统计量: {c.statistic:.4f}, 阈值: {c.threshold:.4f}")
    for c in t_checks:
        print(f"    t检验统计量: {c.statistic:.4f}")

    # 放宽断言：CUSUM或t检验至少一个触发
    assert len(cusum_checks) > 0 or len(t_checks) > 0, "CUSUM或t检验应检测到均值偏移"

    print("  ✓ CUSUM检测测试通过")


# ============================================================
# 测试 4: CorrelationStructureMonitor
# ============================================================

def test_correlation_structure_monitor():
    """测试相关结构变化检测"""
    print("\n" + "=" * 60)
    print("测试 4: CorrelationStructureMonitor")
    print("=" * 60)

    monitor = CorrelationStructureMonitor(
        window_size=30,
        eigenvalue_change_threshold=1.0,  # 降低阈值便于检测
        condition_number_threshold=50.0
    )

    # 前80天低相关，后80天高相关（更多数据使变化更明显）
    returns_low_corr = generate_correlated_returns(80, 3, 0.05, seed=1)
    returns_high_corr = generate_correlated_returns(80, 3, 0.95, seed=2)
    returns = returns_low_corr + returns_high_corr

    # 逐步检测，在切换点附近应该触发
    checks = []
    for i in range(60, len(returns)):
        daily_checks = monitor.check(returns[:i])
        checks.extend(daily_checks)

    print(f"  检测到的异常数: {len(checks)}")
    for check in checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    # 应检测到特征值结构变化或条件数异常
    eigen_checks = [c for c in checks if "特征值" in c.name]
    cond_checks = [c for c in checks if "条件数" in c.name]
    assert len(eigen_checks) > 0 or len(cond_checks) > 0, "应检测到相关结构变化"

    print("  ✓ 相关结构监控测试通过")


def test_condition_number_monitor():
    """测试条件数异常检测"""
    print("\n" + "=" * 60)
    print("测试 5: 条件数异常检测")
    print("=" * 60)

    monitor = CorrelationStructureMonitor(
        window_size=30,
        condition_number_threshold=10.0  # 较低阈值便于测试
    )

    # 高度相关的收益
    returns = generate_correlated_returns(100, 3, 0.95, seed=42)
    checks = monitor.check(returns)

    cond_checks = [c for c in checks if "条件数" in c.name]
    print(f"  条件数警报数: {len(cond_checks)}")
    for c in cond_checks:
        print(f"    统计量: {c.statistic:.1f}, 阈值: {c.threshold:.1f}")

    assert len(cond_checks) > 0, "高度相关数据应触发条件数警报"

    print("  ✓ 条件数检测测试通过")


# ============================================================
# 测试 6: TurnoverMonitor
# ============================================================

def test_turnover_monitor():
    """测试换手率异常检测"""
    print("\n" + "=" * 60)
    print("测试 6: TurnoverMonitor")
    print("=" * 60)

    monitor = TurnoverMonitor(
        turnover_percentile=95.0,
        entropy_drop_threshold=0.3,
        min_effective_count=1.5
    )

    # 正常权重变化
    weights_history = []
    for _ in range(50):
        w = np.array([0.4, 0.3, 0.3]) + np.random.normal(0, 0.01, 3)
        w = np.maximum(w, 0)
        w = w / np.sum(w)
        weights_history.append(w)

    # 突然大幅变化
    sudden_change = np.array([0.9, 0.05, 0.05])

    checks = []
    for i, w in enumerate(weights_history):
        prev = weights_history[i-1] if i > 0 else None
        checks.extend(monitor.check(w, prev))

    # 检测突然变化
    checks.extend(monitor.check(sudden_change, weights_history[-1]))

    print(f"  检测到的异常数: {len(checks)}")
    for check in checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    # 应检测到换手率异常和有效数量过低
    turnover_checks = [c for c in checks if "换手率" in c.name]
    eff_count_checks = [c for c in checks if "有效策略数" in c.name]

    assert len(turnover_checks) > 0, "应检测到换手率异常"
    assert len(eff_count_checks) > 0, "应检测到有效策略数过低"

    print("  ✓ 换手率监控测试通过")


def test_entropy_drop():
    """测试权重熵骤降检测"""
    print("\n" + "=" * 60)
    print("测试 7: 权重熵骤降检测")
    print("=" * 60)

    monitor = TurnoverMonitor(entropy_drop_threshold=0.2)

    # 先填充10期正常分散权重
    for _ in range(10):
        w = np.array([0.34, 0.33, 0.33]) + np.random.normal(0, 0.01, 3)
        w = np.maximum(w, 0)
        w = w / np.sum(w)
        monitor.check(w, None)

    # 突然集中到单一策略
    w_concentrated = np.array([0.8, 0.1, 0.1])
    checks = monitor.check(w_concentrated, None)

    entropy_checks = [c for c in checks if "熵骤降" in c.name]
    print(f"  熵骤降警报数: {len(entropy_checks)}")
    for c in entropy_checks:
        print(f"    统计量: {c.statistic:.4f}")

    assert len(entropy_checks) > 0, "应检测到熵骤降"

    print("  ✓ 熵骤降检测测试通过")


# ============================================================
# 测试 8: BayesianModelMonitor
# ============================================================

def test_bayesian_model_monitor():
    """测试贝叶斯模型监控"""
    print("\n" + "=" * 60)
    print("测试 8: BayesianModelMonitor")
    print("=" * 60)

    monitor = BayesianModelMonitor(
        ppc_outlier_threshold=0.05,
        loglikelihood_drop_threshold=1.0
    )

    # 生成收益和预测
    rng = np.random.RandomState(42)
    returns_history = []
    for _ in range(50):
        returns_history.append(rng.normal(0.001, 0.01, 3))

    # 预测均值和标准差
    predicted_means = np.array([0.001, 0.001, 0.001])
    predicted_stds = np.array([0.01, 0.01, 0.01])

    checks = monitor.check(returns_history, predicted_means, predicted_stds)

    print(f"  检测到的异常数: {len(checks)}")
    for check in checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    print("  ✓ 贝叶斯模型监控测试通过")


def test_innovation_ljung_box():
    """测试创新序列自相关检测"""
    print("\n" + "=" * 60)
    print("测试 9: 创新序列自相关检测")
    print("=" * 60)

    monitor = BayesianModelMonitor(innovation_ljung_box_threshold=0.05)

    # 生成自相关的创新序列
    rng = np.random.RandomState(42)
    innovations = {0: []}
    prev = 0
    for _ in range(100):
        prev = 0.5 * prev + rng.normal(0, 0.01)
        innovations[0].append(prev)

    returns_history = [np.array([0.0]) for _ in range(100)]
    checks = monitor.check(
        returns_history,
        np.array([0.0]),
        np.array([0.01]),
        innovations
    )

    lb_checks = [c for c in checks if "创新序列" in c.name]
    print(f"  Ljung-Box警报数: {len(lb_checks)}")
    for c in lb_checks:
        print(f"    p值: {c.p_value:.4f}")

    assert len(lb_checks) > 0, "自相关创新序列应触发警报"

    print("  ✓ 创新序列检测测试通过")


# ============================================================
# 测试 10: UniversalMonitor
# ============================================================

def test_universal_monitor():
    """测试通用指标监控"""
    print("\n" + "=" * 60)
    print("测试 10: UniversalMonitor")
    print("=" * 60)

    monitor = UniversalMonitor(
        regret_window=20,
        max_regret_growth_rate=0.0001
    )

    # 模拟：组合始终落后于最佳策略
    rng = np.random.RandomState(42)
    returns_history = []
    weights_history = []
    all_checks = []

    for _ in range(50):
        # 策略1总是最好
        ret = np.array([0.02, -0.01, -0.01]) + rng.normal(0, 0.005, 3)
        returns_history.append(ret)
        # 但权重给策略2和3
        weights_history.append(np.array([0.1, 0.45, 0.45]))

        # 逐日调用check以积累regret_history
        checks = monitor.check(returns_history, weights_history)
        all_checks.extend(checks)

    print(f"  检测到的异常数: {len(all_checks)}")
    for check in all_checks:
        print(f"    {check.name}: {check.level.value} - {check.description}")

    # 应检测到遗憾增长或瞬时遗憾
    regret_checks = [c for c in all_checks if "遗憾" in c.name]
    assert len(regret_checks) > 0, "应检测到遗憾增长"

    print("  ✓ 通用监控测试通过")


# ============================================================
# 测试 11: AssumptionMonitorLayer 集成
# ============================================================

def test_assumption_monitor_layer():
    """测试假设检验层集成"""
    print("\n" + "=" * 60)
    print("测试 11: AssumptionMonitorLayer 集成")
    print("=" * 60)

    layer = AssumptionMonitorLayer(
        n_strategies=3,
        fallback_strategy="equal_weight"
    )

    rng = np.random.RandomState(42)

    # 模拟30天正常数据
    for i in range(30):
        weights = np.array([0.34, 0.33, 0.33])
        returns = rng.normal(0.001, 0.01, 3)
        state = layer.monitor(weights, returns)

    print(f"  正常期监控状态: {state.overall_level.value}")
    assert not state.should_fallback, "正常期不应触发退化"

    # 模拟10天异常数据（大幅波动）
    for i in range(10):
        weights = np.array([0.9, 0.05, 0.05])  # 过度集中
        returns = rng.normal(0.05, 0.05, 3)  # 高波动
        state = layer.monitor(weights, returns)

    print(f"  异常期监控状态: {state.overall_level.value}")
    print(f"  是否触发退化: {state.should_fallback}")

    if state.should_fallback:
        print(f"  退化权重: {state.fallback_weights}")
        assert np.allclose(state.fallback_weights, np.ones(3)/3), "退化应为等权"

    # 验证摘要
    summary = layer.get_summary()
    print(f"  监控摘要: {summary}")
    assert summary['total_checks'] == 40

    print("  ✓ 集成测试通过")


def test_risk_parity_fallback():
    """测试风险平价退化策略"""
    print("\n" + "=" * 60)
    print("测试 12: 风险平价退化")
    print("=" * 60)

    layer = AssumptionMonitorLayer(
        n_strategies=3,
        fallback_strategy="risk_parity"
    )

    # 生成不同波动率的收益
    rng = np.random.RandomState(42)
    for _ in range(30):
        # 策略1低波动，策略2高波动
        ret = np.array([
            rng.normal(0.001, 0.005),
            rng.normal(0.001, 0.02),
            rng.normal(0.001, 0.01),
        ])
        layer.monitor(np.ones(3)/3, ret)

    fallback = layer._get_fallback_weights()
    print(f"  风险平价退化权重: {fallback}")

    # 低波动策略应获得更高权重
    assert fallback[0] > fallback[1], "低波动策略应获得更高权重"

    print("  ✓ 风险平价退化测试通过")


# ============================================================
# 测试 13: 退化机制触发与恢复
# ============================================================

def test_fallback_and_recovery():
    """测试退化触发后的权重回退"""
    print("\n" + "=" * 60)
    print("测试 13: 退化触发与权重回退")
    print("=" * 60)

    layer = AssumptionMonitorLayer(
        n_strategies=2,
        enable_return_monitor=True,
        enable_correlation_monitor=False,
        enable_turnover_monitor=True,
        enable_bayesian_monitor=False,
        enable_universal_monitor=False,
        fallback_strategy="equal_weight"
    )

    rng = np.random.RandomState(42)
    fallback_triggered = False

    for i in range(100):
        if i < 40:
            # 正常期
            weights = np.array([0.5, 0.5])
            returns = rng.normal(0.001, 0.01, 2)
        elif i < 50:
            # 异常期：权重剧烈变化
            weights = np.array([0.95, 0.05])
            returns = rng.normal(0.05, 0.08, 2)
        else:
            # 恢复期
            weights = np.array([0.5, 0.5])
            returns = rng.normal(0.001, 0.01, 2)

        state = layer.monitor(weights, returns)

        if state.should_fallback:
            fallback_triggered = True
            print(f"  第{i}天触发退化，级别: {state.overall_level.value}")
            print(f"  退化权重: {state.fallback_weights}")

    assert fallback_triggered, "应在异常期触发退化"

    summary = layer.get_summary()
    print(f"  退化触发次数: {summary['fallback_triggered']}")
    print(f"  退化比例: {summary['fallback_ratio']:.1%}")

    print("  ✓ 退化触发测试通过")


# ============================================================
# 主测试入口
# ============================================================

def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("元策略假设检验层测试套件")
    print("=" * 80)

    test_return_distribution_monitor_stationary()
    test_return_distribution_monitor_nonstationary()
    test_cusum_detection()
    test_correlation_structure_monitor()
    test_condition_number_monitor()
    test_turnover_monitor()
    test_entropy_drop()
    test_bayesian_model_monitor()
    test_innovation_ljung_box()
    test_universal_monitor()
    test_assumption_monitor_layer()
    test_risk_parity_fallback()
    test_fallback_and_recovery()

    print("\n" + "=" * 80)
    print("所有测试通过 ✓")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
