# Factor Trading v3.0 - Code Wiki

> 基于 Backtest_Opus_2.0 架构重构的专业量化回测框架，专为 A 股市场设计。
> 版本: v3.0.0 | 代码规模: ~170KB (14 个核心模块)

---

## 目录

1. [项目整体架构](#1-项目整体架构)
2. [模块职责与依赖关系](#2-模块职责与依赖关系)
3. [核心配置系统](#3-核心配置系统)
4. [数据管理模块 (data.py)](#4-数据管理模块-datapy)
5. [股票池过滤模块 (filter/)](#5-股票池过滤模块-filter)
6. [因子处理模块 (factor.py)](#6-因子处理模块-factorpy)
7. [组合优化模块 (portfolio.py)](#7-组合优化模块-portfoliopy)
8. [交易执行模块 (execution.py)](#8-交易执行模块-executionpy)
9. [待执行订单管理 (pending.py)](#9-待执行订单管理-pendingpy)
10. [持仓跟踪模块 (tracker.py)](#10-持仓跟踪模块-trackerpy)
11. [再平衡触发模块 (rebalance.py)](#11-再平衡触发模块-rebalancepy)
12. [回测引擎 (engine.py)](#12-回测引擎-enginepy)
13. [性能分析模块 (analytics.py)](#13-性能分析模块-analyticspy)
14. [项目运行方式](#14-项目运行方式)
15. [依赖关系汇总](#15-依赖关系汇总)

---

## 1. 项目整体架构

### 1.1 架构概览

```
Factor_Trading_v3.0/
|
|-- 核心引擎层
|   ├── engine.py          # 回测引擎核心 (BacktestEngine)
|   ├── config.py          # 全局配置管理 (BacktestConfig)
|   └── data.py            # 数据管理器 (DataManager)
|
|-- 策略处理层
|   ├── factor.py          # 因子处理管道 (FactorPipeline, FactorCombiner)
|   ├── portfolio.py       # 组合优化器 (BaseOptimizer 及子类)
|   └── filter/            # 股票池过滤器 (UniverseFilter)
|       ├── __init__.py
|       ├── base.py
|       ├── universe_filter_clean.py
|       ├── extended.py
|       ├── na_factor.py
|       ├── prefix.py
|       ├── market_cap.py
|       ├── industry.py
|       └── custom.py
|
|-- 交易执行层
|   ├── execution.py       # 交易执行模拟 (ExecutionSimulator)
|   ├── pending.py         # 待执行订单队列 (PendingOrderQueue)
|   ├── tracker.py         # 持仓跟踪器 (PositionTracker)
|   └── rebalance.py       # 再平衡触发器 (BaseTrigger 及子类)
|
|-- 分析输出层
|   ├── analytics.py       # 性能分析 (PerformanceAnalyzer)
|   └── demo.py            # 演示程序与合成数据生成
|
|-- 数据与输出
|   ├── demo_data/         # 演示数据 (pkl 格式)
|   ├── demo_output/       # 回测输出 (图表、CSV、报告)
|   └── data_analysis/     # 数据分析工具
|
|-- 辅助与测试
|   ├── analysis/          # 分析脚本集合
|   ├── debug/             # 调试工具
|   ├── test/              # 测试目录
|   └── requirements.txt   # 依赖包列表
```

### 1.2 核心数据流

```
原始数据 (pkl)
    │
    ▼
┌─────────────┐
│ DataManager │  ← 懒加载 + 智能缓存
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌────────────┐  ┌───────────┐  ┌──────────────┐
│UniverseFilter│  │FactorPipeline│  │PortfolioManager│
│ 股票池过滤  │  │ 因子预处理  │  │ 组合优化      │
└──────┬─────┘  └─────┬─────┘  └──────┬───────┘
       │              │               │
       └──────────────┼───────────────┘
                      ▼
            ┌─────────────────┐
            │  BacktestEngine │  ← 核心回测循环
            │   (engine.py)   │
            └────────┬────────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Execution │  │Rebalance │  │Analytics │
│Simulator │  │Trigger   │  │Engine    │
│(execution)│  │(rebalance)│  │(analytics)│
└──────────┘  └──────────┘  └──────────┘
```

---

## 2. 模块职责与依赖关系

### 2.1 模块职责矩阵

| 模块 | 核心职责 | 关键类/函数 | 代码量 |
|------|---------|------------|--------|
| `config.py` | 全局配置管理，所有子系统的配置参数定义 | `BacktestConfig`, `CostConfig`, `UniverseConfig`, `FactorConfig`, `OptimizerConfig`, `RebalanceConfig` | ~10KB |
| `data.py` | 数据加载、缓存、预处理、复权计算 | `DataManager` | ~15KB |
| `factor.py` | 因子去极值、填充、中性化、标准化、多因子合成 | `FactorPipeline`, `FactorCombiner` | ~14KB |
| `portfolio.py` | 组合优化：等权重、最小方差、均值方差、风险平价 | `BaseOptimizer`, `EqualWeightOptimizer`, `MinVarianceOptimizer`, `MeanVarianceOptimizer`, `RiskParityOptimizer` | ~14KB |
| `execution.py` | 交易执行模拟、成本计算、交易日志 | `ExecutionSimulator`, `TradeLog`, `Trade` | ~11KB |
| `pending.py` | 待执行订单队列、失败重试、备选替补 | `PendingOrderQueue`, `PendingOrder`, `OrderStatus`, `OrderSide` | ~13KB |
| `tracker.py` | 持仓跟踪、市值更新、收益计算、快照记录 | `PositionTracker`, `Position`, `PortfolioSnapshot` | ~14KB |
| `rebalance.py` | 再平衡触发：固定间隔、条件触发、混合模式 | `BaseTrigger`, `FixedIntervalTrigger`, `ConditionalTrigger`, `HybridTrigger`, `RebalanceCalendar` | ~14KB |
| `engine.py` | 回测主循环，集成所有模块 | `BacktestEngine` | ~20KB |
| `analytics.py` | 性能指标计算、可视化图表、报告生成 | `PerformanceAnalyzer`, `generate_report` | ~18KB |
| `filter/universe_filter_clean.py` | 股票池过滤掩码构建 | `UniverseFilter`, `UniverseFilterConfig` | ~22KB |

### 2.2 模块依赖关系

```
                    ┌─────────────────┐
                    │   DataManager   │
                    │   (data.py)     │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ UniverseFilter  │ │  FactorHandler  │ │ PortfolioManager│
│(universe_filter)│ │  (factor.py)    │ │ (portfolio.py)  │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ BacktestEngine  │
                    │  (engine.py)    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ExecutionHandler │ │RebalanceHandler │ │AnalyticsEngine │
│ (execution.py)  │ │ (rebalance.py)  │ │ (analytics.py)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.3 依赖耦合度分析

| 模块 | 依赖模块 | 被依赖模块 | 耦合度 |
|------|----------|------------|--------|
| `data.py` | - | universe_filter, factor, portfolio, engine | **高** (核心) |
| `config.py` | - | 所有模块 | **高** (配置中心) |
| `universe_filter_clean.py` | data.py, config.py | engine, portfolio | 中 |
| `factor.py` | data.py, config.py | engine | 中 |
| `portfolio.py` | data.py, config.py, universe_filter | engine, rebalance | 中 |
| `engine.py` | data, config, universe_filter, factor, portfolio, execution, rebalance, analytics | - | **高** (核心) |
| `execution.py` | config | engine | 低 |
| `rebalance.py` | config, portfolio | engine | 中 |
| `analytics.py` | data, config | engine | 低 |
| `tracker.py` | data, config | - | 低 |

---

## 3. 核心配置系统

### 3.1 配置类层次

```
BacktestConfig (总配置)
├── CostConfig          # 交易成本模型
├── UniverseConfig      # 股票池过滤配置
├── FactorConfig        # 因子处理管道配置
├── OptimizerConfig     # 组合优化器配置
└── RebalanceConfig     # 再平衡触发配置
```

### 3.2 关键配置类详解

#### `CostConfig` - 交易成本模型配置

```python
@dataclass
class CostConfig:
    commission_rate: float = 0.0003      # 佣金率（万三）
    commission_min: float = 5.0          # 最低佣金
    stamp_tax_rate: float = 0.001        # 印花税率（卖出单边）
    slippage_pct: float = 0.001          # 滑点（单边）
```

#### `UniverseConfig` - 股票池过滤配置

```python
@dataclass
class UniverseConfig:
    exclude_suspended: bool = True           # 排除停牌
    exclude_limit_up: bool = True            # 排除涨停（无法买入）
    exclude_limit_down: bool = True          # 排除跌停（无法卖出）
    exclude_st: bool = True                  # 排除ST股票
    check_next_day_tradable: bool = True     # 检查下一日可交易性
    limit_up_threshold: float = 0.095        # 涨停判定阈值（普通股票）
    st_limit_up_threshold: float = 0.048     # ST股票涨停阈值
    # ... 市值过滤、行业过滤、前缀过滤等
```

#### `FactorConfig` - 因子处理管道配置

```python
@dataclass
class FactorConfig:
    winsorize_method: str = "mad"            # 去极值方法: mad | percentile | sigma | none
    winsorize_n: float = 5.0                 # MAD倍数或sigma倍数
    neutralize: bool = False                 # 是否进行行业市值中性化
    standardize_method: str = "zscore"       # 标准化方法: zscore | rank | minmax | none
    fill_method: str = "median"              # 缺失值填充: median | mean | zero | none
    combine_method: str = "weighted_sum"     # 合成方法: weighted_sum | rank_weighted
```

#### `OptimizerConfig` - 组合优化器配置

```python
@dataclass
class OptimizerConfig:
    method: str = "equal_weight"             # 优化方法: equal_weight | min_variance | mvo | risk_parity
    max_weight: float = 0.10                 # 个股最大权重
    target_count: int = 50                   # 目标持股数
    round_lot: bool = True                   # 整手数优化（100股）
    cov_method: str = "ledoit_wolf"          # 协方差估计方法: sample | ledoit_wolf | ewma
    cov_lookback: int = 60                   # 协方差估计回看期
```

#### `RebalanceConfig` - 再平衡触发配置

```python
@dataclass
class RebalanceConfig:
    method: str = "fixed"                    # 触发方法: fixed | conditional | hybrid
    frequency: str = "monthly"               # 频率: daily | weekly | monthly | N_days
    signal_change_threshold: float = 0.3     # 信号变化超过此比例触发
    drawdown_trigger: float | None = None    # 回撤超过此值触发
```

---

## 4. 数据管理模块 (data.py)

### 4.1 核心类: `DataManager`

负责所有市场数据和因子数据的加载、缓存和预处理。采用**懒加载策略**，只在需要时加载数据。

#### 关键属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `trade_dates` | `pd.DatetimeIndex` | 交易日期索引（懒加载） |
| `stock_codes` | `pd.Index` | 股票代码索引（懒加载） |
| `close` / `open` / `high` / `low` | `pd.DataFrame` | 价格数据（懒加载） |
| `adj_factor` | `pd.DataFrame` | 复权因子 |
| `suspend` | `pd.DataFrame` | 停牌状态: 1=停牌, 0=正常 |
| `industry` | `pd.DataFrame` | 行业分类 |
| `st` | `pd.DataFrame` | ST标记: 1=ST, 0=正常 |
| `mktcap` | `pd.DataFrame` | 市值数据 |
| `returns` | `pd.DataFrame` | 日收益率（自动计算） |

#### 关键方法

```python
class DataManager:
    def __init__(self, config: BacktestConfig)
    
    # 数据加载
    def _load_price_data(self, price_type: str) -> pd.DataFrame
    def _load_auxiliary_data(self) -> None
    def _load_and_align_data(self, file_path: Path) -> pd.DataFrame
    
    # 数据获取
    def get_adj_price(self, price_type: str = 'close', adjustment_type: str = 'forward') -> pd.DataFrame
    def load_factor(self, factor_file: str) -> pd.DataFrame
    
    # 缓存管理
    def clear_cache(self) -> None
    def preload_data(self) -> None
    def get_data_info(self) -> dict[str, Any]
```

#### 复权价格计算逻辑

```
前复权（默认）: adj_price = price * adj_factor
后复权: adj_price = price * adj_factor / latest_factor
```

---

## 5. 股票池过滤模块 (filter/)

### 5.1 核心类: `UniverseFilter`

构建多种过滤掩码，支持向量化操作，避免循环。

#### 掩码类型

| 掩码 | 说明 | 构建方法 |
|------|------|---------|
| `_suspend_mask` | 停牌过滤 | `_build_suspend_mask()` |
| `_limit_up_mask` | 涨停过滤（无法买入） | `_build_limit_masks()` |
| `_limit_down_mask` | 跌停过滤（无法卖出） | `_build_limit_masks()` |
| `_st_mask` | ST股票过滤 | `_build_st_mask()` |
| `_next_day_tradable_mask` | 下一交易日可交易性 | `_build_next_day_tradable_mask()` |
| `_na_factor_mask` | 因子NA过滤 | `_build_na_factor_mask()` |
| `_stock_prefix_mask` | 股票代码前缀过滤 | `_build_stock_prefix_mask()` |
| `_market_cap_mask` | 市值过滤 | `_build_market_cap_mask()` |
| `_industry_mask` | 行业过滤 | `_build_industry_mask()` |

#### 最终掩码

| 属性 | 说明 | 计算方式 |
|------|------|---------|
| `buyable` | 可买入掩码 | suspend & limit_up & st & ... & next_day_tradable |
| `sellable` | 可卖出掩码 | suspend & limit_down & st & ... |
| `tradable` | 可交易掩码 | buyable & sellable |

#### 预定义配置

```python
get_conservative_config()   # 保守配置（严格过滤）
get_aggressive_config()     # 激进配置（宽松过滤）
get_balanced_config()       # 平衡配置（适中过滤）
```

### 5.2 Filter 子模块

| 文件 | 核心类 | 功能 |
|------|--------|------|
| `base.py` | `BaseFilter`, `CompositeFilter`, `FilterChain` | 过滤器基类和组合 |
| `extended.py` | `ExtendedFilter`, `DateRangeFilter`, `TurnoverFilter` | 扩展过滤器 |
| `na_factor.py` | `NAFactorFilter`, `NAFactorDropFilter`, `NAFactorFillFilter` | NA值处理 |
| `prefix.py` | `PrefixFilter`, `BoardFilter` | 股票前缀/板块过滤 |
| `market_cap.py` | `MarketCapFilter`, `LargeCapFilter`, `SmallCapFilter` | 市值过滤 |
| `industry.py` | `IndustryFilter`, `SectorFilter` | 行业分类过滤 |
| `custom.py` | `CustomFunctionFilter`, `ExpressionFilter` | 自定义过滤 |

---

## 6. 因子处理模块 (factor.py)

### 6.1 核心类: `FactorPipeline`

负责单个因子的预处理流程，支持完整的因子清洗管道。

#### 处理流程

```
原始因子
    │
    ├──→ [可选] 因子反转 (reverse_factor)
    │
    ├──→ [可选] 去极值处理 (winsorize_method)
    │       ├── mad: MAD去极值 + tanh软截断
    │       ├── percentile: 百分位去极值
    │       └── sigma: 标准差去极值
    │
    ├──→ [可选] 缺失值填充 (fill_method)
    │       ├── median: 中位数填充
    │       ├── mean: 均值填充
    │       └── zero: 零值填充
    │
    ├──→ [可选] 中性化处理 (neutralize)
    │       ├── 行业中性化 (回归残差)
    │       └── 市值中性化 (对数市值回归)
    │
    └──→ [可选] 标准化处理 (standardize_method)
            ├── zscore: Z-score标准化
            ├── rank: 排序标准化
            └── minmax: 最小最大标准化
```

#### 关键方法

```python
class FactorPipeline:
    def process(self, raw_factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame
    def _winsorize_mad(self, factor: pd.DataFrame) -> pd.DataFrame
    def _winsorize_percentile(self, factor: pd.DataFrame) -> pd.DataFrame
    def _winsorize_sigma(self, factor: pd.DataFrame) -> pd.DataFrame
    def _neutralize(self, factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame
    def _standardize(self, factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame
```

### 6.2 核心类: `FactorCombiner`

负责将多个处理后的因子合成为一个综合因子。

```python
class FactorCombiner:
    def combine(self, processed_factors: dict[str, pd.DataFrame]) -> pd.DataFrame
    def get_factor_info(self) -> dict[str, Any]
```

#### 合成方法

| 方法 | 说明 |
|------|------|
| `weighted_sum` | 加权求和合成 |
| `rank_weighted` | 排序加权合成 |

---

## 7. 组合优化模块 (portfolio.py)

### 7.1 优化器类层次

```
BaseOptimizer (基类)
├── EqualWeightOptimizer      # 等权重优化
├── MinVarianceOptimizer      # 最小方差优化
├── MeanVarianceOptimizer     # 均值方差优化（马科维茨）
└── RiskParityOptimizer       # 风险平价优化
```

### 7.2 各优化器详解

#### `EqualWeightOptimizer` - 等权重优化

```python
def optimize(self, factor_scores, returns=None, cov_matrix=None) -> pd.Series:
    # 选择目标数量的股票
    selected = factor_scores.nlargest(target_count).index
    # 等权重分配
    weights = pd.Series(1.0 / len(selected), index=selected)
    # 应用约束
    return self._apply_constraints(weights)
```

#### `MinVarianceOptimizer` - 最小方差优化

使用 `cvxpy` 求解二次规划问题：

```
minimize:   w^T * Σ * w
subject to: sum(w) = 1
            min_weight <= w <= max_weight
```

#### `MeanVarianceOptimizer` - 均值方差优化

```
maximize:   μ^T * w - λ * w^T * Σ * w
subject to: sum(w) = 1
            min_weight <= w <= max_weight
```

#### `RiskParityOptimizer` - 风险平价优化

使用迭代算法使各资产风险贡献相等：

```python
for iteration in range(max_iter):
    portfolio_vol = sqrt(w^T * Σ * w)
    marginal_contrib = Σ * w / portfolio_vol
    risk_contrib = w * marginal_contrib
    target = risk_contrib.mean()
    w_new = w * target / risk_contrib
    if converged: break
```

### 7.3 协方差估计方法

| 方法 | 函数 | 说明 |
|------|------|------|
| `sample` | `returns.cov()` | 样本协方差 |
| `ledoit_wolf` | `_ledoit_wolf_shrinkage()` | Ledoit-Wolf压缩估计 |
| `ewma` | `_ewma_covariance()` | 指数加权移动平均 |

### 7.4 整手数优化

```python
def round_lot_optimize(weights: pd.Series, prices: pd.Series, 
                      total_value: float, lot_size: int = 100) -> pd.Series:
    target_values = weights * total_value
    target_shares = target_values / prices
    rounded_shares = floor(target_shares / lot_size) * lot_size  # 100股整数倍
    actual_weights = rounded_shares * prices / sum(rounded_shares * prices)
    return actual_weights
```

---

## 8. 交易执行模块 (execution.py)

### 8.1 核心类: `ExecutionSimulator`

模拟真实的交易执行过程，包括价格获取、成本计算等。

#### 交易执行流程

```
订单输入
    │
    ├──→ 价格验证（开盘价与收盘价差异检查）
    │
    ├──→ 计算交易金额: amount = quantity * price
    │
    ├──→ 计算交易成本
    │       ├── 佣金: max(amount * commission_rate, commission_min)
    │       ├── 印花税（卖出）: amount * stamp_tax_rate
    │       └── 滑点: amount * slippage_pct
    │
    └──→ 创建交易记录并记录到日志
```

#### 关键方法

```python
class ExecutionSimulator:
    def execute_order(self, stock, side, quantity, date, open_price, close_price=None) -> tuple[bool, Optional[Trade]]
    def execute_pending_order(self, order, date, open_price, close_price=None) -> tuple[bool, Optional[Trade]]
    def _calculate_cost(self, amount: float, side: OrderSide) -> float
    def calculate_liquidation_value(self, stock, quantity, date, close_price) -> float
    def get_execution_stats(self) -> dict[str, Any]
```

### 8.2 交易记录类: `Trade`

```python
@dataclass
class Trade:
    date: pd.Timestamp        # 交易日期
    stock: str                # 股票代码
    side: OrderSide           # 买入/卖出
    quantity: int             # 数量
    price: float              # 成交价格
    amount: float             # 交易金额
    cost: float               # 交易成本
    net_amount: float         # 净金额
```

---

## 9. 待执行订单管理 (pending.py)

### 9.1 核心类: `PendingOrderQueue`

管理所有待执行订单，支持失败交易自动重试和备选替补机制。

#### 订单状态机

```
┌─────────┐    创建     ┌─────────┐    执行成功    ┌─────────┐
│  初始   │ ─────────→ │ PENDING │ ────────────→ │EXECUTED │
└─────────┘            └────┬────┘               └─────────┘
                            │
                            │ 过期
                            ▼
                       ┌─────────┐
                       │ EXPIRED │
                       └─────────┘
                            ▲
                            │ 取消
                            │
                       ┌─────────┐
                       │CANCELLED│
                       └─────────┘
```

#### 关键方法

```python
class PendingOrderQueue:
    def add_order(self, order: PendingOrder) -> None
    def get_pending_orders(self, stock=None, side=None) -> list[PendingOrder]
    def mark_executed(self, order, execute_date, execute_price) -> None
    def mark_expired(self, current_date: pd.Timestamp) -> None
    def cancel_orders(self, stock: str, cancel_date: pd.Timestamp) -> None
    def get_order_stats(self) -> dict[str, Any]
    def get_event_log(self) -> pd.DataFrame
```

#### 备选替补机制

```python
def select_fallback_stocks(factor_scores: pd.Series, excluded_stocks: list[str], depth: int = 10) -> list[str]:
    # 1. 过滤已排除的股票
    available = factor_scores.index.difference(excluded_stocks)
    # 2. 按因子得分排序
    # 3. 选择得分最高的 depth 个股票作为备选
    return available_scores.nlargest(depth).index.tolist()
```

---

## 10. 持仓跟踪模块 (tracker.py)

### 10.1 核心类: `PositionTracker`

负责跟踪持仓变化、计算组合价值和收益。

#### 核心数据结构

```python
@dataclass
class Position:
    stock: str                # 股票代码
    quantity: int             # 持仓数量
    avg_cost: float           # 平均成本
    market_value: float       # 市值
    unrealized_pnl: float     # 未实现盈亏
    realized_pnl: float       # 已实现盈亏

@dataclass
class PortfolioSnapshot:
    date: pd.Timestamp        # 日期
    cash: float               # 现金
    total_value: float        # 总价值
    positions: dict           # 持仓字典
    daily_return: float       # 日收益
    cumulative_return: float  # 累计收益
```

#### 关键方法

```python
class PositionTracker:
    def execute_trade(self, trade: Trade) -> None
    def update_market_values(self, date: pd.Timestamp, prices: pd.Series) -> None
    def get_total_value(self) -> float
    def get_position_weights(self, prices: pd.Series) -> pd.Series
    def get_sector_exposure(self, industry_data: pd.Series) -> dict[str, float]
    def get_snapshots_df(self) -> pd.DataFrame
    def get_performance_metrics(self) -> dict[str, Any]
```

---

## 11. 再平衡触发模块 (rebalance.py)

### 11.1 触发器类层次

```
BaseTrigger (基类)
├── FixedIntervalTrigger    # 固定间隔触发
├── ConditionalTrigger      # 条件触发
└── HybridTrigger           # 混合模式触发
```

### 11.2 各触发器详解

#### `FixedIntervalTrigger` - 固定间隔触发

支持频率: `daily`, `weekly`, `monthly`, `N_days`

```python
def _calculate_rebalance_dates(self) -> set[pd.Timestamp]:
    # daily: 所有交易日
    # weekly: 每周最后一个交易日
    # monthly: 每月最后一个交易日
    # N_days: 每N个交易日
```

#### `ConditionalTrigger` - 条件触发

| 触发条件 | 参数 | 说明 |
|---------|------|------|
| 信号变化 | `signal_change_threshold` | 持仓权重变化的L2范数 |
| 回撤触发 | `drawdown_trigger` | 组合价值回撤比例 |
| 波动率触发 | `volatility_trigger` | 波动率超过阈值 |

#### `HybridTrigger` - 混合触发

```
触发条件 = 固定间隔触发 
         OR 条件触发 
         OR 超过最大间隔天数
         
约束: 距离上次再平衡 >= hybrid_min_days
```

### 11.3 再平衡日历

```python
class RebalanceCalendar:
    def is_rebalance_date(self, date: pd.Timestamp) -> bool
    def get_next_rebalance_date(self, current_date: pd.Timestamp) -> Optional[pd.Timestamp]
    def get_rebalance_stats(self) -> dict[str, Any]
```

---

## 12. 回测引擎 (engine.py)

### 12.1 核心类: `BacktestEngine`

单策略回测引擎，集成所有模块，支持完整的待执行订单管理。

#### 引擎组件

```python
class BacktestEngine:
    self.dm: DataManager                    # 数据管理器
    self.universe: UniverseFilter           # 股票池过滤器
    self.pipeline: FactorPipeline           # 因子处理管道
    self.combiner: FactorCombiner           # 因子合成器
    self.optimizer: BaseOptimizer           # 组合优化器
    self.trigger: BaseTrigger               # 再平衡触发器
    self.executor: ExecutionSimulator       # 交易执行模拟器
    self.tracker: PositionTracker           # 持仓跟踪器
    self.pending_queue: PendingOrderQueue   # 待执行订单队列
```

#### 回测主循环

```python
def run(self) -> dict[str, Any]:
    for i, date in enumerate(self.dm.trade_dates):
        self._process_trading_day(date, i)
    return self._generate_results()

def _process_trading_day(self, date, date_index):
    # 1. 执行前一交易日生成的次日订单（开盘价）
    self._execute_next_day_orders(date, date_index)
    
    # 2. 处理待执行订单（pending_queue）
    self._process_pending_orders(date, date_index)
    
    # 3. 检查是否需要再平衡
    if self.trigger.should_trigger(date, ...):
        self._execute_rebalance(date, date_index)
    
    # 4. 更新持仓市值（收盘价）
    self.tracker.update_market_values(date, close_prices)
```

#### 再平衡执行流程

```
触发再平衡
    │
    ├──→ 1. 取消过期待执行订单
    │
    ├──→ 2. 获取当日因子信号
    │
    ├──→ 3. 过滤可交易股票 (tradable_mask)
    │
    ├──→ 4. 组合优化 (optimizer.optimize)
    │       ├── 获取收益率数据（用于风险模型）
    │       └── 执行优化得到目标权重
    │
    ├──→ 5. 计算目标持仓（考虑整手数）
    │       target_quantity = int(target_value / close_price / 100) * 100
    │
    └──→ 6. 生成交易订单，加入待执行队列
            ├── 买入订单 → pending_queue
            └── 卖出订单 → pending_queue
```

#### 次日开盘执行机制 (方案B)

```python
def _execute_order_next_open(self, order, date, date_index):
    # 将订单存储到 _next_day_orders，在下一个交易日开盘时执行
    self._next_day_orders.append({'order': order, 'create_date': date, ...})

def _execute_next_day_orders(self, date, date_index):
    # 使用当日开盘价执行前一交易日生成的订单
    for order_info in self._next_day_orders:
        success, trade = self.executor.execute_order(..., open_price)
        if success:
            self.tracker.execute_trade(trade)
```

---

## 13. 性能分析模块 (analytics.py)

### 13.1 核心类: `PerformanceAnalyzer`

负责计算和分析回测的各项性能指标，生成可视化报告。

#### 性能指标分类

| 类别 | 指标 | 说明 |
|------|------|------|
| **收益指标** | `total_return` | 累计收益率 |
| | `annual_return` | 年化收益率 |
| | `win_rate` | 胜率 |
| | `win_loss_ratio` | 盈亏比 |
| **风险指标** | `annual_volatility` | 年化波动率 |
| | `max_drawdown` | 最大回撤 |
| | `max_drawdown_duration` | 最大回撤持续期 |
| | `downside_volatility` | 下行波动率 |
| **风险调整收益** | `sharpe_ratio` | 夏普比率 |
| | `sortino_ratio` | 索提诺比率 |
| | `calmar_ratio` | 卡尔玛比率 |
| **交易指标** | `total_trades` | 总交易次数 |
| | `turnover_rate` | 换手率 |
| | `avg_trade_cost` | 平均交易成本 |

#### 可视化输出

| 图表 | 方法 | 输出文件 |
|------|------|---------|
| 净值曲线 | `generate_performance_chart()` | `performance_chart.png` |
| 月度收益热图 | `generate_monthly_returns_heatmap()` | `monthly_returns_heatmap.png` |
| 文本报告 | `_generate_text_report()` | `performance_report.txt` |
| CSV报告 | `_generate_csv_report()` | `performance_metrics.csv` |

#### 便捷函数

```python
def generate_report(snapshots: list[PortfolioSnapshot], trades_df: pd.DataFrame, 
                  output_dir: Path) -> dict[str, Any]:
    """一站式生成完整回测报告"""
```

---

## 14. 项目运行方式

### 14.1 环境安装

```bash
# 安装依赖
pip install -r requirements.txt
```

**依赖包列表:**

| 包名 | 版本 | 用途 |
|------|------|------|
| numpy | >=1.21.0 | 数值计算 |
| pandas | >=1.3.0 | 数据处理 |
| scipy | >=1.7.0 | 科学计算 |
| matplotlib | >=3.4.0 | 可视化 |
| seaborn | >=0.11.0 | 统计可视化 |
| cvxpy | >=1.2.0 | 凸优化 |

### 14.2 快速开始

```python
from pathlib import Path
from config import BacktestConfig, CostConfig, UniverseConfig, FactorConfig, OptimizerConfig, RebalanceConfig
from engine import BacktestEngine

# 创建配置
config = BacktestConfig(
    data_dir=Path("./data"),
    factor_files=["factor_value.pkl", "factor_momentum.pkl"],
    factor_weights={"factor_value": 0.6, "factor_momentum": 0.4},
    cost=CostConfig(commission_rate=0.0003),
    universe=UniverseConfig(exclude_suspended=True),
    factor=FactorConfig(winsorize_method="mad"),
    optimizer=OptimizerConfig(method="equal_weight", target_count=30),
    rebalance=RebalanceConfig(method="fixed", frequency="monthly"),
    initial_capital=10_000_000.0
)

# 运行回测
engine = BacktestEngine(config)
engine.setup()
results = engine.run()

# 查看结果
metrics = results['performance_metrics']
print(f"累计收益率: {metrics['total_return']:.2%}")
print(f"夏普比率: {metrics['sharpe_ratio']:.3f}")
```

### 14.3 运行演示程序

```bash
# 运行完整演示（生成合成数据并回测）
python demo.py
```

演示程序将：
1. 生成 200 只股票 500 天的合成数据
2. 运行完整回测
3. 生成详细报告和图表
4. 输出到 `demo_output/` 目录

### 14.4 数据格式要求

所有数据文件为 **pkl 格式** (pandas DataFrame)，行索引为日期，列索引为股票代码。

| 文件 | 格式 | 说明 |
|------|------|------|
| `close.pkl` | DataFrame | 收盘价 |
| `open.pkl` | DataFrame | 开盘价 |
| `high.pkl` / `low.pkl` | DataFrame | 最高/最低价 |
| `adj.pkl` | DataFrame | 复权因子 |
| `suspend.pkl` | DataFrame | 停牌状态 (1=停牌, 0=正常) |
| `industry.pkl` | DataFrame | 行业分类代码 |
| `st.pkl` | DataFrame | ST标记 (1=ST, 0=正常) |
| `mktcap.pkl` | DataFrame | 市值（元） |
| `factor_*.pkl` | DataFrame | 因子数据 |

---

## 15. 依赖关系汇总

### 15.1 完整依赖图

```
config.py
    │
    ├──→ data.py (BacktestConfig)
    │       │
    │       ├──→ filter/universe_filter_clean.py (DataManager)
    │       │       └──→ engine.py (UniverseFilter)
    │       │
    │       ├──→ factor.py (DataManager)
    │       │       └──→ engine.py (FactorPipeline, FactorCombiner)
    │       │
    │       └──→ portfolio.py (DataManager - 间接)
    │               └──→ engine.py (BaseOptimizer)
    │
    ├──→ execution.py (CostConfig)
    │       └──→ engine.py (ExecutionSimulator)
    │
    ├──→ pending.py (BacktestConfig)
    │       └──→ engine.py (PendingOrderQueue)
    │
    ├──→ rebalance.py (RebalanceConfig)
    │       └──→ engine.py (BaseTrigger)
    │
    ├──→ tracker.py (无直接依赖)
    │       └──→ engine.py (PositionTracker)
    │
    └──→ analytics.py (无直接依赖)
            └──→ engine.py (generate_report)
```

### 15.2 运行时序

```
1. BacktestEngine.__init__(config)
   │
2. BacktestEngine.setup()
   ├──→ DataManager 初始化
   ├──→ UniverseFilter 构建掩码
   ├──→ FactorPipeline 预计算因子
   ├──→ Optimizer 构建
   ├──→ Trigger 构建
   ├──→ ExecutionSimulator 初始化
   ├──→ PositionTracker 初始化
   └──→ PendingOrderQueue 初始化
   │
3. BacktestEngine.run()
   └──→ 遍历每个交易日
        ├──→ 执行次日开盘订单
        ├──→ 处理待执行订单
        ├──→ 检查再平衡触发
        ├──→ 执行再平衡（如触发）
        └──→ 更新持仓市值
   │
4. BacktestEngine._generate_results()
   ├──→ 获取快照和交易记录
   ├──→ 生成性能分析报告
   ├──→ 保存交易记录 CSV
   ├──→ 保存持仓快照 CSV
   └──→ 保存待执行订单事件日志
```

---

## 附录

### A. 关键设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **策略模式** | `portfolio.py` | `BaseOptimizer` + 子类实现不同优化策略 |
| **策略模式** | `rebalance.py` | `BaseTrigger` + 子类实现不同触发方式 |
| **工厂模式** | `portfolio.py` | `build_optimizer()` 根据配置创建优化器 |
| **工厂模式** | `rebalance.py` | `build_trigger()` 根据配置创建触发器 |
| **工厂模式** | `filter/__init__.py` | `create_filter()` 统一创建过滤器 |
| **单例模式** | `data.py` | 每个 `DataManager` 实例管理独立缓存 |
| **观察者模式** | `pending.py` | 事件日志记录订单生命周期 |
| **模板方法** | `factor.py` | `FactorPipeline.process()` 定义处理流程 |

### B. 性能优化策略

| 策略 | 实现位置 | 说明 |
|------|---------|------|
| 懒加载 | `data.py` | 属性访问时才加载数据 |
| 智能缓存 | `data.py` | `_cache` 字典缓存已加载数据 |
| 向量化计算 | `factor.py`, `filter/` | 使用 pandas/numpy 避免 Python 循环 |
| 预计算掩码 | `filter/universe_filter_clean.py` | 一次性构建所有过滤掩码 |
| 整手数优化 | `portfolio.py` | 向下取整到 100 股整数倍 |

### C. A股特殊处理

| 特性 | 实现 | 说明 |
|------|------|------|
| 涨跌停限制 | `UniverseFilter._build_limit_masks()` | 普通股 ±10%, ST股 ±5% |
| 整手交易 | `portfolio.py round_lot_optimize()` | 100股整数倍 |
| 印花税单边 | `execution.py _calculate_cost()` | 仅卖出收取 |
| 佣金最低5元 | `execution.py _calculate_cost()` | 不足5元按5元收取 |
| 停牌处理 | `UniverseFilter._build_suspend_mask()` | 停牌日不可交易 |
| 前复权价格 | `data.py get_adj_price()` | 价格 × 复权因子 |

---

*文档生成时间: 2026-05-10*  
*基于 Factor Trading v3.0 代码库分析生成*
