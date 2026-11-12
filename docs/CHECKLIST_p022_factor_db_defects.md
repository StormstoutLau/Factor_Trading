# CHECKLIST：P-022 Factor_DB 四项缺陷修复

> **批次**: P-022 · T1
> **上游**: [IMPL_p022_factor_db_defects.md](IMPL_p022_factor_db_defects.md)（T-1~T-5 / V1-V6）；[DESIGN_p022_factor_db_defects.md](DESIGN_p022_factor_db_defects.md)（D1-D6 / I1-I6）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 10 完成（18/18 ✅）

---

## 1. 验收项

### A 组：写后重开（B1 / 缺陷③ / I1 / V1）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | 重开后新增因子 | 重开 `FactorDatabase` 后 `add_factor` 不抛 `AttributeError`，`list_factors()` 含新因子 | ✅ `test_reopen_then_add_factor` 绿：重开后新增 `f2`，`list_factors() == {f1, f2}` |
| A-2 | 重开后更新统计 | 重开后 `update_stats(name, ir=0.5)` 成功，`_metadata[name].ir == 0.5` | ✅ `test_reopen_then_update_stats` 绿：`ir == 0.5` |
| A-3 | 重开后双因子删除 | 重开后（≥2 因子）`delete_factor` 成功，剩余因子仍可 `list_factors()` | ✅ `test_reopen_then_delete_with_two_factors` 绿：删 `f1` 后 `list_factors() == ["f2"]` |
| A-4 | 时间字段类型 | 重载后 `type(created_at) is datetime` 且 `type(updated_at) is datetime`，`isoformat()` 可调用 | ✅ `test_reloaded_datetime_fields` 绿：两字段均 `datetime`，`isoformat()` 可调用 |

### B 组：覆盖守卫（B2 / 缺陷① / I2 / V2）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | 重开后同名拒写 | 重开后同名 `add_factor`（`overwrite=False`）抛 `ValueError` | ✅ `test_reopen_rejects_duplicate_without_overwrite` 绿（`match="已存在"`） |
| B-2 | 显式覆盖 | `overwrite=True` 成功，`get_factor` 读回新值 | ✅ `test_overwrite_persisted_factor` 绿：`assert_frame_equal` 通过（新值 = 原值 × 2） |
| B-3 | 孤儿文件拒写 | 仅存在 `{name}.csv`（无 metadata）时，`overwrite=False` 抛 `ValueError` | ✅ `test_orphan_csv_requires_overwrite` 绿（`match="已存在"`） |

### C 组：删除彻底（B3 / 缺陷② / I3 / V3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | CSV 回退因子删除 | 强制 CSV 回退创建因子 → `delete_factor` 后 `{name}.csv` 不存在 | ✅ `test_delete_removes_csv_fallback` 绿：删除后 csv 不存在 |
| C-2 | 删除后不复活 | 删除后 `get_factor(name)` 抛 `KeyError`；`{name}.parquet` 亦不存在 | ✅ `test_deleted_factor_cannot_resurrect` 绿：parquet 不存在 + `KeyError` |

### D 组：单一格式（B4 / 缺陷④ / I4 / V4）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | parquet 成功清理 csv | 预置 `{name}.csv` → `add_factor`（parquet 可用）→ csv 不存在，parquet 存在 | ✅ `test_parquet_write_removes_stale_csv` 绿：csv 删除、parquet 存在、读回等值（按 F-S9-P022-1 用 `overwrite=True`；按 F-S9-P022-3 以 monkeypatch 固定 parquet 成功分支，不依赖 CI 引擎） |
| D-2 | CSV 回退清理 parquet | 预置 `{name}.parquet` → 强制 `ImportError` 写 csv → parquet 不存在，`get_factor` 读回新值 | ✅ `test_csv_fallback_removes_stale_parquet` 绿：预置哨兵 parquet + 强制 `ImportError` → parquet 删除、csv 存在；重开读回 `updated`（`check_freq=False`） |

