"""批量回测模块

支持对多个因子/策略进行批量回测，自动聚合结果。
"""

from batch_backtest.engine import BatchBacktestEngine

__all__ = ['BatchBacktestEngine']
