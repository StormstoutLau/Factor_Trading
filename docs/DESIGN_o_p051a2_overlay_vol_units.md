# DESIGN：O-P051a-2 overlay vol 腿单位口径修复

> **批次**: O-P051a-2（P-048/P-051a 遗留 latent 缺陷修复）· **档位 T2 小流程**（Layer-1 可逆小补，先例 = P-016）
> **裁剪理由**: 不写 RESEARCH/IMPL。缺陷机制已由 [RESEARCH_p051a §3.3](RESEARCH_p051a_sizing_wiring.md) 定位并经 P-051a Step 2 复审 §15.1 #14 独立复算成立；修复方案有**同文件同构先例**（引擎 sizing 路径 `cov × TRADING_DAYS`，G5/I4）；改动 1 行 + 1 个既有用例期望值 → 四文档不成比例。本文件即 DESIGN 与实施规格。
> **上游**: [PROGRESS §1.4 O-P051a-2](../docs/PROGRESS.md) · `core/engine_v2.py` L1474-1475（sizing 同构） · [DESIGN_p051a](DESIGN_p051a_sizing_wiring.md) I12
> **作者**: GLM-5.3-Flash（Step 9 实施与终审须 reviewer ≠ 作者）

---

## 1. 缺陷（E1 可重放）

`apply_overlay` 的 vol 腿公式为 `scale = min(target_vol / σ_p, 1.0)`（`vol_target_scale`，[sizing.py L207-L220](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L207-L220)），要求 **Σ 与 `target_vol` 同频**。而引擎 overlay 分支传的是**日频 Σ**：

```python
# core/engine_v2.py（overlay 分支，修复前）
cov = cov_matrix.to_numpy()          # 日频（estimate_cov 输出）
cov_codes = [str(code) for code in cov_matrix.columns]
```

`RiskOverlayConfig.target_vol` 为**年化**（默认语义同 `SizingConfig.target_vol=0.15`）。故 `σ_p ≈ 0.02`（日频）时 `0.15/0.02 = 7.5 → clip 1.0`，vol 腿恒等 1（**静默失效**）。

**E1 探针**（`%TEMP%\o_p051a2_probe.py`，2026-11-23）：

| 输入 | scale | reason |
|---|---|---|
| 日频 Σ=[[0.0004]] + target=0.15（现状） | **1.000000** | `''` |
| Σ×252 + target=0.15（修复） | **0.472456** | `''` |
| 解析式 `0.15/(0.02·√252)` | **0.472456** | 逐位一致 |

默认 `target_vol=None` → 零触发，故 P-048/P-051a 全部门禁绿而缺陷未被发现（latent）。

## 2. 决策

| ID | 决策 | 被拒替代 | 依据 |
|---|---|---|---|
| **D1** | 引擎 overlay 分支在传入 `apply_overlay` 前**年化 Σ**：`cov = cov_matrix.to_numpy() * TRADING_DAYS` | ① 把 `target_vol` 降频（÷√252）——分散在两条腿，且 sizing 侧已按年化；② 改 `vol_target_scale` 加 `annualize` 参数——污染纯函数契约，P-047 用例与 sizing 调用全受影响 | sizing 路径 **同文件同构先例**（L1474-1475 注释「G5 / I4：Σ 与 target_vol 同口径（日频 → 年化）」） |
| **D2** | **函数层契约为准**：`apply_overlay(..., cov=)` 的 Σ 由调用方保证与 `target_vol` 同频；`vol_target_scale` / `apply_overlay` **零改动** | 在函数内猜频度（无法判定） | `tests/test_p048_risk_overlay.py` 的 I5（σ=0.1→0.5、σ=0.2→0.25）为**函数契约**测试，必须保持 |
| **D3** | 既有引擎用例 `test_enabled_scales_weights` 期望值改为**年化口径**；并加「非 clip」断言 | 保留日频期望值 → 修复后必红 | 行为变更必须显式登记（本表 + PROGRESS §3.110） |
| **D4** | `RiskOverlayConfig.target_vol` 注释补「年化」 | 不补 → 下一位读者重犯 | `SizingConfig.target_vol` 已是「年化目标波动」 |
| **D5** | 默认 `target_vol=None` 路径**零影响** → golden 22 零重录 | — | overlay vol 腿仅在显式配置时进入 |

