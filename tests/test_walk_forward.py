"""
测试Walk-Forward窗口分割器
==========================

验证：
1. 固定窗口分割正确性
2. 扩展窗口分割正确性
3. Purge gap防止数据泄漏
4. 边界条件处理
"""

import sys
sys.path.insert(0, r'F:\Coding\Factor_Trading_v3.0')

import unittest
from datetime import datetime, timedelta

import pandas as pd


class TestWalkForwardSplitter(unittest.TestCase):
    """测试Walk-Forward窗口分割器"""
    
    def setUp(self):
        """创建测试数据"""
        self.dates = pd.date_range('2020-01-01', '2023-12-31', freq='B')  # 约1000个交易日
        
    def test_rolling_window_split(self):
        """测试固定窗口分割"""
        from core.walk_forward import WalkForwardSplitter
        
        splitter = WalkForwardSplitter(
            dates=self.dates,
            train_size=252,      # 1年训练
            test_size=63,        # 3个月测试
            purge_gap=5,         # 5天purge gap
            method='rolling'
        )
        
        splits = list(splitter.split())
        
        # 验证分割数量
        self.assertTrue(len(splits) > 0)
        
        # 验证每个分割的train/test不重叠
        for window in splits:
            train_dates = window.train_dates
            test_dates = window.test_dates
            self.assertTrue(train_dates[-1] < test_dates[0])
            self.assertEqual(len(train_dates), 252)
            self.assertEqual(len(test_dates), 63)
        
        print(f"✓ 固定窗口分割: {len(splits)}个窗口")
    
    def test_expanding_window_split(self):
        """测试扩展窗口分割"""
        from core.walk_forward import WalkForwardSplitter
        
        splitter = WalkForwardSplitter(
            dates=self.dates,
            train_size=252,
            test_size=63,
            purge_gap=5,
            method='expanding'
        )
        
        splits = list(splitter.split())
        
        # 验证训练集逐渐扩大
        prev_train_len = 0
        for window in splits:
            train_dates = window.train_dates
            self.assertTrue(len(train_dates) >= prev_train_len)
            prev_train_len = len(train_dates)
        
        print(f"✓ 扩展窗口分割: {len(splits)}个窗口")
    
    def test_purge_gap(self):
        """测试purge gap防止数据泄漏"""
        from core.walk_forward import WalkForwardSplitter
        
        splitter = WalkForwardSplitter(
            dates=self.dates,
            train_size=100,
            test_size=50,
            purge_gap=10,
            method='rolling'
        )
        
        for window in splitter.split():
            train_dates = window.train_dates
            test_dates = window.test_dates
            # train最后一个日期和test第一个日期之间应该有purge_gap
            gap = (test_dates[0] - train_dates[-1]).days
            self.assertTrue(gap >= 10, f"purge gap不足: {gap}天")
        
        print("✓ Purge gap正确防止数据泄漏")
    
    def test_no_overlap_between_splits(self):
        """测试不同窗口之间不重叠"""
        from core.walk_forward import WalkForwardSplitter
        
        splitter = WalkForwardSplitter(
            dates=self.dates,
            train_size=200,
            test_size=50,
            purge_gap=5,
            method='rolling'
        )
        
        splits = list(splitter.split())
        
        # 验证相邻窗口的test不重叠
        for i in range(len(splits) - 1):
            test_dates_1 = splits[i].test_dates
            test_dates_2 = splits[i + 1].test_dates
            self.assertTrue(test_dates_1[-1] < test_dates_2[0])
        
        print("✓ 窗口之间无重叠")
    
    def test_date_range_validation(self):
        """测试日期范围验证"""
        from core.walk_forward import WalkForwardSplitter
        
        # 训练集太大，无法分割
        splitter = WalkForwardSplitter(
            dates=self.dates[:100],
            train_size=200,
            test_size=50,
            purge_gap=5
        )
        
        splits = list(splitter.split())
        self.assertEqual(len(splits), 0)
        print("✓ 日期范围不足时正确返回空")


class TestWalkForwardPeriod(unittest.TestCase):
    """测试期间类型标记"""
    
    def test_period_types(self):
        """测试期间类型枚举"""
        from core.walk_forward import PeriodType
        
        self.assertEqual(PeriodType.TRAIN, "train")
        self.assertEqual(PeriodType.VALIDATION, "validation")
        self.assertEqual(PeriodType.TEST, "test")
        print("✓ 期间类型枚举正确")


if __name__ == "__main__":
    unittest.main(verbosity=2)
