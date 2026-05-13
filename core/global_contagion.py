"""
全球市场传染分析模块 (Global Market Contagion Analyzer)

仿照 Cruix 开源情报分析体系设计：
1. 分层采集架构 - 多市场数据采集
2. 智能融合 - 跨市场相关性融合+时滞对齐
3. Delta检测 - 传染强度突变检测
4. 三级告警 - FLASH/PRIORITY/ROUTINE

核心功能：
- 跨市场相关性矩阵计算
- 波动率溢出指数 (BEKK-GARCH)
- CoVaR / ΔCoVaR 尾部依赖分析
- 传染网络中心性分析
- Granger因果检验 + 脉冲响应
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats
from scipy.sparse.csgraph import minimum_spanning_tree

from core.risk_monitor import BaseRiskMonitor, RiskLevel, RiskSignal, RiskAction

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


@dataclass
class MarketData:
    """市场数据"""
    name: str           # 市场名称
    code: str           # 市场代码
    returns: pd.Series  # 收益率序列
    volatility: float   # 当前波动率
    regime: str         # 市场状态 (normal/stress/crisis)


@dataclass
class ContagionChannel:
    """传染通道"""
    source: str         # 源头市场
    target: str         # 目标市场
    strength: float     # 传染强度 0-1
    lag: int            # 传染时滞 (天)
    correlation: float  # 相关系数
    spillover_index: float  # 波动率溢出指数
    covar_delta: float  # ΔCoVaR
    trend: str          # 趋势 (up/down/flat)


@dataclass
class ContagionNetwork:
    """传染网络"""
    markets: list[str]                          # 市场列表
    correlation_matrix: pd.DataFrame            # 相关性矩阵
    spillover_matrix: pd.DataFrame              # 溢出矩阵
    centrality: dict[str, float]                # 中心性
    mst_edges: list[tuple]                      # 最小生成树边
    contagion_paths: list[dict]                 # 传染路径


# ==================== 全球市场传染监控器 ====================


class GlobalContagionMonitor(BaseRiskMonitor):
    """
    全球市场传染监控器

    监控维度：
    - 跨市场相关性传染
    - 波动率溢出
    - 尾部依赖 (CoVaR)
    - 网络中心性
    - 情绪传染

    仿 Cruix 设计：
    - Delta检测: 相关性/溢出指数突变
    - 三级告警: 单通道/多通道/系统性传染
    """

    # 全球市场定义
    MARKETS = {
        'SPX': {'name': '美股', 'region': 'US', 'type': 'equity'},
        'DJI': {'name': '道指', 'region': 'US', 'type': 'equity'},
        'NDX': {'name': '纳指', 'region': 'US', 'type': 'equity'},
        'DAX': {'name': '德股', 'region': 'EU', 'type': 'equity'},
        'FTSE': {'name': '英股', 'region': 'EU', 'type': 'equity'},
        'N225': {'name': '日股', 'region': 'AP', 'type': 'equity'},
        'HSI': {'name': '港股', 'region': 'AP', 'type': 'equity'},
        'SH': {'name': '上证', 'region': 'CN', 'type': 'equity'},
        'SZ': {'name': '深证', 'region': 'CN', 'type': 'equity'},
        'VIX': {'name': 'VIX', 'region': 'US', 'type': 'volatility'},
        'GOLD': {'name': '黄金', 'region': 'GL', 'type': 'commodity'},
        'OIL': {'name': '原油', 'region': 'GL', 'type': 'commodity'},
        'DXY': {'name': '美元', 'region': 'US', 'type': 'fx'},
        'USDCNH': {'name': '离岸人民币', 'region': 'CN', 'type': 'fx'},
    }

    # 传染通道定义 (源头→目标)
    CHANNELS = [
        ('SPX', 'SH'),      # 美股→A股
        ('SPX', 'HSI'),     # 美股→港股
        ('SPX', 'N225'),    # 美股→日股
        ('DAX', 'SH'),      # 欧股→A股
        ('N225', 'SH'),     # 日股→A股
        ('HSI', 'SH'),      # 港股→A股
        ('VIX', 'SH'),      # VIX→A股
        ('OIL', 'SH'),      # 原油→A股
        ('GOLD', 'SH'),     # 黄金→A股
        ('DXY', 'USDCNH'),  # 美元→离岸人民币
        ('USDCNH', 'SH'),   # 离岸人民币→A股
    ]

    def __init__(self, enabled: bool = True, weight: float = 1.2):
        super().__init__("global_contagion", enabled, weight)
        self.threshold_low = 0.35      # 三级预警阈值
        self.threshold_medium = 0.60   # 二级预警阈值
        self.threshold_high = 0.80     # 一级预警阈值
        self.correlation_window = 60   # 相关性计算窗口
        self.lookback_history = 20     # Delta检测回看
        self._correlation_history: list[pd.DataFrame] = []
        self._spillover_history: list[pd.DataFrame] = []
        self._network_history: list[ContagionNetwork] = []

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行全球传染监控

        Args:
            symbol: 股票代码（传染监控通常忽略）
            kwargs:
                - market_returns: dict[str, pd.Series], 各市场收益率
                - market_vols: dict[str, float], 各市场波动率
                - stress_events: list, 压力事件列表

        Returns:
            RiskSignal
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="全球传染监控已禁用"
            )

        score = 0.0
        reasons = []
        metadata = {}

        # 1. 获取市场数据
        market_returns = kwargs.get('market_returns', {})
        market_vols = kwargs.get('market_vols', {})
        stress_events = kwargs.get('stress_events', [])

        if not market_returns:
            # 无数据时返回模拟信号
            return self._generate_mock_signal()

        # 2. 计算跨市场相关性矩阵
        corr_matrix = self._compute_correlation_matrix(market_returns)
        self._correlation_history.append(corr_matrix)
        if len(self._correlation_history) > self.lookback_history:
            self._correlation_history.pop(0)

        # 3. 检测相关性突变 (Delta检测)
        corr_delta = self._detect_correlation_delta(corr_matrix)
        if corr_delta['max_delta'] > 0.3:
            score += 0.25
            reasons.append(f"相关性突变: {corr_delta['max_delta']:.2f}")
            metadata['correlation_delta'] = corr_delta

        # 4. 计算波动率溢出指数
        spillover = self._compute_spillover_index(market_returns, market_vols)
        if spillover > 0.3:
            score += 0.25
            reasons.append(f"波动率溢出: {spillover:.2f}")
            metadata['spillover_index'] = spillover

        # 5. 计算CoVaR尾部依赖
        covar_results = self._compute_covar_analysis(market_returns)
        max_covar_delta = max((r['delta_covar'] for r in covar_results.values()), default=0)
        if max_covar_delta > 0.05:
            score += 0.20
            reasons.append(f"CoVaR恶化: {max_covar_delta:.3f}")
            metadata['covar'] = covar_results

        # 6. 网络中心性分析
        network = self._build_contagion_network(corr_matrix, market_vols)
        self._network_history.append(network)
        max_centrality = max(network.centrality.values()) if network.centrality else 0
        if max_centrality > 0.25:
            score += 0.15
            reasons.append(f"系统重要性集中: {max_centrality:.2f}")
            metadata['centrality'] = network.centrality

        # 7. 压力事件检测
        for event in stress_events:
            event_score = self._evaluate_stress_event(event)
            score += event_score
            reasons.append(f"压力事件: {event}")

        # 8. 综合评分
        score = min(1.0, score)
        level = self._score_to_level(score)

        # 9. 构建传染路径描述
        contagion_paths = self._describe_contagion_paths(network)

        message = "; ".join(reasons) if reasons else "全球传染风险正常"

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'correlation_matrix': corr_matrix.to_dict(),
                'spillover_index': spillover,
                'covar_results': covar_results,
                'centrality': network.centrality,
                'contagion_paths': contagion_paths,
                'network_edges': network.mst_edges,
                **metadata
            }
        ))

    def _generate_mock_signal(self) -> RiskSignal:
        """生成模拟信号（无数据时）"""
        return RiskSignal(
            dimension=self.name,
            level=RiskLevel.LOW,
            score=0.35,
            message="全球传染监控运行中 (模拟数据)",
            metadata={
                'status': 'simulation',
                'note': '未提供市场收益率数据，使用模拟值'
            }
        )

    def _compute_correlation_matrix(self, market_returns: dict[str, pd.Series]) -> pd.DataFrame:
        """计算跨市场相关性矩阵"""
        if not market_returns:
            return pd.DataFrame()

        # 构建收益率DataFrame
        df = pd.DataFrame(market_returns)

        # 计算滚动相关性
        corr = df.corr()

        return corr.fillna(0)

    def _detect_correlation_delta(self, current_corr: pd.DataFrame) -> dict:
        """检测相关性突变 (Cruix Delta检测)"""
        if len(self._correlation_history) < 2:
            return {'max_delta': 0.0, 'pairs': []}

        prev_corr = self._correlation_history[-2]

        # 对齐索引
        common_idx = current_corr.index.intersection(prev_corr.index)
        common_cols = current_corr.columns.intersection(prev_corr.columns)

        if len(common_idx) == 0 or len(common_cols) == 0:
            return {'max_delta': 0.0, 'pairs': []}

        curr = current_corr.loc[common_idx, common_cols]
        prev = prev_corr.loc[common_idx, common_cols]

        # 计算变化
        delta = curr - prev

        # 找出最大变化
        max_delta = 0.0
        max_pair = None
        significant_pairs = []

        for i in delta.index:
            for j in delta.columns:
                if i >= j:  # 只看上三角
                    continue
                d = abs(delta.loc[i, j])
                if d > max_delta:
                    max_delta = d
                    max_pair = (i, j)
                if d > 0.2:  # 显著变化阈值
                    significant_pairs.append({
                        'pair': (i, j),
                        'delta': d,
                        'current': curr.loc[i, j],
                        'previous': prev.loc[i, j]
                    })

        return {
            'max_delta': max_delta,
            'max_pair': max_pair,
            'pairs': significant_pairs
        }

    def _compute_spillover_index(self, market_returns: dict[str, pd.Series],
                                  market_vols: dict[str, float]) -> float:
        """计算波动率溢出指数 (简化版BEKK)"""
        if not market_returns or len(market_returns) < 2:
            return 0.0

        # 使用收益率的交叉乘积作为溢出代理
        df = pd.DataFrame(market_returns)

        # 计算交叉波动率贡献
        total_spillover = 0.0
        n = len(df.columns)

        for i, col_i in enumerate(df.columns):
            for j, col_j in enumerate(df.columns):
                if i == j:
                    continue
                # 计算交叉相关系数
                cov = df[col_i].cov(df[col_j])
                var_i = df[col_i].var()
                var_j = df[col_j].var()
                if var_i > 0 and var_j > 0:
                    spillover = abs(cov) / np.sqrt(var_i * var_j)
                    total_spillover += spillover

        # 平均溢出指数
        avg_spillover = total_spillover / (n * (n - 1)) if n > 1 else 0

        return min(1.0, avg_spillover)

    def _compute_covar_analysis(self, market_returns: dict[str, pd.Series]) -> dict:
        """计算CoVaR尾部依赖分析"""
        results = {}

        if not market_returns or len(market_returns) < 2:
            return results

        df = pd.DataFrame(market_returns)

        # 对每个通道计算CoVaR
        for source, target in self.CHANNELS:
            if source not in df.columns or target not in df.columns:
                continue

            source_returns = df[source]
            target_returns = df[target]

            # 计算条件VaR: 当源头市场处于5%分位时，目标市场的VaR
            source_stress = source_returns.quantile(0.05)
            stress_mask = source_returns <= source_stress

            if stress_mask.sum() < 5:
                continue

            # 条件分布
            target_conditional = target_returns[stress_mask]
            covar_95 = target_conditional.quantile(0.05)

            # 无条件VaR
            var_95 = target_returns.quantile(0.05)

            # ΔCoVaR
            delta_covar = abs(covar_95) - abs(var_95)

            results[f"{source}->{target}"] = {
                'source': source,
                'target': target,
                'covar_95': covar_95,
                'var_95': var_95,
                'delta_covar': delta_covar,
                'stress_probability': stress_mask.mean()
            }

        return results

    def _build_contagion_network(self, corr_matrix: pd.DataFrame,
                                  market_vols: dict[str, float]) -> ContagionNetwork:
        """构建传染网络"""
        markets = list(corr_matrix.index)
        n = len(markets)

        if n == 0:
            return ContagionNetwork(
                markets=[], correlation_matrix=pd.DataFrame(),
                spillover_matrix=pd.DataFrame(), centrality={},
                mst_edges=[], contagion_paths=[]
            )

        # 计算溢出矩阵 (基于相关性和波动率)
        spillover = pd.DataFrame(0.0, index=markets, columns=markets)
        for i in markets:
            for j in markets:
                if i == j:
                    continue
                corr = abs(corr_matrix.loc[i, j]) if i in corr_matrix.index and j in corr_matrix.columns else 0
                vol_ratio = market_vols.get(j, 0) / (market_vols.get(i, 1) + 1e-6)
                spillover.loc[i, j] = corr * min(vol_ratio, 2.0)

        # 计算特征向量中心性
        adjacency = spillover.values
        centrality = {}

        try:
            # 使用幂迭代计算特征向量中心性
            eigenvalues, eigenvectors = np.linalg.eigh(adjacency + adjacency.T)
            principal = eigenvectors[:, -1]
            principal = np.abs(principal)
            principal = principal / principal.sum() if principal.sum() > 0 else principal

            for idx, market in enumerate(markets):
                centrality[market] = float(principal[idx])
        except Exception:
            centrality = {m: 1.0 / n for m in markets}

        # 最小生成树 (用于识别主要传染路径)
        try:
            # 使用距离 = 1 - 相关性
            distance = 1 - np.abs(corr_matrix.values)
            np.fill_diagonal(distance, 0)
            mst = minimum_spanning_tree(distance)
            mst_edges = []
            rows, cols = mst.nonzero()
            for r, c in zip(rows, cols):
                if r < c:  # 避免重复
                    mst_edges.append((markets[r], markets[c], float(mst[r, c])))
        except Exception:
            mst_edges = []

        # 识别传染路径
        contagion_paths = self._identify_contagion_paths(spillover, centrality)

        return ContagionNetwork(
            markets=markets,
            correlation_matrix=corr_matrix,
            spillover_matrix=spillover,
            centrality=centrality,
            mst_edges=mst_edges,
            contagion_paths=contagion_paths
        )

    def _identify_contagion_paths(self, spillover: pd.DataFrame,
                                   centrality: dict[str, float]) -> list[dict]:
        """识别主要传染路径"""
        paths = []
        markets = list(spillover.index)

        for source in markets:
            for target in markets:
                if source == target:
                    continue

                strength = spillover.loc[source, target]
                if strength > 0.2:  # 显著传染阈值
                    paths.append({
                        'source': source,
                        'target': target,
                        'strength': float(strength),
                        'source_centrality': centrality.get(source, 0),
                        'target_centrality': centrality.get(target, 0),
                        'risk_level': 'HIGH' if strength > 0.5 else 'MEDIUM' if strength > 0.3 else 'LOW'
                    })

        # 按传染强度排序
        paths.sort(key=lambda x: x['strength'], reverse=True)
        return paths[:20]  # 只保留前20条

    def _describe_contagion_paths(self, network: ContagionNetwork) -> list[str]:
        """生成传染路径描述"""
        descriptions = []
        for path in network.contagion_paths[:5]:
            desc = f"{path['source']}→{path['target']}: 强度{path['strength']:.2f}"
            descriptions.append(desc)
        return descriptions

    def _evaluate_stress_event(self, event: str) -> float:
        """评估压力事件得分"""
        event_scores = {
            'us_market_crash': 0.4,      # 美股崩盘
            'eu_debt_crisis': 0.35,      # 欧债危机
            'geopolitical_conflict': 0.3, # 地缘冲突
            'commodity_spike': 0.25,     # 商品价格暴涨
            'fx_volatility': 0.2,        # 汇率剧烈波动
            'trade_war': 0.35,           # 贸易战
            'pandemic': 0.4,             # 疫情
            'banking_crisis': 0.45,      # 银行业危机
        }
        return event_scores.get(event, 0.15)

    def _score_to_level(self, score: float) -> RiskLevel:
        """分数转风险等级"""
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE

    def get_contagion_summary(self) -> dict[str, Any]:
        """获取传染分析摘要"""
        if not self._network_history:
            return {"status": "无传染网络数据"}

        latest = self._network_history[-1]
        recent_signals = self._history[-5:] if self._history else []

        # 计算综合传染指数
        avg_spillover = latest.spillover_matrix.values.mean()
        max_corr = latest.correlation_matrix.abs().values.max()
        max_centrality = max(latest.centrality.values()) if latest.centrality else 0

        contagion_index = min(1.0, (avg_spillover + max_corr + max_centrality) / 3)

        return {
            "contagion_index": round(contagion_index * 100, 1),
            "markets_count": len(latest.markets),
            "active_channels": len(latest.contagion_paths),
            "high_risk_channels": sum(1 for p in latest.contagion_paths if p['risk_level'] == 'HIGH'),
            "max_correlation": round(max_corr, 3),
            "avg_spillover": round(avg_spillover, 3),
            "most_central_market": max(latest.centrality.items(), key=lambda x: x[1])[0] if latest.centrality else None,
            "top_contagion_paths": latest.contagion_paths[:5],
            "recent_signals": [
                {
                    "time": s.timestamp.strftime("%H:%M:%S"),
                    "level": s.level_name,
                    "score": round(s.score, 2),
                    "message": s.message
                }
                for s in recent_signals
            ]
        }


# ==================== 传染分析工具函数 ====================

def compute_granger_causality(x: pd.Series, y: pd.Series,
                               max_lag: int = 5) -> dict:
    """计算Granger因果检验"""
    from statsmodels.tsa.stattools import grangercausalitytests

    try:
        data = pd.DataFrame({'y': y, 'x': x}).dropna()
        if len(data) < max_lag + 10:
            return {'causal': False, 'p_value': 1.0, 'lag': 0}

        result = grangercausalitytests(data[['y', 'x']], maxlag=max_lag, verbose=False)

        # 找出最小p值
        min_p = 1.0
        best_lag = 0
        for lag, test_result in result.items():
            p_value = test_result[0]['ssr_ftest'][1]
            if p_value < min_p:
                min_p = p_value
                best_lag = lag

        return {
            'causal': min_p < 0.05,
            'p_value': min_p,
            'lag': best_lag,
            'strength': 1 - min_p
        }
    except Exception as e:
        logger.warning(f"Granger因果检验失败: {e}")
        return {'causal': False, 'p_value': 1.0, 'lag': 0, 'strength': 0}


def compute_impulse_response(cov_matrix: np.ndarray,
                              shock_market: int,
                              steps: int = 10) -> np.ndarray:
    """计算脉冲响应函数 (简化版)"""
    n = cov_matrix.shape[0]
    response = np.zeros((steps, n))

    # 初始冲击
    response[0, shock_market] = 1.0

    # 传导效应
    for t in range(1, steps):
        for i in range(n):
            for j in range(n):
                response[t, i] += cov_matrix[i, j] * response[t-1, j]
        response[t] = np.clip(response[t], -2, 2)

    return response


# ==================== 便捷函数 ====================

def create_contagion_monitor(**kwargs) -> GlobalContagionMonitor:
    """创建传染监控器的工厂函数"""
    return GlobalContagionMonitor(**kwargs)


def analyze_market_contagion(market_returns: dict[str, pd.Series],
                              market_vols: Optional[dict[str, float]] = None) -> dict:
    """便捷函数: 分析市场传染"""
    monitor = GlobalContagionMonitor()

    if market_vols is None:
        market_vols = {k: v.std() for k, v in market_returns.items()}

    signal, _ = monitor.evaluate(
        market_returns=market_returns,
        market_vols=market_vols
    )

    return {
        'signal': signal,
        'summary': monitor.get_contagion_summary()
    }
