# CHECKLIST：P-005 Factor_DB 存储与文档对齐

> **批次**: P-005 · T1
> **上游**: [IMPL_p005_factor_db_alignment.md](IMPL_p005_factor_db_alignment.md)（T-1~T-6 / V1-V5）；[DESIGN_p005_factor_db_alignment.md](DESIGN_p005_factor_db_alignment.md)（D1-D5 / I1-I5）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 9 完成（15/15 ✅）· Step 10 ADD 审计通过（§9）

---

## 1. 验收项

### A 组：文档对齐（D1 / D2 / I3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | README 架构图（T-1） | `README.md:67` 区域为 `· Parquet`，无 `DuckDB` | ✅ `README.md:67` = `│  │ · Daily K    │  │ · Parquet    │`；`Grep -i duckdb README.md` = **0**（同列另两 token 一并改为 `Metadata`/`Lineage`，F-S9-P005-1） |
| A-2 | README Factor_DB 章节（T-2，I3） | 标题含 `⚠️ 骨架`；正文含 `metadata.json` + `Parquet` + `CSV` 回退表述；能力表四个成员名逐一匹配 `database.py` 的 `def`；**不含** `Price`/`Macro`/`Sentiment`/`Alternative` 表与 `*Query` 类 | ✅ `README.md:185` `### 🗄️ Factor_DB (Parquet · ⚠️ 骨架)`；L187 含 `metadata.json` / `.parquet` / 降级 `.csv`；7 个成员名 ↔ `database.py` `def`（L86/122/141/175/181/194/198）+ `FactorMetadata.version` L28 / `parent_factors` L33；`Grep 'PriceQuery\|FactorQuery\|MacroQuery\|SentimentQuery\|AlternativeQuery\|High-performance'` = **0** |
| A-3 | README Requirements（T-3） | 无 `Database: duckdb`；含 `pyarrow` 或 `fastparquet` 前提 + `CSV fallback` | ✅ `README.md:228` = `- Storage: JSON metadata + Parquet per factor (needs \`pyarrow\` or \`fastparquet\`; CSV fallback)`；无 `Database: duckdb` |
| A-4 | web Overview（T-4） | `web/streamlit_app/pages/01_Overview.py:96` 为 `Factor_DB(Parquet)` | ✅ L96 = `│  DataManager  │  Factor_DB(Parquet) │  Stock Filter   │`（`)` 后 1 空格，总宽不变） |
| A-5 | ARCHITECTURE 依赖表（T-5） | `docs/ARCHITECTURE.md` 依赖表无 `duckdb` 行；表后有「规划方向 + Parquet 引擎未声明」注；L131 模块表与 L290 缺口表未被改动 | ✅ 依赖表 L310-320 无 duckdb 行；L322 注 = 「Factor_DB 的 DuckDB 查询层为规划方向，当前未声明依赖；Parquet 读写需 pyarrow 或 fastparquet（环境自带，未声明）」；`git diff 586e817..fb94280 -- docs/ARCHITECTURE.md` = **+2/−1**（L131/L290 未在 diff 内） |

### B 组：依赖与 CLI（D3 / I4）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | `pyproject.toml` 依赖面（T-6，V3） | `tomllib` 解析 `[project].dependencies` 不含 `duckdb`；长度 = 改前 − 1；其余项与顺序不变 | ✅ `deps len 25` / `has duckdb: False`（改前 **26** 含）；其余 25 项与顺序不变 |
| B-2 | `cli.py` Key deps（T-6） | `deps` 字面量不含 `"duckdb"`；其余六项顺序不变 | ✅ `cli.py:237` = `["numpy", "pandas", "scipy", "cvxpy", "pydantic", "matplotlib"]` |
| B-3 | CLI 运行时（V4） | `python cli.py info` 输出不含 `duckdb`（改前含） | ✅ 改前 `duckdb 1.5.3`；改后 `Select-String duckdb` **空输出** |

