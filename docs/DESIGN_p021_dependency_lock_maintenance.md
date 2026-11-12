# DESIGN：P-021 依赖与锁维护（重建 uv.lock + 依赖文档如实化）

> **批次**: P-021 · **T1**
> **上游**: [RESEARCH_p021_dependency_lock_maintenance.md](RESEARCH_p021_dependency_lock_maintenance.md)（Step 2 Review 通过；M-A 判定）
> **下游**: IMPL_p021_dependency_lock_maintenance → CHECKLIST_p021_dependency_lock_maintenance
> **代码证据时点**: HEAD `48bf88f`（2026-11-12）
> **状态**: Step 3-4 完稿（§7 Step 4 Review 通过）

---

## 1. 目标与边界

**目标**：① `uv lock` 原样重建，使 `uv lock --check` 归零且不升级既有 pin；② `pyarrow` 明确**不声明**并落档；③ `ARCHITECTURE.md` §9.2 依赖表与 `pyproject.toml` 对齐，并写入「改依赖必须同步锁」纪律。

| 批次 | 内容 |
|------|------|
| **B1** | `uv lock` 重建（仅 `uv.lock`） |
| **B2** | `docs/ARCHITECTURE.md` §9.2 依赖表改写 + 锁维护纪律注（3 子句） |

**不覆盖（明确出界）**：
- `uv lock --upgrade` 全量升级（M-B 否决）；
- CI 新增 `uv lock --check` 门禁（U-P021-1）；
- `numba` 声明（U-P021-2）；
- `pyproject.toml` 任何修改（含 pyarrow extra）；
- 代码/测试/golden 变更（本批零运行时行为）。

**能力边界**：本批不证明「锁中的每个包都能在当前网络/平台安装」；只证明**锁与清单一致**（`--check`）且**解析可导出**（`uv export --frozen`）。

---

## 2. 设计决策（D1-D5）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | **plain `uv lock` 原样重建**（不加 `--upgrade`），一次提交 | ① `--upgrade`；② 保持陈旧；③ 继续手工补 | ① E2 明示 plain lock 优先沿用旧 pin，升级需显式 `--upgrade`；② README L220 承诺 `uv sync`，陈旧锁使该路径不可复现；③ P-005 已证手工补会遗漏（web extra） | 生成文件 +1200 行级差异（一次性） |
| **D2** | **不声明 `pyarrow`/`fastparquet`**（维持 U-P005-4 倾向并结案） | ① 加入核心 dependencies；② 新增 `[project.optional-dependencies] parquet` extra | ① 重二进制进所有安装，而 Factor_DB 零真实数据（P-005 P8）；② E5 的 extra 语义要求「特定功能需要」，但 E3 明确 `uv sync` 默认不装 extras——extra 不能解决默认可用性，只是把问题改名；CSV 回退已存在（E4） | Parquet 默认依赖环境自带；未装时降级 CSV（已有行为） |
| **D3** | **`ARCHITECTURE.md` §9.2 如实化**：删去误列为可选的 `ta`/`tushare`/`akshare`（实为核心依赖），补 `numba`、`pyarrow`/`fastparquet` 行并标「未声明」；表后加纪律注（3 子句：改依赖须 `uv lock` 并提交锁；CI 用 pip 不校验锁；`uv sync` 默认不装 extras） | 保留原表只加注 | 原表 3 行与 `pyproject.toml` 直接矛盾，只加注仍留失真主体 | 6 行表格重写 |
| **D4** | **不新增 CI 门禁** | 在 `tests.yml` 加 `uv lock --check` | CI 走 pip（P4），锁只服务本地 `uv sync`；为低频事件增加门禁违反「不为判断造门禁」 | 锁漂移仍靠人工纪律（U-P021-1 触发再议） |
| **D5** | **`pyproject.toml` 零改动**（字节级不变） | 顺手调整依赖顺序/版本 | 本批主题是「锁与文档对齐」，不是升级或重排；零改动使 I2 可机械核验 | 无 |

---

## 3. 不变量（I1-I5）

