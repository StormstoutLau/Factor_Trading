# RESEARCH：P-021 依赖与锁维护（uv.lock 重建 / pyarrow 声明决策）

> **批次**: P-021 · **T1**（`uv.lock` 依赖锁 + `docs/ARCHITECTURE.md` 依赖表；判档规则 2「真值源/依赖面不可判则升级」）
> **上游**: [PROGRESS §1.4](PROGRESS.md) U-P005-5 / U-P005-4；[CHECKLIST_p005 §9.5](CHECKLIST_p005_factor_db_alignment.md) 观察 2
> **代码证据时点**: HEAD `48bf88f`（2026-11-12，工作区干净）
> **状态**: Step 1-2 完稿（含 Step 2 Review，§7）

---

## 1. 背景与目标

P-005 的 B3 为最小面同步，只手工移除了 `uv.lock` 中的 duckdb 三处引用，未重建整个锁文件；当时实测 `uv lock --check` 在 HEAD 已失败（既有漂移），故登记 **U-P005-5** 留待独立批。同批的 **U-P005-4**（是否声明 `pyarrow`/`fastparquet`）触发条件为「下一次打包相关批次」，本批即为该批次。

**目标**：① 重建 `uv.lock` 使 `uv lock --check` 归零（锁定 web extra 与缺失依赖）；② 对 `pyarrow` 声明作出**可证伪决策**并落档；③ 把「改依赖必须同步锁」的纪律写入架构文档，避免 P-005 式手工同步复发。

**出界（不回答）**：升级任何已锁包版本（`uv lock --upgrade`）；新增 CI 门禁；`numba` 声明（另项）；Factor_DB 实现缺陷（U-P005-2）。

---

## 2. 本仓事实（P1-P9）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **`pyproject.toml` 依赖面**：`[project].dependencies` **25 项**；extras 两组——`dev` 6 项、`web` 1 项（`streamlit>=1.28.0`） | E3 @`48bf88f` [pyproject.toml](../pyproject.toml) L28-54 / L59-70 |
| **P2** | **锁文件漂移**：`uv.lock` 根项目 `dependencies` **30 条**（25 逻辑依赖按 Python 版本 marker 展开）；`[package.metadata].provides-extras` 仅 **`["dev"]`**，**缺 `web`**；总包数 120 | E1 `tomllib` 解析（§5 读数 A） |
| **P3** | **锁过期可机械判定**：`uv lock --check` → `Resolved 148 packages` + 「lockfile needs to be updated」，**exit 1** | E1 命令原文（§5 读数 B） |
| **P4** | **CI 不使用 uv**：`.github/workflows/tests.yml` 仅 `pip install ".[dev]"`；无 `uv sync` / `uv.lock` 校验步骤 | E3 [tests.yml](../.github/workflows/tests.yml) L36-37 |
| **P5** | **README 提供 uv 路径**：Quick Start 与 Installation 均列 `uv sync`；pip 路径为 `pip install -e ".[web]"` / `".[dev]"` | E3 [README.md](../README.md) L83 / L206 / L220 |
| **P6** | **本机已装引擎**：`pyarrow 24.0.0`、`fastparquet` **缺失**、`streamlit 1.65.0`（项目解释器 3.12.10）；即 Parquet 走 pyarrow，CSV 回退未被触发 | E1 `importlib.metadata`（§5 读数 C） |
| **P7** | **P-005 B3 仅三处删除**：duckdb 包块 + `dependencies` 引用 + `requires-dist` 引用；锁的其余漂移（web extra 等）未处理 | E1 `git show e1bc656 --stat` = `0/−44`；P-005 IMPL §7.6 |
| **P8** | **pyarrow 未声明**：`pyproject.toml` 全文无 `pyarrow`/`fastparquet`；README L228 与 ARCHITECTURE L322 已注明「需 `pyarrow` 或 `fastparquet`（环境自带，未声明）」 | E1 `Grep 'pyarrow|fastparquet' pyproject.toml` = 0；E3 README L228 / ARCHITECTURE L322 |
| **P9** | **架构文档 §9.2 可选依赖表失真**：表中 `ta` / `tushare` / `akshare` 实为**核心 dependencies**（非可选）；`numba` 未在任何依赖表声明；`pyarrow`/`fastparquet` 未列 | E3 [ARCHITECTURE.md](ARCHITECTURE.md) L324-331 ↔ [pyproject.toml](../pyproject.toml) L36-38 |

