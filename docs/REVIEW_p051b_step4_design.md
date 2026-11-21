# REVIEW：P-051b Step 4 异构独立复审（DESIGN 文档）

> **复审对象**: [DESIGN_p051b_strategy_library.md](DESIGN_p051b_strategy_library.md)（507 行）· 作者 DeepSeek-V4.1-Flash
> **复审方**: GLM-5.3-Flash（异构，RULE-5 满足）· 日期 2026-11-21
> **复审方法**: 独立取证——DESIGN 全文实读 + RESEARCH §18.3/§4 对照 + `stops.py` / `volatility.py` / `registry.py` 接口实读 + 全部闭式手算复验
> **复审重点**（RESEARCH §9）: 前视、归一、注册、回归

---

## 0. 判定

| 项 | 结论 |
|----|------|
| **P1 缺陷** | **2 条（F-D1 / F-D2）→ Step 4 出口未达（需 0 P1），须收敛后复验** |
| P2 缺陷 | 1 条（F-D3，实施歧义须收敛） |
| P3 备注 | 8 条（F-D4..F-D11，附最小修复措辞） |
| 通过面 | 闭式数学全部复验通过；接口引用全部实读相符；前视/归一/注册/回归四主题中「归一/注册/回归」三面无 P1/P2 |

两条 P1 均为「设计内部自洽、但与上游样例/裁决冲突」型缺陷，修复成本低（各一处伪码/一行裁决），不影响 D1/D2/D5/D7/D8/D9 架构主体。

---

## 1. 独立取证记录（通过项）

