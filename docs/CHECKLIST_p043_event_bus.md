# CHECKLIST：P-043 事件总线（EventLog 接入引擎）

> **批次**: P-043 · **T1**（Layer-1：`core/event_log.py` 契约 + `core/engine_v2.py` 运行时 + `core/config.py` 字段 + `tests/`）
> **上游**: [IMPL_p043](IMPL_p043_event_bus.md)（§3 逐处代码 / §4 V1-V8 / §9 Step 6 pass：0 P1/P2 + 3 P3）；[DESIGN_p043](DESIGN_p043_event_bus.md)（D1-D8 / I1-I10 / §10 Step 4 pass：0 P1/P2 + 5 P3）；[RESEARCH_p043](RESEARCH_p043_event_bus.md)（§7 S1-S10 / §13 Step 2 pass）
> **状态**: **Step 10 ADD pass + U-P043-5 异构终审闭合（2026-11-18，GLM-5.3-Flash）——41/41；D7 提交与 CI 待用户授权；批次关闭以 D7 为条件**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止预填
> **基线读数（@`1306bf8`，P-042 关闭）**: pytest **795** / golden **13 passed, 782 deselected** / black `core tests` **129**（全仓 **196**）/ mypy **104 files 0** / AST `except Exception` **22** / `tests/*.py` **91** / `uv lock --check` exit **0**
> **目标读数**: pytest **803** / golden 13 零重录 / black **130**（全仓 **197**）/ mypy **104 files 0** / AST **22（不变；core 外口径）** / `tests/*.py` **92** / uv exit **0**

---

## 1. A 组：代码变更（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `core/event_log.py` 有 `EventType` 且 5 常量逐字：`engine.run_started` / `engine.rebalance` / `engine.day_end` / `engine.error` / `engine.run_finished` | B1 落码 | 读码 + V1 | ✅ L50-57 逐字；V1 PASS |
| A2 | `IEventBus` 为 `@runtime_checkable` Protocol，4 方法：`append` / `last_seq` / `read` / `subscribe`，签名与 `EventLog` 逐参同型 | A1 落码 | 读码 + V1 + mypy | ✅ L60-77；V1 PASS；mypy 104 files 0 |
| A3 | `EventLog.replay(after_seq=0, handler=None)`：返回 `read(after_seq)` 升序全集；handler 逐条调用且异常**向外传播** | A1 落码 | 读码 + V2 | ✅ L212-226；V2 PASS |
| A4 | `BacktestConfig.event_log_path: Path \| None = None` 位于 `dump_layers_dir` 之后 | B2 落码 | 读码 | ✅ config.py L344 |
| A5 | `BacktestEngineV2.__init__` 末尾有 `event_bus: Optional[IEventBus] = None`；存在 `_injected_event_bus` / `_event_bus` / `_event_bus_errors` 三属性 | A4 落码 | 读码 | ✅ L118 / L149 / L177-178 |
| A6 | `setup()` 步骤 14 三分支：注入优先（config 路径非空时 `logger.info` 显形被忽略）/ 仅 config → `EventLog(log_path=...)` / 均无 → `None` | A5 落码 | 读码 + V4/V6 | ✅ L316-327 三分支逐字；V4/V6 PASS |
| A7 | `_emit` 首行 `bus is None` 短路；`append` 包在 `try/except Exception` 内，失败 `_event_bus_errors += 1` + `logger.debug`，永不抛 | A5 落码 | 读码 + V7 | ✅ L413-422；V7 PASS（errors==calls） |
| A8 | **6 处发射点**逐字：`run()` 的 `RUN_STARTED`（循环前）/ `ERROR`（`_diagnostics.record` 后）/ `RUN_FINISHED`（`elapsed` 后、`_generate_results` 前）；`_process_trading_day` 的 `DAY_END`（`update_market_values` 后）；`_execute_rebalance` 的 `ERROR`（record 后）/ `REBALANCE`（`_last_target_stocks` 赋值后） | A6/A7 落码 | 读码 + V5/V8 | ✅ 6 处逐字；V5/V8 PASS |
| A9 | 结果键 `additional_info["event_bus"] == {"enabled": True, "last_seq": int, "errors": int}`，**仅 `_event_bus is not None` 时出现** | A7 落码 | 读码 + V4/V5/V7 | ✅ L1335-1341；V4 无键 / V5 三值 / V7 errors>0 |
| A10 | 两处 error payload 的 `message` 均截断为 `str(e)[: self._diagnostics.MAX_MESSAGE]`（=200，F-S6-P043-1） | A8 落码 | 读码（`grep "MAX_MESSAGE" core/engine_v2.py` = 2） | ✅ grep **2**（L400/L1019） |