**事实小结**：本批要修的是「锁与清单不一致」（P2/P3）与「依赖文档失真」（P9）；`pyarrow` 声明本身（P8）零生产数据、零失败路径，属**决策项**而非缺陷。

---

## 3. 外部锚点（F1-F4）

### 3.1 降级链（F3）

`WebFetch` 直接读取 uv 官方文档 1 页（sync/lock 语义），命中正文；P-005 的 3 条锚点（pandas `to_parquet`、Packaging Guide、DuckDB Parquet）沿用其 2026-11-11 读取记录，不重复抓取。**无降级跳转**。

### 3.2 锚点清单与验证表（F1/F2/F4）

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点 |
|----|------|-----------|--------|------|----------|
| **E1** | uv docs *Locking and syncing*（Checking the lockfile） | docs stable（uv 0.11.14） | 2026-11-12 | ✅ 正文 | `uv lock --check` 等价 `--locked`；**新版本发布不会使锁过期，只有项目约束变化才会** |
| **E2** | 同上（Upgrading locked package versions） | docs stable | 2026-11-12 | ✅ 正文 | 有 `uv.lock` 时，`uv lock`/`uv sync` **优先沿用已锁版本**；仅当项目约束排除旧版本才变更；升级需 `--upgrade` |
| **E3** | 同上（Syncing optional dependencies） | docs stable | 2026-11-12 | ✅ 正文 | extras 来自 `[project.optional-dependencies]`；**`uv sync` 默认不同步 extras**，需 `--extra` / `--all-extras` |
| **E4** | pandas `DataFrame.to_parquet` | v3.0.6 | 2026-11-11（沿用 P-005） | ✅ 正文 | 需要 `fastparquet` 或 `pyarrow`；`engine` 默认 `auto` |
| **E5** | Python Packaging Guide *pyproject.toml* | 官方指南 | 2026-11-11（沿用 P-005） | ✅ 正文 | `optional-dependencies` 仅用于「特定功能需要」的依赖 |

> **F4**：5 条外部引用 ≥3，已建表。**F1/F2** 均记录读取日与版本。**F5**：Step 1 无先行失败记录 → N/A；Step 9 以「`uv lock --check` 1→0」与「锁内 extras 缺→齐」两组红/绿读数回填。

---

## 4. 方案矩阵（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **M-A 原样重建锁（推荐）** | `uv lock`（不加 `--upgrade`）+ 文档如实化 | 低（1 生成文件 + 3 行文档） | 高：`uv lock --check` 归零；web extra 入锁；开发者环境可复现 | 低 | 高（E2 保证旧 pin 不变） | 高 | 1 批 | 锁与清单长期一致 |
| M-B 全量升级 `uv lock --upgrade` | 升级所有包 | 中 | 低（无升级需求） | 中 | **低**（传递依赖可能破坏 636 基线） | 中 | 需回归 + 重录 golden | 版本债务后移 |
| M-C 删除 `uv.lock` 或保持陈旧 | 放弃锁 | 零 | 负（README 承诺 `uv sync`，无锁则不可复现） | 高 | 中 | 低 | — | 环境漂移 |
| M-D 新增 CI `uv lock --check` 门禁 | 在 workflow 加一步 | 中 | 中：锁不再漂移 | 低 | 高 | 高 | 多改 1 门禁 | 需维护 uv 安装 |

**判定**：
- **M-A 采用**：E2 明确 plain `uv lock` 优先保留旧 pin，满足「只补缺、不升级」；E1 提供机械判据 `--check`；E3 解释为何锁里可以有 web 而默认不装。
- **M-B 否决**：无升级需求（P9 无版本事故），且会引入 636 基线回归风险，超出「维护」主题。
- **M-C 否决**：README L220 已承诺 `uv sync` 路径；删锁使该路径不可复现。
- **M-D 暂不**：新增门禁属独立决策（U-P021-1），本批只修不一致，不扩门禁面。

