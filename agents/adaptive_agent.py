"""
自适应Agent框架 - 动态风格学习机制
=====================================

借鉴 "Enhancing Academic Contribution.md" 中的核心思想：
1. 五层蒸馏模型：表达DNA → 心智模型 → 决策启发式 → 反模式 → 诚实边界
2. 六路并行Agent采集
3. 三重验证确保逻辑一致性
4. 贝叶斯学习反思机制

应用到量化投研场景：
- Agent不再硬编码风格，而是从数据中"学习"风格
- 通过历史回测表现动态调整策略参数
- 引入置信度量化和不确定性管理
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. Agent认知模型（五层蒸馏）
# ============================================================

@dataclass
class AgentCognition:
    """Agent认知模型 - 五层蒸馏结构
    
    借鉴 nuwa-skill 的五层模型：
    1. 表达DNA: Agent的"表达方式"（选股偏好、权重分配模式）
    2. 心智模型: 对市场的核心认知（如"均值回归"、"趋势跟踪"）
    3. 决策启发式: 具体的决策规则（如"RSI<30买入"）
    4. 反模式: 绝对不会做的事（如"不追高"、"不碰ST"）
    5. 诚实边界: Agent的局限性认知
    """
    
    # 1. 表达DNA
    expression_dna: dict[str, Any] = field(default_factory=lambda: {
        'position_concentration': 0.05,      # 默认单股5%
        'sector_preference': None,           # 行业偏好
        'market_cap_bias': 'none',           # 市值偏好: small/mid/large/none
        'turnover_tolerance': 'medium',      # 换手率容忍度
    })
    
    # 2. 心智模型
    mental_models: list[dict] = field(default_factory=lambda: [
        {'name': '均值回归', 'belief_strength': 0.5, 'applicable_regimes': ['震荡']},
        {'name': '趋势跟踪', 'belief_strength': 0.5, 'applicable_regimes': ['趋势']},
    ])
    
    # 3. 决策启发式
    heuristics: list[dict] = field(default_factory=lambda: [
        {'condition': 'RSI < 30', 'action': '买入', 'confidence': 0.6},
        {'condition': 'RSI > 70', 'action': '卖出', 'confidence': 0.6},
    ])
    
    # 4. 反模式（绝对不做的事）
    anti_patterns: list[str] = field(default_factory=lambda: [
        '不追涨超过5%的股票',
        '不持有停牌超过3天的股票',
        '不在财报前3天建仓',
    ])
    
    # 5. 诚实边界（局限性认知）
    honest_boundaries: list[str] = field(default_factory=lambda: [
        '无法预测黑天鹅事件',
        '在流动性危机时模型可能失效',
        '对小盘股（<50亿）的预测置信度较低',
    ])
    
    def to_dict(self) -> dict:
        return {
            'expression_dna': self.expression_dna,
            'mental_models': self.mental_models,
            'heuristics': self.heuristics,
            'anti_patterns': self.anti_patterns,
            'honest_boundaries': self.honest_boundaries
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> AgentCognition:
        return cls(
            expression_dna=data.get('expression_dna', {}),
            mental_models=data.get('mental_models', []),
            heuristics=data.get('heuristics', []),
            anti_patterns=data.get('anti_patterns', []),
            honest_boundaries=data.get('honest_boundaries', [])
        )


# ============================================================
# 2. 贝叶斯信念更新系统
# ============================================================

@dataclass
class BeliefState:
    """信念状态
    
    量化Agent对某个心智模型的置信度
    """
    model_name: str
    prior_probability: float = 0.5        # 先验概率
    posterior_probability: float = 0.5    # 后验概率
    evidence_count: int = 0               # 支持证据数量
    contradictory_count: int = 0          # 矛盾证据数量
    prediction_accuracy: float = 0.5      # 预测准确率
    
    def bayesian_update(self, likelihood_ratio: float):
        """贝叶斯更新
        
        P(H|E) = P(E|H) * P(H) / P(E)
        
        Args:
            likelihood_ratio: P(E|H) / P(E|~H)
        """
        prior_odds = self.prior_probability / (1 - self.prior_probability)
        posterior_odds = prior_odds * likelihood_ratio
        self.posterior_probability = posterior_odds / (1 + posterior_odds)
        self.prior_probability = self.posterior_probability
    
    def add_evidence(self, supports: bool, prediction_correct: bool | None = None):
        """添加证据"""
        if supports:
            self.evidence_count += 1
        else:
            self.contradictory_count += 1
        
        if prediction_correct is not None:
            # 更新预测准确率（指数移动平均）
            alpha = 0.1
            self.prediction_accuracy = (1 - alpha) * self.prediction_accuracy + \
                                       alpha * (1.0 if prediction_correct else 0.0)
    
    def get_confidence(self) -> float:
        """获取综合置信度"""
        # 综合：后验概率 + 预测准确率 + 证据平衡
        evidence_ratio = self.evidence_count / max(
            self.evidence_count + self.contradictory_count, 1
        )
        return 0.4 * self.posterior_probability + \
               0.4 * self.prediction_accuracy + \
               0.2 * evidence_ratio


class BayesianLearningEngine:
    """贝叶斯学习引擎
    
    实现Agent的动态学习机制：
    1. 预测-检验-修正闭环
    2. 置信度量化更新
    3. 模型间的竞争与选择
    """
    
    def __init__(self):
        self.beliefs: dict[str, BeliefState] = {}
        self.prediction_history: list[dict] = []
        self.learning_rate: float = 0.1
    
    def register_model(self, model_name: str, initial_probability: float = 0.5):
        """注册一个心智模型"""
        self.beliefs[model_name] = BeliefState(
            model_name=model_name,
            prior_probability=initial_probability
        )
    
    def make_prediction(self, model_name: str, 
                       context: dict[str, Any]) -> dict[str, Any]:
        """基于信念状态做出预测"""
        belief = self.beliefs.get(model_name)
        if belief is None:
            return {'prediction': None, 'confidence': 0.0}
        
        # 置信度影响预测强度
        confidence = belief.get_confidence()
        
        return {
            'prediction': model_name,  # 简化：预测就是模型本身的适用性
            'confidence': confidence,
            'timestamp': datetime.now()
        }
    
    def evaluate_prediction(self, model_name: str, 
                           actual_outcome: bool,
                           context: dict[str, Any]):
        """评估预测结果并更新信念"""
        belief = self.beliefs.get(model_name)
        if belief is None:
            return
        
        # 计算似然比
        if actual_outcome:
            # 预测正确：增加对该模型的信念
            likelihood_ratio = 1.5
            belief.add_evidence(supports=True, prediction_correct=True)
        else:
            # 预测错误：降低对该模型的信念
            likelihood_ratio = 0.67
            belief.add_evidence(supports=False, prediction_correct=False)
        
        # 贝叶斯更新
        belief.bayesian_update(likelihood_ratio)
        
        # 记录历史
        self.prediction_history.append({
            'model': model_name,
            'actual': actual_outcome,
            'timestamp': datetime.now(),
            'posterior': belief.posterior_probability
        })
    
    def select_best_model(self, context: dict[str, Any]) -> str | None:
        """选择当前最优模型"""
        if not self.beliefs:
            return None
        
        # 按后验概率排序
        sorted_beliefs = sorted(
            self.beliefs.items(),
            key=lambda x: x[1].get_confidence(),
            reverse=True
        )
        
        return sorted_beliefs[0][0]
    
    def get_model_weights(self) -> dict[str, float]:
        """获取所有模型的权重（Softmax归一化）"""
        if not self.beliefs:
            return {}
        
        confidences = {name: b.get_confidence() for name, b in self.beliefs.items()}
        
        # Softmax
        exp_scores = {k: np.exp(v * 5) for k, v in confidences.items()}  # *5放大差异
        total = sum(exp_scores.values())
        
        return {k: v / total for k, v in exp_scores.items()}
    
    def get_learning_summary(self) -> dict[str, Any]:
        """获取学习摘要"""
        return {
            'models': {
                name: {
                    'posterior': belief.posterior_probability,
                    'accuracy': belief.prediction_accuracy,
                    'evidence': belief.evidence_count,
                    'contradictions': belief.contradictory_count,
                    'confidence': belief.get_confidence()
                }
                for name, belief in self.beliefs.items()
            },
            'prediction_count': len(self.prediction_history),
            'best_model': self.select_best_model({})
        }


# ============================================================
# 3. 自适应Agent
# ============================================================

class AdaptiveAgent:
    """自适应Agent
    
    核心特性：
    1. 动态风格学习：从回测表现中学习最优风格
    2. 贝叶斯信念更新：量化置信度，概率化决策
    3. 多模型竞争：多个心智模型竞争，动态选择最优
    4. 不确定性管理：明确标注不确定领域
    """
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        
        # 认知模型
        self.cognition = AgentCognition()
        
        # 贝叶斯学习引擎
        self.learning_engine = BayesianLearningEngine()
        
        # 初始化心智模型
        self._initialize_models()
        
        # 回测表现跟踪
        self.performance_history: list[dict] = []
        self.current_regime: str = 'unknown'  # 当前市场 regime
        
        logger.info(f"自适应Agent初始化: [{agent_id}] {name}")
    
    def _initialize_models(self):
        """初始化心智模型"""
        models = [
            '均值回归',
            '趋势跟踪',
            '动量效应',
            '价值发现',
            '质量溢价',
            '小市值效应'
        ]
        
        for model in models:
            self.learning_engine.register_model(model, initial_probability=1.0/len(models))
    
    def adapt_to_regime(self, regime: str, 
                       historical_performance: dict[str, float]):
        """根据市场regime自适应调整
        
        Args:
            regime: 市场状态 ('趋势', '震荡', '熊市', '牛市')
            historical_performance: 各模型在该regime下的历史表现
        """
        self.current_regime = regime
        
        logger.info(f"[{self.agent_id}] 适应市场状态: {regime}")
        
        # 根据历史表现更新模型信念
        for model_name, performance in historical_performance.items():
            if model_name in self.learning_engine.beliefs:
                # 性能越好，似然比越高
                if performance > 0:
                    likelihood_ratio = 1.0 + performance * 2
                else:
                    likelihood_ratio = max(0.3, 1.0 + performance)
                
                self.learning_engine.beliefs[model_name].bayesian_update(likelihood_ratio)
        
        # 更新表达DNA
        self._update_expression_dna(regime)
    
    def _update_expression_dna(self, regime: str):
        """根据市场状态更新表达DNA"""
        if regime == '趋势':
            self.cognition.expression_dna.update({
                'position_concentration': 0.08,  # 趋势市场更集中
                'market_cap_bias': 'none',
            })
        elif regime == '震荡':
            self.cognition.expression_dna.update({
                'position_concentration': 0.04,  # 震荡市场更分散
                'market_cap_bias': 'small',      # 小盘股在震荡中更有优势
            })
        elif regime == '熊市':
            self.cognition.expression_dna.update({
                'position_concentration': 0.03,  # 熊市降低仓位
                'market_cap_bias': 'large',      # 大盘股防御
            })
        elif regime == '牛市':
            self.cognition.expression_dna.update({
                'position_concentration': 0.10,  # 牛市更激进
                'market_cap_bias': 'small',      # 小盘股弹性大
            })
    
    def generate_signals(self, 
                        date: pd.Timestamp,
                        factor_data: pd.DataFrame,
                        tradable_mask: pd.Series) -> pd.Series:
        """生成交易信号
        
        根据当前最优模型的权重，动态组合信号
        """
        # 获取模型权重
        model_weights = self.learning_engine.get_model_weights()
        
        # 根据权重组合因子
        composite_signal = pd.Series(0.0, index=factor_data.columns)
        
        for model_name, weight in model_weights.items():
            # 根据模型类型应用不同的因子处理
            model_signal = self._apply_model(model_name, factor_data, tradable_mask)
            composite_signal += model_signal * weight
        
        # 只选可交易股票
        valid_signal = composite_signal[tradable_mask].dropna()
        
        return valid_signal
    
    def _apply_model(self, model_name: str, 
                    factor_data: pd.DataFrame,
                    tradable_mask: pd.Series) -> pd.Series:
        """应用特定心智模型"""
        if model_name == '均值回归':
            # 选低分股票（反转）
            return -factor_data.iloc[-1]
        elif model_name == '趋势跟踪':
            # 选高分股票（动量）
            return factor_data.iloc[-1]
        elif model_name == '动量效应':
            # 近期涨幅最大的
            return factor_data.iloc[-1]
        elif model_name == '价值发现':
            # 低PE（假设factor是PE）
            return -factor_data.iloc[-1]
        elif model_name == '质量溢价':
            # 高ROE（假设factor是ROE）
            return factor_data.iloc[-1]
        elif model_name == '小市值效应':
            # 小市值（假设factor是市值倒数）
            return factor_data.iloc[-1]
        else:
            return factor_data.iloc[-1]
    
    def update_from_backtest(self, 
                            backtest_results: dict[str, Any]):
        """从回测结果中学习
        
        Args:
            backtest_results: 回测结果，包含各模型的表现
        """
        logger.info(f"[{self.agent_id}] 从回测结果学习...")
        
        # 提取各模型的表现
        for model_name in self.learning_engine.beliefs.keys():
            # 假设backtest_results包含各模型的夏普比率
            sharpe = backtest_results.get(f'{model_name}_sharpe', 0.0)
            
            # 评估预测（正夏普 = 预测正确）
            self.learning_engine.evaluate_prediction(
                model_name,
                actual_outcome=(sharpe > 0.5),
                context={'regime': self.current_regime}
            )
        
        # 保存表现历史
        self.performance_history.append({
            'date': datetime.now(),
            'regime': self.current_regime,
            'results': backtest_results,
            'model_weights': self.learning_engine.get_model_weights()
        })
        
        logger.info(f"[{self.agent_id}] 学习完成")
        logger.info(f"  当前模型权重: {self.learning_engine.get_model_weights()}")
    
    def get_cognition_report(self) -> dict[str, Any]:
        """获取认知报告"""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'current_regime': self.current_regime,
            'cognition': self.cognition.to_dict(),
            'learning': self.learning_engine.get_learning_summary(),
            'performance_count': len(self.performance_history)
        }
    
    def save_state(self, filepath: Path):
        """保存Agent状态"""
        state = {
            'agent_id': self.agent_id,
            'name': self.name,
            'cognition': self.cognition.to_dict(),
            'beliefs': {
                name: {
                    'prior': b.prior_probability,
                    'posterior': b.posterior_probability,
                    'evidence': b.evidence_count,
                    'accuracy': b.prediction_accuracy
                }
                for name, b in self.learning_engine.beliefs.items()
            },
            'performance_history': self.performance_history[-100:]  # 最近100条
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Agent状态已保存: {filepath}")
    
    def load_state(self, filepath: Path):
        """加载Agent状态"""
        if not filepath.exists():
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        self.agent_id = state.get('agent_id', self.agent_id)
        self.name = state.get('name', self.name)
        self.cognition = AgentCognition.from_dict(state.get('cognition', {}))
        
        # 恢复信念状态
        for name, b_data in state.get('beliefs', {}).items():
            if name in self.learning_engine.beliefs:
                belief = self.learning_engine.beliefs[name]
                belief.prior_probability = b_data.get('prior', 0.5)
                belief.posterior_probability = b_data.get('posterior', 0.5)
                belief.evidence_count = b_data.get('evidence', 0)
                belief.prediction_accuracy = b_data.get('accuracy', 0.5)
        
        self.performance_history = state.get('performance_history', [])
        
        logger.info(f"Agent状态已加载: {filepath}")


# ============================================================
# 4. Agent风格蒸馏器（从硬编码到学习）
# ============================================================

class AgentStyleDistiller:
    """Agent风格蒸馏器
    
    将硬编码的Agent风格转化为可学习的认知模型。
    
    借鉴 nuwa-skill 的六路并行采集思想：
    1. 历史回测数据 → 提取有效模式
    2. 因子IC分析 → 识别有效因子
    3. 市场环境分类 → 识别适用场景
    4. 交易记录分析 → 提取决策规则
    5. 失败案例总结 → 识别反模式
    6. 时间线追踪 → 识别风格演化
    """
    
    def __init__(self):
        self.collected_patterns: list[dict] = []
    
    def distill_from_backtest(self, 
                             backtest_data: pd.DataFrame,
                             trades_df: pd.DataFrame,
                             factor_data: dict[str, pd.DataFrame]) -> AgentCognition:
        """从回测数据中蒸馏Agent风格
        
        Args:
            backtest_data: 回测结果数据
            trades_df: 交易记录
            factor_data: 各因子数据
            
        Returns:
            蒸馏出的认知模型
        """
        cognition = AgentCognition()
        
        # 1. 分析交易记录 → 提取表达DNA
        cognition.expression_dna = self._distill_expression_dna(trades_df)
        
        # 2. 分析因子IC → 提取心智模型
        cognition.mental_models = self._distill_mental_models(factor_data, backtest_data)
        
        # 3. 分析交易时机 → 提取决策启发式
        cognition.heuristics = self._distill_heuristics(trades_df, factor_data)
        
        # 4. 分析失败交易 → 提取反模式
        cognition.anti_patterns = self._distill_anti_patterns(trades_df, backtest_data)
        
        # 5. 分析局限性 → 提取诚实边界
        cognition.honest_boundaries = self._distill_honest_boundaries(backtest_data)
        
        return cognition
    
    def _distill_expression_dna(self, trades_df: pd.DataFrame) -> dict:
        """从交易记录中提取表达DNA"""
        if trades_df.empty:
            return {}
        
        # 分析持仓集中度
        position_sizes = trades_df.groupby('date')['amount'].sum()
        avg_position = trades_df['amount'].mean()
        
        # 分析行业偏好
        # sector_counts = trades_df['sector'].value_counts() if 'sector' in trades_df else pd.Series()
        
        return {
            'avg_position_size': float(avg_position),
            'position_concentration': float(trades_df['amount'].std() / avg_position) if avg_position > 0 else 0,
            'trade_frequency': len(trades_df) / trades_df['date'].nunique() if trades_df['date'].nunique() > 0 else 0,
        }
    
    def _distill_mental_models(self, 
                              factor_data: dict[str, pd.DataFrame],
                              backtest_data: pd.DataFrame) -> list[dict]:
        """从因子数据中提取心智模型"""
        models = []
        
        # 分析各因子的有效性
        for factor_name, factor_df in factor_data.items():
            # 计算因子与收益的相关系数
            # 简化：假设因子值越大越好
            models.append({
                'name': factor_name,
                'belief_strength': 0.5,  # 初始中性
                'applicable_regimes': ['unknown']
            })
        
        return models
    
    def _distill_heuristics(self, 
                           trades_df: pd.DataFrame,
                           factor_data: dict[str, pd.DataFrame]) -> list[dict]:
        """从交易记录中提取决策启发式"""
        heuristics = []
        
        # 简化：提取常见的交易模式
        if not trades_df.empty:
            # 分析买入时机
            buy_trades = trades_df[trades_df['side'] == 'BUY']
            if not buy_trades.empty:
                heuristics.append({
                    'condition': '价格低于均线',
                    'action': '买入',
                    'confidence': 0.6,
                    'source': '历史交易模式'
                })
        
        return heuristics
    
    def _distill_anti_patterns(self, 
                              trades_df: pd.DataFrame,
                              backtest_data: pd.DataFrame) -> list[str]:
        """从失败交易中提取反模式"""
        anti_patterns = []
        
        # 分析亏损交易
        if 'pnl' in trades_df.columns:
            losing_trades = trades_df[trades_df['pnl'] < 0]
            if len(losing_trades) > 0:
                anti_patterns.append('避免在高点追涨')
        
        return anti_patterns
    
    def _distill_honest_boundaries(self, 
                                  backtest_data: pd.DataFrame) -> list[str]:
        """提取诚实边界"""
        boundaries = [
            '无法预测市场崩盘',
            '在极端波动时模型可能失效',
            '对小盘股的预测置信度较低',
        ]
        
        return boundaries


# ============================================================
# 5. 使用示例
# ============================================================

def example_usage():
    """使用示例"""
    # 创建自适应Agent
    agent = AdaptiveAgent(agent_id="adaptive_001", name="自适应价值Agent")
    
    # 模拟市场状态变化
    regimes = ['震荡', '趋势', '熊市', '牛市']
    
    for regime in regimes:
        # 模拟历史表现
        historical_perf = {
            '均值回归': np.random.normal(0.3, 0.2),
            '趋势跟踪': np.random.normal(0.5 if regime == '趋势' else -0.1, 0.2),
            '动量效应': np.random.normal(0.4 if regime == '牛市' else -0.2, 0.2),
            '价值发现': np.random.normal(0.6 if regime == '熊市' else 0.2, 0.2),
        }
        
        # Agent自适应
        agent.adapt_to_regime(regime, historical_perf)
        
        # 查看当前认知
        report = agent.get_cognition_report()
        print(f"\n市场状态: {regime}")
        print(f"最优模型: {report['learning']['best_model']}")
        print(f"模型权重: {report['learning']['models']}")
    
    # 保存状态
    agent.save_state(Path("agent_state.json"))


if __name__ == "__main__":
    example_usage()
