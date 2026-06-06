"""
量化投研系统 UI 控制台
=======================

设计风格参考：
- Bloomberg Terminal（黑色背景 + 亮色数据）
- TradingView（图表为主 + 侧边栏控制）
- Wind/同花顺iFinD（中文金融终端布局）

架构设计：
1. 使用界面（Trading Mode）：面向交易员，简洁高效
2. 调试界面（Debug Mode）：面向开发者，可视化追溯每一步
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. 视觉设计系统（Bloomberg Terminal 风格）
# ============================================================

class TerminalTheme:
    """终端配色方案"""
    
    # 主色调
    BG_PRIMARY = "#0a0a0a"        # 深黑背景
    BG_SECONDARY = "#141414"      # 次级背景
    BG_PANEL = "#1a1a1a"          # 面板背景
    
    # 文字色
    TEXT_PRIMARY = "#e0e0e0"      # 主文字
    TEXT_SECONDARY = "#888888"    # 次级文字
    TEXT_MUTED = "#555555"        # 弱化文字
    
    # 数据色（金融终端标准）
    UP = "#00c853"                # 上涨绿
    DOWN = "#ff1744"              # 下跌红
    NEUTRAL = "#ffd600"           # 中性黄
    
    # 功能色
    ACCENT = "#2196f3"            # 强调蓝
    ACCENT_SECONDARY = "#9c27b0"  # 强调紫
    SUCCESS = "#4caf50"           # 成功绿
    WARNING = "#ff9800"           # 警告橙
    ERROR = "#f44336"             # 错误红
    
    # 边框
    BORDER = "#2a2a2a"            # 边框色
    BORDER_ACTIVE = "#3a3a3a"     # 活跃边框
    
    # 字体
    FONT_FAMILY = "Consolas, 'Courier New', monospace"
    FONT_SIZE_SMALL = 11
    FONT_SIZE_NORMAL = 13
    FONT_SIZE_LARGE = 16
    FONT_SIZE_HEADER = 20


# ============================================================
# 2. 调试追踪系统（核心）
# ============================================================

@dataclass
class ExecutionStep:
    """执行步骤记录"""
    step_id: int
    timestamp: datetime
    module: str
    function: str
    line_no: int
    
    # 输入
    inputs: dict[str, Any] = field(default_factory=dict)
    
    # 输出
    outputs: dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: str = "pending"  # pending | running | success | error
    error_message: str = ""
    error_traceback: str = ""
    
    # 性能
    duration_ms: float = 0.0
    memory_mb: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'step_id': self.step_id,
            'timestamp': self.timestamp.isoformat(),
            'module': self.module,
            'function': self.function,
            'line_no': self.line_no,
            'inputs': self._serialize(self.inputs),
            'outputs': self._serialize(self.outputs),
            'status': self.status,
            'error_message': self.error_message,
            'duration_ms': self.duration_ms,
        }
    
    def _serialize(self, obj: Any) -> Any:
        """序列化对象"""
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return {
                'type': 'DataFrame' if isinstance(obj, pd.DataFrame) else 'Series',
                'shape': list(obj.shape),
                'head': obj.head(3).to_dict(),
                'dtypes': str(obj.dtypes) if isinstance(obj, pd.Series) else {k: str(v) for k, v in obj.dtypes.items()},
            }
        elif isinstance(obj, np.ndarray):
            return {'type': 'ndarray', 'shape': list(obj.shape), 'dtype': str(obj.dtype)}
        elif isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize(v) for v in obj[:10]]  # 最多10个
        else:
            try:
                json.dumps(obj)
                return obj
            except:
                return str(obj)


class ExecutionTracer:
    """执行追踪器
    
    记录程序每一步的执行状态，支持可视化追溯
    """
    
    def __init__(self, max_steps: int = 10000):
        self.steps: list[ExecutionStep] = []
        self.step_counter: int = 0
        self.max_steps = max_steps
        self.current_module: str = ""
        self.is_recording: bool = True
        
        # 错误统计
        self.error_count: int = 0
        self.error_types: dict[str, int] = {}
    
    def trace(self, module: str, function: str, line_no: int,
              inputs: dict[str, Any] | None = None) -> ExecutionStep:
        """记录执行步骤"""
        if not self.is_recording:
            return None
        
        self.step_counter += 1
        
        step = ExecutionStep(
            step_id=self.step_counter,
            timestamp=datetime.now(),
            module=module,
            function=function,
            line_no=line_no,
            inputs=inputs or {},
            status="running"
        )
        
        self.steps.append(step)
        
        # 限制历史记录
        if len(self.steps) > self.max_steps:
            self.steps = self.steps[-self.max_steps:]
        
        return step
    
    def complete_step(self, step: ExecutionStep, outputs: dict[str, Any],
                      duration_ms: float = 0.0):
        """完成步骤记录"""
        if step is None:
            return
        
        step.outputs = outputs
        step.status = "success"
        step.duration_ms = duration_ms
    
    def record_error(self, step: ExecutionStep, error: Exception):
        """记录错误"""
        if step is None:
            return
        
        step.status = "error"
        step.error_message = str(error)
        step.error_traceback = traceback.format_exc()
        
        self.error_count += 1
        error_type = type(error).__name__
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
    
    def get_error_summary(self) -> dict[str, Any]:
        """获取错误摘要"""
        return {
            'total_errors': self.error_count,
            'error_types': self.error_types,
            'recent_errors': [
                s.to_dict() for s in self.steps[-10:]
                if s.status == "error"
            ]
        }
    
    def get_execution_flow(self, module_filter: str | None = None) -> list[dict]:
        """获取执行流程"""
        steps = self.steps
        if module_filter:
            steps = [s for s in steps if s.module == module_filter]
        
        return [s.to_dict() for s in steps]
    
    def get_step_detail(self, step_id: int) -> ExecutionStep | None:
        """获取步骤详情"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def export_trace(self, filepath: Path):
        """导出追踪记录"""
        data = {
            'export_time': datetime.now().isoformat(),
            'total_steps': len(self.steps),
            'error_summary': self.get_error_summary(),
            'steps': [s.to_dict() for s in self.steps]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"追踪记录已导出: {filepath}")


