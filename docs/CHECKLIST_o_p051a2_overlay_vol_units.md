# CHECKLIST：O-P051a-2 overlay vol 腿单位口径修复

> **批次**: O-P051a-2 · **档位 T2**（先例 P-016：DESIGN + CHECKLIST 两件套；裁剪理由见 [DESIGN §头部](DESIGN_o_p051a2_overlay_vol_units.md)）
> **上游**: [DESIGN_o_p051a2](DESIGN_o_p051a2_overlay_vol_units.md)（D1-D5 / I1-I5 / §3 改动面 / §6 门禁）
> **基线**: `79cb661`（P-046c 关闭）；collect **1503**（1502 passed + 1 skipped）/ `-k p048` **23** / golden **22** / mypy **160·0** / black **325**
> **实测列规则（RULE-1）**: 仅 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止预填**

---

## 1. A 组：机制验证（4 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | 引擎级：显式 `target_vol=0.01` 时 `last_target_weight < 1.0` 且 `< 0.1`（证明非 clip） | D1 落码 | `test_enabled_scales_weights` | ✅ `< 0.1` 断言通过（含于 `-k p048` 23 passed）；修复前 = 1.0（E1 探针），现显著小于 → 非 clip |
| A2 | 数值：`last_target_weight == min(1, target_vol/(σ_daily·√252))`（rel 1e-6） | D1/D3 | 同用例解析式断言 | ✅ `pytest.approx(min(1.0, 0.01/(σ_daily·√252)), rel=1e-6)` 通过 |
| A3 | 函数层零改动：`vol_target_scale` / `apply_overlay` 签名与实现不变（`git diff` 仅注释） | D2 | `git diff core/risk_overlay.py` | ✅ diff 仅 L52 注释 1 行；`core/sizing.py` `git status` 空 |
| A4 | 两腿同构：sizing（L1474-1475）与 overlay 均 `Σ × TRADING_DAYS` | D1 | 读码 | ✅ engine_v2 L1475（sizing）与 L1498（overlay）均 `to_numpy() * TRADING_DAYS` |

## 2. B 组：回归（4 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | I3：`target_vol=None` → `scale_vol≡1`、权重逐值不变（I4 纯函数用例保持） | D5 | `test_p048_risk_overlay.py::test_i4_identity` | ✅ `-k p048` 23 passed（含 `test_i4_identity`）；`None` 路径逐值不变 |
| B2 | golden **22 零重录**；`git status tests/golden/` 空 | D5 | `-k golden` + git | ✅ `-k golden` 22 passed；`git status tests/golden/` 空 |
| B3 | I2：函数层 I5 用例（σ=0.1→0.5、σ=0.2→0.25、scale_floor）逐值不变 | D2 | `test_i5_monotone` | ✅ `test_i5_monotone` 通过（函数层零改动，σ=0.1→0.5、σ=0.2→0.25） |
| B4 | 其它 `target_vol` 用例不受影响（`test_p046_engine` 只数 `estimate_cov`；`test_p051a` 只查 warning） | D3 | `-k p046` / `-k p051` | ✅ `-k p046` 117 passed；`-k p051` 120 passed |

## 3. C 组：门禁（7 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | 全量 pytest **1502 passed + 1 skipped**（collect 1503） | A/B 落码 | 末行 | ✅ **1502 passed, 1 skipped**（132.76s；collect 1503） |
| C2 | `-k p048` **23 passed** | A1 落码 | 末行 | ✅ **23 passed** |
| C3 | `-k golden` **22 passed** 且目录无变更 | 全量 | 命令 + git | ✅ **22 passed**；`git status tests/golden/` 空 |
| C4 | mypy CI 同款 **160 · 0** | 落码 | 末行 | ✅ **Success: no issues found in 160 source files** |
| C5 | `black --check .` **325 unchanged** | 落码 | 末行 | ✅ **325 files would be left unchanged**（本会话复核） |
| C6 | AST `except Exception` **22 · 30**；`lint-imports` **3 kept** | 落码 | 命令 | ✅ AST **22 · core 30**；`lint-imports` **3 contracts kept, 0 broken** |
| C7 | `uv lock --check` exit **0** | 落码 | 命令 | ✅ exit **0**（Resolved 139 packages） |

---

## 4. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **15**（A 4 + B 4 + C 7，逐表行数机械计数） |
| 实测列初始 | 15 × `[待 Step 9]`；`✅` 0（预填=违规） |
| 预期终态 | 15 × ✅ |
| 终态实测 | **15 × ✅**（`[待 Step 9]` 清零） |

## 5. 范围守卫（N1-N4，不计入验收项）

| # | 不做项 | 机械检查 |
|---|---|---|
| N1 | 改 `core/sizing.py`（`vol_target_scale` 契约） | `git status --short core/sizing.py` 空 |
| N2 | 改 `core/config.py` / `config_v2.py` | 两者 `git status` 空 |
| N3 | golden 重录 | `git status tests/golden/` 空 |
| N4 | 新增测试文件 / 新增用例数 | `tests/*.py` 仍 **161**；collect 仍 **1503** |

## 6. 状态链

- **2026-11-23**：O-P051a-2 立项（T2，DESIGN + CHECKLIST）；E1 探针确认失效（scale=1.000000）与修复值（0.472456）；零代码变更。
- **2026-11-23 Step 9**：3 文件落码（engine_v2 L1498 年化 Σ + risk_overlay L52 注释 + `test_enabled_scales_weights` 年化期望 / 非 clip 断言）；门禁 C1-C7 全命中；`core/sizing.py` / `core/config.py` / `config_v2.py` / golden 零 diff（N1-N4 全绿）；实测列 15/15 ✅。
- **下一步**：PROGRESS §3.110 落账 + 提交授权（当前未提交）。
