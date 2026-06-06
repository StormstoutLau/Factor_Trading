# 回测引擎架构升级方案

## 1. 需求分析

### 1.1 因子批量回测需求

**当前限制:**
- 引擎只支持单因子/固定因子组合回测
- 因子文件通过`factor_files`列表静态配置
- 每次回测需要重新加载数据

**需求场景:**
```python
# 批量回测100个因子
factor_library = load_factor_library()  # 因子库
results = {}
for factor_name, factor_data in factor_library.items():
    engine = BacktestEngine(config, factor_data=factor_data)
    results[factor_name] = engine.run()
```

**核心问题:**
1. 数据重复加载（每个因子都重新加载价格数据）
2. 无法动态切换因子
3. 缺乏批量结果聚合和对比分析
4. 因子IC、IR、半衰期等统计量未自动计算

### 1.2 因子库动态维护需求

**当前限制:**
- 因子文件是静态的pickle文件
- 没有因子元数据管理
- 因子版本控制和血缘追踪缺失

**需求场景:**
```python
# 动态添加新因子
factor_db.add_factor(
    name="custom_momentum_20d",
    data=momentum_data,
    metadata={
        "category": "momentum",
        "frequency": "daily",
        "author": "quant_team",
        "version": "1.0.0"
    }
)

# 查询因子
factors = factor_db.query(category="momentum", ic_ir_min=0.03)

# 因子血缘追踪
lineage = factor_db.get_lineage("custom_momentum_20d")
# -> ["close_price", "returns", "rolling_mean"]
```

### 1.3 下单策略评估需求

**当前限制:**
- 执行模型简单（仅支持限价单）
- 缺乏多种订单类型（TWAP、VWAP、冰山订单等）
- 没有市场冲击模型
- 无法评估不同下单策略的绩效差异

**需求场景:**
```python
# 对比不同下单策略
strategies = {
    "market_order": MarketOrderStrategy(),
    "twap": TWAPStrategy(num_slices=10),
    "vwap": VWAPStrategy(window_minutes=30),
    "iceberg": IcebergStrategy(display_qty=100),
}

for name, strategy in strategies.items():
    executor = ExecutionSimulator(strategy=strategy)
    engine = BacktestEngine(config, executor=executor)
    results[name] = engine.run()
```

---

## 2. 架构升级方案

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Factor Trading System V3.1                │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Factor DB   │  │ Strategy    │  │ Order Strategy      │ │
│  │ (因子库)     │  │ Evaluator   │  │ Evaluator           │ │
│  │             │  │ (策略评估)   │  │ (下单策略评估)       │ │
│  │ - CRUD      │  │             │  │                     │ │
│  │ - Metadata  │  │ - IC/IR     │  │ - TWAP/VWAP         │ │
│  │ - Lineage   │  │ - Turnover  │  │ - Iceberg           │ │
│  │ - Version   │  │ - Decay     │  │ - Market Impact     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                    │            │
│         ▼                ▼                    ▼            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Batch Backtest Engine (批量回测引擎)        │  │
│  │                                                     │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │  │
│  │  │ Factor 1│  │ Factor 2│  │ Factor N│  ...       │  │
│  │  │ Engine  │  │ Engine  │  │ Engine  │            │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘            │  │
│  │       └─────────────┴─────────────┘                │  │
│  │                     │                              │  │
│  │                     ▼                              │  │
│  │         ┌─────────────────────┐                   │  │
│  │         │  Result Aggregator  │                   │  │
│  │         │  (结果聚合分析器)     │                   │  │
│  │         └─────────────────────┘                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                           │                                │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Report & Visualization                  │  │
│  │         (报告生成与可视化)                            │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块升级

#### 2.2.1 因子数据库 (FactorDatabase)