## 2. B 组：测试（V1-V8 + 3 取证项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | V1 契约：`isinstance(EventLog, IEventBus)`；4 方法签名与 `source=""` 默认值；5 常量逐字 | A2 落码 | `tests/test_p043_event_bus.py` | ✅ PASS |
| B2 | V2 replay：5 条后 `replay(2)` = seq `[3,4,5]` 且与 `read(after_seq=2)` 一致；handler 收 3 条；handler 抛错 `pytest.raises` | A3 落码 | 同上 | ✅ PASS |
| B3 | V3 续号：3 条 → 重开 → 追加 seq=4；磁盘 `[1,2,3,4]`（非回归护栏） | 无（现状即正确） | 同上 | ✅ PASS（红态亦 PASS） |
| B4 | V4 默认关闭：`engine._event_bus is None`；结果无 `event_bus` 键；`rglob("*.jsonl")` 为空 | A4/A6 落码 | 同上 | ✅ PASS |
| B5 | V5 发射：首 `RUN_STARTED` / 尾 `RUN_FINISHED`；seq `1..N` 连续；`DAY_END`==5；`REBALANCE`==5；source 逐字；`run_started` payload 三值、`rebalance.n_targets`==2、`day_end` 键集；结果键三值 + 磁盘行数 == N | A8/A9 落码 | 同上 | ✅ PASS |
| B6 | V6 订阅：run 前订阅 → 收集 seq == 磁盘 seq；`unsubscribe()` 后追加不再通知 | A2 落码 | 同上 | ✅ PASS |
| B7 | V7 故障隔离：`_BoomBus.append` 恒抛 → `run()` 正常返回；成交数与基线一致；`errors == boom.calls`；`last_seq == 0` | A7 落码 | 同上 | ✅ PASS |
| B8 | V8a day_loop 错误：error 恰 1 条（`stage="day_loop"`、date=DATES[1]、`RuntimeError`）；`DAY_END`==4；尾 `RUN_FINISHED`；`run_diagnostics.counts["day_loop"]==1` | A8 落码 | 同上 | ✅ PASS（V8 前半段） |
| B9 | V8b rebalance 错误：error==5 且 `stage=="rebalance"`；`REBALANCE`==0；`DAY_END`==5；尾 `RUN_FINISHED`；`counts["rebalance"]==5` | A8 落码 | 同上 | ✅ PASS（V8 后半段） |
| B10 | 红态留证：IMPL §4.3 预测 `7 failed, 1 passed` | 新测试文件已写、实现未落 | pytest 输出逐字 | ✅ 实测 **`7 failed, 1 passed in 2.46s`**（ImportError×3 / AttributeError×1 / TypeError×3；V3 PASS） |
| B11 | 绿态：`test_p043_event_bus.py` **8 passed** | A1-A10 落码 | pytest | ✅ `8 passed, 7 warnings in 8.51s` |
| B12 | 既有测试零订正且全绿：`test_engine_plugins` / `test_manifest` / `test_p026_silent_exception_governance` / `test_compatibility` | A5/A9 落码 | `pytest` 指定四文件 | ✅ **37 passed**（零订正） |

