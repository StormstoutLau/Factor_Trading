# CI 测试环境缺失（P-009） · 设计文档

> **文档编号**: DESIGN_ci_test_env
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 4 Review 通过）
> **上游**: [RESEARCH_ci_test_env.md](RESEARCH_ci_test_env.md)（Step 2 复核通过，含社区锚点 S4-S9）
> **下游**: [IMPL_ci_test_env.md](IMPL_ci_test_env.md) → [CHECKLIST_ci_test_env.md](CHECKLIST_ci_test_env.md)
> **证据时点**: 本仓读数 @ `17e6f26`；远端 CI run `41970636863` / `41972980708`
> **档位**: T1（改动路径含 `tests/` 与 `.github/workflows/`，Layer-1）

---

## 1. 设计目标

基于 [RESEARCH §5](RESEARCH_ci_test_env.md) 收敛结论（采纳 A1 + B1 + C1），本设计回答四个问题：

1. **夹具如何在 CI 出现**：由新增脚本在 fresh clone 上就地生成 7 个 pkl，不入库、不改 `.gitignore`（避开 S4 的负模式陷阱，见 R9）。
2. **生成脚本的接口与安全边界**：参数、退出码、输出契约、以及与 `examples/demo.py` 的职责切分；覆盖本地真实夹具的防护（R8 事故的直接对策）。
3. **两处测试缺陷如何定点修复**：5 处绝对路径改仓库锚定；numba 缺失改为模块级 skip（而非删测试或加依赖）。
4. **如何证明修复成立且不扩大改动面**：CI 三版本全绿 + 27 项数据测试不 skip + 本地 `509 passed` 不变。

### 1.1 量化目标

| 目标 | 验收标准 | 复算方式 |
|------|----------|----------|
| CI 三版本全绿 | 3.10 / 3.11 / 3.12 `Run tests` 结论均 success；每版 `502 passed, 1 skipped`（模块级 skip 只计 1 项，见 C-1） | `gh run view --log`（远端） |
| 数据测试仍有覆盖 | 27 项（9 + 18）在 CI 计入 passed，**不得 skip** | CI 日志逐名核对 / 本地 `27 passed` |
| 本地零回归 | 本地（有 numba）全量 `509 passed` | `python -m pytest tests -q` |
| 生产代码改动 | `core/`、`filter/`、`tools/` **0 行** | `git diff --stat` |
| 改动面 | 3 文件修改 + 1 文件新增（`tests.yml` / 2 个测试文件 / `scripts/prepare_test_fixture.py`） | `git status --short` |
| 夹具契约 | 7 个 pkl，形状 `100×50`，`adj≡1`、`suspend≡0`、`industry≡1`，起点 `2024-01-02` | 生成脚本输出 + `pd.read_pickle` 读回 |
| 生成开销 | 单次 < 5s；CI 增加 1 个 step | CI step 时长 |
| 门禁不漂移 | `black-check` 基线 75、`mypy-check` 基线 168 不变（均为预期 fail）；注意 `tests/` 在 gate 范围内（`black --check core tests`），两个被修改测试文件的**新增行须 black 兼容**（≤100 字符） | adapter `gate` 实测（Step 9） |

## 2. 架构设计

```
CI job `test`（ubuntu-latest；矩阵 3.10 / 3.11 / 3.12）
  │
  ├─ actions/checkout@v4
  │     fresh clone：data/ 内无 pkl（.gitignore L62/L67）；gurus/*.json 齐全（已入库）
  │
  ├─ Install dependencies          `pip install ".[dev]"`
  │
  ├─ Prepare test fixture          ★ 本次新增 step
  │     `python scripts/prepare_test_fixture.py`
  │     └─ 生成 7 个 pkl → data/test_ashare/（被 gitignore 覆盖，不提交）
  │
  └─ Run tests                     `python -m pytest tests/ --tb=short -q`
        ├─ test_real_ashare_backtest.py + test_real_ashare_strict_validation.py（27 项）
        │     读 data/test_ashare → 全 passed
        ├─ test_distillation_isolation.py（5 处）
        │     GURU_DIR = Path(__file__).resolve().parents[1] / "gurus" → passed
        └─ test_numba_jit_performance.py（7 项）
              pytest.importorskip("numba") → 整模块 skipped（本地有 numba 则照常执行）
```

**职责边界**：

