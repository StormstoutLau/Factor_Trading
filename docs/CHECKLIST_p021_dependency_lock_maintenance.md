# CHECKLIST：P-021 依赖与锁维护

> **批次**: P-021 · T1
> **上游**: [IMPL_p021_dependency_lock_maintenance.md](IMPL_p021_dependency_lock_maintenance.md)（T-1~T-3 / V1-V5）；[DESIGN_p021_dependency_lock_maintenance.md](DESIGN_p021_dependency_lock_maintenance.md)（D1-D5 / I1-I5）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 10 完成（15/15 ✅）

---

## 1. 验收项

### A 组：锁文件（D1 / I1 / I3 / V1 / V3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | 锁一致性（T-1，V1） | `uv lock --check` **exit 0**（改前 exit 1） | ✅ 2026-11-12 `uv lock --check` → `Resolved 148 packages in 2ms`，exit 0；红态 @`48bf88f` 临时目录重放 exit 1（`The lockfile ... needs to be updated`，[IMPL §7.2](IMPL_p021_dependency_lock_maintenance.md)） |
| A-2 | extras 入锁（T-1，I3） | `uv.lock` 根包 `[package.metadata].provides-extras` = `["dev", "web"]`；`[package.optional-dependencies]` 含 `web = [{ name = "streamlit" }]` | ✅ `uv.lock:1122` `provides-extras = ["dev", "web"]`（`[package.metadata]` 子表，tomllib 实读）；L1082-1085 `web = [streamlit 1.65.0 / 1.67.0]` |
| A-3 | streamlit 闭包（T-1） | `streamlit` 包块存在，且锁内其依赖闭包完整（`uv lock --check` = 0 为机械判据） | ✅ `uv.lock:4253`（1.65.0）/ `L4287`（1.67.0）两个包块；`uv export --frozen --no-hashes` exit 0（325 行）+ `--check` exit 0（闭包完整机械判定） |
| A-4 | duckdb 保持归零（P-005 成果） | `Grep -i duckdb uv.lock` = **0**（包块 / root deps / requires-dist 三处均无） | ✅ `Select-String uv.lock -Pattern duckdb` = **0**；tomllib 包名映射 148 包无 duckdb、根 `requires-dist` 无 duckdb |
| A-5 | 只补缺不升级（I3，V3） | 重建前后 numpy 2.2.6/2.4.6、pandas 2.3.3/3.0.3、scipy、scikit-learn、cvxpy 的同名版本集合**相等** | ✅ tomllib 对拍 `48bf88f:uv.lock` ↔ 当前：包数 **120 → 148**、CHANGED **0** / REMOVED **0** / ADDED **19**；numpy `2.2.6+2.4.6` / pandas `2.3.3+3.0.3` / scipy `1.15.3+1.17.1` / scikit-learn `1.7.2+1.9.0` / cvxpy `1.7.5+1.9.1` |

### B 组：文档与清单（D2 / D3 / D5 / I2 / I5）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | §9.2 表格如实化（T-2） | 表 3 行：`streamlit`（`[web]` extra）/ `numba`（未声明，降级）/ `pyarrow / fastparquet`（未声明，CSV 回退）；**不含** `ta`/`tushare`/`akshare` 行 | ✅ `ARCHITECTURE.md` L324-330：标题「可选与未声明依赖」+ 3 行逐项吻合；表内无 `ta`/`tushare`/`akshare` 行（L332 注中声明其属核心 `dependencies`） |
| B-2 | 维护纪律（T-2，E1/E3） | 表后含「改依赖须 `uv lock` 并提交」+「CI 用 pip 不校验锁」+「`uv sync` 默认不同步 extras（`--extra web`）」三条 | ✅ `ARCHITECTURE.md:332` 单条注含三条：「修改 ... 后须运行 `uv lock` 并提交 `uv.lock`；CI 使用 pip，不校验锁。`uv sync` 默认不同步 extras，需 `--extra web` 或 `--all-extras`」 |
| B-3 | 打包清单零改动（D5，I2，V2） | `git diff --name-only -- pyproject.toml` = **空**；依赖 25 项 / extras `dev,web` 与改前一致 | ✅ `git diff --name-only -- pyproject.toml` = **空**；tomllib：`deps 25` / extras `["dev", "web"]`，与改前一致 |
| B-4 | 零代码/测试改动（I5，V5） | `git diff --name-only` 不含 `core/`、`tests/`、`agents/`、`filter/` | ✅ `git diff --name-only 48bf88f..HEAD -- .github/workflows core tests agents filter` = **空**；变更面仅 `uv.lock` + `docs/ARCHITECTURE.md`（+ docs 回写） |