### E 组：兼容与回归（I5 / I6 / V5 / V6）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 公开签名不变 | 7 个公开方法与 `FactorMetadata` 字段签名与改前一致（`inspect.signature` 对照） | ✅ AST 对照（`cc3214c` ↔ HEAD）：7 个公开方法签名 **完全相等**；`FactorMetadata` 字段 **完全相等** |
| E-2 | 消费方零改动 | `git diff --name-only -- batch_backtest/engine.py` = 空 | ✅ `git diff --name-only cc3214c..HEAD -- batch_backtest pyproject.toml` = **空** |
| E-3 | 全量测试 | `pytest`（Agg，3.12.10）= **636 + 新增** 全绿，0 failed | ✅ **647 passed, 152 warnings in 44.46s**（636 + 11） |
| E-4 | 门禁不劣化 | black 无变更；mypy `core` 仍 36 files 0 errors | ✅ `black --check core tests cli.py` → **112 files unchanged**；mypy → `Success: no issues found in 36 source files` |

### F 组：治理（T-5）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| F-1 | 提交切分 | B1-B4 代码+测试逐批独立，B5 文档；单笔可 revert | ✅ B1 `9c50bcd` / B2 `ec21dc5` / B3 `9ffbfde` / B4 `1550e63` / B4b `59e1273`（black）/ B5 docs；代码提交仅 `database.py` + 测试文件 |
| F-2 | 台账与日志 | `PROGRESS.md` P-022 行 + §3.26；U-P005-2 结案；`CHANGELOG.md` `Fixed` 条目 | ✅ `PROGRESS.md` §1.4 P-022 行 + §3.26；U-P005-2 改「done（2026-11-12 由 P-022 承接）」；`CHANGELOG.md` `Fixed` 首条为 P-022 |
| F-3 | 未决项承接 | U-P022-1（原子写）/ U-P022-2（返回副本）/ U-P022-3（非 ImportError 清理）登记并同步台账 | ✅ [RESEARCH §6](RESEARCH_p022_factor_db_defects.md) 三条四元块；`PROGRESS.md` §1.4 新增 U-P022-1~4（pending） |

---

## 2. 统计

- 总数：**18 项**（A4 / B3 / C2 / D2 / E4 / F3）
- 状态：**18/18 ✅**（Step 9 实测回填，零预填残留）
- 覆盖映射：D1→A-1~A-4；D2→B-1~B-3；D3→C-1/C-2；D4→D-1/D-2；D5→E-1/E-2；D6→F-3；I1→A 组；I2→B 组；I3→C 组；I4→D 组；I5→E-1/E-2；I6→E-3/E-4；T-1→A 组；T-2→B 组；T-3→C 组；T-4→D 组；T-5→F 组

---

## 3. 后续章节

Step 8 一致性 Review（§8）、Step 9 实测回填（§1 验收表）、Step 10 ADD 审计（§9）、签字表（§10）在对应步骤完成后追加；Step 9 记录回填 [IMPL §7](IMPL_p022_factor_db_defects.md)。

---

## 8. Step 8 一致性 Review

**执行时点**: 2026-11-12，四文档完稿后独立 pass；**[RULE-4] 自查（单视角）**；代码证据时点 HEAD `cc3214c`。

### 8.1 机械校验读数

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | 四文档相对链接 **0 broken** |
| 预填检查（RULE-1） | 验收区 **18 项 = 18 处 `[待 Step 9]`**；全文 **20 处** = 18 单元格 + L5 规则声明 + §2 统计说明（合法） |
| ID 引用闭环 | D1-D6 / I1-I6 / T-1~T-5 / V1-V6 / U-P022-1~3 均跨 ≥2 文档；验收 ID A-F 组按 P-005/P-021 先例单文档承载；0 悬空 |

### 8.2 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH P6（写后重开崩溃）→ D1 → T-1 → A-1~A-4 | 一一对应，严重度 P1 已标注 |
| RESEARCH P4（静默覆盖）→ D2 → T-2 → B-1~B-3 | 守卫扩展为 metadata ∪ 内存 ∪ 文件，逐项有验收 |
| RESEARCH P5（删除复活）→ D3 → T-3 → C-1/C-2 | 「文件删除 + 不可复活」双判据 |
| RESEARCH P7（双份存储）→ D4 → T-4 → D-1/D-2 | 双向清理各有测试 |
| RESEARCH P10（原子写/返回副本）→ D6 → U-P022-1~3 → F-3 | 出界项无验收行 = 一致 |
| RESEARCH P1/P2/P8/P9 → D5 → E-1/E-2 | 签名不变 + 消费方零改动可机械核验 |
| DESIGN V1-V6 → IMPL §4 V1-V6 → CHECKLIST | 同编号同义：V1→A 组；V2→B 组；V3→C 组；V4→D 组；V5→E-1/E-2；V6→E-3/E-4 |

