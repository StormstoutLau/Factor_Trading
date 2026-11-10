"""P-015 audit_signatures：vectorbt 权威签名核验（U-P015-3，venv 内运行）。

用法:
    .venv-vbt/Scripts/python.exe scripts/external_benchmark/audit_signatures.py

输出 from_orders / from_signals 关键参数默认值 + settings.defaults —— 附录 §1 读数来源。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vectorbt as vbt  # noqa: E402

KEYS_FO = [
    "size",
    "size_type",
    "price",
    "fees",
    "fixed_fees",
    "slippage",
    "init_cash",
    "cash_sharing",
    "group_by",
    "call_seq",
    "allow_partial",
    "min_size",
    "size_granularity",
    "upto",
    "direction",
]
KEYS_FS = [
    "size",
    "size_type",
    "price",
    "fees",
    "slippage",
    "init_cash",
    "cash_sharing",
    "group_by",
    "call_seq",
    "direction",
    "upon_opposite_entry",
    "allow_partial",
]


def main() -> int:
    sig_fo = (
        vbt.Portfolio.from_orders.__wrapped__.__signature__
        if hasattr(vbt.Portfolio.from_orders, "__wrapped__")
        else None
    )
    import inspect

    sig_fo = inspect.signature(vbt.Portfolio.from_orders)
    sig_fs = inspect.signature(vbt.Portfolio.from_signals)
    print("== from_orders ==")
    for k in KEYS_FO:
        p = sig_fo.parameters.get(k)
        print(f"{k} = {p.default if p is not None else '<absent>'}")
    print("== from_signals ==")
    for k in KEYS_FS:
        p = sig_fs.parameters.get(k)
        print(f"{k} = {p.default if p is not None else '<absent>'}")
    print("== settings.portfolio defaults ==")
    for k in ("fees", "slippage", "init_cash", "size", "call_seq"):
        print(f"{k} = {vbt.settings.portfolio[k]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
