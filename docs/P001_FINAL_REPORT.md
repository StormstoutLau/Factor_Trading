# P-001 最终闭环报告（TD-3 Stage 3：移除 core/engine.py）

> **文档编号**: P001_FINAL_REPORT
> **性质**: 闭环总结（非规范四件套，为 P-001 交付后的汇总存档）
> **日期**: 2026-11-09
> **状态**: **closed**（Step 1-10 全通过 + 提交/推送/远端 CI 全绿 + RULE-5 异构复审 pass）
> **档位**: T1（改动路径含 `core/`、`tests/`、`examples/`，Layer-1）；规范 `F:\Spec_Workflow\SPEC_PROCESS.md` **v1.7.2**
> **会话**: `factorv3-p001-td3-stage3-20261109`（Spec_Runner 门禁 seq 1-9，replay 9 rows OK）
> **四件套**: [RESEARCH_td3_stage3.md](RESEARCH_td3_stage3.md) → [DESIGN_td3_stage3.md](DESIGN_td3_stage3.md) → [IMPL_td3_stage3.md](IMPL_td3_stage3.md) → [CHECKLIST_td3_stage3.md](CHECKLIST_td3_stage3.md)
> **台账**: [PROGRESS.md](PROGRESS.md) §1.4 P-001 = done

---

## 1. 任务与结论一句话

**任务**：执行 TD-3 的 Stage 3（Remove）——删除已弃用的 Engine V1（`core/engine.py`，747 行），迁移全部 10 处活跃调用方至 V2 路径，同步活文档。

**结论**：已完成并闭环。CHECKLIST **43/43 达成，P1/P2 = 0**；净删除 **1245 行**；本地全量 `507 passed`；远端 CI 连续 3 个 run 三版本（3.10/3.11/3.12）全绿；RULE-5 异构基座第二会话复审 pass。

---

## 2. 提交链与远端 CI（证据主干）

| 提交 | 内容 | 触发 CI run | CI 结论 |
|------|------|-------------|---------|
| `ccd0c98` | 主提交：移除 Engine V1 并迁移全部调用方 | — | — |
| `35427f0` | 审计证据绑定至 `ccd0c98`（E3 静态读码行号可回溯） | `42598775895` | ✅ 三版本全绿（`500 passed, 1 skipped` ×3） |
| `c62eada` | CI 结果回填 CHECKLIST B8 / §8 | `42599168755` | ✅ 三版本全绿 |
| `53f3024` | RULE-5 异构复审记录 + 3 项 P3 修正（F-5-1/2/3） | `42600658236` | ✅ 三版本全绿（3.12 job 实测 `500 passed, 1 skipped in 10.80s`） |

推送链：`696bd7b..53f3024` → `origin/master`。历史记录（`DEVLOG.md`、`DIFF_REPORT_2026-10-23.md`、`docs/dev-log/`、`docs/archive/`）**零改动**。

---

## 3. 交付内容

### 3.1 删除（零 shim、零空壳、零 redirect）

| 对象 | 体量 | 备注 |
|------|------|------|
| `core/engine.py` | 747 行（非空行 724）；repo blob 29163 B（LF）/ 29910 B（CRLF 工作区，F-9-3 口径澄清） | 三层弃用标记（module docstring / `.. deprecated::` / 运行时 `DeprecationWarning`）曾长期失效——PEP 594/S2 机制解释见 RESEARCH §2.1 |
| `tests/test_visual_trace.py` | 255 行 | 0 收集诊断脚本（`collected 0 items`） |
| `tests/test_visual_trace_v2.py` | 192 行 | 同上 |

### 3.2 迁移（生产逻辑零算法变更）

| 类别 | 内容 |
|------|------|
| examples（6 文件） | 5 个 config-driven → `from core.factory import create_default_engine`（5 文件 import / 6 处调用）；1 个手动装配（`full_backtest_2020_2026_simple.py`）→ `BacktestEngineV2` 直装配 + D7 的 5 行 `core.*` 导入替换，11 项属性直装配保留 |
| tests | `test_compatibility.py` L48 → `from core.engine_v2 import BacktestEngineV2`（6 项不变）；`test_rebalance_exits.py` 清理 V1 helper / g2 / g3（14 → 12 项） |
| 注释/docstring | `core/__init__.py` L6/L9、`engine_plugins.py` L14/L383、`walk_forward_engine.py` L45 共 5 行/3 文件；`agents/multi_strategy_engine.py:64` 历史表述按契约保留 |

### 3.3 活文档同步

`ARCHITECTURE.md`（3 处）、`CODE_WIKI.md`（25 编辑点，V1 章节改为「已移除」注记）、`DECISIONS.md` L30、`README.md`（507/48 共 4 行 + L359 目录树残行）、`CHANGELOG.md` `[Unreleased] > Removed`、`PROGRESS.md`、`RESEARCH_tech_debt_cleanup.md` TD-3 追加 Stage 3 注记（历史结论未改）。