### 8.3 一致性发现

**0 项**（链接 / 预填 / ID / 编号映射均通过；无 P1/P2/P3）。

**Step 8 结论：通过**（可进入 Step 9 实施）。

---

## 9. Step 10 ADD 审计

**执行时点**: 2026-11-12；**[RULE-4] 自查（单视角）**；代码证据绑定 B1 `9c50bcd` / B2 `ec21dc5` / B3 `9ffbfde` / B4 `1550e63` / B4b `59e1273` + 工作区 docs 回写（B5）。

### 9.1 Phase 0-4

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 四个缺陷均有可重放判据：重开写入（E2）/ 同名拒写（E1 测试）/ 删除后 `KeyError`（E1）/ 文件存在性（E1） |
| Phase 1 完整性 | ✅ D1→A 组；D2→B 组；D3→C 组；D4→D 组；D5→E-1/E-2；D6→U-P022-1~3 + F-3；T-1~T-5 逐项有落点 |
| Phase 2 忠实度 | ✅ `git diff cc3214c..HEAD` 全文核：`database.py +35/−9`、测试 `+172/−3`；无其他文件；`batch_backtest`/`pyproject` 零改动 |
| Phase 3 必要性 | ✅ 无新增依赖；新增测试文件为缺陷回归的必要产物；`_build_metadata` 为私有辅助，未扩公开面 |
| Phase 4 语义 | ✅ 意图 = 四缺陷修复且零接口变更；**647 passed**（636+11）、签名 AST 全等、`batch_backtest` 零改动 |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| 逐批红跑（E1） | F5 / A-D 组 | ✅ B1 4 failed（3×AttributeError + 1×类型断言）/ B2 2 failed（DID NOT RAISE）/ B3 2 failed（文件存在 + 未抛 KeyError）/ B4 2 failed（双份并存） |
| 逐批绿跑（E1） | A-D 组 | ✅ 4 → 7 → 9 → 11 passed |
| 全量 pytest（E1） | E-3 / V6 | ✅ `647 passed, 152 warnings in 44.46s` |
| black / mypy（E1） | E-4 / V6 | ✅ `112 files unchanged` / `36 source files 0` |
| AST 签名对照（E3） | E-1 / V5 | ✅ 7 个公开方法签名与 `FactorMetadata` 字段完全相等 |
| diff 全文审读（E3） | Phase 2 / V5 | ✅ 2 文件 `+207/−12`；无超纲文件 |
| 运行时探针（E2） | A-4 / B-3 / C-2 / D-2 | ✅ 重载 datetime / 孤儿拒写 / 删除不复活 / 反向清理 + 重开读回 |
| 盲区扫描（E4；范围 = `database.py` 全部写路径 × metadata.json 生命周期 × 消费方 × 测试覆盖 × 跨版本） | 全组 | **1 观察升级为 U-P022-4**（§9.3） |
| E5 推测 | — | 无 |

### 9.3 E4 盲区扫描结果

| # | 发现 | 等级 | 处置 |
|---|------|------|------|
| F-S10-P022-1 | `overwrite=True` 会重建 `FactorMetadata`，`created_at` 被重置为当前时间（探针：覆盖前后 `created_at` 相差 8ms）——血缘/审计场景会丢失原始创建时间 | P3 | **登记 U-P022-4**（出界：本批目标是四项缺陷；覆盖语义变更另立） |
| 观察 1 | `get_factor` 命中缓存时返回内部 DataFrame 引用（调用方就地修改会污染缓存） | 观察 | 已在 RESEARCH P10 登记 U-P022-2 |
| 观察 2 | `_save_metadata` 为非原子 `open(..., "w")` 写入，进程中断可能留下半截 JSON | 观察 | 已在 RESEARCH P10 登记 U-P022-1 |
| 观察 3 | `delete_factor` 对不存在因子保持静默 no-op（未改为 `KeyError`），与改前语义一致 | 观察 | 不改（避免超纲行为变更）；测试未覆盖该路径 |
| 环境 | PATH `python`/`mypy` = Anaconda 3.13 | 观察 | 门禁全部显式 `Python312` |

### 9.4 审计结论

