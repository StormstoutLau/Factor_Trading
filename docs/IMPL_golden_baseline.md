# P-013 Golden 基线固化（L4 判据）· 实施规划（Step 5）

> **文档编号**: IMPL_golden_baseline
> **阶段**: Phase 2 - 实施规划（T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 5 完稿，待 Step 6 Review
> **上游**: [DESIGN_golden_baseline.md](DESIGN_golden_baseline.md)（D1-D10 / I1-I6 / §12 Step 4 Review）
> **下游**: CHECKLIST（验收项）
> **档位**: T1
> **门禁 session**: `factorv3-p013-golden-20261110`

---

## 1. RED 基线读数（Step 9 前实测 @`6f583fc`）

| ID | 读数 | 命令 / 证据 |
|----|------|-------------|
| R1 | `609 passed` | `pytest tests -q`（MPLBACKEND=Agg） |
| R2 | black `167 files would be left unchanged` | `python -m black --check .` |
| R3 | mypy `Success: no issues found in 36 source files` | `python -m mypy --explicit-package-bases core` |
| R4 | 盲区 `Found 4 errors in 2 files`（不劣化） | `mypy ... --check-untyped-defs` |
| R5 | 测试文件 **68**（`tests/*.py` 共 70，含 `_synth_fixture.py` / `_reference_impl.py` 两个辅助） | `(Get-ChildItem tests/*.py).Count` = 70 |
| R6 | `tests/golden/` **不存在** | `Test-Path tests/golden` → False |
| R7 | `scripts/record_golden.py` **不存在** | `Test-Path` → False |
| R8 | `_synth_fixture.write_price_fixture` **无 `open_prices` 参数** | `Select-String -Pattern 'open_prices'` → 0 |
| R9 | 工作区干净 | `git status --short` 空 |

**目标末态（预测，Step 9 实测修正见 §8）**：`626 passed`（609 + 9 夹具含参数化展开 + 8 golden；原预测 623 少计 3 项参数化）/ black 不变（新增文件已格式化）/ mypy 0 / 盲区 4 errors 2 files 不劣化 / 测试文件 **70**（68 + `test_golden_baseline.py` + `test_synth_fixture.py`）；`tests/*.py` 由 **70 → 73**（+2 测试 +1 辅助 `_golden_cases.py`）/ `tests/golden/*.json` × 6。

## 2. 任务分解（T-0 ~ T-7）

| ID | 任务 | 交付物 | 批次 | 行为变更 |
|----|------|--------|------|----------|
| **T-0** | 复录 RED 读数 R1-R9 并归档 | 本文件 §1 | 前置 | 否 |
| **T-1** | `_synth_fixture.write_price_fixture` 扩展：独立 `open_prices`/`high_prices`/`low_prices`；`suspend`/`st` 支持矩阵 | `tests/_synth_fixture.py` | B1 | 否（默认参数向后兼容） |
| **T-2** | `_synth_fixture.write_universe` 新增（`list_date.csv`/`delist.csv`/`manifest.json`） | 同上 | B1 | 否 |
| **T-3** | 夹具单测 6 项（独立性 / 兼容性 / 矩阵 suspend / 矩阵 st / universe 格式 / universe manifest 开关） | `tests/test_synth_fixture.py` | B1 | 否 |
| **T-4** | **case 构造器单一来源**：6 个 case 的夹具 + 引擎调用 + 结果抽取 | `tests/_golden_cases.py` | B2 | 否（测试辅助） |
| **T-5** | 录制脚本 `scripts/record_golden.py`（import `_golden_cases`，工作区检查 + 摘要打印 + 只写 `tests/golden/`） | `scripts/record_golden.py` | B2 | 否（仅脚本） |
| **T-6** | 运行录制生成 6 份基线 JSON | `tests/golden/G1..G6.json` | B2 | 否 |
| **T-7** | 断言测试 `tests/test_golden_baseline.py`（6 case 参数化 + I1/I3/I5/I6 结构校验，import `_golden_cases`） | 测试文件 | B2 | 否 |

