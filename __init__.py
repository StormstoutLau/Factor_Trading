"""Factor Trading v3.0 - 基于Backtest_Opus_2.0架构的专业量化回测框架

本框架采用模块化设计，支持完整的待执行订单管理、多种组合优化策略、
灵活的因子处理管道和真实市场约束模拟。

主要特性:
- 完整的待执行订单管理系统
- 多种组合优化策略（等权重、最小方差、均值方差、风险平价）
- 灵活的因子处理管道
- 真实市场约束（停牌、涨跌停、交易成本）
- 整手数优化
- 详细的性能分析
"""

__version__ = "3.0.0"
__author__ = "Factor Trading Team"

from config import (
    BacktestConfig,
    CostConfig,
    UniverseConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig
)

from engine import BacktestEngine

__all__ = [
    "BacktestConfig",
    "CostConfig", 
    "UniverseConfig",
    "FactorConfig",
    "OptimizerConfig",
    "RebalanceConfig",
    "BacktestEngine"
]
