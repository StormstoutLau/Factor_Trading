# RESEARCH：P-005 Factor_DB 存储与文档对齐（DuckDB 规划方向）

> **批次**: P-005 · **T1**（Layer-1：`cli.py` 运行时输出 + `pyproject.toml` 打包声明；判档规则 2「不可判则升级」）
> **上游**: [PROGRESS §1.4](PROGRESS.md) P-005（P3）；[RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md) TD-4
> **代码证据时点**: HEAD `586e817`（2026-11-11，工作区干净）
> **状态**: Step 1-2 完稿（含 Step 2 Review，§8）

---

## 1. 背景与目标

TD-4 原登记两件事：

1. **文档幻觉 H-1**：`ARCHITECTURE.md` 声称 Factor_DB 为 "DuckDB-based"——已于 **2026-10-23** 修正（:65/:132/:291/:317 四处，见 TD-4「修正状态」）。
2. **长期方向**：Factor_DB 存储由 JSON + Parquet 迁移到 DuckDB，获得查询/并发能力（TD-4 P3 第 9 项）。

**本批目标**：先判定「是否现在迁移」，再交付对齐缺口。判定依据 = 实现现状、真实数据面、消费方、外部能力事实（§2-§3），不以「文档写过 DuckDB」为理由逆向倒推。

---

## 2. 本仓事实（P1-P9）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **存储实现**：`FactorDatabase` 以 `metadata.json` 存元数据、`{name}.parquet` 存因子 DataFrame；`to_parquet` 抛 `ImportError` 时降级 `{name}.csv`；读取先 parquet 后 csv | E3 @`586e817` [database.py](../factor_library/database.py) L68-140（236 行 / 7,329 B） |
| **P2** | **公开能力 8 成员**：`add_factor` / `get_factor` / `query` / `get_lineage` / `update_stats` / `list_factors` / `delete_factor` + `FactorMetadata` 数据类；**无** SQL、无多源表、无 `*Query` 类、无并发写 | E3 同上 L20-236 |
| **P3** | **生产消费方仅 1 处**：`BatchBacktestEngine`（`factor_db` 可选参数；`list_factors` 与 `get_factor` 各 1 调用点）；主回测引擎（V1/V2/V3）、filter、factor、agents、web 页面均零导入 | E1 `Grep 'factor_library\|FactorDatabase' --glob '*.py'` = 6 文件（`__init__` / 定义 / `batch_backtest/engine.py` / 2 测试）；E3 [engine.py](../batch_backtest/engine.py) L19/L51/L84/L117 |
| **P4** | **文档声明残留（2026-10-23 修正未覆盖 README/web/cli）**：① `README.md:67` 架构图 `· DuckDB`；② `README.md:185-195` 整节标题 `### 🗄️ Factor_DB (DuckDB)` 并列出 **Price / Factor / Macro / Sentiment / Alternative 五类表与 `PriceQuery`…`AlternativeQuery` 五个查询类**——**代码中均不存在**；③ `README.md:227` Requirements `- Database: duckdb`；④ `web/streamlit_app/pages/01_Overview.py:96` `Factor_DB(DuckDB)`；⑤ `cli.py:237` `info` 命令 Key deps 列表含 `"duckdb"` | E3 @`586e817`：README L67/L185-195/L227；Overview L96；cli L237；对照 ARCHITECTURE L131/L290/L317 已如实（"JSON 元数据 + Parquet 文件存储（DuckDB 为规划方向）"） |
| **P5** | **依赖声明与使用不符**：`pyproject.toml:36` 在 `dependencies` 声明 `duckdb>=0.10.0`；全仓 `import duckdb` = **0**；当前解释器已装 duckdb `1.5.3`（pip 由该声明带入） | E1 `Grep 'duckdb' --glob '*.{py,toml,txt}'` = 2 处（pyproject + cli 字符串）；E1 `importlib.metadata.version('duckdb')` → `1.5.3` |
| **P6** | **测试面**：与 Factor_DB 直接相关 **13 passed**（`test_factor_database.py` 7 + `test_batch_backtest.py` 6）；全量基线 **636 passed**（Agg） | E1 `pytest tests/test_factor_database.py tests/test_batch_backtest.py -q` → `13 passed in 2.48s`；全量读数见 [IMPL_p004 §8.4](IMPL_p004_data_layer_unification.md) |
| **P7** | **实现缺陷 4 项（本批新发现，静态读码）**：① `add_factor` 的 `overwrite` 守卫只查内存 `self._factors`，而 `_load_existing_factors` 只加载 metadata → **已持久化因子可被静默覆盖**；② `delete_factor` 只 `unlink` parquet → csv 回退产物成为**孤儿**；③ `FactorMetadata(**meta_dict)` 把 `created_at` 从 JSON 读成 `str`（注解为 `datetime`），仅靠 `default=str` 掩盖；④ parquet 写入成功时不清理同名旧 csv → 双份存储 | E3 @`586e817` [database.py](../factor_library/database.py) L77-84 / L101-112 / L128-137 / L198-210 / L215-234 |
| **P8** | **真实数据面为零**：仓内无 `factor_db/` 目录（`Test-Path factor_db` = False）；无 CLI 命令、无 examples、无 web 导入；`ARCHITECTURE.md:131` 状态列标 **⚠️ 骨架** | E1 `Test-Path factor_db` → `False`；E3 ARCHITECTURE L131 |
| **P9** | **历史调研文档**：`docs/LEVEL1_DUCKDB_ANALYSIS.md`（17 KB）与 `docs/LOCAL_DATA_STORAGE_ANALYSIS.md`（17 KB）为 2026-05-30 的提案（"DuckDB 作为主存储"），**零实施**；ARCHITECTURE 附录已标「⚠️ 调研阶段」 | E3 ARCHITECTURE L350-351；E1 两文件存在且无对应代码 |

