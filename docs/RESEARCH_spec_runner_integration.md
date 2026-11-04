# Spec_Runner 接入 · 调研文档

> **文档编号**: RESEARCH_spec_runner_integration
> **阶段**: Phase 0 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-04
> **状态**: 已完成（Step 2 Review 通过）
> **上游**: 用户指令（2026-11-04「读取并复用遵守这个框架」）；`F:\Spec_Runner\README.md`
> **下游**: [DESIGN_spec_runner_integration.md](DESIGN_spec_runner_integration.md) → [IMPL_spec_runner_integration.md](IMPL_spec_runner_integration.md) → [CHECKLIST_spec_runner_integration.md](CHECKLIST_spec_runner_integration.md)
> **档位**: T1（改动路径含 `scripts/` 与 `tests/`，按 `F:\Spec_Workflow\SPEC_PROCESS.md` L561 判为 Layer-1）

---

## 1. 问题定义

### 1.1 核心问题

本项目当前的 Spec 流程证据（门禁结论、审查通过态、跨会话状态）依赖**手工命令 + 文档自述**：

- 门禁通过与否只写在 `PROGRESS.md` / `DEV-LOG-*.md`，无机械事件流；
- 跨会话状态靠文档摘要，上下文压缩后需要重新取证；
- “审查 gate 未过 → 实施不可启动”只有纪律，没有物理前置检查。

### 1.2 为什么现在需要解决

用户要求接入并遵守 `F:\Spec_Runner` 框架。该框架把上述三个痛点物理化为：门禁命令（`gate`）、append-only JSONL 事件流（`sessions/*.jsonl`）、重放校验（`replay`）。

### 1.3 影响范围

| 范围 | 内容 |
|------|------|
| `scripts/` | 新增 `spec_runner_adapter.py`（官方模板 + 本项目配置区） |
| `tests/` | 新增 `test_spec_runner_adapter.py`（纯函数/CLI 形态测试，无外部副作用） |
| `docs/` | 四文档 + `PROGRESS.md` / `DEVLOG.md` / `CHANGELOG.md` 回写 |
| 运行态 | `F:\Spec_Runner\sessions\factorv3-*.jsonl`（框架自身状态目录） |

---

## 2. 来源调研

### 2.1 外部来源（T1 一手）

| ID | 来源 | 版本 / 日期 | 关键事实 | 可解析 ID |
|----|------|-------------|----------|-----------|
| S1 | `F:\Spec_Runner\README.md` | @ `60ab3e3`；框架 v1.0.0 | 五命令面（run/gate/status/replay/fork）+ `selftest`；接入模板三步；事件流十字段 schema；`--require-gate` 前置检查 | 文件路径 + commit `60ab3e3b79b38056cb45891c9062dfe6ed83f5e0` |
| S2 | `F:\Spec_Runner\spec_runner.py` | v1.0.0 @ `60ab3e3` | `gate` 用 `subprocess.run(shell=True)` 执行命令并透传 exit；`verdict = pass/fail` 机械映射；`stdout_tail` ≤2000；sessions 默认 `<ROOT>/sessions`，可由 `SR_SESSIONS_DIR` 注入；`run` 对已存在 sid 无 `--resume` 拒绝；`replay` 校验 seq/ session/ llm_request | 源码 L38-L40、L106-L132、L196-L241、L262-L281 |
| S3 | `F:\Spec_Workflow\spec\spec-runner\SPEC_RUNNER_DESIGN.md` | v1.0，2026-08-26 @ `bf83e48` | D1-D7；D3 明确「verdict = exit code 机械映射，不含 LLM 判断」；D7 命令语义 | `spec/spec-runner/SPEC_RUNNER_DESIGN.md` L21-L97 |
| S4 | `F:\Spec_Runner\templates\spec_runner_adapter.py` | v1.0，2026-09-07 | 通用接入样板：只改顶部配置区（RUNNER/PREFIX/CWD/GATES）；编排壳不复制 runner 逻辑、不改 gate 语义 | 模板 L46-L72（配置区）、L82-L224（编排） |
| S5 | `F:\Spec_Runner\templates\examples\spec_workflow_adapter.py` | v1.1，2026-09-08 | 已配置成品（Spec_Workflow 自举），可照改四处的写法 | 示例文件 L73-L104 |

