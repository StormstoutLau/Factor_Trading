"""
GuruAgent v2 - 模块化设计
=======================

核心改进：
1. 数据与逻辑分离：Guru数据存储在JSON文件中，代码只负责加载和运行
2. 插件化注册：新增Guru只需添加JSON文件，无需修改代码
3. 统一接口：所有Guru通过相同的GuruAgent类实例化

目录结构：
gurus/
  ├── buffett.json      # 巴菲特数据
  ├── munger.json       # 芒格数据
  ├── soros.json        # 索罗斯数据
  ├── dalio.json        # 达里奥数据
  └── [new_guru].json   # 新增Guru只需添加JSON
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from agent_framework import BaseAgent, AgentConfig, AgentStyle, AgentSignal, SignalDirection
from config import FactorConfig, OptimizerConfig
from core.config import AgentDistillationConfig, DistillationSource
from data import DataManager
from factor import FactorCombiner, FactorPipeline

logger = logging.getLogger(__name__)


# ============================================================
# 1. JSON数据加载器
# ============================================================

class GuruDataLoader:
    """Guru数据加载器
    
    从JSON文件加载Guru配置，支持热加载
    """
    
    def __init__(self, data_dir: str | Path = "gurus"):
        self.data_dir = Path(data_dir)
        self._cache: dict[str, dict] = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有Guru JSON文件"""
        if not self.data_dir.exists():
            logger.warning(f"Guru数据目录不存在: {self.data_dir}")
            return
        
        for json_file in self.data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 使用文件名（不含扩展名）作为key
                guru_id = json_file.stem
                self._cache[guru_id] = data
                logger.info(f"加载Guru数据: {guru_id} -> {data.get('name', 'Unknown')}")
            except Exception as e:
                logger.error(f"加载 {json_file} 失败: {e}")
    
    def get(self, guru_id: str) -> Optional[dict]:
        """获取Guru数据"""
        return self._cache.get(guru_id)
    
    def list_gurus(self) -> list[str]:
        """列出所有可用Guru"""
        return list(self._cache.keys())
    
    def reload(self, guru_id: str | None = None):
        """热重载Guru数据
        
        Args:
            guru_id: 指定重载某个Guru，None则重载全部
        """
        if guru_id:
            file_path = self.data_dir / f"{guru_id}.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._cache[guru_id] = json.load(f)
                logger.info(f"热重载: {guru_id}")
        else:
            self._cache.clear()
            self._load_all()
            logger.info("热重载全部Guru数据")
    
    def get_guru_info(self, guru_id: str) -> dict[str, Any]:
        """获取Guru摘要信息"""
        data = self._cache.get(guru_id)
        if not data:
            return {}
        
        return {
            'id': guru_id,
            'name': data.get('name', ''),
            'english_name': data.get('english_name', ''),
            'core_philosophy': data.get('core_philosophy', ''),
            'mental_models_count': len(data.get('mental_models', [])),
            'heuristics_count': len(data.get('heuristics', [])),
            'position_style': data.get('position_style', 'unknown'),
            'preferred_factors': data.get('preferred_factors', {}),
        }


# ============================================================
# 2. 模块化GuruAgent
# ============================================================

