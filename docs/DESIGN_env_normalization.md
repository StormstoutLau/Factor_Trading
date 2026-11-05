# 环境规范化（U-001 + U-005） · 设计文档

> **文档编号**: DESIGN_env_normalization
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 4 Review 通过）
> **上游**: [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md)（Step 2 复核通过）
> **下游**: [IMPL_env_normalization.md](IMPL_env_normalization.md) → [CHECKLIST_env_normalization.md](CHECKLIST_env_normalization.md)
> **证据时点**: 本仓读数 @ `116426e`；本机环境读数 2026-11-05
> **档位**: T1（改动路径含 `.github/workflows/`）

---

## 1. 设计目标

基于 [RESEARCH](RESEARCH_env_normalization.md) §5 收敛结论（采纳方案 A），本设计回答三个问题：

1. **CI 如何固定无头后端**：把 matplotlib 后端从「自动选择」变为「显式声明」，且作用域只覆盖测试 job。
2. **本地如何复现 CI 口径**：README 给出解释器选择与后端设置的可复制命令，不依赖全局环境变量。
3. **回退与取证如何成立**：两文件改动可一键还原；证据以本地 E1 + diff 审查为主，远端结果不伪造。

### 1.1 量化目标

| 目标 | 验收标准 | 复算方式 |
|------|----------|----------|
| CI 配置改动面 | 仅 `tests.yml` 1 处新增 `env`（2 行）+ 1 行命令改写；其他 step 零改动 | `git diff .github/workflows/tests.yml` |
| 生产代码改动 | `core/`、`tests/`、`scripts/` **0 行** | `git status --short` / `git diff --stat` |
| README 新增面 | 仅新增 1 个 `## 🧪 Testing` 小节（≤ 40 行，含空行与代码块） | `git diff README.md` 行数 |
| README 计数同步 | 3 处测试计数（L7 徽章 / L98 Quick Start 输出 / L374 结构注释）统一为 `509 passed` / `50 files` | `Select-String "503" README.md` 空输出 |
| 门禁 | 现有四门禁 verdict 不因本批变化（`black-check` / `mypy-check` 仍为预期 fail） | adapter `gate` 实测 |
| 回归 | 本地 `MPLBACKEND=Agg` 全量仍为 `509 passed` | `pytest tests -q` |

## 2. 架构设计

```
        ┌──────────────────────────────┐
        │ 开发者（Windows）             │
        │ py -0p → 选解释器            │
        │ $env:MPLBACKEND = "Agg"      │
        └──────────────┬───────────────┘
                       │
        ┌──────────────▼───────────────┐
        │ CI job `test`（ubuntu-latest）│
        │ env.MPLBACKEND: Agg          │  ← 唯一新增配置
        │ python -m pytest tests/      │  ← 命令改写
        └──────────────┬───────────────┘
                       │ 同一份 pyproject.toml testpaths
                       ▼
        python -m pytest → tests/ → core/engine_v2
                       → core/analytics → matplotlib
                       ▼
        matplotlib import 时读取 MPLBACKEND
                       ▼
        Agg 后端（非交互，只写文件；不触发 tk.Tk）
```

**职责边界**：

| 组件 | 负责 | 不负责 |
|------|------|--------|
| `.github/workflows/tests.yml` | 声明测试 job 的后端与调用方式 | 不改变测试内容、覆盖率、mypy 策略 |
| `README.md` | 写明本地复现口径（解释器 + 后端 + 命令） | 不承诺修复 Tk；不替代 `pyproject.toml` 配置 |
| `docs/PROGRESS.md` | 登记 U-001/U-005 收敛进度与证据出口 | 不承载 CI 配置真值 |
| matplotlib 自身 | 读取 `MPLBACKEND` 并固定后端（S1） | 不保证 GUI/Tk 可用 |

## 2A. 方案对比矩阵（Type-1 决策必填）

**本轮判定：Type-2（可逆）**，不启用 7 维矩阵（`docs/SPEC_STANDARD.md` §11.8.1）。

