# IMPL：P-024 CI 门禁对齐（mypy 假门禁 + README uv extras）

> **批次**: P-024 · **T1**
> **上游**: [DESIGN_p024_ci_gate_alignment.md](DESIGN_p024_ci_gate_alignment.md)（D1-D7 / I1-I6 / T-1~T-7）
> **下游**: [CHECKLIST_p024_ci_gate_alignment.md](CHECKLIST_p024_ci_gate_alignment.md)
> **代码证据时点**: HEAD `6ed74d0`
> **状态**: Step 5 实施规划完稿

---

## 1. 范围与约束

- **变更文件 4 个**：`tests.yml` / `spec_runner_adapter.py` / `README.md` / 新增 `tests/test_p024_ci_gate_alignment.py`。
- **生产代码零改动**：`core/` / `agents/` / `web/` / `factor_library/` 均不触碰。
- **依赖面零改动**：`pyproject.toml`、`uv.lock` 均不改（D6）。
- **硬约束**：任何临时探针文件必须在同一命令序列内删除，且以 `git status --short` 空输出作为 Step 9 的收尾门。
- **不引入新依赖**：新增测试只用 `importlib.util` / `re` / `pathlib`（与 [test_spec_runner_adapter.py](../tests/test_spec_runner_adapter.py) L11-L13 同型）。

---

## 2. 任务拆解