class GuruAgentV2(BaseAgent):
    """模块化GuruAgent
    
    所有Guru共享同一个类，通过JSON配置区分行为
    
    使用方式：
        # 方式1：指定Guru ID
        agent = GuruAgentV2(guru_id='buffett')
        
        # 方式2：动态发现所有Guru并创建
        loader = GuruDataLoader('gurus')
        for guru_id in loader.list_gurus():
            agent = GuruAgentV2(guru_id=guru_id)
    
    新增Guru：
        1. 在 gurus/ 目录下创建 [guru_name].json
        2. 按照标准格式填写数据
        3. 无需修改任何代码
    """
    
    # 全局共享的数据加载器缓存（按目录隔离）
    _loader_cache: dict[str, GuruDataLoader] = {}

    def __init__(self,
                 guru_id: str,
                 agent_id: str | None = None,
                 initial_capital: float = 10_000_000.0,
                 target_count: int = 20,
                 max_weight: float = 0.15,
                 data_dir: str | Path = "gurus",
                 distillation_config: 'AgentDistillationConfig' | None = None):
        """
        Args:
            guru_id: Guru标识（对应JSON文件名）
            agent_id: Agent标识（默认使用 guru_{guru_id}）
            initial_capital: 初始资金
            target_count: 目标持股数
            max_weight: 单股最大权重
            data_dir: Guru数据目录
            distillation_config: 蒸馏配置（数据隔离）
        """
        # 初始化数据加载器（按目录缓存，避免重复加载）
        data_dir_str = str(data_dir)
        if data_dir_str not in GuruAgentV2._loader_cache:
            GuruAgentV2._loader_cache[data_dir_str] = GuruDataLoader(data_dir)

        # 加载Guru数据
        self.guru_data = GuruAgentV2._loader_cache[data_dir_str].get(guru_id)
        if self.guru_data is None:
            available = GuruAgentV2._loader_cache[data_dir_str].list_gurus()
            raise ValueError(f"未知Guru: {guru_id}。可用: {available}")
        
        self.guru_id = guru_id
        self.guru_name = self.guru_data.get('name', guru_id)
        self.guru_english_name = self.guru_data.get('english_name', guru_id)
        
        # 加载蒸馏配置
        self.distillation_config = self._load_distillation_config(distillation_config)
        
        # 验证蒸馏配置
        errors = self.distillation_config.validate()
        if errors:
            for error in errors:
                logger.warning(f"[{self.guru_id}] 蒸馏配置警告: {error}")
        
        # 构建Agent配置
        factor_files, factor_weights = self._build_factor_config()
        
        config = AgentConfig(
            agent_id=agent_id or f"guru_{guru_id}",
            name=f"{self.guru_name}Agent",
            style=AgentStyle.CUSTOM,
            factor_files=factor_files,
            factor_weights=factor_weights,
            factor_config=FactorConfig(
                winsorize_method='mad',
                winsorize_n=5.0,
                fill_method='median',
                standardize_method='zscore',
                reverse_factor=False
            ),
            rebalance_frequency='monthly',
            rebalance_day=1,
            optimizer_config=OptimizerConfig(
                method='equal_weight',
                target_count=target_count,
                max_weight=max_weight,
                select_top=True
            ),
            initial_capital=initial_capital,
            stop_loss=0.10,
            max_drawdown_limit=0.15
        )
        super().__init__(config)
        
        # 设置Guru专属信念
        self._setup_guru_beliefs_from_json()
        
        # 分析日志
        self.analysis_log: list[str] = []
        
        logger.info(f"GuruAgentV2初始化: [{self.agent_id}] {self.guru_name} | "
                   f"哲学: {self.guru_data.get('core_philosophy', '')[:30]}... | "
                   f"蒸馏来源: {self.distillation_config.source.value}")
    
    def _load_distillation_config(self, override_config=None):
        """加载蒸馏配置
        
        优先级：
        1. 传入的override_config
        2. JSON文件中的distillation_config
        3. 默认配置（MANUAL）
        """
        if override_config is not None:
            return override_config
        
        # 从JSON加载
        json_config = self.guru_data.get('distillation_config')
        if json_config:
            return AgentDistillationConfig.from_dict(json_config)

        # 默认配置
        return AgentDistillationConfig(
            source=DistillationSource.MANUAL,
            data_source_declared="人工编写，基于投资大师公开理念"
        )
    
    def set_period(self, period: str):
        """设置当前期间，测试期自动冻结"""
        self.current_period = period
        if period == "test" and self.distillation_config.frozen_in_test:
            # 测试期冻结信念更新
            if hasattr(self, 'belief_engine') and self.belief_engine:
                for layer_beliefs in self.belief_engine.beliefs.values():
                    for belief in layer_beliefs.values():
                        belief.allow_test_update = False
            logger.info(f"[{self.agent_id}] 测试期已冻结信念更新")
    
    def _build_factor_config(self) -> tuple[list[str], dict[str, float]]:
        """从JSON构建因子配置"""
        preferred = self.guru_data.get('preferred_factors', {})
        
        factor_files = []
        factor_weights = {}
        
        for factor_name, weight in preferred.items():
            if weight > 0:
                fname = f"{factor_name}.pkl"
                factor_files.append(fname)
                factor_weights[factor_name] = weight
        
        if not factor_files:
            factor_files = ['factor_value.pkl', 'factor_momentum.pkl']
            factor_weights = {'factor_value': 0.5, 'factor_momentum': 0.5}
        
        return factor_files, factor_weights
    
    def _setup_guru_beliefs_from_json(self):
        """从JSON设置Guru专属信念"""
        if self.belief_engine is None:
            return
        
        from hierarchical_bayesian_agent import BeliefLayer
        
        # 清空默认信念
        self.belief_engine.beliefs = {
            BeliefLayer.PHILOSOPHY: {},
            BeliefLayer.STYLE: {},
            BeliefLayer.TACTIC: {}
        }
        self.belief_engine.parent_map = {}
        
        # 理念层：核心哲学
        philosophy = self.guru_data.get('core_philosophy', '投资')[:10]
        self.belief_engine.register_belief(
            philosophy,
            BeliefLayer.PHILOSOPHY,
            0.8,
            tension_range=0.12
        )
        
        # 风格层：心智模型
        for model in self.guru_data.get('mental_models', [])[:3]:
            self.belief_engine.register_belief(
                model.get('name', 'unknown'),
                BeliefLayer.STYLE,
                0.6,
                parent_name=philosophy,
                tension_range=0.20
            )
        
        # 战术层：启发式
        for heuristic in self.guru_data.get('heuristics', [])[:2]:
            if self.guru_data.get('mental_models'):
                parent = self.guru_data['mental_models'][0].get('name', philosophy)
                self.belief_engine.register_belief(
                    heuristic.get('name', 'rule'),
                    BeliefLayer.TACTIC,
                    heuristic.get('weight', 1.0),
                    parent_name=parent,
                    tension_range=0.35
                )
    
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备因子数据"""
        pipeline = FactorPipeline(data_manager, self.cfg.factor_config)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        processed_factors = {}
        for fname in self.cfg.factor_files:
            raw = data_manager.load_factor(fname)
            key = fname.replace('.pkl', '')
            processed = pipeline.process(raw)
            processed_factors[key] = processed
        
        return combiner.combine(processed_factors)
    
    def generate_signals(self,
                        date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成Guru风格信号"""
        signals = []
        
        # 反思检查
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        valid_signal = composite_signal[tradable_mask].dropna()
        
        # 根据position_style调整目标持股数
        position_style = self.guru_data.get('position_style', 'concentrated')
        style_map = {
            'very_concentrated': 5,
            'concentrated': 10,
            'moderate': 20,
            'diversified': 30
        }
        target = style_map.get(position_style, self.cfg.target_count)
        
        selected = valid_signal.nlargest(target)
        
        # 生成分析日志
        analysis = self._generate_analysis(date, selected)
        self.analysis_log.append(analysis)
        
        for stock, score in selected.items():
            signals.append(AgentSignal(
                agent_id=self.agent_id,
                date=date,
                stock=stock,
                direction=SignalDirection.LONG,
                score=float(score),
                target_weight=1.0 / len(selected),
                metadata={
                    'style': 'guru',
                    'guru_id': self.guru_id,
                    'guru_name': self.guru_name,
                    'analysis': analysis,
                    'mental_models': [m.get('name', '') for m in self.guru_data.get('mental_models', [])[:3]]
                }
            ))
        
        self.signals_history.extend(signals)
        return signals
    
    def _generate_analysis(self, date: pd.Timestamp, 
                          selected: pd.Series) -> str:
        """生成Guru风格的分析日志"""
        dna = self.guru_data.get('expression_dna', {})
        
        opening = dna.get('opening', 'direct_conclusion')
        certainty = dna.get('certainty', 'high')
        
        lines = []
        
        # 开场
        if opening == 'direct_conclusion':
            lines.append(f"[{self.guru_name}] 今日选股{len(selected)}只。")
        elif opening == 'punchline':
            lines.append(f"[{self.guru_name}] {self.guru_data.get('heuristics', [{}])[0].get('rule', '')}")
        elif opening == 'philosophical_premise':
            lines.append(f"[{self.guru_name}] {self.guru_data.get('core_philosophy', '')}")
        elif opening == 'system_definition':
            lines.append(f"[{self.guru_name}] 今日配置基于{self.guru_data.get('core_philosophy', '')[:20]}...")
        
        # 心智模型
        models = self.guru_data.get('mental_models', [])
        if models:
            lines.append(f"应用心智模型: {', '.join(m.get('name', '') for m in models[:2])}")
        
        # 确定性
        if certainty == 'high':
            lines.append("这些选择符合我的投资原则。")
        elif certainty == 'absolute':
            lines.append("毫无疑问，这是正确的方向。")
        elif certainty == 'philosophical':
            lines.append("基于当前信息，这是最合理的推断。")
        elif certainty == 'systematic':
            lines.append("系统化分析后的最优配置。")
        
        # 盲区提醒
        blind_spots = self.guru_data.get('blind_spots', [])
        if blind_spots:
            lines.append(f"注意盲区: {', '.join(blind_spots[:2])}")
        
        return "\n".join(lines)
    
    def should_rebalance(self, date: pd.Timestamp,
                        current_portfolio: dict[str, Any]) -> bool:
        """判断是否调仓"""
        return date.day == self.cfg.rebalance_day
    
    def get_guru_report(self) -> dict[str, Any]:
        """获取Guru专属报告"""
        return {
            'guru_id': self.guru_id,
            'guru_name': self.guru_name,
            'guru_data_summary': {
                'name': self.guru_data.get('name'),
                'english_name': self.guru_data.get('english_name'),
                'core_philosophy': self.guru_data.get('core_philosophy'),
                'mental_models_count': len(self.guru_data.get('mental_models', [])),
                'heuristics_count': len(self.guru_data.get('heuristics', [])),
                'position_style': self.guru_data.get('position_style'),
                'preferred_factors': self.guru_data.get('preferred_factors'),
            },
            'mental_models': [
                {
                    'name': m.get('name'),
                    'type': m.get('model_type'),
                    'one_liner': m.get('one_liner'),
                    'factor_mapping': m.get('factor_mapping')
                }
                for m in self.guru_data.get('mental_models', [])
            ],
            'heuristics': [
                {
                    'name': h.get('name'),
                    'rule': h.get('rule'),
                    'weight': h.get('weight')
                }
                for h in self.guru_data.get('heuristics', [])
            ],
            'analysis_log_count': len(self.analysis_log),
            'recent_analysis': self.analysis_log[-3:] if self.analysis_log else [],
            'belief_report': self.get_belief_report()
        }
    
    @classmethod
    def create_all_gurus(cls,
                        data_dir: str | Path = "gurus",
                        initial_capital: float = 10_000_000.0) -> list['GuruAgentV2']:
        """工厂方法：创建所有可用的GuruAgent
        
        使用方式：
            all_gurus = GuruAgentV2.create_all_gurus()
            for agent in all_gurus:
                engine.register_agent(agent)
        """
        loader = GuruDataLoader(data_dir)
        agents = []
        
        for guru_id in loader.list_gurus():
            try:
                agent = cls(
                    guru_id=guru_id,
                    initial_capital=initial_capital
                )
                agents.append(agent)
            except Exception as e:
                logger.error(f"创建 {guru_id} 失败: {e}")
        
        logger.info(f"成功创建 {len(agents)}/{len(loader.list_gurus())} 个GuruAgent")
        return agents
    
    @classmethod
    def list_available_gurus(cls, data_dir: str | Path = "gurus") -> list[dict]:
        """列出所有可用的Guru信息"""
        loader = GuruDataLoader(data_dir)
        return [loader.get_guru_info(gid) for gid in loader.list_gurus()]


