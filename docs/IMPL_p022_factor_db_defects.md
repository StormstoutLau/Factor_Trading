# IMPL：P-022 Factor_DB 四项缺陷修复

> **批次**: P-022 · **T1**（`factor_library/database.py` + `tests/test_p022_factor_db_defects.py`）
> **上游**: [DESIGN_p022_factor_db_defects.md](DESIGN_p022_factor_db_defects.md)（D1-D6 / I1-I6 / §4 实现规格）
> **下游**: CHECKLIST_p022_factor_db_defects
> **代码证据时点**: HEAD `cc3214c`（2026-11-12，工作区干净）
> **状态**: Step 5 完稿 + Step 6 Review 通过（§6）；Step 9 记录见 §7

---

## 1. 外部锚点（F1-F4，沿用 RESEARCH §3）

有效外部引用 3 条：E1 Python `date.fromisoformat`、E2 PEP 484、E3 pandas `to_parquet`（沿用 P-005）。E4（`pathlib.Path.unlink`）因页面截断未采用；无新增外部声明。

| ID | 来源 | 版本 | 用途 |
|----|------|------|------|
| E1 | Python docs *datetime* — `date.fromisoformat` | 3.12 docs | 支撑 D1（ISO 字符串解析） |
| E2 | PEP 484 *Type Hints* | Final | 支撑 D1（注解不改变运行时值） |
| E3 | pandas *DataFrame.to_parquet* | v3.0.6 | 支撑 D4（引擎缺失降级 CSV） |

---

## 2. 任务分解（T-1 ~ T-5）

### T-1 加载期 datetime 解析（B1，缺陷③）

| 项 | 内容 |
|----|------|
| 文件 | `factor_library/database.py` |
| 改动 | 新增 `_build_metadata(name, meta_dict)`；`_load_existing_factors` 改调用它；`created_at`/`updated_at` 为 `str` 时 `datetime.fromisoformat`，失败抛带上下文 `ValueError` |
| 新增测试 | 重开后 `add_factor` / `update_stats` / 双因子 `delete_factor` 均成功；`created_at` 类型为 `datetime` |
| 预期 | 红灯：`AttributeError: 'str' object has no attribute 'isoformat'`；绿灯：全部返回 |

### T-2 覆盖守卫（B2，缺陷①）

| 项 | 内容 |
|----|------|
| 文件 | `factor_library/database.py` |
| 改动 | 路径计算前置；`exists = name in _metadata or name in _factors or parquet.exists() or csv.exists()`；`exists and not overwrite` → `ValueError` |
| 新增测试 | 重开后同名写入 `ValueError`；`overwrite=True` 成功并读回新值；孤儿 csv 存在时同样 `ValueError` |
| 预期 | 红灯：不抛错且值被覆盖；绿灯：`ValueError` |

### T-3 删除两种格式（B3，缺陷②）

| 项 | 内容 |
|----|------|
| 文件 | `factor_library/database.py` |
| 改动 | `delete_factor` 循环删除 `{name}.parquet` 与 `{name}.csv`（存在才删） |
| 新增测试 | 强制 CSV 回退创建因子 → 删除 → 两文件均不存在 + `get_factor` `KeyError` |
| 预期 | 红灯：`csv_orphan=True` 且 `get_factor` 复活；绿灯：文件不存在 + `KeyError` |

### T-4 单一格式写入（B4，缺陷④）

| 项 | 内容 |
|----|------|
| 文件 | `factor_library/database.py` |
| 改动 | `try/except ImportError/else`：parquet 成功删 csv；CSV 回退成功后删 parquet |
| 新增测试 | 预置 `h.csv` → 写 parquet → csv 不存在；预置 parquet → 强制 `ImportError` 写 csv → parquet 不存在且读回新值 |
| 预期 | 红灯：双份并存；绿灯：单一格式 |

### T-5 文档与台账回写

