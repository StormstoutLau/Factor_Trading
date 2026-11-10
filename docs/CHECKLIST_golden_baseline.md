# P-013 Golden 基线固化（L4 判据）· 验收清单（Step 7 + Step 9 回填）

> **文档编号**: CHECKLIST_golden_baseline
> **阶段**: Phase 3 - 验收（T1 完整管线）
> **日期**: 2026-11-10
> **状态**: **Step 7-10 全通过；36/36 实测回填**（Step 9 实测 **626 passed** / black **171** / mypy **0（36 files）** / 盲区 **4 errors 2 files** 不劣化 / 70 测试文件 / 6 份基线逐字节可重现）
> **上游**: [DESIGN_golden_baseline.md](DESIGN_golden_baseline.md)（D1-D10 / I1-I6）· [IMPL_golden_baseline.md](IMPL_golden_baseline.md)（T-0~T-7 / V1-V12 / R1-R9 / §8 Step 9 记录）
> **填写规则**: 实测列只写 Step 9 实施后的实测证据（RULE-1，禁止预填）
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；测试命令加 `MPLBACKEND=Agg`
> **门禁**: session `factorv3-p013-golden-20261110`
> **基线时点**: `6f583fc`；RED 读数 **609 passed / black 167 / mypy 0（36 files）/ 盲区 4 errors 2 files / 68 测试文件**
> **目标末态（实测）**: **626 passed**（609 + 9 夹具 + 8 golden；原预测 623 少计参数化 3 项，F-S9-G7）/ black **171** / mypy 0 / 盲区不劣化 / **70** 测试文件 / `tests/golden/*.json` × 6

---

## 1. A 夹具能力（B1：T-1/T-2）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `write_price_fixture` 接受 `open_prices`，写出独立 `open.pkl`，`close.pkl` 不受影响 | `pytest tests/test_synth_fixture.py -k independent_open -q` | D5.1 / T-1 | ✅ `1 passed`；`open` == 覆盖矩阵，`close` == 原矩阵 |
| A2 | 接受 `high_prices` / `low_prices`，分别独立写出 | 同上 `-k high_and_low` | D5.1 / T-1 | ✅ `2 passed`（参数化 high/low） |
| A3 | `suspend` / `st` 接受 2D 矩阵并逐值写入 | `pytest ... -k matrix_flags -q` | D5.1 / T-1 | ✅ `2 passed`（参数化 suspend/st），dtype 为整型 |
| A4 | 不传新参数时行为与改造前**完全一致**（open/high/low == close） | `pytest ... -k backward_compatible -q` | D5.1 / 兼容 | ✅ `2 passed`（OHLC 复用 + 标量 0） |
| A5 | `write_universe` 写出三文件（列名精确） | `pytest ... -k write_universe -q` | D5.2 / T-2 | ✅ `2 passed`；`list_date.csv`=[stock,list_date]、`delist.csv`=[stock,delist_date,delist_return]、`manifest.json` schema 1.0 / rows=2 |
| A6 | `load_universe_snapshot` 读回上述夹具时 `status == "corrected"` | 同上 | D5.2 / `universe_data.py:36` | ✅ `snap.status == "corrected"` |

## 2. B 基线 schema 与容差（D2/D3）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 每份基线含 `schema_version` 与 `git_commit` | `test_baseline_schema_valid` | D2 / I6 | ✅ 6/6 文件 `schema_version=="1.0"`、`git_commit` 非空 |
| B2 | `metrics` 六字段齐备 | 同上 | D2 / P4 | ✅ 6/6 含 total/annual/annual_volatility/sharpe/mdd/final_value |
| B3 | `nav` 五字段 + `trades` 三字段齐备 | 同上 | D2 / P5 | ✅ `nav`=length/first/last/min/max；`trades`=count/total_amount/total_cost |
| B4 | `tolerance.rtol <= 1e-9`（不得放宽） | 同上 | D3 / I3 | ✅ `rtol=1e-9`、`money_atol=1e-6`，断言守护 |
| B5 | 基线内不含 `NaN`/`Infinity` | `json.loads` + `math.isfinite` | D2 / I1 | ✅ 逐字段有限性断言通过；录制端 `_has_non_finite` 双保险 |

