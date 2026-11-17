# DESIGN：P-039 adj_factor 日期覆盖缺陷修复

> **批次**: P-039 · **Step 3 设计** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`core/data.py`；判档规则 1）
> **作者基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构；同源时登记 U-P039-3 而非默认异构）
> **上游**: [RESEARCH_p039](RESEARCH_p039_adj_factor_coverage.md)（§2 数据实况 / §6 M-A / §8 C1 / §12 F-S1-P039-1 / §13 Step 2 复审 pass：0 P1/P2 + 3 P3）
> **代码证据时点**: HEAD `377b26a`

---

## 1. 设计目标

| 目标 | 判据 |
|------|------|
| G1 缺陷修复 | 真实数据（adj 缺 81 日）下 `adj_factor` 加载成功，`setup()` 不再抛 KeyError，涨跌停掩码恢复生效 |
| G2 语义正确 | 缺失日按**前值**填充（复权因子日间恒定）；**不 bfill**（不污染未上市期） |
| G3 零回归 | golden 13 零重录；pytest 760 持平（+新增用例）；mypy 12 面 0；black 121 |
| G4 最小影响面 | 只改 `adj_factor` 分支；`close/open/high/low` 路径逐字不变 |
| G5 可观测 | 补齐日数以 `logger.info` 记录（P-026/P-029 静默治理纪律） |
| G6 可回退 | 单提交 revert 即恢复 `.loc` 行为 |

---

## 2. 决策详述

### D1 修复点：`_load_price_data` 的 `adj_factor` 分支（单点）

[core/data.py:300-302](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) 现网：

```python
# 应用日期过滤
if self._trade_dates is not None:
    data = data.loc[self._trade_dates]
```

改为：

```python
# 应用日期过滤
if self._trade_dates is not None:
    if price_type == "adj_factor":
        # 复权因子在除权日之间恒定（P-039 RESEARCH §2.3），缺失日按前值填充；
        # 未上市/退市期保持 NaN（与 close 同步）。三段式：并集对齐创建缺失行 →
        # ffill 取前值（含窗口外）→ 回裁窗口。两段式在窗口首日缺口时留 NaN
        # （F-S1-P039-1 实测），不可简化。
        window = self._trade_dates
        n_missing = len(window.difference(data.index))
        data = data.reindex(data.index.union(window)).ffill().reindex(window)
        if n_missing:
            logger.info(f"adj_factor 日期补齐: {n_missing} 日（ffill 前值填充）")
    else:
        data = data.loc[self._trade_dates]
```

**被拒绝的替代方案**：
- 全 kind 统一 `reindex`：close 缺日由「显式 KeyError」变「静默 NaN」→ 新静默路径（M-B）；
- 只在 `UniverseFilter` 容错：`get_adj_price` 仍抛 KeyError（M-C）；
- `reindex` 不填充：4.81% 真实缺口变 NaN → 复权价污染（M-D）；
- `ffill + bfill`：bfill 污染未上市期（M-E）；
- 数据侧重导出：不在仓内、不可复现（M-F）。

### D2 计数口径（可观测性）

`n_missing = len(window.difference(data.index))` —— 直接计算「窗口内存在但 adj 缺失」的日数，与 §13.1 的 80（窗口口径）/81（全量口径）一致。仅 `n_missing > 0` 时输出，避免正常数据刷日志。

**被拒绝的替代方案**：用 `isna().all(axis=1).sum()` 差值 —— 会把「全列 NaN 的未上市期」误计为缺失日（真实数据 931,013 NaN 中大部分属未上市期），口径错误。

### D3 不扩做（5 项，显式边界）

| 项 | 裁决 | 理由 |
|----|------|------|
| 列维度 `data[self._stock_codes]` 改 `reindex(columns=...)` | 不做 | 当前 adj 缺列 0；改则引入缺列→NaN 新静默路径（U-P039-2 登记） |
| `close/open/high/low` 改 reindex | 不做 | 四者与 `_trade_dates` 同源，实测 0 缺口；改则该四 kind 缺日静默 NaN |
| 修改 `build_limit_prices` / `UniverseFilter` | 不做 | 下游 L145 已 reindex + L148 已 fillna 回退，零改动即可 |
| 修改共享夹具 `_synth_fixture.write_price_fixture` | 不做 | 会改变其他 13 项 golden 与既有测试的构造路径；测试内局部后处理即可 |
| 修复上游数据源（`stock_adj.pkl` 重导出） | 不做 | 不在仓内（U-P039-1 登记） |

### D4 测试策略（新增 1 文件，5 用例）