| 文件 | 改动 |
|------|------|
| 四文档 | 本批 RESEARCH / DESIGN / IMPL / CHECKLIST |
| `docs/PROGRESS.md` | P-022 行 + U-P005-2 结案 + §3.26 执行记录 |
| `CHANGELOG.md` | `Fixed` 条目（四项缺陷） |

---

## 3. 实施顺序与提交切分

| 提交 | 内容 | 测试面 |
|------|------|--------|
| **B1** | T-1（代码 + 4 项测试） | 新增测试红→绿 |
| **B2** | T-2（代码 + 3 项测试） | 新增测试红→绿 |
| **B3** | T-3（代码 + 2 项测试） | 新增测试红→绿 |
| **B4** | T-4（代码 + 2 项测试） | 新增测试红→绿 |
| **B5** | T-5（文档 + 台账） | 零代码 → 全量持平 |

> B1 为硬前置；B2-B4 各自独立、可单独 revert；B5 为记录层。

---

## 4. 验证项（V1-V6，与 DESIGN §5 同编号同义）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 写后重开 | 重开后 `add_factor` / `update_stats` / 双因子 `delete_factor` 成功；`created_at` 为 `datetime` |
| V2 | 覆盖守卫 | 同名持久化因子 `ValueError`；`overwrite=True` 读回新值 |
| V3 | 删除彻底 | 删除后两种格式均无；`get_factor` `KeyError` |
| V4 | 单一格式 | 写后仅存一种格式；读回值等于最后写入 |
| V5 | 兼容 | 7 个公开方法签名不变；`batch_backtest/engine.py` diff 空 |
| V6 | 回归 | 全量测试全绿（636 + 新增）；black / mypy 不劣化 |

---

## 5. 排除的低效操作

- 不做 `_save_metadata` 原子写 / 并发锁（U-P022-1）；
- 不让 `get_factor` 返回副本（U-P022-2）；
- 不扩大 `except` 到非 `ImportError`（U-P022-3）；
- 不新增公开参数/开关（D5）；
- 不改 `FactorMetadata` 字段与类型（D6）；
- 不迁移 DuckDB / 不建 SQL 层（U-P005-1）。

---

## 6. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖；`datetime` 标准库；`pyarrow` 本机已装（P-005 P6）
- [x] stdlib 下限：`datetime.fromisoformat` 自 Python 3.7 可用，项目下限 3.10 满足（E1）
- [x] 命令可实现：临时目录探针已在 Step 1 跑通四组红读数（RESEARCH §5）
- [x] 行锚可核：`database.py` L77-L84 / L101 / L109-L112 / L206-L208 / L222-L223 已 `Read` 确认
- [x] 锚点可解析：E1/E2 `WebFetch` 正文；E3 沿用 P-005 记录
- [x] 低效操作已排除（§5）；回退点按 B1-B5 切分
- [x] F5 声明：Step 1 已取得 4 条红读数；Step 9 逐批以新增测试红→绿回填

**Step 6 Review 结论：通过**。可进入 Step 7 CHECKLIST。

---

## 7. Step 9 实施记录

> [RULE-1] 零预填：本节读数均为 Step 9 执行后实读（2026-11-12，项目解释器 `Python312` 3.12.10，`MPLBACKEND=Agg`）。

### 7.1 基线与提交链

| 项 | 读数 |
|----|------|
| 基线 | HEAD `cc3214c` 干净；`pytest` **636 passed**；`factor_db/` 不存在 |
| **B1** | `9c50bcd`（`database.py +15/−1` / 测试 `+78`）：加载期 datetime 解析 |
| **B2** | `ec21dc5`（`+10/−3` / 测试 `+30`）：覆盖守卫 |
| **B3** | `9ffbfde`（`+4/−4` / 测试 `+30`）：删除两种格式 |
| **B4** | `1550e63`（`+6/−1` / 测试 `+34`）：写入后单一格式 |
| **B4b** | `59e1273`（测试 `0/−3`）：black 格式化（仅删尾部空行） |
| **B5** | 四文档 + `PROGRESS` / `CHANGELOG` 回写（本节所属提交） |