**P1 = 0 / P2 = 0 / P3 = 1（F-S9-P022-1 已记录）/ E4 1 观察升级 U-P022-4 + 3 观察（均不阻断）**；V1-V6 全过、18/18 ✅。**ADD 通过。**

> **RULE-5 状态**：本批**未执行**异构复审——本会话即实施作者（DeepSeek-V4.1-Flash），不满足 RULE-5 异质性约束；需另起异构基座会话对 P-022 全批复审。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §8](RESEARCH_p022_factor_db_defects.md)（RULE-4 自查·单视角；0 P1/P2；缺陷③升级 P1） | 2026-11-12 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §7](DESIGN_p022_factor_db_defects.md)（RULE-4 自查·单视角） | 2026-11-12 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §6](IMPL_p022_factor_db_defects.md)（RULE-4 自查·单视角） | 2026-11-12 |
| Step 7 验收清单 | 通过（零预填） | §1-§3（18 项，实测列全 `[待 Step 9]`） | 2026-11-12 |
| Step 8 一致性 Review | 通过 | §8（20 处 `[待 Step 9]` = 18 格 + 2 合法；链接 0 broken；ID 闭环；对齐矩阵 7 行；0 发现） | 2026-11-12 |
| Step 9 TDD 实施 | 完成 | [IMPL §7](IMPL_p022_factor_db_defects.md)（四批红 4/2/2/2 → 绿 11；B1-B4 + B4b + B5b；18/18 ✅） | 2026-11-12 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵 9 类；P3×1 已记录 + U-P022-4 + 3 观察） | 2026-11-12 |
| RULE-5 异构复审 | **pass** | 异构基座 GLM-5.3-Flash 独立会话全批复审（E1-E4 重放 + 1 P3 回写）；见 §11 | 2026-11-12 |
| CI 回收 | success | 首跑 `43175692308` **failure**（D-1/D-2 环境依赖 parquet，2 failed × 3 版本）→ B5b `e03c650` 修复；第二跑 `43176076114` 三 job **success**（3.10 1m52s / 3.11 1m32s / 3.12 1m36s）；回填提交 `a29b498` 触发 run `43176435214` 三 job **success** 2m20s（F-R5-P022-1 补登） | 2026-11-12 |

---

## 11. RULE-5 异构复审（2026-11-12）

> **复审基座**：GLM-5.3-Flash（本节作者）≠ P-022 实施作者 DeepSeek-V4.1-Flash——满足 RULE-5 异质性约束。复审时点 HEAD `a29b498`（= origin/master，工作区干净）；复审方法与取证矩阵依据 SPEC_PROCESS v1.7.2 RULE-6（E1 可重放命令 / E2 运行时 / E3 静态读码绑 commit / E4 盲区扫描 / E5 推测不用于结论）。

### 11.1 E1 机械重放（全部复现）

| # | 断言 | 重放结果 |
|---|------|----------|
| 1 | HEAD/分支 | `a29b498` = origin/master，工作区干净（复审自证） |
| 2 | CI 三 run | 首跑 `43175692308` **failure** 1m29s（B5 触发）/ 第二跑 `43176076114` **success** 1m55s（B5b 触发；job 明细 **3.10 1m52s / 3.11 1m32s / 3.12 1m36s** 与 §10 逐字一致，`gh run view`）/ 回填 `43176435214` **success** 2m20s（B5c 触发） |
| 3 | 提交面 | 8 笔 numstat 逐笔与 IMPL §7.1 一致：B1 `9c50bcd` **+15/−1 +78** / B2 `ec21dc5` **+10/−3 +30** / B3 `9ffbfde` **+4/−4 +30** / B4 `1550e63` **+6/−1 +34** / B4b `59e1273` **0/−3** / B5 `40e8077` 6 文件 **+679/−1** / B5b `e03c650` 4 文件 **+12/−8** / B5c `a29b498` 3 文件 **+5/−3** |
| 4 | 全量回归 | **647 passed, 152 warnings in 65.72s**（复审自跑，Agg + 项目解释器；文档 44.46s——passed 数一致，时长波动） |
| 5 | 门禁 | black **112 files would be left unchanged** / mypy **`Success: no issues found in 36 source files`**（复审自跑） |
| 6 | AST 签名对照（独立脚本） | `cc3214c` 旧版 vs HEAD 新版：7 个公开方法签名 **全等** + `FactorMetadata` 字段 **全等**（`ast.unparse` 参数串比对） |
| 7 | 四缺陷探针（独立脚本，隔离临时目录） | **6/6 OK**：重开 datetime 还原 + 重开 add/update/delete 不崩 / 守卫 ValueError + overwrite=True 读回新值 / 孤儿 csv 拦截 / 删除双格式 + 不可复活 / parquet 成功清旧 csv / CSV 回退清旧 parquet + 重开读回 |
| 8 | 保护面 | `git diff --name-only cc3214c..HEAD -- batch_backtest pyproject.toml` = **空** |