| 组件 | 负责 | 不负责 |
|------|------|--------|
| `scripts/prepare_test_fixture.py` | 生成 7 个 pkl，只满足 `tests/` 现行校验所需的最小字段 | 不复用 `examples/demo.py`；不生成 st/mktcap/factor 文件；不读 `E:` |
| `tests/test_distillation_isolation.py` | 用仓库锚定路径定位 `gurus/` | 不改被测对象、不改断言 |
| `tests/test_numba_jit_performance.py` | 在 numba 缺失时整模块 skip | 不删除测试、不降级断言、不改为性能门槛 |
| `.github/workflows/tests.yml` | 在安装后、测试前补一次夹具生成 | 不改矩阵、不改 `MPLBACKEND`、不改 mypy step |
| `.gitignore` | **本批不改** | 不走负模式放行夹具（R9） |
| `scripts/prepare_test_data.py` | 保持原样：真实数据重建路径（本地） | 不进 CI（依赖 `E:\Ashare_data`） |

## 2A. 方案对比矩阵（Type-1 决策必填）

**本轮判定：Type-2（可逆）**，不启用 7 维矩阵（`docs/SPEC_STANDARD.md` §11.8.1）。

| 判据 | 结论 | 依据 |
|------|------|------|
| 回退点存在 | ✅ `git revert` 本批提交即完全回退；新增脚本删除即可 | 无数据迁移、无真值源变更 |
| 变更真值源 / 契约 | ❌ 不变 | 不改公开 API、不改 `pyproject.toml` 依赖、不改 `.gitignore` |
| 方案数 ≥2 且选择导致返工 | 候选 A1-A4 / B1-B3 / C1-C3 已在 [RESEARCH §3.2](RESEARCH_ci_test_env.md) 记录，被拒理由与代价同表 | 本设计只细化已采纳方案的接口与边界 |

## 3. 接口定义

### 3.1 夹具生成脚本 CLI 契约

**路径**: `scripts/prepare_test_fixture.py`（新增）
**依赖**: 仅 `numpy` + `pandas`（**禁止** import `core` / `filter` / `tools`，避免 CI 安装顺序与包路径耦合）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--out-dir` | 路径 | `REPO_ROOT / "data/test_ashare"` | 输出目录；**相对路径按仓库根解析**（`REPO_ROOT = Path(__file__).resolve().parents[1]`，S3），不按 cwd |
| `--n-stocks` | int | 50 | 列数；下限 31（`test_04_returns_calculation` 取 `col_idx=30`） |
| `--n-days` | int | 100 | 行数；下限 51（同测试取 `day_idx=50`） |
| `--seed` | int | 42 | `np.random.default_rng(seed)`，保证跨平台可复现 |
| `--start` | ISO 日期 | `2024-01-02` | `pd.bdate_range(start, periods=n_days)` |
| `--force` | flag | False | 目标目录已有同名 pkl 时允许覆盖 |

**退出码契约**：

| 退出码 | 条件 | 行为 |
|--------|------|------|
| 0 | 生成成功 | 打印 `out_dir` 与 7 行 `name: (rows, cols)`（供 CI 日志取证） |
| 2 | `out_dir` 已存在任一目标 pkl 且未传 `--force` | 打印已存在文件清单 + 提示 `--force`，**不写任何文件**（R8 防护） |
| 1 | `n_stocks < 31` 或 `n_days < 51` | 打印下限要求，不写文件 |

**CI 调用**：`python scripts/prepare_test_fixture.py`（不带 `--force`）。fresh clone 无 pkl → 正常生成；若 CI 意外带出已有 pkl，则 exit 2 使 job 快速失败（暴露环境异常而非静默覆盖）。

### 3.2 输出数据契约（与测试断言的映射）

| 文件 | 形状 | 值约束 | 覆盖的断言 |
|------|------|--------|------------|
| `close.pkl` | `100×50` | 正值 GBM；日对数收益 clip `±0.05`（低于 `limit_up_threshold=0.095`，避免被涨停过滤剔除） | strict `test_01`/`test_02`/`test_04`；backtest `test_02`/`test_03` |
| `open.pkl` | 同上 | `roll(close, 1) * U(0.995, 1.005)`，首行 = 初始价 | strict `test_01` |
| `high.pkl` | 同上 | `max(open, close) * U(1.0, 1.02)` | strict `test_01` |
| `low.pkl` | 同上 | `min(open, close) * U(0.98, 1.0)` | strict `test_01` |
| `stock_adj.pkl` | 同上 | **恒等 1.0** | strict `test_03_adj_factor_identity`（容差 1e-6） |
| `suspend.pkl` | 同上 | **恒等 0** | `UniverseFilter` 全可买（`suspend == 0`） |
| `industry.pkl` | 同上 | **恒等 1** | 测试配置 `neutralize=False`，不参与中性化 |

| 契约项 | 值 | 依据 |
|--------|----|------|
| 索引 | `pd.DatetimeIndex`（`pd.bdate_range`，共 `n_days` 个工作日） | `_load_price_data` 对非 DatetimeIndex 会 `to_datetime`；直接给 DatetimeIndex 免转换 |
| 列名 | `000001` … `000050`（六位字符串，无交易所后缀） | 本地真实夹具列样例 `000001`（RESEARCH P2） |
| 日期窗口 | 起点 `2024-01-02`，`n_days=100` 个工作日 | 测试配置 `start_date=2024-01-02`、`end_date=2024-06-04`；夹具末日早于 end_date 不影响过滤（RESEARCH P5 说明 demo 起点不一致的反例） |
| 目录创建 | `out_dir.mkdir(parents=True, exist_ok=True)` | CI fresh clone 无 `data/` 目录 |
| 编码 | `DataFrame.to_pickle(path)` | 与 `DataManager` 读取方式一致（E3 `core/data.py:166`） |

### 3.3 精确变更面

**A. `scripts/prepare_test_fixture.py`（新增，约 90 行）**

文件头必须声明边界（R2）：

```python
"""生成测试夹具（data/test_ashare，7 个 pkl）

边界（RESEARCH_ci_test_env R2）：
- 只生成 tests/ 现行校验所需的最小字段（7 个 pkl），不生成 st/mktcap/factor。
- 不复用 examples/demo.py::generate_synthetic_data：后者会产生变动复权因子
  （违反 test_03_adj_factor_identity 的 adj≡1.0 断言），且日期起点固定 2022-01-04。
- 不读外部数据源（prepare_test_data.py 依赖 E:\Ashare_data，仅作本地真实数据重建）。
"""
```

**B. `tests/test_distillation_isolation.py`（新增 4 行；5 处替换；实测 +9/−5）**

```diff
 import numpy as np
 import pandas as pd
 