### C 组：回归门禁（I4 / V4）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | 全量测试（I4，V4） | `pytest tests`（Agg，3.12.10）= **636 passed** 持平 | ✅ **636 passed, 152 warnings in 49.83s**（Step 9 复跑，Python312 + `MPLBACKEND=Agg`） |
| C-2 | black（I4） | `black --check core tests cli.py` 无变更（111 files unchanged） | ✅ `black --check core tests cli.py` → `111 files would be left unchanged` |
| C-3 | mypy（I4） | `mypy --explicit-package-bases core` = 0 errors（36 files） | ✅ `Success: no issues found in 36 source files` |

### D 组：治理（D3 / 台账）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 台账与日志（T-3） | `PROGRESS.md` P-021 行 + §3.25；U-P005-4/U-P005-5 结案；`CHANGELOG.md` `Changed` 条目 | ✅ `PROGRESS.md` §1.4 P-021 行 + §3.25 执行记录；U-P005-4/5 状态改「done（2026-11-12 由 P-021 承接）」并补实测注；`CHANGELOG.md` `Changed` 首条为 P-021（锁重建 + 依赖文档如实化） |
| D-2 | 提交切分与回退（§3） | B1（`uv.lock`）/ B2（`ARCHITECTURE`）/ B3（docs）三独立提交，文件面不重叠 | ✅ B1 `2245962`（`uv.lock` +1207/−2）/ B2 `6c4adb5`（`docs/ARCHITECTURE.md` +7/−6）/ B3（四文档 + 台账）；`git show --stat` 文件面两两不重叠 |
| D-3 | 未决项承接 | U-P021-1（CI 门禁）/ U-P021-2（numba）/ U-P021-3（升级节奏）登记于 RESEARCH §6 并同步台账 | ✅ [RESEARCH §6](RESEARCH_p021_dependency_lock_maintenance.md) 四元块三条齐备；`PROGRESS.md` §1.4 未决项表新增 U-P021-1~3 三行（pending） |

---

## 2. 统计

- 总数：**15 项**（A5 / B4 / C3 / D3）
- 状态：**15/15 ✅**（Step 9 实测回填，零预填残留）
- 覆盖映射：D1→A-1/A-2；D2→B-1/B-2；D3→B-1/B-2；D4→（无验收行，U-P021-1 登记）；D5→B-3；I1→A-1；I2→B-3；I3→A-2/A-4/A-5；I4→C-1/C-2/C-3；I5→B-4

---

## 3. 后续章节

Step 8 一致性 Review（§8）、Step 9 实测回填（§1 验收表）、Step 10 ADD 审计（§9）、签字表（§10）均已完成；Step 9 记录回填 [IMPL §7](IMPL_p021_dependency_lock_maintenance.md)。

---

## 8. Step 8 一致性 Review

**执行时点**: 2026-11-12，四文档完稿后独立 pass；**[RULE-4] 自查（单视角）**；代码证据时点 HEAD `48bf88f`。

### 8.1 机械校验读数

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | 四文档相对链接 **0 broken**（目标均落在本仓） |
| 预填检查（RULE-1） | 验收区 **15 项 = 15 处 `[待 Step 9]`**；全文 **17 处** = 15 单元格 + L5 规则声明 + §2 统计说明（合法） |
| ID 引用闭环 | D1-D5 / I1-I5 / T-1~T-3 / V1-V5 / U-P021-1~3 均跨 ≥2 文档；0 悬空 |

