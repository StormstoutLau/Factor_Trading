"""回测引擎核心 V2 - 插拔式架构

基于依赖注入的解耦设计，所有组件通过接口交互。
支持Mock测试、模块替换和独立升级。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from core import __api_version__
from core.analytics import generate_report
from core.change_report import LayerDumper
from core.config import BacktestConfig
from core.data import DataManager
from core.execution import ExecutionSimulator
from core.invariants import InvariantViolationError, check_all
from core.manifest import build_manifest, write_manifest
from core.execution_policy import (
    ExecutionPolicy,
    SignalTranslator,
    T1StockPolicy,
)
from core.target_positions import (
    TargetPosition,
    build_target_positions,
    compute_portfolio_value,
)
from core.factor import FactorCombiner, FactorPipeline
from core.interfaces import (
    IDataManager,
    IExecutionSimulator,
    IFactorCombiner,
    IFactorPipeline,
    IOptimizer,
    IPendingOrderQueue,
    IPositionTracker,
    IRebalanceTrigger,
    IUniverseFilter,
)
from core.pending import (
    OrderSide,
    PendingOrder,
    PendingOrderQueue,
    create_pending_order,
    select_fallback_stocks,
)
from core.portfolio import build_optimizer
from core.rebalance import build_trigger
from core.risk_manager import MarkToMarketPolicy
from core.tracker import PositionTracker
from core.validation import build_validation_declaration
from filter.limit_rules import RULESET_VERSION, unknown_board_count
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig

logger = logging.getLogger(__name__)


class BacktestEngineV2:
    """回测引擎 V2 - 插拔式架构

    通过依赖注入实现完全解耦，支持：
    - 独立测试各模块（使用Mock对象）
    - 运行时替换组件实现
    - 第三方模块接入

    Example:
        # 方式1: 使用默认组件
        engine = BacktestEngineV2(config)
        engine.setup()

        # 方式2: 注入自定义组件
        engine = BacktestEngineV2(
            config,
            data_manager=MyDataManager(config),
            optimizer=MyOptimizer(config.optimizer),
        )
        engine.setup()

        # 方式3: 完全自定义
        engine = BacktestEngineV2(
            config,
            data_manager=mock_dm,
            universe_filter=mock_universe,
            factor_pipeline=mock_pipeline,
            optimizer=mock_optimizer,
            trigger=mock_trigger,
            executor=mock_executor,
            tracker=mock_tracker,
        )
        results = engine.run()
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_manager: Optional[IDataManager] = None,
        universe_filter: Optional[IUniverseFilter] = None,
        factor_pipeline: Optional[IFactorPipeline] = None,
        factor_combiner: Optional[IFactorCombiner] = None,
        optimizer: Optional[IOptimizer] = None,
        trigger: Optional[IRebalanceTrigger] = None,
        executor: Optional[IExecutionSimulator] = None,
        tracker: Optional[IPositionTracker] = None,
        pending_queue: Optional[IPendingOrderQueue] = None,
        execution_policy: Optional[ExecutionPolicy] = None,
        risk_manager: Optional[MarkToMarketPolicy] = None,
    ):
        """初始化回测引擎

        Args:
            config: 回测配置
            data_manager: 数据管理器（可选，默认DataManager）
            universe_filter: 股票池过滤器（可选，默认UniverseFilter）
            factor_pipeline: 因子流水线（可选，默认FactorPipeline）
            factor_combiner: 因子合成器（可选，默认FactorCombiner）
            optimizer: 组合优化器（可选，默认根据配置构建）
            trigger: 再平衡触发器（可选，默认根据配置构建）
            executor: 执行模拟器（可选，默认ExecutionSimulator）
            tracker: 持仓跟踪器（可选，默认PositionTracker）
            pending_queue: 待执行订单队列（可选，默认PendingOrderQueue）
            execution_policy: 执行策略（可选，默认None使用旧路径）
            risk_manager: 风险管理器（可选，默认None不启用）
        """
        self.cfg = config

        # 注入的组件（或None，由setup创建）
        self._injected_dm = data_manager
        self._injected_universe = universe_filter
        self._injected_pipeline = factor_pipeline
        self._injected_combiner = factor_combiner
        self._injected_optimizer = optimizer
        self._injected_trigger = trigger
        self._injected_executor = executor
        self._injected_tracker = tracker
        self._injected_pending_queue = pending_queue

        # 新增抽象层 (P0 集成)
        self._execution_policy: Optional[ExecutionPolicy] = execution_policy
        self._risk_manager: Optional[MarkToMarketPolicy] = risk_manager

        # 目标持仓诊断（一致性校验与残留上报）
        self._last_targets: dict[str, TargetPosition] = {}
        self._last_target_stocks: set[str] = set()
        self._unclosed_positions: dict[str, int] = {}

        # 退市结算（P-012 D5 / T-9）
        self._delist_return_source: dict[str, str] = {}
        self._n_delisted_closed: int = 0

        # 运行清单（P-011 D7）：run() 起点时间戳，setup() 不记
        self._run_started_at: Optional[datetime] = None

        # 实际使用的组件（setup后填充）
        self.dm: Optional[IDataManager] = None
        self.universe: Optional[IUniverseFilter] = None
        self.pipeline: Optional[IFactorPipeline] = None
        self.combiner: Optional[IFactorCombiner] = None
        self.optimizer: Optional[IOptimizer] = None
        self.trigger: Optional[IRebalanceTrigger] = None
        self.executor: Optional[IExecutionSimulator] = None
        self.tracker: Optional[IPositionTracker] = None
        self.pending_queue: Optional[IPendingOrderQueue] = None

        # 预计算数据
        self._composite_signal: Optional[pd.DataFrame] = None
        self._returns_matrix: Optional[np.ndarray] = None

        # 六层归因 dump（默认关闭；setup 时按 cfg.dump_layers_dir 重建）
        self._layer_dumper = LayerDumper(None)

        logger.info("回测引擎V2初始化完成")

    def setup(self):
        """设置回测引擎

        根据注入的组件或创建默认组件。
        """
        if (
            not self.cfg.factor_files
            and self._injected_pipeline is None
            and self._injected_combiner is None
        ):
            raise ValueError(
                "factor_files 不能为空：BacktestEngineV2 需要至少一个因子文件；"
                "请在 BacktestConfig.factor_files 中指定（至少 1 项）"
            )
        t0 = time.perf_counter()
        logger.info("开始设置回测引擎V2...")

        # 1. 数据管理器
        if self._injected_dm is not None:
            self.dm = self._injected_dm
            logger.info("使用注入的数据管理器")
        else:
            logger.info("创建默认数据管理器...")
            self.dm = DataManager(self.cfg)

        # 2. 股票池过滤器
        if self._injected_universe is not None:
            self.universe = self._injected_universe
            logger.info("使用注入的股票池过滤器")
        else:
            logger.info("创建默认股票池过滤器...")
            self.universe = UniverseFilter(
                self.dm, UniverseFilterConfig.from_universe_config(self.cfg.universe)
            )
        self.universe.build_masks()

        # 3. 因子处理管道
        if self._injected_pipeline is not None:
            self.pipeline = self._injected_pipeline
            logger.info("使用注入的因子处理管道")
        else:
            logger.info("创建默认因子处理管道...")
            self.pipeline = FactorPipeline(self.dm, self.cfg.factor)

        # 4. 因子合成器
        if self._injected_combiner is not None:
            self.combiner = self._injected_combiner
            logger.info("使用注入的因子合成器")
        else:
            self.combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)

        self._precompute_factors()

        # 5. 组合优化器
        if self._injected_optimizer is not None:
            self.optimizer = self._injected_optimizer
            logger.info("使用注入的组合优化器")
        else:
            self.optimizer = build_optimizer(self.cfg.optimizer)

        # 6. 再平衡触发器
        if self._injected_trigger is not None:
            self.trigger = self._injected_trigger
            logger.info("使用注入的再平衡触发器")
        else:
            self.trigger = build_trigger(self.cfg.rebalance, self.dm.trade_dates)

        # 7. 交易执行模拟器
        if self._injected_executor is not None:
            self.executor = self._injected_executor
            logger.info("使用注入的执行模拟器")
        else:
            self.executor = ExecutionSimulator(self.cfg.cost)

        # 8. 持仓跟踪器
        if self._injected_tracker is not None:
            self.tracker = self._injected_tracker
            logger.info("使用注入的持仓跟踪器")
        else:
            self.tracker = PositionTracker(self.dm.n_stocks, self.cfg.initial_capital)

        # 9. 待执行订单队列
        if self._injected_pending_queue is not None:
            self.pending_queue = self._injected_pending_queue
            logger.info("使用注入的待执行订单队列")
        elif self.cfg.enable_pending_orders:
            self.pending_queue = PendingOrderQueue(
                max_pending_days_buy=self.cfg.max_pending_days_buy,
                max_pending_days_sell=self.cfg.max_pending_days_sell,
            )

        # 10. 预计算收益率矩阵
        self._returns_matrix = self.dm.returns.values

        # 11. 六层归因 dump（默认关闭，零 I/O）
        self._layer_dumper = LayerDumper(self.cfg.dump_layers_dir)
        self._layer_dumper.setup()

        elapsed = time.perf_counter() - t0
        logger.info(f"回测引擎V2设置完成，耗时: {elapsed:.2f}秒")

    def _precompute_factors(self):
        """预计算因子数据"""
        # 只处理第一个因子（简化）
        if not self.cfg.factor_files:
            logger.warning("未指定因子文件")
            return

        fname = self.cfg.factor_files[0]
        logger.info(f"加载因子: {fname}")

        raw = self.dm.load_factor(fname)
        logger.info(
            f"  因子形状: {raw.shape}, NaN: {raw.isna().sum().sum() / (raw.shape[0] * raw.shape[1]):.2%}"
        )

        # 使用管道处理因子（如果可用）
        if self.pipeline is not None:
            processed = self.pipeline.process(raw)
        else:
            processed = raw

        # 简单填充NaN
        self._composite_signal = processed.fillna(0)

        logger.info(f"✓ 因子加载完成: {self._composite_signal.shape}")

    def run(self) -> dict[str, Any]:
        """运行回测"""
        if self.dm is None:
            raise RuntimeError("请先调用setup()方法")

        t0 = time.perf_counter()
        self._run_started_at = datetime.now()
        logger.info("开始回测...")

        last_date_index = len(self.dm.trade_dates) - 1
        for i, date in enumerate(self.dm.trade_dates):
            try:
                self._process_trading_day(date, i)

                if i == last_date_index:
                    self._snapshot_unclosed_positions()
                    self._force_liquidation(date, i)
                    self._refresh_last_nav(date)

            except Exception as e:
                logger.error(f"处理交易日 {date} 时发生错误: {e}")
                continue

        # 清理过期订单
        if self.pending_queue:
            self.pending_queue.mark_expired(self.dm.trade_dates[-1])

        # 六层归因落盘（关闭时零 I/O）
        if self._layer_dumper.enabled:
            trades_df = (
                self.executor.trade_log.get_trades_df() if self.executor is not None else None
            )
            self._layer_dumper.finalize(trades_df)

        elapsed = time.perf_counter() - t0
        logger.info(f"回测完成，总耗时: {elapsed:.2f}秒")

        return self._generate_results()

    def _exec_price(self, dm: IDataManager, kind: str) -> pd.DataFrame:
        """成交/估值取价：新口径统一 raw；legacy 开关恢复旧复权口径。"""
        if self.cfg.legacy_adjustment:
            return dm.get_adj_price(kind, self.cfg.adjustment_type)
        return dm.get_adj_price(kind, "raw")

    def _process_trading_day(self, date: pd.Timestamp, date_index: int):
        """处理单个交易日"""
        dm = self.dm
        trigger = self.trigger
        tracker = self.tracker
        signal_df = self._composite_signal
        assert dm is not None and trigger is not None
        assert tracker is not None and signal_df is not None

        logger.debug(f"处理交易日: {date}")

        # 退市结算（P-012 T-9）：先于订单处理
        self._settle_delisted(date)

        # 执行次日订单
        if hasattr(self, "_next_day_orders") and self._next_day_orders:
            self._execute_next_day_orders(date, date_index)

        # 处理待执行订单
        if self.pending_queue:
            self._process_pending_orders(date, date_index)

        # 检查再平衡
        should_rebalance = trigger.should_trigger(
            date,
            signal=(signal_df.loc[date] if date_index < len(signal_df) else None),
            portfolio_value=tracker.get_total_value(),
        )

        if should_rebalance:
            logger.info(f"触发再平衡: {date}")
            self._execute_rebalance(date, date_index)

        # 更新持仓市值
        close_prices = self._exec_price(dm, "close").loc[date]
        tracker.update_market_values(date, close_prices)

        # 主动盯市 (risk_manager)
        if self._risk_manager is not None:
            positions = tracker.get_all_positions()
            risk_actions = self._risk_manager.check_portfolio(positions)
            for action in risk_actions:
                logger.warning(f"风险动作: {action.action.name} - {action.asset} - {action.reason}")
                # 注意: 风险动作的自动执行在后续版本中实现
                # 当前仅记录日志

        # 六层归因 dump（默认关闭 → 直接返回）
        self._dump_layers(date)

    def _dump_layers(self, date: pd.Timestamp) -> None:
        """记录当日 L1/L2/L4/L6 快照（默认关闭 → 零 I/O）。"""
        dumper = self._layer_dumper
        if not dumper.enabled:
            return

        universe = self.universe
        tracker = self.tracker
        if universe is not None:
            limit_buy, limit_sell, buyable, sellable = universe.get_layer_masks(date)
        else:
            limit_buy = limit_sell = buyable = sellable = None

        if tracker is not None:
            cash = float(tracker.get_cash())
            total = float(tracker.get_total_value())
            nav = {"cash": cash, "market_value": total - cash, "total_value": total}
        else:
            nav = {"cash": 0.0, "market_value": 0.0, "total_value": 0.0}

        dumper.dump_day(date, limit_buy, limit_sell, buyable, sellable, nav)

        orders = []
        if self.pending_queue is not None:
            orders = [
                order
                for order in self.pending_queue.get_pending_orders()
                if order.create_date == date
            ]
        else:
            orders = [
                item["order"]
                for item in getattr(self, "_next_day_orders", [])
                if item.get("create_date") == date
            ]
        dumper.record_orders(date, orders)

    def _refresh_last_nav(self, date: pd.Timestamp) -> None:
        """末日期强平后刷新 L6 终值（默认关闭 → 零 I/O）。"""
        dumper = self._layer_dumper
        tracker = self.tracker
        if not dumper.enabled or tracker is None:
            return
        cash = float(tracker.get_cash())
        total = float(tracker.get_total_value())
        dumper.update_last_nav(
            date, {"cash": cash, "market_value": total - cash, "total_value": total}
        )

    def _snapshot_unclosed_positions(self) -> None:
        """记录强平前仍持有、但已不在目标组合中的标的（正常应为空）

        用于暴露"调出却卖不掉"（停牌/跌停/掩码限制）的隐藏失败，
        快照发生在最后交易日强制平仓之前。
        """
        if self.tracker is None:
            return
        self._unclosed_positions = {
            stock: int(position.quantity)
            for stock, position in self.tracker.get_all_positions().items()
            if int(position.quantity) > 0 and stock not in self._last_target_stocks
        }
        if self._unclosed_positions:
            logger.warning(f"调仓后仍残留未平仓标的: {self._unclosed_positions}")
        else:
            logger.info("调仓残留检查完成：无残留持仓")

    def _force_liquidation(
        self,
        date: pd.Timestamp,
        date_index: int,
        stocks: Optional[dict[str, str]] = None,
        price_override: Optional[dict[str, float]] = None,
        update_market_values: bool = True,
    ) -> int:
        """强制平仓 / 退市结算共用路径（P-012 T-9）。

        Args:
            stocks: 限定平仓标的 ``{stock: reason}``；None=全部持仓
            price_override: 逐股结算价；缺省用当日收盘价
            update_market_values: 结算路径传 False，避免重复盯市（F-I9）

        Returns:
            平仓成功只数
        """
        dm = self.dm
        executor = self.executor
        tracker = self.tracker
        assert dm is not None and executor is not None and tracker is not None

        logger.info(f"最后交易日强制平仓: {date}")

        positions = tracker.get_all_positions()
        if stocks is not None:
            positions = {stock: pos for stock, pos in positions.items() if stock in stocks}
        if not positions:
            logger.info("无持仓需要平仓")
            return 0

        close_prices = None
        if update_market_values or price_override is None:
            try:
                close_prices = self._exec_price(dm, "close").loc[date]
            except KeyError:
                logger.warning(f"最后交易日 {date} 无收盘价数据")
                if price_override is None:
                    return 0

        liquidated_count = 0
        for stock, position in list(positions.items()):
            if position.quantity <= 0:
                continue

            if price_override is not None and stock in price_override:
                price = price_override[stock]
            elif close_prices is not None and stock in close_prices:
                price = close_prices[stock]
            else:
                continue

            if pd.isna(price) or price <= 0:
                continue

            success, trade = executor.execute_order(
                stock, OrderSide.SELL, position.quantity, date, float(price)
            )

            if success and trade:
                tracker.execute_trade(trade)
                liquidated_count += 1
                logger.info(f"强制平仓: {stock} {position.quantity}股 @ {float(price):.2f}")

        if update_market_values and close_prices is not None:
            tracker.update_market_values(date, close_prices)
        logger.info(f"强制平仓完成: {liquidated_count}只股票")
        return liquidated_count

    def _settle_delisted(self, date: pd.Timestamp) -> None:
        """退市日结算（P-012 T-9）：先于订单处理，按 last_close×(1+delist_return)。"""
        dm = self.dm
        tracker = self.tracker
        if dm is None or tracker is None:
            return

        snap = getattr(dm, "universe", None)
        if snap is None or snap.delist is None or snap.delist.empty:
            return

        positions = tracker.get_all_positions()
        if not positions:
            return

        try:
            close = getattr(dm, "close", None)
        except (FileNotFoundError, KeyError):
            close = None

        stocks: dict[str, str] = {}
        prices: dict[str, float] = {}
        for _, row in snap.delist.iterrows():
            stock = str(row["stock"])
            delist_date = pd.to_datetime(row.get("delist_date"), errors="coerce")
            if pd.isna(delist_date) or pd.Timestamp(delist_date) != date:
                continue

            position = positions.get(stock)
            if position is None or position.quantity <= 0:
                continue

            last_close = self._last_close(close, stock, date)
            if last_close is None:
                self._unclosed_positions[stock] = int(position.quantity)
                logger.warning(f"退市日 {date} 无 {stock} 可用行情且无结算价，跳过")
                continue

            delist_return = row.get("delist_return")
            if pd.notna(delist_return):
                prices[stock] = float(last_close) * (1 + float(delist_return))
                self._delist_return_source[stock] = "delist_return"
            else:
                prices[stock] = float(last_close)
                self._delist_return_source[stock] = "last_close"
            stocks[stock] = "delisted"

        if not prices:
            return

        closed = self._force_liquidation(
            date,
            0,
            stocks=stocks,
            price_override=prices,
            update_market_values=False,
        )
        self._n_delisted_closed += closed

    def _last_close(self, close: Optional[pd.DataFrame], stock: str, date: pd.Timestamp):
        """取 ``date`` 及之前最后一个有效收盘价。"""
        if close is None or stock not in close.columns:
            return None
        series = close[stock].loc[:date].dropna()
        if series.empty:
            return None
        return float(series.iloc[-1])

    def _universe_report(self) -> dict[str, Any]:
        """股票池快照与退市结算报告字段（E4 / V11 / V18）。"""
        status = getattr(self.dm, "universe_status", {}) or {}
        sources = set(self._delist_return_source.values())
        if not sources:
            delist_source = None
        elif len(sources) == 1:
            delist_source = sources.pop()
        else:
            delist_source = "mixed"

        return {
            "survivorship": status.get("survivorship", "uncorrected"),
            "n_unknown_list": status.get("n_unknown_list", 0),
            "n_unknown_delist": status.get("n_unknown_delist", 0),
            "n_listed": status.get("n_listed", 0),
            "n_delisted": status.get("n_delisted", 0),
            "data_version": status.get("data_version", "unknown"),
            "delist_period_handled": status.get("delist_period_handled", False),
            "delist_return_source": delist_source,
            "n_delisted_closed": self._n_delisted_closed,
        }

    def _process_pending_orders(self, date: pd.Timestamp, date_index: int):
        """处理待执行订单"""
        if not self.pending_queue:
            return

        dm = self.dm
        universe = self.universe
        executor = self.executor
        tracker = self.tracker
        assert dm is not None and universe is not None
        assert executor is not None and tracker is not None

        pending_orders = self.pending_queue.get_pending_orders()
        if not pending_orders:
            return

        logger.debug(f"处理{len(pending_orders)}个待执行订单")

        open_prices = self._exec_price(dm, "open").loc[date]
        close_prices = (
            self._exec_price(dm, "close").loc[date] if date_index < len(dm.returns) else None
        )

        buyable_mask = universe.buyable.loc[date]
        sellable_mask = universe.sellable.loc[date]

        executed_orders = []
        skipped_suspended = []
        skipped_price = []

        for order in pending_orders:
            if order.side == OrderSide.BUY:
                if not buyable_mask.get(order.stock, False):
                    skipped_suspended.append(order.stock)
                    continue
            else:
                if not sellable_mask.get(order.stock, False):
                    skipped_suspended.append(order.stock)
                    continue

            if order.stock not in open_prices:
                skipped_price.append(order.stock)
                continue

            open_price = open_prices[order.stock]
            close_price = (
                close_prices[order.stock]
                if close_prices is not None and order.stock in close_prices
                else None
            )

            success, trade = executor.execute_pending_order(order, date, open_price, close_price)

            if success and trade:
                tracker.execute_trade(trade)
                self.pending_queue.mark_executed(order, date, trade.price)
                executed_orders.append(order)
                logger.debug(f"待执行订单执行成功: {order.stock} {order.side.name}")
            else:
                if order.side == OrderSide.BUY and self.cfg.enable_fallback:
                    fallback_success = self._try_fallback_order(order, date, date_index)
                    if fallback_success:
                        executed_orders.append(order)

        # 记录被跳过的订单
        if skipped_suspended:
            logger.info(
                f"跳过{len(skipped_suspended)}个不可交易股票订单: "
                f"{', '.join(skipped_suspended)}"
            )
        if skipped_price:
            logger.warning(
                f"跳过{len(skipped_price)}个缺少价格数据订单: " f"{', '.join(skipped_price)}"
            )

        self.pending_queue.mark_expired(date)

    def _try_fallback_order(self, original_order, date: pd.Timestamp, date_index: int) -> bool:
        """尝试备选替补订单"""
        signal_df = self._composite_signal
        assert signal_df is not None
        if not self.pending_queue or date_index >= len(signal_df):
            return False

        universe = self.universe
        dm = self.dm
        executor = self.executor
        tracker = self.tracker
        assert universe is not None and dm is not None
        assert executor is not None and tracker is not None

        daily_signal = signal_df.iloc[date_index]

        excluded_stocks = [original_order.stock]
        fallback_stocks = select_fallback_stocks(
            daily_signal, excluded_stocks, self.cfg.max_fallback_depth
        )

        if not fallback_stocks:
            return False

        buyable_mask = universe.buyable.loc[date]

        for fallback_stock in fallback_stocks:
            if not buyable_mask.get(fallback_stock, False):
                continue

            open_prices = self._exec_price(dm, "open").loc[date]
            if fallback_stock not in open_prices:
                continue

            open_price = open_prices[fallback_stock]

            fallback_order = create_pending_order(
                fallback_stock, OrderSide.BUY, original_order.quantity, date
            )
            fallback_order.fallback_stock = original_order.stock

            success, trade = executor.execute_pending_order(fallback_order, date, open_price)

            if success and trade:
                tracker.execute_trade(trade)
                self.pending_queue.mark_executed(original_order, date, trade.price)
                original_order.fallback_stock = fallback_stock

                logger.info(f"备选订单执行成功: {fallback_stock} 替代 {original_order.stock}")
                return True

        return False

    def _execute_rebalance(self, date: pd.Timestamp, date_index: int):
        """执行再平衡"""
        signal_df = self._composite_signal
        assert signal_df is not None
        if date_index >= len(signal_df):
            return

        dm = self.dm
        universe = self.universe
        optimizer = self.optimizer
        tracker = self.tracker
        returns_matrix = self._returns_matrix
        assert dm is not None and universe is not None
        assert optimizer is not None and tracker is not None

        # 取消过期订单
        if self.pending_queue:
            available_stocks = set(signal_df.columns)
            for stock in available_stocks:
                self.pending_queue.cancel_orders(stock, date)

        # 获取因子信号
        daily_signal = signal_df.iloc[date_index]

        # 过滤可交易股票
        tradable_mask = universe.tradable.loc[date]
        tradable_stocks = daily_signal[tradable_mask].dropna()

        if len(tradable_stocks) == 0:
            logger.warning(f"日期 {date} 没有可交易股票")
            return

        # 组合优化
        try:
            if date_index >= self.cfg.optimizer.cov_lookback:
                assert returns_matrix is not None
                start_idx = date_index - self.cfg.optimizer.cov_lookback
                end_idx = date_index
                returns_data = pd.DataFrame(
                    returns_matrix[start_idx:end_idx],
                    index=dm.trade_dates[start_idx:end_idx],
                    columns=dm.stock_codes,
                )
            else:
                returns_data = None

            target_weights = optimizer.optimize(tradable_stocks, returns_data)

            logger.debug(f"优化得到{len(target_weights)}只股票的目标权重")

        except Exception as e:
            logger.error(f"组合优化失败: {e}")
            return

        # 计算目标持仓（含调出标的的清仓项）
        try:
            prices = self._exec_price(dm, "close").loc[date]
        except (KeyError, IndexError):
            logger.warning(f"日期 {date} 缺少收盘价数据，跳过本次再平衡")
            return

        positions = tracker.get_all_positions()
        current_positions = {
            stock: int(position.quantity)
            for stock, position in positions.items()
            if int(position.quantity) > 0
        }
        total_value = compute_portfolio_value(
            tracker.get_cash(),
            current_positions,
            prices,
            {stock: position.market_value for stock, position in positions.items()},
        )
        targets = build_target_positions(
            target_weights,
            current_positions,
            prices,
            total_value,
            round_lot=self.cfg.optimizer.round_lot,
        )
        self._last_targets = targets
        self._last_target_stocks = {
            stock for stock, target in targets.items() if target.target_quantity > 0
        }
        if self._layer_dumper.enabled:
            self._layer_dumper.record_targets(date, self._last_target_stocks)

        # 生成交易订单
        if self._execution_policy is not None:
            self._generate_orders_via_policy(date, target_weights, date_index)
        else:
            self._generate_rebalance_orders(date, targets, date_index)

    def _generate_orders_via_policy(
        self, date: pd.Timestamp, target_weights: pd.Series, date_index: int
    ):
        """通过 ExecutionPolicy 抽象层生成再平衡订单

        使用 SignalTranslator + ExecutionPolicy 替代旧路径的
        _generate_rebalance_orders，实现资产类型无关的订单生成。

        Args:
            date: 再平衡日期
            target_weights: 优化器输出的目标权重
            date_index: 日期索引
        """
        # 收集当前持仓
        tracker = self.tracker
        dm = self.dm
        policy = self._execution_policy
        assert tracker is not None and dm is not None
        assert policy is not None

        current_positions = {
            stock: pos.quantity for stock, pos in tracker.get_all_positions().items()
        }

        # 获取收盘价
        try:
            all_close = self._exec_price(dm, "close")
            if date in all_close.index:
                close_prices = all_close.loc[date]
            else:
                return
        except (KeyError, IndexError):
            return

        total_value = tracker.get_total_value()

        # 1. 权重信号 → OrderIntent
        intents = SignalTranslator.from_weights(
            target_weights=target_weights,
            current_positions=current_positions,
            prices=close_prices,
            total_value=total_value,
            asset_type="stock",
        )

        # 2. OrderIntent → PendingOrder (通过 ExecutionPolicy)
        all_orders: list[PendingOrder] = []
        for intent in intents:
            orders = policy.create_orders(intent, date)
            all_orders.extend(orders)

        # 3. 订单入队/执行
        for order in all_orders:
            if self.pending_queue:
                self.pending_queue.add_order(order)
            else:
                self._execute_order_next_open(order, date, date_index)

        logger.debug(f"通过ExecutionPolicy生成{len(all_orders)}个订单")

    def _generate_rebalance_orders(
        self,
        date: pd.Timestamp,
        targets: dict[str, TargetPosition],
        date_index: int,
    ):
        """生成再平衡订单

        先卖出（含清仓与减仓）再买入：订单队列路径无资金校验，
        卖出先成交可在同一开盘把回款计入现金，避免不必要的负现金。
        """
        orders = []

        for target in targets.values():
            trade_qty = target.target_quantity - target.current_quantity
            if trade_qty < 0:
                orders.append(create_pending_order(target.stock, OrderSide.SELL, -trade_qty, date))

        for target in targets.values():
            trade_qty = target.target_quantity - target.current_quantity
            if trade_qty > 0:
                orders.append(create_pending_order(target.stock, OrderSide.BUY, trade_qty, date))

        for order in orders:
            if self.pending_queue:
                self.pending_queue.add_order(order)
            else:
                self._execute_order_next_open(order, date, date_index)

    def _execute_order_next_open(self, order, date: pd.Timestamp, date_index: int):
        """延迟到次日开盘执行订单"""
        if not hasattr(self, "_next_day_orders"):
            self._next_day_orders = []

        self._next_day_orders.append(
            {"order": order, "create_date": date, "create_date_index": date_index}
        )
        logger.debug(f"订单标记为次日开盘执行: {order.stock} {order.side.name} {order.quantity}股")

    def _execute_next_day_orders(self, date: pd.Timestamp, date_index: int):
        """执行次日开盘订单"""
        if not hasattr(self, "_next_day_orders") or not self._next_day_orders:
            return

        dm = self.dm
        universe = self.universe
        tracker = self.tracker
        executor = self.executor
        assert dm is not None and universe is not None
        assert tracker is not None and executor is not None

        logger.info(f"执行次日开盘订单: {len(self._next_day_orders)}个订单, 日期: {date}")

        try:
            open_prices = self._exec_price(dm, "open").loc[date]
        except KeyError:
            logger.warning(f"日期 {date} 没有开盘价数据")
            return

        buyable_mask = universe.buyable.loc[date] if hasattr(universe, "buyable") else None
        sellable_mask = universe.sellable.loc[date] if hasattr(universe, "sellable") else None

        executed_count = 0
        failed_orders = []

        for order_info in self._next_day_orders:
            order = order_info["order"]

            if order.side == OrderSide.BUY:
                if buyable_mask is not None and not buyable_mask.get(order.stock, True):
                    failed_orders.append(order_info)
                    continue
            else:
                if sellable_mask is not None and not sellable_mask.get(order.stock, True):
                    failed_orders.append(order_info)
                    continue

            if order.stock not in open_prices:
                failed_orders.append(order_info)
                continue

            open_price = open_prices[order.stock]

            if open_price is None or pd.isna(open_price) or open_price <= 0:
                failed_orders.append(order_info)
                continue

            if order.side == OrderSide.BUY:
                required_cash = order.quantity * open_price * 1.002
                if tracker.get_cash() < required_cash:
                    failed_orders.append(order_info)
                    continue

            success, trade = executor.execute_order(
                order.stock, order.side, order.quantity, date, open_price
            )

            if success and trade:
                tracker.execute_trade(trade)
                executed_count += 1
            else:
                failed_orders.append(order_info)

        self._next_day_orders = failed_orders

        if executed_count > 0:
            logger.info(f"次日开盘订单执行完成: 成功{executed_count}个, 失败{len(failed_orders)}个")

    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        if self.tracker is None or self.executor is None:
            raise RuntimeError("请先调用setup()方法")
        tracker = self.tracker
        executor = self.executor
        snapshots = tracker.get_snapshots()
        trades_df = executor.trade_log.get_trades_df()

        output_dir = self.cfg.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        report_data = generate_report(
            snapshots, trades_df, output_dir, risk_free_rate=self.cfg.risk_free_rate
        )

        additional_info = {
            "config": {
                "initial_capital": self.cfg.initial_capital,
                "optimizer_method": self.cfg.optimizer.method,
                "rebalance_method": self.cfg.rebalance.method,
                "enable_pending_orders": self.cfg.enable_pending_orders,
                "adjustment_mode": {
                    "trade": self.cfg.price_modes.trade,
                    "valuation": self.cfg.price_modes.valuation,
                    "signal": self.cfg.price_modes.signal,
                    "returns": self.cfg.price_modes.returns,
                    "legacy_adjustment": self.cfg.legacy_adjustment,
                },
                "next_day_tradable_mode": getattr(self.universe, "next_day_tradable_mode", None),
                "ruleset_version": RULESET_VERSION,
                "unknown_board_codes": unknown_board_count(),
            },
            "data_info": self.dm.get_data_info() if self.dm else {},
            "universe": self._universe_report(),
            "universe_summary": self.universe.get_mask_summary() if self.universe else {},
            "pending_order_stats": (
                self.pending_queue.get_order_stats() if self.pending_queue else {}
            ),
            "execution_stats": executor.get_execution_stats(),
        }

        # 不变量校验（P-011 D2）：默认 report 仅附诊断字段，不中断回测
        invariant_mode = self.cfg.invariant_mode
        if invariant_mode != "off" and snapshots:
            invariant_report = check_all(
                snapshots,
                executor.trade_log.get_trades(),
                executor.get_execution_stats(),
                initial_capital=self.cfg.initial_capital,
                mode=invariant_mode,
            )
            additional_info["invariant_report"] = invariant_report.to_dict()
            if invariant_mode == "raise" and not invariant_report.ok:
                raise InvariantViolationError(invariant_report.violations[0])

        # 偏差声明（P-011 D6）：字段全部来自运行时状态或能力常量
        execution_timing = (
            self._execution_policy.timing.value
            if self._execution_policy is not None
            else "next_open"
        )
        additional_info["validation_declaration"] = build_validation_declaration(
            risk_free_rate=self.cfg.risk_free_rate,
            universe_report=self._universe_report(),
            execution_timing=execution_timing,
            benchmark_configured=self.cfg.benchmark is not None,
        )

        if not trades_df.empty:
            trades_path = output_dir / "trades.csv"
            trades_df.to_csv(trades_path, index=False, encoding="utf-8-sig")
            logger.info(f"交易记录已保存: {trades_path}")

        if snapshots:
            snapshots_df = tracker.get_snapshots_df()
            snapshots_path = output_dir / "portfolio_snapshots.csv"
            snapshots_df.to_csv(snapshots_path, index=False, encoding="utf-8-sig")
            logger.info(f"持仓快照已保存: {snapshots_path}")

        if self.pending_queue:
            pending_log_df = self.pending_queue.get_event_log()
            if not pending_log_df.empty:
                pending_log_path = output_dir / "pending_order_events.csv"
                pending_log_df.to_csv(pending_log_path, index=False, encoding="utf-8-sig")
                logger.info(f"待执行订单事件日志已保存: {pending_log_path}")

        portfolio_value_series = pd.Series()
        if snapshots:
            snapshots_df = tracker.get_snapshots_df()
            if "total_value" in snapshots_df.columns and "date" in snapshots_df.columns:
                portfolio_value_series = snapshots_df.set_index("date")["total_value"]
                logger.info(f"✓ 组合价值序列已生成: {len(portfolio_value_series)} 个数据点")

        results = {
            "portfolio_value": portfolio_value_series,
            "performance_metrics": report_data["metrics"],
            "charts": report_data["charts"],
            "reports": report_data["reports"],
            "additional_info": additional_info,
            "unclosed_positions": self._unclosed_positions,
        }

        # 运行清单（P-011 D7）：写 output_dir + trace 目录；写失败不影响回测结果
        data_files = [
            self.cfg.close_file,
            self.cfg.open_file,
            self.cfg.high_file,
            self.cfg.low_file,
            self.cfg.adj_factor_file,
            self.cfg.suspend_file,
            self.cfg.industry_file,
            self.cfg.st_file,
            *self.cfg.factor_files,
        ]
        if self.cfg.mktcap_file:
            data_files.append(self.cfg.mktcap_file)
        finished_at = datetime.now()
        manifest = None
        if self.cfg.write_manifest:
            try:
                manifest = build_manifest(
                    self.cfg,
                    data_dir=self.cfg.data_dir,
                    data_files=data_files,
                    caliber={
                        "ruleset_version": RULESET_VERSION,
                        "price_modes": self.cfg.price_modes,
                        "next_day_tradable_mode": getattr(
                            self.universe, "next_day_tradable_mode", None
                        ),
                        "api_version": __api_version__,
                    },
                    started_at=self._run_started_at or finished_at,
                    finished_at=finished_at,
                    outputs={
                        "trades": "trades.csv",
                        "snapshots": "portfolio_snapshots.csv",
                        "metrics": "performance_metrics.csv",
                    },
                    benchmark=self.cfg.benchmark,
                )
                targets = [output_dir]
                if self.cfg.dump_layers_dir is not None:
                    targets.append(Path(self.cfg.dump_layers_dir))
                write_manifest(manifest, targets)
            except OSError as exc:
                logger.warning("manifest 写入失败（不影响回测结果）: %s", exc)
        if manifest is not None:
            additional_info["input_fingerprint"] = manifest["input_fingerprint"]

        logger.info("回测结果生成完成")
        return results