| 判据 | 结论 | 依据 |
|------|------|------|
| 回退点存在 | ✅ 两文件 `git restore` 即完全回退 | 无新增文件、无运行时常驻副作用 |
| 变更真值源 / 契约 | ❌ 不变 | 公开 API、`pyproject.toml`、依赖清单均不改 |
| 方案数 ≥2 且选择导致返工 | 候选 A-E 已在 [RESEARCH §3.2](RESEARCH_env_normalization.md) 记录 | 被拒理由与代价同表 |

## 3. 接口定义

### 3.1 环境变量契约

| 字段 | 类型 | 值 | 作用域 | 约束 |
|------|------|----|--------|------|
| `MPLBACKEND` | 字符串（已注册后端名） | `Agg` | CI：`jobs.test.env`（对该 job 所有 step 生效）；本地：测试进程启动前设置 | 取值必须是 matplotlib 已注册后端；`Agg` 见 S1。**禁止**写入系统环境变量或 shell 启动文件（S1 明确劝阻全局设置） |

读取时机：matplotlib 在**后端解析时**读取 `MPLBACKEND`——实测触发链表明解析发生在首个 `plt.figure` 调用而非 import（[RESEARCH](RESEARCH_env_normalization.md) §1.1 栈帧 `plt.figure → _backend_tk`）；因此变量必须在启动测试进程前存在，不能由测试代码运行时补设（那属 `conftest.py` 方案 C，已被拒）。

### 3.2 CI 配置契约

| 字段 | 当前值 @ `116426e` | 目标值 | 说明 |
|------|--------------------|--------|------|
| `jobs.test.runs-on` | `ubuntu-latest` | 不变 | — |
| `jobs.test.strategy.matrix.python-version` | `["3.10","3.11","3.12"]` | 不变 | S4：已显式指定版本，无需改 |
| `jobs.test.env` | 不存在 | `MPLBACKEND: Agg` | 新增；job 级（非 workflow 级，非 step 级） |
| `Run tests` step | `pytest tests/ --tb=short -q` | `python -m pytest tests/ --tb=short -q` | S3：`-m` 形式把 cwd 加入 `sys.path`，并绑定到 setup-python 选定的解释器 |
| `Type check (mypy)` step | `mypy core/ ... \|\| true` | **不变** | 其收紧属 P-007，不在本批（见 §10） |

### 3.3 精确变更面

**`tests.yml`（+2 / ~1）**

```diff
 jobs:
   test:
     runs-on: ubuntu-latest
+    env:
+      MPLBACKEND: Agg
     strategy:
       matrix:
         python-version: ["3.10", "3.11", "3.12"]
```

```diff
       - name: Run tests
-        run: pytest tests/ --tb=short -q
+        run: python -m pytest tests/ --tb=short -q
```

**`README.md`（新增 1 节 + 3 处计数）**

插入点：`## 📦 Installation` 的 `### Requirements` 列表之后、`## 🚀 Usage Scenarios` 前的现有 `---` 分隔线之前（L229 与 L231 之间）。新增节以**自带的前置 `---` 分隔线开头**，维持本文件「每个 `##` 节以 `---` 起始」的既有分隔约定（行号读数 @ 2026-11-05 E1：L229 = Requirements 末行、L231 = 现有 `---`、L233 = `## 🚀 Usage Scenarios`）。

新节必含 4 项内容（措辞可在 Step 5 微调，语义不得删减）：

1. Agg 的原因与 CI 对齐声明；
2. Windows 解释器选择：`py -0p` 列出、`py -3.12` 显式调用；
3. 两条可复制命令（PowerShell / bash）设置 `MPLBACKEND=Agg` 后运行 `python -m pytest`；
4. 当前基线 `509 passed`，以及 `python cli.py test` 会调用 PATH 上 `pytest` 的提醒（E3：`cli.py:140-147` @ `116426e`）。