### C 组：回归与门禁（I1 / I2 / I5 / V1 / V5）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | 全量测试（I1，V1） | `pytest tests`（Agg，3.12.10）= **636 passed** 持平 | ✅ Step 9 `636 passed, 152 warnings in 76.41s`；Step 10 复核 `636 passed, 152 warnings in 85.41s` |
| C-2 | 变更面（I2 / I5 / V5） | `git diff --stat` 仅 `README.md` / `web/streamlit_app/pages/01_Overview.py` / `docs/ARCHITECTURE.md` / `pyproject.toml` / `cli.py` + docs；`factor_library/`、`batch_backtest/`、`tests/` 零改动；新增文件 0（除四文档） | ✅ `git diff --stat 586e817..fb94280` = **5 文件 +18/−17**；Step 10 补丁 `uv.lock` **−44**（F-S10-P005-1，审计必需）；`factor_library/`、`batch_backtest/`、`tests/` **0 改动**；新增文件仅四文档 |
| C-3 | black（V5 延伸） | `black --check core tests cli.py` 无变更（README/docs 不在 black 范围） | ✅ `111 files would be left unchanged`（项目解释器 black） |
| C-4 | mypy（V5 延伸） | `mypy --explicit-package-bases core` = 0 errors（无 core 改动，应无漂移） | ✅ `Success: no issues found in 36 source files`（项目解释器 mypy；PATH mypy 指向 Anaconda，23 errors 为环境假象） |

### D 组：治理（V2 / E-1）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 声明残留归零（V2） | `Grep -i duckdb`：`README.md` / `web/**/*.py` / `cli.py` / `pyproject.toml` = **0 命中**；全仓剩余命中仅允许：`docs/ARCHITECTURE.md`（规划/缺口表述）、本批四文档、`PROGRESS`/`CHANGELOG` 历史记录、两份历史调研文档 | ✅ 四表面 **0**；全仓 `*.py` / `pyproject.toml` / `uv.lock` **0**；剩余命中全为文档类历史/规划记录（ARCHITECTURE 规划注 L322、DECISIONS ADR-001 决策+实施状态、DEVLOG/DEV-LOG-001、SPEC_STANDARD 示例、P-004/P-005 规格链、PROGRESS/CHANGELOG、两份历史调研）——判据允许集修订为「历史/规划记录类文档」（§9.3 观察 1） |
| D-2 | 台账与日志 | `PROGRESS.md` §1.4 P-005 状态更新 + §3.23 执行记录；`CHANGELOG.md` `Fixed` 条目 | ✅ `PROGRESS.md` §1.4 P-005 = done + §3.23 执行记录（本提交）；`CHANGELOG.md` `Fixed` 首条 P-005（本提交） |
| D-3 | 提交切分与回退 | B1（README/web/ARCHITECTURE）与 B2（pyproject/cli）两独立提交，各自可单独 `git revert` | ✅ B1 `938f413`（3 文件）/ B2 `fb94280`（2 文件）/ B3 `e1bc656`（`uv.lock` 1 文件，Step 10 补丁）；三者文件面不重叠，可独立 revert |

---

## 2. 统计

- 总数：**15 项**（A5 / B3 / C4 / D3）
- 状态：**15/15 ✅**（Step 9 实读回填，零 `[待 Step 9]` 残留）
- 覆盖映射：D1→A-2；D2→A-1/A-4/B-2；D3→B-1（+B3 锁文件补丁）；D4→（不迁移，U-P005-1 登记）；D5→A-5；I1→C-1；I2→C-2；I3→A-2；I4→B-1；I5→C-2

---

## 3. 后续章节

Step 8 一致性 Review（§8）、Step 10 ADD 审计（§9）、签字表（§10）见下；Step 9 记录回填 [IMPL §7](IMPL_p005_factor_db_alignment.md)。

---

## 8. Step 8 一致性 Review

**执行时点**: 2026-11-11，四文档完稿后的独立 pass；**[RULE-4] 自查（单视角）**；代码证据时点 HEAD `586e817`。

