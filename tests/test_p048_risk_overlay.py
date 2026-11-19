"""P-048 风险 overlay 纯函数测试（IMPL §7.1 / DESIGN §6.2 §12）。

A5：ramp 期望值全部为**手算闭式**（``dd_soft=0.08 / dd_hard=0.12 / b_min=0``）：
``dd=0.05 → 1.0`` / ``0.10 → 0.5`` / ``0.15 → 0.0``，禁止跑后回填。
"""

from __future__ import annotations

import numpy as np
import pytest

from core.risk_overlay import (
    DEFENSIVE_POLICIES,
    OVERLAY_CAPABILITIES,
    CapabilityError,
    DeRiskContext,
    RiskOverlayConfig,
    apply_overlay,
    compute_drawdown,
    resolve_policy,
)


def _ctx(dd: float, weights: dict | None = None) -> DeRiskContext:
    return DeRiskContext(
        drawdown=dd,
        peak_nav=100.0,
        current_nav=100.0 * (1.0 - dd),
        weights=weights if weights is not None else {"A": 1.0},
    )


def _cfg(**kwargs) -> RiskOverlayConfig:
    params = {"enabled": True}
    params.update(kwargs)
    return RiskOverlayConfig(**params)


# ---------------------------------------------------------------------------
# 策略闭式（A5 手算）
# ---------------------------------------------------------------------------
def test_ramp_three_points():
    """DESIGN §6.2 三点：0.05 → 1.0；0.10 → 0.5；0.15 → 0.0。"""
    policy = resolve_policy("cash_scaling", _cfg(defensive_policy="cash_scaling"))
    assert policy.plan(_ctx(0.05)).scale == pytest.approx(1.0)
    assert policy.plan(_ctx(0.10)).scale == pytest.approx(0.5)
    assert policy.plan(_ctx(0.15)).scale == pytest.approx(0.0)


def test_ramp_with_b_min():
    """b_min=0.2：dd=0.10 → 1−0.5×0.8 = 0.6；dd=0.15 → 0.2（硬阈）。"""
    policy = resolve_policy("cash_scaling", _cfg(defensive_policy="cash_scaling", b_min=0.2))
    assert policy.plan(_ctx(0.10)).scale == pytest.approx(0.6)
    assert policy.plan(_ctx(0.15)).scale == pytest.approx(0.2)


def test_fixed_floor():
    """单阈值：dd=0.11 → 1.0；dd=0.13 → b_min。"""
    policy = resolve_policy("fixed_floor", _cfg(defensive_policy="fixed_floor"))
    assert policy.plan(_ctx(0.11)).scale == pytest.approx(1.0)
    assert policy.plan(_ctx(0.13)).scale == pytest.approx(0.0)


def test_ladder_deepest_hit():
    """最深命中档：dd=0.13 → 0.25；dd=0.21 → 0.0。"""
    policy = resolve_policy("ladder", _cfg(defensive_policy="ladder"))
    assert policy.plan(_ctx(0.13)).scale == pytest.approx(0.25)
    assert policy.plan(_ctx(0.21)).scale == pytest.approx(0.0)


def test_reserved_policies_raise():
    """2 个预留策略调用即 fail-loud（不静默降级为恒等）。"""
    for name in ("sector_rotation", "hedge_overlay"):
        policy = resolve_policy(name, _cfg(defensive_policy=name))
        with pytest.raises(CapabilityError):
            policy.plan(_ctx(0.2))


def test_unknown_policy_raises():
    with pytest.raises(ValueError, match="未知 defensive_policy"):
        resolve_policy("nope", _cfg())


def test_registry_has_six_keys():
    assert set(DEFENSIVE_POLICIES) == {
        "none",
        "cash_scaling",
        "fixed_floor",
        "ladder",
        "sector_rotation",
        "hedge_overlay",
    }


def test_overlay_capabilities_exact():
    """精确键集（同型断言，防悄悄扩容）；不扩展 P-059 的 8 键表。"""
    assert set(OVERLAY_CAPABILITIES) == {"defensive_asset_rotation", "hedge_overlay"}
    for entry in OVERLAY_CAPABILITIES.values():
        assert entry["supported"] is False
        assert entry["note"]


# ---------------------------------------------------------------------------
# 不变式（DESIGN §12 I1-I7）
# ---------------------------------------------------------------------------
def test_i1_scale_bounds():
    """I1：0 ≤ scale_total ≤ 1（不加杠杆），含 scale_floor 网格。"""
    for dd in (0.0, 0.05, 0.10, 0.12, 0.20, 0.50):
        for b_min in (0.0, 0.3):
            for floor in (0.0, 0.25):
                cfg = _cfg(defensive_policy="cash_scaling", b_min=b_min, scale_floor=floor)
                result = apply_overlay(
                    {"A": 1.0},
                    nav_history=[100.0, 100.0 * (1.0 - dd)],
                    config=cfg,
                )
                assert 0.0 <= result.scale_total <= 1.0
                assert all(weight >= 0.0 for weight in result.weights.values())


