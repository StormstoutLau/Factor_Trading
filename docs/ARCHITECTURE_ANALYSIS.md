# 回测引擎架构分析报告

## 1. 当前架构概述

### 1.1 核心组件

```
BacktestEngine (核心引擎)
├── DataManager (数据管理)
├── UniverseFilter (股票池过滤)
├── FactorPipeline (因子处理管道)
├── FactorCombiner (因子合成器)
├── BaseOptimizer (组合优化器)
├── BaseTrigger (再平衡触发器)
├── ExecutionSimulator (交易执行模拟)
├── PositionTracker (持仓跟踪)
├── PendingOrderQueue (待执行订单队列)
└── PerformanceAnalyzer (绩效分析)
```

### 1.2 配置体系

```
BacktestConfig (总配置)
├── CostConfig (交易成本)
├── UniverseConfig (股票池过滤)
├── FactorConfig (因子处理)
├── OptimizerConfig (组合优化)
├── RebalanceConfig (再平衡触发)
└── AgentDistillationConfig (Agent蒸馏)
```

---

## 2. 耦合度分析

### 2.1 耦合度矩阵

| 模块 | 引擎直接依赖 | 间接依赖 | 耦合度 | 插拔难度 |
|------|------------|---------|-------|---------|
| **DataManager** | ✓ 直接实例化 | 所有模块 | 🔴 高 | 难 |
| **UniverseFilter** | ✓ 直接实例化 | 优化器、执行器 | 🟡 中 | 中 |
| **FactorPipeline** | ✓ 直接实例化 | 优化器 | 🟡 中 | 中 |
| **FactorCombiner** | ✓ 直接实例化 | 优化器 | 🟡 中 | 中 |
| **BaseOptimizer** | ✓ 工厂方法 | 无 | 🟢 低 | 易 |
| **BaseTrigger** | ✓ 工厂方法 | 无 | 🟢 低 | 易 |
| **ExecutionSimulator** | ✓ 直接实例化 | 无 | 🟢 低 | 易 |
| **PositionTracker** | ✓ 直接实例化 | 无 | 🟢 低 | 易 |
| **PendingOrderQueue** | ✓ 条件实例化 | 无 | 🟢 低 | 易 |
| **PerformanceAnalyzer** | ✗ 间接调用 | 无 | 🟢 低 | 易 |

### 2.2 关键耦合点

#### 🔴 高耦合 - DataManager

```python
# engine.py 第74行
self.dm = DataManager(self.cfg)

# 依赖链:
# 1. 所有价格数据: self.dm.get_adj_price('open', self.cfg.adjustment_type)
# 2. 日期序列: self.dm.trade_dates
# 3. 收益率矩阵: self.dm.returns.values
# 4. 股票代码: self.dm.stock_codes
# 5. 数据信息: self.dm.get_data_info()
```

**问题**: DataManager是核心数据枢纽，所有模块都通过它获取数据。如果替换为其他数据源（如实时数据接口），需要修改所有模块。

#### 🟡 中耦合 - UniverseFilter

```python
# engine.py 第78行
self.universe = UniverseFilter(self.dm, self.cfg.universe)

# 依赖点:
# 1. 可交易掩码: self.universe.buyable.loc[date]
# 2. 可卖出掩码: self.universe.sellable.loc[date]
# 3. 综合掩码: self.universe.tradable.loc[date]
```

**问题**: UniverseFilter依赖DataManager的数据格式，且引擎直接访问其内部DataFrame结构。

#### 🟡 中耦合 - FactorPipeline + FactorCombiner

```python
# engine.py 第83-84行
self.pipeline = FactorPipeline(self.dm, self.cfg.factor)
self.combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)

# 依赖点:
# 1. 复合信号: self._composite_signal.iloc[date_index]
# 2. 因子列名: self._composite_signal.columns
```

**问题**: 因子处理管道和合成器紧密耦合，且引擎直接操作内部信号DataFrame。

---

## 3. 插拔式架构评估

### 3.1 已实现插拔式设计的模块 ✅

#### 组合优化器 (BaseOptimizer)

```python
# portfolio.py
class BaseOptimizer(ABC):
    @abstractmethod
    def optimize(self, signals: pd.Series, returns_data: pd.DataFrame | None = None) -> pd.Series:
        ...

# 工厂方法
def build_optimizer(config: OptimizerConfig):
    optimizer_map = {
        'equal_weight': EqualWeightOptimizer,
        'min_variance': MinVarianceOptimizer,
        'mean_variance': MeanVarianceOptimizer,
        'risk_parity': RiskParityOptimizer,
    }
    return optimizer_class(config)
```