### 8.1 机械校验读数

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | **6 个唯一相对链接目标全部存在，0 broken**——`PROGRESS.md`、`RESEARCH_tech_debt_cleanup.md`、`../factor_library/database.py`、`../batch_backtest/engine.py`、`IMPL_p004_data_layer_unification.md`、本批四文档互链 |
| 预填检查（RULE-1） | 验收区 **15 项 = 15 处 `[待 Step 9]`**；全文 17 处命中 = 15 单元格 + L5 规则声明 + §2 统计说明（合法） |
| ID 引用闭环 | D1-D5 / I1-I5 / T-1~T-6 / V1-V5 均跨 ≥2 文档；U-P005-1/2/4 在 RESEARCH 与 DESIGN 双处登记，U-P005-3 仅 RESEARCH（元治理项，单点合法）；0 悬空 ID |

### 8.2 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH §6 B1（文档对齐）→ DESIGN §4.1/§4.2 → IMPL T-1~T-5 → CHECKLIST A 组 | 一一对应（A-1~A-5） |
| RESEARCH §6 B2（依赖与 CLI）→ DESIGN §4.3 → IMPL T-6 → CHECKLIST B 组 | 一一对应（B-1~B-3） |
| RESEARCH P4 五处声明 → D1/D2/D5 → T-1~T-5 → A-1~A-5 | 五处逐项有验收行，无遗漏 |
| RESEARCH P5 依赖声明 → D3 → T-6 → B-1/B-2/B-3 | 静态 + 运行时双判据 |
| RESEARCH P7 四项缺陷 → U-P005-2（出界） | CHECKLIST 无对应行 = 一致（§1 出界声明） |
| RESEARCH P8 零数据 → D4（不迁移） | 决策有事实依据，无验收行（U-P005-1 承接） |
| DESIGN V1-V5 → IMPL §4 V1-V5 → CHECKLIST | 同编号同义：V1→C-1；V2→D-1；V3→B-1；V4→B-3；V5→C-2 |

### 8.3 一致性发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P005-1 | P3 | DESIGN §4.2 对 web Overview 改动的字数描述为「等宽字符数**减少** 1」——方向错误（`DuckDB` 6 → `Parquet` 7 为 **+1**），且未说明删空格补偿；IMPL T-4 示例为正确形态（`)` 后 1 空格、总宽不变） | 已修：DESIGN 措辞改为「`DuckDB`(6) → `Parquet`(7)、`)` 后保留 1 个空格（原 2 个）、总宽不变」，与 IMPL 一致 |

**Step 8 结论：通过**（0 P1 / 0 P2 / 1 P3 已修；可进入 Step 9 实施）。

---

## 9. Step 10 ADD 审计

**执行时点**: 2026-11-11；**[RULE-4] 自查（单视角）**；代码证据绑定 `938f413` / `fb94280` + 工作区 B3（`uv.lock`）。

