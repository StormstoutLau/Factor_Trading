# P-014 V2 停牌路径账目缺陷修复 · 验收 CHECKLIST（Step 7）

> **文档编号**: CHECKLIST_p014_suspension_accounting
> **阶段**: Phase 4 - 验收（T1 完整管线）
> **日期**: 2026-11-10
> **上游**: [IMPL_p014_suspension_accounting.md](IMPL_p014_suspension_accounting.md)（T-1~T-7 / V1-V13）
> **下游**: Step 10 ADD 审计
> **档位**: T1
> **门禁 session**: `factorv3-p014-suspension-20261110`
> **RULE-1 声明**: 实测列于 Step 9 完成后逐项回填（回填时点 2026-11-10，工作区 @`1b7b990` + 本批文档）。

---

## 1. 复现与性质（A）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| A1 | 修复前能稳定复现缺陷：次日路径下停牌标的恢复日卖出 ≥2 笔且收盘持仓 < 0 | 修复前 worktree @`29cd6fa` 跑测试 | RESEARCH §4.2 | ✅ `4 failed, 1 passed`；`I2 违规 5 项: 600000 持仓=-400.0 != 成交累计=-218000.0`（G3 派生夹具为 -113600） |
| A2 | 队列路径修复前 `invariant_report.ok == True` | 同上（`accounting_properties[queue]`） | RESEARCH §4.2 | ✅ 红阶段该参数化用例通过 |
| A3 | **I1**：修复后两条路径的 `invariant_report.ok` 均为 True（I2 违规 0） | 性质测试断言 | I1 | ✅ `pytest tests -q` → `635 passed`；两参数化用例全绿 |
| A4 | **I2**：所有快照持仓 `quantity >= 0` | 遍历快照断言 | I2 | ✅ 断言 `negatives == []` 通过 |
| A5 | **I3**：按时间重放，任一笔 SELL 成交量 ≤ 执行前持仓 | 重放断言 | I3 | ✅ 断言通过（修复前该断言先被 I2 拦截） |
| A6 | **I4**：同一 `(date, stock, side)` 无 quantity 完全相同的两笔成交 | trades 去重断言 | I4 | ✅ `duplicated == set()` |

## 2. 修复行为（B）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| B1 | `_clamp_sell_quantity`：BUY 原样返回 | 单测 | D2 | ✅ `test_clamp_sell_quantity`：BUY 300 → 300 |
| B2 | `_clamp_sell_quantity`：无持仓 → 0；持仓 100 / 订单 300 → 100；持仓 500 / 订单 300 → 300 | 单测三例 | D6 | ✅ 实跑 `test_clamp_sell_quantity` 三例全过（500/800→500、空仓→0） |
| B3 | 队列路径：`qty == 0` 时订单状态变为 `CANCELLED` 且不产生 trade | 单测 | D1 L3 | ✅ `test_queue_sell_without_position_is_cancelled` → `CANCELLED`，trade 数不变 |
| B4 | 次日路径：`qty == 0` 时该订单被丢弃且告警日志命中夹紧文案 | 运行日志扫描 | DR-4 | ✅ `test_next_day_sell_without_position_is_dropped` 通过；日志 `卖出订单无可卖持仓，已丢弃: 600000 100股` |
| B5 | `_cancel_next_day_orders`：指定 stocks 时只撤这些标的，返回撤销数 | 单测 | D5 | ✅ `test_cancel_next_day_orders_scoped`：cancelled=1，范围外订单保留 |
| B6 | `_expire_next_day_orders`：买 5 日 / 卖 10 日过期；未到期保留 | 单测两例 | D7 | ✅ `test_expire_next_day_orders`：expired=2，fresh 保留 |
| B7 | 停牌场景下，恢复日停牌标的只出现**一笔**卖单（不再重复） | 修复后运行记录 | D1 L1 | ✅ 01-22 仅 `SELL 338600` 一笔（修复前三笔） |
| B8 | 陈旧买单不再无限重试：01-17 生成的买单不再存活到 01-29 | 运行时队列快照 / I5 | D7 | ✅ 修复后队列中无 create=01-17 的残留；`_expire_next_day_orders` 单测覆盖 11 自然日 |

