# Spec_Runner 接入 · 实施文档

> **文档编号**: IMPL_spec_runner_integration
> **阶段**: Phase 2 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-04
> **状态**: 已完成（Step 6 Review 通过）
> **上游**: [DESIGN_spec_runner_integration.md](DESIGN_spec_runner_integration.md)
> **下游**: [CHECKLIST_spec_runner_integration.md](CHECKLIST_spec_runner_integration.md)

---

## 1. 任务分解

| Task | 内容 | 文件 | 测试 | 预计规模 |
|------|------|------|------|----------|
| T-1 | 先写失败测试：配置表、前缀、cwd、命令装配、未知门禁、dry-run、解释器固定 | `tests/test_spec_runner_adapter.py`（新增） | 自身 | ~90 行 |
| T-2 | 复制官方模板并只改配置区 | `scripts/spec_runner_adapter.py`（新增） | T-1 | 模板 228 行 + 配置改动 |
| T-3 | 运行 4 个门禁并把 verdict 入流 | 无新文件 | `probe / unit-tests / black-check / mypy-check` | — |
| T-4 | 重放校验与派生视图 | 无新文件 | `replay` / `status` | — |
| T-5 | 回写台账与开发日志 | `docs/PROGRESS.md`、`docs/DEVLOG.md`、`CHANGELOG.md` | 无 | 3 处 |

## 2. 工程细节

### 2.1 版本约束

| 组件 | 版本 / 路径 | 证据 |
|------|-------------|------|
| Python（门禁） | `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10） | P3/P4/P5 |
| 项目 Python 下界 | `requires-python >=3.10` | `pyproject.toml` |
| Spec_Runner | v1.0.0 @ `60ab3e3` | `spec_runner.py` L25 |
| pytest | 基线 503 passed | P3 |
| black | 26.5.0 | P4 |
| mypy | 2.1.0 | P5 |

### 2.2 文件结构

**新增**

- `scripts/spec_runner_adapter.py`：官方模板 v1.0 + 本项目配置区。
- `tests/test_spec_runner_adapter.py`：配置与命令装配的单元测试。

**修改**

- `docs/PROGRESS.md`：新增本批行与 U-006（若出现新的未决项）。
- `docs/DEVLOG.md`：追加本批条目。
- `CHANGELOG.md`：Docs 段追加接入条目。

### 2.3 接口签名（与模板一致，不新增函数）

```python
def _runner_cmd() -> list: ...
def _session_for(name: str) -> str: ...          # f"{PREFIX}-{name}-{yyyymmdd}"
def _build_gate_cmd(args, name: str) -> list: ...  # 未知门禁 → stderr + SystemExit(2)
def _build_run_cmd(args) -> list: ...
def _run(argv_override=None) -> int: ...
def _exec_gate(args) -> int: ...
def _exec_run(args) -> int: ...
def _exec(cmd: list) -> int: ...                 # FileNotFoundError → 127
def _action_cmd(args) -> list: ...               # dry-run 用
```

**配置区（唯一改动）**

```python
RUNNER = r"F:\Spec_Runner\spec_runner.py"
PREFIX = "factorv3"
CWD = None
GATES = {
    "probe": "echo Spec_Runner OK",
    "unit-tests": 'set MPLBACKEND=Agg&& "<PY312>" -m pytest tests -q',
    "black-check": '"<PY312>" -m black --check core tests 2>&1',  # runner 只捕获 stdout
    "mypy-check": '"<PY312>" -m mypy --explicit-package-bases core',
}
```

`<PY312>` 为绝对路径，实施时以实际字符串写入。

### 2.4 性能注意事项

- 不做逐文件扫描或网络请求；adapter 只做参数装配。
- `unit-tests` 约 19 秒，属预期；不在每次编辑后自动触发。
- 事件流写入由 runner 负责（单行 + flush），adapter 不重复写。

### 2.5 测试策略

**单元测试（不启动真实 subprocess）**

| 编号 | 断言 |
|------|------|
| U1 | `GATES` 键集合 = `{probe, unit-tests, black-check, mypy-check}` |
| U2 | `PREFIX == "factorv3"`；`DEFAULT_CWD` = 仓库根 |
| U3 | `_build_gate_cmd` 产出含 `gate --name --cmd --session --cwd`；session 形如 `factorv3-probe-YYYYMMDD` |
| U4 | 未知门禁触发 `SystemExit(2)` |
| U5 | `dry-run gate unit-tests` 返回 0 且打印 `DRY-RUN:`，不调用 `_exec` |
| U6 | `unit-tests/black-check/mypy-check` 命令均含 Python312 绝对路径（防解释器漂移） |

**集成验收（Step 9/10 执行，不作为单元测试）**

- 4 个门禁各跑 1 次，读取 `verdict/exit`；
- `replay` 校验 `probe` session；
- `status` 读取 gate 通过态；
- 全量 pytest 回归。

### 2.6 测试先行（红→绿）记录要求

1. 先创建 `tests/test_spec_runner_adapter.py`；
2. 运行 `pytest tests/test_spec_runner_adapter.py -q`，记录 import 失败（RED）；
3. 再创建 adapter；
4. 重跑，记录通过（GREEN）；
5. 全量回归。

## 3. Review 记录（Step 6）

| 检查项 | 结果 |
|--------|------|
| 路径可实现性 | `scripts/` 与 `tests/` 均存在；新增路径不与现有文件冲突 |
| 版本可查 | runner v1.0.0 / black 26.5.0 / mypy 2.1.0 / Python312 均有 E1 读数 |
| 命令可构造 | 4 条命令均由 `dry-run` 预演后才实际执行 |
| 签名可实现 | 全部函数来自官方模板，无自造 API |
| 测试覆盖 | U1-U6 覆盖配置、装配、错误、dry-run、解释器固定 |
| 回退点 | 删除 2 个新文件 + 还原 3 个文档 |

**发现并修复**：

1. 初稿把 `unit-tests` 写成裸 `pytest tests -q`，会在默认 `python`（Anaconda 3.13.5）下收集失败；已改为固定 Python312 并加 `MPLBACKEND=Agg`。
2. 初稿未说明 `mypy` 需 `--explicit-package-bases`；已补入命令与版本表。

**结论**：通过 Step 6 闸门，可进入 Step 7 验收清单。
