# CHECKLIST：P-025 日循环异常分类与 retry 语义

> **批次**: P-025 · **T1**（`core/` 行为契约 + 结果字典新增键）
> **上游**: [IMPL_p025](IMPL_p025_daily_loop_exception_semantics.md)（T-1~T-6 / §11 Step 6 Review）；[DESIGN_p025](DESIGN_p025_daily_loop_exception_semantics.md)（D1-D7 / I1-I7 / V1-V12）
> **状态**: Step 7 完稿（**42 项**零预填）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **基线读数（Step 7 实测）**: `pytest --collect-only` **654** / `mypy --check-untyped-defs core` **36 files 0** / `black --check core tests cli.py` **114** / `black --check .` **180**

---

## 1. A 组：B1 采集器基座（T-1 → D1 / D2 / D3）

> **DoR**: `core/diagnostics.py` 全量代码形态已在 IMPL §4.1 定稿（含 F-S6-P025-2 的 `_category_counts` 修正）；`day_error_mode` 落地位置已定（config L344 后）。**DoD**: 每项有可重放命令或可读码定位，且读数逐字可比。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | 四类分类真值表 8 组参数化全过：`data`/`execution`/`solver`/`internal` 各有命中，`(category, retryable)` 逐字相等 | `pytest tests/test_p025_day_error_diagnostics.py -q -k classify` = 1 passed（8 参数集） | D2 / T1 / V1 | [待 Step 9] |
| A2 | 采集器任何路径不抛错：非法 date（None）/ 非 Exception 对象均不抛，内部降级为 `logger.error` | `test_collector_never_raises` = 1 passed + 读码 `record` 全体包 `try/except Exception` | D3 / T2 / I3 / V2 | [待 Step 9] |
| A3 | 去重与计数分离：同 `(date,stage,category,type,message)` 记 3 次 → `samples` 1 条、`counts["day_loop"] == 3` | `test_dedup_and_count` = 1 passed | D3 / T3 / V2 | [待 Step 9] |
| A4 | 明细上限 50：60 条不同错误 → `len(samples) == 50` 且 `truncated is True`，且 `counts` 仍按 60 计 | `test_truncation_limit` = 1 passed | D3 / T4 / R6 | [待 Step 9] |
| A5 | `DayErrorRecord` 恰 6 字段（`date/stage/category/error_type/message/retryable`）且 `frozen=True`；message 截断 200 字符 | 读码 + `dataclasses.fields()` 断言 = 6；`record` 内 `[: self.MAX_MESSAGE]` 存在 | D3 §契约 | [待 Step 9] |
| A6 | `off` 模式零分配：`record` 首行 `if self._mode == "off": return None`；`summary()` 返回 `{"mode": "off"}` | 读码两处 + `test_off_mode_summary_minimal` = 1 passed | D1 / I4 | [待 Step 9] |
| A7 | 分类不依赖消息文本：`classify_day_error` 无任何 `message`/字符串匹配分支，仅 `stage` 比较 + `isinstance`/`type().__name__` | 读码；`grep -c "message" core/diagnostics.py` 在 `classify_day_error` 区段 = **0** | D2 核心约束 | [待 Step 9] |

---

## 2. B 组：B2 引擎诊断主线（T-2 → D4）