## 3. C 组：不变式（DESIGN I1-I10）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** 默认关闭：golden **13 零重录**；`additional_info` 无 `event_bus`；无 `*.jsonl` 新建（V4） | 全量实现 | `pytest -k golden` + git + V4 | ✅ golden `13 passed, 790 deselected`；`tests/golden/` 空；V4 PASS |
| C2 | **I2** 空路径 seq `1..N` 连续；`run_started.seq==1`；`run_finished.seq==N==last_seq`（V5） | A8 落码 | V5 | ✅ V5 PASS |
| C3 | **I3** `DAY_END` = 成功完成日数（V5=5 / V8a=4）；`REBALANCE` = 成功产出目标组合次数（V5=5 / V8b=0） | A8 落码 | V5/V8 | ✅ V5/V8 PASS |
| C4 | **I4** `replay(k)` 与 `read(after_seq=k)` 逐条一致、升序（V2） | A3 落码 | V2 | ✅ V2 PASS |
| C5 | **I5** 订阅 seq 集合 = 同次运行磁盘 seq 集合（V6） | A2 落码 | V6 | ✅ V6 PASS |
| C6 | **I6** 伪总线抛错不改变成交数与金额；`errors>0` 显形（V7） | A7 落码 | V7 | ✅ V7 PASS（成交数/金额与基线相等） |
| C7 | **I7** 重开同路径首个新 seq = 旧 `last_seq+1`（V3） | 无（现状即正确） | V3 | ✅ V3 PASS |
| C8 | **I9** `pending_order_events.csv` / `run_diagnostics` / `invariant_report` / layer dump **零 diff**；manifest 顶层键集不变 | 全量实现 | `git diff --stat` + `pytest tests/test_manifest.py` | ✅ 生产 diff 仅 3 文件（event_log/config/engine_v2）；manifest 用例全绿；V8 diagnostics 同步 |
| C9 | **I9** manifest `config` 块新增 `"event_log_path": null` → `input_fingerprint` 变化属预期；无固定指纹断言 | A4 落码 | `test_manifest.py` 全绿 | ✅ `test_manifest.py` 全绿（含 `test_fingerprint_stable`） |
| C10 | **I10** `EventLog` 运行时满足 `IEventBus`；`EventType` 为引擎侧唯一事件类型来源（`grep '"engine\.' core/engine_v2.py` = 0） | A1/A2 落码 | V1 + grep | ✅ V1 PASS；grep **0** |
| C11 | 既有语义零变更：V2 交易/净值路径不改写；`test_engine_plugins` 三插件行为不变 | 全量实现 | 全量 pytest + V7 成交对照 | ✅ 全量 **803**；`test_engine_plugins` 全绿；V7 成交对照一致 |

## 4. D 组：门禁、提交与文档（8 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest **803 passed**（795 + 8） | 全量实现 | 全量末行 | ✅ `803 passed, 179 warnings in 53.65s` |
| D2 | golden **`13 passed, 782 deselected`**；`git status --short tests/golden/` 为空 | 全量实现 | 命令 + git | ✅ `13 passed, 790 deselected`（803−13）；目录空 |
| D3 | black `core tests` **130** / 全仓 **197**；`tests/*.py` **92** | 新测试文件落盘 | `black --check` 双口径 + 计数 | ✅ **130 · 197** unchanged；**92** |
| D4 | mypy **104 source files 0** | 全量实现 | CI 逐字命令 | ✅ `Success: no issues found in 104 source files` |
| D5 | AST `except Exception` **22（不变；core 外口径）**；新增 `# type: ignore` = 0 | A7 落码 | P-029 单行命令 + grep | ✅ AST 门禁 **22**；`core/` 内 28→29 非门禁（F-S9-P043-1）；新增 ignore **0** |
| D6 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 全量实现 | 命令 + `git diff` | ✅ exit **0**；两文件无 diff |
| D7 | 提交原子（3 生产文件 + 1 新建测试 + 6 文档）+ CI 四 job 全绿 | D1-D6 通过 | `git show --stat` + `gh run view` | ⏳ 门禁全绿；**提交与 CI 待用户授权**（未提交） |
| D8 | 文档回填：IMPL §10 / PROGRESS 对应小节 / CHANGELOG / 本文件 **41/41** | D7 通过 | 读回 | ✅ IMPL §10 + PROGRESS §3.49.8 + CHANGELOG + **41/41** |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **41**（A 10 + B 12 + C 11 + D 8 = 41，机械计数；B10-B12 为取证项非新用例） |
| 实测列回填 | **41/41**（40 × `✅`；D7 为 `⏳ 待用户授权提交`，门禁前置项 D1-D6 全绿） |