新增 `tests/test_p039_adj_factor_coverage.py`：

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 缺日补齐 | 完整夹具 → drop 2 个 adj 日 → DataManager.adj_factor | shape 与 `trade_dates` 对齐；缺失日值 = 前一可用日值 |
| V2 | 无缺日等价 | 完整夹具（不 drop） | `dm.adj_factor` 与直接 `read_pickle` 逐值相等（`.loc` 等价） |
| V3 | 窗口首日缺口 | drop 窗口首日；窗口外有前值 | 首日取窗口外前值（三段式唯一性） |
| V4 | 不污染未上市期 | 构造某股上市前 adj 为 NaN（close 亦 NaN） | 修复后仍为 NaN（无 bfill） |
| V5 | 缺口在另一 kind 不触发 | drop `open` 的一日 | `open` 仍抛 KeyError（证明修复范围仅 adj） |

**夹具后处理方式**（不改共享夹具）：

```python
def _drop_adj_rows(data_dir: Path, dates: Sequence[str]) -> None:
    p = data_dir / "stock_adj.pkl"
    df = pd.read_pickle(p)
    df = df.drop(index=[pd.Timestamp(d) for d in dates])
    df.to_pickle(p)
```

> 注：`write_price_fixture` 写出的 index 为 `DatetimeIndex`，`drop` 直接按 Timestamp 命中（Step 9 实测确认）。

---

## 3. 不变式 I1-I6

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | golden 13 **零重录** | `pytest -q -k golden` + `git status --short tests/golden/` |
| I2 | 既有 760 测试**全部通过**；新增 5 用例 → 765 | 全量 `pytest -q` |
| I3 | mypy 12 面 **0 error**；无新增 `# type: ignore` | 门禁命令 + Grep |
| I4 | 公开签名零变更（`_load_price_data` 私有） | `git diff` 逐行 |
| I5 | `except Exception` 恒 **22**；零新增 `except` | AST 脚本 + `^\+.*except`（`-CaseSensitive`） |
| I6 | `close/open/high/low` 四分支**逐字不变** | `git diff -U3` 目视 + V5 用例 |

---

## 4. 验证契约 V1-V6

| ID | 用例 | 断言 |
|----|------|------|
| V1-V5 | 见 §D4 | 5 用例全过 |
| V6 | 门禁终态 | pytest **765** / golden **13** / mypy 12 面 **103 files 0** / black **122**（全仓 **189**，Step 9 订正：新增 1 测试文件）/ AST **22** / `uv lock` exit 0 |
| V6b | 真实数据端到端（本机可选） | **日志证据**：出现「adj_factor 日期补齐: 80 日（ffill 前值填充）」且**不再出现**「加载adj_factor数据失败」；`setup()` 仍会在后续 `_precompute_factors`（L242 → L325 `load_factor("UTR_turnover_new.pkl")`）因 **U-P038-1 未修**而抛 `FileNotFoundError`——**该异常不属本批**（Step 4 F-S4-P039-1 订正）。**Step 9 实施订正（F-S9-P039-3）**：实测更早的 `build_masks()` → `_build_limit_masks` L220 抛 `LimitRuleError(board=bse, 2020-01-23)`，未推进到 `_precompute_factors`；V6b 改以 `DataManager` 直接探针留证（形状 / 全 NaN 行 / 交叉 NaN 三口径），新缺陷登记 U-P039-4（P1，不属本批） |

### 红态口径（Step 9 必须出示修复前读数）

| 项 | 修复前 |
|----|--------|
| V1 缺日补齐 | `KeyError: "['2024-01-04'] not in index"` |
| V2 无缺日等价 | 通过（回归保护，红态即通过） |
| V3 窗口首日缺口 | `KeyError` |
| V4 不污染未上市期 | `KeyError`（同根） |
| V5 缺口在 open | 通过（红态即通过，豁免说明） |

---

## 5. 风险与未决（承 RESEARCH §9）

| ID | 类型 | 处置 |
|----|------|------|
| R-P039-1 | `object` 索引 ffill | Step 9 探针已在 `%TEMP%` 验证（`[1.0, 1.0, 1.2]`），真实数据 V1 再验 |
| R-P039-2 | 窗口首日无前值 | V3 覆盖「窗口外有前值」；「数据首日即缺」留 NaN（不扩做） |
| R-P039-3 | 内存/耗时 | 实测 66 MB / 0.18 s（Step 2 复审） |
| R-P039-4 | nullable dtype | 实测 float64，无此问题 |
| U-P039-1 | 上游 81 日缺失成因 | pending |
| U-P039-2 | 列维度同型严格索引 | pending（条件触发） |
| U-P039-3 | RULE-5 异构终审预留 | pending（Step 2 同基座） |
| O-P039-1/-2 | 四 kind 同源 / `_trade_dates is None` 边界 | 观察，不改 |