def test_i2_no_renormalize():
    """I2：标量乘法不重新归一 → Σ w_out ≤ Σ w_in。"""
    weights = {"A": 0.6, "B": 0.4}
    result = apply_overlay(
        weights, nav_history=[100.0, 90.0], config=_cfg(defensive_policy="cash_scaling")
    )
    assert sum(result.weights.values()) <= sum(weights.values()) + 1e-12
    assert result.scale_total < 1.0


def test_i3_cash_residual():
    """I3：cash_residual ≥ 0 且 Σw + cash == 1。"""
    result = apply_overlay(
        {"A": 0.5, "B": 0.5},
        nav_history=[100.0, 92.0],
        config=_cfg(defensive_policy="cash_scaling"),
    )
    total = sum(result.weights.values())
    assert result.cash_residual >= 0.0
    assert total + result.cash_residual == pytest.approx(1.0)


def test_i5_monotone():
    """I5：σ 越大 scale_vol 越小；scale_floor 兜住下界。"""
    low_sigma = apply_overlay(
        {"A": 1.0},
        nav_history=[100.0],
        cov=np.array([[0.01]]),
        codes=["A"],
        config=_cfg(target_vol=0.05, defensive_policy="none"),
    )
    high_sigma = apply_overlay(
        {"A": 1.0},
        nav_history=[100.0],
        cov=np.array([[0.04]]),
        codes=["A"],
        config=_cfg(target_vol=0.05, defensive_policy="none"),
    )
    # σ=0.1 → 0.5；σ=0.2 → 0.25
    assert low_sigma.scale_vol == pytest.approx(0.5)
    assert high_sigma.scale_vol == pytest.approx(0.25)
    assert high_sigma.scale_total < low_sigma.scale_total

    floored = apply_overlay(
        {"A": 1.0},
        nav_history=[100.0, 50.0],
        config=_cfg(defensive_policy="cash_scaling", scale_floor=0.25),
    )
    assert floored.scale_total == pytest.approx(0.25)


def test_i4_identity():
    """I4 精确条件：policy="none" 且 target_vol=None → 逐值相等、scale_total=1。"""
    weights = {"A": 0.7, "B": 0.3}
    result = apply_overlay(
        weights,
        nav_history=[100.0, 80.0],  # DD=20% 但策略恒等
        config=_cfg(defensive_policy="none", target_vol=None),
    )
    assert result.weights == weights
    assert result.scale_total == pytest.approx(1.0)
    assert result.cash_residual == pytest.approx(0.0)

    # 反例：policy="none" 不是门控——target_vol 非 None 时 vol 缩放仍生效
    scaled = apply_overlay(
        {"A": 1.0},
        nav_history=[100.0, 80.0],
        cov=np.array([[0.04]]),
        codes=["A"],
        config=_cfg(defensive_policy="none", target_vol=0.05),
    )
    assert scaled.scale_total == pytest.approx(0.25)


def test_i6_drawdown_bounds():
    """I6：drawdown ∈ [0,1]、peak = max(nav)、空/非正峰值边界。"""
    assert compute_drawdown([]) == (0.0, 0.0, 0.0)
    assert compute_drawdown([100.0]) == (0.0, 100.0, 100.0)
    dd, peak, current = compute_drawdown([100.0, 110.0, 105.0])
    assert dd == pytest.approx(1.0 - 105.0 / 110.0)
    assert peak == pytest.approx(110.0)
    assert current == pytest.approx(105.0)
    assert compute_drawdown([100.0, 120.0])[0] == pytest.approx(0.0)
    # peak <= 0 → drawdown 记 0（不做除法）
    assert compute_drawdown([0.0, -5.0]) == (0.0, 0.0, -5.0)


# ---------------------------------------------------------------------------
# 能力边界与配置校验
# ---------------------------------------------------------------------------
def test_hysteresis_raises():
    with pytest.raises(CapabilityError, match="dd_hysteresis"):
        apply_overlay(
            {"A": 1.0},
            nav_history=[100.0, 90.0],
            config=_cfg(dd_hysteresis=True),
        )


def test_config_validation():
    with pytest.raises(ValueError, match="dd_soft"):
        RiskOverlayConfig(dd_soft=0.12, dd_hard=0.08)
    with pytest.raises(ValueError, match="b_min"):
        RiskOverlayConfig(b_min=1.5)
    with pytest.raises(ValueError, match="scale_floor"):
        RiskOverlayConfig(scale_floor=-0.1)
    with pytest.raises(ValueError, match="target_vol"):
        RiskOverlayConfig(target_vol=0.0)