> **DoR**: `run()` catch / `__init__` 采集器 / `additional_info` 键三处位置已在 IMPL §4.3 定稿；T5-T7 单日注入手法已定（F-S5 自查修正）。**DoD**: 三态行为可独立观测，键集合差逐字相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `off` 模式：注入单日日级异常 → `run()` 不抛、控制流与 HEAD 一致，`run_diagnostics == {"mode": "off"}` | `test_off_mode_keeps_flow` = 1 passed；断言字典逐字相等 | D1 / T5 / V3 | [待 Step 9] |
| B2 | `report` 模式（默认）：同注入 → 无上抛，`degraded is True`、`counts["day_loop"] == 1` | `test_report_mode_records` = 1 passed | D1 / T6 / V3 | [待 Step 9] |
| B3 | `raise` 模式：同注入 → 按 `sys.version_info` 分支抛（3.11+ `ExceptionGroup` / 3.10 `RuntimeError`），异常携带 `.diagnostics` | `test_raise_mode_raises` = 1 passed（本机 3.12 走 `ExceptionGroup` 分支） | D1 / T7 / V3 | [待 Step 9] |
| B4 | `run_diagnostics` 键**恒存在**（`report` 与 `off` 双跑）；`set(additional_info) - HEAD_KEYS == {"run_diagnostics"}` | `test_result_key_contract` = 1 passed（双 mode 参数化）；HEAD_KEYS = P11 的 10 键 | I1 / V8 | [待 Step 9] |
| B5 | 日循环既有日志行为保留：`logger.error(f"处理交易日 {date} 时发生错误: {e}")` + `continue` 仍在（I2 控制流/日志不变） | `git diff -U0 <base>..HEAD -- core/engine_v2.py` 中该 `logger.error` 行为**未删除**（仅前后新增行） | D4 / I2 | [待 Step 9] |
| B6 | 优化失败计量：`min_variance` + 80 日 + `cov_lookback=60` → `counts["rebalance"] >= 1` 且 `degraded is True` | `test_optimize_failure_counted` = 1 passed（实测值落 Step 9 记录） | D5 / T8 / V5 | [待 Step 9] |

---

## 3. C 组：B3 内层接线与 D6 / D7（T-3 / T-4 / T-5）

> **DoR**: sink 注解 `object` 化 + `getattr` 探测（F-S6-P025-1）已回写；D6 词表与 fail-closed 形态、D7-O2 预检代码已在 IMPL §4.5-§4.7 定稿。**DoD**: 每项可读码 + 有测试或探针读数。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `ExecutionSimulator.set_error_sink` 存在，默认 `self._error_sink = None`，`except` 分支先调 sink 再 `return False, None` | 读码三处（`__init__` / 方法定义 / `execute_order` except） | D5 | [待 Step 9] |
| C2 | 注入 fake executor（无 `set_error_sink`）不报错：`getattr(executor, "set_error_sink", None)` 为 None 时静默跳过 | `pytest tests/test_decoupled_engine.py -q` 全绿（MockExecutionSimulator 形态不破） | D5 / F-S5-P025-4 | [待 Step 9] |
| C3 | D6 别名生效：`build_optimizer(OptimizerConfig(method="mean_variance"))` 返回 `MeanVarianceOptimizer`（原为 EqualWeight） | `test_mean_variance_dispatch` = 1 passed；`type(...).__name__ == "MeanVarianceOptimizer"` | D6 / T10 / V6 | [待 Step 9] |
| C4 | D6 fail-closed：未知 method → `ValueError`，消息含「合法值」并列出 5 键 | `test_unknown_method_fail_closed` = 1 passed；`pytest.raises(ValueError, match="合法值")` | D6 / T10 / R1 | [待 Step 9] |
| C5 | D7-O2 预检：4 交易日 + `min_variance`（`cov_lookback` 默认 60）→ `setup()` 抛 `RuntimeError`，消息含「必然失败」 | `test_setup_cov_precheck` = 1 passed；`pytest.raises(RuntimeError, match="必然失败")` | D7 / T9 / V5 | [待 Step 9] |
| C6 | 预检只对 4 个协方差方法生效：`equal_weight` 短历史 setup 不抛（R2 无误伤） | 读码 `cov_methods` 集合 + `pytest tests/test_rebalance_exits.py -q` 全绿（4 日 + equal_weight） | D7 / R2 | [待 Step 9] |

---

## 4. D 组：不变式与保护面（I1-I7）

