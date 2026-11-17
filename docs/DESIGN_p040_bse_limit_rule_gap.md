# DESIGN：P-040 bse 规则表日期维度补齐

> **批次**: P-040 · **Step 3 设计** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py` 行为变更）
> **上游**: [RESEARCH_p040](RESEARCH_p040_bse_limit_rule_gap.md)（§7 M-A 裁决 / §8 S1-S7 / §9 C1-C2 / §14 Step 2 复审 pass：2 P2 + 3 P3）
> **代码证据时点**: HEAD `fb32ac0`

---

## 1. 范围

| 项 | 内容 |
|----|------|
| 变更文件（代码 1） | `filter/limit_rules.py`：`RULES` 的 bse 段（2 条 → 4 条）+ `RULESET_VERSION` |
| 变更文件（测试 1） | `tests/test_p040_bse_limit_rule_gap.py`（**新建**，6 用例） |
| 变更文件（文档） | 本文件 / `docs/IMPL_p040_*` / `docs/CHECKLIST_p040_*` / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `filter/universe_filter_clean.py`（try 范围）/ `core/**` / `tests/_synth_fixture.py` / `tests/golden/**` / `pyproject.toml` / `uv.lock` / 门禁双载体 |
| 门禁口径 | pytest **765 → 771** / golden **13 零重录** / mypy 12 面 **0** / black **122 → 123**（全仓 **189 → 190**）/ AST `except Exception` 恒 **22** / `uv lock` exit 0 |

---

## 2. 设计决策

### D1 规则表变更（唯一代码改动点）

[limit_rules.py:67-69](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L67-L69) 的 2 条 bse 规则替换为 4 条：

```python
    # 北交所（含前身）：新三板创新层/基础层集合竞价（涨幅 100% / 跌幅 50%，2018-01-15 起）
    # → 精选层 ±30%（2020-07-27 开市）→ 北交所 ±30%（2021-11-15 开市，同一 30% 段延续）
    LimitRule("bse", False, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
    LimitRule("bse", False, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
    LimitRule("bse", True, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
    LimitRule("bse", True, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
```

- `RULESET_VERSION`：`"cn_a_2026_07"` → `"cn_a_2026_11"`（规则集修订标记；非监管生效日）。
- 模块 docstring L5 的「8/4 开头→bse」保持不变（`infer_board` 契约不动），在 D3 声明语义沿革。

### D2 精确语义（与 RESEARCH §8 一致）

| # | 语义 |
|---|------|
| S1 | 区间半开：`2020-07-26` → 第一段；`2020-07-27` → 第二段 |
| S2 | `is_st` 两态同参（`build_limit_prices` 无条件查询 True，必须各有 1 条） |
| S3 | 2018-01-15 起命中恒 1 条；**早于 2018-01-15 仍抛 `LimitRuleError`**（fail-fast 保留） |
| S4 | 首日不设涨跌幅不新增代码：前收 `NaN` → `ref` `NaN` → 掩码不限制（实测 `833874` −30.70%） |
| S5 | 做市/集合竞价不可辨 → 统一按集合竞价上界（+100/−50），宽松不产生伪拦截 |

### D3 不扩做（五项）

1. **不改 `infer_board` 签名**（`830001`/`430001` → `bse` 的既有测试与报告字段不动）；
2. **不改 `universe_filter_clean.py` 的 try 范围**（禁止捕获式降级）；
3. **不新增首日豁免机制**（由 S4 天然覆盖；未来数据连续时另立项，见 O-P040-2）；
4. **不区分做市/集合竞价**（O-P040-1）；
5. **不清理 `_RULE_INDEX` 死代码**（O-P040-5，避免扩做）。

### D4 测试策略（6 用例，纯函数级，无夹具）

| ID | 用例 | 断言 |
|----|------|------|
| V1 | 新三板集合竞价段 | `2020-07-26`：False/True 两态 `up=1.00, down=-0.50` |
| V2 | 精选层边界（半开区间） | `2020-07-27`：两态 `up=0.30, down=-0.30` |
| V3 | 北交所期不变 | `2021-11-15` / `2023-06-01`：两态 30% |
| V4 | fail-fast 保留 | `2018-01-12`：`pytest.raises(LimitRuleError)` |
| V5 | 全窗口可解析 | `pd.bdate_range("2020-01-23", "2021-11-12")` 逐日 × 两态不抛（436 日缺口 → 0） |
| V6 | `build_limit_prices` 不抛且首日不限制 | 3 日迷你帧（停牌前收 NaN）→ `up/down` 在复牌日为 NaN；前一段 10 → limit_up 20 / limit_down 5 |

---

## 3. 不变式

| ID | 不变式 | 判据 |
|----|--------|------|
| I1 | golden **13 零重录**（无 `8`/`4` 代码） | `pytest -k golden` + `git status --short tests/golden/` |
| I2 | pytest **765 → 771**（+6） | 全量末行 |
| I3 | mypy 12 面 **0**；新增 `# type: ignore` **0** | 门禁命令 |
| I4 | 公开签名零变更（`infer_board` / `resolve_limit` / `build_limit_prices` / `RULES` 类型） | `git diff` 中 `^[+-]\s*def ` = 0 |
| I5 | AST `except Exception` 恒 **22**；新增 `except` / `raise` **0** | P-029 十文件命令 + `git diff -U0` |
| I6 | 其余 board 规则逐字不变（main 3 / gem 4 / star 2 共 9 条零改动） | `git diff` 仅 bse 段与版本行 |

---

## 4. 边界与回退

- **回退点**：单提交 revert → 回到 11 条规则（`LimitRuleError` 复现）；无跨批依赖。
- **失败模式**：若 mypy/black 计数不符 → 以实测回填（F-I 惯例）。
- **真实数据验收**：`setup()` 必须推进到 U-P038-1 `FileNotFoundError`（而非 `LimitRuleError`）；不作为 CI 测试（依赖 `E:\Ashare_data`）。

---

## 5. 已知局限（承接 RESEARCH §10）

O-P040-1（做市不设涨跌幅）/ O-P040-2（首日豁免依赖快照或前收 NaN）/ O-P040-3（`4xxxx` 老三板）/ O-P040-4（北交所期无数据行使）/ O-P040-5（`_RULE_INDEX` 死代码）。

---

## 6. Step 3 自查

| # | 项 | 结论 |
|---|----|------|
| 1 | 决策可机械核验 | ✅ D1 行数/值/日期逐字；D4 六用例一一对应 |
| 2 | 失败注入可观测 | ✅ V4 红态为 `LimitRuleError`，V1/V2 红态为「无匹配规则」 |
| 3 | 低效排除 | ✅ 无循环/无新 I/O；规则查找仍为线性过滤（11 → 13 条；U-P040-1 终审核正：原记 15 系 11+4 算术错误，实际为 bse 2→4 **替换**净 +2） |
| 4 | 零依赖新增 | ✅ 仅 pandas 常量 |
| 5 | 测试破坏面 | ✅ 既有 `test_limit_rules.py` 6 用例不受影响（2022+ 日期） |
| 6 | 版本口径 | ✅ C2 显式登记 |

---

## 7. Step 4 设计 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P040-1 累计第 2 轮。

### 7.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | D1 代码与 RESEARCH §8 逐字 | 4 行常量 + 注释 + 版本行一致 | ✅ |
| A | `RULES` 条数 11 → **13**（bse 2→4 替换，净 +2；U-P040-1 终审核正：原记 15/+4 系算术错误，实测 `len(RULES)`=13） | 逐行计数 | ✅ |
| B | V5 日期范围 | `bdate_range("2020-01-23","2021-11-12")` 含首尾（RESEARCH 缺口首尾） | ✅ |
| B | V6 迷你帧可构造 | 3 行 × 1 列，`ref` 需 2 行才有值；首行 NaN 预期 | ✅（断言细化见 F-S4-P040-2） |
| C | I2 计数 | 765 + 6 = **771** | ✅ |
| C | black 计数 | 122 + 1 = **123**；189 + 1 = **190** | ✅ |
| D | 既有测试破坏面 | `test_limit_rules.py` 全部使用 2022+ 或 2026 日期 | ✅ |

### 7.2 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S4-P040-1** | **P2** | D4/V6 未写明「前一段 10 → limit_up 20 / limit_down 5」所依赖的 `ref` 口径（`ref = close.shift(1)*adj.shift(1)/adj`，需 2 行且 adj=1） | D4 表格补口径；IMPL 测试代码显式给 2 行（2020-07-22/23）并断言 20/5 |
| F-S4-P040-2 | P3 | V6 仅断言复牌日 NaN，未断言「不抛」是否覆盖空/全 NaN 输入 | 补断言：`build_limit_prices` 正常返回、形状一致 |
| F-S4-P040-3 | P3 | D1 注释未说明 2021-11-15 与精选层合并同段的原因 | 注释补「同一 30% 段延续」（D1 已含，回写确认） |

### 7.3 结论

**Step 4 Review pass（1 P2 + 2 P3 当轮回写）**——设计可机械核验、红态可观测、计数自洽；**准予进入 Step 5 IMPL**。
**RULE-5**：第 2 轮同基座 → U-P040-1 pending。