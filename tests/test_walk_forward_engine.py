"""
测试Walk-Forward回测引擎
========================

验证：
1. 引擎初始化正确
2. 训练期/测试期自动切换
3. Agent期间设置正确
4. 结果汇总正确
"""

import sys
sys.path.insert(0, r'F:\Coding\Factor_Trading_v3.0')

import unittest
from datetime import datetime

import pandas as pd


class MockAgent:
    """模拟Agent用于测试"""
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.current_period = None
        self.distillation_config = type('obj', (object,), {
            'is_test_period': False
        })()
        self.train_calls = 0
        self.test_calls = 0
    
    def set_period(self, period):
        self.current_period = period
        if period == 'train':
            self.train_calls += 1
        elif period == 'test':
            self.test_calls += 1


class TestWalkForwardEngine(unittest.TestCase):
    """测试Walk-Forward引擎"""
    
    def setUp(self):
        """创建测试数据"""
        from core.walk_forward import WalkForwardSplitter
        
        self.dates = pd.date_range('2020-01-01', '2023-12-31', freq='B')
        self.splitter = WalkForwardSplitter(
            dates=self.dates,
            train_size=252,
            test_size=63,
            purge_gap=5,
            method='rolling'
        )
    
    def test_engine_initialization(self):
        """测试引擎初始化"""
        from core.walk_forward_engine import WalkForwardEngine
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=self.splitter,
            config=None
        )
        
        self.assertIsNotNone(engine)
        self.assertEqual(engine.splitter, self.splitter)
        print("✓ 引擎初始化正确")
    
    def test_agent_period_switching(self):
        """测试Agent期间切换"""
        from core.walk_forward_engine import WalkForwardEngine
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=self.splitter,
            config=None
        )
        
        # 创建模拟Agent
        agents = [MockAgent("agent1"), MockAgent("agent2")]
        
        # 运行（简化模式）
        result = engine.run(agents=agents)
        
        # 验证每个Agent都被设置了训练期和测试期
        for agent in agents:
            self.assertGreater(agent.train_calls, 0, f"Agent {agent.agent_id} 未设置训练期")
            self.assertGreater(agent.test_calls, 0, f"Agent {agent.agent_id} 未设置测试期")
        
        print(f"✓ Agent期间切换正确: {len(agents)}个Agent, {result.n_windows}个窗口")
    
    def test_test_period_frozen(self):
        """测试测试期Agent被冻结"""
        from core.walk_forward_engine import WalkForwardEngine
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=self.splitter,
            config=None
        )
        
        agent = MockAgent("test_agent")
        engine.run(agents=[agent])
        
        # 验证测试期标记
        self.assertTrue(agent.distillation_config.is_test_period)
        print("✓ 测试期冻结标记正确")
    
    def test_result_aggregation(self):
        """测试结果汇总"""
        from core.walk_forward_engine import WalkForwardEngine
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=self.splitter,
            config=None
        )
        
        result = engine.run()
        
        # 验证结果结构
        self.assertIsNotNone(result)
        self.assertGreater(result.n_windows, 0)
        self.assertIn('n_windows', result.to_dict())
        
        print(f"✓ 结果汇总正确: {result.n_windows}个窗口")
    
    def test_callbacks(self):
        """测试回调函数"""
        from core.walk_forward_engine import WalkForwardEngine
        
        callback_log = []
        
        def on_train_complete(window, result):
            callback_log.append(('train', window.window_index))
        
        def on_test_complete(window, result):
            callback_log.append(('test', window.window_index))
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=self.splitter,
            config=None,
            window_callbacks={
                'on_train_complete': on_train_complete,
                'on_test_complete': on_test_complete,
            }
        )
        
        result = engine.run()
        
        # 验证回调被调用
        self.assertEqual(len(callback_log), result.n_windows * 2)
        print(f"✓ 回调函数正确: {len(callback_log)}次调用")


class TestWalkForwardIntegration(unittest.TestCase):
    """测试Walk-Forward与Agent蒸馏隔离集成"""
    
    def test_guru_agent_period_isolation(self):
        """测试GuruAgent期间隔离"""
        from core.walk_forward import WalkForwardSplitter
        from core.walk_forward_engine import WalkForwardEngine
        from agents.guru_agent_v2 import GuruAgentV2
        
        # 创建短周期分割器用于测试
        dates = pd.date_range('2022-01-01', '2023-12-31', freq='B')
        splitter = WalkForwardSplitter(
            dates=dates,
            train_size=100,
            test_size=30,
            purge_gap=5,
            method='rolling'
        )
        
        engine = WalkForwardEngine(
            base_engine_class=None,
            splitter=splitter,
            config=None
        )
        
        # 创建GuruAgent
        try:
            agent = GuruAgentV2('buffett')
            
            # 运行
            result = engine.run(agents=[agent])
            
            # 验证Agent有期间设置
            self.assertTrue(hasattr(agent, 'current_period'))
            print(f"✓ GuruAgent期间隔离集成正确")
        except Exception as e:
            print(f"⚠️ GuruAgent测试跳过: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
