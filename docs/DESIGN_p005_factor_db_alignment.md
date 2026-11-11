# DESIGN：P-005 Factor_DB 存储与文档对齐（不迁移 DuckDB）

> **批次**: P-005 · **T1**（Layer-1：`cli.py` 运行时输出 + `pyproject.toml` 打包声明）
> **上游**: [RESEARCH_p005_factor_db_alignment.md](RESEARCH_p005_factor_db_alignment.md)（Step 2 Review 通过；M-A 判定）
> **下游**: IMPL_p005_factor_db_alignment → CHECKLIST_p005_factor_db_alignment
> **代码证据时点**: HEAD `586e817`（2026-11-11）
> **状态**: Step 3-4 完稿（§7 Step 4 Review 通过）

---

## 1. 目标与边界

**目标**：把「Factor_DB 是 DuckDB 存储」这一**文档承诺**收敛到实现真相（JSON 元数据 + Parquet/CSV），并移除未使用的 `duckdb` 依赖声明；迁移决策登记为未决项。

| 批次 | 目标 |
|------|------|
| **B1** | 文档对齐：`README.md` 三处 + `web/.../01_Overview.py` 一处 + `docs/ARCHITECTURE.md` 依赖表 |
| **B2** | 依赖与 CLI 对齐：`pyproject.toml` 移除 `duckdb>=0.10.0`；`cli.py` `info` 的 Key deps 去掉 `"duckdb"` |

**不覆盖**（明确出界）：

- **DuckDB 迁移**（M-B）：零数据（P8）、单消费方（P3）、无基准——登记 U-P005-1；
- **`FactorStore` 接口抽象**（M-C）：无第二真实需求方，证伪；
- **`factor_library` 四项实现缺陷**（P7）：行为变更与本文档主题不同源，登记 U-P005-2 独立立项；
- **`pyarrow` 依赖声明**：登记 U-P005-4，本批只在 README 写明前提；
- **历史调研文档**（`LEVEL1_DUCKDB_ANALYSIS.md` / `LOCAL_DATA_STORAGE_ANALYSIS.md`）：保持原样（ARCHITECTURE 附录已标「⚠️ 调研阶段」）。

**能力边界**：本批不改变 `factor_library` 任何行为；`cli info` 之外无运行时差异。

---

## 2. 设计决策（D1-D5）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | **README 的 Factor_DB 章节重写为真实现状**（存储格式 / 8 个公开成员 / 能力边界 / 规划方向），删除五类虚构表与五个 `*Query` 类 | 只把标题里的 `(DuckDB)` 改名 | P4② 的表格是**整段虚构能力**（Price/Macro/Sentiment/Alternative 表 + Query 类），只改标题仍留幻觉主体 | 该节从 11 行缩为 10 行左右 |
| **D2** | **四处「DuckDB 即现状」表述统一改为 Parquet**：README 架构图 L67、web Overview L96、（README L185 标题随 D1）；`cli.py` L237 移除 `"duckdb"` | 保留 `cli` 列表并标注 optional | `info` 的语义是「Key deps 已装版本」；未声明的可选项留在列表只会持续打印 `NOT INSTALLED`，误导排障 | 1 处运行时输出变化 |
| **D3** | **移除 `pyproject.toml` 的 `duckdb>=0.10.0` 声明，不新增 extra** | ① 保留声明；② 移到 `[project.optional-dependencies] factor-db` | ① 与「当前未使用」矛盾，每次安装拉未用二进制；② 零代码使用 + 零需求方时新增 extra 是假想需求（E3 的语义是「特定功能需要」，当前不存在该功能） | 未来实施查询层时需重新加依赖（U-P005-1 触发） |
| **D4** | **不迁移、不抽象**：保留 JSON + Parquet 文件存储；迁移登记 U-P005-1，届时优先 E4（DuckDB 直读 Parquet） | M-B / M-C | 见 RESEARCH §4 判定；E1「小事务非设计目标」与逐因子写入冲突 | 查询能力延后 |
| **D5** | **`ARCHITECTURE.md` 依赖表删除 `duckdb` 行，并在表下补一条「可选引擎」注**（Parquet 需 `pyarrow`/`fastparquet`，未声明） | 保留行并标「规划」 | 依赖表若继续列未声明包，表格自身即失真 | 1 行 + 1 注 |