# ============================================================
# 3. 演示
# ============================================================

def demo_guru_agent_v2():
    """演示模块化GuruAgent"""
    print("=" * 70)
    print("GuruAgent v2 - 模块化设计演示")
    print("=" * 70)
    
    # 1. 列出所有可用Guru
    print("\n【可用Guru列表】")
    gurus = GuruAgentV2.list_available_gurus()
    for g in gurus:
        print(f"  {g['id']}: {g['name']} ({g['english_name']})")
        print(f"    哲学: {g['core_philosophy'][:40]}...")
        print(f"    心智模型: {g['mental_models_count']}个")
        print(f"    持仓风格: {g['position_style']}")
    
    # 2. 创建单个GuruAgent
    print(f"\n【创建单个GuruAgent】")
    buffett = GuruAgentV2(guru_id='buffett', initial_capital=20_000_000)
    print(f"  [{buffett.agent_id}] {buffett.name}")
    print(f"    因子配置: {buffett.cfg.factor_files}")
    print(f"    因子权重: {buffett.cfg.factor_weights}")
    
    # 3. 测试学习
    print(f"\n【测试贝叶斯学习】")
    for i in range(15):
        buffett.learn_from_outcome(prediction_correct=(i % 3 != 0), outcome_score=0.03)
    print(f"  预测记录: {len(buffett.prediction_history)}条")
    print(f"  最近准确率: {buffett.accuracy_window[-1]:.1%}")
    
    # 4. 测试反思
    print(f"\n【测试反思机制】")
    report = buffett.reflect()
    print(f"  over_reacting: {report.get('over_reacting_count', 0)}")
    print(f"  under_reacting: {report.get('under_reacting_count', 0)}")
    
    # 5. 获取Guru报告
    print(f"\n【Guru专属报告】")
    guru_report = buffett.get_guru_report()
    print(f"  心智模型:")
    for m in guru_report['mental_models']:
        print(f"    - {m['name']}: {m['one_liner']}")
    print(f"  分析日志数: {guru_report['analysis_log_count']}")
    
    # 6. 工厂方法：创建所有Guru
    print(f"\n【工厂方法：创建所有GuruAgent】")
    all_agents = GuruAgentV2.create_all_gurus(initial_capital=10_000_000)
    for agent in all_agents:
        print(f"  [{agent.agent_id}] {agent.name}")
        print(f"    持仓风格: {agent.guru_data.get('position_style')}")
        print(f"    目标持股: {agent.cfg.target_count}")
    
    print("\n" + "=" * 70)
    print("模块化GuruAgent演示完成")
    print("新增Guru只需在 gurus/ 目录添加JSON文件")
    print("=" * 70)


if __name__ == "__main__":
    demo_guru_agent_v2()