> **RULE-2 统计溯源**：41 = 10 + 12 + 11 + 8（逐表行数）；新用例 **8** = V1-V8（V8 单函数含 a/b 两段，F-S8-P043-1）。
> **RULE-5 声明**：Step 2 同源（DeepSeek-V4.1-Flash）；Step 4 / Step 6 / **Step 8 异构成立**（GLM-5.3-Flash）；Step 10 异构终审由 GLM-5.3-Flash 承接（U-P043-5）。

---

## 6. Step 7 → Step 8 交接

1. 核红态口径：IMPL §4.3 预测 `7 failed, 1 passed`（V3 护栏 PASS）；实测若偏离，按 F-S9-P042-1 惯例以实测回填 B10 与 IMPL §10。
2. 核计数链：795 + 8 = **803**；129 + 1 = **130**；196 + 1 = **197**；91 + 1 = **92**；AST **22 不变**（口径 = core 外十文件；`core/` 内 28→29 非门禁，F-S9-P043-1）；mypy **104** 不变。
3. 核零预填：`[待 Step 9]` 须为 **41**（Step 9 前不得回填）。
4. 核 ID 不混用：DESIGN 决策 `D1-D8` vs 本文件 **D 组**；事件常量 `EventType.*` vs 用例 `V1-V8`；引用一律 `DESIGN-D*`。
5. 核既有测试：B12 四文件必须**零订正**（本批不改 `test_engine_plugins.py`，与 P-042 的 2 文件订正不同）。

---

## 7. Step 8 一致性 Review 记录（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 作者 DeepSeek-V4.1-Flash → **异构成立**（Step 4/6/8 连续三轮）；U-P043-5 终审维持。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 清单总数 | 41 = A 10 + B 12 + C 11 + D 8（逐表行数）；实测列 41 × `[待 Step 9]` | ✅ 零预填保持 |
| 2 | 计数链五文档一致 | RESEARCH §6 / DESIGN §6 / IMPL §7 / 本文件头部 / PROGRESS §3.49.2·4·6 均为 **803 / 130·197 / 23 / 104 / 92** | ✅（F-S8-P043-1 修复后） |
| 3 | 用例数与函数数 | **8 函数** = test_v1..v7 + test_v8（a/b 两段单函数）；795+8=803；红态 7F/1P | ✅（修复前 IMPL 实为 9 函数 → P2） |
| 4 | ID 链 | F-S2-P043-1..4 / F-D3-P043-1..3 / F-S4-P043-1..5 / F-S6-P043-1..3 引用闭环；DESIGN-D1..D8 与本文件 **D 组**无混用（交接项 4） | ✅ |
| 5 | 基座链 | RESEARCH Step2 同源 / Step4·6·8 异构 GLM / Step10 终审 GLM | ✅ 与 §5 RULE-5 声明一致 |

### 7.2 对齐矩阵（RESEARCH S/I ↔ DESIGN ↔ IMPL ↔ CHECKLIST）

