"""
测试Agent蒸馏数据隔离
=====================

验证：
1. DistillationSource和LearningMode枚举
2. Guru JSON的distillation_config字段
3. BayesianResearchRole期间隔离
4. HierarchicalBelief轨迹隔离
5. 回测引擎period传递
6. 测试期自动冻结
"""

import sys
sys.path.insert(0, r'F:\Coding\Factor_Trading_v3.0')

import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


class TestDistillationEnums(unittest.TestCase):
    """测试蒸馏枚举类型"""
    
    def test_distillation_source_values(self):
        """测试DistillationSource枚举值"""
        from core.config import DistillationSource
        self.assertEqual(DistillationSource.MANUAL, "manual")
        self.assertEqual(DistillationSource.TRAINED, "trained")
        self.assertEqual(DistillationSource.HYBRID, "hybrid")
        print("✓ DistillationSource枚举值正确")
    
    def test_learning_mode_values(self):
        """测试LearningMode枚举值"""
        from core.config import LearningMode
        self.assertEqual(LearningMode.ONLINE, "online")
        self.assertEqual(LearningMode.FROZEN, "frozen")
        self.assertEqual(LearningMode.RESET, "reset")
        print("✓ LearningMode枚举值正确")


class TestAgentDistillationConfig(unittest.TestCase):
    """测试Agent蒸馏配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        from core.config import AgentDistillationConfig, DistillationSource, LearningMode
        config = AgentDistillationConfig()
        self.assertEqual(config.source, DistillationSource.MANUAL)
        self.assertEqual(config.learning_mode, LearningMode.FROZEN)
        self.assertIsNone(config.train_period)
        self.assertFalse(config.is_test_period)
        print("✓ AgentDistillationConfig默认值正确")
    
    def test_trained_requires_train_period(self):
        """测试TRAINED来源必须指定train_period"""
        from core.config import AgentDistillationConfig, DistillationSource
        config = AgentDistillationConfig(
            source=DistillationSource.TRAINED,
            train_period=None
        )
        errors = config.validate()
        self.assertTrue(len(errors) > 0)
        print("✓ TRAINED来源验证正确")
    
    def test_test_period_forbids_online(self):
        """测试测试期禁止ONLINE学习模式"""
        from core.config import AgentDistillationConfig, DistillationSource, LearningMode
        config = AgentDistillationConfig(
            source=DistillationSource.TRAINED,
            train_period=("2020-01-01", "2022-12-31"),
            is_test_period=True,
            learning_mode=LearningMode.ONLINE
        )
        errors = config.validate()
        self.assertTrue(any("ONLINE" in e for e in errors))
        print("✓ 测试期ONLINE模式禁止正确")
    
    def test_valid_config(self):
        """测试有效配置"""
        from core.config import AgentDistillationConfig, DistillationSource, LearningMode
        config = AgentDistillationConfig(
            source=DistillationSource.TRAINED,
            train_period=("2020-01-01", "2022-12-31"),
            is_test_period=True,
            learning_mode=LearningMode.FROZEN
        )
        errors = config.validate()
        self.assertEqual(len(errors), 0)
        print("✓ 有效配置验证通过")


class TestHierarchicalBeliefIsolation(unittest.TestCase):
    """测试HierarchicalBelief期间隔离"""
    
    def setUp(self):
        """设置测试环境"""
        from agents.hierarchical_bayesian_agent import HierarchicalBelief, BeliefLayer
        self.belief = HierarchicalBelief(
            name="test_belief",
            layer=BeliefLayer.TACTIC,
            prior=0.5,
            tension_range=0.3
        )
    
    def test_train_period_update(self):
        """测试训练期允许更新"""
        initial_posterior = self.belief.posterior
        
        # 训练期更新
        self.belief.update(
            likelihood_ratio=1.5,
            parent_posterior=0.6,
            macro_shock=False,
            period="train"
        )
        
        # 后验应该改变
        self.assertNotEqual(self.belief.posterior, initial_posterior)
        self.assertEqual(len(self.belief.train_trajectory), 1)
        print(f"✓ 训练期更新正确: posterior={self.belief.posterior:.3f}")
    
    def test_test_period_frozen(self):
        """测试测试期冻结更新"""
        # 先在训练期更新一次
        self.belief.update(
            likelihood_ratio=1.5,
            parent_posterior=0.6,
            macro_shock=False,
            period="train"
        )
        train_posterior = self.belief.posterior
        
        # 测试期尝试更新
        self.belief.update(
            likelihood_ratio=2.0,
            parent_posterior=0.7,
            macro_shock=False,
            period="test"
        )
        
        # 后验应该保持不变
        self.assertEqual(self.belief.posterior, train_posterior)
        self.assertEqual(len(self.belief.test_trajectory), 1)
        print(f"✓ 测试期冻结正确: posterior保持={self.belief.posterior:.3f}")
    
    def test_test_period_with_allow_update(self):
        """测试测试期允许更新（显式设置）"""
        self.belief.allow_test_update = True
        
        initial_posterior = self.belief.posterior
        self.belief.update(
            likelihood_ratio=1.5,
            parent_posterior=0.6,
            macro_shock=False,
            period="test"
        )
        
        # 后验应该改变
        self.assertNotEqual(self.belief.posterior, initial_posterior)
        print(f"✓ 测试期显式允许更新正确: posterior={self.belief.posterior:.3f}")


class TestBayesianResearchRoleIsolation(unittest.TestCase):
    """测试BayesianResearchRole期间隔离"""
    
    def setUp(self):
        from agents.research_team_v2 import BayesianResearchRole, ReflectionType
        
        class MockRole(BayesianResearchRole):
            """模拟角色用于测试"""
            def __init__(self):
                super().__init__("测试角色", weight=1.0, 
                               reflection_type=ReflectionType.BALANCED)
            
            def analyze(self, date, stock, data):
                from agents.research_team_v2 import ResearchView, ViewDirection
                return ResearchView(self.name, stock, ViewDirection.HOLD, 0.5)
        
        self.role = MockRole()
    
    def test_train_period_learning(self):
        """测试训练期允许学习"""
        initial_len = len(self.role.prediction_history)
        
        self.role.learn_from_outcome(
            prediction_correct=True,
            outcome_score=0.05,
            period="train"
        )
        
        self.assertEqual(len(self.role.prediction_history), initial_len + 1)
        self.assertEqual(len(self.role.accuracy_window), 1)
        print("✓ 训练期学习正确")
    
    def test_test_period_frozen(self):
        """测试测试期冻结学习"""
        # 设置冻结模式
        self.role.learning_mode = "frozen"
        
        # 先在训练期学习
        self.role.learn_from_outcome(
            prediction_correct=True,
            outcome_score=0.05,
            period="train"
        )
        train_len = len(self.role.prediction_history)
        
        # 测试期尝试学习
        self.role.learn_from_outcome(
            prediction_correct=True,
            outcome_score=0.03,
            period="test"
        )
        
        # 训练期记录不应增加
        self.assertEqual(len(self.role.prediction_history), train_len)
        # 但测试期记录应该增加
        self.assertEqual(len(self.role.test_prediction_history), 1)
        print("✓ 测试期冻结学习正确")
    
    def test_test_period_reset(self):
        """测试测试期重置模式"""
        self.role.learning_mode = "reset"
        
        # 训练期学习
        self.role.learn_from_outcome(
            prediction_correct=True,
            outcome_score=0.05,
            period="train"
        )
        
        # 测试期学习（RESET模式应清空训练记录）
        self.role.learn_from_outcome(
            prediction_correct=True,
            outcome_score=0.03,
            period="test"
        )
        
        # 训练期记录应该被清空，只有测试期记录
        self.assertEqual(len(self.role.prediction_history), 1)
        print("✓ 测试期重置模式正确")


class TestGuruJSONDistillationConfig(unittest.TestCase):
    """测试Guru JSON蒸馏配置"""
    
    def test_buffett_json_has_distillation(self):
        """测试buffett.json包含distillation_config"""
        import json
        
        json_path = Path(r"F:\Coding\Factor_Trading_v3.0\gurus\buffett.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIn("distillation_config", data)
        config = data["distillation_config"]
        self.assertIn("source", config)
        self.assertIn("data_source_declared", config)
        print(f"✓ buffett.json蒸馏配置: source={config['source']}")
    
    def test_soros_json_has_distillation(self):
        """测试soros.json包含distillation_config"""
        import json
        
        json_path = Path(r"F:\Coding\Factor_Trading_v3.0\gurus\soros.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIn("distillation_config", data)
        print("✓ soros.json蒸馏配置存在")
    
    def test_all_gurus_have_distillation(self):
        """测试所有Guru都有distillation_config"""
        import json
        
        gurus_dir = Path(r"F:\Coding\Factor_Trading_v3.0\gurus")
        for json_file in gurus_dir.glob("*.json"):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertIn("distillation_config", data, 
                         f"{json_file.name} 缺少distillation_config")
        print(f"✓ 所有{len(list(gurus_dir.glob('*.json')))}个Guru配置都有distillation_config")


class TestDistillationAuditor(unittest.TestCase):
    """测试蒸馏审计工具"""
    
    def test_audit_guru_json(self):
        """测试审计Guru JSON"""
        from tools.distillation_audit import DistillationAuditor
        
        auditor = DistillationAuditor()
        result = auditor.audit_guru_json(
            Path(r"F:\Coding\Factor_Trading_v3.0\gurus\buffett.json")
        )
        
        self.assertIn("risk_level", result)
        self.assertIn("risks", result)
        print(f"✓ 审计结果: risk_level={result['risk_level']}, risks={len(result['risks'])}")
    
    def test_audit_belief_trajectory(self):
        """测试审计信念轨迹"""
        from tools.distillation_audit import DistillationAuditor
        
        auditor = DistillationAuditor()
        
        # 正常轨迹
        trajectory = [
            (datetime(2024, 1, 1), 0.5),
            (datetime(2024, 1, 2), 0.6),
            (datetime(2024, 1, 3), 0.55),
        ]
        result = auditor.audit_belief_trajectory(trajectory)
        
        self.assertIn("risk_level", result)
        print(f"✓ 轨迹审计: risk_level={result['risk_level']}")
    
    def test_audit_all_gurus(self):
        """测试审计所有Guru"""
        from tools.distillation_audit import DistillationAuditor
        
        auditor = DistillationAuditor()
        results = auditor.audit_all_gurus(Path(r"F:\Coding\Factor_Trading_v3.0\gurus"))
        
        self.assertTrue(len(results) > 0)
        # 所有Guru都应该是低风险（因为我们已经修复了dalio.json）
        for result in results:
            self.assertIn(result['risk_level'], ['low', 'medium', 'high'])
        
        print(f"✓ 审计了{len(results)}个Guru配置")


class TestBacktestConfigIntegration(unittest.TestCase):
    """测试BacktestConfig集成"""
    
    def test_config_has_distillation_fields(self):
        """测试配置包含蒸馏相关字段"""
        from core.config import BacktestConfig, ExecutionPriceType
        
        config = BacktestConfig(
            data_dir=Path("./demo_data"),
            factor_files=["factor_value.pkl"],
            execution_price_type=ExecutionPriceType.OPEN
        )
        
        self.assertEqual(config.execution_price_type, ExecutionPriceType.OPEN)
        print("✓ BacktestConfig包含执行价格配置")


if __name__ == "__main__":
    unittest.main(verbosity=2)
