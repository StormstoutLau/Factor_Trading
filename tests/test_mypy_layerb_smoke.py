"""P-007 层 B：空因子 fail-fast 与结果生成守卫的 smoke 测试（RED 于实现前）"""

from __future__ import annotations

import pytest

from core.config import BacktestConfig
from core.engine_v2 import BacktestEngineV2


def test_empty_factor_files_raises_value_error():
    """D1：空 factor_files 应在 setup() 入口 fail-fast，且不创建组件"""
    engine = BacktestEngineV2(BacktestConfig())

    with pytest.raises(ValueError, match="factor_files"):
        engine.setup()

    assert engine.dm is None


def test_generate_results_requires_setup():
    """D3：未 setup 直接生成结果应抛 RuntimeError，而非 AttributeError"""
    engine = BacktestEngineV2(BacktestConfig())

    with pytest.raises(RuntimeError, match="setup"):
        engine._generate_results()
