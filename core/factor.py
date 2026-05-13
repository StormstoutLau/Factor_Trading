"""因子处理管道模块 - 基于Backtest_Opus_2.0架构

提供完整的因子预处理和合成功能：
- 去极值处理（MAD、百分位、标准差）
- 缺失值填充
- 行业市值中性化
- 标准化处理
- 多因子合成
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

from config import BacktestConfig, FactorConfig
from data import DataManager

logger = logging.getLogger(__name__)


class FactorPipeline:
    """因子处理管道
    
    负责单个因子的预处理，包括去极值、填充、中性化、标准化等步骤。
    """
    
    def __init__(self, data_manager: DataManager, config: FactorConfig):
        """初始化因子处理管道
        
        Args:
            data_manager: 数据管理器
            config: 因子配置
        """
        self.dm = data_manager
        self.cfg = config
        logger.info("因子处理管道初始化完成")
    
    def process(self, raw_factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """处理原始因子数据
        
        Args:
            raw_factor: 原始因子数据
            tradable_mask: 可交易股票掩码
            
        Returns:
            处理后的因子数据
        """
        logger.debug(f"开始处理因子数据: {raw_factor.shape}")
        
        factor = raw_factor.copy()
        
        # 0. 因子反转（处理负向因子）
        if self.cfg.reverse_factor:
            factor = self._reverse(factor)
            logger.info("因子已反转（负向因子处理）")
        
        # 1. 去极值处理
        if self.cfg.winsorize_method != "none":
            factor = self._winsorize(factor)
        
        # 2. 缺失值填充
        if self.cfg.fill_method != "none":
            factor = self._fill_missing(factor, tradable_mask)
        
        # 3. 中性化处理
        if self.cfg.neutralize:
            factor = self._neutralize(factor, tradable_mask)
        
        # 4. 标准化处理
        if self.cfg.standardize_method != "none":
            factor = self._standardize(factor, tradable_mask)
        
        logger.debug(f"因子处理完成: {factor.shape}")
        return factor
    
    def _winsorize(self, factor: pd.DataFrame) -> pd.DataFrame:
        """去极值处理
        
        Args:
            factor: 原始因子数据
            
        Returns:
            去极值后的因子数据
        """
        if self.cfg.winsorize_method == "none":
            logger.info("跳过去极值处理")
            return factor
        elif self.cfg.winsorize_method == "mad":
            return self._winsorize_mad(factor)
        elif self.cfg.winsorize_method == "percentile":
            return self._winsorize_percentile(factor)
        elif self.cfg.winsorize_method == "sigma":
            return self._winsorize_sigma(factor)
        else:
            logger.warning(f"未知的去极值方法: {self.cfg.winsorize_method}")
            return factor
    
    def _winsorize_mad(self, factor: pd.DataFrame) -> pd.DataFrame:
        """MAD去极值法 - 软截断版本（向量化优化）
        
        使用平滑过渡代替硬截断，在边界附近产生渐变效果。
        
        Args:
            factor: 因子数据
            
        Returns:
            去极值后的因子数据
        """
        def winsorize_row(row):
            row_clean = row.dropna()
            if len(row_clean) == 0:
                return row
            
            median = row_clean.median()
            mad = np.median(np.abs(row_clean - median))
            
            if mad == 0:
                return row
            
            # 计算上下界
            lower = median - self.cfg.winsorize_n * mad
            upper = median + self.cfg.winsorize_n * mad
            
            # 软截断
            scale = (upper - lower) / 2
            center = (upper + lower) / 2
            
            if scale > 0:
                normalized = (row - center) / scale
                compressed = np.tanh(normalized)
                return center + compressed * scale
            return row
        
        return factor.apply(winsorize_row, axis=1)
    
    def _winsorize_percentile(self, factor: pd.DataFrame) -> pd.DataFrame:
        """百分位去极值法 - 软截断版本（向量化优化）
        
        Args:
            factor: 因子数据
            
        Returns:
            去极值后的因子数据
        """
        lower_pct, upper_pct = self.cfg.winsorize_pct
        
        def winsorize_row(row):
            row_clean = row.dropna()
            if len(row_clean) == 0:
                return row
            
            lower = row_clean.quantile(lower_pct)
            upper = row_clean.quantile(upper_pct)
            
            scale = (upper - lower) / 2
            center = (upper + lower) / 2
            
            if scale > 0:
                normalized = (row - center) / scale
                compressed = np.tanh(normalized)
                return center + compressed * scale
            return row
        
        return factor.apply(winsorize_row, axis=1)
    
    def _winsorize_sigma(self, factor: pd.DataFrame) -> pd.DataFrame:
        """标准差去极值法 - 软截断版本（向量化优化）
        
        Args:
            factor: 因子数据
            
        Returns:
            去极值后的因子数据
        """
        def winsorize_row(row):
            row_clean = row.dropna()
            if len(row_clean) == 0:
                return row
            
            mean = row_clean.mean()
            std = row_clean.std()
            
            if std == 0:
                return row
            
            # 计算上下界
            lower = mean - self.cfg.winsorize_n * std
            upper = mean + self.cfg.winsorize_n * std
            
            # 软截断
            scale = (upper - lower) / 2
            center = (upper + lower) / 2
            
            normalized = (row - center) / scale
            compressed = np.tanh(normalized)
            return center + compressed * scale
        
        return factor.apply(winsorize_row, axis=1)
    
    def _reverse(self, factor: pd.DataFrame) -> pd.DataFrame:
        """因子反转处理
        
        对于负向因子（如换手率因子，高值表示风险），反转后高值变为低值，
        使得因子方向统一：高因子值 = 好股票。
        
        反转公式：factor' = -factor
        
        Args:
            factor: 原始因子数据
            
        Returns:
            反转后的因子数据
        """
        return -factor
    
    def _fill_missing(self, factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame | pd.Series] = None) -> pd.DataFrame:
        """缺失值填充 - 向量化优化
        
        Args:
            factor: 因子数据
            tradable_mask: 可交易股票掩码 (DataFrame或Series)
            
        Returns:
            填充后的因子数据
        """
        if tradable_mask is not None:
            # 【修复E4】统一处理DataFrame和Series类型的tradable_mask
            if isinstance(tradable_mask, pd.DataFrame):
                # DataFrame掩码：直接使用（index=dates, columns=stock_codes）
                mask_df = tradable_mask.reindex(index=factor.index, columns=factor.columns).fillna(False)
            elif isinstance(tradable_mask, pd.Series):
                # Series掩码：转换为与factor同形的DataFrame
                mask_df = pd.DataFrame(
                    np.tile(tradable_mask.reindex(factor.columns).values, (len(factor.index), 1)),
                    index=factor.index,
                    columns=factor.columns,
                    dtype=bool
                )
            else:
                mask_df = None
            
            # 根据填充方法计算填充值（只对可交易股票计算）
            if self.cfg.fill_method == "none":
                return factor  # 不填充
            
            if self.cfg.fill_method == "median":
                fill_values = factor.where(mask_df).median(axis=1)
            elif self.cfg.fill_method == "mean":
                fill_values = factor.where(mask_df).mean(axis=1)
            elif self.cfg.fill_method == "zero":
                fill_values = 0
            else:
                fill_values = factor.where(mask_df).median(axis=1)
            
            # 只对可交易且为NaN的位置填充
            result = factor.copy()
            for col in factor.columns:
                if mask_df is not None:
                    mask = mask_df[col] & factor[col].isna()
                elif isinstance(tradable_mask, pd.Series) and col in tradable_mask.index:
                    mask = tradable_mask[col] & factor[col].isna()
                else:
                    continue
                if isinstance(fill_values, pd.Series):
                    result.loc[mask, col] = fill_values[mask]
                else:
                    result.loc[mask, col] = fill_values
            return result
        else:
            # 无掩码时整表填充
            if self.cfg.fill_method == "none":
                return factor  # 不填充
            elif self.cfg.fill_method == "median":
                fill_vals = factor.median(axis=1)
                return factor.apply(lambda col: col.fillna(fill_vals))
            elif self.cfg.fill_method == "mean":
                fill_vals = factor.mean(axis=1)
                return factor.apply(lambda col: col.fillna(fill_vals))
            elif self.cfg.fill_method == "zero":
                return factor.fillna(0)
            else:
                fill_vals = factor.median(axis=1)
                return factor.apply(lambda col: col.fillna(fill_vals))
    
    def _neutralize(self, factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """中性化处理
        
        Args:
            factor: 因子数据
            tradable_mask: 可交易股票掩码
            
        Returns:
            中性化后的因子数据
        """
        result = factor.copy()
        
        for date in factor.index:
            series = factor.loc[date]
            
            # 如果有可交易掩码，只对可交易股票进行中性化
            if tradable_mask is not None:
                mask = tradable_mask.loc[date]
                neutralizable_stocks = series[mask].index
            else:
                neutralizable_stocks = series.index
            
            if len(neutralizable_stocks) < 10:  # 样本太少，跳过中性化
                continue
            
            # 构建回归矩阵
            X = []
            # 【修复E5】确定有完整行业/市值数据的股票子集
            valid_stocks = neutralizable_stocks.copy()
            
            # 行业虚拟变量
            if self.cfg.neutralize_industry and self.dm.industry is not None:
                industry_data = self.dm.industry.loc[date, neutralizable_stocks]
                # 【修复E5】过滤NaN行业数据，避免get_dummies出错
                industry_data = industry_data.dropna()
                if len(industry_data) > 0:
                    industry_dummies = pd.get_dummies(industry_data, prefix='ind')
                    # 确保列对齐
                    aligned_dummies = industry_dummies.reindex(neutralizable_stocks, fill_value=0)
                    X.extend(aligned_dummies.values.T)
                    # 更新有效股票集合（只保留有行业数据的）
                    valid_stocks = industry_data.index
            
            # 市值对数
            if self.cfg.neutralize_mktcap and self.dm.mktcap is not None:
                mktcap_data = self.dm.mktcap.loc[date, valid_stocks]
                log_mktcap = np.log(mktcap_data.replace(0, np.nan))
                X.append(log_mktcap.values)
            
            if not X:
                continue
            
            # 使用有效股票子集的因子值
            y = series[valid_stocks].values
            X = np.column_stack(X)
            
            # 去除常数列
            try:
                col_stds = np.std(X, axis=0)
                X = X[:, col_stds > 1e-8]
            except Exception:
                continue
            
            if X.shape[1] == 0:
                continue
            
            try:
                # 线性回归中性化
                X = np.column_stack([X, np.ones(len(X))])  # 添加常数项
                coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
                
                # 计算残差
                y_pred = X @ coeffs
                residuals = y - y_pred
                
                # 标准化残差
                res_std = float(np.std(residuals))
                residuals = (residuals - np.mean(residuals)) / res_std if res_std > 0 else residuals
                
                # 更新结果（只对有效股票更新）
                result.loc[date, valid_stocks] = residuals
                
            except Exception as e:
                logger.warning(f"日期 {date} 中性化失败: {e}")
                continue
        
        return result
    
    def _standardize(self, factor: pd.DataFrame, tradable_mask: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """标准化处理 - 向量化优化
        
        Args:
            factor: 因子数据
            tradable_mask: 可交易股票掩码 (Series: index=stock_codes, values=bool)
            
        Returns:
            标准化后的因子数据
        """
        # 处理 tradable_mask 是 Series 的情况
        if tradable_mask is not None and isinstance(tradable_mask, pd.Series):
            # 将 Series 掩码转换为与 factor 同形的 DataFrame
            mask_df = pd.DataFrame(
                np.tile(tradable_mask.reindex(factor.columns).values, (len(factor.index), 1)),
                index=factor.index,
                columns=factor.columns,
                dtype=bool
            )
            masked_factor = factor.where(mask_df)
        elif tradable_mask is not None:
            masked_factor = factor.where(tradable_mask)
        else:
            masked_factor = factor
        
        if self.cfg.standardize_method == "none":
            return factor  # 跳过标准化
            
        elif self.cfg.standardize_method == "zscore":
            # Z-score标准化 - 使用掩码后的统计量
            means = masked_factor.mean(axis=1)
            stds = masked_factor.std(axis=1).replace(0, np.nan)
            standardized = factor.sub(means, axis=0).div(stds, axis=0)
            return standardized.fillna(0)
            
        elif self.cfg.standardize_method == "rank":
            # 排序标准化
            # 【修复E6】统一使用masked_factor进行rank计算，确保NaN不参与排序
            ranks = masked_factor.rank(axis=1)
            means = ranks.mean(axis=1)
            stds = ranks.std(axis=1).replace(0, np.nan)
            standardized = ranks.sub(means, axis=0).div(stds, axis=0)
            # NaN位置保持NaN（不参与排序的股票不应被填充为0）
            return standardized.where(~factor.isna(), np.nan)
            
        elif self.cfg.standardize_method == "minmax":
            min_vals = masked_factor.min(axis=1)
            max_vals = masked_factor.max(axis=1)
            ranges = (max_vals - min_vals).replace(0, np.nan)
            standardized = factor.sub(min_vals, axis=0).div(ranges, axis=0)
            return standardized.fillna(0)
        else:
            logger.warning(f"未知的标准化方法: {self.cfg.standardize_method}")
            return factor
    
    def _reverse(self, factor: pd.DataFrame) -> pd.DataFrame:
        """因子反转处理
        
        对于负向因子（如换手率因子，高值表示风险），反转后高值变为低值，
        使得因子方向统一：高因子值 = 好股票。
        
        反转公式：factor' = -factor
        
        Args:
            factor: 原始因子数据
            
        Returns:
            反转后的因子数据
        """
        return -factor
    

class FactorCombiner:
    """因子合成器
    
    负责将多个处理后的因子合成为一个综合因子。
    """
    
    def __init__(self, factor_files: list[str], factor_weights: dict[str, float]):
        """初始化因子合成器
        
        Args:
            factor_files: 因子文件列表
            factor_weights: 因子权重字典
        """
        self.factor_files = factor_files
        self.factor_weights = factor_weights or {}
        self.factor_names = [f.replace('.pkl', '') for f in factor_files]
        
        # 如果没有指定权重，使用等权重
        if not self.factor_weights:
            equal_weight = 1.0 / len(self.factor_names)
            self.factor_weights = {name: equal_weight for name in self.factor_names}
        
        logger.info(f"因子合成器初始化: {self.factor_names}, 权重: {self.factor_weights}")
    
    def combine(self, processed_factors: dict[str, pd.DataFrame | pd.Series]) -> pd.DataFrame | pd.Series:
        """合成多个因子
        
        Args:
            processed_factors: 处理后的因子字典 {factor_name: factor_data}
            
        Returns:
            合成后的综合因子 (DataFrame 或 Series)
        """
        if not processed_factors:
            raise ValueError("没有可合成的因子")
        
        # 获取第一个因子
        first_factor = next(iter(processed_factors.values()))
        
        # 判断输入类型：DataFrame 还是 Series
        is_series = isinstance(first_factor, pd.Series)
        
        if is_series:
            # Series 输入：逐日合成
            composite = pd.Series(0.0, index=first_factor.index)
        else:
            # DataFrame 输入
            composite = pd.DataFrame(0.0, index=first_factor.index, columns=first_factor.columns)
        
        # 按权重合成
        total_weight = 0.0
        for factor_name, factor_data in processed_factors.items():
            # 【修复】如果没有权重配置，使用相等权重
            if factor_name in self.factor_weights:
                weight = self.factor_weights[factor_name]
            else:
                # 未找到权重，使用相等权重
                weight = 1.0 / len(processed_factors)
                logger.warning(f"因子 {factor_name} 未找到权重配置，使用默认权重 {weight:.2f}")
            
            # 处理NaN值，用0填充（避免NaN传播）
            factor_clean = factor_data.fillna(0)
            composite += factor_clean * weight
            total_weight += weight
            logger.debug(f"添加因子 {factor_name}, 权重: {weight}")
        
        # 如果总权重不为1，进行归一化
        if total_weight > 0 and abs(total_weight - 1.0) > 1e-6:
            composite = composite / total_weight
            logger.info(f"权重归一化: 总权重={total_weight:.2f}")
        
        # 【关键】如果composite全为0，说明有问题，返回原始第一个因子
        if is_series:
            if (composite == 0).all():
                logger.warning("合成因子全为0，返回第一个因子数据")
                composite = first_factor.fillna(0)
            logger.info(f"因子合成完成: Series {len(composite)} 只股票")
        else:
            if (composite == 0).all().all():
                logger.warning("合成因子全为0，返回第一个因子数据")
                composite = first_factor.fillna(0)
            logger.info(f"因子合成完成: {composite.shape}, NaN比例: {composite.isna().sum().sum() / (composite.shape[0] * composite.shape[1]):.2%}")
        
        return composite
    
    def get_factor_info(self) -> dict[str, Any]:
        """获取因子信息
        
        Returns:
            因子信息字典
        """
        return {
            'factor_names': self.factor_names,
            'factor_weights': self.factor_weights,
            'n_factors': len(self.factor_names)
        }
