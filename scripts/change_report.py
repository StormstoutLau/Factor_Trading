#!/usr/bin/env python3
"""两次运行目录差分 CLI（P-012 D6 / T-2）。

用法：
    python scripts/change_report.py <before/> <after/> [-o report.json]

退出码：0 = residual < 1e-8 且 attribution_complete；1 = 任一不满足。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.change_report import RESIDUAL_TOL, compare_runs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="六层归因差分（P-012 change_report）")
    parser.add_argument("before", help="改前运行的 dump 目录")
    parser.add_argument("after", help="改后运行的 dump 目录")
    parser.add_argument("-o", "--output", default=None, help="报告输出路径（JSON）")
    parser.add_argument(
        "--tolerance", type=float, default=RESIDUAL_TOL, help="残差容差（默认 1e-8）"
    )
    args = parser.parse_args(argv)

    report = compare_runs(Path(args.before), Path(args.after))
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"report written to {args.output}")
    else:
        print(payload)

    ok = report.residual < args.tolerance and report.attribution_complete
    if not ok:
        print(
            f"error: residual={report.residual:.3e} attribution_complete={report.attribution_complete}",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