**插拔方式**: 通过配置`method`参数切换，已实现完美插拔。

#### 再平衡触发器 (BaseTrigger)

```python
# rebalance.py
class BaseTrigger(ABC):
    @abstractmethod
    def should_trigger(self, date: pd.Timestamp, **kwargs) -> bool:
        ...

# 工厂方法
def build_trigger(config: RebalanceConfig, trade_dates: pd.DatetimeIndex):
    trigger_map = {
        'fixed': FixedIntervalTrigger,
        'conditional': ConditionalTrigger,
        'hybrid': HybridTrigger,
    }
```

**插拔方式**: 通过配置`method`参数切换，已实现完美插拔。

#### 风险监控器 (BaseRiskMonitor)

```python
# risk_monitor.py
class BaseRiskMonitor(ABC):
    @abstractmethod
    def monitor(self, symbol: str, **kwargs) -> RiskSignal:
        ...

# CompositeRiskEngine支持自定义监控器列表
class CompositeRiskEngine:
    def __init__(self, monitors: Optional[list[BaseRiskMonitor]] = None):
        self.monitors = monitors or [FundamentalMonitor(), ...]
```

**插拔方式**: 通过传入自定义监控器列表实现插拔。

### 3.2 未实现插拔式设计的模块 ❌

#### DataManager

**当前问题**:
- 引擎直接实例化: `self.dm = DataManager(self.cfg)`
- 所有模块通过`self.dm`访问数据
- 数据格式（DataFrame结构）硬编码

#### 因子处理管道

**当前问题**:
- 引擎直接实例化: `self.pipeline = FactorPipeline(self.dm, self.cfg.factor)`
- 预计算因子: `self._precompute_factors()` 方法硬编码
- 复合信号直接存储为DataFrame

#### 持仓跟踪器

**当前问题**:
- 引擎直接实例化: `self.tracker = PositionTracker(...)`
- 虽然耦合度低，但缺乏接口抽象

---

## 4. 解耦方案

### 4.1 方案A: 依赖注入 (推荐)

将核心组件的创建从引擎中分离，通过构造函数注入：

```python
class BacktestEngine:
    def __init__(
        self,
        config: BacktestConfig,
        data_manager: IDataManager,  # 接口抽象
        universe_filter: IUniverseFilter,  # 接口抽象
        factor_pipeline: IFactorPipeline,  # 接口抽象
        optimizer: BaseOptimizer,  # 已有抽象
        trigger: BaseTrigger,  # 已有抽象
        executor: IExecutionSimulator,  # 接口抽象
        tracker: IPositionTracker,  # 接口抽象
    ):
        ...
```

**优点**:
- 完全解耦，各模块可独立测试
- 支持Mock测试
- 易于替换实现

**缺点**:
- 构造函数参数较多
- 需要定义更多接口

### 4.2 方案B: 工厂模式 + 配置驱动

通过配置工厂创建组件：

```python
class ComponentFactory:
    @staticmethod
    def create_data_manager(config: BacktestConfig) -> IDataManager:
        if config.data_source == 'local':
            return DataManager(config)
        elif config.data_source == 'api':
            return APIDataManager(config)
        ...
    
    @staticmethod
    def create_factor_pipeline(config: BacktestConfig) -> IFactorPipeline:
        if config.factor.engine == 'default':
            return FactorPipeline(config)
        elif config.factor.engine == 'custom':
            return CustomFactorPipeline(config)
        ...
```

**优点**:
- 集中管理组件创建
- 配置驱动，无需修改引擎代码

**缺点**:
- 工厂类可能变得庞大
- 新增组件需要修改工厂

### 4.3 方案C: 事件驱动架构

将引擎改为事件总线模式：

```python
class EventBus:
    def subscribe(self, event_type: str, handler: Callable):
        ...
    def publish(self, event_type: str, data: Any):
        ...

class BacktestEngine:
    def __init__(self, config: BacktestConfig, event_bus: EventBus):
        self.bus = event_bus
        self.bus.subscribe('data.ready', self._on_data_ready)
        self.bus.subscribe('rebalance.trigger', self._on_rebalance)
        ...
```

**优点**:
- 极致解耦，模块间无直接依赖
- 支持异步处理
- 易于扩展

**缺点**:
- 架构复杂度高
- 调试困难
- 性能开销

---

## 5. 推荐实施方案

### 5.1 第一阶段: 接口抽象 (低风险)

