# RESEARCH：P-022 Factor_DB 四项实现缺陷（U-P005-2）

> **批次**: P-022 · **T1**（`factor_library/database.py` 行为变更 + 4 组红绿测试；判档规则 2「契约/真值面」保守升级）
> **上游**: [PROGRESS §1.4](PROGRESS.md) U-P005-2；[RESEARCH_p005 P7](RESEARCH_p005_factor_db_alignment.md)（四项静态读码发现）
> **代码证据时点**: HEAD `cc3214c`（2026-11-12，工作区干净）
> **状态**: Step 1-2 完稿（含 Step 2 Review，§8）

---

## 1. 背景与目标

P-005 静态读码登记了 Factor_DB 四项实现缺陷（U-P005-2），当时零真实数据、风险未现实化，故未并入 P-005。本批独立立项，按 TDD 逐项修复。

**目标**：① 四项缺陷各有「红 → 绿」测试；② `add_factor` 的 `overwrite` 语义覆盖已持久化因子；③ 重开数据库后的写入路径不再崩溃；④ 删除/覆盖后不残留可被再次读取的旧格式文件。

**出界（不回答）**：DuckDB 迁移（U-P005-1）；`_save_metadata` 原子写/并发（U-P022-1）；`get_factor` 返回副本（U-P022-2）；非 `ImportError` 写入失败的清理（U-P022-3）；SQL 查询层与多源表。

---

## 2. 本仓事实（P1-P10）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **公开 API 8 成员**：`add_factor` / `get_factor` / `query` / `get_lineage` / `update_stats` / `list_factors` / `delete_factor` + `FactorMetadata` | E3 [database.py](../factor_library/database.py) L86 / L122 / L141 / L175 / L181 / L194 / L198 / L20 |
| **P2** | **单消费方且只读**：`batch_backtest/engine.py` 仅调用 `list_factors()`（L84）与 `get_factor()`（L117）；无 `add_factor` / `delete_factor` / `update_stats` 生产调用 | E1 `Select-String -Path batch_backtest/*.py`（L84/L117）；全仓 grep 仅定义与测试命中 |
| **P3** | **零真实数据**：`Test-Path factor_db` = **False**；无 CLI 命令、无 examples、无 web 导入 | E1 `Test-Path factor_db`；E3 ARCHITECTURE L131 状态「⚠️ 骨架」 |
| **P4** | **缺陷①静默覆盖**：`add_factor` 守卫只查内存 `_factors`（L101），而 `_load_existing_factors` 只填 `_metadata`（L83-L84）→ 重开后 `_factors` 为空，同名写入不报错并覆盖磁盘 | E2 探针：重开后 `persisted_in_memory_after_reload=False` → `add_factor` **不抛错** → 读回首格 `9.0`（原 `1.0`） |
| **P5** | **缺陷②删除复活**：`delete_factor` 只 `unlink` parquet（L206-L208），CSV 回退产物残留 → `get_factor` 从 CSV 重新加载已删除因子 | E2 探针：`csv_orphan_after_delete=True`；删除后 `metadata` 无 `g`，但 `get_factor("g")` 返回 **2 行**（复活） |
| **P6** | **缺陷③str-datetime 实为崩溃**：`_save_metadata` 写 `created_at.isoformat()`（L222-L223），重开后 `FactorMetadata(**meta_dict)` 得 `str` → 任何再次 `_save_metadata` 都 `AttributeError` | E2 探针：`created_at_type=str`；重开后 `add_factor` / `update_stats` **均崩溃**；`delete_factor` 在 ≥2 因子时崩溃（单因子删除因先移除该条而幸存） |
| **P7** | **缺陷④双份存储**：parquet 写入成功不清理同名旧 csv（L109-L112）；反向未覆盖（旧 parquet + 新 csv 时 parquet 仍被优先读） | E2 探针：`parquet_created=True` 且 `stale_csv_after_parquet_write=True` |
| **P8** | **现有测试不覆盖写后重开**：7 项测试中仅 `test_persistence` 重开，且只 `get_factor`（L102-L111），故 CI 636 全绿未暴露 P6 | E3 [tests/test_factor_database.py](../tests/test_factor_database.py) L29-L111 |
| **P9** | **`_load_existing_factors` 不读数据**：只解析 `metadata.json`，`_factors` 始终保持空字典直到首次 `get_factor` | E3 database.py L77-L84 |
| **P10** | **旁路观察（出界）**：`get_factor` 命中缓存时直接返回内部 DataFrame（L124-L125），调用方就地修改会污染缓存；`_save_metadata` 为非原子 `open(..., "w")` 写入 | E3 database.py L124-L125 / L235-L236；登记 U-P022-1/2 |

