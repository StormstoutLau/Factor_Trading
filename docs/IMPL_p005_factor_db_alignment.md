# IMPL：P-005 Factor_DB 存储与文档对齐（B1 文档 / B2 依赖与 CLI）

> **批次**: P-005 · **T1**（`README.md` / `web/streamlit_app/pages/01_Overview.py` / `docs/ARCHITECTURE.md` / `pyproject.toml` / `cli.py`）
> **上游**: [DESIGN_p005_factor_db_alignment.md](DESIGN_p005_factor_db_alignment.md)（D1-D5 / I1-I5 / §4 实现规格）
> **下游**: CHECKLIST_p005_factor_db_alignment
> **代码证据时点**: HEAD `586e817`（2026-11-11，工作区干净）
> **状态**: Step 5 完稿 + Step 6 Review 通过（§6）；Step 9 实施记录见 §7（含 Step 10 审计补丁 B3）

---

## 1. 外部锚点（F1-F4，沿用 RESEARCH §3）

本批不新增外部检索；四条锚点均已在 Step 1 用 `WebFetch` 读正文（读取日 **2026-11-11**，无降级）。

| ID | 来源 | 版本 | 用途 |
|----|------|------|------|
| E1 | DuckDB *Concurrency* | docs stable | 支撑 D4「不迁移」：小事务非设计目标、单写多读 |
| E2 | pandas `DataFrame.to_parquet` | v3.0.6 | 支撑 README 写明 Parquet 引擎前提（`pyarrow`/`fastparquet`） |
| E3 | Python Packaging Guide *pyproject.toml* | 官方指南 | 支撑 D3：`optional-dependencies` 仅用于「特定功能需要」的依赖；当前无此功能 |
| E4 | DuckDB *Parquet Files* | docs stable | 支撑 U-P005-1 的优先路径（直读 Parquet，零导入） |

> F3 降级链：无（直接 WebFetch 4/4 命中）。F4 引用验证表见 [RESEARCH §3.2](RESEARCH_p005_factor_db_alignment.md)。

---

## 2. 任务分解（T-1 ~ T-6）

### T-1 README 架构图 token（DESIGN §4.1①）

文件：`README.md` L67

| 改前 | 改后 |
|------|------|
| `│  │  │ · Daily K    │  │ · DuckDB     │  │  · Suspended / Limit-up/down      ││ │` | `│  │  │ · Daily K    │  │ · Parquet    │  │  · Suspended / Limit-up/down      ││ │` |

> 仅替换 `DuckDB`(6 字符) → `Parquet`(7 字符)，行尾空格 5 → 4 补偿，总宽不变。
>
> **F-R5-P005-1（RULE-5 复审更正，P3）**：本行引用初稿误写为 `docs/ARCHITECTURE.md` 的中文图表行（`Stock Filter (10种过滤器)` / `· 停牌/涨跌停/ST`）且注记误写「7 字符 → 7 字符」；README L67 实际为上述英文行，`DuckDB`(6) → `Parquet`(7)。目标定位与替换 token 正确，仅引用文本失真（E1 红读数 `586e817:README.md:67` 为证）。

### T-2 README Factor_DB 章节整节替换（DESIGN §4.1②）

文件：`README.md` L185-195（`### 🗄️ Factor_DB (DuckDB)` 起至表后空行）

替换为 DESIGN §4.1② 的 10 行内容：标题带 `⚠️ 骨架`、存储格式、四行能力表、`能力边界` 段、DuckDB 规划指向。

删除的虚构内容（逐项）：`Price / Factor / Macro / Sentiment / Alternative` 五类表、`PriceQuery / FactorQuery / MacroQuery / SentimentQuery / AlternativeQuery` 五个类、"High-performance" 定性。

### T-3 README Requirements（DESIGN §4.1③）

文件：`README.md` L227

| 改前 | 改后 |
|------|------|
| `- Database: duckdb` | `- Storage: JSON metadata + Parquet per factor (needs \`pyarrow\` or \`fastparquet\`; CSV fallback)` |

### T-4 web Overview token（DESIGN §4.2）

文件：`web/streamlit_app/pages/01_Overview.py` L96

| 改前 | 改后 |
|------|------|
| `│  DataManager  │  Factor_DB(DuckDB)  │  Stock Filter   │` | `│  DataManager  │  Factor_DB(Parquet) │  Stock Filter   │` |

> `DuckDB`(6) → `Parquet`(7)，为保持 ASCII 架构框视觉对齐，`)` 前补 1 空格（`(Parquet) `），总宽 +1；该行是字符串字面量，不影响任何渲染逻辑。

### T-5 ARCHITECTURE 依赖表（DESIGN §4.2）

文件：`docs/ARCHITECTURE.md`

| 位置 | 改动 |
|------|------|
| L317 | 删除 `| duckdb | >=0.10.0 | 规划中的 Factor_DB 查询层（当前代码未使用） |` |
| 表后 | 追加注：`> Factor_DB 的 DuckDB 查询层为规划方向，当前未声明依赖；Parquet 读写需 pyarrow 或 fastparquet（环境自带，未声明）。` |

