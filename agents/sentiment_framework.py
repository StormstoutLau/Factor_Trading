"""
非结构化数据（新闻舆情）分析框架
=====================================

借鉴 Crucix 开源情报分析系统的核心设计：
1. 分层采集架构（RSS → Telegram → GDELT）
2. 智能融合与去重
3. LLM 驱动的情感分析和信号提取
4. Delta 检测（变化追踪）
5. 三级告警机制

适配到量化投研场景：
- 新闻舆情 → 股票情感信号
- 多源融合 → 综合市场情绪
- Delta 检测 → 舆情突变预警
- LLM 分析 → 事件驱动交易信号
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. 数据模型定义
# ============================================================

class SentimentPolarity(Enum):
    """情感极性"""
    VERY_NEGATIVE = -2    # 极度负面
    NEGATIVE = -1         # 负面
    NEUTRAL = 0           # 中性
    POSITIVE = 1          # 正面
    VERY_POSITIVE = 2     # 极度正面


class NewsUrgency(Enum):
    """新闻紧急程度"""
    ROUTINE = 0           # 常规
    PRIORITY = 1          # 重要
    FLASH = 2             # 紧急


@dataclass
class NewsItem:
    """新闻条目"""
    id: str                           # 唯一标识
    title: str                        # 标题
    content: str                      # 内容摘要
    source: str                       # 来源
    timestamp: datetime               # 发布时间
    stock_codes: list[str]            # 相关股票代码
    sector: str | None = None         # 相关行业
    polarity: SentimentPolarity = SentimentPolarity.NEUTRAL
    urgency: NewsUrgency = NewsUrgency.ROUTINE
    confidence: float = 0.5           # 置信度 (0-1)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content[:200],
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'stock_codes': self.stock_codes,
            'sector': self.sector,
            'polarity': self.polarity.name,
            'urgency': self.urgency.name,
            'confidence': self.confidence
        }


@dataclass
class SentimentSignal:
    """情感信号
    
    聚合多源新闻后，对单只股票的情感判断
    """
    stock: str                        # 股票代码
    date: pd.Timestamp                # 日期
    composite_score: float            # 综合情感得分 (-1 ~ 1)
    polarity: SentimentPolarity       # 情感极性
    confidence: float                 # 置信度
    news_count: int                   # 相关新闻数量
    sources: list[str]                # 来源列表
    urgency_level: int                # 最高紧急程度 (0-2)
    delta_change: float | None = None # 相比前一期的变化
    
    def to_series(self) -> pd.Series:
        return pd.Series({
            'composite_score': self.composite_score,
            'confidence': self.confidence,
            'news_count': self.news_count,
            'urgency_level': self.urgency_level,
            'delta_change': self.delta_change
        })


# ============================================================
# 2. 新闻采集层（模拟）
# ============================================================

class NewsCollector:
    """新闻采集器
    
    模拟从多个来源采集新闻。
    实际生产环境中，应接入真实的API：
    - 财经新闻API（如Tushare、AkShare）
    - 社交媒体API（微博、雪球）
    - 公告披露（巨潮资讯）
    """
    
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir
        self.sources = ['财经新闻', '公司公告', '研报', '社交媒体', '行业新闻']
        
        # 情感关键词词典（简化版）
        self.positive_keywords = [
            '利好', '增长', '盈利', '超预期', '突破', '签约', '合作',
            '订单', '扩产', '创新', '领先', '优势', '强劲', '积极',
            'positive', 'growth', 'profit', 'breakthrough', 'partnership'
        ]
        self.negative_keywords = [
            '利空', '下滑', '亏损', '不及预期', '违约', '诉讼', '监管',
            '处罚', '停产', '裁员', '风险', '下滑', '负面', '危机',
            'negative', 'decline', 'loss', 'default', 'lawsuit', 'crisis'
        ]
        self.urgent_keywords = [
            '突发', '紧急', '重大', '停牌', '重组', '收购', '破产',
            '突发', '闪崩', '暴涨', '暴跌', '黑天鹅', '公告',
            'breaking', 'urgent', 'major', 'suspension', 'bankruptcy'
        ]
    
    def collect_for_date(self, date: pd.Timestamp, 
                        stock_codes: list[str]) -> list[NewsItem]:
        """采集某日的所有新闻（模拟）
        
        实际应调用真实API获取新闻数据
        """
        news_items = []
        
        # 为每只股票生成模拟新闻
        np.random.seed(int(date.timestamp()) % 10000)
        
        for stock in stock_codes:
            # 每天每只股票 0-3 条新闻
            n_news = np.random.poisson(1.5)
            
            for i in range(n_news):
                # 随机生成情感倾向
                sentiment_roll = np.random.random()
                
                if sentiment_roll < 0.3:
                    polarity = SentimentPolarity.NEGATIVE
                    keywords = np.random.choice(self.negative_keywords, 2)
                elif sentiment_roll < 0.7:
                    polarity = SentimentPolarity.NEUTRAL
                    keywords = ['正常', '平稳']
                else:
                    polarity = SentimentPolarity.POSITIVE
                    keywords = np.random.choice(self.positive_keywords, 2)
                
                # 紧急程度
                urgent_roll = np.random.random()
                if urgent_roll < 0.05:
                    urgency = NewsUrgency.FLASH
                elif urgent_roll < 0.2:
                    urgency = NewsUrgency.PRIORITY
                else:
                    urgency = NewsUrgency.ROUTINE
                
                # 生成新闻内容
                title = f"{' '.join(keywords)}：{stock}相关动态"
                content = f"据{np.random.choice(self.sources)}报道，{stock}{' '.join(keywords)}..."
                
                news_id = hashlib.md5(
                    f"{stock}_{date}_{i}".encode()
                ).hexdigest()[:12]
                
                news_items.append(NewsItem(
                    id=news_id,
                    title=title,
                    content=content,
                    source=np.random.choice(self.sources),
                    timestamp=date,
                    stock_codes=[stock],
                    polarity=polarity,
                    urgency=urgency,
                    confidence=np.random.uniform(0.5, 0.95)
                ))
        
        return news_items
    
    def collect_from_csv(self, csv_path: Path) -> list[NewsItem]:
        """从CSV文件加载历史新闻数据"""
        if not csv_path.exists():
            return []
        
        df = pd.read_csv(csv_path, encoding='utf-8')
        news_items = []
        
        for _, row in df.iterrows():
            news_items.append(NewsItem(
                id=str(row.get('id', '')),
                title=str(row.get('title', '')),
                content=str(row.get('content', '')),
                source=str(row.get('source', '')),
                timestamp=pd.to_datetime(row.get('timestamp', datetime.now())),
                stock_codes=str(row.get('stock_codes', '')).split(','),
                polarity=SentimentPolarity[row.get('polarity', 'NEUTRAL')],
                urgency=NewsUrgency[row.get('urgency', 'ROUTINE')],
                confidence=float(row.get('confidence', 0.5))
            ))
        
        return news_items


# ============================================================
# 3. 情感分析引擎
# ============================================================

class SentimentAnalyzer:
    """情感分析引擎
    
    对新闻进行情感分析，生成情感信号。
    当前使用基于规则的方法，可扩展为LLM驱动。
    """
    
    def __init__(self):
        # 情感词典（可扩展为更复杂的模型）
        self.sentiment_dict = self._load_sentiment_dict()
        
        # LLM 配置（可选）
        self.use_llm = False
        self.llm_provider = None
    
    def _load_sentiment_dict(self) -> dict[str, float]:
        """加载情感词典"""
        return {
            # 正面词汇
            '利好': 1.0, '增长': 0.8, '盈利': 0.9, '超预期': 1.0,
            '突破': 0.9, '签约': 0.7, '合作': 0.6, '订单': 0.7,
            '扩产': 0.6, '创新': 0.7, '领先': 0.8, '优势': 0.7,
            '强劲': 0.8, '积极': 0.6, 'positive': 0.8, 'growth': 0.8,
            'profit': 0.9, 'breakthrough': 0.9, 'partnership': 0.6,
            
            # 负面词汇
            '利空': -1.0, '下滑': -0.7, '亏损': -0.9, '不及预期': -0.8,
            '违约': -1.0, '诉讼': -0.8, '监管': -0.5, '处罚': -0.7,
            '停产': -0.9, '裁员': -0.7, '风险': -0.5, '负面': -0.6,
            '危机': -0.9, 'negative': -0.8, 'decline': -0.7,
            'loss': -0.9, 'default': -1.0, 'lawsuit': -0.8,
            'crisis': -0.9, 'bankruptcy': -1.0,
        }
    
    def analyze(self, news_items: list[NewsItem]) -> list[NewsItem]:
        """对新闻列表进行情感分析"""
        analyzed = []
        
        for item in news_items:
            # 基于规则的情感分析
            score = self._rule_based_sentiment(item)
            item.confidence = min(abs(score) + 0.3, 0.95)
            
            # 映射到情感极性
            if score > 0.5:
                item.polarity = SentimentPolarity.VERY_POSITIVE
            elif score > 0.1:
                item.polarity = SentimentPolarity.POSITIVE
            elif score < -0.5:
                item.polarity = SentimentPolarity.VERY_NEGATIVE
            elif score < -0.1:
                item.polarity = SentimentPolarity.NEGATIVE
            else:
                item.polarity = SentimentPolarity.NEUTRAL
            
            analyzed.append(item)
        
        return analyzed
    
    def _rule_based_sentiment(self, item: NewsItem) -> float:
        """基于规则的情感分析"""
        text = f"{item.title} {item.content}"
        score = 0.0
        count = 0
        
        for word, weight in self.sentiment_dict.items():
            if word in text:
                score += weight
                count += 1
        
        if count == 0:
            return 0.0
        
        return score / count
    
    def analyze_with_llm(self, news_items: list[NewsItem]) -> list[NewsItem]:
        """使用LLM进行情感分析（高级功能）

        当前为预留接口，实际部署时需：
        1. 配置 llm_provider（如 OpenAI, Anthropic 客户端）
        2. 实现 LLM 调用逻辑
        3. 解析 LLM 返回的情感标签和置信度
        """
        if not self.use_llm or self.llm_provider is None:
            return self.analyze(news_items)

        # 预留：LLM情感分析实现
        # 示例代码：
        #   for item in news_items:
        #       response = self.llm_provider.chat.completions.create(...)
        #       item.sentiment = parse_sentiment(response)
        #       item.confidence = parse_confidence(response)
        #   return news_items
        return self.analyze(news_items)


# ============================================================
# 4. 信号聚合与Delta检测
# ============================================================

class SentimentAggregator:
    """情感信号聚合器
    
    借鉴 Crucix 的 Delta 检测机制：
    - 跨时间周期比对
    - 检测情感突变
    - 三级信号分级
    """
    
    def __init__(self, lookback_window: int = 5):
        """
        Args:
            lookback_window: 回看窗口（交易日）
        """
        self.lookback_window = lookback_window
        self.history: dict[str, list[SentimentSignal]] = {}  # stock -> signals
    
    def aggregate(self, date: pd.Timestamp,
                  news_items: list[NewsItem]) -> dict[str, SentimentSignal]:
        """聚合当日新闻，生成情感信号
        
        Args:
            date: 日期
            news_items: 当日新闻列表
            
        Returns:
            每只股票的情感信号
        """
        # 按股票分组
        stock_news: dict[str, list[NewsItem]] = {}
        for item in news_items:
            for stock in item.stock_codes:
                if stock not in stock_news:
                    stock_news[stock] = []
                stock_news[stock].append(item)
        
        signals = {}
        
        for stock, items in stock_news.items():
            signal = self._compute_signal(stock, date, items)
            signals[stock] = signal
            
            # 保存历史
            if stock not in self.history:
                self.history[stock] = []
            self.history[stock].append(signal)
        
        return signals
    
    def _compute_signal(self, stock: str, date: pd.Timestamp,
                        items: list[NewsItem]) -> SentimentSignal:
        """计算单只股票的情感信号"""
        if not items:
            return SentimentSignal(
                stock=stock, date=date,
                composite_score=0.0,
                polarity=SentimentPolarity.NEUTRAL,
                confidence=0.0, news_count=0,
                sources=[], urgency_level=0
            )
        
        # 加权平均情感得分
        total_weight = 0.0
        weighted_score = 0.0
        
        for item in items:
            # 权重 = 置信度 × 紧急程度权重
            urgency_weight = 1.0 + item.urgency.value * 0.5
            weight = item.confidence * urgency_weight
            
            score = item.polarity.value * item.confidence
            weighted_score += score * weight
            total_weight += weight
        
        composite_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # 计算Delta（变化）
        delta_change = self._compute_delta(stock, composite_score)
        
        # 确定极性
        if composite_score > 0.5:
            polarity = SentimentPolarity.VERY_POSITIVE
        elif composite_score > 0.1:
            polarity = SentimentPolarity.POSITIVE
        elif composite_score < -0.5:
            polarity = SentimentPolarity.VERY_NEGATIVE
        elif composite_score < -0.1:
            polarity = SentimentPolarity.NEGATIVE
        else:
            polarity = SentimentPolarity.NEUTRAL
        
        # 最高紧急程度
        urgency_level = max(item.urgency.value for item in items)
        
        return SentimentSignal(
            stock=stock,
            date=date,
            composite_score=composite_score,
            polarity=polarity,
            confidence=total_weight / len(items),
            news_count=len(items),
            sources=list(set(item.source for item in items)),
            urgency_level=urgency_level,
            delta_change=delta_change
        )
    
    def _compute_delta(self, stock: str, current_score: float) -> float | None:
        """计算情感得分的变化"""
        if stock not in self.history or len(self.history[stock]) == 0:
            return None
        
        # 取上一期的得分
        prev_score = self.history[stock][-1].composite_score
        return current_score - prev_score
    
    def detect_anomalies(self, date: pd.Timestamp) -> list[dict[str, Any]]:
        """检测情感异常（借鉴 Crucix 的 Delta 检测）
        
        Returns:
            异常信号列表
        """
        anomalies = []
        
        for stock, history in self.history.items():
            if len(history) < 2:
                continue
            
            latest = history[-1]
            
            # 检测条件1：情感突变（Delta > 阈值）
            if latest.delta_change is not None and abs(latest.delta_change) > 1.0:
                anomalies.append({
                    'type': 'sentiment_spike',
                    'stock': stock,
                    'date': date,
                    'severity': 'HIGH' if abs(latest.delta_change) > 1.5 else 'MEDIUM',
                    'description': f"情感得分突变: {latest.delta_change:+.2f}",
                    'current_score': latest.composite_score,
                    'previous_score': latest.composite_score - latest.delta_change
                })
            
            # 检测条件2：紧急新闻集中爆发
            if latest.urgency_level >= 2 and latest.news_count >= 3:
                anomalies.append({
                    'type': 'urgent_news_cluster',
                    'stock': stock,
                    'date': date,
                    'severity': 'HIGH',
                    'description': f"紧急新闻集中爆发: {latest.news_count}条",
                    'news_count': latest.news_count
                })
            
            # 检测条件3：情感持续恶化
            if len(history) >= 3:
                recent_scores = [h.composite_score for h in history[-3:]]
                if all(s < -0.3 for s in recent_scores) and \
                   recent_scores[-1] < recent_scores[0]:
                    anomalies.append({
                        'type': 'persistent_negative',
                        'stock': stock,
                        'date': date,
                        'severity': 'MEDIUM',
                        'description': "情感持续恶化",
                        'trend': recent_scores
                    })
        
        return anomalies


# ============================================================
# 5. 情感因子生成器（与量化框架对接）
# ============================================================

class SentimentFactorGenerator:
    """情感因子生成器
    
    将情感信号转换为量化因子（DataFrame格式），
    可直接接入现有的 FactorPipeline
    """
    
    def __init__(self, aggregator: SentimentAggregator):
        self.aggregator = aggregator
    
    def generate_factor(self, dates: pd.DatetimeIndex,
                        stock_codes: list[str]) -> pd.DataFrame:
        """生成情感因子数据
        
        Args:
            dates: 交易日序列
            stock_codes: 股票代码列表
            
        Returns:
            情感因子 DataFrame (index=dates, columns=stock_codes)
        """
        # 初始化结果矩阵
        factor_data = pd.DataFrame(
            np.nan,
            index=dates,
            columns=stock_codes
        )
        
        # 收集器
        collector = NewsCollector()
        analyzer = SentimentAnalyzer()
        
        logger.info(f"生成情感因子: {len(dates)}天 × {len(stock_codes)}只股票")
        
        for date in dates:
            # 1. 采集新闻
            news_items = collector.collect_for_date(date, stock_codes)
            
            if not news_items:
                continue
            
            # 2. 情感分析
            analyzed_items = analyzer.analyze(news_items)
            
            # 3. 聚合信号
            signals = self.aggregator.aggregate(date, analyzed_items)
            
            # 4. 填充因子矩阵
            for stock, signal in signals.items():
                if stock in factor_data.columns:
                    factor_data.loc[date, stock] = signal.composite_score
        
        # 前向填充缺失值
        factor_data = factor_data.ffill(axis=0)
        
        logger.info(f"情感因子生成完成: {factor_data.shape}")
        
        return factor_data
    
    def generate_multi_factors(self, dates: pd.DatetimeIndex,
                               stock_codes: list[str]) -> dict[str, pd.DataFrame]:
        """生成多维度情感因子
        
        Returns:
            多个因子的字典
                - 'sentiment_score': 综合情感得分
                - 'sentiment_confidence': 置信度
                - 'sentiment_urgency': 紧急程度
                - 'sentiment_delta': 变化率
        """
        collector = NewsCollector()
        analyzer = SentimentAnalyzer()
        
        score_df = pd.DataFrame(np.nan, index=dates, columns=stock_codes)
        confidence_df = pd.DataFrame(np.nan, index=dates, columns=stock_codes)
        urgency_df = pd.DataFrame(np.nan, index=dates, columns=stock_codes)
        delta_df = pd.DataFrame(np.nan, index=dates, columns=stock_codes)
        
        for date in dates:
            news_items = collector.collect_for_date(date, stock_codes)
            
            if not news_items:
                continue
            
            analyzed_items = analyzer.analyze(news_items)
            signals = self.aggregator.aggregate(date, analyzed_items)
            
            for stock, signal in signals.items():
                if stock in stock_codes:
                    score_df.loc[date, stock] = signal.composite_score
                    confidence_df.loc[date, stock] = signal.confidence
                    urgency_df.loc[date, stock] = signal.urgency_level
                    delta_df.loc[date, stock] = signal.delta_change or 0.0
        
        # 前向填充
        score_df = score_df.ffill(axis=0)
        confidence_df = confidence_df.ffill(axis=0)
        urgency_df = urgency_df.ffill(axis=0)
        delta_df = delta_df.ffill(axis=0)
        
        return {
            'sentiment_score': score_df,
            'sentiment_confidence': confidence_df,
            'sentiment_urgency': urgency_df,
            'sentiment_delta': delta_df
        }
    
    def save_factors(self, factors: dict[str, pd.DataFrame], 
                    output_dir: Path) -> None:
        """保存因子到pkl文件"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for factor_name, factor_data in factors.items():
            filepath = output_dir / f"factor_{factor_name}.pkl"
            factor_data.to_pickle(filepath)
            logger.info(f"保存因子: {filepath}")