# 全局追踪器实例
tracer = ExecutionTracer()


def trace_execution(module: str):
    """装饰器：自动追踪函数执行"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            step = tracer.trace(
                module=module,
                function=func.__name__,
                line_no=func.__code__.co_firstlineno,
                inputs={'args_count': len(args), 'kwargs_keys': list(kwargs.keys())}
            )
            
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds() * 1000
                tracer.complete_step(step, {'result_type': type(result).__name__}, duration)
                return result
            except Exception as e:
                tracer.record_error(step, e)
                raise
        
        return wrapper
    return decorator


# ============================================================
# 3. 使用界面（Trading Mode）
# ============================================================

class TradingUI:
    """交易界面
    
    面向交易员的使用界面，简洁高效
    设计风格：Bloomberg Terminal 极简风
    """
    
    def __init__(self):
        self.theme = TerminalTheme()
        self.active_agents: list[str] = []
        self.market_status: str = "closed"
    
    def render_header(self) -> str:
        """渲染顶部状态栏"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Factor Trading v3.0  │  {now}  │  市场状态: {self.market_status.upper()}  │  活跃Agent: {len(self.active_agents)}  ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
    
    def render_agent_status(self, agents: list[dict]) -> str:
        """渲染Agent状态面板"""
        lines = [
            "┌─ Agent 状态 ──────────────────────────────────────────────────────────────┐",
            "│  ID          │  名称           │  风格      │  状态  │  持仓  │  今日收益   │",
            "├──────────────┼─────────────────┼────────────┼────────┼────────┼─────────────┤",
        ]
        
        for agent in agents:
            status_color = "✓" if agent.get('is_active') else "✗"
            pnl = agent.get('today_pnl', 0)
            pnl_str = f"{pnl:+.2%}" if pnl != 0 else "0.00%"
            pnl_color = "UP" if pnl > 0 else "DOWN" if pnl < 0 else "NEUTRAL"
            
            lines.append(
                f"│  {agent['id']:<12} │  {agent['name']:<15} │  "
                f"{agent['style']:<10} │  {status_color:<6} │  "
                f"{agent.get('positions', 0):<6} │  {pnl_str:<11} │"
            )
        
        lines.append("└──────────────┴─────────────────┴────────────┴────────┴────────┴─────────────┘")
        return "\n".join(lines)
    
    def render_portfolio_summary(self, portfolio: dict) -> str:
        """渲染组合摘要"""
        total = portfolio.get('total_value', 0)
        cash = portfolio.get('cash', 0)
        positions = portfolio.get('positions', {})
        
        return f"""
┌─ 组合概览 ─────────────────────────────────────────────────────────────────┐
│  总资产: ¥{total:>15,.2f}  │  现金: ¥{cash:>15,.2f}  │  持仓数: {len(positions):>3}  │
└────────────────────────────────────────────────────────────────────────────┘"""
    
    def render_signal_panel(self, signals: list[dict]) -> str:
        """渲染信号面板"""
        lines = [
            "┌─ 最新信号 ─────────────────────────────────────────────────────────────────┐",
            "│  时间        │  Agent      │  股票      │  方向  │  强度  │  目标权重   │",
            "├──────────────┼─────────────┼────────────┼────────┼────────┼─────────────┤",
        ]
        
        for sig in signals[-10:]:
            direction = "LONG" if sig.get('direction', 0) > 0 else "SHORT" if sig.get('direction', 0) < 0 else "NEUTRAL"
            lines.append(
                f"│  {sig.get('time', '--'):<12} │  {sig.get('agent_id', '--'):<11} │  "
                f"{sig.get('stock', '--'):<10} │  {direction:<6} │  "
                f"{sig.get('score', 0):>6.3f} │  {sig.get('target_weight', 0):>10.2%} │"
            )
        
        lines.append("└──────────────┴─────────────┴────────────┴────────┴────────┴─────────────┘")
        return "\n".join(lines)
    
    def render(self, state: dict[str, Any]) -> str:
        """渲染完整界面"""
        sections = [
            self.render_header(),
            "",
            self.render_portfolio_summary(state.get('portfolio', {})),
            "",
            self.render_agent_status(state.get('agents', [])),
            "",
            self.render_signal_panel(state.get('signals', [])),
        ]
        
        return "\n".join(sections)