---

## 4. 验证结果（关键读数）

| 维度 | 基线 @ `696bd7b` | 交付后 | 证据 |
|------|------------------|--------|------|
| 全量测试 | 509 passed | **507 passed, 82 warnings**（门禁 20.32s / 复审重跑 20.90s，≤45s 限值） | CHECKLIST B1 |
| 测试文件数 | 50 | **48** | B3 |
| 两文件收集 | 20（14+6） | **18（12+6）** | B2 |
| V1 import 命中 | 10 活跃 | **0**（三类模式全仓 `*.py`） | A2 |
| `import core.engine` | 有效 | **`ModuleNotFoundError`** exit 1 | E3 |
| golden 测试 | g1-g5 | **g1/g4/g5 `3 passed`**（g2/g3 随 V1 删除，属 DESIGN D3 裁决） | B6 |
| black | 75 files（fail） | **72**（仍 fail，预期基线） | §7 门禁链 seq8 |
| mypy | 168 errors（fail） | **119 errors in 19 files**（仍 fail，预期基线） | §7 门禁链 seq9 |
| 端到端烟测 | — | `demo.py` **exit 0**（5.4s，1140 笔交易）；`cli.py --help` exit 0 | A10/C2 |
| 保护路径 | — | 12 项路径 `git diff --stat` 全空（engine_v2/factory/cli/pyproject 等） | A9/E1/E2 |
| 行数核算 | — | **+25 / −1270 = 净删除 1245 行** | C3 |

门禁链（Spec_Runner，session seq）：probe pass(6) → unit-tests pass(7) → black fail(72)(8) → mypy fail(119)(9)；`spec_runner_adapter.py replay --session` = 9 rows OK。

---

## 5. 评审与审计闭环

| 关卡 | 结果 | 记录位置 |
|------|------|----------|
| Step 2 RESEARCH Review | 通过（0 阻断；5 项 P3 处置，含 U-003 清单修正） | RESEARCH §6.1 |
| Step 4 DESIGN Review | 通过（含 D1-D7） | DESIGN |
| Step 6 IMPL Review | 通过（10 项复核 6 命中 + 6 项 P3 回写，0 阻断） | IMPL §9 |
| Step 8 文档机械核对 | 14 条相对链接 0 broken | CHECKLIST D7 |
| Step 10 ADD 审计（四阶段） | 通过；F-9 系列 5 项 + F-A1 全部登记处置；Iron Law「测试通过 ≠ 设计落地」以 12 项保护路径零 diff + 行号回溯证伪风险 | CHECKLIST §11 |
| RULE-5 异构第二会话复审 | **pass**：复审者 GLM-5.3-Flash（与前序实现会话不同模型家族）；独立重跑不变式与全量测试、按 `ccd0c98` 回溯行号（simple L14/L87/L104、compat L48、`__init__:11`）、盲区独立重扫确认无漏报、静默降级抽查（E3 绑 hash、推演升级实测）无降级；发现 3 项 P3（F-5-1/2/3）已修正并随 `53f3024` 入仓 | CHECKLIST §11.3 |

发现项总计：F-9-1~5、F-A1、F-5-1~3 共 **9 项，全部 P3**，均已登记并处置/澄清；无 P1/P2。

---

## 6. 遗留与能力边界（如实声明）

| 项 | 状态 | 说明 |
|----|------|------|
| examples 运行时覆盖 | `[未在 CI 执行]` | 除 `demo.py` 外的 5 个脚本依赖 `E:/Ashare_data` 本地数据，仅做 `py_compile`（exit 0）；已在 CHECKLIST E4 如实标注，未写成 ✅ |
| black / mypy 门禁 | fail（预期） | 为存量基线（72 / 119），非本批引入；本批使其净改善（75→72、168→119） |
| demo 数值变化 | 预期行为 | V2 真实执行 FactorPipeline，无 golden 断言，CHANGELOG 已注明 |
| CI annotations | 非阻断 | Node.js 20 deprecation / ubuntu-latest 迁移提示，与本批无关 |

---

## 7. 收尾结论

P-001 全链闭环：**十步流程（Step 1-10）→ 提交（`ccd0c98`）→ 证据绑定（`35427f0`）→ CI 复核回填（`c62eada`）→ RULE-5 异构复审 + P3 修正（`53f3024`）→ 远端 CI 三连绿**。

- 验收：43/43 ✅，P1/P2 = 0，9 项发现全部 P3 且已闭环
- 代码面：净删除 1245 行，零算法变更，保护路径零 diff
- 证据面：E1 命令可重放、E3 绑 hash 可回溯、E4 边界如实声明、门禁链 9 rows 可 replay
- TD-3 三阶段（Deprecate → cli.py 替换 → Remove）至此**全部完成**
