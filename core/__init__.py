# Factor_Trading_v3.0 - Core Engine
#
# TD-1.2 (ADR-016): __init__.py 改为空, 避免导入时触发重依赖链
# (cvxpy/ta/tushare/akshare 等). 用户需显式导入:
#     from Factor_Trading_v3_0.core.data_v3 import DataLoaderV3
#     from Factor_Trading_v3_0.core.engine import BacktestEngine
# 或 (cwd=F:/Coding/Factor_Trading_v3.0):
#     from core.data_v3 import DataLoaderV3
#     from core.engine import BacktestEngine
#
# 原便利导出 `from core import BacktestEngine` 已移除 (隐式导入反模式).
