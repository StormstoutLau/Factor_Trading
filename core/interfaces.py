"""回测引擎核心接口定义

实现插拔式架构的基础，所有核心模块通过接口解耦。
支持依赖注入、Mock测试和模块替换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

import numpy as np
import pandas as pd

from core.config import BacktestConfig, CostConfig, FactorConfig, UniverseConfig


# =============================================================================
# 数据层接口
# =============================================================================

class IDataManager(Protocol):
    """数据管理器接口
    
    抽象数据访问层，支持本地数据、API数据、模拟数据等多种实现。
    """
    
    @property
    def trade_dates(self) -> pd.DatetimeIndex:
        """交易日序列"""
        ...
    
    @property
    def stock_codes(self) -> list[str]:
        """股票代码列表"""
        ...
    
    @property
    def n_stocks(self) -> int:
        """股票数量"""
        ...
    
    @property
    def returns(self) -> pd.DataFrame:
        """收益率矩阵"""
        ...
    
    def get_adj_price(self, price_type: str, adjustment: str = "forward") -> pd.DataFrame:
        """获取复权价格

        Args:
            price_type: 价格类型 ('open' | 'high' | 'low' | 'close')
            adjustment: 复权类型 ('forward' | 'backward' | 'none')

        Returns:
            价格DataFrame (dates x stocks)
        """
        ...
    
    def load_factor(self, name: str) -> pd.DataFrame:
        """加载因子数据
        
        Args:
            name: 因子名称/文件名
            
        Returns:
            因子DataFrame (dates x stocks)
        """
        ...
    
    def get_data_info(self) -> dict[str, Any]:
        """获取数据信息摘要"""
        ...


class IUniverseFilter(Protocol):
    """股票池过滤器接口
    
    定义可交易股票集合，支持多种过滤规则。
    """
    
    def build_masks(self) -> None:
        """构建过滤掩码"""
        ...
    
    @property
    def buyable(self) -> pd.DataFrame:
        """可买入掩码 (dates x stocks)"""
        ...
    
    @property
    def sellable(self) -> pd.DataFrame:
        """可卖出掩码 (dates x stocks)"""
        ...
    
    @property
    def tradable(self) -> pd.DataFrame:
        """可交易掩码 (dates x stocks)"""
        ...
    
    def get_mask_summary(self) -> dict[str, Any]:
        """获取掩码统计信息"""
        ...


# =============================================================================
# 因子层接口
# =============================================================================

class IFactorPipeline(Protocol):
    """因子处理管道接口
    
    因子预处理流程：去极值 -> 缺失值填充 -> 中性化 -> 标准化
    """
    
    def process(self, raw_factor: pd.DataFrame) -> pd.DataFrame:
        """处理原始因子
        
        Args:
            raw_factor: 原始因子DataFrame
            
        Returns:
            处理后的因子DataFrame
        """
        ...
    
    def process_single(self, series: pd.Series) -> pd.Series:
        """处理单期因子"""
        ...


class IFactorCombiner(Protocol):
    """因子合成器接口
    
    将多个因子合成为单一信号。
    """
    
    def combine(self, factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """合成因子
        
        Args:
            factors: {因子名: 因子DataFrame}
            
        Returns:
            合成信号DataFrame
        """
        ...
    
    def combine_single(self, daily_factors: dict[str, pd.Series]) -> pd.Series:
        """合成单期因子"""
        ...


# =============================================================================
# 组合优化层接口
# =============================================================================

class IOptimizer(Protocol):
    """组合优化器接口
    
    根据因子信号生成目标权重。
    """
    
    def optimize(
        self,
        signals: pd.Series,
        returns_data: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """执行优化
        
        Args:
            signals: 因子信号 (stock -> score)
            returns_data: 历史收益数据（用于风险模型）
            
        Returns:
            目标权重 (stock -> weight)
        """
        ...


# =============================================================================
# 交易执行层接口
# =============================================================================

class IExecutionSimulator(Protocol):
    """交易执行模拟器接口
    
    模拟订单执行，包含成本计算和滑点。
    """
    
    def execute_order(
        self,
        stock: str,
        side: Any,  # OrderSide
        quantity: int,
        date: pd.Timestamp,
        price: float,
        **kwargs
    ) -> tuple[bool, Optional[Any]]:  # (success, Trade)
        """执行订单
        
        Args:
            stock: 股票代码
            side: 买卖方向
            quantity: 数量
            date: 交易日期
            price: 执行价格
            
        Returns:
            (是否成功, 交易记录)
        """
        ...
    
    def execute_pending_order(
        self,
        order: Any,  # PendingOrder
        date: pd.Timestamp,
        open_price: float,
        close_price: Optional[float] = None
    ) -> tuple[bool, Optional[Any]]:
        """执行待执行订单"""
        ...
    
    def get_execution_stats(self) -> dict[str, Any]:
        """获取执行统计"""
        ...


class IPositionTracker(Protocol):
    """持仓跟踪器接口
    
    跟踪持仓、现金、市值变化。
    """
    
    def execute_trade(self, trade: Any) -> None:
        """执行交易更新持仓"""
        ...
    
    def update_market_values(self, date: pd.Timestamp, prices: pd.Series) -> None:
        """更新持仓市值"""
        ...
    
    def get_position(self, stock: str) -> Optional[Any]:
        """获取单个持仓"""
        ...
    
    def get_all_positions(self) -> dict[str, Any]:
        """获取所有持仓"""
        ...
    
    def get_cash(self) -> float:
        """获取现金余额"""
        ...
    
    def get_total_value(self) -> float:
        """获取总资产"""
        ...
    
    def get_snapshots(self) -> list[dict]:
        """获取持仓快照"""
        ...
    
    def get_snapshots_df(self) -> pd.DataFrame:
        """获取快照DataFrame"""
        ...


# =============================================================================
# 再平衡触发层接口
# =============================================================================

class IRebalanceTrigger(Protocol):
    """再平衡触发器接口
    
    决定是否执行再平衡。
    """
    
    def should_trigger(
        self,
        date: pd.Timestamp,
        **kwargs
    ) -> bool:
        """检查是否触发再平衡
        
        Args:
            date: 当前日期
            **kwargs: 额外参数（如信号变化、组合价值等）
            
        Returns:
            是否触发
        """
        ...


# =============================================================================
# 订单管理层接口
# =============================================================================

class IPendingOrderQueue(Protocol):
    """待执行订单队列接口"""
    
    def add_order(self, order: Any) -> None:
        """添加订单"""
        ...
    
    def get_pending_orders(self) -> list[Any]:
        """获取待执行订单"""
        ...
    
    def mark_executed(self, order: Any, date: pd.Timestamp, price: float) -> None:
        """标记订单已执行"""
        ...
    
    def mark_expired(self, date: pd.Timestamp) -> None:
        """标记过期订单"""
        ...
    
    def cancel_orders(self, stock: str, date: pd.Timestamp) -> None:
        """取消股票的所有订单"""
        ...
    
    def get_order_stats(self) -> dict[str, Any]:
        """获取订单统计"""
        ...
    
    def get_event_log(self) -> pd.DataFrame:
        """获取事件日志"""
        ...


# =============================================================================
# 风险监控层接口
# =============================================================================

class IRiskMonitor(Protocol):
    """风险监控器接口"""
    
    def monitor(self, symbol: str, **kwargs) -> Any:  # RiskSignal
        """监控风险"""
        ...


class IRiskEngine(Protocol):
    """综合风控引擎接口"""
    
    def evaluate(self, **kwargs) -> tuple[Any, list[Any]]:  # (signal, actions)
        """评估风险并生成动作"""
        ...


# =============================================================================
# 归因分析层接口
# =============================================================================

class IAttributionAnalyzer(Protocol):
    """归因分析器接口"""
    
    def calculate_attribution(self) -> dict[str, Any]:
        """计算归因"""
        ...
    
    def generate_report(self) -> dict[str, Any]:
        """生成报告"""
        ...


# =============================================================================
# 报告生成层接口
# =============================================================================

class IReportGenerator(Protocol):
    """报告生成器接口"""
    
    def generate(
        self,
        snapshots: list[dict],
        trades: pd.DataFrame,
        output_dir: Any  # Path
    ) -> dict[str, Any]:
        """生成报告
        
        Args:
            snapshots: 持仓快照
            trades: 交易记录
            output_dir: 输出目录
            
        Returns:
            报告数据
        """
        ...


# =============================================================================
# 抽象基类（提供默认实现）
# =============================================================================

class AbstractDataManager(ABC):
    """数据管理器抽象基类"""
    
    def __init__(self, config: BacktestConfig):
        self.cfg = config
    
    @property
    @abstractmethod
    def trade_dates(self) -> pd.DatetimeIndex:
        ...
    
    @property
    @abstractmethod
    def stock_codes(self) -> list[str]:
        ...
    
    @abstractmethod
    def get_adj_price(self, price_type: str, adjustment: str = "forward") -> pd.DataFrame:
        """获取复权价格 (forward/backward/none)"""
        ...
    
    @abstractmethod
    def load_factor(self, name: str) -> pd.DataFrame:
        ...


class AbstractUniverseFilter(ABC):
    """股票池过滤器抽象基类"""
    
    def __init__(self, data_manager: IDataManager, config: UniverseConfig):
        self.dm = data_manager
        self.cfg = config
    
    @abstractmethod
    def build_masks(self) -> None:
        ...


class AbstractFactorPipeline(ABC):
    """因子处理管道抽象基类"""
    
    def __init__(self, data_manager: IDataManager, config: FactorConfig):
        self.dm = data_manager
        self.cfg = config
    
    @abstractmethod
    def process(self, raw_factor: pd.DataFrame) -> pd.DataFrame:
        ...


class AbstractExecutionSimulator(ABC):
    """交易执行模拟器抽象基类"""
    
    def __init__(self, config: CostConfig):
        self.cfg = config
    
    @abstractmethod
    def execute_order(
        self,
        stock: str,
        side: Any,
        quantity: int,
        date: pd.Timestamp,
        price: float,
        **kwargs
    ) -> tuple[bool, Optional[Any]]:
        ...


class AbstractPositionTracker(ABC):
    """持仓跟踪器抽象基类"""
    
    def __init__(self, n_stocks: int, initial_capital: float):
        self.n_stocks = n_stocks
        self.initial_capital = initial_capital
    
    @abstractmethod
    def execute_trade(self, trade: Any) -> None:
        ...
    
    @abstractmethod
    def get_total_value(self) -> float:
        ...