---

## 3. 不变量（I1-I5）

| ID | 不变量 | 判据 |
|----|--------|------|
| **I1** | 全量测试 **636 passed** 持平（无测试改动） | `pytest tests`（Agg） |
| **I2** | `factor_library/` 与 `batch_backtest/` **零改动** | `git diff --stat` 不含两目录 |
| **I3** | 文档声明与代码逐条可核：README 的存储格式/成员名/边界均能在 `factor_library/database.py` 找到对应 | 人工逐条 + `Grep` |
| **I4** | 打包面：`dependencies` 仅减少 `duckdb` 一项，其余不变 | `tomllib` 解析前后对比 |
| **I5** | 新增文件 = 0（只改 5 个既有文件 + docs） | `git status` |

---

## 4. 实现规格

### 4.1 B1：README 三处（`README.md`）

**① L67 架构图**

```text
│  │  │ Data Manager │  │ Factor_DB    │  │  Stock Filter                     ││ │
│  │  │ · Daily K    │  │ · Parquet    │  │  · Suspended / Limit-up/down      ││ │
```

`· DuckDB` → `· Parquet`（单 token 替换，其余列对齐不变）。

> **F-R5-P005-1（RULE-5 复审更正，P3）**：上方示例初稿误引 `docs/ARCHITECTURE.md` 的中文图表行（`Stock Filter (10种过滤器)` / `· 停牌/涨跌停/ST`）；README.md L67 实为英文行（见 [IMPL T-1](IMPL_p005_factor_db_alignment.md) 更正后引用）。目标定位与替换 token 不受影响。

> **F-S9-P005-1（Step 9 实施期发现，P3）**：同列另两 token `· Macro/News`、`· Alternative` 与 `database.py` 能力无对应（同源幻觉）→ 同批修正为 `· Metadata`、`· Lineage`（均等宽 13 字符）；本项为 D1「删幻觉」意图的同列延伸，超出本小节初稿的单 token 授权，已登记。

**② L185-195 Factor_DB 章节**（整节替换）

```markdown
### 🗄️ Factor_DB (Parquet · ⚠️ 骨架)

Lightweight local factor storage（JSON 元数据 + 每因子一个 Parquet 文件；`pyarrow`/`fastparquet`
不可用时降级 CSV）：

| 能力 | 实现 |
|------|------|
| 因子存取 | `add_factor` / `get_factor` / `delete_factor` / `list_factors` |
| 元数据与检索 | `metadata.json`；`query(category/tags/ic_ir_min/author)` |
| 版本与血缘 | `FactorMetadata.version` / `parent_factors`；`get_lineage` |
| 统计回写 | `update_stats(ic_mean/ic_std/ir/half_life/turnover)` |

**能力边界**：无 SQL 查询层、无多源表（Price/Macro/Sentiment 等）、无并发写；多因子联合检索为
内存过滤。SQL 查询层为**规划方向**（见 `docs/ARCHITECTURE.md` 缺口表与 U-P005-1）。
```

> **F-S9-P005-2（Step 9 实施期发现，P3）**：上段初稿写「DuckDB 查询层为规划方向」，与校验项 D-1/V2「README `Grep -i duckdb` = 0」冲突 → README 实际落文为「**SQL** 查询层为规划方向」；DuckDB 规划表述只保留在 `ARCHITECTURE.md`（L322 注与缺口表）。

**③ L227 Requirements**

```markdown
- Storage: JSON metadata + Parquet per factor (needs `pyarrow` or `fastparquet`; CSV fallback)
```

（删除 `- Database: duckdb`。）

### 4.2 B1：web 与 ARCHITECTURE

