"""
core - 核心模块包

包含:
- config: 配置管理
- data: 数据管理
- engine: 回测引擎
- factor: 因子处理
- portfolio: 组合优化
- execution: 交易执行
- tracker: 持仓跟踪
- rebalance: 再平衡
- pending: 待执行订单
- analytics: 绩效分析
- event_log: 事件日志（新增）
- guard_pipeline: 风控管道（新增）
- registry: 插件注册中心（新增）
"""

from __future__ import annotations

# 为了向后兼容，保留根级导入路径
# 新代码建议使用: from core.config import BacktestConfig