```python
# core/factor_db.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd


@dataclass
class FactorMetadata:
    """因子元数据"""
    name: str
    category: str  # 'value', 'growth', 'momentum', 'quality', etc.
    frequency: str  # 'daily', 'weekly', 'monthly'
    author: str
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parent_factors: list[str] = field(default_factory=list)  # 血缘追踪
    
    # 统计指标（动态计算）
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    ir: Optional[float] = None
    half_life: Optional[float] = None
    turnover: Optional[float] = None


class FactorDatabase:
    """因子数据库
    
    提供因子的增删改查、元数据管理、版本控制和血缘追踪。
    
    Example:
        db = FactorDatabase("./factor_db")
        
        # 添加因子
        db.add_factor("momentum_20d", momentum_data, metadata={
            "category": "momentum",
            "frequency": "daily",
            "author": "quant_team"
        })
        
        # 查询因子
        factors = db.query(category="momentum", ic_ir_min=0.03)
        
        # 获取因子数据
        data = db.get_factor("momentum_20d")
        
        # 血缘追踪
        lineage = db.get_lineage("momentum_20d")
    """
    
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self._factors: dict[str, pd.DataFrame] = {}
        self._metadata: dict[str, FactorMetadata] = {}
        
        self._load_existing_factors()
    
    def _load_existing_factors(self):
        """加载已有因子"""
        meta_path = self.db_path / "metadata.json"
        if meta_path.exists():
            import json
            with open(meta_path, 'r') as f:
                data = json.load(f)
            for name, meta_dict in data.items():
                self._metadata[name] = FactorMetadata(**meta_dict)
    
    def add_factor(
        self,
        name: str,
        data: pd.DataFrame,
        metadata: Optional[dict] = None,
        overwrite: bool = False
    ) -> None:
        """添加因子
        
        Args:
            name: 因子名称
            data: 因子数据 (dates x stocks)
            metadata: 元数据
            overwrite: 是否覆盖已有因子
        """
        if name in self._factors and not overwrite:
            raise ValueError(f"因子 {name} 已存在，设置 overwrite=True 覆盖")
        
        self._factors[name] = data.copy()
        
        # 保存数据
        data_path = self.db_path / f"{name}.parquet"
        data.to_parquet(data_path)
        
        # 更新元数据
        meta = FactorMetadata(name=name, **(metadata or {}))
        meta.updated_at = datetime.now()
        self._metadata[name] = meta
        
        self._save_metadata()
    
    def get_factor(self, name: str) -> pd.DataFrame:
        """获取因子数据"""
        if name in self._factors:
            return self._factors[name]
        
        # 从磁盘加载
        data_path = self.db_path / f"{name}.parquet"
        if data_path.exists():
            data = pd.read_parquet(data_path)
            self._factors[name] = data
            return data
        
        raise KeyError(f"因子 {name} 不存在")
    
    def query(
        self,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        ic_ir_min: Optional[float] = None,
        author: Optional[str] = None,
    ) -> list[str]:
        """查询因子
        
        Args:
            category: 因子类别过滤
            tags: 标签过滤
            ic_ir_min: IC_IR最小值过滤
            author: 作者过滤
            
        Returns:
            符合条件的因子名称列表
        """
        results = []
        
        for name, meta in self._metadata.items():
            if category and meta.category != category:
                continue
            if tags and not any(t in meta.tags for t in tags):
                continue
            if ic_ir_min and (meta.ir is None or meta.ir < ic_ir_min):
                continue
            if author and meta.author != author:
                continue
            
            results.append(name)
        
        return results
    
    def get_lineage(self, name: str) -> list[str]:
        """获取因子血缘（父因子列表）"""
        if name not in self._metadata:
            return []
        return self._metadata[name].parent_factors
    
    def update_stats(self, name: str, **stats) -> None:
        """更新因子统计指标"""
        if name not in self._metadata:
            raise KeyError(f"因子 {name} 不存在")
        
        meta = self._metadata[name]
        for key, value in stats.items():
            if hasattr(meta, key):
                setattr(meta, key, value)
        
        meta.updated_at = datetime.now()
        self._save_metadata()
    
    def list_factors(self) -> list[str]:
        """列出所有因子"""
        return list(self._metadata.keys())
    
    def delete_factor(self, name: str) -> None:
        """删除因子"""
        if name in self._factors:
            del self._factors[name]
        if name in self._metadata:
            del self._metadata[name]
        
        # 删除文件
        data_path = self.db_path / f"{name}.parquet"
        if data_path.exists():
            data_path.unlink()
        
        self._save_metadata()
    
    def _save_metadata(self):
        """保存元数据"""
        import json
        meta_path = self.db_path / "metadata.json"
        data = {
            name: {
                'name': meta.name,
                'category': meta.category,
                'frequency': meta.frequency,
                'author': meta.author,
                'version': meta.version,
                'created_at': meta.created_at.isoformat(),
                'updated_at': meta.updated_at.isoformat(),
                'description': meta.description,
                'tags': meta.tags,
                'parent_factors': meta.parent_factors,
                'ic_mean': meta.ic_mean,
                'ic_std': meta.ic_std,
                'ir': meta.ir,
                'half_life': meta.half_life,
                'turnover': meta.turnover,
            }
            for name, meta in self._metadata.items()
        }
        with open(meta_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
```