# ============================================================
# 6. 实时监控告警（借鉴 Crucix 告警机制）
# ============================================================

class SentimentAlertEngine:
    """情感告警引擎
    
    三级告警机制：
    - FLASH: 情感极端突变，需立即关注
    - PRIORITY: 显著情感变化，建议关注
    - ROUTINE: 常规情感更新
    """
    
    def __init__(self):
        self.alert_history: list[dict] = []
        self.rate_limiter = {
            'FLASH': {'last_sent': None, 'cooldown_minutes': 15},
            'PRIORITY': {'last_sent': None, 'cooldown_minutes': 60},
            'ROUTINE': {'last_sent': None, 'cooldown_minutes': 240}
        }
    
    def evaluate_and_alert(self, signals: dict[str, SentimentSignal],
                          anomalies: list[dict]) -> list[dict]:
        """评估并生成告警"""
        alerts = []
        
        for anomaly in anomalies:
            severity = anomaly['severity']
            
            # 速率检查
            if not self._check_rate_limit(severity):
                continue
            
            alert = {
                'timestamp': datetime.now(),
                'tier': severity,
                'type': anomaly['type'],
                'stock': anomaly['stock'],
                'description': anomaly['description'],
                'data': anomaly
            }
            
            alerts.append(alert)
            self.alert_history.append(alert)
            
            # 更新速率限制
            self._update_rate_limit(severity)
            
            logger.warning(f"[{severity}] {anomaly['stock']}: {anomaly['description']}")
        
        return alerts
    
    def _check_rate_limit(self, severity: str) -> bool:
        """检查是否超过速率限制"""
        limiter = self.rate_limiter.get(severity)
        if limiter is None:
            return True
        
        if limiter['last_sent'] is None:
            return True
        
        elapsed = (datetime.now() - limiter['last_sent']).total_seconds() / 60
        return elapsed >= limiter['cooldown_minutes']
    
    def _update_rate_limit(self, severity: str) -> None:
        """更新速率限制时间戳"""
        if severity in self.rate_limiter:
            self.rate_limiter[severity]['last_sent'] = datetime.now()
    
    def get_alert_summary(self) -> dict[str, Any]:
        """获取告警摘要"""
        if not self.alert_history:
            return {'total': 0, 'by_tier': {}}
        
        by_tier = {}
        for alert in self.alert_history:
            tier = alert['tier']
            by_tier[tier] = by_tier.get(tier, 0) + 1
        
        return {
            'total': len(self.alert_history),
            'by_tier': by_tier,
            'recent': self.alert_history[-10:]
        }