## 3. 逐批 RED 测试（先失败后实现）

### B1：夹具能力扩展（T-1/T-2/T-3）

`tests/test_synth_fixture.py` 6 项，实现前全部失败（`AttributeError` / `TypeError`）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | `test_independent_open_written` | `write_price_fixture(..., open_prices=X)` 后 `open.pkl` 值 == X，且 `close.pkl` 仍为 `prices` |
| 2 | `test_backward_compatible_ohlc` | 不传 `open_prices` 时 `open.pkl` 与 `close.pkl` 逐值相等（旧行为不变） |
| 3 | `test_backward_compatible_suspend_scalar` | `suspend=0` 写出全 0 矩阵（旧行为不变） |
| 4 | `test_suspend_matrix_supported` | `suspend` 传 2D 矩阵时逐值写入 |
| 5 | `test_st_matrix_supported` | 同上（`st`） |
| 6 | `test_write_universe_format` | 写出 `universe/list_date.csv`（列 `stock,list_date`）、`delist.csv`（`stock,delist_date,delist_return`）、`manifest.json`；`load_universe_snapshot` 读回 `status == "corrected"` |

### B2：基线录制与断言（T-4/T-5/T-6/T-7）

`tests/test_golden_baseline.py` 8 项，录制前 6 个 case 用例失败（`FileNotFoundError`）：

| # | 用例 | 断言 |
|---|------|------|
| 1-6 | `test_golden_case[G1..G6]` | 重跑引擎 → 与 JSON 逐字段比对（金额 `rtol=1e-9/atol=1e-6`；比率 `rtol=1e-9`；计数精确） |
| 7 | `test_all_cases_present` | `tests/golden/` 中 `case_id` 集合 == `{G1..G6}`（I5） |
| 8 | `test_baseline_schema_valid` | 每份基线含 `schema_version`/`git_commit`/`tolerance`，且全部数值有限（I1/I6），`rtol <= 1e-9`（I3） |

## 4. 新增用例计数

| 来源 | 数量 |
|------|------|
| B1 夹具单测 | 6 |
| B2 golden 断言 | 8 |
| **合计** | **14** |

预测：本地 **623 passed**；CI（无 numba，7 项 importorskip）**616 passed, 1 skipped**。

## 5. 验证清单（V1-V12，Step 9 执行并回填）

| ID | 验证项 | 方法 |
|----|--------|------|
| V1 | 全量测试 623 passed | `pytest tests -q` |
| V2 | black / mypy / 盲区 不劣化 | 三条门禁命令 |
| V3 | **可重现性**（I2）：连续两次录制 diff 为空 | 录制两遍 → `git diff tests/golden/` 空 |
| V4 | **向后兼容**：现有 4 处 `_synth_fixture` 调用零改动仍绿 | `pytest tests/test_cross_engine_equivalence.py tests/test_reference_diff.py -q` |
| V5 | G4 vs G1 NAV 相等（常量价零费用） | 读两份 JSON 的 `nav.*` |
| V6 | G3 确实触发掩码：被涨停/停牌标的存在「当日无成交」 | 打印 G3 trades 与掩码标的，人工核对 |
| V7 | G6 确实触发退市：退市日后该标的从可交易集合移除 | 打印 G6 可交易集合末 5 日 |
| V8 | 容差不得被放宽（I3） | `test_baseline_schema_valid` |
| V9 | 基线只读（I4） | 测试后 `git status tests/golden/` 无变更 |
| V10 | `--force` 与脏工作区拒绝路径 | 手工构造脏工作区验证退出码 1 |
| V11 | CI 三版本通过（py_func 路径） | `gh run watch` 回收 |
| V12 | 生产代码零改动 | `git diff --stat -- core/ filter/` 为空 |

## 6. 风险与回退点