| RESEARCH | DESIGN | IMPL | CHECKLIST | 判定 |
|----------|--------|------|-----------|------|
| S1（5 常量） | §3.1 `EventType` | §3.1② | A1 | ✅ |
| S2（协议 4 方法） | D1/§3.1 `IEventBus` | §3.1② | A2 | ✅ |
| S3（seq 语义） | D6 | —（既有 `_recover_state`） | B3/C7 | ✅ |
| S4（replay 传播） | D5/§3.1③ | §3.1③ | A3/B2/C4 | ✅ |
| S5/S6（开关与优先级） | D2/D6 | §3.2/§3.3④ | A4/A6/B4 | ✅ |
| S7（payload 键集） | §4（含 F-S6-P043-1 截断注） | §3.3⑥⑦⑧ | A8/A10/B5/B8/B9 | ✅ |
| S8（`_emit` 永不抛） | D4 | §3.3⑤ | A7/B7/D5 | ✅ |
| S9（结果键） | D7 | §3.3⑨ | A9/B5/B7 | ✅ |
| S10（双通道边界） | D8/G8 | §1 不触碰 | C8/C11 | ✅ |
| I1-I9 | I1-I10（I2 细化空路径 / I9 manifest / I10 新增） | — | C1-C10 | ✅（F-S8-P043-2 补 RESEARCH I2 注） |

### 7.3 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P043-1 | **P2** | **用例计数链断裂**：F-S4-P043-1 将 V8 扩展为 V8a/V8b 时声明「计数链 803 不变」，但 IMPL §4.2 落为**两个独立测试函数**（test_v8a/test_v8b）→ 实为 9 函数，pytest +9=**804**、红态 **8F/1P**，与 DESIGN §6 / IMPL §2·§4.3 / RESEARCH §6 / 本文件（41 项·8 用例·803·7F/1P）/ PROGRESS 全部矛盾；IMPL §4.3 表亦列 9 个用例 ID 却聚合为 `7 failed, 1 passed` | IMPL §4.2 **合并为单函数** `test_v8_error_events_emitted_without_interruption`（a/b 两段；**独立 `events_a.jsonl`/`events_b.jsonl`**——合并的技术要点：共用路径会让第二引擎重开续号并污染 `read()` 断言）；§4.3 表 V8a/V8b → V8；PROGRESS §3.49.4/§3.49.6 误计订正；计数链 **803 / 7F+1P / 8 passed** 恢复有效。**P2 理由**：RULE-2 统计溯源数字系统性矛盾，若带入 Step 9 将使门禁读数与验收基线全面错位 |
| F-S8-P043-2 | P3 | RESEARCH §8 I2 未随 DESIGN I2 细化（「启用且**空路径**」+ 重开归 I7）标注，追溯断链（P-042 F-S8-P042-1 同类） | RESEARCH I2 行补注 |
| F-S8-P043-3 | P3 | 本文件 D7「4 文档」低估（实际 6：RESEARCH/DESIGN/IMPL/CHECKLIST/PROGRESS/CHANGELOG）；D8「PROGRESS §3.49.7」为预估小节号，Step 9 实际登记可能顺延 | D7 改「6 文档」；D8 改「编号以实际登记为准」 |

### 7.4 结论

**Step 8 一致性 Review pass（1 P2 + 2 P3，全部当轮处置）**——四文档 S1-S10 / D1-D8 / I1-I10 / V1-V8 四层对齐闭合，计数链经 F-S8-P043-1 修复后五文档一致。**准予进入 Step 9 TDD**（红态预测维持 `7 failed, 1 passed`，实测为准）。

---

## 8. Step 10 ADD 审计记录（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 审计者 **GLM-5.3-Flash** ≠ Step 9 实施者 DeepSeek-V4.1-Flash → **本轮 ADD 即异构终审**（Step 4/6/8/10 四轮异构；**U-P043-5 在本轮闭合**，不再设独立终审轮）。
> **E3 绑定**: 审计在**未提交工作区**进行（HEAD `1306bf8` + 未暂存 diff；D7 提交待用户授权）。

### 8.1 四阶段结论

