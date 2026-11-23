"""P-055 T3：依赖方向门禁（3 契约常绿 / 负例必红 / 契约数守护，3 例）。"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lint_cmd() -> list[str]:
    """import-linter 2.x 无 ``__main__``，必须走 console script（U-D2 Step 9 校准）。"""
    scripts = Path(sys.executable).parent
    for name in ("lint-imports.exe", "lint-imports"):
        candidate = scripts / name
        if candidate.exists():
            return [str(candidate)]
    found = shutil.which("lint-imports")
    assert found is not None, "lint-imports 不可用：环境错误（RULE-3 不 skip）"
    return [found]


def _run_lint(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*_lint_cmd(), "--no-cache"],  # 不在仓库/负例目录留下 .import_linter_cache
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def test_repo_contracts_pass():
    assert (
        importlib.util.find_spec("importlinter") is not None
    ), "import-linter 未安装：这是环境错误，不是可跳过条件（RULE-3）"
    result = _run_lint(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_negative_fixture_fails():
    assert importlib.util.find_spec("importlinter") is not None
    fixture = ROOT / "tests" / "fixtures" / "arch_violation"
    result = _run_lint(fixture)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "violation_app.core" in output


def test_three_contracts_declared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = data["tool"]["importlinter"]["contracts"]
    assert len(contracts) >= 3
    names = " ".join(contract["name"] for contract in contracts)
    assert "C1" in names and "C2" in names and "C3" in names
