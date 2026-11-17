# IMPL：P-040 bse 规则表日期维度补齐

> **批次**: P-040 · **Step 5 实施规划** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py`）
> **上游**: [DESIGN_p040](DESIGN_p040_bse_limit_rule_gap.md)（D1-D4 / I1-I6 / §7 Step 4 复审 pass：1 P2 + 2 P3）
> **代码证据时点**: HEAD `fb32ac0`

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 代码 1 | `filter/limit_rules.py`：bse 段 2 → 4 条 + 版本行（**1 处，约 +6/−2**） |
| 测试 1 | `tests/test_p040_bse_limit_rule_gap.py`（新建，6 用例） |
| 零改动面 | `filter/universe_filter_clean.py` / `core/**` / `tests/_synth_fixture.py` / `tests/golden/**` / `pyproject.toml` / `uv.lock` / 门禁双载体 |
| 门禁 | pytest **765 → 771** / golden 13 零重录 / mypy 12 面 0 / black **123**（全仓 **190**）/ AST **22** / `uv lock` exit 0 |

**四条前提**：① `infer_board` / `resolve_limit` / `build_limit_prices` 签名零变更；② 不新增 `except` / `raise` / `# type: ignore`；③ 其余 9 条 board 规则逐字不动；④ 不清理 `_RULE_INDEX`（O-P040-5）。

---

## 2. 精确变更规格

### 2.1 `filter/limit_rules.py` L67-69 → 4 条 + 注释

**改前**：

```python
    # 北交所：30%（U-D3：ST 闭合行同 30%）
    LimitRule("bse", False, pd.Timestamp("2021-11-15"), None, 0.30, -0.30),
    LimitRule("bse", True, pd.Timestamp("2021-11-15"), None, 0.30, -0.30),
```

**改后**：

```python
    # 北交所（含前身）：新三板创新层/基础层集合竞价（涨幅 100% / 跌幅 50%，2018-01-15 起）
    # → 精选层 ±30%（2020-07-27 开市）→ 北交所 ±30%（2021-11-15 开市，同一 30% 段延续）
    LimitRule("bse", False, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
    LimitRule("bse", False, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
    LimitRule("bse", True, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
    LimitRule("bse", True, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
```

### 2.2 `filter/limit_rules.py` L19

**改前**: `RULESET_VERSION = "cn_a_2026_07"`
**改后**: `RULESET_VERSION = "cn_a_2026_11"`

### 2.3 `tests/test_p040_bse_limit_rule_gap.py`（新建，完整代码）

```python
"""P-040 bse 规则表日期维度补齐回归测试（U-P039-4）。

覆盖：新三板集合竞价段 / 精选层边界 / 北交所期不变 / pre-2018 fail-fast /
全窗口可解析 / build_limit_prices 复牌首日不限制。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filter.limit_rules import (
    RULESET_VERSION,
    LimitRuleError,
    build_limit_prices,
    resolve_limit,
)

PRE_END = pd.Timestamp("2020-07-26")
SEG_START = pd.Timestamp("2020-07-27")
BSE_START = pd.Timestamp("2021-11-15")


def test_v1_neeq_auction_limits():
    """V1：新三板创新层/基础层集合竞价段 +100% / −50%。"""
    for is_st in (False, True):
        rule = resolve_limit("bse", is_st, PRE_END)
        assert (rule.up, rule.down) == (1.00, -0.50)


def test_v2_selection_layer_boundary():
    """V2：2020-07-27 起进入精选层 ±30%（半开区间边界）。"""
    for is_st in (False, True):
        rule = resolve_limit("bse", is_st, SEG_START)
        assert (rule.up, rule.down) == (0.30, -0.30)


def test_v3_bse_unchanged_and_version():
    """V3：北交所期维持 30%；C2 版本口径为 cn_a_2026_11。"""
    assert RULESET_VERSION == "cn_a_2026_11"
    for d in (BSE_START, pd.Timestamp("2023-06-01")):
        for is_st in (False, True):
            rule = resolve_limit("bse", is_st, d)
            assert (rule.up, rule.down) == (0.30, -0.30)


def test_v4_pre_2018_fail_fast():
    """V4：2018-01-15 之前仍无规则 → fail-fast（不回落默认值）。"""
    with pytest.raises(LimitRuleError, match="无匹配涨跌停规则"):
        resolve_limit("bse", False, pd.Timestamp("2018-01-12"))


def test_v5_window_fully_resolvable():
    """V5：真实数据窗口 2020-01-23..2021-11-12 逐日 × 两态均可解析（436 日缺口 → 0）。"""
    dates = pd.bdate_range("2020-01-23", "2021-11-12")
    for d in dates:
        for is_st in (False, True):
            assert resolve_limit("bse", is_st, d) is not None


def test_v6_build_limit_prices_no_raise_and_resume_day_unlimited():
    """V6：不抛错；前收 NaN（停牌复牌首日）不限制；集合竞价段 10 → 20 / 5。"""
    dates = pd.DatetimeIndex(["2020-07-22", "2020-07-23", "2020-07-27"])
    close = pd.DataFrame({"832317": [10.0, np.nan, 13.35]}, index=dates)
    adj = pd.DataFrame({"832317": [1.0, 1.0, 1.0]}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    assert up.shape == (3, 1) and down.shape == (3, 1)
    # 2020-07-23：前收 10，集合竞价段 +100% / −50%
    assert up.loc[dates[1], "832317"] == pytest.approx(20.0)
    assert down.loc[dates[1], "832317"] == pytest.approx(5.0)
    # 2020-07-27：前收 NaN（停牌）→ 不限制
    assert np.isnan(up.loc[dates[2], "832317"])
    assert np.isnan(down.loc[dates[2], "832317"])
```

---

## 3. 红态（修复前预期）

| 用例 | 修复前 | 预期 |
|------|--------|------|
| V1 | `resolve_limit("bse", ..., 2020-07-26)` → `LimitRuleError` | **FAIL** |
| V2 | 同上（2020-07-27） | **FAIL** |
| V3 | 版本断言失败（旧 `cn_a_2026_07`）；30% 部分通过 | **FAIL** |
| V4 | 仍抛 `LimitRuleError` | **PASS**（回归保护） |
| V5 | 2020-01-23 即抛 | **FAIL** |
| V6 | `build_limit_prices` 在 2020-07-23 抛 | **FAIL** |

**预期红态**: `5 failed, 1 passed`（V1/V2/V3/V5/V6 FAIL；V4 PASS）。
> **Step 9 实测订正（F-S9-P040-1）**: 初稿汇总行误写 `4 failed, 2 passed`（漏计 V3 的版本断言失败）；实测为 **`5 failed, 1 passed in 0.85s`**，与逐用例预期一致。

---

## 4. 门禁终态（Step 9 实测）

| 项 | 目标 | 实测 |
|----|------|------|
| pytest | 771 | ✅ `771 passed, 172 warnings in 85.24s` |
| golden | 13·752 零重录 | ✅ `13 passed, 758 deselected`；`tests/golden/` 空 |
| mypy 12 面 | 103 files 0 | ✅ `Success: no issues found in 103 source files` |
| black | 123 / 190 | ✅ `123 files would be left unchanged` / `190 files would be left unchanged` |
| AST | 22 | ✅ **22**（P-029 十文件口径） |
| `tests/*.py` | 86 | ✅ 86 |
| `uv lock --check` | exit 0 | ✅ exit 0 |
| 新增 `except` / `raise` / `# type: ignore` | 0 / 0 / 0 | ✅ `git diff -U0` 过滤均 0；`^[+-]\s*def ` = **0** |
| 代码变更面 | 1 文件 | ✅ `7 4 filter/limit_rules.py`（+7/−4） |

---

## 5. 回退点

单提交 revert → 回到 11 条规则（`LimitRuleError` 复现）；无跨批依赖。

---

## 6. Step 6 实施 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P040-1 累计第 3 轮。

### 6.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 2.1 与 DESIGN-D1 逐字 | 4 行/注释/日期一致 | ✅ |
| A | 版本行 | `cn_a_2026_11` | ✅ |
| B | V6 数值可解析 | `ref(07-23)=10` → up 20 / down 5；`ref(07-27)=NaN` | ✅（F-S4-P040-1 已回写） |
| B | V5 日期范围 | `bdate_range` 含 2020-01-23 与 2021-11-12 | ✅ |
| C | 红态可复现性 | 修复前 V1/V2/V3/V5/V6 均因缺口/版本失败；V4 通过 | ✅（4F/2P） |
| D | 既有测试 | `test_limit_rules.py` 全部 2022+ 日期 | ✅ |
| E | 计数 | 765+6=771；122+1=123；189+1=190 | ✅ |

### 6.2 发现与当轮处置（0 P1 + 1 P2 + 1 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P040-1** | **P2** | V6 的 `close` 第二行设为 `NaN` 会同时使 07-23 的 `ref` 为 10（正常），但 `open` 未参与；若未来 `build_limit_prices` 改用 `open` 作 `ref`，断言将失真 | 在测试 docstring 显式写明依赖 `ref=close.shift(1)` 口径（已含）；不改代码（口径属既有契约） |
| F-S6-P040-2 | P3 | V3 把版本断言与北交所期断言合并，失败时定位不直观 | 保留合并（避免第 7 用例），docstring 已写明双重目的 |
| F-S6-P040-3 | P3 | 红态表中 V3「30% 部分通过」表述模糊 | 改为「版本断言失败（旧值）；30% 部分通过」 |

### 6.3 结论

**Step 6 Review pass（1 P2 + 1 P3 当轮回写）**——规格与 DESIGN 逐字一致、红态可复现、计数自洽；**准予进入 Step 7 CHECKLIST**。
**RULE-5**：第 3 轮同基座 → U-P040-1 pending。

---

## 7. Step 9 实施记录（2026-11-17）

| 项 | 读数 |
|----|------|
| 落码 | [limit_rules.py:19](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L19) 版本行 + [L67-72](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L67-L72) bse 四段；**+7/−4** |
| 测试 | [tests/test_p040_bse_limit_rule_gap.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p040_bse_limit_rule_gap.py) 新建（6 用例） |
| 红态 | **`5 failed, 1 passed in 0.85s`**（V1/V2/V3/V5/V6 FAIL；V4 PASS） |
| 绿态 | **`6 passed in 0.58s`**；既有 `test_limit_rules.py` **7 passed** |
| 门禁 | 见 §4（771 / 13·758 / 123·190 / 103 files 0 / AST 22 / 86 / uv 0） |
| 真实数据（D4） | `resolve_limit("bse", False, 2020-07-26)` = `(1.00, −0.50)`；`2020-07-27` = `(0.30, −0.30)`；`engine.setup()` **推进到** `FileNotFoundError: 因子文件不存在: ...UTR_turnover_new.pkl`（U-P038-1），**不再抛 `LimitRuleError`** |

### 7.1 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P040-1 | P3 | §3 汇总行初写 `4 failed, 2 passed`，漏计 V3 版本断言 → 实测 `5 failed, 1 passed` | 本文件 §3 已订正 |
| F-S9-P040-2 | P3 | V6 首行（2020-07-22）`ref` 为 NaN（无前收），断言只覆盖 07-23/07-27 两行 | 保持（首行 NaN 属既有契约，`test_limit_rules` 已覆盖首行语义） |

**结论**: **Step 9 pass**——6 用例绿、九项门禁全绿、真实数据验收达标；主缺陷（U-P039-4）修复完成。