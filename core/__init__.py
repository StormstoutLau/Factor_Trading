# Factor_Trading_v3.0 - Core Engine
#
# TD-1.2 (ADR-016): __init__.py 改为空, 避免导入时触发重依赖链
# (cvxpy/ta/tushare/akshare 等). 用户需显式导入:
#     from Factor_Trading_v3_0.core.data_v3 import DataLoaderV3
#     from Factor_Trading_v3_0.core.factory import create_default_engine
# 或 (cwd=F:/Coding/Factor_Trading_v3.0):
#     from core.data_v3 import DataLoaderV3
#     from core.factory import create_default_engine
#
# 原便利导出 `from core import BacktestEngine` 已移除 (隐式导入反模式).
#
# P-012 D7 (T-11): 仅元数据版本号，不恢复重导出.
__api_version__ = "3.1.0"