### 11.2 E2 运行时（合成红态重放闭合）

| 探针 | 结果 |
|------|------|
| 红：`git checkout cc3214c -- factor_library/database.py` + HEAD 测试 `tests/test_p022_factor_db_defects.py` | **10 failed, 1 passed in 0.76s**——TestReopenWrites **4** failed（3×`AttributeError: 'str' object has no attribute 'isoformat'` + 1×isinstance 断言）/ TestOverwriteGuard **2** failed（DID NOT RAISE）+ 1 passed（overwrite=True 读写项，旧代码本就支持）/ TestDeleteBothFormats **2** failed / TestSingleFormat **2** failed——与 IMPL §7.2 逐批红态 **4/2/2/2** 同构 ✓ |
| 绿控制组：`git checkout HEAD -- factor_library/database.py` 后重跑 | **11 passed in 0.67s**，工作区恢复干净 ✓ |

### 11.3 E3 静态读码（锚点全命中）

`factor_library/database.py` @`a29b498`：L86 `_build_metadata` / L93 `datetime.fromisoformat` / L96 ISO 错误消息（缺陷③）/ L118 四路并集守卫 + L124 `ValueError`（缺陷①）/ L132 `except ImportError` + L135/L138 双向清理（缺陷④）/ L232+L234 删除双格式循环（缺陷②）——行号逐一命中；四文档相对链接 **14 处 0 broken**；ID 闭环 U-P022-1~4（RESEARCH↔PROGRESS）/ F-S9-P022-1~3（IMPL）/ F-S10-P022-1（CHECKLIST）/ T-1~T-5 / D1-D6 / I1-I6 / V1-V6（IMPL 以 `D1-D6`/`I1-I6` 区间形式引用，合法覆盖）；上游链形 RESEARCH←DESIGN←IMPL←CHECKLIST 与 P-021 先例一致。

### 11.4 复审发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-R5-P022-1 | P3 | CI 回收链不完整：回填提交 `a29b498`（B5c）触发的 run `43176435214`（三 job success 2m20s）未登记于 CHECKLIST §10 / PROGRESS §3.26（均止于 `43176076114`）——与 F-R5-P021-4 同构 | **回写补登**（CHECKLIST §10 CI 回收行 + PROGRESS §3.26，随本节落位一并修正） |

### 11.5 E4 盲区观察（登记，不阻断）

| # | 发现 | 处置 |
|---|------|------|
| 观察 1 | CHECKLIST §9.3 未引 F-S9-P022-2 ID（单因子 delete 因先移除该条而幸存的观察）——实质由 IMPL §7.5 权威登记覆盖，非追溯断裂 | 登记 |
| 观察 2 | §8「全文 20 处 `[待 Step 9]`」为 Step 8 时点快照（18 格 + 2 合法）；Step 9 回填后实测列转 ✅，终态描述性引用 4 处（L5 规则行 / §8 统计行自身 / 签字表 Step 7/8 两处历史描述）——时点陈述非当前态，非缺陷 | 登记 |
| 观察 3 | PROGRESS §1.4「647 passed…44.46s」与复审自跑 65.72s——passed 数一致，时长波动非缺陷 | 登记 |
| 观察 4（环境） | `%TEMP%` 残留实施期探针 14 个（`p022_*`）+ 上批复审脚本（`r5_p021_*` 5 个） | 复审收尾统一清理（本节落位时执行） |

### 11.6 复审结论

**pass**——0 P1 / 0 P2 / **1 P3 登记（F-R5-P022-1，记录层回写）** + 4 观察；P-022 四项修复主结论（加载期 datetime 还原 / 四路守卫 / 双格式删除 / 写后单一格式）独立重放全部成立；ADD 审计结论（P3×1 已记录 + U-P022-4 + 3 观察）维持。复审记录提交与 CI run 于回填提交补记。
