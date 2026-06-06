"""批量回测引擎

支持对多个因子/策略进行批量回测，自动聚合结果。
"""

from __future__ import annotations

import copy
import logging
from itertools import product
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.config import BacktestConfig
from core.engine_v2 import BacktestEngineV2
from core.interfaces import IDataManager
from factor_library.database import FactorDatabase

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
