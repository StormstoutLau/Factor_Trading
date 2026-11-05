# 环境规范化（U-001 + U-005） · 实施文档

> **文档编号**: IMPL_env_normalization
> **阶段**: Phase 2 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 6 Review 通过）
> **上游**: [DESIGN_env_normalization.md](DESIGN_env_normalization.md)（Step 4 Review 通过）
> **下游**: [CHECKLIST_env_normalization.md](CHECKLIST_env_normalization.md)
> **证据时点**: 本仓读数 @ `116426e`；本机环境读数 2026-11-05

---

## 1. 任务分解

| Task | 内容 | 文件 | 验证 | 预计规模 |
|------|------|------|------|----------|
| T-0 | 先写失败断言：YAML 键路径 + README 节与计数（临时脚本，不入仓） | `%TEMP%\p008_verify_*.py` | 自身（RED 读数） | ~40 行，Step 9 末尾删除 |
| T-1 | CI 固定无头后端：job 级 `env` | `.github/workflows/tests.yml` | V1 断言 + diff | +2 行 |
| T-2 | CI 测试命令改 `python -m pytest` | `.github/workflows/tests.yml` | V1 精确字符串断言 | 改 1 行 |
| T-3 | README 新增 `## 🧪 Testing` 小节（全文见 §2.3.3） | `README.md` | V2 节存在/要素/位置断言 | +35 行 |
| T-4 | README 3 处测试计数同步（`509 passed` / `50 files`） | `README.md` | V2 `Select-String "503"` 空输出 | 改 3 行 |
| T-5 | 全量回归 + 门禁入流 + 台账回写 | 无新文件 | V3 / `gate unit-tests` / `replay` | — |

依赖顺序：T-0 → T-1 → T-2 →（V1 GREEN）→ T-3 → T-4 →（V2 GREEN）→ T-5。T-1 与 T-3 无相互依赖，可并行编辑，但断言分两段执行。

## 2. 工程细节

### 2.1 版本约束

| 组件 | 版本 / 取值 | 证据 |
|------|-------------|------|
| 项目 Python 下界 | `>=3.10` | `pyproject.toml` L10 @ `116426e`（E3） |
| 本机基线解释器 | 3.12.10（`C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`） | E1 2026-11-05 |
| matplotlib | 3.10.9 | E1 2026-11-05 |
| pytest | 9.0.3 | E1 2026-11-05 |
| PyYAML（仅本地校验，不入依赖） | 6.0.3 | E1 2026-11-05 |
| `actions/checkout` | `@v4` | `tests.yml` L17 @ `116426e`（E3，不变） |
| `actions/setup-python` | `@v5` | `tests.yml` L20 @ `116426e`（E3，不变） |
| `actions/cache` | `@v4` | `tests.yml` L25 @ `116426e`（E3，不变） |
| runner 镜像 | `ubuntu-latest` | `tests.yml` L11 @ `116426e`（E3） |

**不新增任何 pip / Action / 系统依赖**。PyYAML 只用于 Step 9 的本地一次性断言，不写进 `pyproject.toml`、不进 CI。

### 2.2 文件结构

**修改**

| 文件 | 改动范围 | 行数变化 |
|------|----------|----------|
| `.github/workflows/tests.yml` | `jobs.test` 增加 `env`；`Run tests` 改命令 | +3 / -1（实测） |
| `README.md` | 新增 Testing 小节；3 处计数替换 | +40 / -3（实测；计划 +35） |
| `docs/PROGRESS.md` | §3.5 执行序 + Step 9/10 完成后回写 | +2 / ~1 |

**新增**

- `docs/RESEARCH_env_normalization.md`（已存在，上批未提交）
- `docs/DESIGN_env_normalization.md`（已存在，本批未提交）
- `docs/IMPL_env_normalization.md`（本文件）
- `docs/CHECKLIST_env_normalization.md`（Step 7 产出）

**零改动（交付前断言）**：`core/`、`tests/`、`scripts/`、`pyproject.toml`、`cli.py`。

### 2.3 接口签名（零代码，以配置契约代替函数签名）

#### 2.3.1 CI job 配置契约