#### 2.2.2 批量回测引擎 (BatchBacktestEngine)

```python
# core/batch_engine.py

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from core.config import BacktestConfig
from core.engine_v2 import BacktestEngineV2
from core.factor_db import FactorDatabase
from core.interfaces import IDataManager

logger = logging.getLogger(__name__)


class BatchBacktestEngine:
    """批量回测引擎
    
    支持对多个因子/策略进行批量回测，自动聚合结果。
    
    Example:
        # 方式1: 批量回测因子库中的所有因子
        batch = BatchBacktestEngine(config, factor_db)
        results = batch.run_all_factors()
        
        # 方式2: 批量回测指定因子列表
        results = batch.run_factors(["momentum_20d", "value_pe", "quality_roe"])
        
        # 方式3: 批量回测不同参数组合
        param_grid = {
            "lookback": [5, 10, 20, 60],
            "top_n": [10, 20, 50],
        }
        results = batch.run_param_grid(param_grid)
        
        # 获取对比分析
        comparison = batch.compare_results(results)
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        factor_db: Optional[FactorDatabase] = None,
        data_manager: Optional[IDataManager] = None,
        max_workers: int = 4,
    ):
        """初始化批量回测引擎
        
        Args:
            config: 基础回测配置
            factor_db: 因子数据库（可选）
            data_manager: 数据管理器（可选，共享数据避免重复加载）
            max_workers: 并行 worker 数量
        """
        self.base_config = config
        self.factor_db = factor_db
        self.shared_dm = data_manager
        self.max_workers = max_workers
        
        self.results: dict[str, Any] = {}
        
        logger.info(f"批量回测引擎初始化完成 (max_workers={max_workers})")
    
    def run_all_factors(self, **engine_kwargs) -> dict[str, Any]:
        """回测因子库中的所有因子
        
        Args:
            **engine_kwargs: 传递给 BacktestEngineV2 的额外参数
            
        Returns:
            {因子名: 回测结果}
        """
        if self.factor_db is None:
            raise ValueError("未提供因子数据库")
        
        factor_names = self.factor_db.list_factors()
        logger.info(f"开始批量回测 {len(factor_names)} 个因子")
        
        return self.run_factors(factor_names, **engine_kwargs)
    
    def run_factors(
        self,
        factor_names: list[str],
        **engine_kwargs
    ) -> dict[str, Any]:
        """批量回测指定因子
        
        Args:
            factor_names: 因子名称列表
            **engine_kwargs: 传递给 BacktestEngineV2 的额外参数
            
        Returns:
            {因子名: 回测结果}
        """
        results = {}
        
        # 串行执行（数据共享，避免多进程问题）
        for name in factor_names:
            try:
                logger.info(f"回测因子: {name}")
                result = self._run_single_factor(name, **engine_kwargs)
                results[name] = result
            except Exception as e:
                logger.error(f"因子 {name} 回测失败: {e}")
                results[name] = {"error": str(e)}
        
        self.results.update(results)
        return results
    
    def _run_single_factor(self, factor_name: str, **engine_kwargs) -> Any:
        """回测单个因子"""
        # 获取因子数据
        factor_data = self.factor_db.get_factor(factor_name)
        
        # 创建配置副本
        config = self._create_factor_config(factor_name, factor_data)
        
        # 创建引擎
        if self.shared_dm:
            engine = BacktestEngineV2(
                config,
                data_manager=self.shared_dm,
                **engine_kwargs
            )
        else:
            engine = BacktestEngineV2(config, **engine_kwargs)
        
        # 运行回测
        engine.setup()
        return engine.run()
    
    def _create_factor_config(
        self,
        factor_name: str,
        factor_data: pd.DataFrame
    ) -> BacktestConfig:
        """为单个因子创建配置"""
        # 深拷贝基础配置
        import copy
        config = copy.deepcopy(self.base_config)
        
        # 设置因子特定输出目录
        config.output_dir = config.output_dir / factor_name
        config.output_dir.mkdir(parents=True, exist_ok=True)
        
        return config
    
    def run_param_grid(
        self,
        param_grid: dict[str, list],
        **engine_kwargs
    ) -> dict[str, Any]:
        """参数网格搜索回测
        
        Args:
            param_grid: 参数网格 {参数名: [参数值列表]}
            **engine_kwargs: 额外参数
            
        Returns:
            {参数组合标识: 回测结果}
        """
        from itertools import product
        
        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        results = {}
        
        for values in product(*param_values):
            param_dict = dict(zip(param_names, values))
            param_id = "_".join(f"{k}={v}" for k, v in param_dict.items())
            
            try:
                logger.info(f"回测参数组合: {param_id}")
                result = self._run_with_params(param_dict, **engine_kwargs)
                results[param_id] = result
            except Exception as e:
                logger.error(f"参数组合 {param_id} 回测失败: {e}")
                results[param_id] = {"error": str(e)}
        
        self.results.update(results)
        return results
    
    def _run_with_params(self, params: dict, **engine_kwargs) -> Any:
        """使用指定参数运行回测"""
        import copy
        config = copy.deepcopy(self.base_config)
        
        # 应用参数
        for key, value in params.items():
            if hasattr(config.optimizer, key):
                setattr(config.optimizer, key, value)
            elif hasattr(config.rebalance, key):
                setattr(config.rebalance, key, value)
            elif hasattr(config, key):
                setattr(config, key, value)
        
        if self.shared_dm:
            engine = BacktestEngineV2(config, data_manager=self.shared_dm, **engine_kwargs)
        else:
            engine = BacktestEngineV2(config, **engine_kwargs)
        
        engine.setup()
        return engine.run()
    
    def compare_results(self, results: Optional[dict[str, Any]] = None) -> pd.DataFrame:
        """对比回测结果
        
        Args:
            results: 回测结果字典（默认使用self.results）
            
        Returns:
            对比DataFrame
        """
        if results is None:
            results = self.results
        
        comparison_data = []
        
        for name, result in results.items():
            if "error" in result:
                continue
            
            metrics = result.get('performance_metrics', {})
            row = {
                'name': name,
                'total_return': metrics.get('total_return', 0),
                'annual_return': metrics.get('annual_return', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'volatility': metrics.get('volatility', 0),
                'win_rate': metrics.get('win_rate', 0),
                'trade_count': metrics.get('trade_count', 0),
            }
            comparison_data.append(row)
        
        return pd.DataFrame(comparison_data)
    
    def get_best_factor(
        self,
        metric: str = "sharpe_ratio",
        results: Optional[dict[str, Any]] = None
    ) -> tuple[str, float]:
        """获取最佳因子
        
        Args:
            metric: 评估指标
            results: 回测结果（默认self.results）
            
        Returns:
            (最佳因子名, 指标值)
        """
        df = self.compare_results(results)
        if df.empty:
            return "", 0.0
        
        best_idx = df[metric].idxmax()
        return df.loc[best_idx, 'name'], df.loc[best_idx, metric]
```