### 8.2 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH P2/P3（锁漂移/过期）→ D1 → T-1 → A-1~A-3 | 一一对应 |
| RESEARCH P8（pyarrow 未声明）→ D2 → T-2 → B-1 | 决策为「不声明」，验收体现为文档写明 |
| RESEARCH P9（§9.2 失真）→ D3 → T-2 → B-1/B-2 | 3 行误列 + 缺失行逐项有验收 |
| RESEARCH P4（CI 用 pip）→ D4 → U-P021-1 | 无验收行 = 一致（出界登记） |
| RESEARCH P1/P5（清单/README）→ D5 → T-3 → B-3 | pyproject 零改动可机械核验 |
| U-P005-5 → D1 → A-1~A-3 | 结案判据 = `--check` 0 |
| U-P005-4 → D2 → B-1 | 结案判据 = 文档明确「未声明」 |
| DESIGN V1-V5 → IMPL §4 V1-V5 → CHECKLIST | 同编号同义：V1→A-1；V2→B-3；V3→A-2/A-4/A-5；V4→C-1~C-3；V5→B-4 |

### 8.3 一致性发现

**0 项**（链接 / 预填 / ID / 编号映射均通过；无 P1/P2/P3）。

**Step 8 结论：通过**（可进入 Step 9 实施）。

---

## 9. Step 10 ADD 审计

**执行时点**: 2026-11-12；**[RULE-4] 自查（单视角）**；代码证据绑定 B1 `2245962` / B2 `6c4adb5` + 工作区 docs 回写（B3）。

### 9.1 Phase 0-4

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 五个决策均可证伪：D1（`uv lock --check` exit 0 可重放）/ D2（§9.2 三行可读回）/ D3（注中三条纪律可读回）/ D4（`.github/workflows/` diff 空 + U-P021-1 登记）/ D5（`pyproject.toml` diff 空） |
| Phase 1 完整性 | ✅ D1→A-1~A-3；D2→B-1；D3→B-1/B-2；D4→无验收行（出界，U-P021-1 承接）；D5→B-3；T-1~T-3 逐项有落点 |
| Phase 2 忠实度 | ✅ `git diff 48bf88f..HEAD` 全文核：2 文件 `+1214/−8`（`uv.lock +1207/−2` / `ARCHITECTURE.md +7/−6`）与 DESIGN §4 逐条对应；`.github/workflows` `core` `tests` `agents` `filter` 零改动 |
| Phase 3 必要性 | ✅ 无新增对象 / 依赖 / 代码文件；`uv.lock` 为锁一致性（V1）的必要条件；`ARCHITECTURE §9.2` 为依赖真值面的唯一权威文档 |
| Phase 4 语义 | ✅ 意图 = 锁与清单一致 + 依赖文档如实且零行为；`--check` 1→0、extras 缺→齐、pin changed 0、`636 passed` 持平、`pyproject.toml` 零改动 |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| `uv lock --check` 红/绿（E1） | A-1 / V1 / IMPL §7.2 | ✅ 红 @`48bf88f` 旧锁临时目录 exit 1（`needs to be updated`）；绿 @B1 exit 0（`Resolved 148 packages in 2ms`） |
| `uv export --frozen`（E1） | A-3 / 锁可解析性 | ✅ exit 0，325 行 |
| `tomllib` 锁对拍（E1） | A-2 / A-4 / A-5 / V3 | ✅ 120→148 包；changed 0 / removed 0 / added 19；extras `["dev","web"]`；duckdb 0；五组 pin 逐一相等 |
| `Select-String` duckdb（E1） | A-4 | ✅ `uv.lock` **0** 命中 |
| 全量 pytest（E1） | C-1 / I4 | ✅ `636 passed, 152 warnings in 49.83s` |
| black / mypy（E1） | C-2 / C-3 | ✅ `111 files would be left unchanged` / `Success: no issues found in 36 source files` |
| 静态读码（E3） | B-1 / B-2 | ✅ `ARCHITECTURE.md` L324-330 三行 + L332 三条纪律逐字命中；`uv.lock` L1082-1085 / L1122 / L4253 / L4287 锚点命中 |
| diff 全文审读（E3） | B-4 / V5 / Phase 2 | ✅ 2 文件 `+1214/−8`；无超纲文件；`pyproject.toml` 零改动 |
| 盲区扫描（E4；范围 = 锁与 §9.2 之外：README / CI / 其他文档 / 传递依赖 / 台账历史读数 / 解释器） | 全组 | **3 观察**（§9.3），不阻断 |
| E5 推测 | — | 无 |