| 文件 | 位置 | 改动 |
|------|------|------|
| `web/streamlit_app/pages/01_Overview.py` | L96 | `Factor_DB(DuckDB)` → `Factor_DB(Parquet)`：`DuckDB`(6 字符) → `Parquet`(7 字符)，`)` 之后保留 1 个空格（原 2 个），该行总宽不变；该行为字符串字面量，不影响渲染逻辑 |
| `docs/ARCHITECTURE.md` | L317 | 删除 `| duckdb | >=0.10.0 | 规划中的 Factor_DB 查询层（当前代码未使用） |` 行 |
| `docs/ARCHITECTURE.md` | L317 原位置（表后） | 追加注：`> Factor_DB 的 DuckDB 查询层为规划方向，当前未声明依赖；Parquet 读写需 pyarrow 或 fastparquet（环境自带，未声明）。` |

### 4.3 B2：依赖与 CLI

| 文件 | 位置 | 改动 |
|------|------|------|
| `pyproject.toml` | L36 | 删除 `"duckdb>=0.10.0",` 一行（`dependencies` 数组余项与顺序不变） |
| `cli.py` | L237 | `deps = ["numpy", "pandas", "scipy", "cvxpy", "duckdb", "pydantic", "matplotlib"]` → 去掉 `"duckdb"`，其余顺序不变 |

> **不改**：`factor_library/database.py`、`batch_backtest/`、`tests/`、任何 `import`。

---

## 5. 验证项（V1-V5）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 全量测试 | **636 passed**，`MPLBACKEND=Agg` |
| V2 | 声明残留归零 | `Grep -i 'duckdb'` 在 `README.md` / `web/**/*.py` / `cli.py` = **0 命中**；`pyproject.toml` = 0 命中 |
| V3 | 依赖面 | `tomllib` 解析 `[project].dependencies` 不含 `duckdb`，且长度 = 改前 − 1 |
| V4 | CLI 运行时 | `python cli.py info` 输出**不含** `duckdb`（改前含） |
| V5 | 变更面 | `git diff --stat` 仅 5 文件（README / Overview / ARCHITECTURE / pyproject / cli）+ docs；`factor_library/`、`batch_backtest/`、`tests/` 零改动 |

---

## 6. 风险与回退

| 风险 | 预案 |
|------|------|
| README 重写引入**新幻觉**（把某个成员名写错） | 每个成员名逐一对照 `factor_library/database.py` 的 `def` 行；CHECKLIST 设「逐名核对」项 |
| 移除 duckdb 依赖影响其他开发者的环境 | 全仓 `import duckdb` = 0（P5）；`ARCHITECTURE` 与 README 说明规划方向；回退 = 恢复一行 |
| `cli info` 输出被脚本解析 | 全仓无对 `info` 输出的解析（`Grep 'cmd_info'` = 1 定义）；输出仅少一行 |
| 文档表述把「骨架」写成「可用生产存储」 | 保留 `⚠️ 骨架` 标注 + 能力边界段；不加任何未实现的能力词 |
| 与 U-P005-2（实现缺陷）混淆 | 本批零代码逻辑；缺陷只在 RESEARCH P7 与 U-P005-2 登记 |

---

## 7. Step 4 Review（设计幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证调研结论：五处文档声明（P4）与依赖声明（P5）均逐行核对；未引入新外部假设
- [x] 无未经验证假设：README 重写内容全部来自 `database.py` 现有 `def` 与存储路径（P1/P2），不含规划能力
- [x] 接口/签名可实现：本批无新增接口；`cli.py` 仅改列表字面量
- [x] 依赖真实存在：仅**删除**依赖，无新增；不涉及版本兼容判断
- [x] 边界清晰：§1 出界五项均有归属（U-P005-1/2/4 或保持原样）
- [x] 回退点：B1/B2 各自可单独 revert（文件面不重叠：B1 = README/Overview/ARCHITECTURE；B2 = pyproject/cli）
- [x] 低效操作排除：不新建文档模板、不引入 extra、不迁移、不抽象

**Step 4 Review 结论：通过**（0 P1/P2；1 项设计期修正：D1 由「改标题」升级为「整节重写」，因 P4② 的虚构表格范围大于标题）。
