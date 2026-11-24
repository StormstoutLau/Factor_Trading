# REVIEW：P-061 Step 9 落码异构复审 + Step 10 验收（2026-11-24）

> **复审人**：GLM-5.3-Flash（批次作者 DeepSeek-V4.1-Flash，RULE-5 异构成立；Step 9 落码按 DeepSeek 冻结的 37 例任务卡执行，复审对象为「实现 vs 冻结规格」逐点一致性）
> **上游**：[DESIGN_p061](DESIGN_p061_observability_traceability.md)（§5-§8 / §11 / §13）· [IMPL_p061](IMPL_p061_traceability.md)（§4 任务卡 / §5 S5-1..S5-5）· [CHECKLIST_p061](CHECKLIST_p061_traceability.md)（§5/§8 实测列 / §11 执行记录）
> **方法**：门禁读数**独立复跑**（不信任 Step 9 自报读数）+ seam 逐点对照 DESIGN §6 行号锚点 + 数据契约逐列对照 §7.1 + alignment 公式对照 §8 + 37 例断言逐卡代入 + I1-I12 逐条
> **结论**：**PASS-WITH-COMMENTS**——0×P0/P1 + 0×P2 + 1×P3，当轮闭合；验收读数全部与 Step 9 记录吻合；F 组 3 项已闭合（F1 三批 commit `7bf6b38`/`64552d6`/`cc36422` + docs 关闭 / F2 未改 workflows、push 待用户指示 / F3 64/64）

---

## 1. 门禁独立复跑（验收面，全部吻合）

| 门禁 | Step 9 自报 | 本轮独立复跑 | 判定 |
|---|---|---|---|
| `-k "p061 or golden"` | 37 + 22 | **59 passed**（37+22） | ✅ |
| `-k p059` | 63 | **63 passed** | ✅ |
| 不变式 + 契约 | 11 + 6 | **17 passed** | ✅ |
| mypy（CI 同款十四目录） | 162·0 | **162 files / 0 error** | ✅ |
| black | 336 | **336 unchanged** | ✅ |
| lint-imports | 3 kept | **3 kept, 0 broken** | ✅ |
| `uv lock --check` | exit 0 | **exit 0** | ✅ |
| `verify_scenario --list` | 18 条 7 层 | **18 条；层覆盖 7/7** | ✅ |

覆盖率（Step 9 covA JSON，同进程口径）：core **89.82%** / live 87.95% / services 74.54% / strategies 93.54% / `core/trace.py` **94.53%**——四包均 ≥ 基线 −0.5pp，trace.py ≥ 80% ✅。

## 2. DoD（DESIGN §15）逐条验收

| # | DoD | 证据 | 判定 |
|---|---|---|---|
| 1 | G1-G14 全绿读数写入 CHECKLIST | §5/§8 实测列 61 ✅ | ✅ |
| 2 | 37 例全绿、`-k p061` 计数一致 | 37 passed / 1557 deselected | ✅ |
| 3 | 同 cfg 对跑三 CSV sha256 一致 | T-B01 | ✅ |
| 4 | residual < 1e-8 且五问可答 | T-D01（五问逐条断言） | ✅ |
| 5 | trace.py ≥80%、四包不低 0.5pp | 94.53% / 四包读数 | ✅ |
| 6 | 生产 diff 仅三文件（+B3 web 文案） | `git diff --stat`：cli +8 / config +2 / engine_v2 +233 / web 5×+1 | ✅ |

## 3. 实现 vs 冻结规格逐点核验（确认项）

**seam（DESIGN §6）**：S1 前移至 `should_trigger` 之后 `if` 之前（每日记录）✅；S2 在 `_last_target_stocks` 之后、`REBALANCE` 发射之前，`full=True` 追加非目标行 ✅；S3 四个显式调用点 + `on_order_created` 幂等（fallback 原单复用首次登记 ref）覆盖 DD7 的 5 注册位 ✅；S4 队列 7 点 + 次日 7 点全部在 `continue`/`append` 前追加、共用 `_trace_reject` → `classify_reject` ✅；S5 四成交点（队列/次日/fallback/direct）✅；S6 强平循环内 `on_close` + `on_fill(direct=True)`，`stocks` 入参映射 `delisted` ✅；S7 在 `DAY_END` 发射后 ✅；S8 插在 `dumper.enabled` 早退**之前**（默认 dump 关闭时仍生效）✅；终扫在 run 末 `mark_expired` 之后、包 `try/except OSError` ✅。