> L131（模块表）与 L290（缺口表）已如实，**不动**。

### T-6 依赖与 CLI（DESIGN §4.3）

| 文件 | 位置 | 改动 |
|------|------|------|
| `pyproject.toml` | L36 | 删除 `    "duckdb>=0.10.0",` 整行 |
| `cli.py` | L237 | `deps = ["numpy", "pandas", "scipy", "cvxpy", "duckdb", "pydantic", "matplotlib"]` → `deps = ["numpy", "pandas", "scipy", "cvxpy", "pydantic", "matplotlib"]` |

---

## 3. 实施顺序与提交切分

| 提交 | 内容 | 测试面 |
|------|------|--------|
| **B1** | T-1~T-5（README / web / ARCHITECTURE） | 不改测试 → 636 持平 |
| **B2** | T-6（pyproject / cli） | 不改测试 → 636 持平 |

> 两批文件面不重叠，各自可单独 `git revert`；B2 必须在 B1 之后（README 的 Requirements 已去掉 duckdb，B2 才移除声明，避免中间态「文档说无依赖、打包仍声明」）。

---

## 4. 验证项（V1-V5，与 DESIGN §5 同编号同义）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 全量测试 | 636 passed（Agg，3.12.10） |
| V2 | 声明残留归零 | `Grep -i duckdb` @ `README.md` / `web/**/*.py` / `cli.py` / `pyproject.toml` = 0 |
| V3 | 依赖面 | `tomllib` 解析 `[project].dependencies` 不含 `duckdb`；长度 = 改前 − 1 |
| V4 | CLI 运行时 | `python cli.py info` 无 `duckdb` 行 |
| V5 | 变更面 | 5 文件；`factor_library/`、`batch_backtest/`、`tests/` 零改动 |

---

## 5. 排除的低效操作

- 不新建文档模板、不写迁移脚本、不建 `factor_db/` 样例数据；
- 不引入 `factor-db` extra（零需求方）；
- 不修 `factor_library` 四项缺陷（U-P005-2）；
- 不改 `ARCHITECTURE` L131/L290（已如实）；
- 不动 `LEVEL1_DUCKDB_ANALYSIS.md` / `LOCAL_DATA_STORAGE_ANALYSIS.md`（历史调研，附录已标状态）。

---

## 6. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖；仅删除 `duckdb>=0.10.0` 一行
- [x] stdlib API 下限：验证用 `tomllib`（3.11+）；本项目运行时 3.12.10，CI 矩阵含 3.10——**探针只在本地执行，不写入代码/测试**，不构成 3.10 兼容风险
- [x] API 签名可实现：无新增接口；`cli.py` 仅改列表字面量
- [x] 行锚可核：README L67/L185-195/L227、Overview L96、ARCHITECTURE L317、pyproject L36、cli L237 均已 `Read` 确认
- [x] 锚点可解析：E1-E4 均为 Step 1 正文验证（`WebFetch` 4/4）
- [x] 低效操作已排除（§5）；回退点按 B1/B2 两提交切分
- [x] F5 声明：Step 5 无先行失败记录 → **N/A**；Step 9 以「声明残留 6 命中 → 0 命中」与「`info` 含/不含 duckdb」两组红/绿读数回填

**Step 6 Review 结论：通过**。可进入 Step 7 CHECKLIST。

---

## 7. Step 9 实施记录

> [RULE-1] 零预填：本节读数均为 Step 9/10 执行后实读（2026-11-11，项目解释器 `Python312` 3.12.10，`MPLBACKEND=Agg`）。**解释器约束**：PATH 上的 `python`/`mypy` 指向 Anaconda 3.13（缺 `cvxpy`，pytest collection 13 errors；mypy 23 errors），所有门禁一律显式 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe -m ...`。

### 7.1 基线与提交链

| 项 | 读数 |
|----|------|
| 基线 | HEAD `586e817` 干净（仅四文档未跟踪）；四表面 `Grep -i duckdb` = **6 命中** |
| **B1** | `938f413`（3 文件 +17/−15）：`README.md` / `web/streamlit_app/pages/01_Overview.py` / `docs/ARCHITECTURE.md` |
| **B2** | `fb94280`（2 文件 +1/−2）：`pyproject.toml` / `cli.py` |
| **B3**（Step 10 审计补丁） | `e1bc656`（1 文件 −44）：`uv.lock`（duckdb 包块 + `dependencies` 引用 + `requires-dist` 引用），见 §7.6 |

### 7.2 F5 先失败记录（红 / 绿两读数块）

**红（@`586e817`，可重放：`git grep -i -n duckdb 586e817 -- README.md cli.py pyproject.toml web`）**

| # | 表面 | 命中 |
|---|------|------|
| 1 | `README.md:67` | `│ · DuckDB     │`（架构图） |
| 2 | `README.md:185` | `### 🗄️ Factor_DB (DuckDB)` |
| 3 | `README.md:227` | `- Database: duckdb` |
| 4 | `cli.py:237` | `deps = [... "duckdb" ...]` |
| 5 | `pyproject.toml:36` | `"duckdb>=0.10.0",` |
| 6 | `web/.../01_Overview.py:96` | `Factor_DB(DuckDB)` |