---

## 6. 实施顺序与回退点

```text
改 core/data.py 的 adj_factor 分支（1 处）
  → 新增 tests/test_p039_adj_factor_coverage.py（5 用例）
  → 红态 3 个 / 红态即通过 2 个 → 绿 5 passed
  → 全量 pytest 765 / golden 13 零重录 / mypy 12 面 0 / black 121 / AST 22
  → 本机真实数据端到端（V6b 可选留证）
  → 单提交 → CI 四 job 绿
```

- **回退点**：单提交 revert → 回到 `.loc` 行为（无跨批依赖）。
- **顺序敏感**：三段式顺序（F-S1-P039-1）；计数口径用 `window.difference`（非 NaN 行数）。

---

## 7. 下一 Step

**Step 4 设计 Review（须先自报基座）**：核 ① D1 分支是否覆盖全部缺日形态；② D2 计数口径是否会被未上市期 NaN 干扰；③ D3 五项不扩做是否越界；④ D4 五个用例的红/绿可执行性；⑤ I1-I6 与 V1-V6 是否覆盖 P-036/P-037 既有约束。

---

## 8. Step 4 设计 Review 记录（同基座独立上下文，2026-11-17）

> **基座披露**：复审会话 system prompt 逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.` → **与作者同源，RULE-5 不成立**（RULE-4 披露）；U-P039-3 累计第 2 轮异构未证实。
> **复审方式**：独立读码（`engine_v2.setup` 顺序 / `data.py` logger / 夹具 index 类型）+ 真实数据口径重算；复审时点 HEAD `377b26a`（DESIGN 未提交态）。

### 8.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | `engine_v2.setup()` 顺序 | `build_masks()` **L220** 先于 `_precompute_factors()` **L242** | ✅（并暴露 V6b 失实） |
| A | `core/data.py` logger | L13 `import logging` + L25 `logger = logging.getLogger(__name__)` | ✅ |
| A | 夹具 index 类型 | `_synth_fixture.py:60` `pd.DatetimeIndex(pd.to_datetime(...))` → `drop(Timestamp)` 可命中 | ✅ |
| B | D2 计数口径 | `window.difference(data.index)` 只算日期、不含列 → 不受未上市期 NaN 干扰 | ✅ |
| B | D1 分支覆盖面 | 缺日形态（首/中/尾、连续/分散）均落在同一 `reindex` 逻辑内 | ✅ |
| C | D3 五项不扩做 | 无越界（列/其他 kind/filter/夹具/数据源均显式排除） | ✅ |
| D | D4 五用例红/绿 | V1/V3/V4 可红（KeyError）、V2/V5 红态即通过（回归保护） | ⚠️ F-S4-P039-1 / -2 |
| E | I1-I6 / V1-V6 | 覆盖 golden / pytest / mypy / 签名 / except / 四分支不变 | ✅ |

### 8.2 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S4-P039-1** | **P2** | **V6b 断言失实**：原写「`setup()` 不再抛 FileNotFoundError」——但 `build_masks()`（L220，本批修复点）早于 `_precompute_factors()`（L242），后者对 `UTR_turnover_new.pkl` 的缺失（**U-P038-1，本批不修**）仍会抛 `FileNotFoundError` | V6b 改为**日志证据**断言（「日期补齐: 80 日」出现 + 「加载adj_factor数据失败」消失），并显式声明后续异常不属本批 |
| F-S4-P039-2 | P3 | V2「与直接 `read_pickle` 逐值相等」未规定列对齐口径：`dm.adj_factor` 经 L305-306 裁剪到 `stock_codes`，若比较对象列序不同会误判 | 用例断言改为「先按 `dm.stock_codes` 对齐再比较」 |
| F-S4-P039-3 | P3 | V5「drop `open` 一日 → 仍 KeyError」未写明异常来源（pandas `"not in index"`），易被误读为业务异常 | 用例显式 `pytest.raises(KeyError, match="not in index")` |

### 8.3 结论

**复审结论**：**pass（1 P2 + 2 P3 全部当轮回写）**——D1/D2/D3/I/V 其余项通过；P2 修正后 V6b 可执行且边界清晰，**准予进入 Step 5 IMPL**。
**RULE-5**：第 2 轮同基座 → U-P039-3 维持 pending。