**严重度重估**：P6（写后重开崩溃）为**确定性运行时崩溃**（P1）；P4（静默覆盖）与 P5（删除复活）为数据完整性缺陷（P2）；P7 为潜在陈旧读取（P3）。台账 U-P005-2 原记 P3 系「零数据、风险未现实化」的排期优先级，本批建议按 **P1** 执行。

---

## 3. 外部锚点（F1-F4）

### 3.1 降级链（F3）

`WebFetch` 读取 Python 文档 2 页 + 复用 P-005 的 pandas 锚点 1 条。**降级 1 次**：`datetime.html` 页面被截断在 `date.fromisoformat` 节，未取到 `datetime.fromisoformat` 正文；按同页同族方法记录（`datetime.fromisoformat` 自 3.7 起可解析 `isoformat()` 输出），并在 F4 表标注该降级。PEP 484 与 pandas 锚点均命中正文，无降级。

### 3.2 锚点清单与验证表（F1/F2/F4）

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点 |
|----|------|-----------|--------|------|----------|
| **E1** | Python docs *datetime* — `date.fromisoformat` | Python 3.12 docs | 2026-11-12 | ✅ 正文（同页 `datetime.fromisoformat` 节被截断，降级记录） | ISO 8601 字符串可解析回日期对象；3.7 引入、3.11 扩展格式 |
| **E2** | PEP 484 *Type Hints* | Final（Created 2014，Python 3.5） | 2026-11-12 | ✅ 正文 | 「第三方包需自行实现运行时类型检查」——**类型注解不改变运行时值**；`created_at: datetime` 不会把 `str` 转成 `datetime` |
| **E3** | pandas *DataFrame.to_parquet* | v3.0.6 | 2026-11-11（沿用 P-005） | ✅ 正文 | 需 `pyarrow`/`fastparquet`；`engine` 默认 `auto` |
| **E4** | Python 标准库 `pathlib.Path.unlink` | 3.12 docs | 2026-11-12 | ⚠️ 页面截断（未含该方法节） | **未采用为判据**；本批删除仍用「`exists()` 判断 + `unlink()`」现有写法，不引入 `missing_ok` |

> **F4**：有效外部引用 **3 条**（E1-E3）≥3，已建表。**F1/F2** 均记录读取日与版本。**F5**：本批 Step 1 已取得 4 条红灯读数（§5 表 B-E），Step 9 以同探针转绿回填。

---

## 4. 方案矩阵（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 数据风险 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **M-A 四项最小修复（推荐）** | 逐项加守卫/清理/解析；4 组红绿测试 | 低（单文件 + 测试） | 高：消除崩溃与静默数据丢失 | 低 | 高（API 签名不变） | 低 | 1 批 | 语义清晰 |
| M-B 重写为 SQLite/单文件事务存储 | 换存储层 | 高 | 中 | 中 | **低**（迁移/格式变更） | 中 | 需迁移 | 长期待评估 |
| M-C 只修缺陷③崩溃 | 仅 datetime 解析 | 低 | 中：消除崩溃但保留数据丢失 | 低 | 高 | 中 | 1 批 | 缺陷残留 |
| M-D 四项 + 原子写/锁/返回副本 | 扩为存储可靠性重构 | 中高 | 高 | 中 | 中（`get_factor` 语义变） | 低 | 多批 | 过度设计 |

**判定**：
- **M-A 采用**：四项均由 P4-P7 探针实证，修复面限于 `database.py`；E2 保证「注解不改运行时值」，因此必须在加载处显式解析。
- **M-B 否决**：P2/P3 零数据、单消费方；与 U-P005-1 的 DuckDB 条件触发重复，且无基准。
- **M-C 否决**：只修崩溃会留下 P4/P5 两类数据完整性缺陷。
- **M-D 出界**：原子写/并发/返回副本登记 U-P022-1/2/3，不在本批。

---

## 5. 取证读数（Step 1）

