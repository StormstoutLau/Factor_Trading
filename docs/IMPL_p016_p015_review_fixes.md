# IMPL：P-016 P-015 复审 P3 修正

> **批次**: P-016 · T1
> **上游**: [DESIGN_p016_p015_review_fixes.md](DESIGN_p016_p015_review_fixes.md)（D1-D4 / I1-I6 / §4-§6 规格）
> **下游**: [CHECKLIST_p016_p015_review_fixes.md](CHECKLIST_p016_p015_review_fixes.md)
> **状态**: Step 5 完稿 + Step 6 Review 通过（§5）；Step 9 实施记录见 §6

---

## 1. 任务分解（T-1 ~ T-5）

### T-1 `Checks` 三态改造（D1）

文件：`scripts/external_benchmark/verify_p015.py`

| 改动点 | 内容 |
|--------|------|
| `Checks.__init__` | 不变（`self.rows: list[dict]`） |
| `Checks.add` | 保持签名 `(cid, case, desc, ok, detail)`，内部转 `status = "pass" if ok else "fail"` |
| **新增** `Checks.waive` | `(cid, case, desc, detail)` → `status="waiver"` |
| `Checks.finalize` | 汇总改为 `断言 {N}（失败 {M}）+ 豁免 {K}`；退出码仍 `M > 0 → 1` |
| `write_report` 渲染 | `pass→✅ PASS` / `fail→❌ FAIL` / `waiver→— 豁免（非断言）` |

### T-2 B5 豁免调用改用 `waive`（D1）

`verify_p015.py` 的 `entry_mode == "v3_only"` 分支：`checks.add(..., True, ...)` → `checks.waive(...)`。
保持不变式：`return pv_v3`（供跨 case I5 使用）。

### T-3 报告人工章节保护（D2）

`write_report` 首部增加标记检测 + 改名写入 + 保护提示；`MANUAL_MARKERS` 为模块级常量。

### T-4 `simulate_vbt_spec` fail-fast（D3）

`scripts/external_benchmark/_spec.py`：函数首行守卫 `if spec.cost_rate > 0: raise NotImplementedError(...)`；docstring 补边界说明与 U-P016-1 指针。

### T-5 文档回写（D4 + 本批发现）

| 文件 | 改动 |
|------|------|
| `CHECKLIST_p015` C-2 | 判据列写明「I2a = G1 组三行（verify 无独立命名行）」 |
| `CHECKLIST_p015` B-4 / §1 统计 | 断言口径更新为「28 断言 + 1 豁免」并注明 P-016 变更 |
| `APPENDIX_p015` §2 | 重生成读数表（豁免行改渲染）；§2 头注说明口径；§4 命令注「保护会改名」 |
| `RESEARCH_p015` U-P015-1 | 四元块补「rate>0 targetpercent 规格费用语义」前置（指向 U-P016-1） |
| `DESIGN_p015` §3.2 | I2a 处补「= G1.qty，verify 无独立命名行」 |
| `docs/PROGRESS.md` / `CHANGELOG.md` | P-016 登记与 Fixed 条目 |

## 2. 验证项（V1-V8）

| # | 验证项 | 判据 |
|----|--------|------|
| V1 | 三态渲染正确 | 全链运行时 stdout 出现 `WAIVER(非断言)` 恰 1 次；报告对应行渲染为 `— 豁免（非断言）` |
| V2 | 计数守恒（I2） | 汇总行 `断言 28（失败 0）+ 豁免 1` |
| V3 | 退出码语义不变（I3） | 全链 exit 0；B5 单跑 exit 1（I5 未齐） |
| V4 | 报告 §2 数值不变（I4） | 28 条断言逐行读数与改前完全一致（豁免行除外） |
| V5 | 人工章节保全（I5） | 对入库报告执行 `--report` 指向其副本 → 生成 `<stem>.generated.md`，原文件 SHA256 不变 |
| V6 | fail-fast 精确（I6） | `cost_rate=0.001` → `NotImplementedError`；B2（rate=0）全链仍绿 |
| V7 | 纪律面 | 不新增 `tests/`、不进 CI；主环境 `pytest` 仍 635 passed；`black --check scripts/` 0 变更 |
| V8 | 文档一致性 | C-2/I2a 映射、U-P015-1 前置、APPENDIX 口径三处互指成立 |

## 3. 风险与回退

| 风险 | 预案 |
|------|------|
| 报告 §2 重生成与入库版本数值漂移 | 逐行 diff 比对（V4）；任何数值差异即视为回归，回退重跑 |
| 保护改名导致复放命令「找不到报告」 | 提示文案显式给出新文件名；§4 命令同步注释 |
| 未来启用 rate>0 targetpercent 时被守卫拦住 | 守卫文案指向 U-P016-1，属预期行为 |