## 3. 双路径与语义（C）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| C1 | 两条路径在同一停牌夹具上均满足 I1-I4 | 参数化性质测试 | D1 | ✅ `test_accounting_properties[next_day|queue]` 均通过 |
| C2 | 两条路径的关键指标方向一致（total_return 符号相同、final_value 差异 < 5%） | 运行对比 | U-P014-2 | ✅ `test_two_paths_final_value_close`：差异 < 5% |
| C3 | 撤单范围与队列路径一致（`set(signal_df.columns)`） | 读码 + 单测 | D5 | ✅ `engine_v2.py` `_execute_rebalance` 两分支同集合语义 |
| C4 | 掩码语义零改动（停牌日仍无该标的成交） | 运行记录 | 约束 1 | ✅ 01-18/01-19 无 600000 成交（与修复前一致） |

## 4. 基线与回归（D）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| D1 | golden G7 新增且 schema 校验通过 | `pytest -k G7` + `test_baseline_schema_valid` | D9 | ✅ G7 录制成功；schema 用例（含 `suspend` 场景白名单）通过 |
| D2 | G7 基线两次录制 SHA256 一致 | 录制脚本跑两次 | V11 | ✅ 全量复录与仓内 JSON `IDENTICAL`（含 G7） |
| D3 | G1-G6 逐 case 比对：有变化者给出「改前/改后 + 合理性」说明后重录 | 录制 diff 台账 | A20 / D10 | ✅ G1/G2/G4/G5/G6 `IDENTICAL`；G3 重录（trades 56→55、NAV rel 1.11e-6，理由见 IMPL §9.3） |
| D4 | 全量回归 `635 passed` 且 0 fail | `pytest tests -q` | V1 | ✅ `635 passed, 152 warnings in 42.26s` |

## 5. 文档与声明（E）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| E1 | RESEARCH 对「停牌日成交」症状的**订正**可追溯（保留原登记值） | 读回 RESEARCH §4.3 | F-R-P014-1 | ✅ §4.3 三行对照表（原描述 / 本次复现 / 处置） |
| E2 | PROGRESS 的 P-014 行更新为 done 并附证据链接 | 读回 PROGRESS §1.4 | Step 10 | ✅ P-014 → done（2026-11-10），链接本目录四文档 |
| E3 | CHANGELOG 记录行为变更（两条路径的订单生命周期语义） | 读回 CHANGELOG | — | ✅ Fixed/Changed 条目（P-014） |

## 6. 门禁（F）

| ID | 验收项（DoR → DoD） | 证据出口 | 锚点 | 实测 |
|----|---------------------|----------|------|------|
| F1 | black 全绿 | `black --check .` | V2 | ✅ `172 files would be left unchanged` |
| F2 | mypy `Success`（36 files） | `mypy --explicit-package-bases core` | V2 | ✅ `Success: no issues found in 36 source files` |
| F3 | 盲区 `4 errors 2 files` 不劣化 | `mypy ... --check-untyped-defs` | V2 | ✅ `Found 4 errors in 2 files (checked 36 source files)` |
| F4 | 生产代码改动仅 `core/engine_v2.py` + `core/pending.py`（+ `interfaces.py` 协议声明） | `git diff --stat` | V12 | ✅ `engine_v2.py` / `pending.py` / `interfaces.py` 三文件（DR-1） |
| F5 | CI 三版本全绿 | `gh run watch` | V13 | ✅ run `42791704254`（@`6ad7678`）三 job `success`，3.10/3.11/3.12 各 `628 passed, 1 skipped`（= 本地 635 − 7 项 numba `importorskip`）→ G7 与 8 项性质测试在 `py_func` 路径全部通过 |
| F6 | F5 红→绿记录齐备（红 = 修复前失败读数；绿 = 修复后通过读数） | IMPL §9.1 | F5 形态 | ✅ 红 `7 failed, 1 passed`（exit=1）→ 绿 `8 passed`（exit=0） |