运行时：`python cli.py info` 输出含 `duckdb 1.5.3`；`tomllib` 解析 `[project].dependencies` 长度 **26**、含 duckdb。

**绿（@`fb94280` + B3）**

- 四表面 `Grep -i duckdb` = **0 命中**；全仓 `*.py` / `pyproject.toml` = **0**
- `python cli.py info` = **无 duckdb 行**
- `tomllib`：`deps len 25` / `has duckdb: False`
- `uv.lock`：包块 0、根依赖 31 → 30、`requires-dist` 0 引用

### 7.3 验证项（V1-V5 实读）

| # | 验证项 | 实读 |
|---|--------|------|
| V1 | 全量测试 | **636 passed, 152 warnings in 76.41s**（Step 9）；Step 10 复核 **636 passed in 85.41s** |
| V2 | 声明残留归零 | 四表面 **0**；全仓 `*.py` **0** |
| V3 | 依赖面 | `deps len 25` / `has duckdb: False`（改前 26） |
| V4 | CLI 运行时 | `info` 无 duckdb |
| V5 | 变更面 | `git diff --stat 586e817..fb94280` = **5 文件 +18/−17**；`factor_library/`、`batch_backtest/`、`tests/` 零改动；B3 另 +1 文件（`uv.lock`） |

### 7.4 探针读数（I3 / A-2 / A-5）

| 探针 | 读数 |
|------|------|
| README 成员名 ↔ 代码 | 7 个成员名全部有对应 `def`：`add_factor` L86 / `get_factor` L122 / `query` L141 / `get_lineage` L175 / `update_stats` L181 / `list_factors` L194 / `delete_factor` L198；`FactorMetadata.version` L28 / `parent_factors` L33 |
| 虚构能力归零 | `Grep 'PriceQuery|FactorQuery|MacroQuery|SentimentQuery|AlternativeQuery|High-performance' README.md` = **0** |
| ARCHITECTURE 注位置 | L322（plotly 行之后、§9.2 之前）；依赖表无 duckdb 行；L131/L290 未动 |
| web 架构框 | `Factor_DB(Parquet) ` 与相邻列对齐（`DuckDB` 6 → `Parquet` 7，`)` 后空格 2 → 1，总宽不变） |

### 7.5 实施期偏差与发现

| ID | 级别 | 说明 | 处置 |
|----|------|------|------|
| F-S9-P005-1 | P3 | README 架构图同列另两 token（`Macro/News`、`Alternative`）在 `database.py` 无对应能力（同源幻觉）；T-1 只授权 `DuckDB`→`Parquet` | 同批修正为 `Metadata` / `Lineage`（等宽 13 字符）；DESIGN §4.1① 已补注 |
| F-S9-P005-2 | P3 | DESIGN §4.1② 的 README 示例含「DuckDB 查询层为规划方向」，与 D-1/V2「README 0 命中」冲突 | README 改为「SQL 查询层为规划方向」，DuckDB 规划表述只留 ARCHITECTURE；DESIGN §4.1② 已同步 |
| F-S9-P005-3 | P3 | ARCHITECTURE 注首版误插在依赖表内（matplotlib 与 plotly 之间），破坏表格结构 | 自纠：移至 plotly 行之后、§9.2 之前（L322） |
| 环境 | 观察 | PATH `python`/`mypy` = Anaconda 3.13（缺 cvxpy；mypy 23 errors） | 门禁全部显式项目解释器；Step 10 复核通过 |

### 7.6 Step 10 审计补丁（B3：`uv.lock`）

**发现（F-S10-P005-1，P2）**：B2 只改 `pyproject.toml`，`uv.lock` 根项目 `dependencies` 与 `[package.metadata].requires-dist` 仍含 `duckdb`，并保留 `[[package]] name = "duckdb" version = "1.5.3"` 包块。README 的 `uv sync` 安装路径因此仍会装 duckdb，与 D3「移除未使用依赖」目标相悖；D-1 的允许命中清单也未覆盖 `uv.lock`。

**处置**：B3 仅做三处删除（包块 / `dependencies` 引用 / `requires-dist` 引用），`git diff --numstat` = **0 insertions / 44 deletions**；`tomllib` 复核：根依赖 **31 → 30**、duckdb 包块 **0**、`duckdb` 字符串 **0**。

**为何不整文件 `uv lock`**：HEAD 时点 `uv lock --check` 已失败（既有漂移——锁内根项目仅 `provides-extras = ["dev"]`，缺 `web` extra）；完整重建会 **+1207/−46 行**（新增 streamlit 等既存缺失包），超出 P-005 声明面（I5）。既有漂移登记 **U-P005-5**，另批处理。

