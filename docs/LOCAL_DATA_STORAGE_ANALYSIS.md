# 本地数据存储方案深度分析

## 一、现有数据结构分析

### 1.1 当前数据文件（E:\Ashare_data\market_data）

| 文件 | 内容 | 预估大小 | 访问模式 |
|------|------|---------|---------|
| `stock_close.pkl` | 收盘价矩阵 (dates × stocks) | ~500MB | 高频读取 |
| `stock_open.pkl` | 开盘价矩阵 | ~500MB | 高频读取 |
| `stock_high.pkl` | 最高价矩阵 | ~500MB | 中频读取 |
| `stock_low.pkl` | 最低价矩阵 | ~500MB | 中频读取 |
| `stock_volume.pkl` | 成交量矩阵 | ~500MB | 中频读取 |
| `stock_amount.pkl` | 成交额矩阵 | ~500MB | 低频读取 |
| `stock_adj.pkl` | 复权因子矩阵 | ~200MB | 高频读取 |
| `stock_return.pkl` | 收益率矩阵 | ~500MB | 高频读取 |
| `stock_suspend.pkl` | 停牌标记矩阵 | ~100MB | 中频读取 |
| `stock_ind.pkl` | 行业分类矩阵 | ~50MB | 低频读取 |
| `stock_name.pkl` | 股票名称映射 | ~10MB | 低频读取 |
| `list_date_df.pkl` | 上市日期 | ~5MB | 低频读取 |
| `all_dates.pkl` | 交易日历 | ~1MB | 高频读取 |
| `barra_df_tl.pkl` | Barra风险因子 | ~1GB | 中频读取 |
| `index_dict.pkl` | 指数成分股 | ~50MB | 中频读取 |
| `stock_df.pkl` | 股票基础信息 | ~20MB | 低频读取 |

**总计预估**: ~5-6GB 的 pickle 文件

### 1.2 当前存储问题

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| **Pickle 格式** | 加载慢、版本兼容差、无压缩 | 🔴 高 |
| **全量加载** | 内存占用大（5GB+），启动慢 | 🔴 高 |
| **无索引** | 日期/股票查询需全表扫描 | 🔴 高 |
| **无分区** | 无法按需加载特定时间段 | 🟡 中 |
| **单列存储** | 无法高效进行 SQL 式条件过滤 | 🟡 中 |
| **无元数据** | 数据版本、更新时间管理困难 | 🟡 中 |

---

## 二、开源时序数据库方案对比

### 2.1 方案总览

| 方案 | 类型 | 适用场景 | 学习成本 | 维护成本 |
|------|------|---------|---------|---------|
| **DuckDB** | 嵌入式 OLAP | 本地分析、SQL 查询 | 低 | 极低 |
| **TimescaleDB** | PostgreSQL 扩展 | 大规模时序存储 | 中 | 中 |
| **InfluxDB** | 专用时序数据库 | 实时写入、监控 | 中 | 中 |
| **ClickHouse** | 列式 OLAP | 海量数据分析 | 中 | 高 |
| **Arctic (MongoDB)** | 量化专用 | 金融时序数据 | 低 | 低 |
| **Parquet + PyArrow** | 文件格式 | 静态数据、批量读取 | 低 | 极低 |
| **Zarr** | 分块数组存储 | 大规模数组、云存储 | 中 | 低 |

### 2.2 详细对比

#### 方案 A: DuckDB（强烈推荐 ⭐）

```python
# DuckDB 示例
import duckdb

con = duckdb.connect('market_data.duckdb')

# 创建表
con.execute("""
    CREATE TABLE daily_prices (
        trade_date DATE,
        stock_code VARCHAR,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        volume BIGINT,
        amount DOUBLE
    )
""")

# 从 DataFrame 导入
con.execute("INSERT INTO daily_prices SELECT * FROM df")

# 时序查询 - 极快
con.execute("""
    SELECT stock_code, 
           AVG(close) as avg_close,
           STDDEV(close) as volatility
    FROM daily_prices 
    WHERE trade_date BETWEEN '2020-01-01' AND '2023-12-31'
    GROUP BY stock_code
""").fetchdf()
```

