"""
蒸馏产物审计工具
===============

自动检测Agent蒸馏产物中的数据窥探风险。

审计项目：
1. Guru JSON配置中的可疑权重
2. 信念轨迹中的异常模式
3. 训练/测试期数据隔离合规性
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class DistillationAuditor:
    """蒸馏产物审计器"""
    
    # 可疑的精确权重值（可能来自数据调参）
    SUSPICIOUS_WEIGHTS = {
        0.33, 0.333, 0.3333,  # 1/3
        0.67, 0.667, 0.6667,  # 2/3
        0.25, 0.75,           # 1/4, 3/4
        0.2, 0.4, 0.6, 0.8,   # 1/5倍数
        0.125, 0.375, 0.625, 0.875,  # 1/8倍数
    }
    
    # 合理的整数值权重（人工设定）
    REASONABLE_WEIGHTS = {0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}
    
    def __init__(self):
        self.audit_results: list[dict] = []
    
    def audit_guru_json(self, json_path: Path) -> dict:
        """审计Guru JSON配置
        
        检查项：
        1. preferred_factors权重是否过于精确
        2. factor_mapping权重是否可疑
        3. distillation_config是否存在
        4. 数据来源声明是否充分
        """
        risks = []
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查1：distillation_config是否存在
        if "distillation_config" not in data:
            risks.append("缺少distillation_config字段，无法验证数据来源")
        else:
            dist_config = data["distillation_config"]
            
            # 检查1a：数据来源声明
            if not dist_config.get("data_source_declared"):
                risks.append("未声明数据来源")
            
            # 检查1b：MANUAL来源不应有train_period
            if dist_config.get("source") == "manual" and dist_config.get("train_period"):
                risks.append("MANUAL来源不应指定train_period")
            
            # 检查1c：TRAINED来源必须有train_period
            if dist_config.get("source") == "trained" and not dist_config.get("train_period"):
                risks.append("TRAINED来源必须指定train_period")
        
        # 检查2：preferred_factors权重
        preferred = data.get("preferred_factors", {})
        for factor, weight in preferred.items():
            if weight not in self.REASONABLE_WEIGHTS:
                if weight in self.SUSPICIOUS_WEIGHTS:
                    risks.append(f"因子'{factor}'权重{weight}过于精确（可能来自数据调参）")
                elif abs(weight) > 1.0:
                    risks.append(f"因子'{factor}'权重{weight}超出[0,1]范围")
        
        # 检查3：mental_models中的factor_mapping
        for model in data.get("mental_models", []):
            mapping = model.get("factor_mapping", {})
            for factor, weight in mapping.items():
                if weight not in self.REASONABLE_WEIGHTS:
                    if weight in self.SUSPICIOUS_WEIGHTS:
                        risks.append(f"心智模型'{model.get('name', 'unknown')}'的因子'{factor}'权重{weight}过于精确")
                    elif abs(weight) > 1.0:
                        risks.append(f"心智模型'{model.get('name', 'unknown')}'的因子'{factor}'权重{weight}超出[-1,1]范围")
        
        # 评估风险等级
        risk_level = self._assess_risk_level(risks)
        
        result = {
            "file": str(json_path),
            "guru_name": data.get("name", "unknown"),
            "risk_level": risk_level,
            "risks": risks,
            "has_distillation_config": "distillation_config" in data,
            "source": data.get("distillation_config", {}).get("source", "unknown"),
        }
        
        self.audit_results.append(result)
        return result
    
    def audit_belief_trajectory(self, trajectory: list[tuple[datetime, float]]) -> dict:
        """审计信念轨迹
        
        检查项：
        1. 轨迹长度是否合理
        2. 变化速度是否异常
        3. 是否存在过度拟合迹象
        """
        if len(trajectory) < 2:
            return {"risk_level": "low", "reason": "轨迹太短，无法评估"}
        
        risks = []
        values = [v for _, v in trajectory]
        
        # 检查1：变化幅度
        total_change = abs(values[-1] - values[0])
        if total_change > 0.8:
            risks.append(f"信念变化幅度过大({total_change:.2f})，可能存在过度反应")
        
        # 检查2：变化速度
        if len(values) >= 10:
            recent_values = values[-10:]
            std = np.std(recent_values)
            if std > 0.3:
                risks.append(f"近期信念波动过大(std={std:.3f})，可能不稳定")
        
        # 检查3：单调性（过度拟合迹象）
        if len(values) >= 20:
            # 检查是否存在长期单调趋势
            increasing = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
            decreasing = len(values) - 1 - increasing
            
            if increasing / (len(values) - 1) > 0.8:
                risks.append("信念长期单调上升，可能过度拟合")
            elif decreasing / (len(values) - 1) > 0.8:
                risks.append("信念长期单调下降，可能过度拟合")
        
        risk_level = self._assess_risk_level(risks)
        
        return {
            "risk_level": risk_level,
            "risks": risks,
            "trajectory_length": len(trajectory),
            "total_change": total_change,
        }
    
    def audit_all_gurus(self, gurus_dir: Path = Path("gurus")) -> list[dict]:
        """审计所有Guru配置"""
        results = []
        
        if not gurus_dir.exists():
            logger.warning(f"Guru目录不存在: {gurus_dir}")
            return results
        
        for json_file in gurus_dir.glob("*.json"):
            try:
                result = self.audit_guru_json(json_file)
                results.append(result)
                
                # 打印审计结果
                print(f"\n{'='*50}")
                print(f"审计: {result['guru_name']} ({json_file.name})")
                print(f"风险等级: {result['risk_level'].upper()}")
                if result['risks']:
                    print("发现的问题:")
                    for risk in result['risks']:
                        print(f"  ⚠️  {risk}")
                else:
                    print("✅ 未发现明显风险")
                    
            except Exception as e:
                logger.error(f"审计 {json_file} 失败: {e}")
                results.append({
                    "file": str(json_file),
                    "risk_level": "error",
                    "risks": [f"审计失败: {e}"],
                })
        
        return results
    
    def generate_report(self, output_path: Path | None = None) -> str:
        """生成审计报告"""
        lines = [
            "# Agent蒸馏产物审计报告",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"审计项目数: {len(self.audit_results)}",
            "",
            "## 摘要",
        ]
        
        # 统计风险等级
        risk_counts = {"high": 0, "medium": 0, "low": 0, "error": 0}
        for result in self.audit_results:
            risk_counts[result.get("risk_level", "unknown")] += 1
        
        lines.extend([
            f"- 高风险: {risk_counts['high']} 项",
            f"- 中风险: {risk_counts['medium']} 项",
            f"- 低风险: {risk_counts['low']} 项",
            f"- 错误: {risk_counts['error']} 项",
            "",
            "## 详细结果",
        ])
        
        for result in self.audit_results:
            lines.extend([
                f"### {result['guru_name']}",
                f"- 文件: {result['file']}",
                f"- 风险等级: {result['risk_level'].upper()}",
                f"- 数据来源: {result.get('source', 'unknown')}",
            ])
            
            if result['risks']:
                lines.append("- 问题列表:")
                for risk in result['risks']:
                    lines.append(f"  - ⚠️ {risk}")
            else:
                lines.append("- ✅ 无风险")
            
            lines.append("")
        
        report = "\n".join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"审计报告已保存: {output_path}")
        
        return report
    
    def _assess_risk_level(self, risks: list[str]) -> str:
        """评估风险等级"""
        if not risks:
            return "low"
        
        # 根据问题数量和严重性评估
        high_risk_keywords = ["缺少", "必须", "超出范围", "审计失败"]
        medium_risk_keywords = ["过于精确", "可能", "不应"]
        
        high_count = sum(1 for r in risks if any(k in r for k in high_risk_keywords))
        medium_count = sum(1 for r in risks if any(k in r for k in medium_risk_keywords))
        
        if high_count > 0 or len(risks) >= 3:
            return "high"
        elif medium_count > 0 or len(risks) >= 1:
            return "medium"
        else:
            return "low"


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent蒸馏产物审计工具")
    parser.add_argument("--gurus-dir", type=Path, default=Path("gurus"),
                       help="Guru配置目录")
    parser.add_argument("--output", type=Path, default=None,
                       help="审计报告输出路径")
    
    args = parser.parse_args()
    
    auditor = DistillationAuditor()
    results = auditor.audit_all_gurus(args.gurus_dir)
    
    if args.output:
        auditor.generate_report(args.output)
    else:
        print("\n" + "="*50)
        print(auditor.generate_report())


if __name__ == "__main__":
    main()