---

## 5. 取证读数（Step 1）

| # | 命令 | 读数 |
|---|------|------|
| A | `tomllib` 解析 `pyproject.toml` + `uv.lock` | deps **25** / extras `['dev','web']`；lock root deps **30** / `provides-extras ['dev']` / 包数 **120** |
| B | `uv lock --check` | `Resolved 148 packages`；「lockfile needs to be updated」**exit 1** |
| C | `importlib.metadata`（Python312） | `pyarrow 24.0.0` / `fastparquet MISSING` / `streamlit 1.65.0` |
| D | `uv --version` | `uv 0.11.14`（2026-05-12） |
| E | CI workflow | `pip install ".[dev]"`（L37），无 uv 步骤 |

---

## 6. 未决项登记（四元块）

- **U-P021-1 CI 增加 `uv lock --check` 门禁**
  - 判据：CI 出现锁漂移（PR 改依赖但未提交锁）≥1 次，或本地锁事故 ≥1 次
  - 触发条件：下一次 CI/门禁批次
  - 当前倾向：**不加**（CI 走 pip，锁仅服务本地 `uv sync`；避免为低频事件加门禁）
  - 证据等级：E3（P4）

- **U-P021-2 `numba` 依赖声明**
  - 判据：`engine_v3` 无 numba 时的降级路径是否可接受；是否需要在 `[tool.uv]`/extra 中声明
  - 触发条件：下一次打包批或 numba 路径变更
  - 当前倾向：**维持不声明**（自动降级为 `py_func`；E2 的 `uv lock` 不涉及）
  - 证据等级：E3（ARCHITECTURE §9.2 + engine_v3 降级逻辑）

- **U-P021-3 锁升级节奏**
  - 判据：距上次锁更新 > 6 个月，或出现安全公告
  - 触发条件：定时维护或安全事件
  - 当前倾向：按需 `uv lock --upgrade-package <pkg>` 单包升级，不做全量
  - 证据等级：E2

---

## 7. 批次切分建议（供 DESIGN 采纳）

| 批次 | 内容 | 验证 |
|------|------|------|
| **B1** | `uv lock` 重建（仅 `uv.lock`） | `uv lock --check` exit 0；关键 pin 不变；duckdb 仍为 0 |
| **B2** | `docs/ARCHITECTURE.md` §9.2 依赖表如实化 + 锁维护纪律 2 行 | 表格与 `pyproject.toml` 逐行一致；无新增门禁 |

---

## 8. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] **每条事实绑证据**：P1-P9 均带 E1 读数或 E3 文件行锚（@`48bf88f`）
- [x] **外部引用验证**：E1-E3 `WebFetch` 正文命中并记录 uv 版本与读取日；E4/E5 沿用 P-005 记录（原读取日 2026-11-11）
- [x] **未验证项显式**：无；E2 的「优先沿用旧 pin」将由 Step 9 的 pin 对比实测复核
- [x] **反证检查**：主动核对「锁过期是否只是版本发布导致」——E1 明确「新版本发布不会使锁过期」，故 P3 的 exit 1 只能由**项目约束变化**（web extra 未入锁）解释
- [x] **无归因扭曲**：未把 P-005 B3 的「最小面同步」误记为「锁已修好」；明确 U-P005-5 仍未关闭
- [x] **成本估计有据**：M-A「1 生成文件」= P-005 实测 +1207/−46 的同一操作；M-D「多改 1 门禁」= workflow 单步
- [x] **F5**：Step 1 无先行失败 → N/A；Step 9 按红/绿两读数回填
- [x] **档位理由**：T1——改动落在依赖锁（环境真值面），按判档规则 2 保守升级

**Step 2 Review 结论：通过**（0 P1/P2；1 项范围收敛：M-D CI 门禁改为 U-P021-1 登记，不并入本批）。可进入 Step 3 DESIGN。