**优势**:
- ✅ 零配置，单文件存储
- ✅ 向量化执行，性能接近 C++
- ✅ 完整 SQL 支持，窗口函数丰富
- ✅ 与 Pandas/NumPy 零拷贝集成
- ✅ 支持直接查询 Parquet/CSV
- ✅ 压缩率高（比 CSV 小 10-100 倍）

**劣势**:
- ❌ 不支持并发写入（单写多读）
- ❌ 非纯时序优化（但性能足够）

**适用**: 本地量化研究、回测、因子计算

---

#### 方案 B: Arctic (MongoDB 上层封装)

```python
# Arctic 示例
from arctic import Arctic

store = Arctic('mongodb://localhost:27017')
store.initialize_library('market_data')
lib = store['market_data']

# 写入时序数据
lib.write('stock_close', close_df, metadata={'source': 'tushare'})

# 读取指定日期范围
lib.read('stock_close', date_range=DateRange('2020-01-01', '2023-12-31'))
```

**优势**:
- ✅ 专为金融时序设计
- ✅ 版本控制（数据历史回溯）
- ✅ Pandas DataFrame 原生支持
- ✅ 压缩和分块存储

**劣势**:
- ❌ 依赖 MongoDB（需单独安装）
- ❌ 社区活跃度下降
- ❌ 大规模查询性能一般

**适用**: 需要数据版本管理的场景

---

#### 方案 C: Parquet + PyArrow + 分区

```python
# Parquet 分区存储
import pyarrow.parquet as pq
import pyarrow as pa

# 按年份分区存储
table = pa.Table.from_pandas(df)
pq.write_to_dataset(
    table,
    root_path='market_data/parquet/daily_prices',
    partition_cols=['year'],
    compression='zstd'
)

# 读取特定分区
table = pq.read_table(
    'market_data/parquet/daily_prices',
    columns=['trade_date', 'stock_code', 'close'],
    filters=[('year', '=', 2023)]
)
```

**优势**:
- ✅ 列式存储，读取只需加载所需列
- ✅ 高效压缩（Zstd/Snappy）
- ✅ 跨语言支持（Python/R/Java）
- ✅ 与 Pandas/Spark/DuckDB 兼容

**劣势**:
- ❌ 更新数据需重写文件
- ❌ 无索引（需配合 DuckDB）

**适用**: 静态历史数据、批量分析

---

#### 方案 D: TimescaleDB

```sql
-- TimescaleDB 示例
CREATE TABLE stock_prices (
    trade_date TIMESTAMPTZ NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    open DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    PRIMARY KEY (trade_date, stock_code)
);

-- 转换为超表
SELECT create_hypertable('stock_prices', 'trade_date', chunk_time_interval => INTERVAL '1 month');

-- 时序查询
SELECT time_bucket('1 month', trade_date) AS month,
       stock_code,
       first(open, trade_date) as month_open,
       last(close, trade_date) as month_close
FROM stock_prices
WHERE stock_code = '000001.SZ'
GROUP BY month, stock_code;
```

**优势**:
- ✅ 纯时序优化（自动分区、压缩）
- ✅ 完整 SQL + 时序扩展函数
- ✅ 水平扩展（多节点集群）
- ✅ 持续聚合（自动物化视图）

**劣势**:
- ❌ 需安装 PostgreSQL + 扩展
- ❌ 配置较复杂
- ❌ 单机性能不如 DuckDB

**适用**: 生产环境、多用户共享、实时数据接入

---

## 三、推荐架构：分层存储方案

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层（回测/因子/策略）                     │
│         BacktestEngine / FactorPipeline / Strategy           │
├─────────────────────────────────────────────────────────────┤
│                    数据接口层 (Data API)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  DataManager │  │ DataLoaderV3 │  │  DuckDBQueryEngine  │  │
│  │  (兼容层)    │  │ (高性能层)   │  │  (SQL分析层)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    存储引擎层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  DuckDB     │  │  Parquet    │  │  Pickle (迁移中)    │  │
│  │  (主存储)   │  │  (归档存储)  │  │  (兼容旧数据)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    数据源层                                    │
│              Tushare / AKShare / 本地文件                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 存储分层策略

