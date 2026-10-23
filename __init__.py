"""Factor Trading v3.0 - 基于Backtest_Opus_2.0架构的专业量化回测框架

TD-1.2 (ADR-016): __init__.py 改为轻量, 延迟导入避免重依赖链.
原 from core.config import ... 移除, 用户需显式导入:
    from Factor_Trading_v3_0.core.config import BacktestConfig
或 (cwd=F:/Coding/Factor_Trading_v3.0):
    from core.config import BacktestConfig
"""

__version__ = "3.0.0"
__author__ = "Factor Trading Team"