### 2.2 本仓事实（E1 命令取证）

| ID | 断言 | 证据 | 等级 |
|----|------|------|------|
| P1 | 本仓 `scripts/` 当前仅有 `prepare_test_data.py` | `Get-ChildItem scripts` | E1 |
| P2 | 项目要求 Python ≥3.10；black line-length=100 | `pyproject.toml` `requires-python`、`[tool.black]` | E1 |
| P3 | 全量测试基线 `503 passed`（`MPLBACKEND=Agg` + Python312） | `%TEMP%\pytest_agg_devlog003_20261104.log`，SHA256 `71F014D4…` | E1 |
| P4 | black 26.5.0 基线 `75 files would be reformatted, 4 unchanged`（exit 1） | `python312 -m black --check core tests` | E1 |
| P5 | mypy 2.1.0 在 `--explicit-package-bases core` 下 `168 errors in 20 files`（exit 1）；无该旗标时因目录名含点直接报错 | `python312 -m mypy --explicit-package-bases core` | E1 |
| P6 | 默认 `python` 为 Anaconda 3.13.5，缺 `cvxpy`，直接跑 pytest 收集失败 | `Get-Command python`；`ModuleNotFoundError: No module named 'cvxpy'` | E1 |
| P7 | Runner 内置自测 `21/21 passed` | `python F:\Spec_Runner\spec_runner.py selftest` | E1 |
| P8 | Runner 仓工作区干净；历史中存在 gate 自动 commit | `git -C F:\Spec_Runner status --short` 空；`git log` 见 `gate:*` 提交 | E1 |

### 2.3 外部框架的运行态约束（须在本仓显式承认）

1. **自动提交**：`gate` 成功后 runner 会 `git add -A sessions` 并 commit（源码 L106-L114）。写入范围仅 `F:\Spec_Runner\sessions`，不改 runner 源码。
2. **会话默认落盘在 Runner 仓**：`sessions_dir()` 默认 `<RUNner ROOT>/sessions`；本仓不覆盖 `SR_SESSIONS_DIR`，保持与 README 一致。
3. **边界区分**：`F:\Spec_Workflow` 是方法论文档参考仓（只读）；`F:\Spec_Runner` 是执行器，其 `sessions/` 是设计内的状态目录，不属于“修改外部参考仓”。

---

## 3. 方案对比

### 3.1 Type-1 / Type-2 判定

| 类别 | 判据 | 本轮判定 |
|------|------|----------|
| Type-2（可逆） | 有回退点 / 无常驻副作用 | **✅**：删除 `scripts/spec_runner_adapter.py` + 测试文件、还原 `docs/` 即完全回退；不改变运行时、公开接口、真值源或门禁 |
| Type-1（不可逆） | 无回退点 / 变更真值源或契约 | ☐ |

> 依据 `docs/SPEC_STANDARD.md` §11.8.1：Type-2 不启用 7 维矩阵，改为「先做再改 + 记录决策」。以下保留候选、拒绝理由与代价。

### 3.2 候选与裁决

| 候选 | 描述 | 优点 | 缺点 / 代价 | 裁决 |
|------|------|------|-------------|------|
| **A. 官方 adapter 落 `scripts/`** | 复制 `templates/spec_runner_adapter.py`，只改配置区 | 与 README 接入路径一致；零逻辑复制；可直接 `probe`；退出码透传可进 CI | 新增 1 个仓内脚本 + 1 个测试文件；新增 T1 档位成本 | **采纳** |
| B. 零落仓，直接调用 `spec_runner.py gate` | 不新增文件，命令里手写 `--name/--cmd/--session/--cwd` | 零仓内改动；最快 | 每次手写 session 命名与 cwd；易漏参数；团队不可复用 | 拒绝：可维护性低于 A，代价是重复命令 |
| C. 项目内自研封装 / 复制 runner 逻辑 | 在 `scripts/` 重写 gate 执行与事件流 | 可定制 | 与上游双实现漂移；违背 S4「不复制 runner 逻辑、不改 gate 语义」；维护面翻倍 | 拒绝：与框架定位冲突 |

