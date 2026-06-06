# Level 1 行情数据 × DuckDB 支持性分析

## 一、Level 1 数据现状

### 1.1 数据规模

| 指标 | 数值 |
|------|------|
| **文件数量** | 2,250 个 |
| **总大小** | **25.64 GB** |
| **时间范围** | 2014-01-02 ~ 2023-03-30 |
| **单文件平均** | ~11.4 MB |
| **单文件行数** | ~662,268 行 |
| **总记录数** | ~15 亿条 |

### 1.2 数据结构

```
Level 1 快照数据（每分钟/每5分钟一条）
┌──────────┬────────────┬──────┬──────┬──────┬───────┬────────┬────────┐
│   time   │ stock_code │ open │ high │  low │ close │ volume │ amount │
├──────────┼────────────┼──────┼──────┼──────┼───────┼────────┼────────┤
│  93000   │     1      │12.12 │12.12 │12.12 │ 12.12 │ 236865 │2.87e+06│
│  93100   │     1      │12.11 │12.11 │12.09 │ 12.11 │ 859551 │1.04e+07│
│   ...    │    ...     │ ...  │ ...  │ ...  │  ...  │  ...   │  ...   │
└──────────┴────────────┴──────┴──────┴──────┴───────┴────────┴────────┘
```

**字段说明**:
- `time`: 时间戳 (int32) - 格式 HHMMSS，如 93000 表示 09:30:00
- `stock_code`: 股票代码 (int64) - 数字格式，如 1=000001.SZ
- `open/high/low/close`: OHLC 价格
- `volume`: 成交量
- `amount`: 成交额

### 1.3 数据特点

| 特点 | 说明 |
|------|------|
| **高频** | 分钟级/5分钟级快照 |
| **大容量** | 25GB+，15亿条记录 |
| **追加写入** | 每日新增一个文件 |
| **时间有序** | 每个文件内按时间排序 |
| **多股票混合** | 单文件包含当日所有股票 |

---

## 二、DuckDB 对 Level 1 数据的支持能力分析

### 2.1 DuckDB 核心能力匹配度

| Level 1 需求 | DuckDB 支持 | 匹配度 |
|-------------|------------|--------|
| **海量数据存储** | 单文件可达 TB 级 | ✅ 优秀 |
| **高频时序查询** | 向量化执行，毫秒级 | ✅ 优秀 |
| **时间范围过滤** | 日期/时间索引优化 | ✅ 优秀 |
| **股票代码过滤** | 字符串/整数索引 | ✅ 优秀 |
| **聚合计算** | 窗口函数、GROUP BY | ✅ 优秀 |
| **实时追加写入** | 支持 INSERT，但非最优 | ⚠️ 一般 |
| **流式处理** | 不支持原生流式 | ❌ 较弱 |

### 2.2 性能预估

基于 DuckDB 的向量化执行引擎，对 Level 1 数据的性能预期：

| 操作 | 数据量 | 预估耗时 | 说明 |
|------|--------|---------|------|
| **全表扫描** | 15亿条 | 2-5秒 | 顺序读取 |
| **单日查询** | 66万条 | 0.01秒 | 日期过滤 |
| **单股全历史** | ~2250条 | 0.001秒 | 代码+日期索引 |
| **1分钟K线聚合** | 15亿→日级 | 5-10秒 | 时间桶聚合 |
| **VWAP计算** | 15亿条 | 10-20秒 | 加权平均 |

### 2.3 存储空间预估

| 格式 | 原始大小 | DuckDB 压缩后 | 压缩率 |
|------|---------|--------------|--------|
| Feather (当前) | 25.64 GB | - | - |
| DuckDB (导入后) | - | **8-12 GB** | **~60%** |
| Parquet (归档) | - | 6-10 GB | ~70% |

---

## 三、Level 1 场景下的 DuckDB 适用性评估

### 3.1 ✅ 非常适合的场景