> **DoR**: 保护面清单已在 IMPL §1「零改动面」定稿；golden 基线 7 条已存在。**DoD**: diff 为空或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：`additional_info` 既有 10 键名与语义不变，键集合差恰为 `{"run_diagnostics"}` | B4 已覆盖；另 `git diff` 中既有 10 键构造行 **0 处删除** | I1 | [待 Step 9] |
| D2 | I2：`report`/`off` 下仍 `continue`；探针 A2 快照 20 条 / 19 去重日与 HEAD 逐字节一致 | 探针 `%TEMP%\p025_probe_a2.py` 复跑读数（`report` 模式） | I2 / V4 | [待 Step 9] |
| D3 | I3：采集器零抛错，且 sink 调用不改变 `execute_order` 对外行为 | A2 已覆盖 collectors；探针 C 复跑（3 次注入 → `counts.execution >= 3` 且仍 `return False, None`） | I3 / V7 | [待 Step 9] |
| D4 | I4：`off` 零开销——不构造 record、不写 `counts`，`run_diagnostics` 仅 1 键 | 读码 `record` 首行短路 + B1 断言 | I4 | [待 Step 9] |
| D5 | I5：`execute_order` 签名（5 位置参数 + 4 可选）与返回 `tuple[bool, Optional[Trade]]` 不变 | AST 比对：`ast.dump` 前后 `args`/`returns` 相等；4 处生产调用点（engine L533/L782/L1127 + execution L392）零改动 | I5 | [待 Step 9] |
| D6 | I6：golden G1-G7 数值不变、无重录 | `pytest tests/test_golden*.py -q` 全绿；`git status --short tests/golden/` = 空 | I6 / V9 | [待 Step 9] |
| D7 | I7：末日重复快照形态保留——21 快照 / 20 去重日（与 HEAD 相同，**不得顺带修复**） | 探针 A3 复跑读数与 RESEARCH §5 逐字一致 | I7 / O1 | [待 Step 9] |
| D8 | 零改动面：`core/interfaces.py` / `pending.py` / `data.py` / `rebalance.py` / `cli.py` / `pyproject.toml` / `.github/` / `engine_v3_vector.py` 全部 diff 空 | `git diff --name-only <base>..HEAD -- <上述路径>` = 空 | IMPL §1 | [待 Step 9] |

---

## 5. E 组：测试与门禁（V1-V12）

> **DoR**: T1-T10 规格已在 IMPL §4.8 定稿；基线读数已实测（见文档头）。**DoD**: 计数与末行读数逐字一致。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新增测试文件恰含 **10** 个 `test_*` 函数 | `pytest --collect-only -q tests/test_p025_day_error_diagnostics.py` 末行 `10 tests collected` | V1 / T1-T10 | [待 Step 9] |
| E2 | 新增 10 项全绿 | `pytest tests/test_p025_day_error_diagnostics.py -q` = `10 passed` | V1 | [待 Step 9] |
| E3 | 全量回归 **≥ 664 passed**（654 基线 + 10 新） | `pytest -q` 末行 `664 passed` | V11 | [待 Step 9] |
| E4 | mypy 门禁：**37 files 0 error**（36 + `core/diagnostics.py`） | `mypy --explicit-package-bases --check-untyped-defs core` 末行 `Success: no issues found in 37 source files` | V10 / F-S6-P025-1 | [待 Step 9] |
| E5 | black 两口径：`core tests cli.py` **116** unchanged（114 + 2）/ `.` **182** unchanged（180 + 2） | `black --check core tests cli.py` 与 `black --check .` 末行读数 | V10 | [待 Step 9] |
| E6 | 探针 B2 复跑：20 日 + `min_variance` → **`setup()` 抛 `RuntimeError`**（不再出假成功结果） | `%TEMP%\p025_probe_b2.py` 复跑：旧读数 `sharpe 0.0 / 0 成交` → 新读数 setup 抛错 | V5 / P7 | [待 Step 9] |
| E7 | 探针 C 复跑：3 日注入执行异常 → `counts.execution >= 3`，且第 4 日订单仍全成（成交语义未变） | 探针 C 复跑 + `run_diagnostics` 读数 | V7 / D5 | [待 Step 9] |
| E8 | 五处红态可观测（实现前逐批取证）：T5/T6 键缺失、T8 counts 缺失、T9 `DID NOT RAISE`、T10 `is` 断言失败、测试文件 `ImportError` | Step 9 逐批记录 pytest 读数（**不预填结论**） | F5 / IMPL §11.1 #8 | [待 Step 9] |
| E9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | V12 | [待 Step 9] |

---

## 6. F 组：治理与台账（T-6 → B4）