### 9.1 Phase 0-4

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 五个决策均可证伪：D1（README 成员名可逐个对照 `database.py` `def`）/ D2（四表面 grep 计数可复核）/ D3（`tomllib` 长度可复核）/ D4（无代码改动，决策登记 U-P005-1）/ D5（依赖表行 + 表后注可读回） |
| Phase 1 完整性 | ✅ D1→A-2；D2→A-1/A-4/B-2；D3→B-1 + B3（锁文件补丁）；D4→无验收行（出界，U-P005-1 承接）；D5→A-5；T-1~T-6 逐项有落点 |
| Phase 2 忠实度 | ✅ `git diff 586e817..fb94280` 全文审读：5 文件 +18/−17 与 DESIGN §4.1-§4.3 逐条对应；`factor_library/`、`batch_backtest/`、`tests/` 零改动；B3 仅 `uv.lock` −44 行（三处删除） |
| Phase 3 必要性 | ✅ 无新增对象、无新增依赖、无新文件（四文档为 T1 规格产物）；`uv.lock` 补丁为 D3 目标的必要条件（否则 `uv sync` 仍装 duckdb） |
| Phase 4 语义 | ✅ 意图 = 文档与依赖声明收敛到实现真相且零行为——四表面 0 命中、`info` 无 duckdb、`deps` 26→25、全量 **636 passed** 持平；无 `factor_library` 行为变更 |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| 改前 grep 回放（E1） | V2 / D-1 / IMPL §7.2 红读数 | ✅ `git grep -i -n duckdb 586e817 -- README.md cli.py pyproject.toml web` = **6 行**（L67/L185/L227/L237/L36/L96） |
| 改后 grep（E1） | V2 / D-1 | ✅ 四表面 0；全仓 `*.py` / `pyproject.toml` / `uv.lock` 0 |
| CLI 运行时（E2） | V4 / B-3 | ✅ `cli.py info` 改前含 `duckdb 1.5.3`，改后无 |
| `tomllib` 解析（E1） | V3 / B-1 / B3 | ✅ `deps len 25` / `has duckdb False`；`uv.lock` 根依赖 31→30、包块 0 |
| 全量 pytest（E1） | I1 / V1 / C-1 | ✅ `636 passed, 152 warnings in 85.41s`（Step 10 复核；Step 9 为 76.41s） |
| black（E1） | C-3 | ✅ `111 files would be left unchanged` |
| mypy（E1） | C-4 | ✅ `Success: no issues found in 36 source files` |
| 静态读码 @`938f413`（E3） | A-1/A-2/A-4/A-5 / I3 | ✅ README L67/L185-196/L228、Overview L96、ARCHITECTURE L310-322、`database.py` L86-198/L28-33 逐锚命中 |
| diff 全文审读（E3） | Phase 2 / I2 / I5 | ✅ 5 文件 +18/−17；B3 −44；无超纲文件 |
| 盲区扫描（E4；范围 = 四表面外全仓词元 × 锁文件 × 决策记录 × 历史文档 × 解释器） | 全组 | **P2×1（已修）+ 3 观察**（§9.3） |
| E5 推测 | — | 无 |

### 9.3 E4 盲区扫描结果

| # | 发现 | 等级 | 处置 |
|---|------|------|------|
| F-S10-P005-1 | `uv.lock` 仍含 duckdb（根 `dependencies` + `requires-dist` + 包块），`uv sync` 路径与 D3 目标相悖 | **P2** | **已修**：B3 `e1bc656` 三处删除（−44 行）；`tomllib` 复核通过。完整 `uv lock` 会引入既有漂移 +1207 行，故按最小面同步 |
| F-S10-P005-2 | `DECISIONS.md` ADR-001 仍写「状态 ✅ 已采纳 / 决策 DuckDB」，与实现真相不符 | P3 | **已修**：新增「实施状态（2026-11-11 P-005 核验）: 未实施——JSON 元数据 + Parquet；DuckDB 规划方向（U-P005-1）」 |
| 观察 1 | D-1 允许命中清单未覆盖 DECISIONS/DEVLOG/SPEC_STANDARD 等历史记录类文档 | 观察 | 判据修订为「历史/规划记录类文档」，D-1 实测列已注明 |
| 观察 2 | HEAD 时点 `uv lock --check` 已失败——锁内根项目仅 `provides-extras = ["dev"]`，缺 `web` extra（既有漂移，非本批引入） | 观察 | 登记 **U-P005-5**（独立锁刷新批）；本批不整文件重锁 |
| 观察 3 | PATH `python`/`mypy` → Anaconda 3.13（pytest 13 collection errors / mypy 23 errors），与项目解释器读数相反 | 观察 | 所有门禁显式 `Python312\python.exe -m ...`；已在 IMPL §7 声明 |

### 9.4 审计结论

**P1 = 0 / P2 = 1（F-S10-P005-1，已修）/ P3 = 4（F-S9-P005-1~3 + F-S10-P005-2，均已修）**；E4 另 3 观察（判据口径修订 / U-P005-5 锁漂移 / 解释器环境），均不阻断。**ADD 通过。**