# ============================================================
# 4. 调试界面（Debug Mode）
# ============================================================

class DebugUI:
    """调试界面
    
    面向开发者的调试界面，可视化追溯每一步
    设计风格：IDE调试器 + 系统监控面板
    """
    
    def __init__(self, tracer: ExecutionTracer):
        self.tracer = tracer
        self.theme = TerminalTheme()
        self.selected_step: int | None = None
        self.filter_module: str | None = None
    
    def render_header(self) -> str:
        """渲染调试界面头部"""
        stats = self.tracer.get_error_summary()
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DEBUG MODE  │  总步骤: {len(self.tracer.steps):>6}  │  错误: {stats['total_errors']:>3}  │  "
        f"模块: {self.filter_module or 'ALL':<15}  │  [Q]退出 [F]过滤 [E]错误 [S]保存  ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
    
    def render_execution_tree(self) -> str:
        """渲染执行树"""
        steps = self.tracer.steps[-50:]  # 最近50步
        
        lines = [
            "┌─ 执行流程（最近50步）──────────────────────────────────────────────────────┐",
            "│  #    │  模块              │  函数                  │  行号  │  状态    │ 耗时(ms) │",
            "├───────┼────────────────────┼────────────────────────┼────────┼──────────┼──────────┤",
        ]
        
        for step in steps:
            status_icon = {
                "pending": "○",
                "running": "◐",
                "success": "●",
                "error": "✗"
            }.get(step.status, "?")
            
            status_color = {
                "success": "",
                "error": "ERROR",
                "running": "ACCENT"
            }.get(step.status, "")
            
            module_short = step.module[:18]
            func_short = step.function[:22]
            
            lines.append(
                f"│  {step.step_id:<5} │  {module_short:<18} │  "
                f"{func_short:<22} │  {step.line_no:<6} │  "
                f"{status_icon} {step.status:<7} │  {step.duration_ms:>8.2f} │"
            )
        
        lines.append("└───────┴────────────────────┴────────────────────────┴────────┴──────────┴──────────┘")
        return "\n".join(lines)
    
    def render_step_detail(self, step_id: int) -> str:
        """渲染步骤详情"""
        step = self.tracer.get_step_detail(step_id)
        if step is None:
            return "步骤未找到"
        
        lines = [
            f"┌─ 步骤 #{step.step_id} 详情 ──────────────────────────────────────────────────────────┐",
            f"│  时间: {step.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}",
            f"│  位置: {step.module}.{step.function} (第{step.line_no}行)",
            f"│  状态: {step.status} | 耗时: {step.duration_ms:.2f}ms",
            "│",
            "│  【输入参数】",
        ]
        
        for key, value in step.inputs.items():
            lines.append(f"│    {key}: {self._format_value(value)}")
        
        lines.extend([
            "│",
            "│  【输出结果】",
        ])
        
        for key, value in step.outputs.items():
            lines.append(f"│    {key}: {self._format_value(value)}")
        
        if step.status == "error":
            lines.extend([
                "│",
                "│  【错误信息】",
                f"│    {step.error_message}",
                "│",
                "│  【堆栈跟踪】",
            ])
            for line in step.error_traceback.split('\n')[:10]:
                lines.append(f"│    {line}")
        
        lines.append("└──────────────────────────────────────────────────────────────────────────────┘")
        return "\n".join(lines)
    
    def render_error_panel(self) -> str:
        """渲染错误面板"""
        stats = self.tracer.get_error_summary()
        
        lines = [
            "┌─ 错误统计 ─────────────────────────────────────────────────────────────────┐",
            f"│  总错误数: {stats['total_errors']}",
            "│  错误类型分布:",
        ]
        
        for error_type, count in sorted(stats['error_types'].items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 20)
            lines.append(f"│    {error_type:<25} │ {count:>4} │ {bar}")
        
        lines.append("└──────────────────────────────────────────────────────────────────────────────┘")
        return "\n".join(lines)
    
    def render_data_preview(self, step_id: int, key: str) -> str:
        """渲染数据预览（DataFrame/Series）"""
        step = self.tracer.get_step_detail(step_id)
        if step is None:
            return "步骤未找到"
        
        data = step.outputs.get(key) or step.inputs.get(key)
        if data is None:
            return "数据未找到"
        
        if isinstance(data, dict) and data.get('type') in ['DataFrame', 'Series']:
            lines = [
                f"┌─ 数据预览: {key} ───────────────────────────────────────────────────────────┐",
                f"│  类型: {data['type']} | 形状: {data['shape']}",
                f"│  数据类型: {data.get('dtypes', 'N/A')}",
                "│",
                "│  【前3行】",
            ]
            
            head = data.get('head', {})
            for idx, row in head.items():
                lines.append(f"│    {idx}: {row}")
            
            lines.append("└──────────────────────────────────────────────────────────────────────────────┘")
            return "\n".join(lines)
        
        return f"数据类型不支持预览: {type(data)}"
    
    def _format_value(self, value: Any, max_len: int = 80) -> str:
        """格式化值显示"""
        text = str(value)
        if len(text) > max_len:
            text = text[:max_len-3] + "..."
        return text
    
    def render(self) -> str:
        """渲染完整调试界面"""
        sections = [
            self.render_header(),
            "",
            self.render_execution_tree(),
            "",
            self.render_error_panel(),
        ]
        
        if self.selected_step:
            sections.extend([
                "",
                self.render_step_detail(self.selected_step),
            ])
        
        return "\n".join(sections)