为当前硬编码的模块定义接口：

```python
# interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol

class IDataManager(Protocol):
    """数据管理器接口"""
    @property
    def trade_dates(self) -> pd.DatetimeIndex: ...
    @property
    def stock_codes(self) -> list[str]: ...
    def get_adj_price(self, price_type: str, adjustment: str) -> pd.DataFrame: ...
    def load_factor(self, name: str) -> pd.DataFrame: ...

class IUniverseFilter(Protocol):
    """股票池过滤器接口"""
    def build_masks(self) -> None: ...
    @property
    def buyable(self) -> pd.DataFrame: ...
    @property
    def sellable(self) -> pd.DataFrame: ...
    @property
    def tradable(self) -> pd.DataFrame: ...

class IFactorPipeline(Protocol):
    """因子处理管道接口"""
    def process(self, raw_factor: pd.DataFrame) -> pd.DataFrame: ...

class IExecutionSimulator(Protocol):
    """执行模拟器接口"""
    def execute_order(self, stock: str, side: OrderSide, quantity: int, 
                      date: pd.Timestamp, price: float) -> tuple[bool, Trade | None]: ...
```

### 5.2 第二阶段: 依赖注入 (中风险)

修改引擎构造函数，支持注入：

```python
class BacktestEngine:
    def __init__(
        self,
        config: BacktestConfig,
        data_manager: IDataManager | None = None,
        universe_filter: IUniverseFilter | None = None,
        factor_pipeline: IFactorPipeline | None = None,
        optimizer: BaseOptimizer | None = None,
        trigger: BaseTrigger | None = None,
        executor: IExecutionSimulator | None = None,
        tracker: IPositionTracker | None = None,
    ):
        self.cfg = config
        
        # 使用注入的组件或创建默认实例
        self.dm = data_manager or DataManager(config)
        self.universe = universe_filter or UniverseFilter(self.dm, config.universe)
        self.pipeline = factor_pipeline or FactorPipeline(self.dm, config.factor)
        self.optimizer = optimizer or build_optimizer(config.optimizer)
        self.trigger = trigger or build_trigger(config.rebalance, self.dm.trade_dates)
        self.executor = executor or ExecutionSimulator(config.cost)
        self.tracker = tracker or PositionTracker(self.dm.n_stocks, config.initial_capital)
        ...
```

### 5.3 第三阶段: 插件系统 (高风险)

实现完整的插件注册机制：

```python
class PluginRegistry:
    _plugins: dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, plugin_class: type):
        cls._plugins[name] = plugin_class
    
    @classmethod
    def create(cls, name: str, config: BacktestConfig, **kwargs):
        plugin_class = cls._plugins.get(name)
        if not plugin_class:
            raise ValueError(f"Unknown plugin: {name}")
        return plugin_class(config, **kwargs)

# 注册插件
PluginRegistry.register('data.local', DataManager)
PluginRegistry.register('data.api', APIDataManager)
PluginRegistry.register('factor.default', FactorPipeline)
PluginRegistry.register('factor.custom', CustomFactorPipeline)
```

---

## 6. 当前已实现插拔的模块总结

| 模块 | 插拔方式 | 实现状态 |
|------|---------|---------|
| 组合优化器 | 配置`method`参数 | ✅ 已完成 |
| 再平衡触发器 | 配置`method`参数 | ✅ 已完成 |
| 风险监控器 | 传入监控器列表 | ✅ 已完成 |
| 执行价格类型 | 配置`execution_price_type` | ✅ 已完成 |
| Agent学习模式 | 配置`learning_mode` | ✅ 已完成 |
| 归因连接方法 | 配置`linking_method` | ✅ 已完成 |
| Walk-Forward方法 | 配置`method`参数 | ✅ 已完成 |

---

## 7. 建议优先级

1. **P0 (立即)**: 为DataManager定义接口，这是最大的耦合点
2. **P1 (短期)**: 为UniverseFilter和FactorPipeline定义接口
3. **P2 (中期)**: 实现依赖注入，修改引擎构造函数
4. **P3 (长期)**: 实现完整插件系统

---

## 8. 结论

当前架构已经实现了部分插拔式设计（优化器、触发器、风险监控器等），但核心数据层（DataManager）和因子处理层（FactorPipeline）仍存在紧耦合。

**建议采用渐进式解耦策略**：
1. 先定义接口（Protocol）
2. 再实现依赖注入
3. 最后考虑插件系统

这样既保证了向后兼容性，又逐步实现了真正的插拔式架构。