| Phase | 项 | 读数 | 判定 |
|-------|----|------|------|
| 0 | 模糊词自审（审计语言） | 本节无「显然/明显/应该没问题」类断言；全部读数带命令 | ✅ |
| 1 | DESIGN D1-D8 落地 | D1 协议同文件（L50-77）/ D2 config+注入三分支 / D3 6 发射点 / D4 `_emit` / D5 replay / D6 默认不构造 / D7 结果键 / D8 缺口映射（G1/G3-G6 关闭、G2→O-P043-1、G7/G8 声明）——V1-V8 + 探针 P1-P8 逐项命中 | ✅ |
| 2 | 生产 diff ↔ IMPL §3 对拍 | `git diff --stat`：`engine_v2.py` +86/−4、`event_log.py` +56/−1、`config.py` +1、测试 +1 文件；black 格式化差异（`logger.info` 折叠）已由 F-S9-P043-2 披露，语义逐字等价 | ✅ |
| 3 | 变更面越界 | `git status --short` 排除白名单后**空输出**——恰 10 文件（5 M + 5 新）；`pyproject.toml`/`uv.lock`/`tests/golden/` 零 diff | ✅ |
| 4 | 深挖（探针 + 盲区） | E2 八组探针全过（含 2 组套件未覆盖增量）；E4 全净（见 8.3）；1 项 P3 观察（8.2） | ✅ |

### 8.2 发现与处置（0 P1 / 0 P2 / 1 P3 观察）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S10-P043-1 | P3（观察） | P7 探针暴露：error 事件 payload 已截断至 200（F-S6-P043-1），但**既有** `logger.error(f"处理交易日 {date} 时发生错误: {e}")`（L405/L1024）打印完整异常消息（探针中 500 字符全文落日志）——属 P-025 时代既有行为，本批未改日志面 | 登记 **O-P043-2**：日志行截断与 P-054 服务层日志治理一并裁决；本批零改动（改动即越界） |

### 8.3 取证矩阵（RULE-6）

| 层 | 读数 |
|----|------|
| **E1** | pytest **`803 passed, 179 warnings in 82.47s`** / golden **`13 passed, 790 deselected`** / mypy **`104 source files 0`** / black **130 · 197** / AST 门禁 **22** / `tests/*.py` **92** / `uv lock --check` exit **0**——七门禁独立复跑全命中 |
| **E2** | 自编探针 `%TEMP%\p043_add_probe.py`（非测试套件）8 组全过：P1 契约常量逐字 / P2 replay+handler 传播 / P3 重开续号 / P4 默认关闭 / P5 发射 N=12（1+5+5+1）seq 连续+payload+结果键 / P6 故障隔离 calls=12·trades=10 / **P7 message 截断恰 200** / **P8 注入优先且 config 路径文件未创建**；`PROBE_OK p043_all_8_groups` |
| **E3** | 读码 @未提交工作区（HEAD `1306bf8` + diff）：`EventType` L50-57 / `IEventBus` L60-77 / `replay` L212-226 / config L344 / 引擎 9 处（`_emit` L413-422、结果键 L1335-1341）；`except Exception` 恰 3（HEAD 2 + `_emit` 1）；`"engine\.` 裸字符串 **0**；`get_event_log/log_event(` 唯一命中 = L1353 `pending_queue.get_event_log()`（独立通道）；`contextlib.suppress` **0**；新增 `# type: ignore` **0** |
| **E4** | 盲区扫描：变更面白名单外**零文件**；`EventLogPlugin` 与总线双入口已由 S6 隔离（注入优先 + 不使用全局单例）；`setup()` 重调用语义 = 组件重建、事件随磁盘恢复续号（E2-P3 覆盖）；cursor/live/WS 面零触碰 |
| **E5** | 无推测——全部读数可重放 |

### 8.4 结论

**Step 10 ADD pass（0 P1 / 0 P2 / 1 P3 观察当轮登记）**；**U-P043-5 异构终审由本轮承接并闭合**。G1/G3-G6 关闭、G2→O-P043-1、G7/G8 边界声明维持；批次剩 **D7 提交与 CI 待用户授权**。