| 键路径 | 类型 | 目标值 | 约束 | 回退点 |
|--------|------|--------|------|--------|
| `jobs.test.runs-on` | str | `ubuntu-latest` | 不变 | `git restore .github/workflows/tests.yml` |
| `jobs.test.env` | map[str, str] | `{"MPLBACKEND": "Agg"}` | 仅此 1 个键；不得放 workflow 顶层或 step 级（DESIGN D1） | 同上 |
| `jobs.test.strategy.matrix.python-version` | list[str] | `["3.10","3.11","3.12"]` | 不变（S4） | — |
| `jobs.test.steps[4].run` | str | `python -m pytest tests/ --tb=short -q` | 精确字符串；含 `-m`（S3） | 同上 |
| `jobs.test.steps[5].run` | str | `mypy core/ --ignore-missing-imports --no-error-summary \|\| true` | **不变**（P-007 范围） | — |
| `jobs.test.steps` 长度 | int | `6` | 不增删 step | — |

#### 2.3.2 README 计数契约

| 位置 | 当前值 @ `116426e` | 目标值 | 约束 |
|------|---------------------|--------|------|
| L7 徽章 | `Tests-503%20passed` | `Tests-509%20passed` | 只改数字段 |
| L98 Quick Start 输出 | `# Output: 503 passed ✓` | `# Output: 509 passed ✓` | 保留 `✓` |
| L374 结构注释 | `# 测试套件 (503 tests, 49 files)` | `# 测试套件 (509 tests, 50 files)` | 两个数字同时改（50 = 实测文件数） |

计数依据：`MPLBACKEND=Agg` 全量 `509 passed`（RESEARCH P8；Step 4 复跑 31.99s 同读数）；`Get-ChildItem tests -Filter test_*.py` = 50（E1）。

#### 2.3.3 README 新增节（实施时逐字落盘，仅允许 Step 6 批准后微调）

插入位置：L229 `- Full list: [pyproject.toml](pyproject.toml)` 之后、现有 L231 `---` 之前；新块自带前置 `---`（DESIGN §3.3）。

````markdown
---

## 🧪 Testing

Tests run headless: matplotlib uses the non-interactive `Agg` backend, which only writes
image files and never opens a window. CI sets `MPLBACKEND: Agg` at job level — do the same
locally.

### Choose the interpreter explicitly (Windows)

The project supports Python 3.10+; CI runs 3.10 / 3.11 / 3.12. If `python` on your PATH
resolves to another install (e.g. an Anaconda environment without the project dependencies),
pick the version explicitly:

```powershell
py -0p                        # list installed versions and their paths
py -3.12 -m pip install -e ".[dev]"
py -3.12 -m pytest            # run tests with that interpreter
```

### Run tests

```powershell
$env:MPLBACKEND = "Agg"; python -m pytest
```

```bash
MPLBACKEND=Agg python -m pytest
```

`python -m pytest` reads `testpaths = ["tests"]` from `pyproject.toml`, so no path argument
is needed. Current baseline: **509 passed** (Python 3.12.10, `MPLBACKEND=Agg`).

> `python cli.py test` wraps whatever `pytest` is on PATH. If `python` is not the
> interpreter you installed into (see above), prefix the commands accordingly,
> e.g. `py -3.12 -m pytest`.
````

新节要素检查（V2 断言对象）：`## 🧪 Testing` 唯一、`MPLBACKEND`、`py -0p`、`py -3.12`、`509 passed`、`cli.py test` 提醒。

#### 2.3.4 环境变量契约

| 名称 | 值 | 生效范围 | 读取者 | 回退点 |
|------|----|----------|--------|--------|
| `MPLBACKEND` | `Agg` | CI 测试 job 全 step；本地测试进程 | matplotlib 后端解析时（不迟于首个 `plt.figure`，触发链为证，见 [RESEARCH](RESEARCH_env_normalization.md) §1.1；S1） | 删除 `env` 块 / 关闭终端 |

### 2.4 性能注意事项与低效排除表

| 禁止的操作模式 | 原因 | 替代做法 |
|----------------|------|----------|
| 用脚本逐行读改写 README | 易损换行与编码，diff 不可审查 | 单次 `Edit` 精确替换，再读回 diff |
| 全仓正则替换 `503` | 可能误伤无关数字（日志、日期、其他计数） | 仅 3 处定点替换 + `Select-String "503"` 复核 |
| 新增 `tests/conftest.py` / pytest 插件 | 违反零代码，且改变测试语义（DESIGN D3 被拒③） | job 级 `env` + README |
| 给 CI 测试 step 加 `\|\| true` | 掩盖红基线 | 如实 red |
| 每次编辑后跑全量 pytest | 单次 20-32 秒，重复执行低效 | 编辑期只跑 V1/V2 毫秒级断言；全量回归仅 Step 9 末尾 1 次 |
| 引入 actionlint / 新 linter | 非必要新依赖 | PyYAML 解析 + 结构断言 + diff 审查 |
| 写系统环境变量 / 注册表 / shell profile | S1 明确劝阻全局设置，且不受 git 回退覆盖 | 仅 CI job env 与进程内临时变量 |
| 用 `findstr` 匹配中文 | 本机 cp65001 下失配（RESEARCH R7） | 断言脚本用 Python `open(encoding="utf-8")` |