## 3. 改动面（精确）

| 文件 | 动作 | 内容 |
|---|---|---|
| `core/engine_v2.py` | 改 1 行 + 1 注释 | overlay 分支 `cov = cov_matrix.to_numpy() * TRADING_DAYS`，注释「O-P051a-2：Σ 与 target_vol 同口径（日频→年化，与 sizing 同构）」 |
| `core/risk_overlay.py` | 改 1 注释 | L52 `target_vol: Optional[float] = None  # 年化目标波动；None = 不做 vol 缩放` |
| `tests/test_p048_overlay_engine.py` | 改期望值 + 加 1 断言 | `sigma_annual = sigma_daily * sqrt(TRADING_DAYS)`；`expected = min(1.0, 0.01/sigma_annual)`；加 `assert enabled["last_target_weight"] < 0.1`（证明非 clip） |

**零改动面**：`core/sizing.py` / `core/portfolio.py` / `core/config.py` / `tests/golden/` / `pyproject.toml` / `uv.lock`。

## 4. 不变式 I1-I5

| ID | 不变式 | 验证 |
|---|---|---|
| **I1** | 显式 `target_vol` 时 vol 腿**真实生效**：`scale_vol = min(target/σ_annual, 1)` 且通常 `<1` | A1/A2 |
| **I2** | 函数层契约不变：`apply_overlay` 的 I5 用例（σ=0.1→0.5、σ=0.2→0.25）逐值保持 | B3 |
| **I3** | 默认 `target_vol=None` → `scale_vol≡1`、权重逐值不变 | B1 |
| **I4** | golden 22 零重录（overlay golden 均未配置 `target_vol`） | B2 |
| **I5** | sizing 与 overlay 两腿同口径（均年化 Σ + 年化 target） | A4 |

## 5. 验收映射（CHECKLIST 见 [CHECKLIST_o_p051a2](CHECKLIST_o_p051a2_overlay_vol_units.md)）

- 机制：A1（引擎级 scale<1）/ A2（解析式逐位）/ A3（函数层零改动）/ A4（两腿同构）
- 回归：B1（None 零影响）/ B2（golden 22）/ B3（I5 函数契约）/ B4（其它 target_vol 用例）
- 门禁：C1-C7（全量 / `-k p048` / golden / mypy / black / AST+lint / lock）

## 6. 门禁与预期（基线 `79cb661`）

| 指标 | 基线 | 目标 |
|---|---|---|
| pytest collect | 1503（1502+1） | **1503（1502+1）**（仅改期望值，不加例） |
| `-k p048` | 23 | **23** |
| `-k golden` | 22 | **22（零重录）** |
| mypy | 160·0 | **160·0** |
| black | 325 | **325** |
| AST / lint / lock | 22·30 / 3 kept / 0 | 不变 |

## 7. 回退点

`git revert` 单提交即可（3 文件、无数据迁移、无锁变更、无 golden 重录）。行为回退后果：显式 `target_vol` 回到「静默失效」——须在 CHANGELOG 或台账注明。

## 8. 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 其它用例隐含日频期望 | 低 | 红 | 已 grep 全仓 `target_vol=` 7 处：仅 `test_enabled_scales_weights` 断言数值；`test_p046_engine` 只数 `estimate_cov` 次数；`test_p051a` 只查 warning |
| 组合含期货致 Σ/权重维度不匹配 | 低 | 异常 | 既有 `vol_target_scale` 已按 `codes` 取向量；本次只乘常数，不改变维度语义 |
| `TRADING_DAYS` 硬编码 252 与用户年化口径不符 | 低 | 轻微 | 与 sizing 路径同源常量（`core/volatility.TRADING_DAYS`），一致性优先 |
