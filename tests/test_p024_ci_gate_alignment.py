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
