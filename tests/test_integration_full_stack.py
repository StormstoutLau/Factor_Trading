"""
全栈集成测试：风控 + 假设检验 + 多策略动态分配

验证三个模块的联动逻辑：
1. 多策略动态分配产生权重
2. 假设检验层监控分配器的隐含假设
3. 风控模块监控持仓标的风险
4. 当任一模块触发高风险时，整体系统应正确响应
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.strategy_allocator import StrategyAllocationManager
from agents.assumption_monitor import AssumptionMonitorLayer, AlertLevel
from core.risk_monitor import (
    CompositeRiskEngine,
    FundamentalMonitor,
    IndustryMonitor,
    MacroMonitor,
    CapitalFlowMonitor,
    SentimentMonitor,
    RiskLevel,
)


# ============================================================
# 辅助函数
# ============================================================

def generate_market_scenario(n_days: int, scenario: str = "normal", seed: int = 42):
    """生成不同市场场景下的策略收益"""
    rng = np.random.RandomState(seed)
    returns = np.zeros((n_days, 3))

    if scenario == "normal":
        # 正常市场：动量略好
        returns[:, 0] = rng.normal(0.001, 0.012, n_days)
        returns[:, 1] = rng.normal(0.0005, 0.010, n_days)
        returns[:, 2] = rng.normal(0.000, 0.015, n_days)
    elif scenario == "bull":
        # 牛市：动量策略大幅领先
        returns[:, 0] = rng.normal(0.005, 0.012, n_days)
        returns[:, 1] = rng.normal(0.002, 0.010, n_days)
        returns[:, 2] = rng.normal(-0.001, 0.015, n_days)
    elif scenario == "crash":
        # 崩盘：所有策略亏损，动量亏最多
        returns[:, 0] = rng.normal(-0.008, 0.025, n_days)
        returns[:, 1] = rng.normal(-0.003, 0.020, n_days)
        returns[:, 2] = rng.normal(-0.005, 0.030, n_days)
    elif scenario == "regime_change":
        # 前半牛市，后半崩盘
        mid = n_days // 2
        returns[:mid, 0] = rng.normal(0.005, 0.012, mid)
        returns[:mid, 1] = rng.normal(0.002, 0.010, mid)
        returns[:mid, 2] = rng.normal(-0.001, 0.015, mid)
        returns[mid:, 0] = rng.normal(-0.008, 0.025, n_days - mid)
        returns[mid:, 1] = rng.normal(-0.003, 0.020, n_days - mid)
        returns[mid:, 2] = rng.normal(-0.005, 0.030, n_days - mid)

    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    return returns, dates


# ============================================================
# 测试 1: 正常市场下的全栈运行
# ============================================================

def test_normal_market():
    """正常市场：分配器正常工作，假设检验不触发，风控安全"""
    print("\n" + "=" * 70)
    print("测试 1: 正常市场全栈运行")
    print("=" * 70)

    returns, dates = generate_market_scenario(60, "normal")

    # 初始化三个模块
    allocator = StrategyAllocationManager(
        strategy_names=["动量策略", "价值策略", "均值回归策略"],
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.95,
        turnover_penalty=0.01,
        min_weight=0.1,
    )

    assumption_layer = AssumptionMonitorLayer(
        n_strategies=3,
        fallback_strategy="equal_weight"
    )

    risk_engine = CompositeRiskEngine()

    # 模拟每日运行
    portfolio_returns = []
    fallback_count = 0
    risk_alerts = []

    for i, (ret, date) in enumerate(zip(returns, dates)):
        # 1. 动态分配
        weights = allocator.update(ret, date)

        # 2. 假设检验监控
        pred_means = allocator.evaluator.get_expected_returns()
        pred_stds = allocator.evaluator.get_uncertainty()
        monitor_state = assumption_layer.monitor(
            weights, ret,
            predicted_means=pred_means,
            predicted_stds=pred_stds
        )

        if monitor_state.should_fallback:
            weights = monitor_state.fallback_weights
            fallback_count += 1

        # 3. 风控监控（模拟组合级）
        risk_signal, risk_actions = risk_engine.evaluate(symbol=None)
        if risk_signal.level.value >= RiskLevel.MEDIUM.value:
            risk_alerts.append((date, risk_signal))

        # 4. 计算组合收益
        portfolio_returns.append(np.dot(weights, ret))

    # 验证
    cumulative_return = np.sum(portfolio_returns)
    print(f"  组合累计收益: {cumulative_return:.4f}")
    print(f"  退化触发次数: {fallback_count}")
    print(f"  风控警报次数: {len(risk_alerts)}")

    assert fallback_count == 0, "正常市场不应触发退化"
    assert len(risk_alerts) == 0, "正常市场不应触发风控警报"
    print("  ✓ 正常市场测试通过")


# ============================================================
# 测试 2: 崩盘市场下的全栈运行
# ============================================================

def test_crash_market():
    """崩盘市场：假设检验应触发退化，风控应发出警报"""
    print("\n" + "=" * 70)
    print("测试 2: 崩盘市场全栈运行")
    print("=" * 70)

    returns, dates = generate_market_scenario(60, "crash")

    allocator = StrategyAllocationManager(
        strategy_names=["动量策略", "价值策略", "均值回归策略"],
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.95,
        turnover_penalty=0.01,
        min_weight=0.1,
    )

    assumption_layer = AssumptionMonitorLayer(
        n_strategies=3,
        fallback_strategy="equal_weight"
    )

    risk_engine = CompositeRiskEngine()

    portfolio_returns = []
    fallback_count = 0
    risk_alerts = []

    for i, (ret, date) in enumerate(zip(returns, dates)):
        weights = allocator.update(ret, date)

        pred_means = allocator.evaluator.get_expected_returns()
        pred_stds = allocator.evaluator.get_uncertainty()
        monitor_state = assumption_layer.monitor(
            weights, ret,
            predicted_means=pred_means,
            predicted_stds=pred_stds
        )

        if monitor_state.should_fallback:
            weights = monitor_state.fallback_weights
            fallback_count += 1

        # 模拟崩盘时的高风险信号
        if i > 30:  # 模拟后期崩盘加剧
            risk_signal, risk_actions = risk_engine.evaluate(
                symbol=None,
                fundamental={
                    'earnings_miss': True,
                    'financial_data': {'debt_ratio': 0.9, 'operating_cashflow': -100, 'revenue_growth': -0.5},
                    'events': ['lawsuit', 'insider_selling']
                },
                industry={'policy_restrictions': True, 'tech_disruption': True},
                macro={'pmi': 45.0, 'interest_rate_hike': True, 'geopolitical_conflict': True},
                capital={'main_force_outflow': -500, 'northbound_net_flow': -200},
                sentiment={'limit_down_count': 50, 'margin_balance_drop': -0.15, 'vix_spike': True}
            )
        else:
            risk_signal, risk_actions = risk_engine.evaluate(symbol=None)

        if risk_signal.level.value >= RiskLevel.MEDIUM.value:
            risk_alerts.append((date, risk_signal))

        portfolio_returns.append(np.dot(weights, ret))

    cumulative_return = np.sum(portfolio_returns)
    print(f"  组合累计收益: {cumulative_return:.4f}")
    print(f"  退化触发次数: {fallback_count}")
    print(f"  风控警报次数: {len(risk_alerts)}")

    # 崩盘市场应触发风控
    assert len(risk_alerts) > 0, "崩盘市场应触发风控警报"
    print("  ✓ 崩盘市场测试通过")


# ============================================================
# 测试 3: 状态切换下的全栈运行
# ============================================================

def test_regime_change():
    """状态切换：假设检验应检测到非平稳性并触发退化"""
    print("\n" + "=" * 70)
    print("测试 3: 状态切换全栈运行")
    print("=" * 70)

    returns, dates = generate_market_scenario(100, "regime_change")

    allocator = StrategyAllocationManager(
        strategy_names=["动量策略", "价值策略", "均值回归策略"],
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.97,
        turnover_penalty=0.005,
        min_weight=0.1,
    )

    assumption_layer = AssumptionMonitorLayer(
        n_strategies=3,
        fallback_strategy="equal_weight"
    )

    portfolio_returns = []
    weights_history = []
    fallback_count = 0
    fallback_days = []

    for i, (ret, date) in enumerate(zip(returns, dates)):
        weights = allocator.update(ret, date)

        pred_means = allocator.evaluator.get_expected_returns()
        pred_stds = allocator.evaluator.get_uncertainty()
        monitor_state = assumption_layer.monitor(
            weights, ret,
            predicted_means=pred_means,
            predicted_stds=pred_stds
        )

        if monitor_state.should_fallback:
            weights = monitor_state.fallback_weights
            fallback_count += 1
            fallback_days.append(i)

        portfolio_returns.append(np.dot(weights, ret))
        weights_history.append(weights.copy())

    weights_history = np.array(weights_history)

    # 分析
    cumulative_return = np.sum(portfolio_returns)
    print(f"  组合累计收益: {cumulative_return:.4f}")
    print(f"  退化触发次数: {fallback_count}")
    if fallback_days:
        print(f"  首次退化日期: 第{fallback_days[0]}天")

    # 验证：状态切换后应触发退化
    assert fallback_count > 0, "状态切换应触发假设检验退化"

    # 验证：退化后权重应更分散
    if fallback_days:
        post_fallback_weights = weights_history[fallback_days[0]:]
        avg_weight_std = np.mean(np.std(post_fallback_weights, axis=1))
        print(f"  退化后权重标准差均值: {avg_weight_std:.4f}")
        assert avg_weight_std < 0.15, "退化后权重应更分散"

    print("  ✓ 状态切换测试通过")


# ============================================================
# 测试 4: 权重过度集中时的联动
# ============================================================

def test_concentration_risk():
    """权重过度集中：假设检验应检测到过拟合并触发退化"""
    print("\n" + "=" * 70)
    print("测试 4: 权重过度集中联动测试")
    print("=" * 70)

    rng = np.random.RandomState(42)
    n_days = 50

    allocator = StrategyAllocationManager(
        strategy_names=["策略A", "策略B", "策略C"],
        allocator_type='ftrl',
        learning_rate=0.5,  # 高学习率导致权重快速集中
        forget_factor=1.0,
        turnover_penalty=0.0,  # 无换手率惩罚
        min_weight=0.0,  # 无最小权重约束
    )

    assumption_layer = AssumptionMonitorLayer(
        n_strategies=3,
        enable_turnover_monitor=True,
        enable_return_monitor=False,
        enable_correlation_monitor=False,
        enable_bayesian_monitor=False,
        enable_universal_monitor=False,
        fallback_strategy="equal_weight"
    )

    # 策略A持续略好，导致权重过度集中
    for i in range(n_days):
        ret = np.array([0.02, 0.001, 0.001]) + rng.normal(0, 0.01, 3)
        date = datetime(2024, 1, 1) + timedelta(days=i)

        weights = allocator.update(ret, date)
        monitor_state = assumption_layer.monitor(weights, ret)

        if monitor_state.should_fallback:
            print(f"  第{i}天触发退化，权重从 {weights.round(3)} 回退到等权")
            weights = monitor_state.fallback_weights

    final_weights = allocator.get_weights()
    print(f"  最终权重（未退化时）: {final_weights}")

    summary = assumption_layer.get_summary()
    print(f"  假设检验摘要: {summary}")

    assert summary['fallback_triggered'] > 0, "权重过度集中应触发退化"
    print("  ✓ 权重过度集中测试通过")


# ============================================================
# 测试 5: 综合报告生成
# ============================================================

def test_comprehensive_report():
    """生成综合报告，验证三个模块的数据一致性"""
    print("\n" + "=" * 70)
    print("测试 5: 综合报告一致性")
    print("=" * 70)

    returns, dates = generate_market_scenario(40, "normal")

    allocator = StrategyAllocationManager(
        strategy_names=["动量策略", "价值策略", "均值回归策略"],
        allocator_type='ftrl',
        learning_rate=0.1,
        forget_factor=0.95,
    )

    assumption_layer = AssumptionMonitorLayer(n_strategies=3)
    risk_engine = CompositeRiskEngine()

    daily_records = []

    for i, (ret, date) in enumerate(zip(returns, dates)):
        weights = allocator.update(ret, date)

        pred_means = allocator.evaluator.get_expected_returns()
        pred_stds = allocator.evaluator.get_uncertainty()
        monitor_state = assumption_layer.monitor(weights, ret, pred_means, pred_stds)

        risk_signal, risk_actions = risk_engine.evaluate(symbol=None)

        daily_records.append({
            'date': date,
            'weights': weights.copy(),
            'returns': ret.copy(),
            'portfolio_return': np.dot(weights, ret),
            'assumption_level': monitor_state.overall_level.value,
            'should_fallback': monitor_state.should_fallback,
            'risk_level': risk_signal.level.value,
            'risk_score': risk_signal.score,
        })

    # 生成综合报告
    portfolio_returns = [r['portfolio_return'] for r in daily_records]
    cumulative = np.cumsum(portfolio_returns)

    fallback_days = sum(1 for r in daily_records if r['should_fallback'])
    risk_alert_days = sum(1 for r in daily_records if r['risk_level'] >= RiskLevel.MEDIUM.value)

    print(f"\n  【综合报告】")
    print(f"  总交易日: {len(daily_records)}")
    print(f"  组合累计收益: {cumulative[-1]:.4f}")
    print(f"  组合夏普比率: {np.mean(portfolio_returns)/(np.std(portfolio_returns)+1e-8):.4f}")
    print(f"  假设检验退化天数: {fallback_days}")
    print(f"  风控警报天数: {risk_alert_days}")
    print(f"  最终权重: {allocator.get_weights()}")

    # 验证数据一致性
    assert len(daily_records) == 40, "记录数应等于交易日数"
    assert all(abs(np.sum(r['weights']) - 1.0) < 1e-6 for r in daily_records), "权重和应始终为1"

    print("  ✓ 综合报告一致性测试通过")


# ============================================================
# 主测试入口
# ============================================================

def run_all_tests():
    """运行所有集成测试"""
    print("\n" + "=" * 80)
    print("全栈集成测试：风控 + 假设检验 + 多策略动态分配")
    print("=" * 80)

    test_normal_market()
    test_crash_market()
    test_regime_change()
    test_concentration_risk()
    test_comprehensive_report()

    print("\n" + "=" * 80)
    print("所有集成测试通过 ✓")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()