**事实小结**：Factor_DB 是**零真实数据、单消费方、骨架态**的模块；「现在迁移到 DuckDB」缺三类前提——数据规模（P8 零数据）、性能证据（无基准）、消费者需求（P3 单消费方且仅两个方法）。

---

## 3. 外部锚点（F1-F4）

### 3.1 降级链（F3）

直接 `WebFetch` 4 次全部命中（未使用 MCP 搜索镜像，无降级）。读取日均为 **2026-11-11**。

### 3.2 锚点清单与验证表（F1/F2/F4）

| ID | 来源 | 发布/版本 | 验证 | 命中要点 |
|----|------|-----------|------|----------|
| **E1** | DuckDB 官方文档 *Concurrency* | docs stable（读取日） | ✅ 正文 | 「一个进程可读写；多进程只能只读」；「DuckDB 为批量操作优化，**执行大量小事务不是设计目标**」 |
| **E2** | pandas `DataFrame.to_parquet` | pandas docs **v3.0.6**（读取日） | ✅ 正文 | 「需要 fastparquet 或 pyarrow」；`engine` 默认 `auto`（先 pyarrow 后 fastparquet） |
| **E3** | Python Packaging Guide *Writing your pyproject.toml* | 官方指南（读取日） | ✅ 正文 | `[project.optional-dependencies]` 定义 extra；「仅在特定功能需要的依赖放 optional」 |
| **E4** | DuckDB 官方文档 *Reading and Writing Parquet Files* | docs stable（读取日） | ✅ 正文 | 可直接 `SELECT * FROM 'x.parquet'` / `read_parquet([...])` / glob，**无需先导入数据库** |

### 3.3 锚点 → 本批决策映射

| 锚点 | 落入本批的判断 |
|------|----------------|
| E1 | Factor_DB 的写入模式是「逐因子 add/delete」（小事务），与 DuckDB 的批量 OLAP 定位**不匹配**；单写多读限制也会约束未来多进程批量回测 |
| E4 | **不迁移也能获得查询能力**：保留 Parquet，未来查询层可用 DuckDB 直接读 parquet（零导入）；迁移的收益率因此进一步下降 |
| E2 | Parquet 是「需要可选引擎」的格式——文档必须写明 `pyarrow`/`fastparquet` 前提，否则 CSV 降级是静默的 |
| E3 | 若保留 duckdb 依赖，应放 `optional-dependencies`；但当前**零代码使用**，故本批直接移除声明，留待查询层实施时再引入 |

---

## 4. 方案矩阵（7 维，按 SPEC_PROCESS §11.8）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **M-A 文档与依赖对齐（推荐）** | README/web/cli/pyproject 四处对齐到实现真相；迁移登记为未决项 | 低（5 文件，零逻辑） | 中：消除「文档承诺 ≠ 实现」的系统性幻觉；安装不再拉未用依赖 | 低 | 高 | 高 | 1 批 | 债务显性化 |
| M-B 全量 DuckDB 迁移 | `FactorDatabase` 改为 duckdb 后端（SQL 表 + 事务） | 高（重写 236 行 + 新增 schama/迁移脚本） | 低：无数据可迁、无查询需求 | 中（新增 DB 运维面） | 中（API 可保持） | 中 | — | 需先有数据 |
| M-C 接口抽象 + 可选后端 | 抽 `FactorStore` 协议，保 Parquet 默认 + DuckDB 可选实现 | 中（协议 + 2 实现 + 契约测试） | 低-中：无第二个真实需求方 | 中 | 高 | 高 | 多批 | 过度设计 |
| M-D 修复实现缺陷（P7 四项） | 修守卫/孤儿/类型/双份存储 | 中（行为变更 + 4 测试） | 中：消除静默覆盖风险 | 低 | 中（`add_factor` 语义变严） | 高 | 0 | 应独立立项 |

**判定**：