## 7. 分母统计

| 组 | 项数 | 通过 |
|----|------|------|
| A 复现与性质 | 6 | 6 |
| B 修复行为 | 8 | 8 |
| C 双路径与语义 | 4 | 4 |
| D 基线与回归 | 4 | 4 |
| E 文档与声明 | 3 | 3 |
| F 门禁 | 6 | 6 |
| **合计** | **31** | **31** |

## 8. Step 8 一致性 Review（四文档对齐）

> 执行时点：四文档全部完稿后（Step 7 之后）；机械校验命令见各结果列

| # | 核对点 | 结果 |
|---|--------|------|
| 1 | 文档间链接可达（相对路径存在性扫描） | ✅ RESEARCH 3 / DESIGN 1 / IMPL 1 / CHECKLIST 1，**broken = 0** |
| 2 | 不变量数量与编号一致（I1-I5） | ✅ DESIGN §3 定义 5 条；CHECKLIST A3(I1)/A4(I2)/A5(I3)/A6(I4)/B8(I5) 覆盖 5/5 |
| 3 | 任务 ↔ 验收项覆盖（T-1~T-7） | ✅ T-1→B3；T-2→B1/B2/B3/B4/C4；T-3→B5/B7/C3；T-4→B6/B8；T-5→A1-A6；T-6→D1/D2；T-7→D3（7/7） |
| 4 | 风险项 ↔ 未决项引用一致（U-P014-1/2/3） | ✅ U-P014-2→C2；U-P014-1（停牌语义）与 U-P014-3（买侧现金）为**显式非目标**，不设验收行（DESIGN §1），符合「非目标不验收」 |
| 5 | 派生需求 DR-1~DR-4 均有验收行 | ✅ DR-1→B3/F4；DR-2→B2/B3；DR-3→D1；DR-4→B4（4/4） |
| 6 | 预测用例数一致 | ⚠️ 预测 `634` → 实测 `635`（新增 8 性质测试 + G7；F-S9-P014-5），已回填 |

**Step 8 结论**：机械校验 6/6 通过（第 6 项按实测订正，非矛盾）；**P1=P2=0**，进入 Step 9 后全部验收落账。

## 9. Step 10 ADD 审计（Phase 0-4 + 取证矩阵）

### 9.1 Phase 0-4

| Phase | 检查 | 结果 |
|-------|------|------|
| 0 措辞扫描 | RESEARCH/DESIGN/IMPL/CHECKLIST 的不可审计措辞（「合理处理 / 酌情 / 视情况 / 适当」） | ✅ 0 命中（`Select-String` 四文件） |
| 1 设计-实施映射 | D1-D10 → 实际代码/测试 | ✅ D1→三层防线（`engine_v2.py` 三个 helper + 三处接入）；D2→`_clamp_sell_quantity`；D3→`mark_cancelled`；D4→`pending.py::cancel_order`；D5→`_cancel_next_day_orders` + `_execute_rebalance`；D6→`min(qty, available)`；D7→`_expire_next_day_orders`；D8→无改动（正确）；D9→G7；D10→8 项性质测试 |
| 2 numstat 对账 | `git diff --numstat 29cd6fa -- core/ tests/ scripts/` | ✅ 生产代码 3 文件 `+146/−5`（engine_v2 +116/−5、interfaces +4、pending +26）；测试/基线 6 文件 +340/−18；脚本 1 行文档串 |
| 3 盲区扫描 | 逐行归属新增代码 | ✅ 无无依据行为；`tracker.py` / `filter/` / 掩码层 **零改动** |
| 4 Iron Law | 「测试通过 ≠ 设计落地」 | ✅ 以 **F5 红→绿** 为证：红阶段（旧代码）7 failed，每个失败可映射到 D1/D5/D7 的缺失；绿阶段 8 passed 且额外由 G7 golden 锁行为 |

