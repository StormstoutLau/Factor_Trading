"""Spec_Runner adapter 接入测试（TDD 先行）。

锚点（T1）：
- `F:\\Spec_Runner\\spec_runner.py` v1.0.0 @ 60ab3e3 L325-L330（gate 参数面）
- `F:\\Spec_Runner\\templates\\spec_runner_adapter.py` v1.0 L46-L104（配置区与命令装配）
- `F:\\Spec_Runner\\README.md` L72-L88（接入三步与 probe 语义）

测试只验证配置与命令装配，不启动真实 subprocess。
"""

import importlib.util
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = REPO_ROOT / "scripts" / "spec_runner_adapter.py"


@pytest.fixture(scope="module")
def adapter():
    if not ADAPTER_PATH.exists():
        pytest.fail(f"adapter 未实现：{ADAPTER_PATH}")
    spec = importlib.util.spec_from_file_location("spec_runner_adapter", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_u1_gates_table_has_required_entries(adapter):
    assert set(adapter.GATES) == {
        "probe",
        "unit-tests",
        "black-check",
        "mypy-check",
    }


def test_u2_project_identity_and_cwd(adapter):
    assert adapter.RUNNER == r"F:\Spec_Runner\spec_runner.py"
    assert adapter.PREFIX == "factorv3"
    assert adapter.CWD is None
    assert Path(adapter.DEFAULT_CWD).resolve() == REPO_ROOT


def test_u3_build_gate_cmd_shape(adapter):
    args = types.SimpleNamespace(name="probe", session=None)
    cmd = adapter._build_gate_cmd(args, "probe")
    assert cmd[0] == adapter.sys.executable
    assert cmd[1] == adapter.RUNNER
    assert cmd[2] == "gate"
    assert cmd[cmd.index("--name") + 1] == "probe"
    assert cmd[cmd.index("--cmd") + 1] == adapter.GATES["probe"]
    session = cmd[cmd.index("--session") + 1]
    assert session.startswith("factorv3-probe-")
    assert len(session.rsplit("-", 1)[-1]) == 8
    assert cmd[cmd.index("--cwd") + 1] == adapter.DEFAULT_CWD


def test_u4_unknown_gate_exits_2(adapter, capsys):
    args = types.SimpleNamespace(name="no-such-gate", session=None)
    with pytest.raises(SystemExit) as exc:
        adapter._build_gate_cmd(args, "no-such-gate")
    assert exc.value.code == 2
    assert "unknown" in capsys.readouterr().err


def test_u5_dry_run_does_not_execute(adapter, capsys, monkeypatch):
    def _boom(cmd):
        raise AssertionError(f"dry-run 不应执行子进程：{cmd}")

    monkeypatch.setattr(adapter, "_exec", _boom)
    rc = adapter._run(["dry-run", "gate", "unit-tests"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN:" in out
    assert "--name unit-tests" in out


def test_u6_heavy_gates_pin_python312(adapter):
    for gate in ("unit-tests", "black-check", "mypy-check"):
        assert "Python312" in adapter.GATES[gate], gate
