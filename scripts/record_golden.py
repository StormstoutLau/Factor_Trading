"""P-013：golden 基线录制脚本（DESIGN §7 D6 / IMPL T-5）。

用法::

    python scripts/record_golden.py                # 录制全部 6 个 case
    python scripts/record_golden.py --case G1 G3   # 只录制指定 case
    python scripts/record_golden.py --force        # 允许脏工作区（JSON 记 dirty=true）

**边界（A20）**：golden 只锁「当前行为」，不证明正确性。录制完成后必须人工核对
打印的 metrics / nav / trades 摘要，确认它们是被认可的当前行为，再提交
``tests/golden/*.json`` 的 diff。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from _golden_cases import CASE_IDS, build_case  # noqa: E402


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _is_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return bool(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _has_non_finite(obj) -> bool:
    if isinstance(obj, dict):
        return any(_has_non_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_has_non_finite(v) for v in obj)
    if isinstance(obj, float):
        return not (obj == obj and obj not in (float("inf"), float("-inf")))
    return False


def _print_summary(payload: dict) -> None:
    m = payload["metrics"]
    n = payload["nav"]
    t = payload["trades"]
    print(
        f"  metrics: total_return={m['total_return']:.10f} "
        f"annual_return={m['annual_return']:.10f} "
        f"vol={m['annual_volatility']:.10f} "
        f"sharpe={m['sharpe_ratio']:.10f} "
        f"mdd={m['max_drawdown']:.10f} "
        f"final={m['final_value']:.4f}"
    )
    print(
        f"  nav: len={n['length']} first={n['first']:.4f} "
        f"last={n['last']:.4f} min={n['min']:.4f} max={n['max']:.4f}"
    )
    print(
        f"  trades: count={t['count']} amount={t['total_amount']:.4f} "
        f"cost={t['total_cost']:.4f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="录制 golden 基线（P-013）")
    parser.add_argument(
        "--case", nargs="+", choices=list(CASE_IDS), default=list(CASE_IDS), help="要录制的 case"
    )
    parser.add_argument("--force", action="store_true", help="允许脏工作区录制（JSON 记 dirty）")
    parser.add_argument("--out-dir", default=str(GOLDEN_DIR), help="输出目录")
    args = parser.parse_args(argv)

    if os.environ.get("CI", "").lower() in ("1", "true", "yes"):
        print("[拒绝] 检测到 CI 环境：基线必须在本地录制，避免用 py_func 路径结果覆盖本地基线")
        return 1

    dirty = _is_dirty()
    if dirty and not args.force:
        print("[拒绝] 工作区不干净：请先提交或使用 --force（U-G2=A）")
        return 1
    if dirty:
        print("[警告] 工作区不干净，基线将标记 dirty=true")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    commit = _git_commit()
    print(f"录制基线：commit={commit} dirty={dirty} cases={args.case}")

    for case_id in args.case:
        with tempfile.TemporaryDirectory(prefix=f"golden_{case_id}_") as tmp:
            payload = build_case(case_id, Path(tmp))

        payload["git_commit"] = commit
        payload["python_version"] = sys.version.split()[0]
        payload["dirty"] = dirty
        payload["numba_available"] = _numba_available()

        if _has_non_finite(payload):
            print(f"[失败] {case_id} 含非有限数值，拒绝写入")
            return 2

        path = out_dir / f"{case_id}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"[已写入] {path.relative_to(REPO_ROOT)}")
        _print_summary(payload)

    print("录制完成。请人工核对上述摘要，再提交 tests/golden/ 的 diff。")
    return 0


def _numba_available() -> bool:
    try:
        import numba  # noqa: F401
    except ImportError:
        return False
    return not os.environ.get("NUMBA_DISABLE_JIT")


if __name__ == "__main__":
    raise SystemExit(main())