#### 2.2.3 策略评估器 (StrategyEvaluator)

```python
# core/strategy_evaluator.py

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class FactorStatsCalculator:
    """因子统计量计算器
    
    计算因子的IC、IR、半衰期、换手率等统计指标。
    """
    
    def __init__(self, factor_data: pd.DataFrame, returns_data: pd.DataFrame):
        """初始化
        
        Args:
            factor_data: 因子数据 (dates x stocks)
            returns_data: 未来收益数据 (dates x stocks)
        """
        self.factor = factor_data
        self.returns = returns_data
        
        # 对齐数据
        common_dates = self.factor.index.intersection(self.returns.index)
        common_stocks = self.factor.columns.intersection(self.returns.columns)
        
        self.factor = self.factor.loc[common_dates, common_stocks]
        self.returns = self.returns.loc[common_dates, common_stocks]
    
    def calculate_ic(self, method: str = "spearman") -> pd.Series:
        """计算信息系数 (IC)
        
        Args:
            method: 相关系数方法 ("spearman" | "pearson")
            
        Returns:
            每日IC序列
        """
        ic_values = []
        
        for date in self.factor.index:
            f = self.factor.loc[date].dropna()
            r = self.returns.loc[date].dropna()
            
            common = f.index.intersection(r.index)
            if len(common) < 10:
                ic_values.append(np.nan)
                continue
            
            f_aligned = f[common]
            r_aligned = r[common]
            
            if method == "spearman":
                ic, _ = stats.spearmanr(f_aligned, r_aligned)
            else:
                ic, _ = stats.pearsonr(f_aligned, r_aligned)
            
            ic_values.append(ic)
        
        return pd.Series(ic_values, index=self.factor.index, name="IC")
    
    def calculate_ic_stats(self, ic_series: pd.Series) -> dict[str, float]:
        """计算IC统计量"""
        ic_clean = ic_series.dropna()
        
        if len(ic_clean) == 0:
            return {"ic_mean": 0, "ic_std": 0, "ir": 0, "ic_ratio": 0}
        
        ic_mean = ic_clean.mean()
        ic_std = ic_clean.std()
        ir = ic_mean / ic_std if ic_std > 0 else 0
        ic_ratio = (ic_clean > 0).sum() / len(ic_clean)
        
        return {
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "ir": ir,
            "ic_ratio": ic_ratio,
            "ic_tstat": ic_mean / (ic_std / np.sqrt(len(ic_clean))) if ic_std > 0 else 0,
        }
    
    def calculate_half_life(self, ic_series: pd.Series) -> float:
        """计算IC半衰期"""
        ic_clean = ic_series.dropna()
        if len(ic_clean) < 10:
            return np.nan
        
        # 自回归系数
        ic_lag = ic_clean.shift(1).dropna()
        ic_curr = ic_clean.iloc[1:]
        
        if len(ic_lag) < 5:
            return np.nan
        
        try:
            rho = np.corrcoef(ic_lag, ic_curr)[0, 1]
            if rho >= 1 or rho <= 0:
                return np.nan
            half_life = -np.log(2) / np.log(rho)
            return half_life
        except:
            return np.nan
    
    def calculate_turnover(
        self,
        factor_data: pd.DataFrame,
        top_n: int = 50
    ) -> pd.Series:
        """计算因子换手率"""
        turnovers = []
        
        for i in range(1, len(factor_data)):
            prev_top = set(factor_data.iloc[i-1].nlargest(top_n).index)
            curr_top = set(factor_data.iloc[i].nlargest(top_n).index)
            
            if len(prev_top) == 0:
                turnover = 0
            else:
                turnover = len(prev_top - curr_top) / len(prev_top)
            
            turnovers.append(turnover)
        
        return pd.Series(turnovers, index=factor_data.index[1:], name="turnover")
    
    def calculate_all_stats(self) -> dict[str, Any]:
        """计算所有统计量"""
        ic_series = self.calculate_ic()
        ic_stats = self.calculate_ic_stats(ic_series)
        half_life = self.calculate_half_life(ic_series)
        turnover = self.calculate_turnover(self.factor)
        
        return {
            **ic_stats,
            "half_life": half_life,
            "turnover_mean": turnover.mean(),
            "turnover_std": turnover.std(),
            "ic_series": ic_series,
            "turnover_series": turnover,
        }


class StrategyEvaluator:
    """策略评估器
    
    综合评估策略/因子的绩效表现。
    """
    
    def __init__(self, backtest_results: dict[str, Any]):
        """初始化
        
        Args:
            backtest_results: 回测结果字典 {name: result}
        """
        self.results = backtest_results
    
    def rank_strategies(
        self,
        metrics: list[str] = ["sharpe_ratio", "total_return", "max_drawdown"],
        weights: Optional[list[float]] = None
    ) -> pd.DataFrame:
        """策略排名
        
        Args:
            metrics: 评估指标列表
            weights: 指标权重（默认等权）
            
        Returns:
            排名DataFrame
        """
        if weights is None:
            weights = [1.0 / len(metrics)] * len(metrics)
        
        data = []
        for name, result in self.results.items():
            if "error" in result:
                continue
            
            perf = result.get('performance_metrics', {})
            row = {'name': name}
            
            score = 0
            for metric, weight in zip(metrics, weights):
                value = perf.get(metric, 0)
                # 对回撤进行反向处理
                if 'drawdown' in metric:
                    value = -value
                row[metric] = value
                score += value * weight
            
            row['score'] = score
            data.append(row)
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('score', ascending=False)
        
        return df
    
    def generate_evaluation_report(self) -> dict[str, Any]:
        """生成评估报告"""
        ranking = self.rank_strategies()
        
        return {
            'ranking': ranking,
            'best_strategy': ranking.iloc[0]['name'] if not ranking.empty else None,
            'total_strategies': len(self.results),
            'successful_strategies': len([r for r in self.results.values() if 'error' not in r]),
        }
```