+
+# 仓库锚定路径（RESEARCH S3 / 方案 B1）：与 cwd 无关，跨平台可移植
+GURU_DIR = Path(__file__).resolve().parents[1] / "gurus"
+
 
 class TestDistillationEnums(unittest.TestCase):
```

5 处替换（行号 @ `17e6f26`，逐处核对）：

```diff
-        json_path = Path(r"F:\Coding\Factor_Trading_v3.0\gurus\buffett.json")      # L255
+        json_path = GURU_DIR / "buffett.json"

-        json_path = Path(r"F:\Coding\Factor_Trading_v3.0\gurus\soros.json")        # L269
+        json_path = GURU_DIR / "soros.json"

-        gurus_dir = Path(r"F:\Coding\Factor_Trading_v3.0\gurus")                   # L280
+        gurus_dir = GURU_DIR

-            Path(r"F:\Coding\Factor_Trading_v3.0\gurus\buffett.json")              # L298
+            GURU_DIR / "buffett.json"

-            Path(r"F:\Coding\Factor_Trading_v3.0\gurus")                           # L327
+            GURU_DIR
```

**C. `tests/test_numba_jit_performance.py`（+4）**

```diff
 import numpy as np
+import pytest
 
 sys.path.insert(0, str(Path(__file__).parent.parent))
 
+# numba 为可选依赖（RESEARCH P9/P10）；缺失时整模块 skip（方案 C1，S1 官方支持）
+pytest.importorskip("numba", reason="numba 为可选依赖，CI 未安装时跳过 JIT 性能测试")
```

- 插入点：`sys.path.insert` 之后、`build_large_test_data` 之前（L20 与 L23 之间）。
- 影响面：该文件 7 个 `test_*` 函数全部随模块跳过；**其余 502 项不受影响**；pytest 将该模块报告为 **1 个 skipped**（collection 级，非 7 项，见 C-1）。
- `test_numba_available` 保留原样（本地无 numba 时整模块已 skip，函数内 `raise` 不再可达；本地有 numba 时它仍验证可导入——不作删除）。

**D. `.github/workflows/tests.yml`（+3）**

```diff
       - name: Install dependencies
         run: |
           python -m pip install --upgrade pip
           pip install ".[dev]"
 
+      - name: Prepare test fixture
+        run: python scripts/prepare_test_fixture.py
+
       - name: Run tests
         run: python -m pytest tests/ --tb=short -q