### 7.2 F5 先失败记录（逐批红 → 绿）

| 批次 | 红读数（修前同测试） | 绿读数 |
|------|----------------------|--------|
| B1 | **4 failed**：3 项 `AttributeError: 'str' object has no attribute 'isoformat'`；1 项 `isinstance(created_at, datetime)` = False | **4 passed** |
| B2 | **2 failed**：`test_reopen_rejects_duplicate_without_overwrite` / `test_orphan_csv_requires_overwrite` 均 `DID NOT RAISE ValueError` | **7 passed**（累计） |
| B3 | **2 failed**：csv 仍存在（`assert not True`）；删除后 `get_factor` 未抛 `KeyError` | **9 passed**（累计） |
| B4 | **2 failed**：`both.csv` 仍存在；`swap.parquet` 仍存在 | **11 passed**（累计） |

### 7.3 验证项（V1-V6 实读）

| # | 验证项 | 实读 |
|---|--------|------|
| V1 | 写后重开 | 重开后 `add_factor` / `update_stats` / 双因子 `delete_factor` 全部成功；`created_at` 为 `datetime` |
| V2 | 覆盖守卫 | 同名持久化因子 `ValueError`；`overwrite=True` 读回新值；孤儿 csv 同样 `ValueError` |
| V3 | 删除彻底 | csv-only 因子删除后两格式均无；`get_factor` `KeyError` |
| V4 | 单一格式 | parquet 成功后 csv 删除；CSV 回退后 parquet 删除，重开读回新值 |
| V5 | 兼容 | AST 对照：7 个公开方法签名 **完全相等**；`FactorMetadata` 字段 **完全相等**；`batch_backtest/` 与 `pyproject.toml` diff **空** |
| V6 | 回归 | **647 passed, 152 warnings in 44.46s**（636 + 11）；black **112 files unchanged**；mypy **36 files 0** |

### 7.4 探针读数（A-4 / B-3 / C-2 / D-2）

| 探针 | 读数 |
|------|------|
| 重载时间字段 | `type(created_at)=datetime`、`type(updated_at)=datetime`，`isoformat()` 可调用 |
| 孤儿拒写 | 仅 `orphan.csv` 存在且无 metadata → `add_factor(overwrite=False)` 抛 `ValueError` |
| 删除复活 | 删除后 `metadata` 无该因子、两文件不存在 → `get_factor` 抛 `KeyError` |
| 反向清理 | 预置 parquet + 强制 `ImportError` → `swap.parquet` 删除、`swap.csv` 生成；重开读回 `updated` 值 |

### 7.5 实施期偏差与发现

| ID | 级别 | 说明 | 处置 |
|----|------|------|------|
| F-S9-P022-1 | P3 | B2 守卫生效后，「预置 csv 再写入」必须先 `overwrite=True`，否则在进入 B4 清理路径前即被拒绝；DESIGN §4.4 样例未显式写 `overwrite` | D-1/D-2 测试按 `overwrite=True` 实现；§7.4 记录该前提 |
| F-S9-P022-2 | 观察 | `delete_factor` 在「重开 + 单因子」时不会崩溃（该条先被移除再 `_save_metadata`），仅 ≥2 因子时触发 P6 | RESEARCH P6 已如实记录，测试用双因子覆盖 |
| F-S9-P022-3 | P3 | CI 用 `pip install ".[dev]"`，**无 parquet 引擎**：D-1 原测试依赖真实 parquet、D-2 依赖 seed 写 parquet → CI 三版本各 2 failed（run `43175692308`） | 测试改为固定分支：D-1 `monkeypatch` 写哨兵 parquet；D-2 预置哨兵 parquet + 强制 `ImportError`；B5b 提交修复 |
| 环境 | 观察 | PATH 上的 `python` 仍指向 Anaconda 3.13；所有命令显式 `Python312` | 已在 §7 声明 |

**与 DESIGN 偏差**：无（D1-D6 / I1-I6 全部按规划落地；未做原子写/返回副本/非 ImportError 清理）。
