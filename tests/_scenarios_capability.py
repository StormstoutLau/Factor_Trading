"""P-059 能力边界声明（DESIGN §10 / Step 5 T6）。

8 键全量：缺一即缺口（``assert_capability_declared`` 做键集等值断言）。
``supported`` 表示「当前引擎是否建模该能力」，``note`` 为报告口径说明。
"""

from __future__ import annotations

from typing import Any

CAPABILITY_BOUNDARIES: dict[str, dict[str, Any]] = {
    "timeframe": {
        "supported": False,
        "note": "仅日线 bar；无分钟/逐笔，日内路径不可验证",
    },
    "intraday_auction": {
        "supported": False,
        "note": "集合竞价未建模，按开盘价直接成交",
    },
    "intraday_halt": {
        "supported": False,
        "note": "盘中临停未建模（仅日频 suspend 标记）",
    },
    "delist_period_no_limit": {
        "supported": False,
        "note": "退市整理期首日无涨跌幅未实现（special_no_limit_mask 仅覆盖 IPO 前 5 日）",
    },
    "expiry_basis": {
        "supported": True,
        "note": "挂单过期按自然日（max_pending_days_buy=5 / sell=10）",
    },
    "alpha_claim": {
        "supported": False,
        "note": "场景验证只锁行为与账目，不构成任何 alpha/收益声明",
    },
    "execution_price": {
        "supported": True,
        "note": "默认开盘价成交（ExecutionPriceType.OPEN），收盘价仅用于估值/强平",
    },
    "limit_price_rounding": {
        "supported": True,
        "note": "涨跌停价按浮点直乘，不做 0.01 元四舍五入（E01 锁定）",
    },
}
