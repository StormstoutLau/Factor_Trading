"""
Plugin Registry — 统一插件注册中心

借鉴 OpenAlice Broker Registry 设计:
- 每个插件自注册: config_schema + factory_function + metadata
- 新增插件只需注册，无需修改框架代码
- 支持动态发现、配置验证、元数据查询

适用于:
- Optimizer (组合优化器)
- Trigger (再平衡触发器)
- Filter (股票池过滤器)
- Guard (风控规则)
- Agent (Agent 类型)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PluginEntry(Generic[T]):
    """插件注册条目"""

    name: str
    description: str
    factory: Callable[..., T]
    config_schema: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    category: str = ""

    def create(self, config: Optional[Any] = None, **kwargs: Any) -> T:
        """创建插件实例"""
        if config is not None:
            return self.factory(config, **kwargs)
        return self.factory(**kwargs)


class PluginRegistry(Generic[T]):
    """
    插件注册中心

    支持按名称注册、查询、创建实例
    """

    def __init__(self, category: str):
        self.category = category
        self._plugins: dict[str, PluginEntry[T]] = {}

    # ==================== Registration ====================

    def register(
        self,
        name: str,
        factory: Callable[..., T],
        description: str = "",
        config_schema: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PluginRegistry[T]:
        """
        注册插件

        Args:
            name: 插件唯一标识名
            factory: 工厂函数，签名: (config, **kwargs) -> T
            description: 插件描述
            config_schema: 配置参数 schema（用于验证和文档）
            metadata: 额外元数据
        """
        if name in self._plugins:
            logger.warning(f"Plugin '{name}' already registered, overwriting")

        self._plugins[name] = PluginEntry(
            name=name,
            description=description,
            factory=factory,
            config_schema=config_schema,
            metadata=metadata or {},
            category=self.category,
        )
        logger.debug(f"Registered {self.category} plugin: {name}")
        return self

    def unregister(self, name: str) -> bool:
        """注销插件"""
        if name in self._plugins:
            del self._plugins[name]
            return True
        return False

    # ==================== Query ====================

    def get(self, name: str) -> Optional[PluginEntry[T]]:
        """获取插件条目"""
        return self._plugins.get(name)

    def has(self, name: str) -> bool:
        """检查插件是否已注册"""
        return name in self._plugins

    def list_names(self) -> list[str]:
        """列出所有插件名称"""
        return list(self._plugins.keys())

    def list_all(self) -> list[PluginEntry[T]]:
        """列出所有插件条目"""
        return list(self._plugins.values())

    def get_inventory(self) -> list[dict[str, Any]]:
        """
        获取插件清单（用于 UI 展示）

        Returns:
            [{name, description, category, metadata}]
        """
        return [
            {
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "metadata": p.metadata,
            }
            for p in self._plugins.values()
        ]

    # ==================== Factory ====================

    def create(self, name: str, config: Optional[Any] = None, **kwargs: Any) -> T:
        """
        创建插件实例

        Args:
            name: 插件名称
            config: 配置对象
            **kwargs: 额外参数

        Raises:
            KeyError: 插件未注册
        """
        entry = self._plugins.get(name)
        if entry is None:
            available = ", ".join(self.list_names())
            raise KeyError(
                f"{self.category} plugin '{name}' not found. "
                f"Available: {available or 'none'}"
            )
        return entry.create(config, **kwargs)

    def create_or_default(
        self, name: str, default_name: str, config: Optional[Any] = None, **kwargs: Any
    ) -> T:
        """
        创建插件实例，如果不存在则使用默认

        Args:
            name: 目标插件名称
            default_name: 默认插件名称
            config: 配置对象
            **kwargs: 额外参数
        """
        try:
            return self.create(name, config, **kwargs)
        except KeyError:
            logger.warning(
                f"Plugin '{name}' not found, falling back to '{default_name}'"
            )
            return self.create(default_name, config, **kwargs)


# ==================== Global Registries ====================

_optimizer_registry: Optional[PluginRegistry[Any]] = None
_trigger_registry: Optional[PluginRegistry[Any]] = None
_filter_registry: Optional[PluginRegistry[Any]] = None
_guard_registry: Optional[PluginRegistry[Any]] = None
_agent_registry: Optional[PluginRegistry[Any]] = None


def get_optimizer_registry() -> PluginRegistry[Any]:
    """获取 Optimizer 注册中心"""
    global _optimizer_registry
    if _optimizer_registry is None:
        _optimizer_registry = PluginRegistry("optimizer")
    return _optimizer_registry


def get_trigger_registry() -> PluginRegistry[Any]:
    """获取 Trigger 注册中心"""
    global _trigger_registry
    if _trigger_registry is None:
        _trigger_registry = PluginRegistry("trigger")
    return _trigger_registry


def get_filter_registry() -> PluginRegistry[Any]:
    """获取 Filter 注册中心"""
    global _filter_registry
    if _filter_registry is None:
        _filter_registry = PluginRegistry("filter")
    return _filter_registry


def get_guard_registry() -> PluginRegistry[Any]:
    """获取 Guard 注册中心"""
    global _guard_registry
    if _guard_registry is None:
        _guard_registry = PluginRegistry("guard")
    return _guard_registry


def get_agent_registry() -> PluginRegistry[Any]:
    """获取 Agent 注册中心"""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = PluginRegistry("agent")
    return _agent_registry


# ==================== Decorator Helpers ====================


def register_optimizer(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Optimizer 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_optimizer_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator


def register_trigger(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Trigger 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_trigger_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator


def register_filter(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Filter 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_filter_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator


def register_guard(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Guard 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_guard_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator


def register_agent(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Agent 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_agent_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator
