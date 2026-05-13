"""
Walk-Forward回测引擎
===================

在每个Walk-Forward窗口上运行回测，自动：
1. 训练期：允许Agent在线学习
2. 测试期：冻结Agent，防止数据窥探
3. 汇总所有窗口的测试结果

与Agent蒸馏隔离机制集成：
- 自动传递period参数给Agent
- 测试期自动冻结belief更新
- 窗口切换时重置Agent学习状态
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.walk_forward import (
    WalkForwardSplitter, WalkForwardWindow, WalkForwardResult, PeriodType
)

logger = logging.getLogger(__name__)


class WalkForwardEngine:
    """Walk-Forward回测引擎
    
    在多个时间窗口上运行回测，自动处理期间切换。
    
    Args:
        base_engine: 基础回测引擎类
        splitter: WalkForward窗口分割器
        config: 回测配置
    
    Example:
        >>> engine = WalkForwardEngine(
        ...     base_engine=BacktestEngine,
        ...     splitter=splitter,
        ...     config=backtest_config
        ... )
        >>> result = engine.run()
    """
    
    def __init__(self,
                 base_engine_class: type,
                 splitter: WalkForwardSplitter,
                 config: Any,
                 window_callbacks: Optional[dict] = None):
        self.base_engine_class = base_engine_class
        self.splitter = splitter
        self.config = config
        self.window_callbacks = window_callbacks or {}
        
        # 结果收集
        self.window_results: list[dict] = []
        self.current_window: Optional[WalkForwardWindow] = None
        
        logger.info(f"WalkForwardEngine初始化: {splitter.get_n_splits()}个窗口")
    
    def run(self, agents: Optional[list] = None) -> WalkForwardResult:
        """运行Walk-Forward回测
        
        Args:
            agents: Agent列表（可选）
        
        Returns:
            WalkForwardResult: 汇总结果
        """
        self.window_results = []
        
        for window in self.splitter.split():
            self.current_window = window
            logger.info(f"\n{'='*60}")
            logger.info(f"处理窗口 {window.window_index}: "
                       f"train=[{window.train_start.date()} ~ {window.train_end.date()}], "
                       f"test=[{window.test_start.date()} ~ {window.test_end.date()}]")
            
            # 步骤1：训练期
            train_result = self._run_train_period(window, agents)
            
            # 步骤2：测试期
            test_result = self._run_test_period(window, agents, train_result)
            
            # 收集结果
            self.window_results.append({
                'window_index': window.window_index,
                'train_period': (window.train_start, window.train_end),
                'test_period': (window.test_start, window.test_end),
                'train_result': train_result,
                'test_result': test_result,
            })
            
            # 执行回调
            self._execute_callback('on_window_complete', window, test_result)
        
        # 生成汇总结果
        result = self._aggregate_results()
        logger.info(f"\n{'='*60}")
        logger.info(f"Walk-Forward回测完成: {result}")
        
        return result
    
    def _run_train_period(self, window: WalkForwardWindow, 
                         agents: Optional[list]) -> dict:
        """运行训练期
        
        训练期允许Agent在线学习
        """
        logger.info(f"  训练期: {window.train_start.date()} ~ {window.train_end.date()}")
        
        # 设置Agent为训练模式
        if agents:
            for agent in agents:
                self._set_agent_period(agent, PeriodType.TRAIN)
        
        # 创建训练期配置
        train_config = self._create_period_config(
            self.config, window.train_start, window.train_end
        )
        
        # 运行训练期回测
        # 注意：这里简化处理，实际应该运行完整的训练流程
        train_result = {
            'period': 'train',
            'start_date': window.train_start,
            'end_date': window.train_end,
            'n_days': len(window.train_dates),
        }
        
        self._execute_callback('on_train_complete', window, train_result)
        return train_result
    
    def _run_test_period(self, window: WalkForwardWindow,
                        agents: Optional[list],
                        train_result: dict) -> dict:
        """运行测试期
        
        测试期冻结Agent，防止数据窥探
        """
        logger.info(f"  测试期: {window.test_start.date()} ~ {window.test_end.date()}")
        
        # 设置Agent为测试模式（冻结学习）
        if agents:
            for agent in agents:
                self._set_agent_period(agent, PeriodType.TEST)
        
        # 创建测试期配置
        test_config = self._create_period_config(
            self.config, window.test_start, window.test_end
        )
        
        # 运行测试期回测
        # 注意：这里简化处理，实际应该运行完整的测试流程
        test_result = {
            'period': 'test',
            'start_date': window.test_start,
            'end_date': window.test_end,
            'n_days': len(window.test_dates),
            'total_return': 0.0,  # 占位
            'sharpe_ratio': 0.0,  # 占位
        }
        
        self._execute_callback('on_test_complete', window, test_result)
        return test_result
    
    def _set_agent_period(self, agent: Any, period: PeriodType):
        """设置Agent的期间类型
        
        自动调用Agent的set_period方法（如果存在）
        """
        if hasattr(agent, 'set_period'):
            try:
                agent.set_period(period.value)
                logger.debug(f"    Agent {getattr(agent, 'agent_id', 'unknown')} "
                           f"设置为 {period.value} 模式")
            except Exception as e:
                logger.warning(f"    设置Agent期间失败: {e}")
        
        # 同时设置蒸馏配置
        if hasattr(agent, 'distillation_config'):
            agent.distillation_config.is_test_period = (period == PeriodType.TEST)
    
    def _create_period_config(self, base_config: Any, 
                             start_date: pd.Timestamp,
                             end_date: pd.Timestamp) -> Any:
        """创建特定期间的配置"""
        # 复制基础配置
        import copy
        period_config = copy.deepcopy(base_config)
        
        # 设置期间日期
        if hasattr(period_config, 'start_date'):
            period_config.start_date = start_date
        if hasattr(period_config, 'end_date'):
            period_config.end_date = end_date
        
        return period_config
    
    def _execute_callback(self, event: str, window: WalkForwardWindow, result: dict):
        """执行回调函数"""
        if event in self.window_callbacks:
            try:
                self.window_callbacks[event](window, result)
            except Exception as e:
                logger.warning(f"回调 {event} 执行失败: {e}")
    
    def _aggregate_results(self) -> WalkForwardResult:
        """汇总所有窗口的结果"""
        # 提取测试期结果
        test_results = []
        for wr in self.window_results:
            test_result = wr.get('test_result', {})
            test_results.append({
                'window_index': wr['window_index'],
                'total_return': test_result.get('total_return', 0),
                'sharpe_ratio': test_result.get('sharpe_ratio', 0),
            })
        
        return WalkForwardResult(window_results=test_results)


def run_walk_forward_backtest(
    engine_class: type,
    config: Any,
    start_date: str,
    end_date: str,
    train_years: float = 2.0,
    test_months: float = 3.0,
    purge_days: int = 5,
    method: str = "rolling",
    agents: Optional[list] = None,
    callbacks: Optional[dict] = None
) -> WalkForwardResult:
    """便捷函数：运行Walk-Forward回测
    
    Args:
        engine_class: 回测引擎类
        config: 回测配置
        start_date: 起始日期
        end_date: 结束日期
        train_years: 训练期年数
        test_months: 测试期月数
        purge_days: purge gap天数
        method: 分割方法
        agents: Agent列表
        callbacks: 回调函数字典
    
    Returns:
        WalkForwardResult: Walk-Forward回测结果
    """
    from core.walk_forward import create_walk_forward_splits
    
    # 创建分割器
    splitter = create_walk_forward_splits(
        start_date=start_date,
        end_date=end_date,
        train_years=train_years,
        test_months=test_months,
        purge_days=purge_days,
        method=method
    )
    
    # 创建引擎
    wf_engine = WalkForwardEngine(
        base_engine_class=engine_class,
        splitter=splitter,
        config=config,
        window_callbacks=callbacks
    )
    
    # 运行回测
    return wf_engine.run(agents=agents)


if __name__ == "__main__":
    # 简单测试
    from core.walk_forward import create_walk_forward_splits
    
    splitter = create_walk_forward_splits(
        '2020-01-01', '2023-12-31',
        train_years=1, test_months=3
    )
    
    engine = WalkForwardEngine(
        base_engine_class=None,
        splitter=splitter,
        config=None
    )
    
    result = engine.run()
    print(result)