#### 2.2.4 下单策略评估器 (OrderStrategyEvaluator)

```python
# core/order_strategy.py

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MarketImpactModel:
    """市场冲击模型"""
    
    permanent_impact_coeff: float = 0.1  # 永久冲击系数
    temporary_impact_coeff: float = 0.05  # 临时冲击系数
    decay_rate: float = 0.5  # 冲击衰减率
    
    def calculate_impact(
        self,
        order_size: int,
        avg_daily_volume: float,
        volatility: float
    ) -> tuple[float, float]:
        """计算市场冲击
        
        Returns:
            (永久冲击, 临时冲击)
        """
        participation_rate = order_size / avg_daily_volume if avg_daily_volume > 0 else 0
        
        permanent = self.permanent_impact_coeff * volatility * participation_rate
        temporary = self.temporary_impact_coeff * volatility * (participation_rate ** 0.6)
        
        return permanent, temporary


class BaseOrderStrategy(ABC):
    """下单策略基类"""
    
    def __init__(self, impact_model: Optional[MarketImpactModel] = None):
        self.impact_model = impact_model or MarketImpactModel()
    
    @abstractmethod
    def execute(
        self,
        stock: str,
        side: Any,
        total_quantity: int,
        date: pd.Timestamp,
        market_data: dict[str, Any]
    ) -> list[dict]:
        """执行订单
        
        Returns:
            分笔交易列表 [{stock, side, quantity, price, timestamp}, ...]
        """
        ...


class MarketOrderStrategy(BaseOrderStrategy):
    """市价单策略 - 立即全部成交"""
    
    def execute(self, stock, side, total_quantity, date, market_data):
        price = market_data.get('open_price', 0)
        
        # 计算市场冲击
        adv = market_data.get('avg_daily_volume', total_quantity * 10)
        vol = market_data.get('volatility', 0.02)
        perm, temp = self.impact_model.calculate_impact(total_quantity, adv, vol)
        
        executed_price = price * (1 + perm + temp)
        
        return [{
            'stock': stock,
            'side': side,
            'quantity': total_quantity,
            'price': executed_price,
            'timestamp': date,
        }]


class TWAPStrategy(BaseOrderStrategy):
    """TWAP策略 - 时间加权平均价格"""
    
    def __init__(self, num_slices: int = 10, impact_model=None):
        super().__init__(impact_model)
        self.num_slices = num_slices
    
    def execute(self, stock, side, total_quantity, date, market_data):
        slice_qty = total_quantity // self.num_slices
        remainder = total_quantity % self.num_slices
        
        trades = []
        base_price = market_data.get('open_price', 0)
        
        for i in range(self.num_slices):
            qty = slice_qty + (1 if i < remainder else 0)
            if qty == 0:
                continue
            
            # 模拟价格漂移
            price_drift = np.random.normal(0, 0.001)
            slice_price = base_price * (1 + price_drift)
            
            trades.append({
                'stock': stock,
                'side': side,
                'quantity': qty,
                'price': slice_price,
                'timestamp': pd.Timestamp(date) + pd.Timedelta(minutes=i * 30),
            })
        
        return trades


class VWAPStrategy(BaseOrderStrategy):
    """VWAP策略 - 成交量加权平均价格"""
    
    def __init__(self, window_minutes: int = 30, impact_model=None):
        super().__init__(impact_model)
        self.window_minutes = window_minutes
    
    def execute(self, stock, side, total_quantity, date, market_data):
        # 模拟日内成交量分布
        volume_profile = market_data.get('volume_profile', [0.1] * 10)
        
        trades = []
        base_price = market_data.get('open_price', 0)
        
        for i, vol_pct in enumerate(volume_profile):
            qty = int(total_quantity * vol_pct)
            if qty == 0:
                continue
            
            # VWAP价格
            vwap_price = market_data.get('vwap', base_price)
            
            trades.append({
                'stock': stock,
                'side': side,
                'quantity': qty,
                'price': vwap_price,
                'timestamp': pd.Timestamp(date) + pd.Timedelta(minutes=i * self.window_minutes),
            })
        
        return trades


class IcebergStrategy(BaseOrderStrategy):
    """冰山订单策略 - 隐藏大单"""
    
    def __init__(self, display_qty: int = 100, impact_model=None):
        super().__init__(impact_model)
        self.display_qty = display_qty
    
    def execute(self, stock, side, total_quantity, date, market_data):
        trades = []
        remaining = total_quantity
        base_price = market_data.get('open_price', 0)
        
        while remaining > 0:
            qty = min(self.display_qty, remaining)
            
            # 每次下单后价格可能反弹
            price = base_price * (1 + np.random.normal(0, 0.0005))
            
            trades.append({
                'stock': stock,
                'side': side,
                'quantity': qty,
                'price': price,
                'timestamp': pd.Timestamp(date) + pd.Timedelta(minutes=len(trades) * 5),
            })
            
            remaining -= qty
        
        return trades


class OrderStrategyEvaluator:
    """下单策略评估器"""
    
    def __init__(self):
        self.results: dict[str, list[dict]] = {}
    
    def evaluate_strategy(
        self,
        strategy: BaseOrderStrategy,
        test_orders: list[dict],
        market_data: dict[str, Any]
    ) -> dict[str, Any]:
        """评估下单策略
        
        Args:
            strategy: 下单策略
            test_orders: 测试订单列表
            market_data: 市场数据
            
        Returns:
            评估结果
        """
        all_trades = []
        
        for order in test_orders:
            trades = strategy.execute(
                order['stock'],
                order['side'],
                order['quantity'],
                order['date'],
                market_data
            )
            all_trades.extend(trades)
        
        # 计算评估指标
        total_quantity = sum(t['quantity'] for t in all_trades)
        avg_price = np.average(
            [t['price'] for t in all_trades],
            weights=[t['quantity'] for t in all_trades]
        )
        
        # 价格冲击
        benchmark_price = market_data.get('open_price', avg_price)
        price_impact = (avg_price - benchmark_price) / benchmark_price
        
        # 执行时间
        if all_trades:
            first_time = all_trades[0]['timestamp']
            last_time = all_trades[-1]['timestamp']
            execution_time = (last_time - first_time).total_seconds() / 60  # 分钟
        else:
            execution_time = 0
        
        return {
            'strategy_name': strategy.__class__.__name__,
            'total_trades': len(all_trades),
            'total_quantity': total_quantity,
            'avg_price': avg_price,
            'benchmark_price': benchmark_price,
            'price_impact_bps': price_impact * 10000,  # 基点
            'execution_time_min': execution_time,
            'trades': all_trades,
        }
    
    def compare_strategies(
        self,
        strategies: dict[str, BaseOrderStrategy],
        test_orders: list[dict],
        market_data: dict[str, Any]
    ) -> pd.DataFrame:
        """对比多个下单策略"""
        results = []
        
        for name, strategy in strategies.items():
            result = self.evaluate_strategy(strategy, test_orders, market_data)
            results.append({
                'strategy': name,
                'price_impact_bps': result['price_impact_bps'],
                'execution_time_min': result['execution_time_min'],
                'total_trades': result['total_trades'],
            })
        
        return pd.DataFrame(results)
```