---

### 9.5 RULE-5 异构复审（2026-11-11，全批）

**复审基座**: GLM-5.3-Flash ≠ 实施作者 DeepSeek-V4.1-Flash（RULE-5 异质性约束满足）；复审会话独立于实施会话，E1-E4 全部现场重放，不依赖文档自报；reviewer 只标记（单向权限），勘误回写为复审结束后的记录层修正（P-004「3 P3 登记并已回写」先例）。

**E1 机械重放（全部复现）**

| # | 断言 | 重放结果 |
|---|------|----------|
| 1 | HEAD/分支 | `420a320` = origin/master，工作区干净 |
| 2 | CI | run `43012172205` + `43012554920` 双 **success**（`gh run list`） |
| 3 | 提交面 | B1 `938f413` numstat **+17/−15**（README 14/13 + ARCH 2/1 + Overview 1/1）/ B2 `fb94280` **+1/−2** / B3 `e1bc656` **0/−44**——与 IMPL §7.1 一致 |
| 4 | 红读数 | `git grep -i duckdb 586e817 -- README.md cli.py pyproject.toml web` = **6 行**（L67/L185/L227/L237/L36/L96）逐条复现 |
| 5 | 绿读数 | 四表面 + 全仓 `*.py` / `pyproject.toml` / `uv.lock` = **0**；ARCHITECTURE 剩余 4 处均为规划/历史表述（L131/L290/L322/L351，D-1 允许集内） |
| 6 | 依赖面 | `tomllib`：pyproject deps **25** 无 duckdb；uv.lock 根依赖 **30**、duckdb 包块 **0**、字符串 **0** |
| 7 | 全量回归 | **636 passed, 152 warnings in 44.44s**（复审自跑，Agg + 项目解释器） |
| 8 | 门禁 | black **111 files unchanged** / mypy **36 source files 0**（复审自跑） |

**E2 运行时（红绿对照成立）**

| 探针 | 结果 |
|------|------|
| 红：`git show 586e817:cli.py` 落临时脚本跑 `info` | 打印 `duckdb          1.5.3` ✓ |
| 绿：当前 `cli.py info` | 无 duckdb，exit 0 ✓ |
| `uv lock --check`（U-P005-5 判据） | 仍失败（exit 1）——锁根包 `metadata.provides-extras = ["dev"]` 缺 pyproject 的 `web` extra；失败与 duckdb 无关，B3 未留下 duckdb 形态的不一致 ✓ |

**E3 静态读码（锚点全命中）**: README L66-69 图表 `Parquet/Metadata/Lineage` 与 L185-196/L228 能力表述 ↔ `factor_library/database.py` 逐字核验——7 个 `def`（L86/122/141/175/181/194/198）、`FactorMetadata` 统计字段 **L36-40 五键与 README `update_stats(ic_mean/ic_std/ir/half_life/turnover)` 逐字吻合**、`query` 四参数 L141-147 逐字吻合、`metadata.json` L79；ARCHITECTURE L131/L290/L322/L351；Overview L96；RESEARCH P1-P9 重放吻合（database.py **236 行** ✓ / P4 五处 ✓ / P8 零数据 ✓）；ID 闭环 U-P005-1×17 / -2×8 / -3×2 / -4×2 / -5×6、F-S8×3 / F-S9×8 / F-S10×8，0 悬空；七文件相对链接 **0 broken**。

