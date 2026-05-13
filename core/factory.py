"""组件工厂 - 集中管理模块创建

支持配置驱动的组件实例化，实现插拔式架构。
所有组件通过工厂创建，便于统一管理和替换。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.config import BacktestConfig
from core.data import DataManager
from core.execution import ExecutionSimulator
from core.factor import FactorCombiner, FactorPipeline
from core.interfaces import (
    IDataManager,
    IExecutionSimulator,
    IFactorCombiner,
    IFactorPipeline,
    IOptimizer,
    IPendingOrderQueue,
    IPositionTracker,
    IRebalanceTrigger,
    IUniverseFilter,
)
from core.pending import PendingOrderQueue
from core.portfolio import build_optimizer
from core.rebalance import build_trigger
from core.tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter

logger = logging.getLogger(__name__)


class ComponentFactory:
    """组件工厂
    
    集中管理所有回测组件的创建，支持：
    - 默认组件创建
    - 自定义组件注册
    - 配置驱动的实例化
    
    Example:
        # 创建默认引擎所需的所有组件
        factory = ComponentFactory(config)
        components = factory.create_all()
        
        # 创建引擎（使用工厂创建的组件）
        engine = BacktestEngineV2(config, **components)
        
        # 注册自定义组件
        factory.register('data_manager', MyDataManager)
        factory.register('optimizer', MyOptimizer)
    """
    
    # 组件注册表
    _registry: dict[str, type] = {}
    
    def __init__(self, config: BacktestConfig):
        """初始化工厂
        
        Args:
            config: 回测配置
        """
        self.cfg = config
    
    @classmethod
    def register(cls, component_type: str, component_class: type) -> None:
        """注册自定义组件
        
        Args:
            component_type: 组件类型标识
            component_class: 组件类
            
        Example:
            ComponentFactory.register('data_manager', APIDataManager)
            ComponentFactory.register('optimizer', MyOptimizer)
        """
        cls._registry[component_type] = component_class
        logger.info(f"注册组件: {component_type} -> {component_class.__name__}")
    
    @classmethod
    def unregister(cls, component_type: str) -> None:
        """注销组件
        
        Args:
            component_type: 组件类型标识
        """
        if component_type in cls._registry:
            del cls._registry[component_type]
            logger.info(f"注销组件: {component_type}")
    
    def _create_component(self, component_type: str, default_factory: callable, *args, **kwargs) -> Any:
        """创建组件（优先使用注册表）
        
        Args:
            component_type: 组件类型
            default_factory: 默认工厂函数
            *args, **kwargs: 传递给工厂函数的参数
            
        Returns:
            组件实例
        """
        if component_type in self._registry:
            component_class = self._registry[component_type]
            logger.info(f"使用注册组件: {component_type} -> {component_class.__name__}")
            return component_class(*args, **kwargs)
        
        return default_factory(*args, **kwargs)
    
    def create_data_manager(self) -> IDataManager:
        """创建数据管理器"""
        return self._create_component(
            'data_manager',
            lambda: DataManager(self.cfg),
        )
    
    def create_universe_filter(self, data_manager: IDataManager) -> IUniverseFilter:
        """创建股票池过滤器"""
        return self._create_component(
            'universe_filter',
            lambda dm, cfg: UniverseFilter(dm, cfg),
            data_manager,
            self.cfg.universe,
        )
    
    def create_factor_pipeline(self, data_manager: IDataManager) -> IFactorPipeline:
        """创建因子处理管道"""
        return self._create_component(
            'factor_pipeline',
            lambda dm, cfg: FactorPipeline(dm, cfg),
            data_manager,
            self.cfg.factor,
        )
    
    def create_factor_combiner(self) -> IFactorCombiner:
        """创建因子合成器"""
        return self._create_component(
            'factor_combiner',
            lambda: FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights),
        )
    
    def create_optimizer(self) -> IOptimizer:
        """创建组合优化器"""
        return self._create_component(
            'optimizer',
            lambda: build_optimizer(self.cfg.optimizer),
        )
    
    def create_trigger(self, trade_dates) -> IRebalanceTrigger:
        """创建再平衡触发器"""
        return self._create_component(
            'trigger',
            lambda cfg, dates: build_trigger(cfg, dates),
            self.cfg.rebalance,
            trade_dates,
        )
    
    def create_executor(self) -> IExecutionSimulator:
        """创建执行模拟器"""
        return self._create_component(
            'executor',
            lambda: ExecutionSimulator(self.cfg.cost),
        )
    
    def create_tracker(self, n_stocks: int) -> IPositionTracker:
        """创建持仓跟踪器"""
        return self._create_component(
            'tracker',
            lambda n, capital: PositionTracker(n, capital),
            n_stocks,
            self.cfg.initial_capital,
        )
    
    def create_pending_queue(self) -> Optional[IPendingOrderQueue]:
        """创建待执行订单队列"""
        if not self.cfg.enable_pending_orders:
            return None
        
        return self._create_component(
            'pending_queue',
            lambda buy_days, sell_days: PendingOrderQueue(
                max_pending_days_buy=buy_days,
                max_pending_days_sell=sell_days,
            ),
            self.cfg.max_pending_days_buy,
            self.cfg.max_pending_days_sell,
        )
    
    def create_all(self) -> dict[str, Any]:
        """创建所有组件
        
        Returns:
            组件字典，可直接传递给BacktestEngineV2
        """
        logger.info("开始创建所有组件...")
        
        # 1. 数据管理器（其他组件依赖它）
        dm = self.create_data_manager()
        
        # 2. 其他组件
        components = {
            'data_manager': dm,
            'universe_filter': self.create_universe_filter(dm),
            'factor_pipeline': self.create_factor_pipeline(dm),
            'factor_combiner': self.create_factor_combiner(),
            'optimizer': self.create_optimizer(),
            'trigger': self.create_trigger(dm.trade_dates),
            'executor': self.create_executor(),
            'tracker': self.create_tracker(dm.n_stocks),
            'pending_queue': self.create_pending_queue(),
        }
        
        logger.info("所有组件创建完成")
        return components
    
    def create_engine_kwargs(self) -> dict[str, Any]:
        """创建引擎关键字参数
        
        Returns:
            可直接解包为BacktestEngineV2参数的字典
        """
        components = self.create_all()
        return {
            'data_manager': components['data_manager'],
            'universe_filter': components['universe_filter'],
            'factor_pipeline': components['factor_pipeline'],
            'factor_combiner': components['factor_combiner'],
            'optimizer': components['optimizer'],
            'trigger': components['trigger'],
            'executor': components['executor'],
            'tracker': components['tracker'],
            'pending_queue': components['pending_queue'],
        }


# =============================================================================
# 便捷函数
# =============================================================================

def create_default_engine(config: BacktestConfig) -> 'BacktestEngineV2':
    """创建默认配置的引擎
    
    Args:
        config: 回测配置
        
    Returns:
        配置好的BacktestEngineV2实例
    """
    from core.engine_v2 import BacktestEngineV2
    
    factory = ComponentFactory(config)
    kwargs = factory.create_engine_kwargs()
    
    engine = BacktestEngineV2(config, **kwargs)
    return engine


def create_engine_with_custom(
    config: BacktestConfig,
    **custom_components
) -> 'BacktestEngineV2':
    """创建带自定义组件的引擎
    
    Args:
        config: 回测配置
        **custom_components: 自定义组件（如 data_manager=MyDataManager()）
        
    Returns:
        配置好的BacktestEngineV2实例
        
    Example:
        engine = create_engine_with_custom(
            config,
            data_manager=APIDataManager(config),
            optimizer=MyOptimizer(config.optimizer),
        )
    """
    from core.engine_v2 import BacktestEngineV2
    
    factory = ComponentFactory(config)
    kwargs = factory.create_engine_kwargs()
    
    # 用自定义组件覆盖默认组件
    kwargs.update(custom_components)
    
    engine = BacktestEngineV2(config, **kwargs)
    return engine