| 场景 | 说明 |
|------|------|
| **历史数据回测** | 加载特定日期范围，快速筛选 |
| **因子计算** | 分钟级收益率、波动率、成交量因子 |
| **条件选股** | 盘中价格突破、成交量异常筛选 |
| **统计分析** | 日内波动统计、价格分布 |
| **数据探索** | SQL 交互式查询 |

### 3.2 ⚠️ 需要权衡的场景

| 场景 | 问题 | 解决方案 |
|------|------|---------|
| **每日数据追加** | DuckDB 单写多读，并发写入受限 | 每日批量导入，或分库策略 |
| **实时流处理** | 不支持流式计算 | 结合 Kafka + 内存缓存 |
| **超高频查询** | 毫秒级延迟要求 | 热数据缓存到内存 |

### 3.3 ❌ 不适合的场景

| 场景 | 原因 | 替代方案 |
|------|------|---------|
| **Tick级高频交易** | 延迟不够低 | 专用时序库 (InfluxDB/TimescaleDB) |
| **多用户并发写入** | 锁机制限制 | TimescaleDB / ClickHouse |
| **实时行情推送** | 非流式架构 | Redis / Kafka |

---

## 四、推荐架构：Level 1 数据分层存储

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层                                     │
│    回测引擎 / 因子计算 / 策略研究 / 实时监控                    │
├─────────────────────────────────────────────────────────────┤
│                    数据接口层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Level1Loader │  │  DuckDBMgr  │  │   RealtimeCache     │  │
│  │  (数据加载)   │  │  (SQL查询)   │  │   (实时缓存)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    存储引擎层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  DuckDB     │  │  Feather    │  │     Parquet         │  │
│  │  (热数据)   │  │  (原始文件)  │  │   (归档压缩)        │  │
│  │  最近2年    │  │  每日文件   │  │   历史数据          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 存储分层策略

| 层级 | 存储 | 数据范围 | 用途 | 更新策略 |
|------|------|---------|------|---------|
| **热数据** | DuckDB | 最近 2 年 (~5GB) | 日常回测、因子研究 | 每日批量导入 |
| **温数据** | Feather 文件 | 近 5 年 | 历史回溯、全量分析 | 每日新增文件 |
| **冷数据** | Parquet 压缩 | 全量历史 | 归档、合规 | 月度压缩归档 |

---

## 五、具体实施方案

### 5.1 Phase 1: DuckDB 导入 Level 1 数据

```python
# level1_duckdb_loader.py
import duckdb
import pyarrow.feather as feather
from pathlib import Path
from datetime import datetime

class Level1DuckDBLoader:
    """Level 1 数据 DuckDB 加载器"""
    
    def __init__(self, db_path: str = 'level1_data.duckdb'):
        self.con = duckdb.connect(db_path)
        self._create_table()
    
    def _create_table(self):
        """创建 Level 1 数据表"""
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS level1_snapshots (
                trade_date DATE,
                trade_time TIME,
                stock_code VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE
            )
        """)
        
        # 创建索引
        self.con.execute("""
            CREATE INDEX IF NOT EXISTS idx_date_code 
            ON level1_snapshots(trade_date, stock_code)
        """)
    
    def import_feather_file(self, file_path: Path):
        """导入单个 Feather 文件"""
        # 从文件名提取日期
        date_str = file_path.stem  # "2014-01-02"
        trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 读取 Feather
        df = feather.read_feather(str(file_path))
        
        # 转换时间格式
        df['trade_date'] = trade_date
        df['trade_time'] = df['time'].apply(
            lambda x: f"{x//10000:02d}:{(x//100)%100:02d}:{x%100:02d}"
        )
        
        # 转换股票代码
        df['stock_code'] = df['stock_code'].apply(
            lambda x: f"{x:06d}.SZ" if x < 1000000 else f"{x:06d}.SH"
        )
        
        # 选择并重命名列
        df = df[['trade_date', 'trade_time', 'stock_code', 
                 'open', 'high', 'low', 'close', 'volume', 'amount']]
        
        # 导入 DuckDB
        self.con.register('temp_df', df)
        self.con.execute("INSERT INTO level1_snapshots SELECT * FROM temp_df")
        self.con.unregister('temp_df')
    
    def import_directory(self, data_dir: Path, start_date=None, end_date=None):
        """批量导入目录"""
        files = sorted(data_dir.glob('*.feather'))
        
        for file_path in files:
            date_str = file_path.stem
            file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 日期过滤
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue
            
            self.import_feather_file(file_path)
            print(f"导入完成: {date_str}")
```