### 2.5 测试策略

本批零代码，**不新增仓内测试文件**；用三段式验证（V1/V2 为一次性断言脚本，V3 为既有回归）。

| 编号 | 类型 | 断言 | 执行时点 |
|------|------|------|----------|
| V1 | YAML 结构 | `yaml.safe_load` 后：`jobs.test.env == {"MPLBACKEND": "Agg"}`；`steps[4].run == "python -m pytest tests/ --tb=short -q"`；`runs-on == "ubuntu-latest"`；matrix 三版本不变；`steps[5].run` 与基线逐字相同；`len(steps) == 6` | T-1/T-2 后 |
| V2 | README 文档 | `## 🧪 Testing` 出现且仅 1 次；节内 `MPLBACKEND`/`py -0p`/`py -3.12`/`509 passed`/`cli.py test` 各 ≥1；`Select-String "503"` 空输出；Testing 行号 > Installation 行号且 < Usage Scenarios 行号 | T-3/T-4 后 |
| V3 | 全量回归 | `$env:MPLBACKEND='Agg'` + Python312 `-m pytest tests -q` → `509 passed` | T-5 |
| V4 | 远端 CI | **不执行**（不 push 触发或等待远端）；结果标注 `[未在远端执行]` | — |

**边界与反例覆盖**：

| 边界 | 反例形态 | 拦截断言 |
|------|----------|----------|
| `env` 放错层级 | 写成 `steps[].env` 或 workflow 顶层 | V1 键路径 `jobs.test.env` |
| 命令缺失 `-m` | `pytest tests/ --tb=short -q` | V1 精确字符串 |
| 误删 mypy step 的 `\|\| true` | 顺手“修好” | V1 与基线逐字比对 |
| README 节插错位置 | 放在 Usage 之后 | V2 行号序 |
| 计数只改徽章 | 漏 L98/L374 | V2 `Select-String "503"` |
| 文件数写错 | 沿用 `49 files` | V2 断言 `50 files` |

### 2.6 测试先行（红→绿）执行序（Step 9）

1. 在 `%TEMP%` 写 `p008_verify_yaml.py` 与 `p008_verify_readme.py`（不入仓）；
2. 运行 → 记录 **RED**：`env is None`、`## 🧪 Testing` 缺失、`503` 命中 3 处；
3. 执行 T-1/T-2 → 重跑 V1 → **GREEN**；
4. 执行 T-3/T-4 → 重跑 V2 → **GREEN**；
5. 全量回归 V3；
6. 删除临时脚本（`Remove-Item`），`git status` 确认无残留；
7. 门禁：`gate unit-tests`（pass 入流）；`gate probe` 可选；不重跑 black/mypy（零代码变动）。

**红→绿记录义务**：两条失败读数与两条通过读数逐一写入 [CHECKLIST](CHECKLIST_env_normalization.md) §10。

## 3. 回退点

| 层级 | 动作 |
|------|------|
| 单 Task | `git restore .github/workflows/tests.yml`（T-1/T-2）或 `git restore README.md`（T-3/T-4） |
| 整批（提交前） | `git restore` 两文件 + 删除本批四文档与 PROGRESS 改动 |
| 整批（提交后） | `git revert <commit>` |
| 运行态 | 无残留：不改系统环境变量、不装依赖、不写注册表；临时脚本已删除 |

## 4. 锚点表（§11.3 Step 5 要求）

| 契约项 | 锚点 | 等级 | 版本 / 日期 | 适用性 |
|--------|------|------|-------------|--------|
| `env` 键与作用域 | S5 GitHub Actions variables | T1 | 访问 2026-11-04 | job 级对全 step 生效；本仓仅用该作用域 |
| `MPLBACKEND=Agg` | S1 Matplotlib Backends | T1 | 访问 2026-11-04 | 覆盖任何 matplotlibrc；Agg 仅写文件 |
| `python -m pytest` | S3 pytest usage | T1 | 访问 2026-11-04 | 加 cwd 到 `sys.path`；本仓从仓库根运行 |
| `py -3.12` 选择 | S6 Python Windows | T1 | 访问 2026-11-04 | Windows 启动器；Linux CI 不使用 |
| `setup-python` 显式版本 | S4 setup-python README | T1 | 访问 2026-11-04 | 已满足，不改矩阵 |
| 计数 / 文件数 | E1 + E3 `cli.py:140-147` @ `116426e` | E1 / E3 | 2026-11-05 | 本仓机械复算 |