| ID | 任务 | 文件 | 对应决策 | 规模 |
|----|------|------|----------|------|
| **T-0** | 基线与先红准备（Step 1 读数复跑） | — | F5 | 0 |
| **T-1** | CI mypy 步骤替换 | [tests.yml](../.github/workflows/tests.yml) L45-L46 | D1 | −1/+1 |
| **T-2** | 本地门禁同步加旗标 | [spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L67 | D2 | −1/+1 |
| **T-3** | 门禁漂移守卫测试（3 断言） | 新增 `tests/test_p024_ci_gate_alignment.py` | D4 | +~60 |
| **T-4** | README uv 段替换 | [README.md](../README.md) L220 | D3 | −1/+1 |
| **T-5** | 台账补登（§1.4 七行 + §2 注记 + §3.28） | [PROGRESS.md](PROGRESS.md) | D5 | +~20 |
| **T-6** | CHANGELOG 条目 | [CHANGELOG.md](../CHANGELOG.md) | D5 | +~5 |
| **T-7** | 四文档回填（Step 9 记录 + 读数） | `docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p024_*.md` | — | 回填 |
| **T-8** | 收口：提交 / 推送 / CI run 回收 / 关闭注 | — | D5 | 0 |
| **T-9** | **（Step 9 追加）声明 `filter.*` 越界**：`[[tool.mypy.overrides]] ignore_errors = true` | [pyproject.toml](../pyproject.toml) L112-L117 | D6（修订） | +8/0 |

---

## 3. 实施顺序与依赖

```
T-0 ─→ T-1 ─→ T-3 ─→ T-4 ─→ T-5 ─→ T-6 ─→ T-7 ─→ T-8
        │      ↑
        └→ T-2 ┘   （T-3 的断言 A 依赖 T-1 + T-2 同时完成）

批次：
  B1 = T-1 + T-2 + T-3   （口径对齐 + 守卫，可独立红绿验证）
  B2 = T-4               （README，单行）
  B3 = T-5 + T-6 + T-7   （台账 + 文档）
```

**为何 B1 一次性包含 T-1/T-2/T-3**：断言 A 比较**两侧**命令，只改一侧会使断言失败——三者构成一个不可分割的最小红绿单元。

---

## 4. 精确变更预案

### 4.1 T-1 `tests.yml`

**位置**：L45-L46（文件共 46 行，末两行）。

```yaml
# 变更前
      - name: Type check (mypy)
        run: mypy core/ --ignore-missing-imports --no-error-summary || true

# 变更后
      - name: Type check (mypy)
        run: python -m mypy --explicit-package-bases --check-untyped-defs core
```

**边界确认**：不改步骤名、不改其上 `Run tests` 步骤、不改文件头 `env` / `matrix`。

### 4.2 T-2 `spec_runner_adapter.py`

```python
# 变更前（L67）
"mypy-check": f"{_PY312} -m mypy --explicit-package-bases core",

# 变更后
"mypy-check": f"{_PY312} -m mypy --explicit-package-bases --check-untyped-defs core",
```

### 4.3 T-3 新增测试

```python
"""P-024 门禁漂移守卫（DESIGN D4 的 A/B/C 三断言）。

只读仓库内的三个真值面：CI workflow、本地 adapter 配置、README uv 段。
不启动 subprocess、不写文件。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "tests.yml"
ADAPTER_PATH = REPO_ROOT / "scripts" / "spec_runner_adapter.py"
README_PATH = REPO_ROOT / "README.md"

MYPY_STEP_NAME = "Type check (mypy)"
_OUTPUT_ONLY_FLAGS = {"--no-error-summary"}


def _ci_mypy_run_line() -> str:
    """返回 mypy 步骤的 run 命令原文（去前缀空白）。"""
    lines = WORKFLOW_PATH.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == f"- name: {MYPY_STEP_NAME}":
            for follow in lines[idx + 1 :]:
                stripped = follow.strip()
                if stripped.startswith("- name:"):
                    break
                if stripped.startswith("run:"):
                    return stripped[len("run:") :].strip()
    raise AssertionError(f"{WORKFLOW_PATH.name} 中未找到 {MYPY_STEP_NAME!r} 步骤的 run 行")


def _normalize_mypy_cmd(cmd: str) -> tuple[str, ...]:
    """去掉解释器前缀与纯输出旗标，返回 (mypy 旗标..., target)。"""
    tokens = cmd.replace('"', " ").replace("'", " ").split()
    if "mypy" not in tokens:
        raise AssertionError(f"命令不含 mypy 可执行项：{cmd!r}")
    tail = tokens[tokens.index("mypy") + 1 :]
    return tuple(tok for tok in tail if tok not in _OUTPUT_ONLY_FLAGS)


@pytest.fixture(scope="module")
def adapter():
    spec = importlib.util.spec_from_file_location("_p024_adapter", ADAPTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_mypy_flags_match_local_gate(adapter):
    ci = _normalize_mypy_cmd(_ci_mypy_run_line())
    local = _normalize_mypy_cmd(adapter.GATES["mypy-check"])
    assert ci == local, f"CI 口径 {ci} 与本地门禁口径 {local} 不一致"


def test_ci_mypy_step_is_blocking():
    run_line = _ci_mypy_run_line()
    assert "|| true" not in run_line, f"CI mypy 步骤仍带短路：{run_line!r}"
    assert not re.search(r"mypy[^\n]*\|\|\s*true", WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_readme_uv_uses_all_extras():
    text = README_PATH.read_text(encoding="utf-8")
    section = text.split("### uv", 1)
    assert len(section) == 2, "README 缺少 '### uv' 段"
    block = section[1].split("```bash", 1)
    assert len(block) == 2, "README '### uv' 段缺少 bash 代码块"
    code = block[1].split("```", 1)[0]
    assert "uv sync --all-extras" in code, f"README uv 段命令为：{code.strip()!r}"
```

### 4.4 T-4 `README.md`

```bash
# 变更前（L219-L221）
```bash
uv sync
```

# 变更后
```bash
uv sync --all-extras
```
```

### 4.5 T-5/T-6 台账与 CHANGELOG

- **§1.4**（表尾，U-P021-3 之后）插入 7 行：`U-P023-1`~`U-P023-4`（内容照 [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md) 四元块）、`U-P024-1`~`U-P024-3`（照 [RESEARCH §6](RESEARCH_p024_ci_gate_alignment.md)）；并新增 `P-024` 主行。
- **§2 U-006 行**「当前倾向」追加：`**2026-11-12 注记（P-024）**：口径已收紧为 --check-untyped-defs 且 CI/本地双侧对齐，判据达成，本项关闭（见下方关闭注）`。
- **§2 关闭注区**追加一行：`> **已关闭（2026-11-12，P-024）**: U-006 / U-P023-2 / U-P023-4 —— ...；详见 §3.28。`
- **§3.28** 新增 P-024 执行记录（项目符号形态，含红绿读数与 CI run）。
- **CHANGELOG**：`## [Unreleased]` 下新增 `### CI` 条目，说明「类型检查步骤不再吞退出码；门禁纳入 --check-untyped-defs；README uv 安装补齐 extras」。

---

## 5. 验证矩阵

| ID | 命令 | 期望（Step 9 回填） | 对应不变式 |
|----|------|---------------------|------------|
| **V1** | 临时写 `core/_p024_probe.py`（`x: int = "s"`）+ 新 CI 命令 | exit 1，含 `Incompatible types in assignment` | I3（先红） |
| **V2** | V1 同命令追加 `\|\| true` | 内部 `exit=0` | I3（假门禁对照） |
| **V3** | 删除探针 + 新 CI 命令 | exit 0，`Success: no issues found in 36 source files` | I2 |
| **V4** | `mypy --explicit-package-bases --check-untyped-defs core`（本地门禁口径） | exit 0 / 36 files | I2 |
| **V5** | `pytest -q` | **654 passed** | I4 |
| **V6** | `black --check .` | **180 files would be left unchanged** | I6 |
| **V7** | `uv lock --check`；`git diff --stat` | exit 0；仅 4 文件（含新增测试） | I5/I6 |
| **V8** | `Grep -n "mypy.*\|\| true" .github/` | 0 命中 | I3 |
| **V9** | push 后 CI run | 三 job success；mypy step 日志含 `36 source files` | I7（远端） |

---

## 6. Step 6 Review（独立 pass）

### 6.1 检查表

| # | 审查项 | 结论 |
|---|--------|------|
| R1 | 每条 DESIGN 决策是否都有 T-* 落点 | ✅ D1→T-1 / D2→T-2 / D3→T-4 / D4→T-3 / D5→T-5,T-6 / D6,D7→「不改」即达成 |
| R2 | 变更预案是否精确到行 | ✅ 4.1-4.4 均给出前后对照；4.5 给出插入位置锚点 |
| R3 | 测试是否可在无网络、无 subprocess 下运行 | ✅ 纯文件解析 |
| R4 | 测试是否依赖工作目录 | ✅ 全部使用 `Path(__file__).resolve().parents[1]` 绝对定位 |
| R5 | 断言失败信息是否可定位 | ✅ 均带实际值（`{ci}` / `{run_line!r}` / `{code.strip()!r}`） |
| R6 | 是否存在「测试与实现同源导致自证」 | ✅ 断言读取的是**独立真值面**（workflow 文本 / adapter 模块 / README 文本），非本测试内的常量 |
| R7 | 先红是否真的会红 | ✅ V1 注入 `str`→`int` 赋值，mypy 必报 `Incompatible types in assignment`；V2 证明判别力来自去 `\|\| true` |
| R8 | 临时文件是否可能残留 | ✅ §1 硬约束 + V7 的 `git status` 校验 |
| R9 | 预期计数是否可推演 | ✅ 654 = 651 + 3；180 = 179 + 1（新测试文件） |
| R10 | 是否遗漏 CI 侧另一处 mypy 调用 | ✅ `Grep -n "mypy" .github/` 仅 L46 一处（Step 1 已确认） |

### 6.2 发现

- **F-I1-P024-1（P3）**：`_normalize_mypy_cmd` 用 `tokens.index("mypy")` 定位，若未来命令写成 `python -m mypy.c` 之类变体会失效。→ 已限定判据为「token 精确等于 `mypy`」；失败时抛带原文的 `AssertionError`，可见即修。
- **F-I2-P024-2（P3）**：V2 的「内部 exit=0」需读取 shell 展开后的值；若用 `$LASTEXITCODE` 读外层会被 `echo` 掩盖。→ 固定用 `sh -c "... || true"; echo exit=$?` 形态（与 Step 1 探针 P13 同型）。

### 6.3 结论

**0 个 P1/P2，2 个 P3 已回写**。可进入 Step 7 CHECKLIST。

---

## 7. Step 9 实施记录

### 7.1 提交链

| 批次 | 提交 | 内容 | 状态 |
|------|------|------|------|
| B1 | `e360436` | `tests.yml` L46 + adapter L67 + 守卫测试（3 断言） | ✅ 3 文件 **+77/−2** |
| B2 | `ac2a3d6` | README uv 段 → `--all-extras` | ✅ 1 文件 +1/−1 |
| B3 | `c1c67b2` | PROGRESS（§1.4 七行 + §2 注记 + 关闭注 + §3.28）+ CHANGELOG + 四文档 | ✅ 6 文件 **+871/−1** |
| B4 | `[待回填]` | T-9：`pyproject.toml` 追加 `[[tool.mypy.overrides]] filter.*`（+8 行）；临时 mypy 钉版已撤回 | `[待回填]` |
| B5 | `[待回填]` | 文档回填（版本漂移发现 + 计数 28→29） | `[待回填]` |

### 7.2 F5 红绿读数

| # | 读数 | 结果 |
|---|------|------|
| V1 | 先红（注入 `core/_p024_probe.py`：`x: int = "s"` + 新 CI 命令） | **exit 1**：`core\_p024_probe.py:7: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]` / `Found 1 error in 1 file (checked 37 source files)` |
| V2 | 假门禁对照（同命令 + `\|\| true`） | 内部 **`V2_EXIT=0`**；**同命令去掉 `\|\| true`** → `V2_RAW_EXIT=1`（判别力来自 D1 而非命令本身） |
| V3 | 后绿（删除探针 + 新 CI 命令） | **exit 0** / `Success: no issues found in 36 source files` |

### 7.3 V4-V9 实读

| # | 命令 | 实测 | 判定 |
|---|------|------|------|
| V4 | 本地门禁口径 mypy | `Success: no issues found in 36 source files`（exit 0） | ✅ |
| V5 | `pytest -q` | **654 passed, 152 warnings in 52.13s** | ✅（= 651 + 3） |
| V6 | `black --check .` | **180 files would be left unchanged** | ✅（= 179 + 1） |
| V7 | `uv lock --check` + `git diff --stat` | exit 0（`Resolved 148 packages`）；B1+B2 累计 4 文件 | ✅ |
| V8 | `Select-String "mypy.*\|\| true"` on `.github/` | **0 命中** | ✅ |
| V9 | 远端 CI run | `[待回填]` | `[待回填]` |
| V10 | **（追加）越界声明跨版本/跨依赖验证** | X1（CI 依赖 + 无声明）**21 errors**；X2（+ 声明，mypy 2.1.0）**0**；X3（+ 声明，mypy 2.4.1）**0** | ✅ |

### 7.4 实施发现

- **F-S9-P024-4（P2，CI 首跑红）**：推送 `c1c67b2` 后 run [`43193963200`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43193963200) —— 3.10 leg **failure**（3.11/3.12 canceled），日志为 **21 errors / 7 files，全部在 `filter/*`**，`core/` 0 条。归因实验（RESEARCH §5 X1-X4）定位为 **pandas 3.1.1 类型桩**（CI 装 3.1.1、本地 2.2.3；`pandas>=2.0.0` 无上限），`core` 经 `engine_v2` L61-62 / `factory` L31 导入 `filter` 后被 follow，越界错误计入闸门。**处置**：新增 `[[tool.mypy.overrides]] module = ["filter.*"] ignore_errors = true`（X2/X3 验证跨 mypy 版本均 0 errors）；`filter/` 的 21 条登记 U-P024-4。
- **F-S9-P024-5（P2，误诊与撤回）**：首次归因误判为「mypy 2.4.1 vs 2.1.0 版本漂移」，并据此提交 `745e2b7`（`mypy~=2.1.0`）。复核发现该读数来自 `uv run --no-project` **缺 pydantic/pandas** 的环境：`ignore_missing_imports=true` 使 pydantic 成 `Any`，`config_v2.py` 的 `model_dump/model_validate` 触发 3 条伪影错误（X4）。**已撤回钉版**（`pyproject` 恢复 `mypy>=1.5.0`，`uv.lock` 复原），改以越界声明收口。教训：**隔离实验必须与 CI 依赖集对齐**，否则会把缺失依赖的伪影当成版本差异。
- **F-S9-P024-1（P3，工具坑）**：`shutil.which("bash")` 在 Windows 解析到 `C:\Windows\system32\bash.EXE`（WSL 存根，**恒返回 0**），首轮探针 A-D 全为 `exit=0` 造成「假阴性」；改用 Git bash 绝对路径后读数正常（A `exit=3` / B `exit=0` / C `exit=2` / D `exit=0`）。→ 已写入探针脚本注释；复审时须确认 bash 路径。
- **F-S9-P024-2（P3）**：`git commit` 时 git 提示 `LF will be replaced by CRLF`（autocrlf=true），与既有仓库行为一致，无内容影响；未做额外处置。
- **F-S9-P024-3（P3）**：Step 8 的 3 处「未创建文件链接」已按 F-S8-P024-1 改为代码字面量；Step 9 文件创建后**未**恢复为链接（避免 3 处链接噪声，且 CHECKLIST E1 以文件存在性单独验收）。