| 风险 | 缓解 |
|------|------|
| 基线固化错误行为 | 录制需干净工作区 + 打印摘要人工核对；文档声明非正确性证明（A20） |
| G3/G6 未真正触发（静默空过） | V6/V7 要求人工核对 trades 与可交易集合，不接受「只跑通」 |
| 夹具扩展破坏既有测试 | V4 专项回归 + 6 项兼容性单测 |
| numba 双路径导致 CI 红 | D3 分字段容差；V11 三版本实测 |

**回退点**：B1 与 B2 各自独立可回退（B1 只动测试辅助，B2 只增脚本/JSON/测试）；生产代码永不涉及，回退无行为风险。

## 7. Step 6 实施规划 Review 结论（2026-11-10）

**审查基座**: 本会话 DeepSeek-V4.1-Flash（同基座；异构 RULE-5 留待独立会话）

| 检查项 | 方法 | 结果 |
|--------|------|------|
| R1-R9 复录自洽 | E1 本会话实测 | ✅ 609 / 167 / 36 files / 4 errors 2 files / 70 个 `tests/*.py`（= 68 测试 + 2 辅助）/ golden 与脚本均不存在 / 工作区干净 |
| 用例计数 14 → 623 | 算术复核 | ✅ 6 + 8 = 14；609 + 14 = 623 |
| 测试文件计数 | 复核 | ⚠️ 原文写 69，实为 **68 + 2 = 70**；`tests/*.py` 70 → 73（含 `_golden_cases.py`）——已修正 |
| 录制/断言夹具一致性 | 设计走查 | ❌ **原 D7 规定「测试不 import 录制脚本」，但未规定共用构造器 → 两侧各建夹具会漂移**——F-I-G1 |
| 任务覆盖 D1-D10 | 双向核对 | ✅ D1(I1-I6)→T-7；D2(schema)→T-4；D3(容差)→T-7；D4(6 case)→T-6；D5(夹具)→T-1/T-2；D6(脚本)→T-5；D7(测试)→T-7；D8(CI)→无任务（不改 workflow，正确）；D9(批次)→B1/B2；D10(风险)→§6 |

**发现（2 项，已回写）**

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-I-G1 | **P2** | case 构造器无单一来源：录制脚本与断言测试各自构造夹具 → 「录制的是 A、断言跑的是 B」静默漂移，基线失去意义 | 新增 T-4 `tests/_golden_cases.py` 作为唯一构造器；D7 同步写入该约束 |
| F-I-G2 | P3 | 目标末态「测试文件 69」计算错误（68+2=70），且未计入 `_golden_cases.py` | 已修正为 70 / `tests/*.py` 73 |

**结论**：P1=0 / P2=1（已回写）/ P3=1（已回写）；任务分解可执行，**可进入 Step 7 CHECKLIST**。

## 8. Step 9 实施记录（2026-11-10）

### 8.1 门禁实测（@ 实施后工作区，基线 `6f583fc`）

| 读数 | 实测 | 与预测 |
|------|------|--------|
| pytest | **626 passed, 142 warnings in 60.67s** | 预测 623 → 实测 626（参数化展开多 3 项，F-S9-G7） |
| black | **171 files would be left unchanged** | 167 + 4 新增 py 文件 ✅ |
| mypy | `Success: no issues found in 36 source files` | 0 ✅ |
| 盲区 | `Found 4 errors in 2 files (checked 36 source files)` | 不劣化 ✅ |
| 生产代码 | `git diff --stat -- core/ filter/` = 空 | 零改动 ✅ |

### 8.2 验证清单回填（V1-V12）

