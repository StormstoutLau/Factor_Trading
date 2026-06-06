"""
向量回测引擎 V3 - 高性能向量化因子筛选

定位: 快速因子预筛选工具 (Fast Factor Screening)
    - 用于快速评估因子信号的粗略表现，而非完整回测
    - 不支持完整回测所需的高级功能，仅做因子方向性验证

设计目标:
    1. 全向量化计算，避免逐日循环
    2. NumPy 数组操作，无 pandas 开销
    3. 与现有 engine_v2 兼容的接口
    4. 支持批量因子回测

性能预期:
    - 5000股 × 2500天：~10-30秒（对比 engine_v2 的 ~180秒）
    - @njit JIT 加速后：再平衡 0.10ms/次 (5000股)，指标 0.014ms/次 (2500天)

不支持的功能 (与 engine_v2 对比):
    - execution_policy: 无 T+1/T+0 执行策略抽象
    - pending_orders: 无待执行订单队列
    - risk_manager: 无止损/保证金/盯市风险检查
    - universe_filter: 无停牌/涨跌停/ST 过滤
    - signal_translator: 无信号→订单意图转换
    - multi_asset: 仅支持单一资产类型

何时使用 V3:
    - 快速筛选因子方向 (看因子收益是否为正)
    - 批量因子回测 (数百个因子并行评估)
    - 因子衰减分析 (IC decay, 换手率估算)

何时使用 V2:
    - 需要精确模拟 T+1 交易机制
    - 需要待执行订单队列和替补股票
    - 需要风险管理 (止损/保证金)
    - 需要多资产类型 (股票+期货)
    - 需要完整策略回测报告
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional, Dict

import numpy as np
import pandas as pd

try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        """Fallback: 无 numba 时返回原始函数"""
        def decorator(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

from core.data_v3 import DataLoaderV3

logger = logging.getLogger(__name__)


# ============================================================
# Numba JIT 内核函数
# ============================================================

@njit
def _rebalance_kernel(
    positions: np.ndarray,
    cash: float,
    last_portfolio_value: float,
    signal: np.ndarray,
    prices: np.ndarray,
    buyable_mask: np.ndarray,
    sellable_mask: np.ndarray,
    top_n: int,
    cost_rate: float,
):
    """@njit 编译的再平衡计算内核

    Args:
        positions: 当前持仓 (1D, n_stocks)
        cash: 当前现金
        last_portfolio_value: 前一日组合价值
        signal: 当日信号 (1D, n_stocks)
        prices: 当日收盘价 (1D, n_stocks)
        buyable_mask: 可买入掩码 (1D bool, n_stocks)
        sellable_mask: 可卖出掩码 (1D bool, n_stocks)
        top_n: 持仓数量
        cost_rate: 交易费率

    Returns:
        (new_positions, new_cash)
    """
    n_stocks = len(signal)

    # 处理 NaN
    signal_clean = np.nan_to_num(signal, nan=0.0)

    # 选择 top_n 股票
    if n_stocks <= top_n:
        selected_mask = signal_clean > 0
    else:
        abs_signal = np.abs(signal_clean)
        threshold_idx = np.argpartition(abs_signal, -top_n)[-top_n]
        threshold = abs_signal[threshold_idx]
        selected_mask = abs_signal >= threshold

    # 应用可交易过滤
    selected_mask = selected_mask & buyable_mask

    n_selected = np.sum(selected_mask)
    if n_selected == 0:
        return positions.copy(), cash

    target_weight = 1.0 / n_selected
    target_value_per_stock = last_portfolio_value * target_weight

    # 计算目标仓位
    target_positions = np.zeros(n_stocks, dtype=np.float64)
    valid_prices = prices > 0
    for i in range(n_stocks):
        if selected_mask[i] and valid_prices[i]:
            target_positions[i] = target_value_per_stock / prices[i]

    # 处理卖出约束: 不在 sellable 的持仓强制清零
    for i in range(n_stocks):
        if (not sellable_mask[i]) and positions[i] > 0:
            target_positions[i] = 0.0

    # 计算交易
    trade_positions = target_positions - positions

    # 计算交易成本
    trade_costs = 0.0
    for i in range(n_stocks):
        trade_costs += abs(trade_positions[i]) * prices[i] * cost_rate

    # 更新仓位和现金
    new_cash = cash - np.sum(trade_positions * prices) - trade_costs

    return target_positions, new_cash


@njit
def _metrics_kernel(portfolio_value: np.ndarray):
    """@njit 编译的指标计算内核

    Args:
        portfolio_value: 组合价值序列 (1D)

    Returns:
        (total_return, annual_return, volatility, sharpe_ratio,
         max_drawdown, final_value)
    """
    n = len(portfolio_value)
    if n < 2:
        return 0.0, 0.0, 0.0, 0.0, 0.0, portfolio_value[-1]

    returns = np.diff(portfolio_value) / portfolio_value[:-1]
    total_return = (portfolio_value[-1] / portfolio_value[0]) - 1.0
    annual_return = (1.0 + total_return) ** (252.0 / n) - 1.0
    volatility = np.std(returns) * np.sqrt(252.0)
    sharpe_ratio = annual_return / volatility if volatility > 0 else 0.0

    # 最大回撤 - 手动实现 cummax (numba 不支持 np.maximum.accumulate)
    cumulative = np.cumprod(1.0 + returns)
    running_max = np.empty(len(cumulative), dtype=np.float64)
    running_max[0] = cumulative[0]
    for i in range(1, len(cumulative)):
        running_max[i] = max(running_max[i - 1], cumulative[i])
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = np.min(drawdown)

    return total_return, annual_return, volatility, sharpe_ratio, max_drawdown, portfolio_value[-1]


class VectorBacktestEngine:
    """向量回测引擎

    核心设计：
        - 预计算所有信号
        - 向量化仓位计算
        - 向量化收益计算

    Example:
        dl = DataLoaderV3.from_pandas_dataframes(close=close_df, open=open_df)
        engine = VectorBacktestEngine(config)
        engine.setup(dl)
        results = engine.run()
    """

    # 引擎定位 (P2.1)
    purpose = "快速因子预筛选工具 (Fast Factor Screening)"
    unsupported_features = [
        "execution_policy (T+1/T+0 执行策略)",
        "pending_orders (待执行订单队列)",
        "risk_manager (止损/保证金/盯市)",
        "universe_filter (停牌/涨跌停/ST 过滤)",
        "signal_translator (信号→订单意图)",
        "multi_asset (多资产类型)",
    ]

    def __init__(self, config: Optional[dict] = None):
        """初始化向量回测引擎

        Args:
            config: 配置字典
        """
        self.cfg = config or {}
        self.dl: Optional[DataLoaderV3] = None

        # 预计算数据
        self._signals: Optional[np.ndarray] = None
        self._positions: Optional[np.ndarray] = None
        self._cash: Optional[np.ndarray] = None
        self._portfolio_value: Optional[np.ndarray] = None

        # 结果
        self._results: Optional[dict] = None

        logger.info("VectorBacktestEngine 初始化完成")

    def setup(self, data_loader: DataLoaderV3) -> None:
        """设置引擎

        Args:
            data_loader: DataLoaderV3 实例
        """
        t0 = time.perf_counter()
        logger.info("设置 VectorBacktestEngine...")

        self.dl = data_loader

        # 初始化仓位和现金
        n_dates, n_stocks = self.dl.n_dates, self.dl.n_stocks
        self._positions = np.zeros((n_dates, n_stocks))
        self._cash = np.ones(n_dates) * self.cfg.get("initial_capital", 10000000.0)
        self._portfolio_value = np.zeros(n_dates)

        # 预计算信号
        self._precompute_signals()

        elapsed = time.perf_counter() - t0
        logger.info(f"VectorBacktestEngine 设置完成，耗时: {elapsed:.3f}秒")

    def _precompute_signals(self) -> None:
        """预计算交易信号"""
        logger.info("预计算交易信号...")

        if "factor" in self.dl.factor_data:
            factor = self.dl.factor_data["factor"]
        elif self.dl.factor_data:
            # 使用第一个因子
            factor = list(self.dl.factor_data.values())[0]
        else:
            # 使用价格动量作为默认信号
            close = self.dl.price_data["close"]
            factor = np.zeros_like(close)
            factor[1:] = (close[1:] - close[:-1]) / close[:-1]
            factor[0] = 0

        self._signals = factor
        logger.info(f"信号预计算完成: {self._signals.shape}")

    def run(self) -> dict[str, Any]:
        """运行向量回测

        Returns:
            回测结果字典
        """
        if self.dl is None:
            raise RuntimeError("请先调用 setup() 方法")

        t0 = time.perf_counter()
        logger.info("开始向量回测...")

        n_dates, n_stocks = self.dl.n_dates, self.dl.n_stocks
        close_prices = self.dl.price_data["close"]

        # 再平衡频率
        rebalance_freq = self.cfg.get("rebalance_freq", 20)
        top_n = self.cfg.get("top_n", 50)

        # 向量化主循环
        for i in range(n_dates):
            if i == 0:
                # 首日初始化
                self._portfolio_value[i] = self._cash[i]
                continue

            # 复制前一日仓位
            self._positions[i] = self._positions[i - 1]
            self._cash[i] = self._cash[i - 1]

            # 再平衡日
            if i % rebalance_freq == 0 and i > 0:
                self._rebalance_vectorized(i, top_n)

            # 计算当日市值
            position_value = np.sum(self._positions[i] * close_prices[i])
            self._portfolio_value[i] = self._cash[i] + position_value

        # 生成结果
        self._results = self._generate_results()

        elapsed = time.perf_counter() - t0
        logger.info(f"向量回测完成，耗时: {elapsed:.3f}秒")

        return self._results

    def _rebalance_vectorized(self, date_idx: int, top_n: int) -> None:
        """向量化再平衡

        Args:
            date_idx: 日期索引
            top_n: 持仓数量
        """
        n_stocks = self.dl.n_stocks

        # 获取当日信号
        signal = self._signals[date_idx].astype(np.float64)

        # 获取可交易掩码 (默认全 True)
        if "buyable" in self.dl.mask_data:
            buyable_mask = self.dl.mask_data["buyable"][date_idx]
        else:
            buyable_mask = np.ones(n_stocks, dtype=bool)
        if "sellable" in self.dl.mask_data:
            sellable_mask = self.dl.mask_data["sellable"][date_idx]
        else:
            sellable_mask = np.ones(n_stocks, dtype=bool)

        # 获取价格
        prices = self.dl.price_data["close"][date_idx].astype(np.float64)

        # 前一日组合价值
        last_pv = self._portfolio_value[date_idx - 1] if date_idx > 0 else self._cash[date_idx]

        # 调用 @njit 内核
        new_positions, new_cash = _rebalance_kernel(
            self._positions[date_idx].astype(np.float64),
            float(self._cash[date_idx]),
            float(last_pv),
            signal,
            prices,
            buyable_mask,
            sellable_mask,
            top_n,
            float(self.cfg.get("cost_rate", 0.001)),
        )

        self._positions[date_idx] = new_positions
        self._cash[date_idx] = new_cash

    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        if self._portfolio_value is None or len(self._portfolio_value) == 0:
            return {}

        # 调用 @njit 内核计算指标
        total_return, annual_return, volatility, sharpe_ratio, max_drawdown, final_value = \
            _metrics_kernel(self._portfolio_value)

        # 计算 returns 序列 (用于后续分析)
        returns = np.diff(self._portfolio_value) / self._portfolio_value[:-1]

        return {
            "portfolio_value": self._portfolio_value,
            "returns": returns,
            "total_return": total_return,
            "annual_return": annual_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "final_value": final_value,
            "initial_value": self._portfolio_value[0],
        }

    def get_positions(self) -> Optional[np.ndarray]:
        """获取仓位序列"""
        return self._positions

    def get_portfolio_value(self) -> Optional[np.ndarray]:
        """获取组合价值序列"""
        return self._portfolio_value