### 9.2 取证矩阵（E1-E5）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| `pytest tests -q`（E1） | A3/A4/A5/A6、C1、D4 | ✅ `635 passed`，0 fail |
| 修复前 worktree 重放（E1） | A1/A2、F6 红读数 | ✅ `7 failed, 1 passed`（@`29cd6fa`） |
| `pytest tests/test_p014_suspension_accounting.py -q`（E1） | B1-B8、C1/C2 | ✅ `8 passed` |
| 运行时复现脚本（E2，含两路径对照与停牌/涨停双掩码场景） | A1/A2、B7、C4、§9.5 对照 | ✅ 修复后两路径 I2 均为 0；恢复日仅 1 笔卖单 |
| 录制脚本复录比对（E2，7 case 全量） | D2/D3 | ✅ G1/G2/G4/G5/G6 `IDENTICAL`；G3/G7 与仓内一致 |
| 静态读码（E3 @`1b7b990`） | B5/B6、C3 | ✅ `_cancel_next_day_orders` / `_expire_next_day_orders` / `_execute_rebalance` 两分支 |
| `git diff --numstat`（E1） | F4、Phase 2 | ✅ 生产代码仅 3 文件 |
| 盲区扫描（E4，扫描范围：`core/engine_v2.py` 全部新增行 + 两个 helper 的调用点） | Phase 1/3 | **发现 0 项无设计依据行为**（降级重扫：换「调用点反向核对」角度二次扫描，仍 0 项） |
| 门禁三校验（E1） | F1/F2/F3 | ✅ black 172 / mypy 0（36）/ 盲区 4 errors 2 files 不劣化 |

### 9.3 审计结论

**P1 = 0 / P2 = 2（F-S9-P014-1 / -2，均已修复）/ P3 = 3（F-S9-P014-3 未修并登记；-4 / -5 已修）**；CHECKLIST **31/31**（F5 已由 CI run 42791704254 回收）。审计者与实施者为同一 Agent（RULE-4 自查声明），RULE-5 异构复审见 §9.4。

### 9.4 RULE-5 异构复审（2026-11-10，pass）

> **复审基座**: **GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash**（异构性成立）
> **复审方式**: 不信任既有结论，E1-E5 独立重放；复审输出只标记问题（单向权限），不改写实现
> **复审会话**: 独立会话执行，仅携带四文档与待验证声明清单

#### E1 可重放命令重放（7/7 命中）

| # | 命令 | 作者声明 | 复审实测 | 结论 |
|---|------|----------|----------|------|
| 1 | `git rev-parse HEAD` + `git status --short` | HEAD=`a2b50f2`，干净 | `a2b50f2c838…`，空输出 | ✅ |
| 2 | `pytest tests -q`（Agg） | `635 passed` | **`635 passed, 152 warnings in 45.17s`** | ✅ |
| 3 | `black --check .` | `172 unchanged` | **`172 files would be left unchanged`** | ✅ |
| 4 | `mypy --explicit-package-bases core` | `0（36 files）` | **`Success: no issues found in 36 source files`** | ✅ |
| 5 | `mypy … --check-untyped-defs core` | `4 errors 2 files` | **`Found 4 errors in 2 files`** | ✅ |
| 6 | `gh run view 42791704254` | 三 job success | **3.10/3.11/3.12 全 `✓`**（另 `42792162974` / `42792500049` 亦 success） | ✅ |
| 7 | worktree @`29cd6fa` + 当前测试集 | 红 `7 failed, 1 passed` | **`7 failed, 1 passed`**，失败签名逐项一致（I2×5 项 / `EXECUTED≠CANCELLED` / `1==0` / 净值 13.19M vs 9.93M / 3×AttributeError） | ✅ |

#### E2 运行时取证（复审自建夹具，未复用作者构造器）

