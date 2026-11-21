# REVIEW：P-051b Step 6 异构独立复审（IMPL 文档）

> **复审对象**: [IMPL_p051b_strategy_library.md](IMPL_p051b_strategy_library.md)（995 行）· 作者 DeepSeek-V4.1-Flash
> **复审方**: GLM-5.3-Flash（异构，RULE-5 满足）· 日期 2026-11-21
> **复审方法**: 6 个新文件全文逐行核 + 闭式手算复验（M1 票数 / R 组 z 表 / G 组权重）+ 接口实读（registry / tests.yml / volatility）+ 测试计数重算
> **复审重点**: 代码可执行性、C-1..C-3 语义对 DESIGN 的忠实度、测试规格自洽、mypy 风险

---

## 0. 判定

| 项 | 结论 |
|----|------|
| **P1 缺陷** | **3 条（F-I1 / F-I2 / F-I3）→ Step 6 出口未达，须收敛后复验** |
| P2 缺陷 | 3 条（F-I4 / F-I5 / F-I6） |
| P3 备注 | 6 条（F-I7..F-I12） |
| 通过面 | 四模板算法代码与 DESIGN 逐条一致；`views_from_data` 改动正确（V1-V7 语义全对、I11 成立）；`base.py` 五工具逻辑正确；M1 锚点索引与 9 个收益值手算全对；G 组权重表手算全对；零改动清单完整 |

三条 P1 均为「IMPL 转录/构造错误」型（非设计缺陷），修复全部为局部文本/字段级，不动架构。

---

## 1. 独立取证记录（通过项）

| # | 核查项 | 方法 | 结果 |
|---|--------|------|------|
| V1 | M1 票数与锚点索引 | 手算 120 行窗口 `iloc[-lb]` → iloc[0]/[60]/[100]；9 个收益值（A:−0.10/+0.50/+0.125；B:+0.60/+0.333/+0.143；C:−0.25/−0.0625/+0.071） | 全对 ✓，与 §18.3.1 逐点一致 |
| V2 | momentum 代码链路 | `votes` 累加 / `np.sign` / `fillna(0)` / NaN→0 票 | 正确 ✓（C-3 落实） |
| V3 | G1/G2/G3 | 全 TR=1.0 → seed 精确 1.0；`floor((10−P)/1)` 档位 0/1/2/3/4→clip；4/3 缩放 | 全对 ✓（与 Step 4 复验一致） |
| V4 | trend T1/T3/T4 | 条件手推（11>10∧11>10；8.5<9；9.5≥9） | 全对 ✓ |
| V5 | `base.py` 五工具 | equal_weight 去重保序 / scale_to_one 除零安全 / build_config 未知键拦截 / require_history 三级校验 | 正确 ✓ |
| V6 | `views_from_data` 改动 | `history_window=0` 零行为（panels 空、history 恒 None）；`iloc[i−W:i]` 与 returns 同窗（V6）；`i<W → None`（V5） | 正确 ✓（I11 成立） |
| V7 | C1/C3/C5/C6/C7 | 对照 registry 实测行为：`get()` Optional ✓、warning 文本 "already registered" ✓（L79）、`fields()` 键集 ✓、装饰器签名 ✓ | 全部可测 ✓ |
| V8 | mypy 配置理解 | pyproject L109-114（`disallow_untyped_defs=false` / `warn_return_any=true`） | §6.1 表述正确 ✓ |
| V9 | C-1/C-2/C-3 忠实度 | 对照 DESIGN D5/D9/D10 | 等权 selected 语义与 §18.3 全部闭式数值一致 ✓；未静默扩大设计 |
| V10 | 零改动清单 | §1 末尾 8 项 | 完整 ✓（含 golden / `core/*` 全保） |

---

## 2. P1 缺陷（3 条）

### F-I1：`GridATRConfig.base_price` 无默认值 → C2/G4 断言必然失败