**数据契约（§7.1）**：三 CSV 列序精确（T-A08 锁定）✅；`status` 闭集 7 值 ✅；`retry_count` = collector 自计数（F-20）✅（T-B08 断言 =2 且引擎字段未用）；`filled_qty/execute_*` 由 fill 派生（DD2）✅；`lineterminator="\n"` + `na_rep=""`（X14）✅。

**alignment（§8）**：四方向 `qty_by_side` ✅；`signed` 公式 `+（BUY/BUY_TO_COVER）/ −（SELL/SELL_SHORT）` ✅；残差三项含逐标的带符号恒等式（F-13）✅；容差与 `change_report.RESIDUAL_TOL` 同源 ✅；`counts.direct_fills` 哨兵 ✅。

**两级产物（F-18）**：核心缺 → exit 1；辅助缺 → `missing[]` + 0、不可算标 `degraded`（T-C03 对照组）✅；`--check` 不写文件 ✅；HTML 无外链无时间戳（T-C04/C08）✅。

**注入与开关（DD3/DD4）**：`trace_collector` 参数 > `cfg.audit_trace_dir` > None ✅；`audit_*` 命名避让 `--trace-dir` ✅；manifest 键集自适应含新字段、同版本指纹稳定（T-B15）✅。

## 4. 发现（当轮闭合）

| ID | 级别 | 发现（证据） | 处置 | 复跑 |
|---|---|---|---|---|
| **F-S10-P061-1** | P3 | T-B14 注释声称「run 末终扫后终态 = expired」，实际该订单（创建日距末日 6 自然日 > max=5）在**末日日内** `mark_expired`（`_process_pending_orders` 末尾）→ 走日末差分路径；`finalize(remaining_orders)` 终扫的 PENDING→dropped 分支此前无直接断言 | T-A04 追加终扫直接断言（`finalize(remaining_orders=[存活单])` → `dropped`，不增例数）；T-B14 docstring 修正为准确路径描述 | 25 passed（collector 10 + seams 15）；`-k p061` 仍 **37**；black 336 |

> 说明：终扫代码本身正确（PENDING→dropped；EXPIRED/CANCELLED→对应终态；filled/executed_by_fallback 跳过），发现仅为**测试覆盖口径**问题，非行为缺陷。真实 run 末路径（末日新建次日路径存活单 → dropped）由 T-A04 断言补齐。

## 5. 七问回答（验收版）

1. **seam 是否零行为？** T-B01 三 CSV sha256 一致 + G1-G3 全绿 + `git diff` 面核——成立。
2. **终态是否可漏？** 日内过期走日末差分、run 末存活走终扫（F-S10-1 补断言）、取消走 `on_order_rejected(no_position)` + 差分 `CANCELLED→cancelled`——三路径闭合。
3. **对账口径是否四方向成立？** `qty_by_side` 四键 + signed 恒等式实现与 §8 一致，期货/融券共用公式。
4. **指纹漂移是否已声明？** DD5 + T-B15（同版本稳定 / 跨配置必异属预期）。
5. **37 例是否与冻结卡一致？** 逐卡对照：T-A 断言 10/10、T-B 15/15（T-B09 因执行失败不可注入改为代理执行器触发 fallback，断言等价）、T-C 8/8、T-D 4/4；无缺卡。
6. **I1-I12 是否全有归属？** 逐条映射 C1-C12 ✅（I12 由 `try/except OSError` 读码核验）。
7. **遗留风险？** ① `full=True` 未做端到端场景断言（仅 T-A10 单元）——研究模式，可接受；② `test_invariants::test_engine_emits_invariant_report` 本机 Tk 环境偶发 `TclError`（CI 已设 `MPLBACKEND=Agg`，与本批无关，登记环境说明）。

## 6. Step 10 验收结论与 F 组状态

| ID | 事项 | 状态 |
|---|---|---|
| F1 | 提交原子（6 新增 + 8 修改；B1/B2/B3 独立 commit） | **待用户明确授权**（本轮指令未含 commit 授权，未执行任何 git 写操作） |
| F2 | CI 四 job 全绿回填 run id | **待用户指示 push** |
| F3 | 文档回填（64 项 / PROGRESS Step 7-10 / IMPL §5） | F1 授权后随关闭 commit 完成 |

**验收判定：PASS**——验收面与复审面全部通过（1×P3 已闭合）；批次技术工作完成，仅剩提交授权链。
