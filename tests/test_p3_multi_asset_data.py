"""
P3.2 TDD: 多资产市场数据接口测试

验证:
1. AssetInfo 数据类定义
2. IDataManager 接口扩展 get_asset_info()
3. DataManager 实现 get_asset_info()
4. DataLoaderV3 实现 get_asset_info()
5. 向后兼容：现有代码不受影响
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import numpy as np
import pandas as pd


# ============================================================================
# P3.2.1: AssetInfo 数据类
# ============================================================================


class TestAssetInfo(unittest.TestCase):
    """AssetInfo 数据类定义"""

    def test_asset_info_exists(self):
        """AssetInfo 类存在"""
        from core.config import AssetInfo

        self.assertTrue(hasattr(AssetInfo, "__dataclass_fields__"))

    def test_asset_info_default_values(self):
        """AssetInfo 默认值 (股票)"""
        from core.config import AssetInfo, AssetType

        info = AssetInfo(asset_type=AssetType.STOCK)

        self.assertEqual(info.asset_type, AssetType.STOCK)
        self.assertEqual(info.multiplier, 1)
        self.assertIsNone(info.margin_ratio)
        self.assertIsNone(info.expiry_date)
        self.assertEqual(info.tick_size, 0.01)

    def test_asset_info_futures(self):
        """AssetInfo 期货配置"""
        from core.config import AssetInfo, AssetType

        info = AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
            margin_ratio=0.12,
            tick_size=0.2,
            expiry_date="2024-06-21",
        )

        self.assertEqual(info.asset_type, AssetType.FUTURE)
        self.assertEqual(info.multiplier, 300)
        self.assertEqual(info.margin_ratio, 0.12)
        self.assertEqual(info.tick_size, 0.2)
        self.assertEqual(info.expiry_date, "2024-06-21")

    def test_asset_info_contract_value(self):
        """期货合约价值 = multiplier × price"""
        from core.config import AssetInfo, AssetType

        info = AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
        )
        # 合约价值 = 300 × 3500 = 1,050,000
        contract_value = info.multiplier * 3500.0
        self.assertEqual(contract_value, 1_050_000.0)

    def test_asset_info_margin_required(self):
        """期货保证金 = contract_value × margin_ratio"""
        from core.config import AssetInfo, AssetType

        info = AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
            margin_ratio=0.12,
        )
        contract_value = info.multiplier * 3500.0
        margin = contract_value * info.margin_ratio
        self.assertAlmostEqual(margin, 126_000.0)


# ============================================================================
# P3.2.2: IDataManager 接口扩展
# ============================================================================


class TestIDataManagerAssetInfo(unittest.TestCase):
    """IDataManager 接口扩展"""

    def test_interface_has_get_asset_info(self):
        """IDataManager 定义 get_asset_info 方法"""
        from core.interfaces import IDataManager

        self.assertTrue(hasattr(IDataManager, "get_asset_info"))

    def test_get_asset_info_returns_asset_info(self):
        """get_asset_info 返回 AssetInfo 实例"""
        from core.interfaces import IDataManager
        from core.config import AssetInfo

        # 检查返回类型注解
        import inspect

        sig = inspect.signature(IDataManager.get_asset_info)
        return_annotation = sig.return_annotation
        self.assertIsNotNone(return_annotation)


# ============================================================================
# P3.2.3: DataManager 实现
# ============================================================================


class TestDataManagerAssetInfo(unittest.TestCase):
    """DataManager 实现 get_asset_info"""

    def setUp(self):
        from core.config import BacktestConfig, AssetInfo, AssetType
        from core.data import DataManager

        self.cfg = BacktestConfig()
        self.dm = DataManager(self.cfg)

    def test_data_manager_implements_get_asset_info(self):
        """DataManager 实现 get_asset_info"""
        self.assertTrue(hasattr(self.dm, "get_asset_info"))

    def test_get_asset_info_returns_asset_info_instance(self):
        """get_asset_info 返回 AssetInfo 实例"""
        from core.config import AssetInfo

        info = self.dm.get_asset_info("000001.SZ")
        self.assertIsInstance(info, AssetInfo)

    def test_unknown_symbol_defaults_to_stock(self):
        """未知代码默认返回股票类型 AssetInfo"""
        from core.config import AssetType

        info = self.dm.get_asset_info("UNKNOWN_CODE")
        self.assertEqual(info.asset_type, AssetType.STOCK)
        self.assertEqual(info.multiplier, 1)

    def test_configured_asset_info_is_returned(self):
        """已配置的资产信息返回正确值"""
        from core.config import AssetInfo, AssetType

        # 配置期货信息
        self.dm.configure_asset("IF2406", AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
            margin_ratio=0.12,
            tick_size=0.2,
        ))

        info = self.dm.get_asset_info("IF2406")
        self.assertEqual(info.asset_type, AssetType.FUTURE)
        self.assertEqual(info.multiplier, 300)
        self.assertEqual(info.margin_ratio, 0.12)

    def test_bulk_configure_assets(self):
        """批量配置多资产"""
        from core.config import AssetInfo, AssetType

        self.dm.configure_assets({
            "IF2406": AssetInfo(asset_type=AssetType.FUTURE, multiplier=300),
            "IC2406": AssetInfo(asset_type=AssetType.FUTURE, multiplier=200),
            "000001.SZ": AssetInfo(asset_type=AssetType.STOCK),
        })

        self.assertEqual(
            self.dm.get_asset_info("IF2406").asset_type,
            AssetType.FUTURE,
        )
        self.assertEqual(
            self.dm.get_asset_info("IC2406").multiplier,
            200,
        )
        self.assertEqual(
            self.dm.get_asset_info("000001.SZ").asset_type,
            AssetType.STOCK,
        )


# ============================================================================
# P3.2.4: DataLoaderV3 实现
# ============================================================================


class TestDataLoaderV3AssetInfo(unittest.TestCase):
    """DataLoaderV3 实现 get_asset_info"""

    def setUp(self):
        from core.data_v3 import DataLoaderV3

        self.dl = DataLoaderV3()

    def test_dataloader_v3_implements_get_asset_info(self):
        """DataLoaderV3 实现 get_asset_info"""
        self.assertTrue(hasattr(self.dl, "get_asset_info"))

    def test_dataloader_v3_returns_asset_info(self):
        """DataLoaderV3.get_asset_info 返回 AssetInfo"""
        from core.config import AssetInfo

        info = self.dl.get_asset_info("000001.SZ")
        self.assertIsInstance(info, AssetInfo)

    def test_dataloader_v3_configure_asset(self):
        """DataLoaderV3 支持 configure_asset"""
        from core.config import AssetInfo, AssetType

        self.dl.configure_asset("IF2406", AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
        ))

        info = self.dl.get_asset_info("IF2406")
        self.assertEqual(info.asset_type, AssetType.FUTURE)
        self.assertEqual(info.multiplier, 300)


# ============================================================================
# P3.2.5: 向后兼容
# ============================================================================


class TestBackwardCompatibility(unittest.TestCase):
    """向后兼容验证"""

    def test_existing_data_manager_usage_unaffected(self):
        """现有 DataManager 用法不受影响"""
        from core.config import BacktestConfig
        from core.data import DataManager

        dm = DataManager(BacktestConfig())
        # 原有方法仍然可用 (不触发数据加载)
        self.assertTrue(hasattr(dm, "get_data_info"))
        self.assertTrue(hasattr(dm, "clear_cache"))
        self.assertTrue(hasattr(dm, "get_asset_info"))

    def test_asset_info_serializable(self):
        """AssetInfo 可序列化"""
        import json
        from dataclasses import asdict
        from core.config import AssetInfo, AssetType

        info = AssetInfo(
            asset_type=AssetType.FUTURE,
            multiplier=300,
            margin_ratio=0.12,
        )

        d = asdict(info)
        self.assertEqual(d["asset_type"], "future")
        self.assertEqual(d["multiplier"], 300)
        self.assertEqual(d["margin_ratio"], 0.12)


if __name__ == "__main__":
    unittest.main(verbosity=2)