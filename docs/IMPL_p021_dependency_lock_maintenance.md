# IMPL：P-021 依赖与锁维护（B1 锁重建 / B2 依赖文档）

> **批次**: P-021 · **T1**（`uv.lock` / `docs/ARCHITECTURE.md`）
> **上游**: [DESIGN_p021_dependency_lock_maintenance.md](DESIGN_p021_dependency_lock_maintenance.md)（D1-D5 / I1-I5 / §4 实现规格）
> **下游**: CHECKLIST_p021_dependency_lock_maintenance
> **代码证据时点**: HEAD `48bf88f`（2026-11-12，工作区干净）
> **状态**: Step 5 完稿 + Step 6 Review 通过（§6）；Step 9 记录见 §7

---

## 1. 外部锚点（F1-F4，沿用 RESEARCH §3）

本批 `WebFetch` uv 官方文档 1 页（读取日 **2026-11-12**，uv 0.11.14），另沿用 P-005 的 2 条（读取日 2026-11-11）；无降级。

| ID | 来源 | 版本 | 用途 |
|----|------|------|------|
| E1 | uv *Locking and syncing* · Checking the lockfile | docs stable | 支撑 V1 判据 `uv lock --check` |
| E2 | 同上 · Upgrading locked package versions | docs stable | 支撑 D1/I3「只补缺不升级」 |
| E3 | 同上 · Syncing optional dependencies | docs stable | 支撑 D3 的 `--extra` 说明 |
| E4 | pandas `to_parquet` | v3.0.6 | 支撑 D2（引擎前提 + CSV 回退） |
| E5 | Packaging Guide *pyproject.toml* | 官方指南 | 支撑 D2（extra 语义） |

---

## 2. 任务分解（T-1 ~ T-3）

### T-1 `uv lock` 重建（DESIGN §4.1）

| 项 | 内容 |
|----|------|
| 命令 | `uv lock`（**不加** `--upgrade`） |
| 文件 | `uv.lock` |
| 预期增量 | `[package.optional-dependencies].web` + `provides-extras = ["dev","web"]` + streamlit 传递闭包 |
| 预期不变 | numpy / pandas / scipy / scikit-learn / cvxpy 已锁版本；duckdb 仍为 0 |

### T-2 `ARCHITECTURE.md` §9.2 整节替换（DESIGN §4.2）

| 位置 | 改动 |
|------|------|
| L324-331 | 标题改「可选与未声明依赖」；表格 4 行 → 3 行（streamlit / numba / pyarrow+fastparquet），删除误列的 ta/tushare/akshare |
| 表后 | 追加 2 条纪律（改依赖须 `uv lock`；`uv sync` 默认不装 extras） |

> 不改 §9.1 核心依赖表与 L322 DuckDB 注。

### T-3 文档与台账回写

| 文件 | 改动 |
|------|------|
| 四文档 | 本批 RESEARCH / DESIGN / IMPL / CHECKLIST |
| `docs/PROGRESS.md` | P-021 行 + U-P005-4/U-P005-5 结案 + §3.25 执行记录 |
| `CHANGELOG.md` | `Changed` 条目（锁重建 + 依赖文档如实化） |

---

## 3. 实施顺序与提交切分

| 提交 | 内容 | 测试面 |
|------|------|--------|
| **B1** | T-1（`uv.lock`） | 零代码 → 636 持平 |
| **B2** | T-2（`ARCHITECTURE.md`） | 零代码 → 636 持平 |
| **B3** | T-3（四文档 + 台账） | 零代码 → 636 持平 |

> B1 单独可 revert（恢复旧锁）；B2 与 B1 无耦合；B3 为记录层。

---

## 4. 验证项（V1-V5，与 DESIGN §5 同编号同义）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 锁一致 | `uv lock --check` exit 0 |
| V2 | 清单零改动 | `git diff --name-only -- pyproject.toml` 为空 |
| V3 | 只补缺不升级 | 重建前后同名包版本集合相等；duckdb 0；extras `["dev","web"]` |
| V4 | 回归门禁 | 636 passed（Agg）/ black 111 / mypy 36 files 0 |
| V5 | 变更面 | 仅 `uv.lock` + `docs/ARCHITECTURE.md`（+ docs 回写） |

---

## 5. 排除的低效操作

- 不执行 `uv lock --upgrade` / `--upgrade-package`；
- 不新增 CI 门禁（U-P021-1）；
- 不声明 `pyarrow`/`numba`（D2 / U-P021-2）；
- 不改 `pyproject.toml`（D5）；
- 不重写 §9.1 核心依赖表。

---

## 6. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增声明；`streamlit>=1.28.0` 已在 `[web]` extra
- [x] stdlib/工具下限：`uv 0.11.14` 已确认支持 `lock --check` / `export --frozen`
- [x] 命令可实现：`uv lock` 已在 P-005 Step 10 实测成功（Resolved 148 packages）
- [x] 行锚可核：ARCHITECTURE §9.2 已 `Read` 确认 L324-331；pyproject extras 已确认 L59-70
- [x] 锚点可解析：E1-E3 `WebFetch` 正文；E4/E5 沿用 P-005 验证记录
- [x] 低效操作已排除（§5）；回退点按 B1/B2/B3 三提交切分
- [x] F5 声明：Step 5 无先行失败记录 → N/A；Step 9 以「`--check` 1→0 / extras 缺→齐 / pin 不变」三组读数回填

