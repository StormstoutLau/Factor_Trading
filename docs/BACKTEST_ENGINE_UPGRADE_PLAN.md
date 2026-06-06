# 回测引擎升级方案 - v4.0
---
> 对标 Qlib 等顶尖框架，贴近真实交易，性能极致优化

## 目录

---

## 一、当前架构分析

### 1.1 当前优势
- ✅ **依赖注入架构已落地，模块解耦完整
- ✅ **核心引擎 V2 提供接口规范
- ✅ 已支持多种执行价格类型
- ✅ Walk-Forward 回测框架已实现
- ✅ 风控、多策略分配、Agent 系统较完善

### 1.2 主要问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| **数据层 | 🔴 高 | 每日主循环逐个遍历日期，频繁 DataFrame.loc 操作，性能瓶颈 |
| **订单撮合** | 🔴 高 | 没有按顺序处理，缺乏市场微结构缺失 |
| **实时事件驱动缺失 |
| **因子计算** | 🟡 中 | 单因子处理管道虽已存在，但未向量化不足 |
| **内存管理** | 🟡 中 | 大量中间 DataFrame 冗余，重复计算 |
| **实盘对接** | 🔴 高 | 缺少订单执行算法（TWAP/VWAP/ICEBERG 只是占位，需完善 |
| **高性能向量回测** | 🟡 中 | 缺少 Qlib 风格的表达式 DSL / HDF5 / Parquet 优化缺失 |

---

## 二、对标 Qlib / Backtrader / Zipline 架构特性对比

| 特性 | 当前 v3.0 | Qlib | Backtrader | 升级优先级 |
|------|---------|------|------------|------------|
| **高性能向量回测** | ❌ | ✅ | ❌ | P0 |
| **表达式语言（DSL）** | ❌ | ✅ | ❌ | P1 |
| **多股票/多因子并行** | ❌ | ✅ | ❌ | P0 |
| **事件驱动** | ⚠️ | ❌ | ✅ | P1 |
| **订单簿/微结构模拟** | ❌ | ❌ | ❌ | P2 |
| **复权处理** | ✅ | ✅ | ✅ | P0 |
| **回测性能（速度** |
| **实盘对接** | ❌ | ✅ | ✅ | P1 |
| **因子库管理** | ✅ | ✅ | ❌ | P0 |
| **风险归因** | ✅ | ✅ | ❌ | P1 |

---

## 三、详细升级方案

---

### Phase 1️⃣ **性能极致优化：DataLayer V3 - 矢量化回测引擎

#### 核心思路
放弃 `for date in dates` 循环
改为：**全向量化模式 + 分块日期循环
参考 Qlib 的 `RecordHandler` + `Inferencer` 设计

#### 1.1 新增 `core/data_v3.py`

**核心类**：`Qlib 风格数据处理器

```python
class DataLoaderV3:
    """Qlib风格数据加载器

    设计目标：
    1. 预加载所有必要数据到内存中
    2. 统一对齐到同一交易日历
    3. NumPy 数组化存储，避免 pandas 开销
    4. 日期位置映射 {date_str: idx}
    5. HDF5/Parquet 原生文件格式
    """

    _data: dict[str, np.ndarray]  # 所有数据均为 NumPy 数组，形状 (n_dates, n_stocks
    _date2idx: dict[str, int]
    _stock2idx: dict[str, int]
    _idx2date: list[str]
    _idx2stock: list[str]
```

**性能优化对比**
| 指标 | 当前（pandas 方案 | 优化 NumPy 向量化 | 加速比 |
|------|-------------------|------------------|--------|
| 日期循环 | O(D×S | O(D) | 50-100x |
| 内存占用 | ~2.5GB | ~0.8GB | 3x |
| 因子计算 | 循环中切片 | 向量化 | 20-50x |

#### 1.2 新增 `core/engine_v3_vector.py` - 向量回测引擎

```python
class VectorBacktestEngine:
    """全向量化回测引擎

    设计:
        主循环：先预计算所有信号 → 预计算交易 → 按块执行
    """