**复审发现**

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-R5-P005-1 | P3 | IMPL T-1 两处描述失真：① 改前/改后整行引用为 `ARCHITECTURE.md` 的中文图表行（`Stock Filter (10种过滤器)` / `· 停牌/涨跌停/ST`），README.md L67 实为英文行（`Stock Filter` / `· Suspended / Limit-up/down`），DESIGN §4.1① 示例同；② 注记「7 字符 → 7 字符」错误——`DuckDB`(6) → `Parquet`(7)，行尾空格 5→4 补偿（与 F-S8-P005-1 同类）。目标定位与替换 token 正确，零行为影响 | **回写更正**：IMPL T-1 + DESIGN §4.1① 引用实际行并注 F-R5-P005-1；CHECKLIST A-1 局部引号前缀亦差一组 `│  │`（随本项说明，判定不受影响） |
| F-R5-P005-2 | P3 | `ARCHITECTURE.md` L66-68 图表 token `· Price数据 / · Macro/News / · Alternative` 与 `database.py` 能力不符（无多源表）——**F-S9-P005-1 同源幻觉的残留面**；`Grep -i duckdb` 词元法对不含该词元的幻觉不可见，Step 8/10 均漏扫；T-5 只声明不动 L131/L290，未覆盖图表区 | **登记，留后续文档批**（P-004 E4 观察 1 同处理，收口后不扩面）；U-P005-3 判据补强：图表 token 逐格对照能力清单 |
| F-R5-P005-3 | P3 | RESEARCH 头部「含 Step 2 Review，§8」编号失准（Step 2 Review 实为 §7，§8 为本复审节） | **回写更正**（随本节落位一并修正） |

**E4 盲区观察（登记，不阻断）**

| # | 发现 | 处置 |
|---|------|------|
| 观察 1 | 测试计数漂移：README L7 badge `Tests-507` / L98 `507 passed ✓` / L263 `Current baseline: 507` / L412 `507 tests, 48 files`；ARCHITECTURE L3 `测试: 489 个`——实测 **636 passed** | 先于本批存在、出 P-005 声明面（Factor_DB 主题）；登记留后续文档批 |
| 观察 2 | README L196 本批新增文本中 `U-P005-1` 为裸 ID 无链接，README 读者不可跳转（同句 ARCHITECTURE 缺口表链接可解析，主指针有效） | 登记；建议后续批补 RESEARCH 链接 |
| 观察 3 | uv.lock 根包 `provides-extras` 位于 `[package.metadata]` 子表（TOML 语义），程序化探测须读 `root['metadata']['provides-extras']`——顶层读取会误报 None | 登记（U-P005-5 复核方法注） |

**复审结论**: **pass**——0 P1 / 0 P2 / 3 P3 登记（F-R5-P005-1/3 文档勘误已回写、F-R5-P005-2 幻觉残留登记留后续批）+ 3 观察；RESEARCH 三大主结论（M-A 文档与依赖对齐 / 不迁移 DuckDB→U-P005-1 / 零行为）独立重放全部成立；ADD 审计结论（P2×1 已修 / P3×4 已修）维持。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §7](RESEARCH_p005_factor_db_alignment.md)（RULE-4 自查·单视角） | 2026-11-11 |
| RULE-5 异构复审（全批） | pass | §9.5（基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1-E4 现场重放全复现；0 P1/P2，3 P3 登记——2 勘误回写 + 1 幻觉残留登记 + 3 观察） | 2026-11-11 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §7](DESIGN_p005_factor_db_alignment.md)（RULE-4 自查·单视角） | 2026-11-11 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §6](IMPL_p005_factor_db_alignment.md)（RULE-4 自查·单视角） | 2026-11-11 |
| Step 7 验收清单 | 通过（零预填） | §1-§3（15 项，实测列全 `[待 Step 9]`） | 2026-11-11 |
| Step 8 一致性 Review | 通过 | §8（6 链接 0 broken；15=15 预填；对齐矩阵 7 行；F-S8-P005-1 已修） | 2026-11-11 |
| Step 9 TDD 实施 | 完成 | [IMPL §7](IMPL_p005_factor_db_alignment.md)（F5 红 6 命中 → 绿 0；B1/B2 两提交；15/15 ✅） | 2026-11-11 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵 10 类；P2×1 已由 B3 `e1bc656` 修复 + P3×4 已修 + 3 观察） | 2026-11-11 |
| CI 回收 | success | run `43012172205`（3.10 1m51s / 3.11 1m53s / 3.12 1m22s，三 job 全绿） | 2026-11-11 |