**被拒方案代价**：B 的代价 = 每次门禁需人工拼 4 个参数，且无固定前缀；C 的代价 = 两套 gate 语义长期分叉，升级需双改。

---

## 4. 风险识别

| 风险 | 触发条件 | 缓解策略 |
|------|----------|----------|
| R1 外部仓自动提交 | 每次 `gate` 运行 | 承认并记录：runner 仅 `git add -A sessions`；运行前后用 `git -C F:\Spec_Runner status --short` 取证；不动源码 |
| R2 解释器漂移 | 默认 `python` 指向 Anaconda 3.13.5 | 门禁命令**显式固定** Python312 路径；记录 U-005 |
| R3 已知红基线混入门禁 | black 75 文件 / mypy 168 errors | 注册为**预期 fail**，在清单中写基线读数，不把 fail 伪装成 pass；TD-9 完成后自然转绿 |
| R4 长门禁阻塞交互 | `unit-tests` 约 19 秒 | 仅作为批末/审查轮门禁，不挂 pre-commit；需要快速反馈时用 `probe` |
| R5 同日 session 复用 | 同日重复跑同名 gate | runner 对 gate 是 append-only（源码 L186-L188 模板注释）；用 `status`/`replay` 复核 seq 单调 |
| R6 Runner 不可用 | 路径被移动 / 环境重建 | adapter 找不到 RUNNER 返回 127；降级为直接运行等价命令并标 `[未取证]` |

> 已知风险 6 项 ≥ 3；未知风险：Windows `cmd.exe` 与 `set VAR=&&` 语法差异，由 Step 9 实测探测（不靠推测）。

---

## 5. 调研结论

1. **采纳方案 A**：复制官方 adapter，仅改 `RUNNER / PREFIX / CWD / GATES` 四处。
2. **配置基线**：`RUNNER=F:\Spec_Runner\spec_runner.py`；`PREFIX=factorv3`；`CWD=None`（自动取 `scripts/` 父目录 = 仓库根）；`GATES` 含 `probe / unit-tests / black-check / mypy-check`。
3. **门禁预期**：`probe` pass、`unit-tests` pass（503）、`black-check` fail（75 文件基线）、`mypy-check` fail（168 errors 基线）。
4. **关键假设**：
   - A1：本机 Python312 路径稳定（`C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`）；
   - A2：`F:\Spec_Runner` 可执行且其 `sessions/` 可写；
   - A3：同日同名 gate 采用 append-only 复用，不要求唯一 session。
5. **下一步**：进入 Step 3 设计（接口、错误处理、回退点）。

---

## 6. 来源验证表（Step 2 Review）

| 引用 | ID / 路径 | 验证方式 | 状态 |
|------|-----------|----------|------|
| S1 | `F:\Spec_Runner\README.md` | 读回原文 + `git -C F:\Spec_Runner rev-parse HEAD` = `60ab3e3` | 已验证（T1） |
| S2 | `F:\Spec_Runner\spec_runner.py` | 读回 L38-L40、L106-L132、L196-L281 | 已验证（T1） |
| S3 | `SPEC_RUNNER_DESIGN.md` | 读回 L21-L97；commit `bf83e48` | 已验证（T1） |
| S4 | `templates/spec_runner_adapter.py` | 读回配置区 L46-L72 与编排 L82-L224 | 已验证（T1） |
| S5 | `templates/examples/spec_workflow_adapter.py` | 读回 L73-L104 | 已验证（T1） |
| P1-P8 | 本仓/本机命令 | 逐条 E1 命令重跑 | 已验证（E1） |

**Review 结论**：5 个外部来源均可解析且与原文一致；无虚构版本/路径；本仓 8 条事实均有 E1 读数。通过 Step 2 闸门。