| 层级 | 存储 | 数据范围 | 用途 | 保留策略 |
|------|------|---------|------|---------|
| **热数据** | DuckDB (内存+磁盘) | 最近 2 年 | 日常回测、因子研究 | 常驻内存 |
| **温数据** | DuckDB (磁盘) | 近 5 年 | 历史分析、策略验证 | 按需加载 |
| **冷数据** | Parquet (压缩) | 全量历史 | 全量回测、数据归档 | 归档存储 |
| **元数据** | DuckDB/SQLite | 全量 | 股票信息、交易日历 | 常驻 |

---

## 四、具体实施方案

### 4.1 Phase 1: 数据迁移到 DuckDB（1-2 天）

```python
# data_migration.py
import duckdb
import pandas as pd
from pathlib import Path

class DataMigrator:
    """数据迁移工具：从 Pickle 迁移到 DuckDB"""
    
    def __init__(self, db_path: str = 'market_data.duckdb'):
        self.con = duckdb.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        """创建表结构"""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS daily_prices (
                trade_date DATE,
                stock_code VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                adj_factor DOUBLE,
                PRIMARY KEY (trade_date, stock_code)
            )
        """)
        
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS stock_info (
                stock_code VARCHAR PRIMARY KEY,
                stock_name VARCHAR,
                list_date DATE,
                industry VARCHAR,
                market VARCHAR
            )
        """)
        
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS trade_calendar (
                trade_date DATE PRIMARY KEY,
                is_trading_day BOOLEAN
            )
        """)
    
    def migrate_from_pickle(self, data_dir: Path):
        """从 Pickle 文件迁移"""
        # 读取 pickle
        close_df = pd.read_pickle(data_dir / 'stock_close.pkl')
        open_df = pd.read_pickle(data_dir / 'stock_open.pkl')
        # ... 其他字段
        
        # 转换成长格式
        df_long = self._pivot_to_long(close_df, open_df, high_df, low_df)
        
        # 导入 DuckDB
        self.con.execute("INSERT INTO daily_prices SELECT * FROM df_long")
        
    def _pivot_to_long(self, **kwargs) -> pd.DataFrame:
        """将宽格式转为长格式"""
        # 实现宽表转长表逻辑
        pass
```

### 4.2 Phase 2: 高性能查询接口（1 天）

```python
# core/data_duckdb.py
import duckdb
import pandas as pd
import numpy as np
from typing import Optional, List

class DuckDBDataManager:
    """DuckDB 数据管理器
    
    提供高性能的时序数据查询接口。
    """
    
    def __init__(self, db_path: str = 'market_data.duckdb'):
        self.con = duckdb.connect(db_path, read_only=True)
        
    def get_price_matrix(
        self,
        start_date: str,
        end_date: str,
        fields: List[str] = ['close'],
        stock_codes: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取价格矩阵（用于回测）
        
        Returns:
            DataFrame (dates × stocks)
        """
        fields_str = ', '.join(fields)
        
        query = f"""
            SELECT trade_date, stock_code, {fields_str}
            FROM daily_prices
            WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
        """
        
        if stock_codes:
            codes_str = ', '.join(f"'{c}'" for c in stock_codes)
            query += f" AND stock_code IN ({codes_str})"
        
        df = self.con.execute(query).fetchdf()
        
        # 转为宽格式
        return df.pivot(index='trade_date', columns='stock_code', values=fields[0])
    
    def get_factor_data(
        self,
        factor_name: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取因子数据"""
        query = f"""
            SELECT trade_date, stock_code, value as {factor_name}
            FROM factor_data
            WHERE factor_name = '{factor_name}'
            AND trade_date BETWEEN '{start_date}' AND '{end_date}'
        """
        df = self.con.execute(query).fetchdf()
        return df.pivot(index='trade_date', columns='stock_code', values=factor_name)
    
    def filter_stocks(
        self,
        date: str,
        conditions: List[str]
    ) -> List[str]:
        """条件过滤选股
        
        Args:
            conditions: SQL WHERE 条件列表
                例如: ["close > 10", "volume > 1000000"]
        """
        where_clause = ' AND '.join(conditions)
        
        query = f"""
            SELECT DISTINCT stock_code
            FROM daily_prices
            WHERE trade_date = '{date}'
            AND {where_clause}
        """
        
        result = self.con.execute(query).fetchdf()
        return result['stock_code'].tolist()
    
    def get_univariate_series(
        self,
        stock_code: str,
        field: str,
        start_date: str,
        end_date: str
    ) -> pd.Series:
        """获取单只股票时序"""
        query = f"""
            SELECT trade_date, {field}
            FROM daily_prices
            WHERE stock_code = '{stock_code}'
            AND trade_date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY trade_date
        """
        df = self.con.execute(query).fetchdf()
        return df.set_index('trade_date')[field]
    
    def execute_sql(self, query: str) -> pd.DataFrame:
        """执行自定义 SQL"""
        return self.con.execute(query).fetchdf()
```