## 3. C 六条 case（D4）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | **G1** V2 baseline：常量价零费用 5×2 | `pytest tests/test_golden_baseline.py -k G1 -q` | D4 | ✅ `1 passed`；`total_return=0`、`final=1e7`、trades=4（首建 2 + 末日强平 2）、`nav.length=6` |
| C2 | **G2** V2 cost：含佣金/印花税/滑点/整手 | 同上 `-k G2` | D4 | ✅ `1 passed`；`total_return=-0.00560`、trades=57、`total_cost=36526.96>0` |
| C3 | **G3** V2 mask：涨停**确实触发**（非静默空过） | 同上 `-k G3` + V6 人工核对 | D4 / §12 | ✅ 涨停日 `2024-01-16` 对 `000001` 买入 **0 笔**、`limit_up_mask=False`；`total_return=+0.02865`（真实一次涨停） |
| C4 | **G4** V3 baseline：`nav.first/last/min/max` 与 G1 相等（`length` 差 1，见 F-S9-G4） | 同上 `-k G4` + 跨文件比对 | D4 | ✅ 四项均为 `1e7`；`length` 5 vs 6（V2 末日双快照，既有行为 F-S9-3） |
| C5 | **G5** V3 cost：`cost_rate=0.001` 生效 | 同上 `-k G5` | D4 | ✅ `1 passed`；`total_return=-0.00221`、`nav.length=20`（V3 无末日强平，故比 V2 少 1） |
| C6 | **G6** V2 delisting：退市后该标的从可交易集合移除 | 同上 `-k G6` + V7 人工核对 | D4 / P-012 B5 | ✅ 退市日 `2024-01-22` 起**无 BUY**；仅 1 笔 `SELL qty=162300` 清仓，此后持仓恒 0（F-S9-G6 观察项） |

## 4. D 录制脚本（D6）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 工作区脏时拒绝录制，退出码 1 | 手工实测 | D6 / U-G2=A | ✅ `[拒绝] 工作区不干净`，`exit=1` |
| D2 | `--force` 可覆盖，JSON 记 `dirty=true` | 同上 | D6 | ✅ 全量录制时 `dirty=True` 写入 6 份 JSON |
| D3 | `CI=true` 环境拒绝录制 | 设环境变量实测 | D6 | ✅ `[拒绝] 检测到 CI 环境`，`exit=1` |
| D4 | 每个 case 打印 `metrics`/`nav`/`trades` 摘要 | 录制输出 | D6 | ✅ 每 case 三行摘要（见 IMPL §8.1 抄录） |

## 5. E 测试与不变式（D7 / I1-I6）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | I1：基线全部数值有限 | `test_baseline_schema_valid` | I1 | ✅ 全字段 `math.isfinite` |
| E2 | I2：连续两次录制 SHA256 一致（可重现） | E1 两次录制比对 | I2 | ✅ `reproducible=True files=6`（逐字节） |
| E3 | I3：容差上限受断言保护 | `test_baseline_schema_valid` | I3 | ✅ `rtol<=1e-9`、`money_atol<=1e-6` |
| E4 | I4：测试只读——跑完基线 SHA256 不变 | E1 前后比对 | I4 | ✅ `readonly=True` |
| E5 | I5：`case_id` 集合恰为 `{G1..G6}` | `test_all_cases_present` | I5 | ✅ `1 passed` |
| E6 | 失败信息可定位（`[Gx]` + 字段 + expected/got/rel_err） | 临时偏移实测后还原 | D7 / U-G3=A | ✅ `[G3] metrics.sharpe_ratio: expected=3.1 got=3.0090121123042275 rel_err=2.935e-02 (rtol=1e-09, atol=1e-12)` |
| E7 | case 构造器单一来源，无第二份逻辑 | `Grep 'def build_case'` | F-I-G1 | ✅ 定义 **1 处**（`tests/_golden_cases.py`），脚本与测试均 import |

## 6. F 文档与声明（D1/D10）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 四文档齐备且双向引用（0 broken） | 链接检查 | T1 流程 | ✅ RESEARCH 3 / DESIGN 1 / IMPL 1 / CHECKLIST 2，**7 链接 0 broken** |
| F2 | 明确声明 golden **不证明正确性** | 文档 + 代码 docstring | A20 | ✅ 8 处声明（RESEARCH 约束 5 / DESIGN §1 / 两测试 docstring / `_golden_cases` docstring 等） |
| F3 | 基线变更纪律写入文档 | DESIGN §11 读回 | D10 | ✅ 「变更方须先说明基线 diff 合理性，再更新基线」 |