**Step 6 Review 结论：通过**。可进入 Step 7 CHECKLIST。

---

## 7. Step 9 实施记录

> [RULE-1] 零预填：本节读数均为 Step 9 执行后实读（2026-11-12，项目解释器 `Python312` 3.12.10，`MPLBACKEND=Agg`）。PATH 上的 `python`/`mypy` 指向 Anaconda 3.13，所有门禁一律显式 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe -m ...`。

### 7.1 基线与提交链

| 项 | 读数 |
|----|------|
| 基线 | HEAD `48bf88f` 干净（仅四文档未跟踪）；`uv lock --check` = **exit 1**；锁根包 `provides-extras = ["dev"]`；锁内 **120** 包 |
| **B1** | `2245962`（1 文件 `+1207/−2`）：`uv.lock` |
| **B2** | `6c4adb5`（1 文件 `+7/−6`）：`docs/ARCHITECTURE.md` §9.2 |
| **B3** | `0e0d594`（6 文件 `+593/−2`）：四文档 + `PROGRESS` / `CHANGELOG`；CI run `43167039277` 三 job success（回填见 CHECKLIST §10） |

### 7.2 F5 先失败记录（红 / 绿两读数块）

**红（@`48bf88f` 旧锁 + 当前 `pyproject.toml`）**：`uv lock --check --directory <临时目录>` → **exit 1**，末行

```
The lockfile at `uv.lock` needs to be updated, but `--check` was provided. To update the lockfile, run `uv lock`.
```

旧锁根包仅 `provides-extras = ["dev"]`（缺 `[project.optional-dependencies].web`），且 `[package.metadata].requires-dist` 中 black 为 `specifier = ">=23.0.0"`（`pyproject.toml` 自 P-003 起为 `black~=26.0`）——两处陈旧均使锁与清单不一致。

**绿（@`2245962`）**

- `uv lock --check` → `Resolved 148 packages in 2ms`，**exit 0**
- `uv export --frozen --no-hashes` → **exit 0**（325 行），锁可解析
- `pyproject.toml` 零改动（V2）

### 7.3 验证项（V1-V5 实读）

| # | 验证项 | 实读 |
|---|--------|------|
| V1 | 锁一致 | `uv lock --check` **exit 0**（红态 exit 1，见 §7.2） |
| V2 | 清单零改动 | `git diff --name-only -- pyproject.toml` = **空** |
| V3 | 只补缺不升级 | 包数 **120 → 148**；同名版本集合 **changed 0 / removed 0**；新增 19 包（`streamlit` / `pyarrow` / `altair` / `anyio` / `starlette` / `uvicorn` 等）；`provides-extras = ["dev", "web"]`；duckdb **0**；numpy `2.2.6+2.4.6` / pandas `2.3.3+3.0.3` / scipy `1.15.3+1.17.1` / scikit-learn `1.7.2+1.9.0` / cvxpy `1.7.5+1.9.1` 均不变 |
| V4 | 回归门禁 | **636 passed, 152 warnings in 49.83s** / black **111 files unchanged** / mypy `Success: no issues found in 36 source files` |
| V5 | 变更面 | B1 `uv.lock +1207/−2`；B2 `ARCHITECTURE.md +7/−6`；`core/` `tests/` `agents/` `filter/` 零改动 |

### 7.4 探针读数（I3 / A-2 / A-3）

| 探针 | 读数 |
|------|------|
| 根包 extras | `uv.lock:1122` `provides-extras = ["dev", "web"]`（位于 `[package.metadata]` 子表） |
| web 入锁 | `uv.lock:1082-1085` `web = [{ streamlit 1.65.0, <3.11 }, { streamlit 1.67.0, >=3.11 }]` |
| streamlit 包块 | `uv.lock:4253`（1.65.0）/ `uv.lock:4287`（1.67.0） |
| `requires-dist` | `uv.lock:1117` `{ name = "streamlit", marker = "extra == 'web'", specifier = ">=1.28.0" }` |
| duckdb | `Select-String uv.lock -Pattern duckdb` = **0** |

### 7.5 实施期偏差与发现

| ID | 级别 | 说明 | 处置 |
|----|------|------|------|
| F-S9-P021-1 | P3 | 旧锁 `[package.metadata].requires-dist` 中 black specifier 为 `>=23.0.0`，与 `pyproject.toml` 现行 `black~=26.0`（P-003 起）不一致；`--check` 失败的另一成因 | 随 plain `uv lock` 一并修正为 `~=26.0`（锁元数据同步，非升级；black 已锁版本不变） |
| F-S9-P021-2 | 观察 | 锁根包 extras 位于 `[package.metadata]` 子表，程序化探测须读 `root["metadata"]["provides-extras"]`；顶层读取误报 None（P-005 RULE-5 观察 3 同源） | CHECKLIST A-2 判据已按子表路径表述 |
| 环境 | 观察 | PATH `python`/`mypy` = Anaconda 3.13（缺 `cvxpy` / `streamlit`） | 门禁全部显式项目解释器 |

**与 DESIGN 偏差**：无（D1-D5 / I1-I5 / V1-V5 全部按规划落地；未执行 `--upgrade`，未改 `pyproject.toml`，未新增 CI 门禁）。
