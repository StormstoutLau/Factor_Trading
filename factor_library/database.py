"""因子数据库

提供因子的增删改查、元数据管理、版本控制和血缘追踪。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FactorMetadata:
    """因子元数据"""
    name: str
    category: str
    frequency: str
    author: str
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parent_factors: list[str] = field(default_factory=list)
    
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
            with open(meta_path, 'r', encoding='utf-8') as f:
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
        
        # 保存数据（优先parquet，降级csv）
        data_path = self.db_path / f"{name}.parquet"
        csv_path = self.db_path / f"{name}.csv"
        try:
            data.to_parquet(data_path)
        except ImportError:
            data.to_csv(csv_path)
        
        # 更新元数据
        meta = FactorMetadata(name=name, **(metadata or {}))
        meta.updated_at = datetime.now()
        self._metadata[name] = meta
        
        self._save_metadata()
        logger.info(f"因子 {name} 已添加/更新")
    
    def get_factor(self, name: str) -> pd.DataFrame:
        """获取因子数据"""
        if name in self._factors:
            return self._factors[name]
        
        # 从磁盘加载
        data_path = self.db_path / f"{name}.parquet"
        csv_path = self.db_path / f"{name}.csv"
        if data_path.exists():
            data = pd.read_parquet(data_path)
            self._factors[name] = data
            return data
        elif csv_path.exists():
            data = pd.read_csv(csv_path, index_col=0, parse_dates=True)
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
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