## 7. G 门禁与 CI

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| G1 | 全量 `626 passed`（0 fail / 0 新 skip） | `pytest tests -q` | V1 | ✅ `626 passed, 142 warnings in 60.67s` |
| G2 | black 全绿 | `black --check .` | V2 | ✅ `171 files would be left unchanged`（167 + 4 新增） |
| G3 | mypy `Success`（36 files，`core/` 零改动） | `mypy --explicit-package-bases core` | V2/V12 | ✅ `Success: no issues found in 36 source files`；`git diff core/ filter/` 空 |
| G4 | 盲区 `4 errors 2 files` 不劣化 | `mypy ... --check-untyped-defs` | V2 | ✅ `Found 4 errors in 2 files (checked 36 source files)` |
| G5 | CI 三版本全绿（`py_func` 路径容差有效） | `gh run 42786173151` | V11 | ✅ 3.10/3.11/3.12 三 job `success`，各自 `619 passed, 1 skipped`（= 本地 626 − 7 项 numba `importorskip`）→ 6 条 golden 在无 numba 的 `py_func` 路径上全部通过，容差 `rtol=1e-9 / money_atol=1e-6` 有效。**观察（既有，非本批引入）**：CI 的 `Type check (mypy)` 步骤为 `|| true`（不阻断）且报 `core/metrics.py: error: Source file found twice under different module names`（CI 工作目录 + 已安装包的 `Factor_Trading` 命名冲突），本地 `mypy --explicit-package-bases core` 为 `Success: 36 source files` |

## 8. 预登记核对点（Step 8 一致性 Review）

| # | 核对点 | 结果 |
|---|--------|------|
| 1 | 四文档 `case` 数量一致为 6 | ✅ G1-G6 定义 6 处 |
| 2 | 用例计数与总数预测一致 | ⚠️ 原 14/623 少计参数化 → 实测 **17/626**（F-S9-G7），四文档已同步 |
| 3 | 「不证明正确性」表述一致 | ✅ 8 处，口径统一 |
| 4 | 容差数值一致 | ✅ `rtol=1e-9 / atol=1e-12 / money_atol=1e-6` |
| 5 | `_golden_cases.py` 单一来源约束一致 | ✅ DESIGN D7 / IMPL T-4 / CHECKLIST E7 三处一致 |

**Step 8 结论**：机械校验（四文档 7 链接 0 broken、G1-G6 = 6、623/14 引用自洽）通过；唯一需修正的是用例计数的参数化展开（已在 Step 9 按实测回填），**P1=P2=0，通过**。

## 9. Step 10 ADD 审计（Phase 0-4）

| Phase | 检查 | 结果 |
|-------|------|------|
| 0 措辞扫描 | DESIGN/IMPL/CHECKLIST 不可审计措辞（「合理处理/酌情/视情况」） | ✅ 0 命中 |
| 1 设计-实施映射 | D1-D10 → 实际文件；每项带行号 | ✅ D1(I1-I6)→`test_golden_baseline.py`；D2/D3→JSON+断言；D4→`_golden_cases.CASES`；D5→`_synth_fixture.py`；D6→`record_golden.py`；D7→测试；D8→无 workflow 改动（正确）；D9→B1/B2；D10→§11 |
| 2 numstat 对账 | `git diff --numstat` 与新文件清单 | ✅ 改 2（`_synth_fixture.py` / `BACKTEST_CALIBER_MAPPING.md`）+ 新增 10（4 文档 + 1 脚本 + 2 测试 + 1 辅助 + 1 目录含 6 JSON） |
| 3 盲区扫描 | 全部新增/修改文件逐行归属 | ✅ 无无依据代码行为；`core/`、`filter/` diff = 0 |
| 4 Iron Law | 交付物是否都有验收行 | ✅ 36 项覆盖 6 case / schema / 容差 / 脚本 / 不变式 / 文档 / 门禁；**F-S9-G1 反例**：不变量观测网再次捕获真实缺陷（停牌路径），证明「基线必须过不变量门」的必要性 |

**Step 10 结论**：**P1=1（F-S9-G1，**不在本批修复**，另立批次）/ P2=2（F-S9-G2 / F-S9-G5，已修）/ P3=4（已回写）**；生产代码零改动；门禁 **5/5 pass**（G5 已由 CI run `42786173151` 回收）。

## 10. 分母统计与签字

| 组 | 项数 | 通过 |
|----|------|------|
| A 夹具能力 | 6 | 6 |
| B schema/容差 | 5 | 5 |
| C 六条 case | 6 | 6 |
| D 录制脚本 | 4 | 4 |
| E 测试与不变式 | 7 | 7 |
| F 文档与声明 | 3 | 3 |
| G 门禁与 CI | 5 | 5 |
| **合计** | **36** | **36** |

| 角色 | 基座 | 日期 |
|------|------|------|
| 实施 | DeepSeek-V4.1-Flash | 2026-11-10 |
| 审计（Step 10，单 Agent 自查） | DeepSeek-V4.1-Flash（**同基座限定**） | 2026-11-10 |
| RULE-5 异构复审 | **待独立会话** | — |