```

---

### Phase 2️⃣ **真实交易：事件驱动 + 微结构模拟**

#### 2.1 新增 `core/order_book.py` 与 `core/market_microstructure.py`

```
├── core/
│   ├── order_book.py              # 订单簿模拟器
│   │   ├── OrderBookSimulator  # 模拟盘口、深度、冲击成本
│   ├── market_microstructure.py  # 市场微结构模型
│   │   ├── 滑点模型、冲击成本、冲击成本衰减
│   ├── execution_algorithms.py     # TWAP/VWAP/ICEBERG
```

#### 2.2 订单执行算法完善

| 算法 | 说明 |
|------|------|
| `TWAP` | 时间加权平均价格 |
| `VWAP` | 成交量加权平均价格 |
| `ICEBERG` | 冰山单 |
| `MKT_IMPACT` | 冲击模型 |

---

### Phase 3️⃣ **架构：DSL 因子语言（可选，但有意义）
```python
# 类似 Qlib 的 Alpha360 表达式风格
# 简化的简易 DSL 解析器
# 例如：
from factor_dsl import FactorExpr
expr = FactorExpr("(rank(ts_mean(close, 20)) / ts_mean(close, 60)) - 1")
factor = expr.compute(data_v3.eval(expr)
```

---

### Phase 4️⃣ **工具链增强

| 工具 | 说明 |
|------|------|
| `benchmark.py` | 性能基准测试 |
| `profile_engine.py` | 性能分析 |
| `profile_engine.py` | 性能分析 |
| `factor_builder.py` | 因子构造器 |
| `optimizer_v3.py` | 组合优化 |

---

## 四、升级后的性能预期

| 场景 | 当前 | 目标 |
|------|------|------|
| 5000 只股票 × 2500 天 | ~180s | ~10-30s |
| Walk-Forward (1000万组合 × 100回测 |  | 3-5分钟 |
| 因子批量测试 100个×20参数 |  |  |
|

---

## 五、升级路线图

| 阶段 | 任务 | 预计时间 | 状态 |
|------|------|----------|------|
| 0️⃣1 | DataLayer V3 | 3-5天 | 设计中 |
| 2️⃣ | Vector Engine | 5-7天 | 设计中 |
| 3️⃣ | Event-Driven + Execution V3 | 3-5天 | 设计中 |
| 4️⃣ | Integration Testing + Benchmarking | 3-5天 | 设计中 |

---

## 六、具体设计细节

### 6.1 VectorBacktestEngine 核心流程

```mermaid
graph TD
    A[Start] --> B{Setup\nDataLoaderV3]
    B --> C[Signal\nVectorized]
    C --> D[Portfolio\nVector]
    D --> E[Rebalance\nSignals]
    E --> F[Execute\nVectorized]
    F --> G[Performance\nMetrics]
```

### 6.2 真实交易场景新增

```python
class MarketImpactModel:
    """冲击成本模型
    - 流动性分层
    - 冲击成本衰减
    - 滑点分布
    - 对手方对手方方
    """
    slippage: SlippageModel
    market_impact: MarketImpactModel
    order_book: OrderBookSimulator
    trade_simulation: TradeSimulator
```

---

## 七、兼容性与迁移路径

### 7.1 渐进式升级保证

```python
# Backward Compatibility Layer
from core.engine_v2 import BacktestEngineV2
# ✅ 继续支持当前代码
from core.engine_v3_vector import VectorBacktestEngine
# ✅ 新增高性能引擎
```

---

## 八、具体代码改动

### 8.1 core/data_v3.py 预览

```python
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any

class DataLoaderV3:
    """Qlib风格向量化数据加载器

    Attributes:
        price_data: Dict[str, np.ndarray]  # 'open'/'close'/'high'/'low' → shape (n_dates, n_stocks)
        factor_data: Dict[str, np.ndarray]  # 因子数据 shape (n_dates, n_stocks)
        dates: np.ndarray[str]  # shape (n_dates,)
        stocks: np.ndarray[str]  # shape (n_stocks,)
        date_map: Dict[str, int]  # 日期名 → 索引
        stock_map: Dict[str, int]  # 股票名 → 索引

    """
    def __init__(self, data_dir: Path, from_hdf5: bool = True):
        ...

    def preload(self) -> None:
        ...

    def get_slice(self, start: int, end: int) -> dict[str, np.ndarray]:
        return {k: v[start:end] for k, v in self.price_data.items()}

    @staticmethod
    def from_pandas_dataframes(
        close: pd.DataFrame,
        open: pd.DataFrame,
        high: pd.DataFrame,
        low: pd.DataFrame,
        factor_dict: Dict[str, pd.DataFrame]
    ) -> "DataLoaderV3":
        """从 pandas 迁移数据构建
        """
```

### 8.2 core/engine_v3_vector.py 预览

```python
class VectorBacktestEngine:
    """全向量化回测引擎

    设计思路:
        1. 预先计算所有因子 → 预先计算信号 → 预先计算再平衡 →
        → 预计算仓位变更
    """

    def __init__(self, config, data_v3: DataLoaderV3):
        self.cfg = config
        self.dl = data_v3
        self._signals = None
        self._positions = np.zeros_like(data_v3.price_data['close'])
        self._cash = np.ones(data_v3.n_dates) * config.initial_capital
        self._trade_dates_rebalance = ...

    def setup(self):
        # 预计算因子
        self._precompute_factors()
        # 预计算信号
        self._precompute_signals()

    def run_vectorized(self):
        """核心循环
        for i in range(0, self.dl.n_dates):
            if i in self._rebalance_indices:
                # 向量化计算再平衡
            self._advance_one_step(i)

        return self._results
```

---

## 九、现有问题与现有代码兼容性

### 9.1 已有的好设计保留

| 模块 | 状态 | 说明 |
|------|------|------|
| `core/interfaces.py` | ✅ 保留 | 接口层不变 |
| `core/factory.py` | ✅ 保留 | 工厂模式 |
| `core/risk_monitor.py` | ✅ 保留 | 风控引擎 |
| `core/attribution.py` | ✅ 保留 | 归因 |
| `core/analytics.py` | ✅ 保留 | 分析 |
| `agents/` | ✅ 保留 | 全部 Agent 系统 |

---

## 十、总结与优先级

| 任务 | 优先度 | 时间窗口 |
|------|--------|----------|
| **核心 DataLayerV3 与 VectorEngine | 🔥 P0 | 第一周 |
| Execution V3 执行升级 | 🔥 P0 | 第二周 |
| DSL（简化） | ⚡️ P1 | 第一-第二周 |
| 实盘桥接层 | ⚡️ P1 | 第三周 |
| Benchmarking & Testing | ⚡️ P0 | 始终 |