| 场景 | 复审实测 | 结论 |
|------|----------|------|
| 双路径停牌（suspend[12:14,1]=1，独立生成价格/因子） | 两路径恢复日均**仅 1 笔** 600000 卖单、`invariant ok=True`、违规 0、无负持仓 | ✅ 修复性质独立成立 |
| 队列订单簿探针 | `EXECUTED` 且 `_filled_qty != quantity` 的订单 = **0**，PARTIAL = 0 | ✅ 本场景无错配（见 F-R5-P014-1 潜在分支） |
| 7 case 全量复录比对（@`a2b50f2` vs 仓内 @`d1a1cc2`） | **G1-G7 全部 IDENTICAL**（metrics/nav/trades 逐值） | ✅ D2/D3 声明成立 |

#### E3 静态锚点（绑定 `@a2b50f2`）

| 锚点 | 行号 | 结论 |
|------|------|------|
| `_clamp_sell_quantity` | engine_v2.py:631 | ✅ |
| `_cancel_next_day_orders` | engine_v2.py:650 | ✅ |
| `_expire_next_day_orders` | engine_v2.py:679 | ✅ |
| 队列路径接入（clamp / cancel / mark_executed） | engine_v2.py:752 / 755 / 781 | ✅ |
| 再平衡接入（elif 分支） | engine_v2.py:877 | ✅ |
| 次日路径接入（expire / clamp） | engine_v2.py:1063 / 1109 | ✅ |
| `cancel_order` 实现 + 协议声明 | pending.py:355 / interfaces.py:357 | ✅ |
| 不变量 fail-fast 守卫（G7 录制侧） | _golden_cases.py:131-135 | ✅ |

#### E4 盲区重扫（发现 3 项，均为 P3；已按单向权限仅标记）

| ID | 等级 | 发现 | 建议 |
|----|------|------|------|
| **F-R5-P014-1** | P3 | 队列路径「部分夹紧」分支（`0 < qty < 订单量`，engine_v2.py:770-781）成交后仍调 `mark_executed`，`_filled_qty` 被置为**全量**（pending.py:145-155）——订单簿记录与实际成交量不一致。账目（现金/持仓）不受影响、订单不重试（剩余量本不应再卖），且 E2 探针证实当前场景未触发（0 mismatch）；但该分支无端到端测试覆盖 | 后续批次改用 `mark_partial(qty, …)` + `mark_executed_full` 语义，或补 1 条端到端部分夹紧用例 |
| **F-R5-P014-2** | P3 | RESEARCH §4.3 处置列的推断（「原描述**可能**来自当时价格污染…」）未加显式证据等级标注；Step 2 Review L139 声称「已标注为推断」略有夸大（仅有「可能」措辞，无「推断/E5」标签） | 行内补「（推断，E5 级，不作为结论）」 |
| **F-R5-P014-3** | P3 | CHECKLIST F5 引用 run `42791704254` @`6ad7678` 准确，但终态 HEAD 为 `a2b50f2`——基线与代码的最后变更提交确为 `6ad7678`，其后均为纯文档提交且 CI 亦绿；声明无误但终态读者需自行推断 | F5 补注「其后两次纯文档提交 CI（`42792162974` / `42792500049`）亦 success」 |

#### E5 诚实性核查

- 作者声明中未发现 E5 级断言被用作结论；红→绿两读数、CI run 号、IDENTICAL 声明均可重放。
- 「G3 行为变更合理性」属解释性论证（A20 允许），数值证据（56→55、rel 1.11e-6）已由 E2 复录独立确认。

#### 复审结论

**P1 = 0 / P2 = 0 / P3 = 3（F-R5-P014-1 ~ -3，均不阻断验收，登记待后续批次）**。E1 七项、E2 三项、E3 八项全部独立命中，作者声明与实测**零偏差**；RULE-5 复审 **pass**。

## 10. 签字

| 角色 | 基座 | 日期 |
|------|------|------|
| 实施 | DeepSeek-V4.1-Flash | 2026-11-10 |
| Step 10 审计（单 Agent 自查） | DeepSeek-V4.1-Flash（同基座限定） | 2026-11-10 |
| RULE-5 异构复审 | **GLM-5.3-Flash**（≠ 作者基座，§9.4 pass） | 2026-11-10 |