## 4. 排除的低效操作

- 不为 `verify_p015` 新建 pytest（P7 纪律：校准工具不进 `tests/`）；回归保护用 CLI 读数（V1-V6）
- 不重构 `Checks` 之外的代码（`verify_case` 主体零改动）
- 不改任何恒等式算式

## 5. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖（仅 stdlib `pathlib`/`hashlib` 如需）；vectorbt 版本不变
- [x] stdlib API 下限：仅用 `str.replace`/`pathlib.Path`，3.12 可用
- [x] API 签名可实现：`Checks.waive` 与 `add` 同形；`write_report` 增加内部分支不改调用方
- [x] 兼容性：`rows` dict 新增 `status` 键，唯一消费方 `write_report` 同步改；无外部消费者
- [x] 低效操作已排除（§4）
- [x] 回退点：单文件级 `git checkout` 即可回退；报告可从 case 目录重生成

**Step 6 Review 结论：通过**。

---

## 6. Step 9 实施记录（2026-11-10 回填）

### 6.1 F5 红→绿两读数（三组探针）

| 组 | 红（改前 @`90eb879`） | 绿（改后） |
|----|----------------------|------------|
| **A（F-R5-P015-2）** | `verify --case-dir B5` → `G2 [B5] PASS`；`共 5 项断言，失败 1 项`；exit 1 ⇒ 豁免被计为断言 | 同命令 → `G2 [B5] WAIVER(非断言)`；`共 4 项断言（失败 1 项）+ 豁免登记 1 项`；exit 1（I5 仍 FAIL，语义未变） |
| **B（F-R5-P015-3）** | `simulate_vbt_spec(cost_rate=0.001)` → `NO_GUARD: … pv_last = 9843199.479897`（静默产出） | 同调用 → `NotImplementedError: simulate_vbt_spec 的费用语义未定义（F-R5-P015-3 / U-P016-1）：case=B2 c…` |
| **C（F-S9-P016-1）** | 对入库报告副本执行 `--report` → 副本 L8/L47 变为 `（T-1.4 读数回填区…）`/`（T-4 回填区…）` ⇒ **人工段被覆盖** | 同命令 → `[保护] APPENDIX.md 含人工章节（§1/§3），改写 APPENDIX.generated.md`；`ORIG_UNCHANGED=True`；生成文件存在 |

### 6.2 实施期发现（2 项，均回写）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P016-1** | **P2** | 报告覆盖**在 P-015 会话内已真实发生**：`git show HEAD:docs/APPENDIX…` 证实入库版 §1/§3/§4 已是占位模板（black 后的最终全链复放 `--report` 指向本文件所致）。不是「潜在风险」而是既成数据丢失 | ① 生成器加人工章节保护（D2）；② **重新回填** §1（E1 现场重放 `audit_signatures.py`）/§3（M1-M5）/§4（实跑命令 + 保护说明）；③ 报告头与 §4 写入保护提示 |
| **F-S9-P016-2** | P3 | RULE-5 复审（P-015 §9.4）E1 九项未覆盖「交付物内容完整性」，故已发生的覆盖事件未被发现；复审的 D-1 项在 Step 10 时点（覆盖前）确实满足，属时点错位盲区 | 建议后续复审 E1 清单增一项「生成物占位残留扫描」（`grep 回填区`）+ 交付物哈希复核；本批不新增门禁 |

### 6.3 终态读数

| 项 | 读数 |
|----|------|
| 全链断言 | `共 28 项断言（失败 0 项）+ 豁免登记 1 项`，exit 0 |
| 报告 §2 一致性 | generated 与入库版 §2 **逐行完全一致**（`§2 完全一致: True`） |
| 报告保护（真实路径） | 复放写入 `docs/APPENDIX_p015_external_calibration.generated.md`，原文件未被覆盖；临时生成物已清理 |
| I4 逐行差异 | 29 行记录中仅 1 行差异（B5 豁免渲染），28 条断言读数逐行不变 |
| `pytest tests` | **635 passed, 152 warnings in 76.89s** |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` |
| 主环境 | pandas 2.2.3 / numba 0.65.1 不变；未新增 `tests/`、未改 CI |

### 6.4 排除的低效操作（实施确认）

- 未为校准脚本新增 pytest（P7 纪律）；回归保护由 CLI 读数（6.1 三组 + 6.3）承担
- 未改动任何恒等式算式与 case 数据（`_spec` 仅加守卫，`export/run` 零改动）