### 9.3 E4 盲区扫描结果

| # | 发现 | 等级 | 处置 |
|---|------|------|------|
| 观察 1 | README `### uv` 段仅写 `uv sync`（L220），未提示 `--extra web`——按该路径安装后 Dashboard 仍缺 streamlit；ARCHITECTURE §9.2 已写明，但 README 自身未改（D3 只授权 ARCHITECTURE，V5 变更面不含 README） | 观察 | 登记留后续文档批（与 P-020 同类）；不改本批变更面 |
| 观察 2 | `pyarrow` 经 streamlit 传递依赖入锁（`uv sync --extra web` 后可用），而 §9.2「pyarrow 未声明」指项目未**显式**声明——表述准确；Factor_DB 的 Parquet 能力在 web extra 下实际可得 | 观察 | 不改文档（D2 决策不变）；U-P005-4 结案注中说明「未显式声明，锁内以 streamlit 传递依赖出现」 |
| 观察 3 | `U-P005-5` 原估「完整重锁 +1207/−46 行」，实测 **+1207/−2**（差异来自 plain `uv lock` 保留既有 pin、仅 2 行元数据变更；−46 为 P-005 时点按整文件重写估算） | 观察 | 结案行按实测改写，并注明估算偏差 |
| 环境 | PATH `python`/`mypy` = Anaconda 3.13（缺 `cvxpy`/`streamlit`），与项目解释器读数相反 | 观察 | 门禁全部显式项目解释器；IMPL §7 已声明 |

### 9.4 审计结论

**P1 = 0 / P2 = 0 / P3 = 1（F-S9-P021-1 旧锁 black specifier 漂移，已随 B1 修复）/ E4 3 观察 + 1 环境观察（均不阻断）**；V1-V5 全过、15/15 ✅。**ADD 通过。**

> **RULE-5 状态**：本批**未执行**异构复审——本会话即实施作者（DeepSeek-V4.1-Flash），不满足 RULE-5 异质性约束；需另起异构基座会话对 P-021 全批复审，E1-E4 现场重放后再行签字。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §8](RESEARCH_p021_dependency_lock_maintenance.md)（RULE-4 自查·单视角；0 P1/P2，M-D 改登记） | 2026-11-12 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §7](DESIGN_p021_dependency_lock_maintenance.md)（RULE-4 自查·单视角） | 2026-11-12 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §6](IMPL_p021_dependency_lock_maintenance.md)（RULE-4 自查·单视角） | 2026-11-12 |
| Step 7 验收清单 | 通过（零预填） | §1-§3（15 项，实测列全 `[待 Step 9]`） | 2026-11-12 |
| Step 8 一致性 Review | 通过 | §8（17 处 `[待 Step 9]` = 15 格 + 2 合法；ID 闭环；对齐矩阵 8 行；0 发现） | 2026-11-12 |
| Step 9 TDD 实施 | 完成 | [IMPL §7](IMPL_p021_dependency_lock_maintenance.md)（F5 红 exit 1 → 绿 exit 0；B1/B2/B3 三提交；15/15 ✅） | 2026-11-12 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵 10 类；P3×1 已修 + 3 观察 + 1 环境观察） | 2026-11-12 |
| RULE-5 异构复审 | **未执行** | 本会话即作者（DeepSeek-V4.1-Flash），不满足异质约束；待异构基座独立会话全批复审 | — |
| CI 回收 | success | run `43167039277`（3.10 1m54s / 3.11 1m11s / 3.12 1m30s，三 job 全绿） | 2026-11-12 |