| ID | 结果 | 证据 |
|----|------|------|
| V1 | ✅ | `626 passed` |
| V2 | ✅ | black 171 / mypy 0（36） / 盲区 4 errors 2 files |
| V3 | ✅ **逐字节可重现** | 连续两次录制 6 份 JSON 的 SHA256 完全一致 |
| V4 | ✅ | `test_synth_fixture.py`(9) + `test_cross_engine_equivalence.py`(5) = 14 passed |
| V5 | ✅ | G1/G4 的 `nav.first/last/min/max` 均为 1e7（length 6 vs 5，见 F-S9-G4） |
| V6 | ✅ | G3：涨停日 `2024-01-16` 对 `000001` 买入 0 笔；`limit_up_mask=False` |
| V7 | ✅（部分） | G6：退市日起仅 1 笔 `SELL qty=162300` 清仓，此后持仓恒为 0；无 BUY（见 F-S9-G6） |
| V8 | ✅ | `test_baseline_schema_valid`：`rtol<=1e-9` / `money_atol<=1e-6` |
| V9 | ✅ | 跑完全量测试后 6 份基线 SHA256 不变 |
| V10 | ✅ | 脏工作区 → 拒绝 exit=1；`CI=true` → 拒绝 exit=1 |
| V11 | 待远端 | CI 三版本 |
| V12 | ✅ | `core/`、`filter/` diff 为空 |

### 8.3 实施期发现（F-S9-G1 ~ F-S9-G7）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-G1** | **P1** | **停牌路径账目缺陷**：G3 初版（含 `suspend[12:14,1]=1`）触发 5 项 I2 违规——停牌日 `2024-01-17` 仍发生 `BUY 108800`；恢复日 `2024-01-22` 同一卖出被重复记录（`SELL 326500` ×2 + `SELL 109500`），实际执行 436000 但 trade_log 记 762500，导致持仓 **-109500**（负持仓）与 I2 不一致 | **不在本批修复**（P-013 非目标=不改 core）。G3 移除停牌场景，仅保留涨停掩码；缺陷登记并建议另立 P-014。`_run_v2` 增加不变量 fail-fast（违规即拒绝生成基线），防止未来静默固化违规行为 |
| **F-S9-G2** | P2 | G3 初版涨停构造污染价格序列（`open=prev×1.10` 但 `close` 未涨），产生 `total_return=+47.4%` / `annual_return=+10449%` / `vol=4.18` 的荒谬基线 | 改为整段上移（`close[10:,0] ×= bump`，`open=close`），涨停真实且价格连续；实测 `+2.86%` / `vol=0.124` |
| **F-S9-G3** | P3 | V3 `-float(max_drawdown)` 在 mdd=0 时产生 `-0.0`，基线 JSON 出现负零 | `_run_v3` 归一化 `abs(mdd)<1e-15 → 0.0` |
| **F-S9-G4** | P3 | DESIGN/CHECKLIST 假设「G4 与 G1 nav 逐项相等」不成立——V2 末日强平追加同日第二快照（F-S9-3 既有行为），`nav.length` 为 6 而 V3 为 5 | 口径修正为「`first/last/min/max` 相等，`length` 差 1（V2 末日双快照）」 |
| **F-S9-G5** | P2 | 基线 JSON 含 `recorded_at` 时间戳 → 每次重录必产生 diff，**V3 可重现性验证永远失败** | 移除该字段；基线只保留 `git_commit`/`python_version`/`dirty`/`numba_available` 四项元数据 |
| **F-S9-G6** | P3 | 退市日 `2024-01-22` 出现 1 笔 `SELL` 清仓，而 `listing_mask` 标该股当日不可交易（含卖出）——账目一致且持仓归零，属合理结果但与掩码语义有张力 | 登记为观察项；V7 口径改为「退市起无 BUY + 持仓归零」；建议后续批次明确「退市结算」契约 |
| **F-S9-G7** | P3 | 用例计数预测 623 少于实测 626——`test_synth_fixture` 两处参数化各展开 2 项（6 → 9） | 已修正本文与 CHECKLIST 的目标末态 |

### 8.4 产物清单

| 类型 | 路径 |
|------|------|
| 夹具扩展 | `tests/_synth_fixture.py`（改） |
| case 构造器 | `tests/_golden_cases.py`（新，单一来源） |
| 录制脚本 | `scripts/record_golden.py`（新） |
| 基线 | `tests/golden/G1..G6.json`（新，6 份） |
| 测试 | `tests/test_synth_fixture.py`（新，9 用例）/ `tests/test_golden_baseline.py`（新，8 用例） |
| 文档 | 四文档 + 本 §8 |