**证据**（[IMPL L260](IMPL_p051b_strategy_library.md#L260)）：

```python
base_price: Mapping[str, float]      # ← 无默认值，必填位置参数
```

调用链：`factory(None)` → `PluginEntry.create(None)` → `factory(**kwargs)` → `grid_atr_factory()` → `build_config(GridATRConfig, None, {})` → `merged={}` → `GridATRConfig(**{})` → **`TypeError: missing 1 required positional argument: 'base_price'`** —— 根本进不了 `__post_init__` 的 `StrategyConfigError` 分支。

C2 参数化 `pytest.raises(StrategyConfigError)` 与 G4 对 `factory(None)` / `factory({})` 的断言**必然失败**（抛的是 TypeError）。

**修复（唯一可行）**：

```python
base_price: Mapping[str, float] | None = None   # 默认 None，让构造可完成

def __post_init__(self) -> None:
    if self.base_price is None or not self.base_price:
        raise StrategyConfigError("grid_atr: base_price 必填且不得为空")
    ...
```

（`None → fail-fast` 语义不变，且 `__post_init__` 能被进入；`asdict` 输出不变——None 分支已被拒绝。）

### F-I2：E1/E3/E4 端到端协议缺失——头部 `history=None` 触发 fail-fast，或切片后 `set_signal` 校验失败

**证据**（[IMPL §4.7 L925-941](IMPL_p051b_strategy_library.md#L925-L941)）：E1 夹具 5 行（P-044 `_make_engine` 样板）+ `lookbacks=(5,)` / `lookback=5`。

三连失效：

1. `views_from_data(history_window=5)` 在 5 行数据下：`i < 5` 恒成立 → **全部 view 的 `history=None`**；
2. `signals_frame(views)` 逐日调用 `generate_signals` → 首个 view 即触发 `require_history` → **`StrategyConfigError`**（违反 I10 是预期行为，但测试没有处理它）；
3. 若实施者切片 `views[W:]` 绕过 → `frame.index` 缺头部 → `set_signal(mode="weights")` 的「index 必须等于 `dm.trade_dates`」校验 **fail-fast**。

无论哪条路径 E1/E4 都跑不通。

**修复（端到端协议，三步）**：

```python
# ① 夹具扩行：DATES periods=30（write_price_fixture 支持任意行数）
# ② 只消费有效段：
frame = adapter.signals_frame(views[W:])          # W = max(模板窗长)
# ③ 头部补零行，满足 set_signal 的 index 全集校验：
head = pd.DataFrame(0.0, index=dates[:W], columns=frame.columns)
engine.set_signal(pd.concat([head, frame]), mode="weights")
```

E3/E4 同协议（E4 的两次调用都消费 `views[W:]`）。**此协议须写进 IMPL §4.7 正文**，否则 Step 9 实施必返工。

### F-I3：R 组夹具方向错误——latest 不是低点，z 符号全部反转

**证据**（[IMPL §4.5 L888-890](IMPL_p051b_strategy_library.md#L888-L890)）：「以『20 行、首位 10.0、其余 9.0』构造单点偏离（z = −4.24853，R3）」。

§18.3.2 的闭式 `z_low = −√((n−k)(n−1)/(n·k))` 推导前提是 **latest = L（窗口末值为低点）**。「首位 10.0、其余 9.0」的实际构造：k=19（19 个 L）、latest=9.0=L → z = −√(1·19/(20·19)) = **−0.2236** ≠ −4.2485，且 > −z_entry → R3 断言「入场」失败。R1/R2 同理（若 k 个 9.0 放头部 → latest=H → z 为正 → 全部反转）。

**修复（统一构造条款）**：

- 夹具 = 前 `(20−k)` 行 10.0（H）+ **末 `k` 行 9.0（L）**（保证 latest=L）；
- R1（k=3）：行 0..16=10.0，行 17..19=9.0 → z=−2.3202 ✓；
- R3（k=1）：行 0..18=10.0，行 19=9.0 → z=−4.2485 ✓；
- R4/R5（k=16/15）同条款 + `positions={"A":0.5}`。

## 3. P2 缺陷（3 条）

| ID | 位置 | 问题 | 修复 |
|----|------|------|------|
| **F-I4** | §4.5 T2 L902 | 「同上但 `prices=10.5`（>MA 10 但 < 11）」——T1 夹具 `high=10` → `upper=10`，则 10.5>10 且 10.5>ma=10 → **会入场**，断言「空 Series」失败。DESIGN T2 原规格「10.5<11」隐含 `upper=11`，IMPL 抄录时丢失夹具条件 | T2 改为**自建夹具**：60 行 `close=10 / high=11 / low=9`（upper=11），`prices=10.5` → 10.5<11 → 拒绝 ✓ |
| **F-I5** | §4.7 L950 | 计数不自洽：C2_grid 参数化 `[None,{}]` 2 例 → C 组实际 11 条 → 总参数化 **+49 → 1089**，与同段声称的「+48 / 1088」矛盾（DESIGN §5/D11 均为 1088） | `test_c2_grid_requires_base_price` 去参数化，单函数内两个 `pytest.raises` 块 → C 组 10 条 → **+48 → 1088** 与 DESIGN 对齐 |
| **F-I6** | §4.7 E2 L946 | E1 夹具恒定价（10.0）不会触发 `stop_loss_pct=0.2`（需 ≥20% 跌幅）→ 「触发日该标的 0」断言前提不成立 | E2 自建价格路径：如第 3 日 close 10→7.5（−25%）→ 触发；断言触发日该标的权重为 0 |

## 4. P3 备注（6 条）

| ID | 位置 | 问题 | 最小修复 |
|----|------|------|----------|
| F-I7 | mean_reversion L612-613 | 两行 `where` 顺序使「窗口全 NaN（std=NaN）」走 `std>0` 为 False 的分支 → z 被置 **0**（非 NaN）——最终行为恰好仍符合 D10（未持仓不入选 / 持仓 continue 出场），但注释「价格 NaN → z=NaN → 不入选」的路径描述不实 | L612 改 `z = z.mask(std == 0, 0.0)`（`std==0 → 0`；`std=NaN` 时 mask 条件为 False → z 保持 NaN）→ 行为与路径均精确 |
| F-I8 | `__init__.py` L648 | 注册顺序 `grid→mean_reversion→momentum→trend` 与 DESIGN §2.3 的 `grid→trend→momentum→mean_reversion` 不一致（语义无关，Step 8 一致性检查会命中） | 对齐 DESIGN 顺序，注释改「顺序遵循 DESIGN §2.3」 |
| F-I9 | `_p051b_common.py` L726 | 残留垃圾注释「# index=-1 表示…」（`index` 参数已删除） | 删除该行 |
| F-I10 | §3.8 L692 | tests.yml「原」行缺 flags：实际 L46 为 `python -m mypy --explicit-package-bases --check-untyped-defs core agents …`——照 IMPL 原文替换会丢两个 flag | 更正原文引用；「后」行同样保留 `python -m mypy --explicit-package-bases --check-untyped-defs` 前缀 |
| F-I11 | grid.py L304-306 | `atr()` 返回 `pd.Series \| pd.DataFrame` union → `.iloc[-1]` 的 mypy narrowing 报错风险（§6.3 已口头提示但代码未落实） | `atr_frame = cast(pd.DataFrame, atr(...))` 后再 `.iloc[-1]`（补 `from typing import cast`） |
| F-I12 | §4.3 V4 | 「prices/returns 与改动前逐值相同（复用 P-044 V5 基线）」不可直接测试（无法运行旧代码） | 改可测形式：「`history_window=0` → `history` 恒 `None`；`returns`/`prices` 形状与 dtype 正常；等价性以 1040 全量不退化为准（I11）」 |

---

## 5. 收敛流程建议

1. 设计方按 §2 修复 3 条 P1（F-I1 字段默认值 / F-I2 端到端协议三步 / F-I3 R 组夹具条款），同步 §3 三条 P2；
2. 联动：IMPL §4.7 正文写入端到端协议；C2_grid 去参数化后重算计数（45 条 / +48 / 1088 保持）；T2/E2 夹具条款补全；
3. IMPL 追加「Step 6 复审发现收敛表」（体例同 DESIGN §0.3）；
4. 复审方做 **6b 快速复验**（只核 P1/P2 修复点 + 计数联动）→ 0 P1 后放行 Step 7（CHECKLIST）。

---

## 6. 修复响应记录（设计方填写，**非复审结论**，供 6b 核验）

> 填写方：DeepSeek-V4.1-Flash（IMPL 作者）· 2026-11-21

| ID | 处置 | 实际落点 |
|----|------|----------|
| **F-I1** | `base_price: Mapping[str, float] \| None = None`；`__post_init__` 先取局部 `base` 再判 `None or 空`；`object.__setattr__` 与 `generate_signals` 均用 `base` / `base_prices = cfg.base_price or {}` | IMPL §3.3 |
| **F-I2** | 三步协议写入 §4.7 正文：`PERIODS=30`、`WINDOW=15`、`signals_frame(views[WINDOW:])`、头部补零 concat、`assert list(full.index) == list(dates)`；参数化含 trend 自定义窗长（`ma_n=10`）使 `WINDOW=15` 覆盖四模板 | IMPL §4.7 |
| **F-I3** | R 组统一条款：前 `20−k` 行 H、末 `k` 行 L；R1/R2/R3/R4/R5 逐条重列 k 与 z | IMPL §4.5 |
| F-I4 | T2 改自建 `high=11`（upper=11、ma=10），10.5<11 拒绝 | IMPL §4.5 |
| F-I5 | `test_c2_grid_requires_base_price` 去参数化，单函数三个 `pytest.raises`（`None` / `{}` / `base_price={}`）→ 计数回 +48/1088 | IMPL §4.2 |
| F-I6 | E2 自建 `10→10→7.5` 路径 | IMPL §4.7 |
| F-I7 | `z.mask(std == 0, 0.0)`，删除误导注释前缀 | IMPL §3.6 |
| F-I8 | `__init__.py` 顺序改 grid→trend→momentum→mean_reversion，注释指向 DESIGN §2.3 | IMPL §3.7 |
| F-I9 | 删除 `make_view` 垃圾注释 | IMPL §4.1 |
| F-I10 | tests.yml 原文补 `--explicit-package-bases --check-untyped-defs`；「后」行保留 | IMPL §3.8 |
| F-I11 | `cast(pd.DataFrame, atr(...))` + `from typing import Any, cast` | IMPL §3.3 |
| F-I12 | V4 改为可测表述 | IMPL §4.3 |

**联动同步**：IMPL 新增 §9 收敛表；§4.7 计数表述改「仅 C7 参数化（+3）」；§6 风险表第 1 条改为「已用 cast 收窄」；§8 保留公共夹具命名裁决。

**待 6b 核验清单（5 项）**：
1. `GridATRConfig()` 无参构造是否抛 `StrategyConfigError`（而非 `TypeError`）；
2. `factory(None)` / `factory({})` / `factory(base_price={})` 三个入口是否都抛 `StrategyConfigError`；
3. E1 协议在 `PERIODS=30 / WINDOW=15` 下是否 ① 头部零行 ② index 与 `dates` 全等 ③ 四模板均不抛；
4. R 组 k 与 z 是否逐条自洽（k=3→−2.3202、k=4→−1.9494、k=1→−4.2485、k=16→−0.4873、k=15→−0.5627）；
5. 计数是否回到 45 条 / +48 / 1088（C2_grid 无参数化标记）。

---

## 7. 6b 快速复验结论（复审方 GLM-5.3-Flash · 2026-11-21）

**判定：5 项核验全部通过，0 P1 / 0 P2 → Step 6 出口达标，放行 Step 7（CHECKLIST）。**

| # | 核验项 | 结果 |
|---|--------|------|
| 1 | `GridATRConfig()` 无参构造 | **通过**：L260 `base_price: Mapping[str, float] \| None = None` → 构造可完成 → L266-268 局部 `base` 判 `None or 空` → `StrategyConfigError`（不再 TypeError） |
| 2 | `factory` 三入口 fail-fast | **通过**：`factory(None)` → `merged={}` → 无参构造 → 抛；`factory({})` 同；`factory(base_price={})` → 空 dict → `not base` → 抛。三处均 `StrategyConfigError` |
| 3 | E1 协议（PERIODS=30 / WINDOW=15） | **通过**：`views[15:]` 的 15 个 view history 各 15 行 ≥ 四模板窗长（grid 15 / trend 10 / momentum 5 / mean_reversion 5）；`head=dates[:15]` 零行 + 有效段 → `full.index` 与 `dates` 全等（30 行）；头部 `history=None` 段不进入 `signals_frame`；`base_price` 与首日 close 对齐不触发异常分支 |
| 4 | R 组 k 与 z 自洽（独立手算） | **通过**：z=−√((n−k)(n−1)/(n·k))，n=20：k=3 → −√(323/60)=−2.3202；k=4 → −√3.8=−1.9494；k=1 → −√18.05=−4.2485；k=16 → −√0.2375=−0.4873（≥−0.5 出场）；k=15 → −√(95/300)=−0.5627（<−0.5 保持）。夹具条款「末 k 行=L」保证 latest=L，符号正确 |
| 5 | 计数 45 / +48 / 1088 | **通过**：C2_grid 已无 `@pytest.mark.parametrize` 装饰器（L797-805 单函数三 raises）；参数化仅剩 C7（4 例 → +3）；§4.7 计数行已改「C7 参数化 4 例额外 +3」；与 DESIGN §5/D11 的 1088 一致 |

**顺带核实的修复**：F-I7 `mask(std == 0, 0.0)` + 注释更新（L621-622/L650）；F-I8 `__init__` 顺序 grid→trend→momentum→mean_reversion（L657-680）；F-I11 `cast(pd.DataFrame, atr(...))`（L305-314）+ `from typing import Any, cast`；F-I9 垃圾注释已删；F-I10 tests.yml 原文含两个 flag；F-I12 V4 可测表述（L857）。

**移交 Step 9 的唯一注记**：`write_price_fixture` 的 high/low 关键字名（`high_prices`/`low_prices` vs `high`/`low`）以 `_synth_fixture.py` 实际签名为准（IMPL §4.7 已自留核对注记，非缺陷）。
