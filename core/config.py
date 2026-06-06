"""全局配置管理系统 - 基于Backtest_Opus_2.0架构设计

提供完整的回测配置管理，包括交易成本、股票池过滤、因子处理、
组合优化、再平衡触发等各个子系统的配置参数。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExecutionPriceType(str, Enum):
    """执行价格类型"""
    OPEN = "open"           # 开盘价
    VWAP = "vwap"           # 成交量加权平均价
    CLOSE = "close"         # 收盘价（仅用于对比测试，不推荐实盘）
    CUSTOM = "custom"       # 自定义价格（通过回调函数指定）


class AdjustmentType(str, Enum):
    """价格复权类型"""
    FORWARD = "forward"     # 前复权（以当前为基准，历史价格调整）
    BACKWARD = "backward"   # 后复权（以历史为基准，当前价格调整）
    NONE = "none"           # 不复权（使用原始价格）


class DistillationSource(str, Enum):
    """蒸馏数据来源类型"""
    MANUAL = "manual"      # 人工编写，无数据依赖
    TRAINED = "trained"    # 从训练期数据学习
    HYBRID = "hybrid"      # 人工+数据混合


class LearningMode(str, Enum):
    """Agent学习模式"""
    ONLINE = "online"      # 全程在线学习（仅训练期可用）
    FROZEN = "frozen"      # 冻结，不学习
    RESET = "reset"        # 每期重置（walk-forward）


@dataclass
class AgentDistillationConfig:
    """Agent蒸馏配置
    
    用于声明Agent心智设定的数据来源和学习模式，
    防止蒸馏产物在回测中出现数据窥探。
    """
    source: DistillationSource = DistillationSource.MANUAL
    learning_mode: LearningMode = LearningMode.FROZEN
    train_period: tuple[str, str] | None = None  # (start, end)
    validation_period: tuple[str, str] | None = None
    test_period: tuple[str, str] | None = None
    is_test_period: bool = False
    frozen_in_test: bool = True
    data_source_declared: str = ""  # 人工声明的数据来源说明
    
    def validate(self) -> list[str]:
        """验证配置合法性"""
        errors = []
        
        if self.source == DistillationSource.TRAINED and self.train_period is None:
            errors.append("TRAINED来源必须指定train_period")
        
        if self.is_test_period and self.learning_mode == LearningMode.ONLINE:
            errors.append("测试期禁止使用ONLINE学习模式")
        
        if self.source == DistillationSource.MANUAL and self.train_period is not None:
            errors.append("MANUAL来源不应指定train_period")
        
        return errors
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'source': self.source.value,
            'learning_mode': self.learning_mode.value,
            'train_period': self.train_period,
            'validation_period': self.validation_period,
            'test_period': self.test_period,
            'is_test_period': self.is_test_period,
            'frozen_in_test': self.frozen_in_test,
            'data_source_declared': self.data_source_declared,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentDistillationConfig':
        """从字典创建"""
        return cls(
            source=DistillationSource(data.get('source', 'manual')),
            learning_mode=LearningMode(data.get('learning_mode', 'frozen')),
            train_period=tuple(data['train_period']) if data.get('train_period') else None,
            validation_period=tuple(data['validation_period']) if data.get('validation_period') else None,
            test_period=tuple(data['test_period']) if data.get('test_period') else None,
            is_test_period=data.get('is_test_period', False),
            frozen_in_test=data.get('frozen_in_test', True),
            data_source_declared=data.get('data_source_declared', ''),
        )



logger = logging.getLogger(__name__)


# ============================================================================
# 资产类型 (Phase P1.1)
# ============================================================================


class AssetType(str, Enum):
    """资产类型枚举

    使用 str, Enum 混合继承，同时支持:
        - 枚举成员: AssetType.STOCK
        - 字符串比较: AssetType.STOCK == "stock"
    """
    STOCK = "stock"
    FUTURE = "future"
    OPTION = "option"


@dataclass
class AssetCost:
    """按资产类型的成本配置

    Attributes:
        stamp_tax_rate: 印花税率 (股票 0.001, 期货 0)
        exchange_fee: 交易所手续费 (期货专用)
        commission_rate: 覆盖通用佣金率 (None=使用通用)
    """
    stamp_tax_rate: float = 0.0
    exchange_fee: float = 0.0
    commission_rate: float | None = None


@dataclass
class AssetInfo:
    """资产基本信息 (P3.2)

    用于统一描述不同资产类型的元数据。

    Attributes:
        asset_type: 资产类型 (STOCK/FUTURE/OPTION)
        multiplier: 合约乘数 (股票=1, 期货=合约乘数)
        margin_ratio: 保证金比例 (股票=None, 期货>0)
        tick_size: 最小变动价位
        expiry_date: 到期日 (期货/期权, 股票=None)
        exchange: 交易所代码
    """

    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    margin_ratio: float | None = None
    tick_size: float = 0.01
    expiry_date: str | None = None
    exchange: str | None = None


# ============================================================================
# 配置类
# ============================================================================


@dataclass
class CostConfig:
    """交易成本模型配置
    
    Attributes:
        commission_rate: 佣金率（万三）
        commission_min: 最低佣金
        stamp_tax_rate: 印花税率（卖出单边，股票默认 0.1%）
        slippage_pct: 滑点（单边）
        asset_costs: 按资产类型区分的成本配置（可选覆盖）
    """
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage_pct: float = 0.001
    asset_costs: dict = field(default_factory=dict)

    def get_asset_cost(self, asset_type: AssetType) -> AssetCost:
        """获取指定资产类型的成本配置

        如果未配置则返回默认值（印花税=通用配置，交易所费=0）。
        """
        if asset_type in self.asset_costs:
            return self.asset_costs[asset_type]
        return AssetCost(stamp_tax_rate=self.stamp_tax_rate)


@dataclass
class UniverseConfig:
    """股票池过滤配置
    
    支持多种市场约束的股票过滤：
    - 停牌股票过滤
    - 涨跌停股票过滤
    - ST股票特殊处理
    - 下一交易日可交易性检查
    """
    exclude_suspended: bool = True          # 排除停牌
    exclude_limit_up: bool = True           # 排除涨停（无法买入）
    exclude_limit_down: bool = True         # 排除跌停（无法卖出）
    exclude_stock_prefixes: list[str] = field(default_factory=list)  # 排除特定前缀的股票
    excluded_prefixes: list[str] = field(default_factory=list)  # 需要排除的前缀列表
    exclude_st: bool = True                 # 排除ST股票
    exclude_na_factors: bool = True         # 排除因子值缺失的股票
    na_factor_names: list[str] = field(default_factory=list)  # 需要检查缺失值的因子名称列表
    na_threshold: float = 0.3               # 缺失值比例阈值
    exclude_by_market_cap: bool = False     # 是否按市值过滤
    min_market_cap: float = 1e9             # 最小市值（元）
    max_market_cap: float = 5e11           # 最大市值（元）
    exclude_industries: bool = False        # 是否按行业过滤
    excluded_industries: list[str] = field(default_factory=list)  # 需要排除的行业列表
    enable_custom_filters: bool = False     # 是否启用自定义过滤
    custom_filter_configs: dict = field(default_factory=dict)  # 自定义过滤配置
    check_next_day_tradable: bool = True    # 检查下一日可交易性
    limit_up_threshold: float = 0.095       # 涨停判定阈值（普通股票）
    limit_down_threshold: float = -0.095    # 跌停判定阈值（普通股票）
    st_limit_up_threshold: float = 0.048    # ST股票涨停阈值
    st_limit_down_threshold: float = -0.048 # ST股票跌停阈值


@dataclass
class FactorConfig:
    """因子处理管道配置
    
    完整的因子预处理流程：
    - 去极值处理（MAD、百分位、标准差）
    - 缺失值填充（中位数、均值、零值）
    - 行业市值中性化
    - 标准化处理（Z-score、排序、最小最大）
    """
    winsorize_method: str = "mad"           # 去极值方法: 'mad' | 'percentile' | 'sigma' | 'none' (跳过)
    winsorize_n: float = 5.0               # MAD倍数或sigma倍数
    winsorize_pct: tuple[float, float] = (0.01, 0.99)  # 百分位去极值范围
    reverse_factor: bool = False            # 是否反转因子值（负向因子设为True）
    neutralize: bool = False               # 是否进行行业市值中性化
    neutralize_industry: bool = True        # 行业中性化
    neutralize_mktcap: bool = True         # 市值中性化
    standardize_method: str = "zscore"      # 标准化方法: 'zscore' | 'rank' | 'minmax' | 'none' (跳过)
    fill_method: str = "median"            # 缺失值填充: 'median' | 'mean' | 'zero' | 'none' (跳过)
    
    # 因子合成配置
    factor_weights: dict[str, float] = field(default_factory=dict)  # 因子权重
    combine_method: str = "weighted_sum"    # 合成方法: 'weighted_sum' | 'rank_weighted'


@dataclass
class OptimizerConfig:
    """组合优化器配置
    
    支持多种优化策略：
    - 等权重分配
    - 最小方差优化
    - 均值方差优化（马科维茨）
    - 风险平价优化
    """
    method: str = "equal_weight"            # 优化方法
    max_weight: float = 0.10               # 个股最大权重
    min_weight: float = 0.0                 # 个股最小权重
    industry_max_weight: float | None = None  # 行业最大权重
    round_lot: bool = True                 # 整手数优化（100股）
    target_count: int = 50                 # 目标持股数
    select_top: bool = True                # True=选因子分数最高, False=选最低
    
    # 均值方差优化参数
    risk_aversion: float = 1.0             # 风险厌恶系数
    
    # 风险平价参数
    risk_parity_tol: float = 1e-6          # 风险平价收敛容差
    risk_parity_max_iter: int = 500        # 风险平价最大迭代次数
    
    # 协方差估计参数
    cov_method: str = "ledoit_wolf"        # 协方差估计方法
    cov_lookback: int = 60                 # 协方差估计回看期
    cov_shrinkage: float = 0.1             # 压缩估计参数（如果适用）


@dataclass
class RebalanceConfig:
    """再平衡触发配置
    
    支持多种触发方式：
    - 固定间隔（每日、每周、每月、N天）
    - 条件触发（信号变化、回撤触发）
    - 混合模式（固定间隔+条件触发）
    """
    method: str = "fixed"                   # 触发方法: 'fixed' | 'conditional' | 'hybrid'
    
    # 固定间隔参数
    frequency: str = "monthly"             # 频率: 'daily' | 'weekly' | 'monthly' | 'N_days'
    n_days: int = 20                       # N_days模式下的天数
    
    # 条件触发参数
    signal_change_threshold: float = 0.3   # 信号变化超过此比例触发
    drawdown_trigger: float | None = None  # 回撤超过此值触发
    volatility_trigger: float | None = None # 波动率超过此值触发
    
    # 混合模式参数
    hybrid_min_days: int = 5               # 混合模式最小间隔天数
    hybrid_max_days: int = 30              # 混合模式最大间隔天数


@dataclass
class BacktestConfig:
    """回测系统总配置
    
    整合所有子系统的配置参数，提供统一的配置接口。
    """
    # 数据路径配置
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    
    # 数据文件配置（pkl格式）
    close_file: str = "close.pkl"
    open_file: str = "open.pkl"
    high_file: str = "high.pkl"
    low_file: str = "low.pkl"
    adj_factor_file: str = "stock_adj.pkl"              # 复权因子
    adjustment_type: str = "forward"                    # 复权类型: 'forward'=前复权, 'backward'=后复权, 'none'=不复权
    suspend_file: str = "suspend.pkl"        # 停牌状态: 1=停牌, 0=正常
    industry_file: str = "industry.pkl"      # 行业分类
    st_file: str = "st.pkl"                  # ST标记: 1=ST, 0=正常
    mktcap_file: str | None = None           # 市值数据（可选，用于中性化）
    
    # 因子文件配置
    factor_files: list[str] = field(default_factory=list)
    factor_weights: dict[str, float] = field(default_factory=dict)  # 空=等权
    
    # 子系统配置
    cost: CostConfig = field(default_factory=CostConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    factor: FactorConfig = field(default_factory=FactorConfig)
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    rebalance: RebalanceConfig = field(default_factory=RebalanceConfig)
    
    # 待执行订单管理配置
    enable_pending_orders: bool = True        # 启用待执行订单队列
    max_pending_days_buy: int = 5             # 买入待执行最大天数
    max_pending_days_sell: int = 10           # 卖出待执行最大天数（更宽松）
    enable_fallback: bool = True              # 启用备选替补股票
    max_fallback_depth: int = 10             # 备选替补搜索深度
    fallback_weight_factor: float = 1.2      # 替补股票权重放大因子
    
    # 执行价格配置
    execution_price_type: ExecutionPriceType = ExecutionPriceType.OPEN  # 默认开盘价
    execution_price_custom_callback: Any = None  # 自定义价格回调函数 (date, stock, side) -> float
    
    # 回测基本参数
    initial_capital: float = 10_000_000.0   # 初始资金
    start_date: str | None = None            # 回测起始日 'YYYY-MM-DD'
    end_date: str | None = None              # 回测结束日
    benchmark: str | None = None             # 基准指数（暂留接口）
    
    # 性能优化配置
    enable_parallel: bool = True             # 启用并行计算
    max_workers: int = 4                     # 最大工作线程数
    enable_cache: bool = True                # 启用数据缓存
    cache_size_mb: int = 1000                # 缓存大小限制（MB）
    
    # 日志和调试配置
    log_level: str = "INFO"                  # 日志级别
    save_intermediate: bool = False           # 保存中间结果
    debug_mode: bool = False                 # 调试模式
    
    def validate(self) -> list[str]:
        """验证配置参数的有效性"""
        errors = []
        
        # 验证数据目录
        if not self.data_dir.exists():
            errors.append(f"数据目录不存在: {self.data_dir}")
        
        # 验证因子文件
        if not self.factor_files:
            errors.append("至少需要指定一个因子文件")
        
        # 验证权重配置
        if self.factor_weights:
            total_weight = sum(self.factor_weights.values())
            if abs(total_weight - 1.0) > 1e-6:
                errors.append(f"因子权重总和应为1.0，当前为{total_weight}")
        
        # 验证优化器配置
        if self.optimizer.max_weight <= 0 or self.optimizer.max_weight > 1:
            errors.append("最大权重应在(0,1]范围内")
        
        if self.optimizer.target_count <= 0:
            errors.append("目标持股数应大于0")
        
        # 验证再平衡配置
        if self.rebalance.frequency not in ["daily", "weekly", "monthly", "N_days"]:
            errors.append("再平衡频率应为: daily, weekly, monthly, N_days")
        
        return errors
    
    @classmethod
    def create_default(cls) -> BacktestConfig:
        """创建默认配置"""
        return cls()
    
    @classmethod
    def create_from_dict(cls, config_dict: dict[str, Any]) -> BacktestConfig:
        """从字典创建配置"""
        # 递归处理嵌套配置
        def update_config(obj: Any, data: dict[str, Any]):
            for key, value in data.items():
                if hasattr(obj, key):
                    attr = getattr(obj, key)
                    if hasattr(attr, '__dataclass_fields__'):
                        if isinstance(value, dict):
                            update_config(attr, value)
                        else:
                            setattr(obj, key, value)
                    else:
                        setattr(obj, key, value)
        
        config = cls()
        update_config(config, config_dict)
        return config


# ============================================================================
# 保证金配置 (Phase 2: 期货/杠杆交易)
# ============================================================================


@dataclass
class MarginConfig:
    """保证金配置

    用于期货等杠杆交易品种的保证金管理。

    Attributes:
        initial_margin_ratio: 初始保证金比例 (默认 10%)
        maintenance_margin_ratio: 维持保证金比例 (默认 8%)
        force_liquidation_ratio: 强平线比例 (默认 5%, 低于此比例强制平仓)
    """
    initial_margin_ratio: float = 0.10
    maintenance_margin_ratio: float = 0.08
    force_liquidation_ratio: float = 0.05

    def calculate_initial_margin(self, notional_value: float) -> float:
        """计算初始保证金"""
        return notional_value * self.initial_margin_ratio

    def calculate_maintenance_margin(self, notional_value: float) -> float:
        """计算维持保证金"""
        return notional_value * self.maintenance_margin_ratio

    def validate(self) -> list[str]:
        """验证配置合法性"""
        errors = []
        if not 0 < self.initial_margin_ratio <= 1:
            errors.append("初始保证金比例应在 (0, 1] 范围内")
        if not 0 < self.maintenance_margin_ratio <= self.initial_margin_ratio:
            errors.append("维持保证金比例应在 (0, initial_margin_ratio] 范围内")
        if not 0 < self.force_liquidation_ratio <= self.maintenance_margin_ratio:
            errors.append("强平线比例应在 (0, maintenance_margin_ratio] 范围内")
        return errors

    def to_dict(self) -> dict:
        return {
            'initial_margin_ratio': self.initial_margin_ratio,
            'maintenance_margin_ratio': self.maintenance_margin_ratio,
            'force_liquidation_ratio': self.force_liquidation_ratio,
        }