计数同步：L7 `Tests-503%20passed` → `Tests-509%20passed`；L98 `# Output: 503 passed ✓` → `509 passed`；L374 `(503 tests, 49 files)` → `(509 tests, 50 files)`。

> 计数证据：`MPLBACKEND=Agg` 全量 `509 passed`（[RESEARCH P8](RESEARCH_env_normalization.md)，日志 SHA256 `D262199F…`）；`tests/test_*.py` 实测 50 个文件（`Get-ChildItem tests -Filter test_*.py`，E1 2026-11-05）。

### 3.4 向后兼容性

| 面 | 影响 |
|----|------|
| 公开 API / 类 / 函数 | 无（零代码） |
| `pyproject.toml` | 不改：`requires-python >=3.10`、`[tool.pytest.ini_options]` 保持 `testpaths=["tests"]`、`addopts="-v --tb=short"` |
| 依赖清单 | 不变；`MPLBACKEND` 是 matplotlib 标准环境变量，不引入新包 |
| 本地默认行为 | 不设变量时行为不变（仍属 U-001 未定位根因，不由本批修复） |
| CI 命令语义 | `pytest` → `python -m pytest` 按 S3 仅在 `sys.path` 上增加 cwd；本仓从仓库根运行，符合预期（R6 缓解） |

### 3.5 假设携带（上游 RESEARCH §5.4 → 本设计）

| 假设 | 来源 | 消费位置 | 状态 |
|------|------|----------|------|
| A1 GitHub Actions `ubuntu-latest` 无显示环境，`Agg` 可正常 `savefig` | [RESEARCH](RESEARCH_env_normalization.md) §5.4 | §2 架构图、§6「远端未执行」处置行 | 采纳为运行前提；远端读数标 `[未在远端执行]`；本地 Agg `509 passed` 为旁证（E1，2026-11-05 复跑） |
| A2 job 级 `env` 对该 job 所有 step 生效 | RESEARCH §5.4（S5） | §3.1 作用域、§3.2 `env` 行、D1 | S5 为 T1 锚点，已支持，升级为结论 |
| A3 CI 矩阵 3.10-3.12 不改版本 | RESEARCH §5.4（S4） | §3.2 matrix 行（不变） | S4 为 T1 锚点，已支持，升级为结论 |

## 4. 依赖分析

| 类型 | 内容 | 证据 |
|------|------|------|
| 运行时依赖 | **新增 0**；`MPLBACKEND` 由 matplotlib 读取 | S1 |
| CI Action 依赖 | 不新增：沿用 `actions/checkout@v4`、`actions/setup-python@v5`、`actions/cache@v4` | `tests.yml` L17-L30 @ `116426e` |
| 本地校验依赖 | `PyYAML 6.0.3`（已安装，E1 2026-11-05）；仅 Step 9 用于 `yaml.safe_load` 校验，**不写入** `pyproject.toml` | 本机 Python312 实测 |
| 内部依赖 | 无：不改任何项目模块，不被任何模块 import | `git diff --stat` |
| 可选依赖 | 无 | — |

## 5. 性能与资源

| 维度 | 评估 | 依据 |
|------|------|------|
| 时间复杂度 | 不变：测试仍单次全量收集执行 | — |
| 本地耗时 | 默认后端 20.92s / Agg 20.02s | [RESEARCH §1.1](RESEARCH_env_normalization.md)（E1） |
| CI 耗时 | 不变；矩阵 3 个 job 并行，`env` 不引入额外步骤 | `tests.yml` L12-L14 |
| 内存 / I/O | 不变；Agg 与 TkAgg 均写图片到 `output_dir` | S1 |
| 磁盘增量 | 0（无新增缓存文件、无事件流写入本仓） | — |

## 6. 错误处理

