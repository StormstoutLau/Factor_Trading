# Factor_Trading_v3.0 - Core Engine
#
# 核心模块公共 API 导出
# 使用方式: from core import BacktestEngine, BacktestConfig, ...
#

from core.config import (
    BacktestConfig,
    CostConfig,
    ExecutionPriceType,
    FactorConfig,
    MarginConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.engine import BacktestEngine
from core.data import DataManager
from core.factor import FactorPipeline, FactorCombiner
from core.execution import ExecutionSimulator, Trade
from core.portfolio import BaseOptimizer, build_optimizer
from core.rebalance import BaseTrigger, build_trigger
from core.tracker import PositionTracker, PortfolioSnapshot
from core.pending import OrderSide, PendingOrderQueue, create_pending_order
from core.execution_policy import (
    ExecutionTiming,
    OrderIntent,
    ExecutionResult,
    ExecutionPolicy,
    T1StockPolicy,
    T0FuturesPolicy,
    SignalTranslator,
)
from core.analytics import PerformanceAnalyzer, generate_report

__all__ = [
    # Config
    "BacktestConfig",
    "CostConfig",
    "ExecutionPriceType",
    "FactorConfig",
    "OptimizerConfig",
    "RebalanceConfig",
    "UniverseConfig",
    "MarginConfig",
    # Engine
    "BacktestEngine",
    # Data
    "DataManager",
    # Factor
    "FactorPipeline",
    "FactorCombiner",
    # Execution
    "ExecutionSimulator",
    "Trade",
    # Portfolio
    "BaseOptimizer",
    "build_optimizer",
    # Rebalance
    "BaseTrigger",
    "build_trigger",
    # Tracker
    "PositionTracker",
    "PortfolioSnapshot",
    # Pending
    "OrderSide",
    "PendingOrderQueue",
    "create_pending_order",
    # Execution Policy
    "ExecutionTiming",
    "OrderIntent",
    "ExecutionResult",
    "ExecutionPolicy",
    "T1StockPolicy",
    "T0FuturesPolicy",
    "SignalTranslator",
    # Analytics
    "PerformanceAnalyzer",
    "generate_report",
]