---

## 3. 使用示例

### 3.1 因子批量回测

```python
from core.config import BacktestConfig
from core.factor_db import FactorDatabase
from core.batch_engine import BatchBacktestEngine

# 初始化
config = BacktestConfig(
    data_dir="./data",
    output_dir="./output/batch",
    initial_capital=1_000_000,
)

factor_db = FactorDatabase("./factor_db")

# 批量回测
batch = BatchBacktestEngine(config, factor_db=factor_db)
results = batch.run_all_factors()

# 对比分析
comparison = batch.compare_results()
print(comparison.sort_values('sharpe_ratio', ascending=False))

# 最佳因子
best_name, best_sharpe = batch.get_best_factor("sharpe_ratio")
print(f"最佳因子: {best_name}, Sharpe: {best_sharpe:.2f}")
```

### 3.2 因子库动态维护

```python
from core.factor_db import FactorDatabase

# 初始化因子库
db = FactorDatabase("./factor_db")

# 添加因子
db.add_factor(
    "momentum_20d",
    momentum_data,
    metadata={
        "category": "momentum",
        "frequency": "daily",
        "author": "quant_team",
        "tags": ["technical", "trend"],
        "parent_factors": ["close_price"],
    }
)

# 查询高质量因子
good_factors = db.query(
    category="momentum",
    ic_ir_min=0.03,
    tags=["technical"]
)

# 更新统计指标
db.update_stats("momentum_20d", ic_mean=0.05, ir=0.8, half_life=15)

# 血缘追踪
lineage = db.get_lineage("momentum_20d")
print(f"父因子: {lineage}")
```