| 场景 | 系统行为 | 设计处置 | 证据 |
|------|----------|----------|------|
| `tests.yml` YAML 语法错误 | GitHub 不解析 workflow，job 不排程 | Step 9 用 `yaml.safe_load` 本地解析，解析失败即阻断交付 | PyYAML 6.0.3（E1） |
| 测试在 CI 失败 | job red、exit 非 0 | 如实 red，不加重试、不加 `\|\| true` | — |
| 本地未设 `MPLBACKEND` | 仍可能触发 Tk 初始化失败（U-001） | README 给可复制命令；不宣称 Tk 已修复 | [RESEARCH §1.1](RESEARCH_env_normalization.md) |
| `python` 解析到非项目解释器 | 收集期缺 `cvxpy` 等依赖 | README `py -0p` + `py -3.12`；CI 矩阵已显式版本 | U-005 / S4 |
| 远端未执行 | 无 GitHub 运行读数 | 标 `[未在远端执行]`，只交付本地解析 + diff 审查 | R3 |
| 后续新增测试步骤漏设后端 | 新步骤继承 job 级 `env`，仍为 Agg | 选 job 级而非 step 级的原因 | S5 |

## 7. 回退点

- `git restore .github/workflows/tests.yml README.md` 即完全回退（两文件均无新增配套文件）。
- 无运行时常驻副作用：不改环境变量、不写注册表、不改 `pyproject.toml`、不新增依赖。
- 台账与四文档删除即可；CI 下次运行回到原 `pytest tests/` 命令。
- 不涉及数据迁移或真值源，回退后无残留状态。

## 8. 决策 / 拒绝方案表（Step 3 要求）

| ID | 决策 | 选择 | 被拒绝的替代方案 | 拒绝理由 | 被拒代价 |
|----|------|------|------------------|----------|----------|
| D1 | CI 后端变量作用域 | `jobs.test.env` | ① workflow 顶层 `env` ② 仅 `Run tests` step 级 ③ 不设置，依赖自动选择 | ① 波及未来所有 job（R2）；② 后续新增测试步骤需重复声明、易漏；③ Linux 无显示时靠「自动顺序选中 Agg」（S1），非显式契约 | ① 全局副作用面扩大；② 配置重复维护；③ 行为不可复现 |
| D2 | CI 测试命令 | `python -m pytest tests/ --tb=short -q` | ① 保留 `pytest tests/ ...` | S3：`-m` 形式把 cwd 加入 `sys.path` 且与 setup-python 选定解释器绑定；保留 `pytest` 依赖 PATH 入口点 | 失去「命令即解释器」的确定性；本地已实测两者等价性由 S3 说明、回归 509 验证 |
| D3 | 本地口径载体 | README `## 🧪 Testing` 小节（`py -0p`/`py -3.12` + 临时 `MPLBACKEND`） | ① `.python-version` 固定 3.12 ② 写全局环境变量 ③ `tests/conftest.py` 强制 `matplotlib.use("Agg")` ④ 只写 CONTRIBUTING | ① 收窄支持面、与 CI 3.10-3.12 矩阵冲突；② S1 明确劝阻全局覆盖；③ 属代码改动且掩盖 GUI 差异；④ README 入口缺失 | ① 用户误以为仅支持 3.12；② 影响交互式分析；③ 违反零代码约束并改变测试语义；④ 文档可达性下降 |
| D4 | README 测试计数 | 3 处统一 `509 passed` / `50 files` | ① 保留 `503` ② 删去具体数字只写「全部通过」 | ① 与同一文件新增的 Testing 基线自相矛盾（Step 8 一致性必被拦）；② 无法复核、失去可信度 | ① 文档内部矛盾；② 每次计数变化仍需人工同步（可接受，属文档维护成本） |
| D5 | Tk 根因处置 | 本批**不纳入**修复；U-001 判据改为「固定 Agg 下全绿」 | ① Windows 安装器 `Repair` ② `TK_LIBRARY` 规避 ③ 追查 Tcl 初始化根因 | [RESEARCH §3.2 B](RESEARCH_env_normalization.md) 非仓内可复现且文件已存在；`TK_LIBRARY` 仅为 T3 线索未采纳；根因未定位（P4/P5 与全量失败矛盾） | ① 可能无效且无法写回仓库；② 引入未验证的本地规避；③ 超出本批范围且无收敛判据 |