| # | 命令/探针 | 读数 |
|---|-----------|------|
| A | `pytest -q`（基线，Agg） | **636 passed**（2026-11-12，Python312 3.12.10） |
| B | 缺陷①探针（临时目录） | 重开 `_factors` 空 → 同名 `add_factor` **不抛错** → 首格 `1.0 → 9.0` |
| C | 缺陷②探针 | `g.csv` 存在 → `delete_factor("g")` → `csv_orphan=True` → `get_factor("g")` 返回 2 行 |
| D | 缺陷③探针 | 重开后 `type(created_at)=str`；`add_factor`/`update_stats` **AttributeError**；双因子 `delete_factor` **AttributeError** |
| E | 缺陷④探针 | 预置 `h.csv` → `add_factor("h")` → `h.parquet` 与 `h.csv` **并存** |
| F | 数据面 | `Test-Path factor_db` = **False**；生产调用点仅 `get_factor`/`list_factors` |

---

## 6. 未决项登记（四元块）

- **U-P022-1 `_save_metadata` 原子写**
  - 判据：出现「写入中断导致 metadata.json 损坏」的可复现事故，或引入并发写
  - 触发条件：下一次存储可靠性批次
  - 当前倾向：不做（零数据、单进程）；届时用 `tmp + os.replace`
  - 证据等级：E3（database.py L235-L236 非原子写）

- **U-P022-2 `get_factor` 返回副本**
  - 判据：消费方出现就地修改返回值并影响后续读取
  - 触发条件：新增写消费方或缓存污染事故
  - 当前倾向：维持返回缓存引用（零拷贝，现有消费方只读）
  - 证据等级：E3（database.py L124-L125）

- **U-P022-3 非 `ImportError` 写入失败的清理**
  - 判据：parquet 引擎抛 `ArrowInvalid` 等非 `ImportError` 异常且留下半成品文件
  - 触发条件：出现真实引擎异常样本
  - 当前倾向：不扩大到 `except Exception`（避免吞错）；保留现状
  - 证据等级：E3（database.py L109-L112）

- **U-P022-4 `overwrite=True` 保留 `created_at`**
  - 判据：因子覆盖后需要审计原始创建时间（血缘/版本追溯）
  - 触发条件：出现按 `created_at` 排序或审计的需求
  - 当前倾向：维持「覆盖即重建元数据」（`created_at` 重置为当前时间）；届时合并旧元数据并只更新 `updated_at`
  - 证据等级：E2（Step 10 审计探针：覆盖前后 `created_at` 不相等）

---

## 7. 批次切分建议（供 DESIGN 采纳）

| 批次 | 内容 | 缺陷 | 行为 |
|------|------|------|------|
| **B1** | 重开加载时解析 `created_at`/`updated_at`；补「重开后再写」测试 | ③（P6，P1） | 崩溃 → 正常写入 |
| **B2** | `add_factor` 守卫覆盖 `_metadata` + 数据文件存在性 | ①（P4，P2） | 静默覆盖 → `ValueError`（`overwrite=True` 放行） |
| **B3** | `delete_factor` 同时删除 parquet 与 csv；补「删除后不可复活」测试 | ②（P5，P2） | 删除不彻底 → 彻底 |
| **B4** | 成功写入一种格式后清理另一种；补双向陈旧测试 | ④（P7，P3） | 双份存储 → 单一格式 |

> B1 为硬前置（否则 B2/B3/B4 的「重开后写入」测试无法通过）；B2-B4 相互独立，可串行提交。

---

## 8. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] **每条事实绑证据**：P1-P10 均带 E1 命令读数 / E2 探针输出 / E3 文件行锚（@`cc3214c`）
- [x] **外部引用验证**：E1/E2 读取正文；E3 沿用 P-005 记录（原读取日 2026-11-11）；E4 因页面截断**未采用为判据**并如实登记
- [x] **未验证项显式**：无；`datetime.fromisoformat` 的截断降级已在 §3.1/F4 标注
- [x] **反证检查**：主动核对「P6 是否只是注解问题」——探针证明重开后 `add_factor`/`update_stats` 实际抛 `AttributeError`，故升级为崩溃而非类型漂移；核对「P4 是否已有守卫」——守卫只查 `_factors`，重开后为空，实证不生效
- [x] **无归因扭曲**：未把「CI 636 全绿」误记为「四项不存在」；明确 P8 的覆盖缺口
- [x] **成本估计有据**：M-A 单文件 + 4 组测试；M-B 引 U-P005-1 前置
- [x] **F5**：Step 1 已取得 4 条红灯读数（§5 B-E），Step 9 同探针转绿
- [x] **档位理由**：T1——`factor_library/` 行为变更 + 4 组契约测试；不适用 T3 轻批

**Step 2 Review 结论：通过**（0 P1/P2；1 项严重度重估：缺陷③由「str-datetime 类型漂移」升级为「写后重开崩溃」P1；1 项范围收敛：E4 未采用）。可进入 Step 3 DESIGN。
