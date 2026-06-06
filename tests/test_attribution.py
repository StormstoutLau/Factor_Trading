"""Brinson归因分析测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest

from core.attribution import (
    AttributionPeriod,
    BrinsonAttributionAnalyzer,
    BrinsonAttributionResult,
    FactorAttributionAnalyzer,
    calculate_sector_returns,
    create_benchmark_from_universe,
)


class TestBrinsonAttribution:
    """Brinson归因测试"""
    
    def test_single_period_basic(self):
        """测试单期基本归因"""
        # 组合收益 = 0.4*0.08 + 0.3*0.02 + 0.3*0.04 = 0.032 + 0.006 + 0.012 = 0.05
        # 基准收益 = 0.3*0.06 + 0.4*0.03 + 0.3*0.02 = 0.018 + 0.012 + 0.006 = 0.036
        period = AttributionPeriod(
            period_date=pd.Timestamp("2024-01-01"),
            portfolio_return=0.050,
            benchmark_return=0.036,
            portfolio_weights={"科技": 0.4, "金融": 0.3, "消费": 0.3},
            portfolio_returns={"科技": 0.08, "金融": 0.02, "消费": 0.04},
            benchmark_weights={"科技": 0.3, "金融": 0.4, "消费": 0.3},
            benchmark_returns={"科技": 0.06, "金融": 0.03, "消费": 0.02},
        )
        
        analyzer = BrinsonAttributionAnalyzer()
        result = analyzer.calculate_single_period(period)
        
        # 验证超额收益 = 0.05 - 0.036 = 0.014
        assert abs(result.total_excess_return - 0.014) < 1e-10
        
        # 验证分解
        total = result.allocation_effect + result.selection_effect + result.interaction_effect
        assert abs(total - result.total_excess_return) < 1e-10
        
        # 配置效应: (0.4-0.3)*0.06 + (0.3-0.4)*0.03 + (0.3-0.3)*0.02 = 0.006 - 0.003 = 0.003
        assert abs(result.allocation_effect - 0.003) < 1e-10
        
        # 选择效应: 0.3*(0.08-0.06) + 0.4*(0.02-0.03) + 0.3*(0.04-0.02) = 0.006 - 0.004 + 0.006 = 0.008
        assert abs(result.selection_effect - 0.008) < 1e-10
        
        # 交互效应: (0.4-0.3)*(0.08-0.06) + (0.3-0.4)*(0.02-0.03) + 0 = 0.002 + 0.001 = 0.003
        assert abs(result.interaction_effect - 0.003) < 1e-10
    
    def test_multi_period_geometric(self):
        """测试多期几何连接"""
        analyzer = BrinsonAttributionAnalyzer(linking_method="geometric")
        
        # 添加两期数据
        analyzer.add_period(AttributionPeriod(
            period_date=pd.Timestamp("2024-01-01"),
            portfolio_return=0.05,
            benchmark_return=0.03,
            portfolio_weights={"科技": 0.5, "金融": 0.5},
            portfolio_returns={"科技": 0.08, "金融": 0.02},
            benchmark_weights={"科技": 0.5, "金融": 0.5},
            benchmark_returns={"科技": 0.06, "金融": 0.02},
        ))
        
        analyzer.add_period(AttributionPeriod(
            period_date=pd.Timestamp("2024-02-01"),
            portfolio_return=0.03,
            benchmark_return=0.02,
            portfolio_weights={"科技": 0.6, "金融": 0.4},
            portfolio_returns={"科技": 0.05, "金融": 0.01},
            benchmark_weights={"科技": 0.5, "金融": 0.5},
            benchmark_returns={"科技": 0.04, "金融": 0.01},
        ))
        
        result = analyzer.calculate_multi_period()
        
        # 验证累计收益
        expected_portfolio = (1.05) * (1.03) - 1
        expected_benchmark = (1.03) * (1.02) - 1
        
        assert abs(result.cumulative_portfolio_return - expected_portfolio) < 1e-10
        assert abs(result.cumulative_benchmark_return - expected_benchmark) < 1e-10
        
        # 验证归因分解非零
        assert result.cumulative_allocation != 0
        assert result.cumulative_selection != 0
    
    def test_multi_period_arithmetic(self):
        """测试多期算术连接"""
        analyzer = BrinsonAttributionAnalyzer(linking_method="arithmetic")
        
        analyzer.add_period(AttributionPeriod(
            period_date=pd.Timestamp("2024-01-01"),
            portfolio_return=0.05,
            benchmark_return=0.03,
            portfolio_weights={"科技": 0.5, "金融": 0.5},
            portfolio_returns={"科技": 0.08, "金融": 0.02},
            benchmark_weights={"科技": 0.5, "金融": 0.5},
            benchmark_returns={"科技": 0.06, "金融": 0.02},
        ))
        
        result = analyzer.calculate_multi_period()
        
        # 算术连接 = 简单求和
        assert abs(result.cumulative_allocation - 0.0) < 1e-10  # 等权配置无配置效应
        assert abs(result.cumulative_selection - 0.01) < 1e-10  # 0.5*(0.08-0.06) + 0.5*(0.02-0.02)
    
    def test_sector_breakdown(self):
        """测试行业分解"""
        analyzer = BrinsonAttributionAnalyzer(linking_method="arithmetic")
        
        # 使用一致的收益数据: 组合=0.050, 基准=0.036
        analyzer.add_period(AttributionPeriod(
            period_date=pd.Timestamp("2024-01-01"),
            portfolio_return=0.050,
            benchmark_return=0.036,
            portfolio_weights={"科技": 0.4, "金融": 0.3, "消费": 0.3},
            portfolio_returns={"科技": 0.08, "金融": 0.02, "消费": 0.04},
            benchmark_weights={"科技": 0.3, "金融": 0.4, "消费": 0.3},
            benchmark_returns={"科技": 0.06, "金融": 0.03, "消费": 0.02},
        ))
        
        result = analyzer.calculate_multi_period()
        breakdown = analyzer._get_sector_breakdown()
        
        assert "科技" in breakdown
        assert "金融" in breakdown
        assert "消费" in breakdown
        
        # 验证各行业贡献和等于总效应 (算术连接直接求和)
        total_alloc = sum(v['allocation'] for v in breakdown.values())
        total_select = sum(v['selection'] for v in breakdown.values())
        total_inter = sum(v['interaction'] for v in breakdown.values())
        
        assert abs(total_alloc - result.cumulative_allocation) < 1e-10
        assert abs(total_select - result.cumulative_selection) < 1e-10
        assert abs(total_inter - result.cumulative_interaction) < 1e-10
    
    def test_report_generation(self):
        """测试报告生成"""
        analyzer = BrinsonAttributionAnalyzer()
        
        analyzer.add_period(AttributionPeriod(
            period_date=pd.Timestamp("2024-01-01"),
            portfolio_return=0.05,
            benchmark_return=0.03,
            portfolio_weights={"科技": 0.5, "金融": 0.5},
            portfolio_returns={"科技": 0.08, "金融": 0.02},
            benchmark_weights={"科技": 0.5, "金融": 0.5},
            benchmark_returns={"科技": 0.06, "金融": 0.02},
        ))
        
        report = analyzer.generate_report()
        
        assert 'summary' in report
        assert 'period_results' in report
        assert 'sector_breakdown' in report
        
        summary = report['summary']
        assert 'cumulative_portfolio_return' in summary
        assert 'allocation_effect' in summary
        assert 'selection_effect' in summary
        assert 'interaction_effect' in summary


class TestFactorAttribution:
    """多因子归因测试"""
    
    def test_basic_factor_attribution(self):
        """测试基本因子归因"""
        analyzer = FactorAttributionAnalyzer(factor_names=["size", "value", "momentum"])
        
        analyzer.add_period(
            date=pd.Timestamp("2024-01-01"),
            portfolio_exposure={"size": 0.3, "value": 0.5, "momentum": 0.2},
            benchmark_exposure={"size": 0.2, "value": 0.3, "momentum": 0.1},
            factor_returns={"size": 0.01, "value": 0.02, "momentum": 0.015},
            specific_return=0.005,
        )
        
        result = analyzer.calculate_attribution()
        
        # size: (0.3-0.2)*0.01 = 0.001
        assert abs(result['factor_contributions']['size'] - 0.001) < 1e-10
        
        # value: (0.5-0.3)*0.02 = 0.004
        assert abs(result['factor_contributions']['value'] - 0.004) < 1e-10
        
        # momentum: (0.2-0.1)*0.015 = 0.0015
        assert abs(result['factor_contributions']['momentum'] - 0.0015) < 1e-10
        
        # 特质收益
        assert abs(result['specific_contribution'] - 0.005) < 1e-10
        
        # 总超额
        expected_total = 0.001 + 0.004 + 0.0015 + 0.005
        assert abs(result['total_excess'] - expected_total) < 1e-10
    
    def test_multi_period_factor(self):
        """测试多期因子归因"""
        analyzer = FactorAttributionAnalyzer(factor_names=["size", "value"])
        
        for i in range(3):
            analyzer.add_period(
                date=pd.Timestamp(f"2024-0{i+1}-01"),
                portfolio_exposure={"size": 0.3, "value": 0.5},
                benchmark_exposure={"size": 0.2, "value": 0.3},
                factor_returns={"size": 0.01, "value": 0.02},
                specific_return=0.005,
            )
        
        result = analyzer.calculate_attribution()
        
        # 3期累计
        assert abs(result['factor_contributions']['size'] - 0.003) < 1e-10
        assert abs(result['factor_contributions']['value'] - 0.012) < 1e-10
        assert abs(result['specific_contribution'] - 0.015) < 1e-10


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_create_benchmark_equal_weight(self):
        """测试等权基准创建"""
        dates = pd.date_range("2024-01-01", periods=5)
        returns = pd.DataFrame({
            "A": [0.01, 0.02, -0.01, 0.03, 0.01],
            "B": [0.02, -0.01, 0.01, 0.02, 0.03],
            "C": [-0.01, 0.01, 0.02, -0.01, 0.02],
        }, index=dates)
        
        benchmark = create_benchmark_from_universe(returns)
        
        expected = returns.mean(axis=1)
        pd.testing.assert_series_equal(benchmark, expected)
    
    def test_create_benchmark_custom_weight(self):
        """测试自定义权重基准"""
        dates = pd.date_range("2024-01-01", periods=3)
        returns = pd.DataFrame({
            "A": [0.01, 0.02, 0.03],
            "B": [0.02, 0.03, 0.04],
        }, index=dates)
        
        weights = {"A": 0.6, "B": 0.4}
        benchmark = create_benchmark_from_universe(returns, weights)
        
        expected = returns["A"] * 0.6 + returns["B"] * 0.4
        pd.testing.assert_series_equal(benchmark, expected)
    
    def test_calculate_sector_returns(self):
        """测试行业收益计算"""
        dates = pd.date_range("2024-01-01", periods=3)
        returns = pd.DataFrame({
            "A": [0.01, 0.02, 0.03],
            "B": [0.02, 0.03, 0.04],
            "C": [0.03, 0.04, 0.05],
        }, index=dates)
        
        mapping = {"A": "科技", "B": "科技", "C": "金融"}
        sector_returns = calculate_sector_returns(returns, mapping)
        
        assert "科技" in sector_returns.columns
        assert "金融" in sector_returns.columns
        
        # 科技 = (A + B) / 2
        expected_tech = (returns["A"] + returns["B"]) / 2
        expected_tech.name = "科技"
        pd.testing.assert_series_equal(sector_returns["科技"], expected_tech)
        
        # 金融 = C
        expected_fin = returns["C"].copy()
        expected_fin.name = "金融"
        pd.testing.assert_series_equal(sector_returns["金融"], expected_fin)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
