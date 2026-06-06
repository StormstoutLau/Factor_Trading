"""
风险监控模块 - 主动盯市 + 止损/追保/强平

与 risk_monitor.py 的职责划分:
    - risk_manager.py (本模块): 主动盯市风险管理器
      → 处理持仓级别风险 (个股止损、保证金检查、强平)
      → 基于每日盯市生成即时执行动作 (RiskAction 枚举)
      → 关注: 单个持仓的盈亏、保证金比例
    - risk_monitor.py: 多维度风险监控器
      → 处理组合/市场级别风险 (基本面、行业、宏观、资金、情绪)
      → 生成预警信号 (RiskSignal) 和风控建议 (MonitorAction)
      → 关注: 市场环境、行业趋势、宏观政策、资金流向

Phase 3: 主动盯市策略
- RiskAction: 风险动作枚举
- RiskActionItem: 风险动作数据结构
- StopLossConfig: 止损配置
- MarkToMarketPolicy: 主动盯市策略（检查持仓生成风险动作）

设计原则:
    1. 最小侵入: 纯新增模块，不修改现有引擎代码
    2. 解耦: 风险检查与执行分离，MarkToMarketPolicy 只生成动作，不执行
    3. 可插拔: 可配置启用/禁用止损和保证金检查
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from core.config import MarginConfig

if TYPE_CHECKING:
    from core.tracker import Position


# ============================================================================
# Module 1: RiskAction - 风险动作
# ============================================================================


class RiskAction(Enum):
    """风险动作类型"""
    NONE = auto()           # 无风险
    STOP_LOSS = auto()      # 止损
    MARGIN_CALL = auto()    # 追加保证金
    FORCE_CLOSE = auto()    # 强制平仓


@dataclass
class RiskActionItem:
    """风险动作明细

    Attributes:
        action: 风险动作类型
        asset: 触发风险的资产代码
        reason: 触发原因描述
        severity: 严重程度 (0-1, 1=最高)
    """
    action: RiskAction
    asset: str
    reason: str
    severity: float = 0.0

    @property
    def requires_immediate_action(self) -> bool:
        """是否需要立即执行"""
        return self.action in (RiskAction.FORCE_CLOSE, RiskAction.STOP_LOSS)


# ============================================================================
# Module 2: StopLossConfig - 止损配置
# ============================================================================


@dataclass
class StopLossConfig:
    """止损配置

    Attributes:
        stop_loss_pct: 固定止损线 (负值, 如 -0.10 表示亏损 10% 止损)
        trailing_stop_pct: 移动止损线 (负值, 从最高点回撤触发)
        enabled: 是否启用止损
    """
    stop_loss_pct: float = -0.10
    trailing_stop_pct: float = -0.05
    enabled: bool = True

    def check_stop_loss(self, unrealized_pnl_pct: float) -> RiskActionItem | None:
        """检查是否触发止损

        Args:
            unrealized_pnl_pct: 未实现盈亏百分比 (负值表示亏损)

        Returns:
            RiskActionItem 或 None (未触发)
        """
        if not self.enabled:
            return None

        if unrealized_pnl_pct <= self.stop_loss_pct:
            severity = min(1.0, abs(unrealized_pnl_pct) / abs(self.stop_loss_pct))
            return RiskActionItem(
                action=RiskAction.STOP_LOSS,
                asset="",
                reason=f"止损触发: 亏损 {unrealized_pnl_pct:.1%} >= {self.stop_loss_pct:.1%}",
                severity=severity,
            )

        return None


# ============================================================================
# Module 3: MarkToMarketPolicy - 主动盯市策略
# ============================================================================


@dataclass
class MarkToMarketPolicy:
    """主动盯市策略

    检查持仓并生成风险动作:
        1. 止损检查: 亏损超过阈值 → STOP_LOSS
        2. 保证金检查: 保证金不足 → MARGIN_CALL / FORCE_CLOSE

    注意: 此模块只生成风险动作，不执行。执行由引擎负责。
    """

    stop_loss_config: StopLossConfig = field(default_factory=StopLossConfig)
    margin_config: MarginConfig = field(default_factory=MarginConfig)

    def check_position(self, position: Position) -> list[RiskActionItem]:
        """检查单个持仓的风险

        Args:
            position: 持仓对象

        Returns:
            风险动作列表
        """
        results: list[RiskActionItem] = []

        # 无持仓跳过
        if position.quantity == 0:
            return results

        # 1. 止损检查
        if self.stop_loss_config.enabled:
            cost_basis = abs(position.quantity) * position.avg_cost
            if cost_basis > 0:
                pnl_pct = position.unrealized_pnl / cost_basis
                stop_result = self.stop_loss_config.check_stop_loss(pnl_pct)
                if stop_result is not None:
                    stop_result.asset = position.stock
                    results.append(stop_result)

        # 2. 保证金检查 (仅期货/杠杆品种)
        if position.margin_used > 0 and position.market_value > 0:
            margin_ratio = position.margin_used / position.market_value

            if margin_ratio < self.margin_config.force_liquidation_ratio:
                results.append(RiskActionItem(
                    action=RiskAction.FORCE_CLOSE,
                    asset=position.stock,
                    reason=(
                        f"保证金比例 {margin_ratio:.1%} "
                        f"低于强平线 {self.margin_config.force_liquidation_ratio:.1%}"
                    ),
                    severity=1.0,
                ))
            elif margin_ratio < self.margin_config.maintenance_margin_ratio:
                results.append(RiskActionItem(
                    action=RiskAction.MARGIN_CALL,
                    asset=position.stock,
                    reason=(
                        f"保证金比例 {margin_ratio:.1%} "
                        f"低于维持线 {self.margin_config.maintenance_margin_ratio:.1%}"
                    ),
                    severity=0.7,
                ))

        return results

    def check_portfolio(
        self, positions: dict[str, Position]
    ) -> list[RiskActionItem]:
        """检查整个组合的风险

        Args:
            positions: 持仓字典 (asset → Position)

        Returns:
            所有风险动作的列表
        """
        all_results: list[RiskActionItem] = []
        for position in positions.values():
            all_results.extend(self.check_position(position))
        return all_results