### 4.3 Phase 3: 与现有引擎集成（1 天）

```python
# core/engine_v3_duckdb.py
from core.data_duckdb import DuckDBDataManager
from core.engine_v3_vector import VectorBacktestEngine

class DuckDBBacktestEngine(VectorBacktestEngine):
    """集成 DuckDB 的向量化回测引擎"""
    
    def __init__(self, config: dict, db_path: str = 'market_data.duckdb'):
        super().__init__(config)
        self.db = DuckDBDataManager(db_path)
        
    def load_data(self, start_date: str, end_date: str, stock_codes: List[str]):
        """从 DuckDB 加载数据"""
        close_df = self.db.get_price_matrix(start_date, end_date, ['close'], stock_codes)
        open_df = self.db.get_price_matrix(start_date, end_date, ['open'], stock_codes)
        
        from core.data_v3 import DataLoaderV3
        self.dl = DataLoaderV3.from_pandas_dataframes(
            close=close_df,
            open=open_df
        )
```

---

## 五、性能对比预期

| 操作 | Pickle (当前) | DuckDB (目标) | 提升 |
|------|--------------|---------------|------|
| 加载 5 年日 K 线 | 30-60 秒 | 2-5 秒 | **10x** |
| 查询单只股票 1 年 | 需加载全部 | 0.01 秒 | **1000x** |
| 条件过滤选股 | 内存中过滤 | 0.1 秒 | **100x** |
| 范围查询 (2年) | 加载全部后切片 | 1 秒 | **30x** |
| 存储空间 | ~5GB | ~1-2GB (压缩) | **3x** |
| 内存占用 | 5GB+ | 按需加载 | **灵活** |

---

## 六、推荐实施路线

| 阶段 | 任务 | 时间 | 优先级 |
|------|------|------|--------|
| **Phase 1** | 搭建 DuckDB，迁移现有 Pickle 数据 | 1-2 天 | 🔥 P0 |
| **Phase 2** | 封装 DuckDBDataManager 查询接口 | 1 天 | 🔥 P0 |
| **Phase 3** | 修改 DataManager 支持 DuckDB 后端 | 1 天 | 🔥 P0 |
| **Phase 4** | 回测引擎集成 DuckDB 数据加载 | 0.5 天 | ⚡ P1 |
| **Phase 5** | 历史数据归档到 Parquet | 0.5 天 | ⚡ P1 |
| **Phase 6** | 数据更新管道（Tushare → DuckDB） | 1 天 | ⚡ P1 |

---

## 七、总结

**推荐方案**: **DuckDB 作为主存储 + Parquet 作为归档**

**核心优势**:
1. **零配置**: 单文件，无需安装数据库服务
2. **高性能**: 向量化执行，比 Pandas 快 10-100 倍
3. **SQL 支持**: 复杂条件过滤、窗口函数、时序分析
4. **压缩存储**: 比 Pickle 节省 50-70% 空间
5. **生态兼容**: 与 Pandas/NumPy/Arrow 零拷贝集成

**适用场景**:
- ✅ 本地量化研究（单用户）
- ✅ 历史数据回测
- ✅ 因子计算与验证
- ✅ 条件选股、时序分析
- ⚠️ 实时高频交易（需配合消息队列）
- ❌ 多用户并发写入（考虑 TimescaleDB）