```

- 位置约束：必须在 `Install dependencies` 之后（pandas/numpy 已装）、`Run tests` 之前。
- 不加 `if` 条件、不加 `continue-on-error`、不加 `|| true`（失败即 job red）。
- `env.MPLBACKEND: Agg`（P-008 已落地）不动。

### 3.4 向后兼容性

| 面 | 影响 |
|----|------|
| 生产代码 / 公开 API | 无改动 |
| `pyproject.toml` | 不改：依赖清单、`testpaths`、`addopts` 均保持 |
| 本地开发者流程 | 不变（本地已有真实夹具则测试照常）；只有主动运行新脚本且带 `--force` 才会改写本地夹具 |
| `scripts/prepare_test_data.py` | 保留原样，仍是本地真实数据重建路径（R7） |
| CI 语义 | 新增一个生成 step；测试命令与矩阵不变 |
| `.gitignore` | 不改（R9）：夹具仍不入库 |
| 测试计数 | CI 由 `509 passed` 变为 `502 passed, 1 skipped`（仅 numba 文件，模块级 skip 计 1 项）；本地保持 `509 passed` |

### 3.5 假设携带（上游 RESEARCH §5.3 → 本设计）

| 假设 | 来源 | 消费位置 | 状态 |
|------|------|----------|------|
| A1′ 合成夹具满足现行 27 项严格校验 | RESEARCH P13（E1 实测 27 passed） | §3.2 契约表、§6 错误处理 | 采纳为设计前提；P13 标 `[未入仓-不可重放]`，Step 9 由正式脚本重放并升级证据 |
| A2′ CI runner 可执行生成脚本（纯 numpy/pandas，无外部依赖） | RESEARCH §3.2 A1 | §3.1 依赖约束、§3.3 D | 采纳；由「禁止 import core」与「无网络/无外部源」两条约束保证 |
| A3′ numba 保持可选依赖定位 | RESEARCH P9（E3 `ARCHITECTURE.md:329`、`DECISIONS.md:85-87`） | §3.3 C、§8 D4 | 采纳为结论；C2（CI 加装 numba）已拒 |

## 4. 依赖分析

| 类型 | 内容 | 证据 |
|------|------|------|
| 运行时依赖 | **新增 0**；脚本只用 `numpy` / `pandas`（已在 `dependencies`） | `pyproject.toml:29-30` |
| CI Action 依赖 | 不新增：沿用 `checkout@v4` / `setup-python@v5` / `cache@v4` | `tests.yml:19-32` @ `17e6f26` |
| 脚本 → 项目模块 | **无依赖**（禁止 import `core`） | §3.1 |
| 测试 → 夹具 | 27 项测试读 `data/test_ashare`（cwd 相对，`pyproject.toml` `testpaths` 保证从仓库根收集） | E3 `test_real_ashare_backtest.py:25` + `test_real_ashare_strict_validation.py:27/146/256/393/513`（共 **6 处**） |
| 可选依赖 | numba 仍不入 `[dev]`（D4） | RESEARCH P10 |
| 本地校验依赖 | `PyYAML 6.0.3`（已安装，E1）；仅 Step 9 用于 `yaml.safe_load` 校验 `tests.yml`，**不写入** `pyproject.toml` | 本机 Python312 实测 |

## 5. 性能与资源

| 维度 | 评估 | 依据 |
|------|------|------|
| 夹具生成耗时 | < 5s（50×100 × 7 个 DataFrame，纯 NumPy 随机数） | 数据规模与 P13 探测一致 |
| CI 增加时长 | 约一次解释器启动 + 生成，1 个 step，&lt; 10s / job | 同上 |
| 磁盘增量 | 约 297 KB / job（7 个 pkl，与本地真实夹具同量级：各 42419 B） | `Get-ChildItem data\test_ashare` E1 |
| 测试时长 | 不变：27 项数据测试原已执行（CI 中此前因缺文件失败/报错） | RESEARCH P12 |
| 内存 | 不变：`100×50` 的 float64 矩阵约 40 KB | — |
| 本地副作用 | 仅在使用 `--force` 时覆盖 `data/test_ashare`（R8 防护见 §3.1 退出码 2） | — |

## 6. 错误处理

| 场景 | 系统行为 | 设计处置 | 证据 |
|------|----------|----------|------|
| CI fresh clone 无 `data/` 目录 | `mkdir` 失败或路径不存在 | 脚本 `mkdir(parents=True, exist_ok=True)` | §3.2 |
| 脚本在 CI 失败（缺依赖 / 参数非法） | step 非 0 → job red，后续 step 不执行 | 不加 `\|\| true`、不加 `continue-on-error`；exit 码契约明确 | §3.1 |
| 本地误运行覆盖真实夹具 | 27 项断言仍可能通过（合成数据不同），但真实夹具丢失 | ① 无 `--force` 时 exit 2 拒绝；② 验收流程先备份（Step 7 列明）；③ 恢复路径 `prepare_test_data.py` 从 `E:` 重建（R7/R8） | R8/P14 |
| 合成数据触发涨停过滤 → 无可买股票 | 优化器无权重 → strict `test_10` 失败 | 日收益 clip `±0.05` < `limit_up_threshold=0.095` | §3.2；`filter/universe_filter_clean.py:27` |
| `industry` 全 1 导致中性化除零 | 若未来测试改 `neutralize=True` | 现行两测试均 `neutralize=False`；契约表注明边界 | E3 测试配置 |
| 未来新增依赖真实市场特征的断言 | 合成数据不满足 → 测试失败 | R1：新增断言须同步更新生成脚本并在批次内验证 | RESEARCH R1 |
| numba 缺失时其他测试是否受影响 | `core.engine_v3_vector` **可正常导入**（E3 L49-61：`try: from numba import njit` + `except ImportError` 下降级为纯 Python `njit` fallback）——CI 上 numba 文件 7 项中仅 `test_numba_available` 失败，其余 6 项走降级路径通过（含于 477 passed，P12） | 模块级 skip 后 7 项全部不执行；CI 计数推演：passed = 477 − 6 + 27 + 4 = **502**，skipped = **1**（collection 级，C-1）；降级路径不再被 CI 执行（记入 U-008′） | E3 `core/engine_v3_vector.py:49-61` + P12 |
| numba 已安装但不可用（如 NumPy 版本不匹配） | numba 自身抛 `ImportError` | **`importorskip` 默认 `exc_type=ImportError`，故此类情况亦会 skip**（C-2）。要区分「真未安装」需 `exc_type=ModuleNotFoundError`（pytest ≥8.2，超出项目 `>=7.4` 契约）或手写 `try/except`；本批不做，登记为 U-008′ 边界 | S1（T1）+ S5（T2）+ S10（T1） |
| 远端未执行 | 无 GitHub 运行读数 | 标 `[未在远端执行]`；只交付本地 E1 + YAML 解析 + diff 审查 | R6 |

## 7. 回退点

- `git revert <本批提交>`：三处修改 + 一个新增脚本全部回到 `17e6f26` 状态。
- 新增脚本无运行时副作用（不写环境变量、不注册计划任务、不产生缓存文件）。
- CI 下次运行回到「无夹具生成 step」，即恢复原红基线（已知且已登记 P-009）。
- 本地真实夹具若被覆盖：`python scripts/prepare_test_data.py` 可从 `E:\Ashare_data` 重建（RESEARCH R7/P14 已验证）。
- 不涉及数据迁移或真值源，无残留状态。

## 8. 决策 / 拒绝方案表（Step 3 要求）

| ID | 决策 | 选择 | 被拒绝的替代方案 | 拒绝理由 | 被拒代价 |
|----|------|------|------------------|----------|----------|
| D1 | 夹具来源 | 新增 `scripts/prepare_test_fixture.py`，CI 就地生成 7 个 pkl | ① `git add -f` 提交 pkl（A2）② 缺文件时 skip（A3）③ CI 下载真实数据（A4）④ 复用 `examples/demo.py` 生成器 | ① 二进制入库 + 破坏 `data/` 运行时约定 + 需 gitignore 例外（S4 负模式陷阱，R9）；② 27 项失去覆盖且违反 RULE-3；③ 无凭证/不可复现；④ 含变动复权因子（违反 P3）且起点 `2022-01-04`（P5） | ① 仓库膨胀与规则冲突；② 真实数据覆盖归零；③ CI 不可重复；④ 必改 demo 语义或引入双份分支 |
| D2 | 覆盖本地夹具的防护 | 无 `--force` 时 exit 2 拒绝，打印已存在清单 | ① 静默覆盖 ② 写入临时目录再让测试改路径 ③ `tests/conftest.py` 自动生成 | ① 直接复现 P14 事故；② 需改两个测试文件的数据路径，扩大面且与 B1 范围不符；③ 把环境准备藏进测试会话（本地会静默覆盖），与 P-008 D3 拒绝 conftest 强制后端的先例不一致 | ① 一次误运行即丢真实夹具；② 改动面翻倍；③ 隐患不可见 |
| D3 | 路径解析 | 模块常量 `GURU_DIR = Path(__file__).resolve().parents[1] / "gurus"` | ① 环境变量 `GURU_DIR`（B2）② cwd 相对 `Path("gurus")`（B3）③ 5 处各写一遍 `parents[1]` | ① 新增配置面与默认值回退；② cwd 耦合（S9 同型陷阱）；③ 重复表达式易漂移 | ① 测试需注入环境；② 换目录即失效；③ 维护成本 |
| D4 | numba 缺失处置 | 模块级 `pytest.importorskip("numba")` | ① dev extras 加 `numba>=0.65.1`（C2）② 删除该文件（C3）③ `skipif` 逐项标注 | ① 引入 llvmlite/LLVM 重量依赖且需维护 NumPy 上限（S2 `<2.5`、S5 wheel 不匹配案例）；② 丢失性能回归保护；③ 7 处重复标注易漏 | ① CI 安装变重、版本漂移风险；② 保护缺失；③ 维护负担 |
| D5 | CI 生成 step 位置 | `Install dependencies` 之后、`Run tests` 之前；不带 `--force` | ① 放到 `Run tests` 同一步（`&&` 串联）② 放在 checkout 之后、安装之前 ③ 带 `--force` | ① 单 step 失败定位模糊、日志混叠；② pandas/numpy 尚未就绪；③ 掩盖「fresh clone 意外带出 pkl」的环境异常 | ① 排障成本上升；② 必然 ImportError；③ 静默继续 |
| D6 | 测试数据路径（`data/test_ashare`）是否也仓库锚定 | **不锚定**，保持 `Path("data/test_ashare")` | 改为 `Path(__file__).resolve().parents[1] / "data/test_ashare"`（两文件共 **6 处**：strict 5 处 + backtest 1 处） | pytest 由 `pyproject.toml:100 testpaths=["tests"]` 与 CI 命令均在仓库根收集；现状可工作；6 处改动超出 P-009 最小修复面 | 若未来有人从其他 cwd 直接 `pytest` 指向该文件，会失效——记入本批不覆盖项（§10），不阻断 CI 目标 |

## 9. 锚点表（§11.3 Step 3 要求）

> 本批**未新增外部检索**：全部锚点沿用 [RESEARCH §2.1/§2.1B](RESEARCH_ci_test_env.md) 已于 2026-11-05 读回并验证的来源（Step 2 §6 验证表 + 社区锚点补充复核）。

| 决策 | 锚点 ID | 等级 | 版本 / 日期 | 适用性（外部环境 vs 本仓差异） |
|------|---------|------|-------------|-------------------------------|
| D1 | S4 git `gitignore` | T1 | 2.55.0；访问 2026-11-05 | 「父目录被排除时无法 re-include」解释为何不能靠负模式放行夹具；本仓 `data/`（L62）+ `*.pkl`（L67）实测零跟踪（E1） |
| D1 | S3 Python `pathlib` | T1 | 访问 2026-11-05 | 脚本以 `resolve()` 锚定仓库根；跨平台 |
| D1 | P13 / P14（本仓） | E1 | 2026-11-05 | 合成夹具 27 项全过（`[未入仓-不可重放]`）；事故与恢复给出防护必要性 |
| D2 | S4 + R8/P14（E1） | T1 / E1 | 2026-11-05 | S4 只解释「何物不进 CI」；覆盖防护来自本仓 P14 事故 |
| D2 | S1 pytest skipping | T1 | 访问 2026-11-05 | 不用于 D2 主体；仅确认测试侧无「自动准备」机制需绕过 |
| D3 | S3 Python `pathlib` | T1 | 访问 2026-11-05 | 官方建议向上遍历前先 `resolve()`；与 S9（cwd 陷阱，T3 对照）形成正反例 |
| D4 | S1 pytest skipping | T1 | 访问 2026-11-05 | `importorskip` 官方支持模块级使用；本仓 `pytest>=7.4` 满足 |
| D4 | S2 Numba version support | T1 | 0.65.1 / 2026-04-23 | 解释 C2 一旦采纳须锁定 NumPy `<2.5` 与 llvmlite 0.47.x |
| D5 | S4 git `gitignore` | T1 | 2.55.0；访问 2026-11-05 | 「fresh clone 不含被忽略文件」是 step 必须存在的直接理由 |
| D6 | E3 `pyproject.toml` `testpaths` + CI 命令 | E3 | `17e6f26` | 本仓收集均从仓库根；不外推为通用最佳实践 |

锚点覆盖度：D1 有 2 个 T1 + E1；D2 有 1 个 T1 + E1；D3 有 1 个 T1；D4 有 2 个 T1；D5 有 1 个 T1；D6 为 E3 本仓证据（拒绝类决策，允许）。每个采纳类决策满足「≥1 个 T1/T2 锚点」，无 `[无外部锚点-自证]` 项。

## 10. 职责边界与不覆盖问题域（Step 4 Review 前置声明）

**职责外（本设计不回答）**：

- numba 在 CI 的实际覆盖（U-008：是否单开 optional job）——本批只保证「缺失可跳过」，不新增覆盖；
- `.gitignore` 结构重构（`data/*` + 负模式）与夹具入库策略（R9 明确不走）；
- `README.md` 任何改动（P-008 已完成测试说明；本批不重复文档化）；
- `scripts/prepare_test_data.py` 与真实数据链路改造（保留为本地重建路径）；
- `black` / `mypy` 基线清理（归 P-003 / P-007）；
- 27 项测试的断言强度调整或新增数据特征断言（R1 边界）。

**能力边界（本设计回答不了）**：

- 远端三版本实际结果：需 push 后观测，一律标 `[未在远端执行]`；
- Python 3.10 / 3.11 本地实测：本机仅 3.12.10 依赖完整；
- 合成夹具能否覆盖**未来**新增断言：只承诺现行 27 项（P13）。

**未闭合项（四元块）**：

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| U-007′ | CI `Run tests` 三版本全绿 | 本批 push 后每次远端验收 | 本设计落定三处修复 + 夹具 step；待远端运行 | `[未在远端执行]` |
| U-008′ | numba JIT 路径在 CI 有覆盖 | CI 出现 numba 相关回归而无法拦截 | 暂不新增 optional job | E1（本地有 numba 时仍执行） |
| U-001′ | 本地 Agg 全绿 + 远端全绿 | 每次本地/CI 测试 | 本地已达成（P-008）；远端待本批 | E1（本地） / `[未在远端执行]` |

## 11. Review 记录（Step 4）

- **时点**：2026-11-05，本文档完稿（Step 3）之后的独立 pass 执行；未与正文同一次写入（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**：重跑 E1/E3 命令 + 读回文件逐项核对 + 对照 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 4 检查单与 `docs/SPEC_STANDARD.md` Phase 1 Review 检查点（不依赖正文自报）

**检查项与结果**：

| 检查项（来源） | 结果 |
|----------------|------|
| 设计基于已验证的调研结论（Step 4） | 通过：D1-D6 均引用 RESEARCH §6 已验证锚点（S1-S4 T1 / P13-P14 E1） |
| 无未经验证的假设（Step 4） | 通过：A1′-A3′ 已在 §3.5 显式携带并注明 `[未入仓-不可重放]` 升级路径 |
| 归因扭曲检查（Step 4） | 通过：D1 被拒④对 demo.py 的描述限于 P3/P5 实测（变动复权因子、起点 `2022-01-04`），未虚构其他缺陷 |
| 替代方案 ≥2 并被否决（Step 4） | 通过：D1-D6 每项含被拒方案 + 理由 + 代价 |
| 职责边界清晰（Step 4） | 通过：§10 分「职责外 / 能力边界 / 未闭合项」三类显式声明；R9 边界（不动 gitignore）在 §2 职责表重申 |
| 幻觉排除（Phase 1） | 修复后通过：F-D3 揭示 §6 对 `engine_v3_vector` 的降级机制描述失准，已按 E3 实测（L49-61）修正 |
| 方案对比完整性（Phase 1） | 通过：Type-2 判定有依据（§2A），不启用 7 维矩阵符合 §11.8.1 |
| 接口完整性（Phase 1） | 通过：§3.1-§3.3 CLI 契约 / 数据契约 / 精确 diff 三层；退出码 0/1/2 全覆盖 |
| 兼容性（Phase 1） | 通过：§3.4 七面逐项（API / pyproject / 本地流程 / 旧脚本 / CI / gitignore / 计数） |
| 性能目标（Phase 1） | 通过：§5 全部基于实测（7 pkl × 42419 B ≈ 297 KB；P13 探测规模） |
| 降级策略（Phase 1） | 通过：§6 九类场景（含「有意不兜底」的 numba 损坏场景与远端诚实标注） |

**发现并修复（3 项，均 P3）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-D3 | §6「numba 缺失但其他测试间接受影响」行的系统行为写「`core.engine_v3_vector` import 失败」——E3 实测该模块 L49-61 有 `try/except ImportError` 降级 + 纯 Python `njit` fallback，numba 缺失时**仍可导入**；这正是 CI 读数中 numba 文件 7 项仅 1 failed、其余 6 项 passed（含于 477）的原因，也使 §1.1 的 `502 passed, 7 skipped` 缺少推演依据 | 重写该行：修正系统行为描述，补计数推演（477 − 6 + 27 + 4 = 502；skip 7），并注明「降级路径不再被 CI 执行」归入 U-008′ |
| F-D4 | §4 依赖分析缺「本地校验依赖 PyYAML」（Step 9 需 `yaml.safe_load` 校验 tests.yml；P-008 设计 §4 有对应项，本批遗漏） | 补一行：PyYAML 6.0.3 已安装（E1），仅 Step 9 使用、不写入 pyproject |
| F-D5 | §1.1「black-check 基线 75 不变」未注明 `tests/` 在 gate 范围内（`black --check core tests`），两个被修改测试文件的新增行可能引入新违规 | 加注：新增行须 black 兼容（≤100 字符），Step 9 实测不漂移 |

**复核结果（E1/E3 重跑，2026-11-05）**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD 绑定 | `git rev-parse --short HEAD` | `17e6f26`（与 E3 引用一致） |
| 硬编码路径 5 处行号 | `Grep "F:.Coding.Factor_Trading_v3.0.gurus"` | L255 / L269 / L280 / L298 / L327 全命中（与 §3.3 B 一致） |
| numba 插入点行号 | 读回 L12-L23 | L20 `sys.path.insert`、L23 `build_large_test_data`（与 §3.3 C 一致） |
| numba 文件测试数 | `Grep "^def test_"` | 7 个（L39/52/101/141/171/200/263，与 §3.3 C「7 项」一致） |
| `engine_v3_vector` 降级机制 | 读回 L44-L61 | `try: from numba import njit` / `except ImportError` + 纯 Python fallback（F-D3 依据） |
| 涨停阈值 | `Select-String filter\universe_filter_clean.py` | L27 `limit_up_threshold: float = 0.095`（clip ±0.05 安全裕度成立） |
| strict test_04 索引 | 读回 L123-L124 | `day_idx in [1,10,50]` / `col_idx in [0,10,30]`（§3.1 下限 51/31 的依据） |
| 测试数据路径处数 | `Grep 'data_dir=Path\("data/test_ashare"\)'` | strict 5 处（L27/146/256/393/513）+ backtest 1 处（L25）= 6 处（与 D6 一致） |
| pyproject 行号 | `Select-String` | L29-30 numpy/pandas、L100 `testpaths`（与 §4/D6 引用一致） |
| 本地夹具规模 | `Get-ChildItem data\test_ashare -Filter *.pkl` | 7 个，各 42419 B（≈297 KB，与 §5 一致） |
| PyYAML 可用 | `python -c "import yaml"` | 6.0.3（F-D4 依据） |
| CI 计数推演 | 代数核对 P12 读数 | 477 + 14 + 18 = 509；修复后 477 − 6 + 27 + 4 = 502 passed；numba 模块 7 项随模块 skip，报告 **1 skipped**（C-1 修正，见下） |

**结论**：无 P1/P2；3 项 P3 已修复；Step 4 闸门通过，可进入 Step 5 实施规划。

> **门禁记录（2026-11-05）**：session `factorv3-p009-ci-env-20261105`，`design-review` pass（门禁命令用 ASCII 模式串，规避 P-008 §4 R7 findstr 中文陷阱）。

**Step 5 规划期修正（C-1 / C-2，2026-11-05）**

> Step 5 实施规划期间以 E1 探针与外部检索复核，发现本文档 2 处表述与实测不符，已就地修正并留痕（不改变 D1-D6 决策）。

| ID | 修正 | 依据 |
|----|------|------|
| C-1 | CI 预期 `7 skipped` → **`1 skipped`**：模块级 `pytest.importorskip` 属 collection 级 skip，整个模块只计 1 项，模块内 7 个测试不单独计数。已同步 §1.1、§3.3 C、§3.4、§6、§11（F-S1 补列 §11） | E1 探针（pytest 9.0.3：含 3 个测试的模块 + 1 个正常测试 → `1 passed, 1 skipped`）；详见 [IMPL §2.7](IMPL_ci_test_env.md) |
| C-2 | §6「numba 损坏不兜底」不成立：默认 `exc_type=ImportError` 会捕获 numba 的版本不匹配 `ImportError` 并 skip。改为「已知语义边界，区分需 `exc_type=ModuleNotFoundError`（pytest ≥8.2）或手写 try，本批不做 → U-008′」 | S1（pytest 文档）、S5（numba Discourse 同型 ImportError 案例，T2）、S10（`exc_type` 8.2 引入） |