### 5.2 Phase 2: Level 1 查询接口

```python
# core/level1_manager.py
import duckdb
import pandas as pd
from typing import List, Optional

class Level1DataManager:
    """Level 1 数据管理器"""
    
    def __init__(self, db_path: str = 'level1_data.duckdb'):
        self.con = duckdb.connect(db_path, read_only=True)
    
    def get_intraday_bars(
        self,
        stock_code: str,
        trade_date: str,
        fields: List[str] = ['open', 'high', 'low', 'close', 'volume']
    ) -> pd.DataFrame:
        """获取日内分钟线"""
        fields_str = ', '.join(fields)
        query = f"""
            SELECT trade_time, {fields_str}
            FROM level1_snapshots
            WHERE stock_code = '{stock_code}'
            AND trade_date = '{trade_date}'
            ORDER BY trade_time
        """
        return self.con.execute(query).fetchdf()
    
    def get_daily_vwap(
        self,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """计算日度 VWAP"""
        query = f"""
            SELECT 
                trade_date,
                SUM(close * volume) / SUM(volume) as vwap,
                SUM(volume) as total_volume,
                SUM(amount) as total_amount
            FROM level1_snapshots
            WHERE stock_code = '{stock_code}'
            AND trade_date BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY trade_date
            ORDER BY trade_date
        """
        return self.con.execute(query).fetchdf()
    
    def get_intraday_volatility(
        self,
        stock_code: str,
        trade_date: str
    ) -> float:
        """计算日内波动率"""
        query = f"""
            SELECT STDDEV(close) as volatility
            FROM level1_snapshots
            WHERE stock_code = '{stock_code}'
            AND trade_date = '{trade_date}'
        """
        result = self.con.execute(query).fetchdf()
        return result['volatility'].iloc[0]
    
    def screen_stocks(
        self,
        trade_date: str,
        conditions: List[str]
    ) -> List[str]:
        """条件选股（如：盘中突破、放量）"""
        where_clause = ' AND '.join(conditions)
        query = f"""
            SELECT DISTINCT stock_code
            FROM level1_snapshots
            WHERE trade_date = '{trade_date}'
            AND {where_clause}
        """
        result = self.con.execute(query).fetchdf()
        return result['stock_code'].tolist()
```

### 5.3 Phase 3: 与回测引擎集成

