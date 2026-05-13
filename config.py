"""
兼容性适配层 - config

此文件同时暴露:
1. 旧版 dataclass 配置 (core.config) — 完全向后兼容
2. 新版 Pydantic 配置 (core.config_v2) — 新增验证和热重载

新代码推荐使用:
    from core.config_v2 import BacktestConfig, ConfigHotReloader

旧代码仍然可用:
    from config import BacktestConfig  # 返回 dataclass 版本
"""

from __future__ import annotations

# 旧版 dataclass 配置（完全向后兼容）
from core.config import (  # noqa: F401
    BacktestConfig,
    CostConfig,
    UniverseConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
    ExecutionPriceType,
    DistillationSource,
    LearningMode,
    AgentDistillationConfig,
)

# 新版 Pydantic 配置（新增验证和热重载）
from core.config_v2 import (  # noqa: F401
    BacktestConfig as BacktestConfigV2,
    CostConfig as CostConfigV2,
    UniverseConfig as UniverseConfigV2,
    FactorConfig as FactorConfigV2,
    OptimizerConfig as OptimizerConfigV2,
    RebalanceConfig as RebalanceConfigV2,
    ConfigHotReloader,
    create_default_config,
    load_config,
    save_config,
)