**无新增 API / 依赖**，故无新增 API 锚点需求；`actions/*` 版本沿用现值，不升级。

## 5. Review 记录（Step 6）

- **时点**：2026-11-05，本文档完稿（Step 5）之后的独立 pass；未与正文同一次写入（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**：重跑 E1 版本 / 行号读数 + 读回 [DESIGN](DESIGN_env_normalization.md) / [RESEARCH](RESEARCH_env_normalization.md) 交叉核对 + 对照 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 6 检查单与 `docs/SPEC_STANDARD.md` Phase 2 检查点

**检查项与结果**：

| 检查项（来源） | 结果 |
|----------------|------|
| 依赖版本真实存在（Step 6） | 通过：matplotlib 3.10.9 / pytest 9.0.3 / PyYAML 6.0.3 / Python 3.12.10 重跑确认（E1） |
| stdlib API 下限（Step 6） | 不适用（零代码）；校验脚本仅用 PyYAML（已装 6.0.3）与本机 Python 3.12 |
| API 签名可实现（Step 6） | 不适用（零代码）；以 YAML 键路径 + 精确字符串契约替代（§2.3.1），无 `Any` |
| 无虚构的库或函数（Step 6） | 通过：Action 版本沿用现值（checkout@v4 / setup-python@v5 / cache@v4），无新增 pip 依赖 |
| 兼容性声明已验证（Step 6） | 通过：`steps[5]`（mypy）与 matrix 逐字不变断言（V1）；`pyproject.toml` 零改动 |
| 低效操作已排除（Step 6 / Phase 2） | 通过：§2.4 八条禁止模式，非空 |
| 文件路径存在或计划创建（Phase 2） | 通过：两目标文件均存在；新增文档均在 `docs/` |
| 每 Task 有文件 + 验证 + 行数（Phase 2） | 通过：T-0~T-5 逐项映射 V1-V4 |
| 测试覆盖（Phase 2） | 通过：零代码批次以 V1/V2 断言脚本替代仓内测试文件；边界反例 6 项（§2.5） |

**发现并修复（3 项，均 P3）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-I1 | §2.3.3 提醒注释逻辑不精确：「prefer `python -m pytest` so tests run under the interpreter you installed into」仅在 `python` 本身解析正确时成立；Anaconda 默认用户照抄仍会踩 U-005 | 注释改写：明确「若 `python` 非目标解释器，加前缀如 `py -3.12 -m pytest`」 |
| F-I2 | [DESIGN](DESIGN_env_normalization.md) §3.1 与本文 §2.3.4 写「matplotlib 在 import 时决定后端（S1）」，与 [RESEARCH](RESEARCH_env_normalization.md) §1.1 触发链矛盾——栈帧 `plt.figure → _backend_tk` 证明后端解析发生在首次绘图调用而非 import（S1 原文亦无此时序声明，属锚点过度归属） | 两处改为「后端解析时读取（不迟于首个 `plt.figure`，RESEARCH §1.1 触发链为证）」；不影响 D1 契约——进程启动前设置仍是充分条件 |
| F-I3 | §2.4「全局环境变量…且不可回退」措辞过强（系统环境变量可手动撤销） | 改为「不受 git 回退覆盖」 |

**复核结果（E1 重跑，2026-11-05）**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| 版本四元组 | Python312 `-c "import sys, matplotlib, pytest, yaml"` | `3.12.10 3.10.9 9.0.3 6.0.3`（与 §2.1 一致） |
| pyproject L10 | 读回 | `requires-python = ">=3.10"` |
| tests.yml 行号 | 读回 L11/L17/L20/L25 | `runs-on: ubuntu-latest` / `checkout@v4` / `setup-python@v5` / `cache@v4`（与 §2.1 一致） |
| README 插入点 | 读回 L229/L231/L233 | 与 §2.3.3 一致（Step 4 已核，本批复读确认） |
| steps 索引 | Step 4 PyYAML 读数沿用 | `steps[4]` = Run tests、`steps[5]` = mypy（与 §2.3.1 键路径一致） |

**结论**：无 P1/P2；3 项 P3 已修复；Step 6 闸门通过，可进入 Step 7 验收清单。

> **门禁记录（2026-11-05）**：session `factorv3-p008-env-norm-20261105`，`step-implement-review` pass（门禁命令用 ASCII 模式串，规避 §2.4 R7 陷阱）。