## 9. 锚点表（§11.3 Step 3 要求）

> 本批**未新增外部检索**：全部外部锚点沿用 [RESEARCH §2.1](RESEARCH_env_normalization.md) 已于 2026-11-04 读回并验证的来源（Step 2 验证表 §6）。Step 3 属纯文档阶段，无「需外部新事实」触发（`SPEC_PROCESS.md` Step 3 行：无必用检索通道）。

| 决策 | 锚点 ID | 等级 | 版本 / 日期 | 适用性（外部环境 vs 本仓差异） |
|------|---------|------|-------------|-------------------------------|
| D1 | S1 Matplotlib Backends | T1 | 访问 2026-11-04 | 外部机制通用；本仓 `env` 语法依 S5，CI 为 Linux（无显示），与本地 Windows 差异见 R1 |
| D1 | S5 GitHub Actions variables | T1 | 访问 2026-11-04 | `env` 三作用域在 GitHub 托管 runner 通用；本仓仅用 job 级 |
| D2 | S3 pytest usage | T1 | 访问 2026-11-04 | `python -m pytest` 加 cwd 到 `sys.path`；本仓在仓库根运行，与文档描述一致 |
| D3 | S1（全局劝阻）、S6（venv / `py`）、S4（显式 python-version） | T1 | 访问 2026-11-04 | Windows 特有：`py` 启动器；本仓 README 面向 Windows 本地 + Linux CI 双口径 |
| D4 | E1（`509 passed`；50 个测试文件）、E3 `cli.py:140-147` @ `116426e` | E1 / E3 | 2026-11-05 / `116426e` | 计数与文件数均由本仓机械复算；`cli.py` 内部调用 PATH 上 `pytest` 为代码事实 |
| D5 | S1 + P4/P5（E1） | T1 / E1 | 2026-11-04 | `Agg` 可绕开 GUI；不证明 Tk 根因，结论仅到「触发链确定」 |

锚点覆盖度：D1 有 2 个外部 T1；D2 有 1 个外部 T1；D3 有 3 个外部 T1；D4 为 E1/E3 本仓证据；D5 为 T1 + E1。每个决策满足「≥1 个 T1/T2 锚点」，无 `[无外部锚点-自证]` 项。

## 10. 职责边界与不覆盖问题域（Step 4 Review 前置声明）

**职责外（本设计不回答）**：

- Tk / Tcl 初始化根因与 GUI 后端可用性修复（U-001 只收敛「测试在 Agg 下全绿」）；
- CI mypy step 的 `|| true` 收紧与 168 errors 清理（归 P-007）；
- black 全量重排（归 P-003）；
- 测试内容、覆盖率、性能基准。

**能力边界（本设计回答不了）**：

- GitHub 远端实际执行结果：本批不触发 push 后的 CI 运行，只能给本地 YAML 解析 + diff 审查读数；远端结果一律标 `[未在远端执行]`；
- Python 3.10 / 3.11 的本地实测：本机仅 3.12.10 具备完整依赖，矩阵其余版本未本地验证。

**未闭合项（四元块）**：

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| U-001′ | 固定 `MPLBACKEND=Agg` 后全量 `pytest tests` 全绿（本地 + CI） | 每次本地/CI 测试 | 已由本设计落实配置；本地 E1 达成，CI 侧待远端运行 | E1（本地） / `[未在远端执行]` |
| U-005′ | README 写明测试解释器选择方式 | 本批 Step 9 完成后复核 | README Testing 小节承载（D3） | E1（文件读回） |

## 11. Review 记录（Step 4）

- **时点**：2026-11-05，本文档完稿（Step 3）之后的独立 pass 执行；未与正文同一次写入（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**：重跑 E1 命令 + 读回文件逐项核对 + 对照 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 4 检查单与 `docs/SPEC_STANDARD.md` Phase 1 Review 检查点（不依赖正文自报）

