"""性能分析模块 - 基于Backtest_Opus_2.0架构

提供完整的回测性能分析功能：
- 收益指标计算
- 风险指标计算
- 交易指标分析
- 可视化图表生成
- 详细报告输出
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from tracker import PortfolioSnapshot

logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class PerformanceAnalyzer:
    """性能分析器
    
    负责计算和分析回测的各项性能指标。
    """
    
    def __init__(self):
        """初始化性能分析器"""
        self.snapshots: list[PortfolioSnapshot] = []
        self.trades_df: Optional[pd.DataFrame] = None
        logger.info("性能分析器初始化完成")
    
    def set_data(self, snapshots: list[PortfolioSnapshot], trades_df: pd.DataFrame):
        """设置分析数据
        
        Args:
            snapshots: 组合快照列表
            trades_df: 交易记录DataFrame
        """
        self.snapshots = snapshots
        self.trades_df = trades_df
        logger.info(f"设置分析数据: {len(snapshots)}个快照, {len(trades_df)}笔交易")
    
    def calculate_performance_metrics(self) -> dict[str, Any]:
        """计算性能指标
        
        Returns:
            性能指标字典
        """
        if not self.snapshots:
            return {}
        
        # 提取数据
        dates = [s.date for s in self.snapshots]
        total_values = [s.total_value for s in self.snapshots]
        daily_returns = [s.daily_return for s in self.snapshots if not pd.isna(s.daily_return)]
        cumulative_returns = [s.cumulative_return for s in self.snapshots]
        
        if not daily_returns:
            return {}
        
        # 基础指标
        total_return = cumulative_returns[-1] if cumulative_returns else 0
        n_days = len(daily_returns)
        
        # 年化收益率（假设252个交易日）
        # 【修复E13】负收益保护：当total_return <= -1时，使用对数收益率近似
        if total_return <= -1:
            annual_return = -1.0  # 全部亏损
        elif n_days > 0:
            annual_return = (1 + total_return) ** (252 / n_days) - 1
        else:
            annual_return = 0
        
        # 年化波动率
        annual_volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0
        
        # 夏普比率（假设无风险利率为3%）
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0
        
        # 索提诺比率（下行风险）
        downside_returns = [r for r in daily_returns if r < 0]
        downside_volatility = np.std(downside_returns) * np.sqrt(252) if downside_returns else 0
        sortino_ratio = (annual_return - risk_free_rate) / downside_volatility if downside_volatility > 0 else 0
        
        # 最大回撤
        cumulative_values = [1 + r for r in cumulative_returns]
        peak = np.maximum.accumulate(cumulative_values)
        drawdown = (peak - cumulative_values) / peak
        max_drawdown = np.max(drawdown) if drawdown.size > 0 else 0
        
        # 最大回撤持续期
        drawdown_periods = self._calculate_drawdown_periods(drawdown)
        max_drawdown_duration = np.max(drawdown_periods) if drawdown_periods.size > 0 else 0
        
        # 卡尔玛比率
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        # 胜率
        win_rate = len([r for r in daily_returns if r > 0]) / len(daily_returns) if daily_returns else 0
        
        # 盈亏比
        winning_returns = [r for r in daily_returns if r > 0]
        losing_returns = [r for r in daily_returns if r < 0]
        avg_win = np.mean(winning_returns) if winning_returns else 0
        avg_loss = np.mean(losing_returns) if losing_returns else 0
        win_loss_ratio = -avg_win / avg_loss if avg_loss != 0 else 0
        
        # 交易指标
        trade_metrics = self._calculate_trade_metrics()
        
        return {
            # 收益指标
            'total_return': total_return,
            'annual_return': annual_return,
            'cumulative_return_series': cumulative_returns,
            
            # 风险指标
            'annual_volatility': annual_volatility,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            'downside_volatility': downside_volatility,
            
            # 风险调整收益指标
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            
            # 其他指标
            'win_rate': win_rate,
            'win_loss_ratio': win_loss_ratio,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            
            # 交易指标
            **trade_metrics,
            
            # 基础信息
            'trading_days': n_days,
            'start_date': dates[0] if dates else None,
            'end_date': dates[-1] if dates else None,
        }
    
    def _calculate_drawdown_periods(self, drawdown) -> np.ndarray:
        """计算回撤持续期
        
        Args:
            drawdown: 回撤序列 (list, np.ndarray, or pd.Series)
            
        Returns:
            回撤持续期序列
        """
        # 【修复E14】统一转换为numpy数组
        drawdown_arr = np.asarray(drawdown)
        in_drawdown = drawdown_arr > 0
        drawdown_periods = []
        current_period = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_period += 1
            else:
                if current_period > 0:
                    drawdown_periods.append(current_period)
                current_period = 0
        
        if current_period > 0:
            drawdown_periods.append(current_period)
        
        return np.array(drawdown_periods) if drawdown_periods else np.array([0])
    
    def _calculate_trade_metrics(self) -> dict[str, Any]:
        """计算交易指标
        
        Returns:
            交易指标字典
        """
        if self.trades_df is None or self.trades_df.empty:
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'turnover_rate': 0,
                'avg_trade_cost': 0
            }
        
        # 基础交易统计
        total_trades = len(self.trades_df)
        buy_trades = len(self.trades_df[self.trades_df['side'] == 'BUY'])
        sell_trades = len(self.trades_df[self.trades_df['side'] == 'SELL'])
        
        # 换手率
        if self.snapshots:
            total_values = [s.total_value for s in self.snapshots]
            avg_portfolio_value = np.mean(total_values)
            total_trade_amount = self.trades_df['amount'].sum()
            turnover_rate = total_trade_amount / (avg_portfolio_value * len(self.snapshots)) if avg_portfolio_value > 0 else 0
        else:
            turnover_rate = 0
        
        # 平均交易成本
        avg_trade_cost = self.trades_df['cost'].mean() if not self.trades_df['cost'].empty else 0
        
        return {
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'turnover_rate': turnover_rate,
            'avg_trade_cost': avg_trade_cost,
            'total_trade_amount': total_trade_amount if 'total_trade_amount' in locals() else 0
        }
    
    def generate_monthly_returns_heatmap(self, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
        """生成月度收益热图
        
        Args:
            output_path: 输出路径
            
        Returns:
            matplotlib图形对象
        """
        if not self.snapshots:
            logger.warning("没有快照数据，无法生成月度收益热图")
            return None
        
        # 构建月度收益数据
        dates = [s.date for s in self.snapshots]
        daily_returns = [s.daily_return for s in self.snapshots]
        
        returns_df = pd.DataFrame({
            'date': dates,
            'return': daily_returns
        })
        returns_df.set_index('date', inplace=True)
        
        # 按年月分组计算累计收益
        monthly_returns = returns_df['return'].groupby([
            returns_df.index.year,
            returns_df.index.month
        ]).apply(lambda x: (1 + x).prod() - 1)
        
        # 转换为透视表
        monthly_pivot = monthly_returns.unstack(fill_value=0)
        
        # 动态生成月份列名
        month_names = [f'{i}月' for i in sorted(monthly_pivot.columns)]
        monthly_pivot.columns = month_names
        monthly_pivot.index.name = '年份'
        
        # 绘制热图
        plt.figure(figsize=(12, 8))
        sns.heatmap(monthly_pivot, annot=True, fmt='.2%', cmap='RdYlGn', center=0)
        plt.title('月度收益热图')
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"月度收益热图已保存: {output_path}")
        
        return plt.gcf()
    
    def generate_performance_chart(self, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
        """生成性能图表
        
        Args:
            output_path: 输出路径
            
        Returns:
            matplotlib图形对象
        """
        if not self.snapshots:
            logger.warning("没有快照数据，无法生成性能图表")
            return None
        
        # 提取数据
        dates = [s.date for s in self.snapshots]
        total_values = [s.total_value for s in self.snapshots]
        cumulative_returns = [s.cumulative_return for s in self.snapshots]
        
        # 创建子图
        fig, axes = plt.subplots(3, 1, figsize=(15, 12))
        
        # 净值曲线
        axes[0].plot(dates, total_values, 'b-', linewidth=2)
        axes[0].set_title('组合净值曲线')
        axes[0].set_ylabel('组合净值')
        axes[0].grid(True, alpha=0.3)
        
        # 累计收益曲线
        axes[1].plot(dates, [r * 100 for r in cumulative_returns], 'g-', linewidth=2)
        axes[1].set_title('累计收益率曲线')
        axes[1].set_ylabel('累计收益率 (%)')
        axes[1].grid(True, alpha=0.3)
        
        # 回撤曲线
        cumulative_values = [1 + r for r in cumulative_returns]
        peak = np.maximum.accumulate(cumulative_values)
        drawdown = (peak - cumulative_values) / peak * 100
        
        axes[2].fill_between(dates, drawdown, 0, alpha=0.3, color='red')
        axes[2].plot(dates, drawdown, 'r-', linewidth=1)
        axes[2].set_title('回撤曲线')
        axes[2].set_ylabel('回撤 (%)')
        axes[2].set_xlabel('日期')
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"性能图表已保存: {output_path}")
        
        return fig
    
    def generate_report(self, output_dir: Path) -> dict[str, Any]:
        """生成完整报告
        
        Args:
            output_dir: 输出目录
            
        Returns:
            报告数据
        """
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 计算性能指标
        metrics = self.calculate_performance_metrics()
        
        # 生成图表
        performance_chart_path = output_dir / "performance_chart.png"
        self.generate_performance_chart(performance_chart_path)
        
        monthly_heatmap_path = output_dir / "monthly_returns_heatmap.png"
        self.generate_monthly_returns_heatmap(monthly_heatmap_path)
        
        # 生成文本报告
        report_path = output_dir / "performance_report.txt"
        self._generate_text_report(metrics, report_path)
        
        # 生成CSV报告
        csv_report_path = output_dir / "performance_metrics.csv"
        self._generate_csv_report(metrics, csv_report_path)
        
        report_data = {
            'metrics': metrics,
            'charts': {
                'performance_chart': performance_chart_path,
                'monthly_heatmap': monthly_heatmap_path
            },
            'reports': {
                'text_report': report_path,
                'csv_report': csv_report_path
            }
        }
        
        logger.info(f"完整报告已生成到: {output_dir}")
        return report_data
    
    def _generate_text_report(self, metrics: dict[str, Any], output_path: Path):
        """生成文本报告
        
        Args:
            metrics: 性能指标
            output_path: 输出路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("回测性能报告\n")
            f.write("=" * 50 + "\n\n")
            
            # 基础信息
            f.write("基础信息\n")
            f.write("-" * 20 + "\n")
            f.write(f"回测期间: {metrics.get('start_date')} 至 {metrics.get('end_date')}\n")
            f.write(f"交易天数: {metrics.get('trading_days', 0)}\n\n")
            
            # 收益指标
            f.write("收益指标\n")
            f.write("-" * 20 + "\n")
            f.write(f"累计收益率: {metrics.get('total_return', 0):.2%}\n")
            f.write(f"年化收益率: {metrics.get('annual_return', 0):.2%}\n")
            f.write(f"胜率: {metrics.get('win_rate', 0):.2%}\n")
            f.write(f"盈亏比: {metrics.get('win_loss_ratio', 0):.2f}\n\n")
            
            # 风险指标
            f.write("风险指标\n")
            f.write("-" * 20 + "\n")
            f.write(f"年化波动率: {metrics.get('annual_volatility', 0):.2%}\n")
            f.write(f"最大回撤: {metrics.get('max_drawdown', 0):.2%}\n")
            f.write(f"最大回撤持续期: {metrics.get('max_drawdown_duration', 0)}天\n\n")
            
            # 风险调整收益指标
            f.write("风险调整收益指标\n")
            f.write("-" * 20 + "\n")
            f.write(f"夏普比率: {metrics.get('sharpe_ratio', 0):.3f}\n")
            f.write(f"索提诺比率: {metrics.get('sortino_ratio', 0):.3f}\n")
            f.write(f"卡尔玛比率: {metrics.get('calmar_ratio', 0):.3f}\n\n")
            
            # 交易指标
            f.write("交易指标\n")
            f.write("-" * 20 + "\n")
            f.write(f"总交易次数: {metrics.get('total_trades', 0)}\n")
            f.write(f"买入交易: {metrics.get('buy_trades', 0)}\n")
            f.write(f"卖出交易: {metrics.get('sell_trades', 0)}\n")
            f.write(f"换手率: {metrics.get('turnover_rate', 0):.2%}\n")
            f.write(f"平均交易成本: {metrics.get('avg_trade_cost', 0):.2f}\n")
    
    def _generate_csv_report(self, metrics: dict[str, Any], output_path: Path):
        """生成CSV报告
        
        Args:
            metrics: 性能指标
            output_path: 输出路径
        """
        # 准备CSV数据
        csv_data = []
        
        # 收益指标
        csv_data.append(['收益指标', '', ''])
        csv_data.append(['累计收益率', f"{metrics.get('total_return', 0):.2%}", ''])
        csv_data.append(['年化收益率', f"{metrics.get('annual_return', 0):.2%}", ''])
        csv_data.append(['胜率', f"{metrics.get('win_rate', 0):.2%}", ''])
        csv_data.append(['盈亏比', f"{metrics.get('win_loss_ratio', 0):.2f}", ''])
        csv_data.append(['', '', ''])
        
        # 风险指标
        csv_data.append(['风险指标', '', ''])
        csv_data.append(['年化波动率', f"{metrics.get('annual_volatility', 0):.2%}", ''])
        csv_data.append(['最大回撤', f"{metrics.get('max_drawdown', 0):.2%}", ''])
        csv_data.append(['最大回撤持续期', f"{metrics.get('max_drawdown_duration', 0)}天", ''])
        csv_data.append(['', '', ''])
        
        # 风险调整收益指标
        csv_data.append(['风险调整收益指标', '', ''])
        csv_data.append(['夏普比率', f"{metrics.get('sharpe_ratio', 0):.3f}", ''])
        csv_data.append(['索提诺比率', f"{metrics.get('sortino_ratio', 0):.3f}", ''])
        csv_data.append(['卡尔玛比率', f"{metrics.get('calmar_ratio', 0):.3f}", ''])
        csv_data.append(['', '', ''])
        
        # 交易指标
        csv_data.append(['交易指标', '', ''])
        csv_data.append(['总交易次数', metrics.get('total_trades', 0), ''])
        csv_data.append(['买入交易', metrics.get('buy_trades', 0), ''])
        csv_data.append(['卖出交易', metrics.get('sell_trades', 0), ''])
        csv_data.append(['换手率', f"{metrics.get('turnover_rate', 0):.2%}", ''])
        csv_data.append(['平均交易成本', f"{metrics.get('avg_trade_cost', 0):.2f}", ''])
        
        # 写入CSV
        df = pd.DataFrame(csv_data, columns=['指标名称', '数值', '备注'])
        df.to_csv(output_path, index=False, encoding='utf-8-sig')


def generate_report(snapshots: list[PortfolioSnapshot], trades_df: pd.DataFrame, 
                  output_dir: Path) -> dict[str, Any]:
    """生成回测报告
    
    Args:
        snapshots: 组合快照列表
        trades_df: 交易记录DataFrame
        output_dir: 输出目录
        
    Returns:
        报告数据
    """
    analyzer = PerformanceAnalyzer()
    analyzer.set_data(snapshots, trades_df)
    return analyzer.generate_report(output_dir)