- **M-B 否决（本批）**：P8 零数据 + P3 单消费方 + 无基准，迁移无收益可度量；E1 的「小事务非设计目标」与当前逐因子写入模式冲突，迁移会引入新的写入约束（如批量缓冲），属**未定义需求驱动的重写**。
- **M-C 证伪**：仅一个真实实现、零第二个需求方时抽协议，是为假想需求造抽象；E4 已提供「不迁移也能查询」的路径，抽象可推迟到查询层真正实施时。
- **M-D 移出本批**：四项均为 `factor_library/` 行为缺陷，与「存储迁移/文档对齐」主题不同源；本批只登记（U-P005-2），避免把行为变更混入零逻辑批次。
- **M-A 为本批**：零逻辑改动、可逐条机械核验（P4 五处声明 + P5 一处依赖），且直接消除 TD-4 残余幻觉。

---

## 5. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| **U-P005-1** DuckDB 存储迁移 | Factor_DB 出现 ≥1 个真实数据集且查询/并发成为可度量瓶颈（有基准读数） | 出现首个生产因子库数据集，或单次 `query()` 内存过滤耗时 >1s（可机械测量） | 不迁移；届时优先 E4 路径（DuckDB 直读 Parquet，零导入） | E1/E4 |
| **U-P005-2** Factor_DB 实现缺陷（P7 四项） | 四项各有红→绿测试（静默覆盖 / csv 孤儿 / str-datetime / 双份存储） | 下一批次排期（P3；当前零数据，风险未现实化） | 独立立项修复，含 4 项 TDD | E3 |
| **U-P005-3** 文档幻觉的修复面完整性 | 任一「文档幻觉」修复必须同时扫描 README / web / cli / ARCHITECTURE 四类表面 | 每次文档修正批次 Step 8 校验时 | 把「四处表面扫描」写入本批 CHECKLIST 模板项，供后续批次复用 | E4（本批实证：2026-10-23 只修了 ARCHITECTURE） |
| **U-P005-4** Parquet 可选引擎声明 | `pyproject.toml` 是否显式声明 `pyarrow`（或 extra） | 下一次打包相关批次 | 不声明（当前靠环境自带；CSV 回退可用）；在 README 写明前提 | E2 |
| **U-P005-5** `uv.lock` 既有漂移 | `uv lock --check` 返回 0 | 下一次依赖维护批次 | 独立锁刷新（Step 10 实读：HEAD `fb94280` 时点已失败——锁内根项目仅 `provides-extras = ["dev"]`，缺 `web` extra；完整重建 +1207/−46 行，故本批只最小面移除 duckdb） | E1 |

---

## 6. 批次切分建议（供 DESIGN 采纳）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1** | 文档对齐：README 三处（架构图 / Factor_DB 章节 / Requirements）+ web Overview 一处 + ARCHITECTURE 依赖表一行 | 零逻辑 | `Grep` 后无「当前为 DuckDB」类声明；全量 636 passed 持平 |
| **B2** | 依赖与 CLI 对齐：`pyproject.toml` 移除 `duckdb>=0.10.0`；`cli.py` Key deps 去掉 `duckdb` | 运行时仅 `info` 输出变化 | `python cli.py info` 输出无 duckdb；`tomllib` 解析 dependencies 无 duckdb；全量持平 |

两批可合并为一次提交（同主题、零逻辑），但必须**逐文件可回退**；若 DESIGN 判定拆两提交，则按 B1→B2 顺序。

---

## 7. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] **每条事实绑证据**：P1-P9 均带 E1 命令读数或 E3 文件行锚（@`586e817`）；P4 五处声明逐行对照，非概括
- [x] **外部引用验证**：E1-E4 全部 `WebFetch` 正文命中并记录版本（pandas v3.0.6 / DuckDB stable / Packaging Guide）；无「搜索摘要即结论」
- [x] **未验证项显式**：本批无未验证外部引用；E1/E4 同一站点两页，均已读正文
- [x] **反证检查**：主动核对「README 的 DuckDB 描述是否可能对应其他模块」——全仓 `import duckdb` = 0，排除；`factor_library` 是唯一因子库模块
- [x] **无归因扭曲**：未把 `ARCHITECTURE.md` 已修正（2026-10-23）错记为「未修」；明确区分「已修 4 处」与「漏修 5 处」
- [x] **成本估计有据**：M-B「重写 236 行」以 P1 文件长度为据；M-A「5 文件」以 P4/P5 命中清单为据
- [x] **F5（先失败记录）**：Step 1 无先行失败记录 → **N/A**；Step 9 若有可执行判据，按红/绿两读数回填
- [x] **档位理由**：T1——`cli.py` 改变运行时输出、`pyproject.toml` 改变打包面；按判档规则 2「不可判则升级」取 T1

**Step 2 Review 结论：通过**（0 P1/P2；1 项措辞收敛：M-D 由「本批可顺带修」改为「独立立项」，避免范围蔓延）。可进入 Step 3 DESIGN。

---

## 8. RULE-5 异构复审

待用户指派后追加（先例：P-004 调研/设计各一轮）。