**检查项与结果**：

| 检查项（来源） | 结果 |
|----------------|------|
| 设计基于已验证的调研结论（Step 4） | 通过：D1-D5 均引用 RESEARCH §6 已验证锚点 |
| 无未经验证的假设（Step 4） | 修复后通过：A1-A3 补 §3.5 显式携带（发现 F-D1） |
| 归因扭曲检查（Step 4） | 通过：D1 被拒③对无显示环境的表述限于 S1 记录的自动选择顺序，未虚构降级机制细节 |
| 替代方案 ≥2 并被否决（Step 4） | 通过：D1-D5 每项含被拒方案 + 理由 + 代价 |
| 职责边界清晰（Step 4） | 通过：§10 分「职责外 / 能力边界」两类显式声明 |
| 幻觉排除（Phase 1） | 通过：环境变量、YAML 键、Action 版本均经本仓 E1 读数核对 |
| 方案对比完整性（Phase 1） | 通过：Type-2 判定有依据（§2A），不启用 7 维矩阵符合 §11.8.1 |
| 接口完整性（Phase 1） | 通过：§3.1-§3.3 环境变量 / CI 配置 / 精确 diff 三层契约 |
| 兼容性（Phase 1） | 通过：§3.4 逐面核对（API / pyproject / 依赖 / 本地默认 / CI 语义） |
| 性能目标（Phase 1） | 通过：§5 全部使用实测读数（20.92s / 20.02s），无编造 |
| 降级策略（Phase 1） | 通过：§6 六类场景处置（含远端未执行的诚实标注） |

**发现并修复（2 项，均 P3）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-D1 | RESEARCH §5.4 假设 A1-A3 未显式携带进本设计（Step 2 门禁 (d)「假设以 [待定] 显式携带进下游文档」的下游落点缺失）；其中 A2/A3 已有 T1 支持但未声明升级 | 新增 §3.5 假设携带表：A1 标注为运行前提 + `[未在远端执行]`；A2/A3 声明由 S5/S4 T1 锚点支持、升级为结论 |
| F-D2 | §3.3 插入点未说明新增节需自带前置 `---`，与 README「每个 `##` 节以 `---` 起始」的既有分隔约定冲突（实施时易丢分隔线） | §3.3 补：新增节以前置 `---` 开头，并附插入点行号读数 |

**复核结果（E1 重跑，2026-11-05）**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD 绑定 | `git rev-parse --short HEAD` | `116426e`（与 E3 引用一致） |
| README 现存 503 计数恰为 3 处 | `Select-String "503" README.md` | L7 徽章 / L98 Quick Start / L374 结构注释（与 §3.3 一致） |
| 插入点行号 | 读回 README L222-L233 | L229 = Requirements 末行、L231 = `---`、L233 = Usage Scenarios（与 §3.3 一致） |
| 测试文件数 | `Get-ChildItem tests -Filter test_*.py` | 50（与 §3.3「50 files」一致） |
| Agg 全量回归 | `$env:MPLBACKEND='Agg'` + Python312 `-m pytest tests -q` | `509 passed, 82 warnings in 31.99s`（与 §1.1 目标一致） |
| tests.yml 现状 | PyYAML `safe_load` 解析 | job `test` 无 `env` 键；`Run tests` = `'pytest tests/ --tb=short -q'`；mypy step 含 `\|\| true`（与 §3.2 当前值一致） |
| cli.py 调用形态 | 读回 `cli.py` L140-L147 @ `116426e` | `pytest_args = ["pytest", ...]` 走 PATH（与 D3 提醒项一致） |

**结论**：无 P1/P2；2 项 P3 已修复；Step 4 闸门通过，可进入 Step 5 实施规划。

> **门禁记录（2026-11-05）**：session `factorv3-p008-env-norm-20261105`，`design-review` pass（门禁命令用 ASCII 模式串，规避 §4 R7 findstr 中文陷阱）。