| ID | 不变量 | 判据 |
|----|--------|------|
| **I1** | 锁与清单一致 | `uv lock --check` exit 0 |
| **I2** | 打包清单零改动 | `git diff --exit-code -- pyproject.toml` = 0 |
| **I3** | **只补缺不升级**：既有核心 pin 不变（numpy 2.2.6/2.4.6、pandas 2.3.3/3.0.3、scipy、scikit-learn、cvxpy 按各自 marker） | 重建前后 `tomllib` 对比同名包版本集合相等 |
| **I4** | 零运行时行为 | `pytest` **636 passed** 持平；black 111 unchanged；mypy 36 files 0 |
| **I5** | 变更面最小 | 仅 `uv.lock` + `docs/ARCHITECTURE.md` + docs；`core/`、`tests/`、`pyproject.toml` 零改动 |

---

## 4. 实现规格

### 4.1 B1：`uv lock` 重建

```text
uv lock
```

- **不加** `--upgrade` / `--upgrade-package`；
- 预期：`uv.lock` 根项目 `[package.optional-dependencies]` 增加 `web = [{ name = "streamlit" }]`；`[package.metadata].provides-extras = ["dev", "web"]`；streamlit 及其传递依赖入锁；
- 预期不动：numpy / pandas / scipy / scikit-learn / cvxpy 的已锁版本（I3）；
- 预期仍无：`duckdb`（P-005 B3 成果保持）。

### 4.2 B2：`ARCHITECTURE.md` §9.2（L324-331 整节替换）

```markdown
### 9.2 可选与未声明依赖

| 包 | 用途 | 声明状态 |
|----|------|----------|
| streamlit | Web Dashboard | `[web]` extra |
| numba | Engine V3 JIT 加速 | 未声明；缺失时降级 `py_func` |
| pyarrow / fastparquet | Parquet 读写（Factor_DB） | 未声明；缺失时 CSV 回退 |

> `ta` / `tushare` / `akshare` 位于核心 `dependencies`（非可选）。修改 `[project].dependencies`
> 或 extras 后须运行 `uv lock` 并提交 `uv.lock`；CI 使用 pip，不校验锁。`uv sync` 默认不同步
> extras，需 `--extra web` 或 `--all-extras`。
```

> 不改 §9.1（核心依赖表）与 L322 的 DuckDB 注。

---

## 5. 验证项（V1-V5）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 锁一致 | `uv lock --check` **exit 0** |
| V2 | 清单零改动 | `git diff --name-only -- pyproject.toml` 为空 |
| V3 | 只补缺不升级 | 重建前后同名包版本集合相等；`duckdb` 命中 0；`provides-extras` = `["dev","web"]` |
| V4 | 回归门禁 | `636 passed`（Agg，3.12.10）/ black 111 unchanged / mypy 36 files 0 |
| V5 | 变更面 | `git diff --stat` 仅 `uv.lock` + `docs/ARCHITECTURE.md`（+ docs 回写） |

---

## 6. 风险与回退

| 风险 | 预案 |
|------|------|
| plain `uv lock` 实际升级了既有 pin（E2 语义误读） | V3 逐包对比；若发生，保留旧锁并改 `uv lock --frozen` 方案（本批暂停） |
| 锁新增包在 3.10 marker 下解析失败 | `uv lock` 已解决 10 environments；失败则回退 M-C 并登记 |
| 锁文件巨大 diff 影响 review | 单文件提交、生成物声明、`--check` 机械判据 |
| 文档表格再次与 pyproject 漂移 | D3 表格逐行对照 L28-38 / L59-70；CHECKLIST 设逐行验收 |
| 误加 CI 门禁 | D4 明示出界；diff 面 I5 校验 |

**回退点**：B1 / B2 各一提交，可独立 `git revert`；B1 回退即恢复旧锁（`uv lock --check` 回到 exit 1）。

---

## 7. Step 4 Review（设计幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证事实：P1-P9 均有 E1/E3 锚；未引入新外部假设
- [x] 无未经验证假设：E2 的「优先沿用旧 pin」被显式转为 V3 可证伪判据（若不成立即停批）
- [x] 依赖真实存在：本批不新增依赖；`streamlit` 已在 `[web]` extra 声明
- [x] 接口/签名可实现：无代码接口变更；仅生成锁 + 改写文档表
- [x] 边界清晰：出界五项均有归属（U-P021-1/2 或否决项）
- [x] 回退点：B1/B2 文件面不重叠
- [x] 低效操作排除：不做全量升级、不加门禁、不动 pyproject

**Step 4 Review 结论：通过**（0 P1/P2；1 项设计期强化：把 E2 的「旧 pin 保留」从背景陈述升级为 I3/V3 硬判据）。
