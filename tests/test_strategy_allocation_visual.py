"""
策略权重时间序列可视化测试

展示动态资金分配在多策略回测中的权重变化过程。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.strategy_allocator import StrategyAllocationManager


def generate_regime_switching_returns(n_days: int = 300) -> tuple[np.ndarray, list[datetime], list[str]]:
    """生成带有状态切换的策略收益

    模拟三个策略在不同市场状态下的表现：
    - 0-100天: 牛市（动量策略好）
    - 100-200天: 震荡市（均值回归策略好）
    - 200-300天: 熊市（空头策略好）
    """
    rng = np.random.RandomState(42)
    returns = np.zeros((n_days, 3))
    regimes = []

    for i in range(n_days):
        if i < 100:
            # 牛市: 动量策略好
            regimes.append("bull")
            returns[i] = [
                rng.normal(0.003, 0.015),   # 动量策略: 高正收益
                rng.normal(0.001, 0.012),   # 价值策略: 中等
                rng.normal(-0.002, 0.02),   # 均值回归: 负收益
            ]
        elif i < 200:
            # 震荡市: 均值回归策略好
            regimes.append("range")
            returns[i] = [
                rng.normal(-0.001, 0.018),  # 动量策略: 亏损
                rng.normal(0.000, 0.010),   # 价值策略: 持平
                rng.normal(0.002, 0.008),   # 均值回归: 正收益
            ]
        else:
            # 熊市: 空头策略相对好（或亏得少）
            regimes.append("bear")
            returns[i] = [
                rng.normal(-0.003, 0.020),  # 动量策略: 大亏
                rng.normal(-0.001, 0.015),  # 价值策略: 小亏
                rng.normal(0.001, 0.012),   # 均值回归: 微盈
            ]

    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    return returns, dates, regimes


def visualize_allocation_weights():
    """可视化策略权重变化"""
    print("\n" + "=" * 80)
    print("策略权重时间序列可视化")
    print("=" * 80)

    strategy_names = ["动量策略", "价值策略", "均值回归策略"]
    returns, dates, regimes = generate_regime_switching_returns(300)

    # 使用FTRL分配器（带遗忘因子，适应非平稳环境）
    manager = StrategyAllocationManager(
        strategy_names=strategy_names,
        allocator_type='ftrl',
        learning_rate=0.15,
        forget_factor=0.97,
        turnover_penalty=0.005,
        min_weight=0.1,
        max_weight=0.7
    )

    # 逐日更新
    weights_history = []
    portfolio_returns = []

    for i, (ret, date) in enumerate(zip(returns, dates)):
        weights = manager.update(ret, date, adapt_meta=True)
        weights_history.append(weights.copy())
        portfolio_returns.append(np.dot(weights, ret))

    weights_history = np.array(weights_history)
    portfolio_returns = np.array(portfolio_returns)

    # 计算累计收益
    cumulative_returns = np.cumsum(portfolio_returns)
    strategy_cumreturns = np.cumsum(returns, axis=0)

    # 输出关键统计
    print(f"\n【回测统计】")
    print(f"  总天数: {len(dates)}")
    print(f"  组合累计收益: {cumulative_returns[-1]:.4f}")
    print(f"  组合夏普比率: {np.mean(portfolio_returns) / (np.std(portfolio_returns) + 1e-8):.4f}")
    print(f"  组合最大回撤: {np.min(cumulative_returns - np.maximum.accumulate(cumulative_returns)):.4f}")

    print(f"\n【各策略累计收益】")
    for i, name in enumerate(strategy_names):
        print(f"  {name}: {strategy_cumreturns[-1, i]:.4f}")

    print(f"\n【最终权重】")
    final_weights = manager.get_weights()
    for name, w in final_weights.items():
        print(f"  {name}: {w:.4f}")

    # 按市场状态统计平均权重
    print(f"\n【各市场状态下的平均权重】")
    regime_names = {"bull": "牛市", "range": "震荡市", "bear": "熊市"}
    for regime_key, regime_label in regime_names.items():
        mask = np.array([r == regime_key for r in regimes])
        if np.any(mask):
            avg_weights = np.mean(weights_history[mask], axis=0)
            print(f"  {regime_label}:")
            for i, name in enumerate(strategy_names):
                print(f"    {name}: {avg_weights[i]:.4f}")

    # 权重变化统计
    weight_changes = np.diff(weights_history, axis=0)
    avg_daily_turnover = np.mean(np.sum(np.abs(weight_changes), axis=1)) / 2
    print(f"\n【换手率统计】")
    print(f"  日均换手率: {avg_daily_turnover:.4f}")
    print(f"  最大单日换手: {np.max(np.sum(np.abs(weight_changes), axis=1)) / 2:.4f}")

    # 尝试生成可视化图表
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        # 图1: 权重时间序列
        ax1 = axes[0]
        colors = ['#e74c3c', '#3498db', '#2ecc71']
        for i, name in enumerate(strategy_names):
            ax1.plot(dates, weights_history[:, i], label=name, color=colors[i], linewidth=1.5)
        ax1.axvline(x=dates[100], color='gray', linestyle='--', alpha=0.5, label='状态切换')
        ax1.axvline(x=dates[200], color='gray', linestyle='--', alpha=0.5)
        ax1.set_ylabel('权重', fontsize=12)
        ax1.set_title('动态资金分配权重变化', fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=10)
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3)

        # 添加市场状态标注
        ax1.text(dates[50], 0.95, '牛市', ha='center', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
        ax1.text(dates[150], 0.95, '震荡市', ha='center', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
        ax1.text(dates[250], 0.95, '熊市', ha='center', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.5))

        # 图2: 累计收益对比
        ax2 = axes[1]
        ax2.plot(dates, cumulative_returns, label='动态分配组合', color='purple', linewidth=2)
        for i, name in enumerate(strategy_names):
            ax2.plot(dates, strategy_cumreturns[:, i], label=name, color=colors[i],
                    linewidth=1, alpha=0.6, linestyle='--')
        ax2.axvline(x=dates[100], color='gray', linestyle='--', alpha=0.5)
        ax2.axvline(x=dates[200], color='gray', linestyle='--', alpha=0.5)
        ax2.set_ylabel('累计收益', fontsize=12)
        ax2.set_title('累计收益对比', fontsize=14, fontweight='bold')
        ax2.legend(loc='upper left', fontsize=10)
        ax2.grid(True, alpha=0.3)

        # 图3: 每日收益
        ax3 = axes[2]
        ax3.bar(dates, portfolio_returns, color='steelblue', alpha=0.6, width=0.8)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax3.axvline(x=dates[100], color='gray', linestyle='--', alpha=0.5)
        ax3.axvline(x=dates[200], color='gray', linestyle='--', alpha=0.5)
        ax3.set_ylabel('日收益', fontsize=12)
        ax3.set_xlabel('日期', fontsize=12)
        ax3.set_title('组合每日收益', fontsize=14, fontweight='bold')
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存图表
        output_path = Path(__file__).parent.parent / "output" / "strategy_allocation_weights.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"\n  图表已保存: {output_path}")

        plt.close()

    except ImportError:
        print("\n  未安装matplotlib，跳过图表生成")
    except Exception as e:
        print(f"\n  图表生成失败: {e}")

    print("\n" + "=" * 80)
    print("可视化完成")
    print("=" * 80)


def compare_allocators():
    """对比不同分配器的表现"""
    print("\n" + "=" * 80)
    print("不同分配器对比")
    print("=" * 80)

    strategy_names = ["动量策略", "价值策略", "均值回归策略"]
    returns, dates, regimes = generate_regime_switching_returns(300)

    allocator_configs = {
        '等权固定': {'type': 'ftrl', 'kwargs': {'learning_rate': 0.0}, 'desc': '基准: 始终1/3等权'},
        'Hedge': {'type': 'hedge', 'kwargs': {'learning_rate': 0.1, 'forget_factor': 0.97}, 'desc': '指数加权平均'},
        'FTRL': {'type': 'ftrl', 'kwargs': {'learning_rate': 0.15, 'forget_factor': 0.97, 'turnover_penalty': 0.005}, 'desc': '在线凸优化'},
        'UCB': {'type': 'ucb', 'kwargs': {'exploration_coeff': 1.5, 'min_weight': 0.1}, 'desc': '上置信界'},
        'Thompson': {'type': 'thompson', 'kwargs': {'temperature': 1.0, 'min_weight': 0.1}, 'desc': '贝叶斯采样'},
    }

    results = []

    for name, config in allocator_configs.items():
        manager = StrategyAllocationManager(
            strategy_names=strategy_names,
            allocator_type=config['type'],
            **config['kwargs']
        )

        portfolio_returns = []
        for ret, date in zip(returns, dates):
            weights = manager.update(ret, date, adapt_meta=False)
            portfolio_returns.append(np.dot(weights, ret))

        portfolio_returns = np.array(portfolio_returns)
        cumulative = np.cumsum(portfolio_returns)

        sharpe = np.mean(portfolio_returns) / (np.std(portfolio_returns) + 1e-8)
        max_dd = np.min(cumulative - np.maximum.accumulate(cumulative))
        final_return = cumulative[-1]

        # 计算换手率
        weights_history = np.array([w for _, w in manager.weight_history])
        if len(weights_history) > 1:
            turnover = np.mean(np.sum(np.abs(np.diff(weights_history, axis=0)), axis=1)) / 2
        else:
            turnover = 0.0

        results.append({
            'name': name,
            'desc': config['desc'],
            'final_return': final_return,
            'sharpe': sharpe,
            'max_dd': max_dd,
            'turnover': turnover,
        })

    print(f"\n{'分配器':<12} {'描述':<20} {'累计收益':>10} {'夏普比率':>10} {'最大回撤':>10} {'日均换手':>10}")
    print("-" * 80)
    for r in results:
        print(f"{r['name']:<12} {r['desc']:<20} {r['final_return']:>10.4f} {r['sharpe']:>10.4f} {r['max_dd']:>10.4f} {r['turnover']:>10.4f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    visualize_allocation_weights()
    compare_allocators()
