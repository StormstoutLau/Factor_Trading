"""因子统计量计算器

计算因子的IC、IR、半衰期、换手率等统计指标。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class FactorStatsCalculator:
    """因子统计量计算器
    
    计算因子的IC、IR、半衰期、换手率等统计指标。
    
    Example:
        calc = FactorStatsCalculator(factor_data, returns_data)
        
        # 计算IC序列
        ic_series = calc.calculate_ic()
        
        # 计算所有统计量
        stats = calc.calculate_all_stats()
        print(f"IC均值: {stats['ic_mean']:.4f}")
        print(f"IR: {stats['ir']:.4f}")
        print(f"半衰期: {stats['half_life']:.1f}天")
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
        """计算IC统计量
        
        Args:
            ic_series: IC序列
            
        Returns:
            IC统计量字典
        """
        ic_clean = ic_series.dropna()
        
        if len(ic_clean) == 0:
            return {"ic_mean": 0, "ic_std": 0, "ir": 0, "ic_ratio": 0, "ic_tstat": 0}
        
        ic_mean = ic_clean.mean()
        ic_std = ic_clean.std()
        ir = ic_mean / ic_std if ic_std > 0 else 0
        ic_ratio = (ic_clean > 0).sum() / len(ic_clean)
        ic_tstat = ic_mean / (ic_std / np.sqrt(len(ic_clean))) if ic_std > 0 else 0
        
        return {
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "ir": ir,
            "ic_ratio": ic_ratio,
            "ic_tstat": ic_tstat,
        }
    
    def calculate_half_life(self, ic_series: pd.Series) -> float:
        """计算IC半衰期
        
        Args:
            ic_series: IC序列
            
        Returns:
            半衰期（天数）
        """
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
        except Exception:
            return np.nan
    
    def calculate_turnover(
        self,
        factor_data: Optional[pd.DataFrame] = None,
        top_n: int = 50
    ) -> pd.Series:
        """计算因子换手率
        
        Args:
            factor_data: 因子数据（默认使用self.factor）
            top_n: 头部股票数量
            
        Returns:
            换手率序列
        """
        if factor_data is None:
            factor_data = self.factor
        
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
        """计算所有统计量
        
        Returns:
            包含所有统计量的字典
        """
        ic_series = self.calculate_ic()
        ic_stats = self.calculate_ic_stats(ic_series)
        half_life = self.calculate_half_life(ic_series)
        turnover = self.calculate_turnover()
        
        return {
            **ic_stats,
            "half_life": half_life,
            "turnover_mean": turnover.mean(),
            "turnover_std": turnover.std(),
            "ic_series": ic_series,
            "turnover_series": turnover,
        }
