"""
Walk-Forward回测框架
===================

实现时间序列的Walk-Forward分割，支持：
1. 固定窗口（Rolling Window）
2. 扩展窗口（Expanding Window）
3. Purge Gap防止数据泄漏
4. 与Agent蒸馏隔离机制集成

参考：
- Marcos Lopez de Prado: "Advances in Financial Machine Learning"
-  purged k-fold cross-validation for time series
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PeriodType(str, Enum):
    """回测期间类型"""
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class SplitMethod(str, Enum):
    """窗口分割方法"""
    ROLLING = "rolling"      # 固定窗口大小
    EXPANDING = "expanding"  # 扩展窗口大小


@dataclass
class WalkForwardWindow:
    """Walk-Forward窗口
    
    包含训练期和测试期的日期范围
    """
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    window_index: int = 0
    
    @property
    def train_dates(self) -> pd.DatetimeIndex:
        """训练期日期"""
        return pd.date_range(self.train_start, self.train_end, freq='B')
    
    @property
    def test_dates(self) -> pd.DatetimeIndex:
        """测试期日期"""
        return pd.date_range(self.test_start, self.test_end, freq='B')
    
    def get_period(self, date: pd.Timestamp) -> PeriodType:
        """判断指定日期属于哪个期间"""
        if self.train_start <= date <= self.train_end:
            return PeriodType.TRAIN
        elif self.test_start <= date <= self.test_end:
            return PeriodType.TEST
        else:
            raise ValueError(f"日期 {date} 不在当前窗口范围内")
    
    def __repr__(self) -> str:
        return (f"WalkForwardWindow({self.window_index}): "
                f"train=[{self.train_start.date()} ~ {self.train_end.date()}], "
                f"test=[{self.test_start.date()} ~ {self.test_end.date()}]")


class WalkForwardSplitter:
    """Walk-Forward窗口分割器
    
    将时间序列分割为多个训练/测试窗口，支持purge gap防止数据泄漏。
    
    Args:
        dates: 完整的交易日历
        train_size: 训练期大小（交易日数）
        test_size: 测试期大小（交易日数）
        purge_gap: 训练期和测试期之间的间隔（交易日数）
        method: 分割方法（rolling/expanding）
        step_size: 窗口滚动步长（默认=test_size）
        min_train_size: 最小训练期大小（仅expanding模式）
    
    Example:
        >>> dates = pd.date_range('2020-01-01', '2023-12-31', freq='B')
        >>> splitter = WalkForwardSplitter(
        ...     dates=dates,
        ...     train_size=252,
        ...     test_size=63,
        ...     purge_gap=5,
        ...     method='rolling'
        ... )
        >>> for window in splitter.split():
        ...     print(window)
    """
    
    def __init__(self,
                 dates: pd.DatetimeIndex,
                 train_size: int = 252,
                 test_size: int = 63,
                 purge_gap: int = 5,
                 method: str = "rolling",
                 step_size: Optional[int] = None,
                 min_train_size: Optional[int] = None):
        self.dates = dates
        self.train_size = train_size
        self.test_size = test_size
        self.purge_gap = purge_gap
        self.method = SplitMethod(method)
        self.step_size = step_size or test_size
        self.min_train_size = min_train_size or train_size
        
        # 验证参数
        self._validate_params()
        
        logger.info(f"WalkForwardSplitter初始化: "
                   f"method={method}, train={train_size}, test={test_size}, "
                   f"purge_gap={purge_gap}, step={self.step_size}")
    
    def _validate_params(self):
        """验证参数合法性"""
        if self.train_size <= 0:
            raise ValueError("train_size必须大于0")
        if self.test_size <= 0:
            raise ValueError("test_size必须大于0")
        if self.purge_gap < 0:
            raise ValueError("purge_gap不能为负数")
        if self.step_size <= 0:
            raise ValueError("step_size必须大于0")
        
        total_needed = self.train_size + self.purge_gap + self.test_size
        if len(self.dates) < total_needed:
            logger.warning(f"日期数量({len(self.dates)})不足，"
                          f"需要至少{total_needed}个交易日")
    
    def split(self) -> Iterator[WalkForwardWindow]:
        """生成分割窗口
        
        Yields:
            WalkForwardWindow: 每个窗口包含训练期和测试期
        """
        n_dates = len(self.dates)
        
        # 计算第一个窗口的起始位置
        if self.method == SplitMethod.ROLLING:
            # 固定窗口：从足够数据的位置开始
            first_start_idx = 0
        else:
            # 扩展窗口：从min_train_size开始
            first_start_idx = 0
        
        window_index = 0
        current_idx = first_start_idx
        
        while True:
            # 计算当前窗口的边界
            if self.method == SplitMethod.ROLLING:
                # 固定窗口
                train_start_idx = current_idx
                train_end_idx = train_start_idx + self.train_size - 1
            else:
                # 扩展窗口
                train_start_idx = 0
                train_end_idx = max(
                    current_idx + self.min_train_size - 1,
                    self.min_train_size - 1
                )
            
            # 计算测试期起始位置（考虑purge gap）
            test_start_idx = train_end_idx + 1 + self.purge_gap
            test_end_idx = test_start_idx + self.test_size - 1
            
            # 检查是否超出数据范围
            if test_end_idx >= n_dates:
                break
            
            # 创建窗口
            window = WalkForwardWindow(
                train_start=self.dates[train_start_idx],
                train_end=self.dates[train_end_idx],
                test_start=self.dates[test_start_idx],
                test_end=self.dates[test_end_idx],
                window_index=window_index
            )
            
            logger.debug(f"生成窗口: {window}")
            yield window
            
            # 移动到下一个窗口
            window_index += 1
            current_idx += self.step_size
    
    def get_n_splits(self) -> int:
        """获取分割窗口数量"""
        return sum(1 for _ in self.split())
    
    def get_window(self, index: int) -> WalkForwardWindow:
        """获取指定索引的窗口"""
        for i, window in enumerate(self.split()):
            if i == index:
                return window
        raise IndexError(f"窗口索引 {index} 超出范围")


@dataclass
class WalkForwardResult:
    """Walk-Forward回测结果
    
    汇总所有窗口的回测结果
    """
    window_results: list[dict]
    
    @property
    def n_windows(self) -> int:
        """窗口数量"""
        return len(self.window_results)
    
    @property
    def total_return(self) -> float:
        """总收益（所有窗口的复合收益）"""
        if not self.window_results:
            return 0.0
        
        total = 1.0
        for result in self.window_results:
            total *= (1 + result.get('total_return', 0))
        return total - 1.0
    
    @property
    def avg_return(self) -> float:
        """平均窗口收益"""
        if not self.window_results:
            return 0.0
        returns = [r.get('total_return', 0) for r in self.window_results]
        return np.mean(returns)
    
    @property
    def avg_sharpe(self) -> float:
        """平均夏普比率"""
        if not self.window_results:
            return 0.0
        sharpes = [r.get('sharpe_ratio', 0) for r in self.window_results]
        return np.mean(sharpes)
    
    @property
    def win_rate(self) -> float:
        """胜率（正收益窗口比例）"""
        if not self.window_results:
            return 0.0
        wins = sum(1 for r in self.window_results if r.get('total_return', 0) > 0)
        return wins / len(self.window_results)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'n_windows': self.n_windows,
            'total_return': self.total_return,
            'avg_return': self.avg_return,
            'avg_sharpe': self.avg_sharpe,
            'win_rate': self.win_rate,
            'window_results': self.window_results,
        }
    
    def __repr__(self) -> str:
        return (f"WalkForwardResult: {self.n_windows}个窗口, "
                f"总收益={self.total_return:.2%}, "
                f"胜率={self.win_rate:.1%}")


def create_walk_forward_splits(
    start_date: str,
    end_date: str,
    train_years: float = 2.0,
    test_months: float = 3.0,
    purge_days: int = 5,
    method: str = "rolling"
) -> WalkForwardSplitter:
    """便捷函数：创建Walk-Forward分割器
    
    Args:
        start_date: 起始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'
        train_years: 训练期年数
        test_months: 测试期月数
        purge_days: purge gap天数
        method: 分割方法
    
    Returns:
        WalkForwardSplitter: 配置好的分割器
    """
    dates = pd.date_range(start_date, end_date, freq='B')
    
    train_size = int(train_years * 252)  # 约252个交易日/年
    test_size = int(test_months * 21)    # 约21个交易日/月
    
    return WalkForwardSplitter(
        dates=dates,
        train_size=train_size,
        test_size=test_size,
        purge_gap=purge_days,
        method=method
    )


if __name__ == "__main__":
    # 简单测试
    dates = pd.date_range('2020-01-01', '2023-12-31', freq='B')
    splitter = WalkForwardSplitter(
        dates=dates,
        train_size=252,
        test_size=63,
        purge_gap=5,
        method='rolling'
    )
    
    print(f"Walk-Forward分割: {splitter.get_n_splits()}个窗口")
    for window in splitter.split():
        print(f"  {window}")