> **DoR**: 文档落位清单已在 IMPL §2 T-6 定稿；ARCHITECTURE 计数口径问题已登记（F-S4-P025-4）。**DoD**: 行存在、引用可解析、计数自洽。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 四文档齐备且互链：`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p025_daily_loop_exception_semantics.md` 存在，相对链接 0 broken | Step 8 机械校验脚本读数 | T-6 | [待 Step 9] |
| F2 | PROGRESS §1.4 P-025 行置 `done`（含 T1 / 四文档链接 / CI run id） | 读回 §1.4 | T-6 | [待 Step 9] |
| F3 | CHANGELOG `[Unreleased] > Changed` 记录 **3 项行为变更**：`mean_variance` 真正生效 / 未知 method fail-closed / 短历史协方差方法 setup fail-fast | 读回 `CHANGELOG.md` `Changed` 前三条 | D6+D7 观察-2 / R1 | [待 Step 9] |
| F4 | README 增「运行诊断（run_diagnostics）」字段说明；ARCHITECTURE 新增 `core/diagnostics.py` 模块行 + 计数**按其口径**订正（不得简单 +1，见 F-S4-P025-4） | 读回两文档对应节 | T-6 / R5 | [待 Step 9] |
| F5 | U-P025-1~6 六项未决状态更新（承接/关闭/另立），U-P023-1 关闭注写明「由 P-025 承接并完成」 | 读回 PROGRESS §1.4 未决表 | RESEARCH §7 | [待 Step 9] |
| F6 | 实施提交推送后 CI run 三 job success（与 E9 同一 run；F6 只登记提交链） | `git log --oneline` + `gh run list` | V12 | [待 Step 9] |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **42**（A 7 + B 6 + C 6 + D 8 + E 9 + F 6，机械计数） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | **42 处** = 42 验收单元格，**零 ✅ 预填** |
| Step 9 回填后剩余 | 待回填（目标 **0 处**） |

> **RULE-2 统计溯源**：上表 42 由 §1-§6 六张表逐行机械计数得出（A1-A7 / B1-B6 / C1-C6 / D1-D8 / E1-E9 / F1-F6），非估计值。

---

## 8. Step 7 → Step 8 交接事项

| # | 事项 | 说明 |
|---|------|------|
| 1 | **IMPL 基线数字需订正** | IMPL §1 写「black 文件数 +1」，实测为 **+2**（`core/diagnostics.py` + 测试文件）；`black --check core tests cli.py` 基线实为 **114**（非 113）。Step 8 一致性 Review 回写 IMPL |
| 2 | V10 目标读数 | IMPL §8 写「`black --check .` 不变」，应为 **182**；本清单 E5 已按实测口径表述 |
| 3 | 验收项 ↔ 验证项映射 | V1→A1、V2→A2/A3/A4、V3→B1/B2/B3、V4→D2、V5→B6/C5/E6、V6→C3、V7→D3/E7、V8→B4、V9→D6、V10→E4/E5、V11→E3、V12→E9/F6；无遗留 |
| 4 | 未覆盖声明 | `record_failure` 无验收项（F-S5-P025-2 裁决：实现不接线、不单独测试）；「success=False 计量」不在本批范围（F-S4-P025-3） |

---

## 9. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §10](RESEARCH_p025_daily_loop_exception_semantics.md)（异构 GLM-5.3-Flash；2 P3 回写 + 2 观察） | 2026-11-12 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §10](DESIGN_p025_daily_loop_exception_semantics.md)（异构 GLM-5.3-Flash；7 P3 回写 + 4 观察） | 2026-11-12 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §11](IMPL_p025_daily_loop_exception_semantics.md)（1 P2 + 3 P3 回写 + 3 观察） | 2026-11-12 |
| Step 7 验收清单 | 完稿（零预填 42 项） | §1-§7 | 2026-11-12 |
| Step 8 一致性 Review | [待 Step 8] | — | — |
| Step 9 TDD 实施 | [待 Step 9] | — | — |
| Step 10 ADD 审计 | [待 Step 10] | — | — |
| RULE-5 异构复审 | [待 RULE-5] | — | — |
| CI 回收 | [待 Step 9] | — | — |