```python
# core/engine_level1.py
from core.level1_manager import Level1DataManager
from core.engine_v3_vector import VectorBacktestEngine

class Level1BacktestEngine(VectorBacktestEngine):
    """基于 Level 1 数据的回测引擎"""
    
    def __init__(self, config: dict, db_path: str = 'level1_data.duckdb'):
        super().__init__(config)
        self.level1 = Level1DataManager(db_path)
    
    def load_level1_data(
        self,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
        bar_freq: str = '1min'
    ):
        """加载 Level 1 数据并转换为指定频率"""
        # 从 DuckDB 查询
        query = f"""
            SELECT 
                trade_date,
                trade_time,
                stock_code,
                open, high, low, close, volume, amount
            FROM level1_snapshots
            WHERE stock_code IN ({', '.join(f"'{c}'" for c in stock_codes)})
            AND trade_date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY trade_date, trade_time
        """
        df = self.level1.con.execute(query).fetchdf()
        
        # 转换为分钟 K 线 (如果需要)
        if bar_freq == '1min':
            # 已经是分钟级
            pass
        elif bar_freq == '5min':
            df = self._resample_to_5min(df)
        
        # 转换为 DataLoaderV3 格式
        close_df = df.pivot(index='datetime', columns='stock_code', values='close')
        
        from core.data_v3 import DataLoaderV3
        self.dl = DataLoaderV3.from_pandas_dataframes(close=close_df)
    
    def _resample_to_5min(self, df: pd.DataFrame) -> pd.DataFrame:
        """重采样为 5 分钟 K 线"""
        df['datetime'] = pd.to_datetime(
            df['trade_date'].astype(str) + ' ' + df['trade_time'].astype(str)
        )
        df = df.set_index('datetime')
        
        resampled = df.groupby('stock_code').resample('5min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum'
        }).reset_index()
        
        return resampled
```

---

## 六、性能优化策略

### 6.1 索引优化

```sql
-- 复合索引（最常用查询）
CREATE INDEX idx_date_code ON level1_snapshots(trade_date, stock_code);

-- 时间索引（日内查询）
CREATE INDEX idx_time ON level1_snapshots(trade_time);

-- 股票代码索引（单股历史）
CREATE INDEX idx_code ON level1_snapshots(stock_code);
```

### 6.2 分区策略

```sql
-- 按年份分区（如果 DuckDB 支持）
-- 或使用多个 DuckDB 文件
-- 2014-2016.duckdb, 2017-2019.duckdb, 2020-2023.duckdb
```

### 6.3 内存优化

```python
# 只加载需要的列
query = """
    SELECT trade_date, trade_time, stock_code, close, volume
    FROM level1_snapshots
    WHERE ...
"""

# 使用更小的数据类型
ALTER TABLE level1_snapshots 
ALTER COLUMN volume TYPE INTEGER;
```

---

## 七、总结与建议

### 7.1 DuckDB 适用性结论

| 维度 | 评估 | 说明 |
|------|------|------|
| **存储能力** | ✅ 完全支持 | 25GB 数据轻松处理 |
| **查询性能** | ✅ 优秀 | 向量化执行，毫秒级响应 |
| **时序分析** | ✅ 优秀 | 窗口函数、时间桶聚合 |
| **实时写入** | ⚠️ 一般 | 单写多读，需批量导入 |
| **高频交易** | ❌ 不适合 | 延迟不够低 |

### 7.2 推荐方案

**✅ 推荐：DuckDB 作为 Level 1 数据主存储**

理由：
1. **零配置**：单文件数据库，无需安装服务
2. **高性能**：向量化查询比 pandas 快 10-100 倍
3. **压缩率高**：25GB → ~8-12GB
4. **SQL 支持**：复杂时序查询、窗口函数
5. **生态兼容**：与 Python/Pandas/Arrow 无缝集成

### 7.3 实施路线图

| 阶段 | 任务 | 时间 | 优先级 |
|------|------|------|--------|
| **Phase 1** | 搭建 DuckDB，导入历史 Level 1 数据 | 2-3 天 | 🔥 P0 |
| **Phase 2** | 封装 Level1DataManager 查询接口 | 1 天 | 🔥 P0 |
| **Phase 3** | 回测引擎集成 Level 1 数据加载 | 1 天 | 🔥 P0 |
| **Phase 4** | 每日自动导入新数据脚本 | 0.5 天 | ⚡ P1 |
| **Phase 5** | 热数据缓存优化 | 1 天 | ⚡ P1 |

### 7.4 注意事项

1. **写入策略**：每日收盘后批量导入，避免实时写入
2. **备份策略**：定期备份 DuckDB 文件
3. **监控**：监控数据库大小和查询性能
4. **扩展**：数据量超过 100GB 时考虑分库或 TimescaleDB
