"""
Phase 4 TDD: vbt 信号兼容测试

测试 SignalTranslator.from_signals() - vbt 风格 buy_signal/sell_signal 转换
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import pandas as pd


class TestSignalTranslatorFromSignals(unittest.TestCase):
    """SignalTranslator.from_signals - vbt 信号格式"""

    def test_buy_signal_new_position(self):
        """buy_signal=True 且无持仓 → BUY intent"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([True], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.asset, "IF2406")
        self.assertEqual(intent.action, "BUY")
        self.assertEqual(intent.current_quantity, 0.0)
        # total_value=700000 / price=3500 = 200
        self.assertAlmostEqual(intent.target_quantity, 200.0)

    def test_sell_signal_close_position(self):
        """sell_signal=True 且有多头持仓 → SELL intent"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([False], index=["IF2406"])
        sell_signal = pd.Series([True], index=["IF2406"])
        prices = pd.Series([3600.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={"IF2406": 2.0},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.action, "SELL")
        self.assertEqual(intent.current_quantity, 2.0)
        self.assertEqual(intent.target_quantity, 0.0)

    def test_short_signal_new_short(self):
        """short_signal=True 且无持仓 → SELL_SHORT intent"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([False], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        short_signal = pd.Series([True], index=["IF2406"])
        short_exit_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
            short_signal=short_signal,
            short_exit_signal=short_exit_signal,
        )

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.action, "SELL_SHORT")
        self.assertEqual(intent.target_quantity, -200.0)

    def test_short_exit_signal(self):
        """short_exit_signal=True 且有空头持仓 → BUY_TO_COVER intent"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([False], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        short_signal = pd.Series([False], index=["IF2406"])
        short_exit_signal = pd.Series([True], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={"IF2406": -2.0},
            prices=prices,
            total_value=700000.0,
            short_signal=short_signal,
            short_exit_signal=short_exit_signal,
        )

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.action, "BUY_TO_COVER")
        self.assertEqual(intent.current_quantity, -2.0)
        self.assertEqual(intent.target_quantity, 0.0)

    def test_no_signals_no_intents(self):
        """无信号 → 空列表"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([False], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 0)

    def test_ignore_buy_when_already_long(self):
        """已有持仓时 buy_signal=True → 跳过"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([True], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={"IF2406": 2.0},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 0)

    def test_ignore_sell_when_no_position(self):
        """无持仓时 sell_signal=True → 跳过"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([False], index=["IF2406"])
        sell_signal = pd.Series([True], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 0)

    def test_multiple_assets(self):
        """多资产信号"""
        from core.execution_policy import SignalTranslator

        assets = ["IF2406", "IC2406", "IH2406"]
        buy_signal = pd.Series([True, False, False], index=assets)
        sell_signal = pd.Series([False, True, False], index=assets)
        prices = pd.Series([3500.0, 5000.0, 2400.0], index=assets)

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={"IC2406": 1.0},  # 持有 IC2406
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 2)

        buy_intent = next(i for i in intents if i.asset == "IF2406")
        self.assertEqual(buy_intent.action, "BUY")

        sell_intent = next(i for i in intents if i.asset == "IC2406")
        self.assertEqual(sell_intent.action, "SELL")

    def test_default_short_signals(self):
        """不提供 short_signal/short_exit_signal 时默认为空"""
        from core.execution_policy import SignalTranslator

        buy_signal = pd.Series([True], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
        )

        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].action, "BUY")

    def test_from_signals_to_t0_policy(self):
        """from_signals 输出可直接消费于 T0FuturesPolicy"""
        from core.execution_policy import (
            SignalTranslator, T0FuturesPolicy,
        )

        buy_signal = pd.Series([True], index=["IF2406"])
        sell_signal = pd.Series([False], index=["IF2406"])
        prices = pd.Series([3500.0], index=["IF2406"])

        intents = SignalTranslator.from_signals(
            buy_signal=buy_signal,
            sell_signal=sell_signal,
            current_positions={},
            prices=prices,
            total_value=700000.0,
        )

        policy = T0FuturesPolicy()
        orders = policy.create_orders(intents[0], pd.Timestamp("2024-01-15"))
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side.name, "BUY")


if __name__ == "__main__":
    unittest.main(verbosity=2)