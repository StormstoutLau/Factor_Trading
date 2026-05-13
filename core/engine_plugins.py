"""
Engine 即插即用扩展模块

非侵入式设计原则:
- 原有 Engine 代码完全不变
- 通过可选参数注入扩展功能
- 扩展模块不修改 Engine 状态，只记录/检查
- 移除扩展后 Engine 仍能正常运行

使用方式:
    from core.engine_plugins import EventLogPlugin, GuardPlugin, PluginIntegration
    
    # 方式1: 手动集成
    engine = BacktestEngine(config)
    engine.setup()
    
    event_plugin = EventLogPlugin(engine)
    guard_plugin = GuardPlugin(engine, GuardPipeline.default())
    
    # 方式2: 一键集成
    integration = PluginIntegration(engine)
    integration.enable_all()  # 启用所有插件
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import pandas as pd

from core.event_log import EventLog, log_event
from core.guard_pipeline import GuardContext, GuardPipeline, create_guard_context_from_engine
from core.registry import get_optimizer_registry, get_trigger_registry

logger = logging.getLogger(__name__)


# ==================== EventLog 插件 ====================


class EventLogPlugin:
    """
    EventLog 即插即用插件

    旁路记录引擎关键事件，不影响主流程
    """

    def __init__(
        self,
        engine: Any,
        event_log: Optional[EventLog] = None,
        log_path: str = "data/events.jsonl",
    ):
        self.engine = engine
        self.event_log = event_log or EventLog(log_path=log_path)
        self._subscribers: list[Callable] = []
        self._enabled = False

    def enable(self) -> EventLogPlugin:
        """启用事件记录"""
        if self._enabled:
            return self

        self._enabled = True

        # 记录引擎初始化事件
        self._log("engine.init", {
            "initial_capital": self.engine.cfg.initial_capital,
            "optimizer": self.engine.cfg.optimizer.method,
            "rebalance": self.engine.cfg.rebalance.method,
        })

        logger.info("EventLogPlugin 已启用")
        return self

    def disable(self) -> EventLogPlugin:
        """禁用事件记录"""
        self._enabled = False
        logger.info("EventLogPlugin 已禁用")
        return self

    def log_rebalance(self, date: pd.Timestamp, target_weights: dict[str, float]) -> None:
        """记录再平衡事件"""
        if not self._enabled:
            return
        self._log("engine.rebalance", {
            "date": str(date),
            "n_stocks": len(target_weights),
            "top_stocks": list(target_weights.keys())[:5],
        })

    def log_trade(
        self,
        date: pd.Timestamp,
        stock: str,
        side: str,
        quantity: float,
        price: float,
        success: bool,
    ) -> None:
        """记录交易事件"""
        if not self._enabled:
            return
        self._log("engine.trade", {
            "date": str(date),
            "stock": stock,
            "side": side,
            "quantity": quantity,
            "price": price,
            "success": success,
        })

    def log_pending(
        self,
        date: pd.Timestamp,
        stock: str,
        side: str,
        quantity: float,
        action: str,  # 'created' | 'executed' | 'expired' | 'fallback'
    ) -> None:
        """记录待执行订单事件"""
        if not self._enabled:
            return
        self._log("engine.pending", {
            "date": str(date),
            "stock": stock,
            "side": side,
            "quantity": quantity,
            "action": action,
        })

    def log_day_end(self, date: pd.Timestamp, portfolio_value: float) -> None:
        """记录日终事件"""
        if not self._enabled:
            return
        self._log("engine.day_end", {
            "date": str(date),
            "portfolio_value": portfolio_value,
        })

    def _log(self, event_type: str, payload: dict[str, Any]) -> None:
        """内部记录方法"""
        try:
            self.event_log.append(event_type, payload, source="engine")
        except Exception as e:
            logger.debug(f"EventLog 记录失败: {e}")

    @property
    def is_enabled(self) -> bool:
        return self._enabled


# ==================== GuardPipeline 插件 ====================


class GuardPlugin:
    """
    GuardPipeline 即插即用插件

    在交易执行前进行风控检查，可配置阻断或仅警告
    """

    def __init__(
        self,
        engine: Any,
        pipeline: Optional[GuardPipeline] = None,
        mode: str = "block",  # 'block' | 'warn'
    ):
        self.engine = engine
        self.pipeline = pipeline or GuardPipeline.default()
        self.mode = mode
        self._enabled = False
        self._blocked_count = 0
        self._warning_count = 0

    def enable(self) -> GuardPlugin:
        """启用风控检查"""
        self._enabled = True
        logger.info(f"GuardPlugin 已启用 (mode={self.mode})")
        return self

    def disable(self) -> GuardPlugin:
        """禁用风控检查"""
        self._enabled = False
        logger.info("GuardPlugin 已禁用")
        return self

    def check_trade(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
    ) -> tuple[bool, list[str]]:
        """
        检查交易是否允许

        Returns:
            (allowed, reasons)
        """
        if not self._enabled:
            return True, []

        try:
            ctx = create_guard_context_from_engine(
                self.engine, action, symbol, quantity, price
            )
            reasons = self.pipeline.get_blocking_reasons(ctx)

            if reasons:
                if self.mode == "block":
                    self._blocked_count += 1
                    logger.warning(f"Guard 阻断交易: {symbol} {action} - {reasons}")
                    return False, reasons
                else:
                    self._warning_count += 1
                    logger.warning(f"Guard 警告: {symbol} {action} - {reasons}")
                    return True, reasons

            return True, []
        except Exception as e:
            logger.warning(f"Guard 检查异常: {e}")
            return True, []  # 异常时允许执行，避免阻断正常交易

    def check_and_log(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
        event_plugin: Optional[EventLogPlugin] = None,
    ) -> bool:
        """检查并记录结果"""
        allowed, reasons = self.check_trade(action, symbol, quantity, price)

        if event_plugin and event_plugin.is_enabled:
            event_plugin._log("engine.guard_check", {
                "action": action,
                "symbol": symbol,
                "allowed": allowed,
                "reasons": reasons,
                "mode": self.mode,
            })

        return allowed

    def get_stats(self) -> dict[str, Any]:
        """获取风控统计"""
        return {
            "enabled": self._enabled,
            "mode": self.mode,
            "blocked_count": self._blocked_count,
            "warning_count": self._warning_count,
        }

    @property
    def is_enabled(self) -> bool:
        return self._enabled


# ==================== PluginRegistry 集成 ====================


class RegistryPlugin:
    """
    PluginRegistry 即插即用集成

    将原有的 build_optimizer / build_trigger 替换为 Registry 模式
    不修改原有函数，而是提供替代方案
    """

    def __init__(self):
        self._registered = False

    def enable(self) -> RegistryPlugin:
        """注册所有内置插件到 Registry"""
        if self._registered:
            return self

        self._register_optimizers()
        self._register_triggers()

        self._registered = True
        logger.info("RegistryPlugin 已启用")
        return self

    def _register_optimizers(self) -> None:
        """注册优化器到 Registry"""
        from portfolio import (
            EqualWeightOptimizer,
            MinVarianceOptimizer,
            MeanVarianceOptimizer,
            RiskParityOptimizer,
        )

        reg = get_optimizer_registry()

        # 避免重复注册
        if reg.has("equal_weight"):
            return

        reg.register(
            "equal_weight",
            lambda cfg: EqualWeightOptimizer(cfg),
            description="等权重优化",
            config_schema={"target_count": "int", "max_weight": "float"},
        )
        reg.register(
            "min_variance",
            lambda cfg: MinVarianceOptimizer(cfg),
            description="最小方差优化",
        )
        reg.register(
            "mean_variance",
            lambda cfg: MeanVarianceOptimizer(cfg),
            description="均值方差优化",
        )
        reg.register(
            "risk_parity",
            lambda cfg: RiskParityOptimizer(cfg),
            description="风险平价优化",
        )

        logger.info(f"已注册 {len(reg.list_names())} 个优化器")

    def _register_triggers(self) -> None:
        """注册触发器到 Registry"""
        from rebalance import FixedIntervalTrigger, ConditionalTrigger, HybridTrigger

        reg = get_trigger_registry()

        if reg.has("fixed"):
            return

        # 注意：trigger 需要 trade_dates，这里注册工厂函数
        reg.register(
            "fixed",
            lambda cfg, dates: FixedIntervalTrigger(cfg, dates),
            description="固定间隔触发",
        )
        reg.register(
            "conditional",
            lambda cfg, dates: ConditionalTrigger(cfg),
            description="条件触发",
        )
        reg.register(
            "hybrid",
            lambda cfg, dates: HybridTrigger(cfg, dates),
            description="混合触发",
        )

        logger.info(f"已注册 {len(reg.list_names())} 个触发器")

    def create_optimizer(self, config: Any):
        """通过 Registry 创建优化器"""
        if not self._registered:
            self.enable()
        return get_optimizer_registry().create(config.method, config)

    def create_trigger(self, config: Any, trade_dates: pd.DatetimeIndex):
        """通过 Registry 创建触发器"""
        if not self._registered:
            self.enable()
        return get_trigger_registry().create(config.method, config, trade_dates)

    def get_inventory(self) -> dict[str, list[dict]]:
        """获取已注册插件清单"""
        return {
            "optimizers": get_optimizer_registry().get_inventory(),
            "triggers": get_trigger_registry().get_inventory(),
        }


# ==================== 一键集成 ====================


class PluginIntegration:
    """
    一键集成所有插件

    使用方式:
        engine = BacktestEngine(config)
        engine.setup()
        
        integration = PluginIntegration(engine)
        integration.enable_all()  # 启用 EventLog + Guard + Registry
        
        results = engine.run()
        
        stats = integration.get_stats()
    """

    def __init__(self, engine: Any):
        self.engine = engine
        self.event_plugin: Optional[EventLogPlugin] = None
        self.guard_plugin: Optional[GuardPlugin] = None
        self.registry_plugin: Optional[RegistryPlugin] = None

    def enable_event_log(
        self,
        log_path: str = "data/events.jsonl",
        event_log: Optional[EventLog] = None,
    ) -> PluginIntegration:
        """启用 EventLog 插件"""
        self.event_plugin = EventLogPlugin(self.engine, event_log, log_path)
        self.event_plugin.enable()
        return self

    def enable_guard(
        self,
        pipeline: Optional[GuardPipeline] = None,
        mode: str = "block",
    ) -> PluginIntegration:
        """启用 Guard 插件"""
        self.guard_plugin = GuardPlugin(self.engine, pipeline, mode)
        self.guard_plugin.enable()
        return self

    def enable_registry(self) -> PluginIntegration:
        """启用 Registry 插件"""
        self.registry_plugin = RegistryPlugin()
        self.registry_plugin.enable()
        return self

    def enable_all(self) -> PluginIntegration:
        """启用所有插件"""
        self.enable_event_log()
        self.enable_guard()
        self.enable_registry()
        return self

    def get_stats(self) -> dict[str, Any]:
        """获取所有插件统计"""
        stats = {}
        if self.guard_plugin:
            stats["guard"] = self.guard_plugin.get_stats()
        if self.event_plugin:
            stats["event_log"] = {
                "enabled": self.event_plugin.is_enabled,
                "last_seq": self.event_plugin.event_log.last_seq(),
            }
        if self.registry_plugin:
            stats["registry"] = self.registry_plugin.get_inventory()
        return stats