| # | 核查项 | 方法 | 结果 |
|---|--------|------|------|
| V1 | D4.2 mean_reversion 闭式 | 手算 k 表 6 行 + 不变量 −(n−1)/√n | 全对 ✓（与 §18.3.2 一致，ddof=1 已声明） |
| V2 | R1-R5 用例与伪码一致性 | 伪码分支手推（holding→keep/exit） | R1-R5 全对 ✓（z=−0.4873≥−0.5→exit；−0.5627<−0.5→keep） |
| V3 | D4.3 trend 三场景 | 条件手推 | T1-T4 全对 ✓；`iloc[-entry_n:]` = [t−entry_n, t−1] ✓；双条件 AND 反伪通过 ✓ |
| V4 | D4.4 grid 权重表与 ATR 闭式 | 手算 + [volatility.py L67-72](file:///f:/Coding/Factor_Trading_v3.0/core/volatility.py#L67-L72) 实读 | seed=mean(TR[0..13])=1.0 精确、递归 14/14=1.0 精确 → G1 成立 ✓；G2/G3 权重表全对 ✓ |
| V5 | D5 归一 | 除零路径审查 | `sum > 1.0` 才除 → 空仓安全 ✓；1/n 浮点相容（Step 2 已验）✓ |
| V6 | E5 `apply_stops` 接口 | 实读 [stops.py L177-199 / L233](file:///f:/Coding/Factor_Trading_v3.0/core/stops.py#L177-L199) | 签名 `(targets, bars, config, *, tradable)` ✓；触发日归 0 ✓；bars 缺失值 fail-fast → E2 夹具须全网格有价（`_synth_fixture` 满足）✓；targets 禁 NaN → `signals_frame` 物化 0.0 兼容 ✓ |
| V7 | I5/C3 注册覆写 | 实读 [registry.py L79](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L79) | `logger.warning + overwriting` ✓ |
| V8 | E4 重放 | 实读 [strategy.py L234-259](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L234-L259) | `signals_frame` 每次以空 `StrategyState` 起步（`initial_state=None` 分支）→ 同一实例两次调用逐值相等 ✓ |
| V9 | D8 无前视 | 逐模板审查 | momentum/MR 只读 history；trend/grid 读当日 `prices`（决策后次日成交）→ 无前视 ✓；M7 可测 ✓ |
| V10 | D2 additive 论证 | 对照 Step 2 复审 V5/V6 | 全仓 3 处构造均关键字、hash/== 语义不变 ✓ |
| V11 | 计数自洽 | §5 清单加总 | 44 条名义 + C7 参数化 +3 = **+47** → 1087 ✓（但 D11 表 L355 写 1082，见 F-D9） |
| V12 | R-2/R-3 订正 | 对照 P-045/P-051a | 死参数剔除 ✓；止损外移避免双层叠加 ✓（apply_stops 已具备 time_stop_days/stop_loss_pct） |

---

## 2. F-D1（P1）：`ts_momentum` 算法索引与 §18.3.1 样例锚点错位 1 bar

**证据**：
- DESIGN D4.1 伪码（L227）：`sign(p_now / hist.iloc[-1-lb] - 1)`，且 L233/L235 明确 `min_rows = max(lookbacks) + 1`（R-4）。
- 窗口为 `[t−W, t−1]`（W 行），`iloc[k] = t−W+k` → `iloc[-1-lb] = t−1−lb`。W=121 时 `iloc[-1-120] = iloc[0] = t−121`。
- RESEARCH §18.3.1 表头（[L1046](RESEARCH_p051b_strategy_templates.md#L1046)）锚点为 **P(t−120) / P(t−60) / P(t−20)**，收益定义 `P(t−1)/P(t−lb) − 1`。

**缺陷**：算法读 t−121/t−61/t−21，样例锚点在 t−120/t−60/t−20——除 t−1 外全部错位 1 bar。M1 闭式测试若按表头构造 W=121 行窗口，`iloc[0]`（t−121）的值未被样例定义 → 票数不可复现，**M1/M2/M8 三个用例无法编写**，阻断 Step 5。

**修复路径（推荐 b，改动最小）**：
- **b（推荐）**：伪码改 `hist.iloc[-lb]`（W = max(lookbacks) 时 `iloc[-120] = iloc[0] = t−120`，与样例表头逐点吻合，收益 = `P(t−1)/P(t−lb) − 1` 与样例完全一致）；`min_rows` 恢复 `max(lookbacks)`；**撤销 R-4**（§18.2 恢复原式）；M8 改为「行数 = max(lookbacks) − 1 → fail」。
- a（备选）：保留 `iloc[-1-lb]`，样例表头改 P(t−121)/P(t−61)/P(t−21)（数值照抄、标签移位），R-4 保留。
- 两方案任选其一，但**必须二选一**：当前状态算法与样例互斥。

## 3. F-D2（P1）：`grid_atr` 默认基准 = 滚动锚点，违背 U-P051b-6 裁决理由且未披露

**证据**：
- DESIGN D4.4（L274）：`base = base_price if base_price is not None else h["close"].iloc[0]`。`history` 窗口为 `[t−W, t−1]` → `iloc[0] = t−W`，**随 t 逐日滚动**（t+1 日的基准变为 P(t+1−W)）。
- RESEARCH U-P051b-6 原推荐（现已加删除线保留）：「首建仓日收盘（**避免滚动基准导致的历史依赖**）」。
- DESIGN R-1 的「闭式兼容」论证只覆盖恒定价样例（close≡10 → 首值=基准=10），**未披露非恒定价下的语义变更**：固定基准的经典网格（档位=自建仓累计跌幅）→ 每日重锚的滚动网格（档位=近 W 日跌幅），两者是完全不同的策略行为。

**缺陷**：默认行为恰好落入原裁决明确要避免的「滚动基准」，与模板名义语义（经典网格）实质背离；R-1 只论证了「原方案不可实现」（成立），未处理「新默认与裁决理由冲突」。若照现状实施，将产出与上游裁决意图相反的默认行为。

**修复路径（三选一）**：
- **c（推荐）**：`base_price: Mapping[str, float]` **必填**（缺省 None → `StrategyConfigError`，与 I10 fail-fast 风格一致）。网格基准是策略语义的一部分，不应有隐式默认；§18.3.4 样例改为显式传 `base_price=10`（闭式数值不变）；G4 拆两条（显式生效 + 缺省 fail-fast）。
- b′：保留默认窗口首值，但 D4.4/Rk-2 强披露「默认为滚动基准，固定基准须显式传参」，并**显式覆盖 U-P051b-6 裁决记录**（注明为何接受滚动语义）。
- a′：默认取 `state.positions` 首次非零日的推断——已否决（不可实现，需状态回写，即 U-P051b-15）。

## 4. F-D3（P2）：`trend_breakout` 的 NaN 标的级政策未定（实施歧义）

D4.3 伪码 `.max()/.min()/.mean()` 均默认 skipna=True；D10 的 NaN 政策只写了「z / 收益为 NaN → 不入选」（momentum/MR），未覆盖 trend 的 `upper/lower/ma`。真实数据中停牌/未上市标的在 raw 面板为 NaN → 突破区间可能基于**不完整窗口**判定（如 20 日窗口只有 15 个有效 high），行为依赖 pandas skipna 隐式语义。

**修复**：D4.3 补一条标的级政策（与 D10 风格对齐）。建议「判定所需窗口（entry_n 高点 / exit_n 低点 / ma_n 均线）内含 NaN → 该标的不入选（未持仓时）/ 不清仓但记 warning（持仓时，避免 NaN 误清仓）」，或至少显式声明「采用 skipna，接受不完整窗口」（需给理由）。

## 5. P3 备注（8 条，附最小修复）

| ID | 位置 | 问题 | 最小修复 |
|----|------|------|----------|
| F-D4 | D4.2 L249 | 文字「std==0 → 不入场、**不出场**」与伪码矛盾（holding 时 z=0 → `0<−0.5` False → **exit**） | 文字改「不入场；持仓则出场（回归完成即离场）」；R6 断言相应补持仓分支 |
| F-D5 | I6 L421 | 「未 import `strategies` 时 registry 无模板」在 pytest 全局单例 + 收集期 import 下**不可测** | 改写为可测形式：「`get_strategy_registry().get(未注册名)` 返回 None/抛 KeyError，且四个已注册 id 均可取」 |
| F-D6 | D4.4 L272 | `min_rows = atr_period + 1` 比最小必要（`atr_period`，seed 在 `iloc[period−1]` 已可用）多 1 行 | 保守无害，注记即可（保持与 §18.2 公式一致）；G1 不受影响（两条路径 ATR 均 =1.0 精确） |
| F-D7 | D9 L327 | `holding` 基于 `state.positions` = **上一日目标权重**，非实际持仓（sizing/stop 可改变实际持仓）；目标被缩到 0 时策略会误判未持仓而再发入场信号 | D9 加注记：这是 P-044 契约既定边界（`MarketView` 不含实际持仓），语义为「目标持有」，与 E2 组合 `apply_stops` 时的行为差异由该层兜底 |
| F-D8 | D3 L214 | 「iloc 切片为视图（pandas 不复制底层数组）」pandas 不作此保证 | 措辞改「切片共享/复制由 pandas 决定；模板只读使用，两种情况行为一致」 |
| F-D9 | D11 L355 | pytest 目标写 **~1082**，与 §5（L408）/§7（L435）的 **~1087** 不一致 | 统一为 1087（+47 自洽） |
| F-D10 | C2 L364 | 「`factory(None)` / `factory({"levels":2})` / `factory(levels=2)` 三形态等价」——`factory(None)` 是全默认（levels=3），与前两者不等价 | 改「三形态均合法且各产出正确配置；`dict` 形态与 `**overrides` 形态互等价」 |
| F-D11 | V6 L375 | 「`history[k].index == view.returns.index`」未注明前提（`returns_window` 与 `history_window` 须同值；为 0 时 returns=None 无断言对象） | 用例前提补注「`returns_window = history_window = W`」 |

## 6. 收敛流程建议

1. 设计方按 §2/§3 二选一定稿 F-D1 / F-D2（推荐 b / c），同步 F-D3 与 8 条 P3；
2. 联动回填：§18.2（R-4 撤销或保留随方案）、§18.3.4 样例表述、M8/G4/R6 用例文本、D11 数字；
3. DESIGN §0 追加「Step 4 复审发现收敛表」（同 §0.1 体例）；
4. 复审方做 **4b 快速复验**（只核 P1/P2 修复点 + 联动面，不重开全文）→ 0 P1 后放行 Step 5。

---

## 7. 修复响应记录（设计方填写，**非复审结论**，供 4b 核验）

> 填写方：DeepSeek-V4.1-Flash（DESIGN 作者）· 2026-11-21 · 用户裁定按修复 **b** 与 **c** 执行

| ID | 处置 | 实际落点 |
|----|------|----------|
| **F-D1** | 采纳修复 b：伪码 `iloc[-1-lb]` → **`iloc[-lb]`**；`min_rows` = `max(lookbacks)`；R-4 撤销（DESIGN §0.1 已删该条，改在 D4.1 留撤销说明）；M8 改「行数 = `max(lookbacks) − 1` → fail」 | [DESIGN D4.1](DESIGN_p051b_strategy_library.md) / [RESEARCH §18.2](RESEARCH_p051b_strategy_templates.md) |
| **F-D2** | 采纳修复 c：`base_price` **必填**（缺省/空 → `StrategyConfigError`）；D4.4 删除窗口首值回退；`base_price` 缺键 → 该标的 0；§18.3.4 改显式 `base_price={"A": 10.0}`；G4 改缺省 fail-fast、G5 改缺键 | D4.4 / D10 / G4-G5 / RESEARCH §18.3.4 |
| **F-D3** | `skipna=False` 显式化；未持仓 NaN 不入选；持仓 `lower` NaN 保持 | D4.3 / D10 |
| F-D4 | 文字改「未持仓不入场；已持仓出场」；R6 补持仓分支 | D4.2 / R6 |
| F-D5 | I6 改为「未注册 id → `get()` 返回 `None`；import 后四个 id 可取」 | I6 |
| F-D6 | D4.4 注记「`atr_period + 1` 保守无害」 | D4.4 |
| F-D7 | D9 加「`state.positions` = 目标权重，非实际持仓」注记 | D9 |
| F-D8 | D3 / Rk-4 措辞改「copy/view 由 pandas 决定；只读行为一致」 | D3 / Rk-4 |
| F-D9 | 统一为 **1088**（G 组 +1 → 45 条 + C7 参数化 3 = +48） | D11 / §5 / §7 |
| F-D10 | C2 改「`None` 全默认；dict 与 `**overrides` 等价」 | C2 |
| F-D11 | V6 补前提 `returns_window = history_window = W` | V6 |

**联动同步**：RESEARCH §4 U-P051b-6（终版必填）、§9 Step 3/4 行、§18.2（R-4 撤销）、§18.3.4（显式基准 + 止损归属订正）已全部回填。

**待 4b 核验清单（建议 5 项）**：
1. D4.1 `iloc[-lb]` 在 `W = max(lookbacks)` 下是否逐点等于 `P(t−lb)`（含 `lb = max` 边界）；
2. `base_price` 必填是否在所有入口（工厂 `None` / `{}` / `overrides`）都 fail-fast；
3. `trend_breakout` `skipna=False` 在持仓/未持仓两分支的语义是否与 D10 表一致；
4. G 组 7 条 + C7 参数化 → 计数 45/+48/1088 是否自洽；
5. 是否仍有「R-4 / 窗口首值 / 1082 / 1087」残留（设计方 grep 已清零，仅保留撤销说明文本）。

---

## 8. 4b 快速复验结论（复审方 GLM-5.3-Flash · 2026-11-21）

**判定：5 项核验全部通过，0 P1 / 0 P2 → Step 4 出口达标，放行 Step 5。**

| # | 核验项 | 结果 |
|---|--------|------|
| 1 | D4.1 `iloc[-lb]` 逐点对齐 | **通过**：`iloc[-lb]=iloc[W−lb]=t−lb`；W=120 时 lb=120/60/20 → iloc[0]/[60]/[100] = t−120/t−60/t−20，与 §18.3.1 锚点逐点吻合；收益式与样例数值全对；`min_rows=max(lookbacks)` 自洽（含 lb=max 边界） |
| 2 | `base_price` 全入口 fail-fast | **通过**：`__post_init__` 统一拦截（§11 要点 2）覆盖工厂 None/`{}`/overrides，与 D10 一致。**新增 P3-4b-1**：C2 文本未补 grid 例外（见下），已由复审方代修 |
| 3 | `skipna=False` 分支一致 | **通过**：持仓查 `lower`（出场唯一依据）、未持仓查 `upper+ma`，与 D10 表逐字一致；pandas `skipna=False` 含 NaN 返回 NaN，伪码可行 |
| 4 | 计数自洽 | **通过**：实际 +48（C10+V7+M8+R7+T5+G7+E4）、名义 45、目标 1088，三处一致 |
| 5 | 残留清零 | **通过**：DESIGN 无 R-4/窗口首值/iloc[-1-lb]/1082 残留；RESEARCH 仅存 2 处合法撤销说明 |

**P3-4b-1（已当场修复）**：C2 原文「`factory(None)` 为全默认」对 grid_atr 不成立（必填校验 → 抛错）。已改为「三模板 `factory(None)` 全默认；grid_atr `factory(None)`/`factory({})` 须抛 `StrategyConfigError`」。修复由复审方代为落笔（单句文本、修复文本即本报告所给），Step 5 实施时按此断言。

**移交 Step 5 的注记**：E1/E2 端到端构造 `grid_atr` 时须显式传 `base_price`（必填后的自然结果，测试文本粒度不另行展开）。
