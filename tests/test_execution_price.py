"""
测试多种执行价格类型
====================

验证：
1. OPEN - 开盘价执行
2. VWAP - 成交量加权平均价执行
3. CLOSE - 收盘价执行（仅测试）
4. CUSTOM - 自定义价格执行
"""

import sys
sys.path.insert(0, r'F:\Coding\Factor_Trading_v3.0')

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from core.config import CostConfig, ExecutionPriceType
from core.execution import ExecutionSimulator, TradeLog
from pending import OrderSide


class TestExecutionPriceTypes(unittest.TestCase):
    """测试多种执行价格类型"""
    
    def setUp(self):
        """设置测试环境"""
        self.cost_config = CostConfig(
            commission_rate=0.0003,
            commission_min=5.0,
            stamp_tax_rate=0.001,
            slippage_pct=0.0  # 关闭滑点以便精确验证
        )
        
        self.date = pd.Timestamp('2024-01-15')
        self.stock = '000001.SZ'
        self.quantity = 1000
        
        # 测试价格
        self.open_price = 10.0
        self.close_price = 11.0
        self.high_price = 11.5
        self.low_price = 9.8
    
    def test_open_price_execution(self):
        """测试开盘价执行"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.OPEN
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, self.close_price,
            self.high_price, self.low_price
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, self.open_price)  # 应该使用开盘价
        self.assertEqual(trade.amount, self.quantity * self.open_price)
        print(f"✓ OPEN执行: 价格={trade.price}, 金额={trade.amount}")
    
    def test_vwap_price_execution(self):
        """测试VWAP执行"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.VWAP
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, self.close_price,
            self.high_price, self.low_price
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        
        # VWAP = (10.0 + 11.0 + 11.5 + 9.8) / 4 = 10.575
        expected_vwap = (self.open_price + self.close_price + 
                        self.high_price + self.low_price) / 4
        self.assertAlmostEqual(trade.price, expected_vwap, places=2)
        print(f"✓ VWAP执行: 价格={trade.price:.2f} (预期={expected_vwap:.2f})")
    
    def test_close_price_execution(self):
        """测试收盘价执行"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.CLOSE
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, self.close_price,
            self.high_price, self.low_price
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, self.close_price)  # 应该使用收盘价
        print(f"✓ CLOSE执行: 价格={trade.price}, 金额={trade.amount}")
    
    def test_custom_price_execution(self):
        """测试自定义价格执行"""
        custom_price = 10.5
        
        def custom_callback(date, stock, side):
            return custom_price
        
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.CUSTOM,
            custom_price_callback=custom_callback
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, self.close_price,
            self.high_price, self.low_price
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, custom_price)  # 应该使用自定义价格
        print(f"✓ CUSTOM执行: 价格={trade.price} (自定义={custom_price})")
    
    def test_custom_price_fallback(self):
        """测试自定义价格回调失败时回退到开盘价"""
        def bad_callback(date, stock, side):
            raise ValueError("模拟错误")
        
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.CUSTOM,
            custom_price_callback=bad_callback
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, self.close_price,
            self.high_price, self.low_price
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, self.open_price)  # 回退到开盘价
        print(f"✓ CUSTOM回退: 回调失败，回退到开盘价={trade.price}")
    
    def test_close_price_missing_fallback(self):
        """测试收盘价缺失时回退到开盘价"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.CLOSE
        )
        
        # 不传入收盘价
        success, trade = executor.execute_order(
            self.stock, OrderSide.BUY, self.quantity,
            self.date, self.open_price, None, None, None
        )
        
        self.assertTrue(success)
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, self.open_price)  # 回退到开盘价
        print(f"✓ CLOSE回退: 收盘价缺失，回退到开盘价={trade.price}")
    
    def test_sell_cost_calculation(self):
        """测试卖出成本计算"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.OPEN
        )
        
        success, trade = executor.execute_order(
            self.stock, OrderSide.SELL, self.quantity,
            self.date, self.open_price, self.close_price
        )
        
        self.assertTrue(success)
        # 卖出应该有印花税
        expected_stamp_tax = self.quantity * self.open_price * 0.001
        self.assertAlmostEqual(
            trade.cost, 
            expected_stamp_tax + max(self.quantity * self.open_price * 0.0003, 5.0),
            places=1
        )
        print(f"✓ 卖出成本: {trade.cost:.2f} (含印花税)")
    
    def test_trade_log_recording(self):
        """测试交易日志记录"""
        executor = ExecutionSimulator(
            self.cost_config,
            execution_price_type=ExecutionPriceType.VWAP
        )
        
        # 执行多笔交易
        for i in range(3):
            executor.execute_order(
                f'STOCK{i}', OrderSide.BUY, 1000,
                self.date, 10.0 + i, 11.0 + i, 11.5 + i, 9.8 + i
            )
        
        stats = executor.trade_log.get_trade_stats()
        self.assertEqual(stats['total_trades'], 3)
        self.assertEqual(stats['buy_trades'], 3)
        print(f"✓ 交易日志: 共{stats['total_trades']}笔交易")


class TestExecutionPriceConfig(unittest.TestCase):
    """测试配置集成"""
    
    def test_config_default(self):
        """测试默认配置"""
        from core.config import BacktestConfig
        
        cfg = BacktestConfig()
        self.assertEqual(cfg.execution_price_type, ExecutionPriceType.OPEN)
        self.assertIsNone(cfg.execution_price_custom_callback)
        print("✓ 默认配置: execution_price_type=OPEN")
    
    def test_config_custom(self):
        """测试自定义配置"""
        from core.config import BacktestConfig
        
        def my_callback(date, stock, side):
            return 10.0
        
        cfg = BacktestConfig(
            execution_price_type=ExecutionPriceType.CUSTOM,
            execution_price_custom_callback=my_callback
        )
        
        self.assertEqual(cfg.execution_price_type, ExecutionPriceType.CUSTOM)
        self.assertEqual(cfg.execution_price_custom_callback, my_callback)
        print("✓ 自定义配置: execution_price_type=CUSTOM")


def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("执行价格类型测试")
    print("=" * 70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestExecutionPriceTypes))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutionPriceConfig))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