# ============================================================
# 5. 统一控制台
# ============================================================

class TradingConsole:
    """交易控制台
    
    统一管理使用界面和调试界面
    """
    
    def __init__(self):
        self.trading_ui = TradingUI()
        self.debug_ui = DebugUI(tracer)
        self.mode: str = "trading"  # trading | debug
        
        # 系统状态
        self.system_state: dict[str, Any] = {
            'portfolio': {},
            'agents': [],
            'signals': [],
            'errors': []
        }
    
    def switch_mode(self, mode: str):
        """切换模式"""
        if mode in ["trading", "debug"]:
            self.mode = mode
            logger.info(f"切换到 {mode.upper()} 模式")
    
    def update_state(self, state: dict[str, Any]):
        """更新系统状态"""
        self.system_state.update(state)
    
    def render(self) -> str:
        """渲染当前界面"""
        if self.mode == "trading":
            return self.trading_ui.render(self.system_state)
        else:
            return self.debug_ui.render()
    
    def export_debug_trace(self, filepath: str | None = None):
        """导出调试追踪"""
        if filepath is None:
            filepath = f"debug_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        tracer.export_trace(Path(filepath))
        return filepath


# ============================================================
# 6. 使用示例
# ============================================================

def demo_ui():
    """演示UI功能"""
    print("=" * 80)
    print("量化投研系统 UI 控制台演示")
    print("=" * 80)
    
    # 创建控制台
    console = TradingConsole()
    
    # 模拟系统状态
    console.update_state({
        'portfolio': {
            'total_value': 12_500_000,
            'cash': 2_000_000,
            'positions': {'000001.SZ': 1000, '000002.SZ': 2000}
        },
        'agents': [
            {'id': 'value_001', 'name': '价值型Agent', 'style': 'VALUE', 'is_active': True, 'positions': 20, 'today_pnl': 0.023},
            {'id': 'mom_001', 'name': '动量型Agent', 'style': 'MOMENTUM', 'is_active': True, 'positions': 15, 'today_pnl': -0.015},
            {'id': 'res_001', 'name': '韧性Agent', 'style': 'RESILIENT', 'is_active': True, 'positions': 18, 'today_pnl': 0.008},
        ],
        'signals': [
            {'time': '09:35:00', 'agent_id': 'value_001', 'stock': '000001.SZ', 'direction': 1, 'score': 0.85, 'target_weight': 0.05},
            {'time': '09:36:00', 'agent_id': 'mom_001', 'stock': '000002.SZ', 'direction': 1, 'score': 0.72, 'target_weight': 0.08},
            {'time': '09:37:00', 'agent_id': 'res_001', 'stock': '000003.SZ', 'direction': -1, 'score': -0.65, 'target_weight': 0.03},
        ]
    })
    
    # 显示交易界面
    print("\n【交易界面 - Trading Mode】")
    print(console.render())
    
    # 模拟一些执行步骤
    print("\n【模拟执行追踪...】")
    
    @trace_execution("factor_pipeline")
    def demo_factor_process(data: pd.DataFrame) -> pd.DataFrame:
        return data * 2
    
    @trace_execution("portfolio_optimizer")
    def demo_optimize(signals: pd.Series) -> dict:
        return {'selected': signals.nlargest(5).index.tolist()}
    
    try:
        df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        result = demo_factor_process(df)
        
        signals = pd.Series([0.1, 0.5, 0.3, 0.8, 0.2])
        selected = demo_optimize(signals)
        
        # 模拟一个错误
        @trace_execution("execution")
        def demo_error():
            raise ValueError("模拟交易执行错误: 价格数据缺失")
        
        demo_error()
    except:
        pass
    
    # 切换到调试模式
    console.switch_mode("debug")
    console.debug_ui.selected_step = 2
    
    print("\n【调试界面 - Debug Mode】")
    print(console.render())
    
    # 导出追踪
    filepath = console.export_debug_trace("demo_trace.json")
    print(f"\n追踪记录已导出: {filepath}")


if __name__ == "__main__":
    demo_ui()