### 3.3 下单策略评估

```python
from core.order_strategy import (
    MarketOrderStrategy,
    TWAPStrategy,
    VWAPStrategy,
    IcebergStrategy,
    OrderStrategyEvaluator,
)

# 测试订单
test_orders = [
    {"stock": "AAPL", "side": "BUY", "quantity": 10000, "date": pd.Timestamp("2024-01-01")},
    {"stock": "GOOGL", "side": "SELL", "quantity": 5000, "date": pd.Timestamp("2024-01-01")},
]

# 市场数据
market_data = {
    "open_price": 150.0,
    "avg_daily_volume": 1000000,
    "volatility": 0.02,
    "volume_profile": [0.15, 0.12, 0.10, 0.08, 0.08, 0.10, 0.12, 0.15, 0.05, 0.05],
}

# 评估策略
evaluator = OrderStrategyEvaluator()
strategies = {
    "market": MarketOrderStrategy(),
    "twap": TWAPStrategy(num_slices=10),
    "vwap": VWAPStrategy(window_minutes=30),
    "iceberg": IcebergStrategy(display_qty=500),
}

comparison = evaluator.compare_strategies(strategies, test_orders, market_data)
print(comparison)
```

---

## 4. 实施路线图

| 阶段 | 模块 | 优先级 | 工作量 | 依赖 |
|------|------|--------|--------|------|
| **P0** | FactorDatabase | 高 | 中 | 无 |
| **P0** | BatchBacktestEngine | 高 | 中 | FactorDatabase |
| **P1** | FactorStatsCalculator | 中 | 低 | 无 |
| **P1** | StrategyEvaluator | 中 | 低 | 无 |
| **P2** | BaseOrderStrategy | 中 | 中 | 无 |
| **P2** | OrderStrategyEvaluator | 中 | 低 | BaseOrderStrategy |
| **P3** | 集成测试 | 高 | 中 | 所有模块 |

---

## 5. 总结

本次升级将回测引擎从单一策略回测扩展为支持：

1. **因子批量回测** - 自动对比数百个因子的绩效
2. **因子库动态维护** - 完整的因子生命周期管理
3. **下单策略评估** - TWAP/VWAP/冰山订单等策略对比

核心设计原则：
- **插拔式架构** - 所有模块通过接口交互
- **数据共享** - 批量回测时共享DataManager避免重复加载
- **结果聚合** - 自动计算IC/IR/半衰期等统计量
- **配置驱动** - 通过配置而非代码控制行为
