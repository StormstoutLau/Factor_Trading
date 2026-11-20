# RESEARCH：P-051a 策略接线底座（vol/ATR 波动原语 + `apply_sizing` 引擎接线）

> **批次**: P-051a · **Step 1 调研** · 日期 2026-11-20
> **执行序**: 关键路径下一项（P-050 done → **P-051a** → P-051b → P-051c）；总纲 L268 F5 的 `strategies/` 模板库硬前置
> **判档**: **T1**（新增 `core/volatility.py` 纯函数模块 + `core/engine_v2.py` 单点接线 + `core/config.py` 一个可选字段 + 测试；**不新增 golden**）
> **上游**: [PROGRESS §1.4](PROGRESS.md) P-051a 行（2026-11-20 建行）；[DESIGN_p047](DESIGN_p047_position_sizing.md) 四项遗留（§1 F-S8-P047-1 / §2.0 F6 / §R4 L319 / §13 O-S8-P047-2）；[RESEARCH_p047](RESEARCH_p047_position_sizing.md) §6 B1 / §7 S2-S3；[DESIGN_p048](DESIGN_p048_risk_overlay.md) D1 三层架构
> **代码证据时点**: HEAD `95a6f6c`（仅 docs 提交；代码与 `6fe5e08` 逐字一致，工作区干净）
> **基座**: 正文 DeepSeek-V4.1-Flash
> **取证声明**: 本仓源码 T1（逐字读码，标 HEAD + 行号）；外部规范仅用到 pandas 既有语义，无新增外部依赖；E4 闭式推导不依赖运行输出
> **本步只调研**：不改代码、不建分支、不提交

---

## 0. 一句话结论

P-051a 的实质是**把 P-047 已交付但零消费的契约接到引擎执行链上，并补齐两个纯函数原语**：`core/volatility.py`（`estimate_volatility` + `atr`）、`BacktestConfig.sizing`（默认 `None` → 零行为）、`_execute_rebalance` 在 **optimizer 之后、risk overlay 之前** 调用 `apply_sizing`。`kelly` / `risk_parity` 不在引擎接线（前者缺 μ 估计器，后者只输出诊断），`cash_budget_scale` / `pyramid_step` / `holding_age` 继续零接线（归 P-051b/c）。F-S10-P051-1（波动原语归属）以机械判据裁定 **归 P-051a**：无需任何数据管道改动，DESIGN_p047 L319「P-051 数据层」是拆批前假设，Step 3 需登记订正。

---

## 1. 触发与题干

### 1.1 触发

用户 2026-11-20 裁决：P-051 拆 **P-051a（接线底座）/ P-051b（模板库）/ P-051c（生命周期）** 三批，先开工 P-051a。同日完成台账第 7 次断档收口与 U-P046-12 一手原文解结，P-051a 为关键路径下一项。

### 1.2 题干（总纲 L268 F5 摘要）

> P-051 策略模板+生命周期：`strategies/`（网格/趋势/时序动量/均值回归）+ registry + lifecycle（F5）。验收：晋级门机械化；regime 切换样本外验证。

P-051a 只做「模板能跑起来」的底座：波动原语 + sizing 接线；模板本身与生命周期分别归 b/c。

### 1.3 本批承接的四项 P-047 遗留（逐字锚点）

| # | 遗留 | 原文锚点 | 本批处置 |
|---|------|----------|----------|
| L1 | 波动原语未落地 | [DESIGN_p047 §1](DESIGN_p047_position_sizing.md)：B1 的 `estimate_volatility`/`atr` 不落 P-047，`SizingConfig.vol_lookback/atr_period/atr_k` 为「预留字段，本批零消费」；[sizing.py L53-55](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L53-L55) | **落 `core/volatility.py`**（§5 S-A） |
| L2 | `zero_vol` warning 缺失 | [DESIGN_p047 §2.0 F6](DESIGN_p047_position_sizing.md)：「warning 由接线方（P-051）落地」 | **引擎接线层落 `logger.warning`**（§6.4） |
| L3 | `insufficient_history` 诊断缺失 | [DESIGN_p047 §R4 L319](DESIGN_p047_position_sizing.md)：「`insufficient_history` 诊断与样本充足性判定随波动原语批次落地」 | **接线层按 `vol_lookback` 判定 + 诊断**（§6.3） |
| L4 | `SizingState` JSON 往返无验收 | [DESIGN_p047 §13 O-S8-P047-2](DESIGN_p047_position_sizing.md)（L439）：「登记随 P-051 接线批验收」 | **验收测试（零生产 API 变更）**（§5.7） |

### 1.4 显式不做

| # | 不做 | 归属 |
|---|------|------|
| N1 | `strategies/` 模板（网格/趋势/时序动量/均值回归）+ registry | P-051b |
| N2 | 晋级门 / 监控 / 退役 / 多策略虚拟子账户 | P-051c |
| N3 | 矩阵式凯利 / 非等风险预算求解 | P-046c（U-P047-2） |
| N4 | `cash_budget_scale` 预交易预算接线 | 无消费方；等实盘/纸面交易批次（P-053） |
| N5 | `pyramid_step` / `holding_age` 接线 | 需逐持仓状态存储 → P-051c |
| N6 | 短仓/期货的 sizing（负权重语义） | P-058 / 后续批次（P-047 契约明确不做负权重） |
| N7 | 改 `apply_sizing` / `vol_target_scale` 既有语义或 P-047 golden | 契约锁定 |
| N8 | 修 P-048 overlay 的年化口径问题（若成立） | 登记观察项 O-P051a-2，不在本批动 |

---

## 2. 代码事实基线（E3 @`95a6f6c`）

### 2.1 可复用资产

| # | 资产 | 位置 | 复用方式 |
|---|------|------|----------|
| 1 | `SizingConfig`（19 字段，frozen） | [sizing.py L41-93](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L41-L93) | 直接作为 `BacktestConfig.sizing` 的类型；`__post_init__` 已含 5 项合法性校验（F-R3 订正） |
| 2 | `apply_sizing` 分派 | [sizing.py L243-359](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L243-L359) | `method="none"` 幂等；`vol_target` 组合缩放；`risk_parity` 只写 `rc_pct`；未知 method 抛 `ValueError`（L313-314） |
| 3 | `vol_target_scale` | [sizing.py L200-220](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L200-L220) | `scale=min(target/σ_p,1)`；`σ_p==0 → (原权重, 1.0, "zero_vol")` — **无副作用、无 logger** |
| 4 | `estimate_cov` 唯一协方差入口 | [portfolio.py L199-228](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L199-L228) | 引擎接线复用它构造 Σ（与 optimizer/overlay 同源） |
| 5 | 价格面板 | [data.py L501-548](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L501-L548) | `get_adj_price(kind, mode)` 覆盖 `open/high/low/close`；`_exec_price` 统一 raw（[engine L704-708](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L704-L708)） |
| 6 | Bar 帧消费先例 | [stops.py L17](file:///f:/Coding/Factor_Trading_v3.0/core/stops.py#L17)（`_BAR_KEYS`）/ [L48-55](file:///f:/Coding/Factor_Trading_v3.0/core/stops.py#L48-L55)（`StopBar`） | ATR 原语的输入形状与 `stops` 一致：DataFrame 面板 + 列=代码 |
| 7 | 三层架构裁决 | [DESIGN_p048 D1](DESIGN_p048_risk_overlay.md)（L43）：「RiskModel(pre) → Optimizer(in) → RiskOverlay(post)」 | sizing 层插入位置的架构依据（§5.2） |
| 8 | overlay 复用 sizing 先例 | [risk_overlay.py L26 / L268-276](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L268-L276) | `from core.sizing import vol_target_scale`；证明 `core.sizing` 可被上层安全依赖（无环） |

### 2.2 现状缺口证据

| # | 事实 | 证据 |
|---|------|------|
| E1 | `apply_sizing` 全仓**零生产调用**（仅 `core/sizing.py` 定义 + 测试） | 全仓 grep `apply_sizing`：`core/sizing.py` 4 处（`__all__`/def/内部）+ `tests/test_p047_position_sizing.py` 7 处，无其他引用 |
| E2 | `cash_budget_scale` / `pyramid_step` / `holding_age` 同样零生产调用 | 同上 grep（仅定义与测试） |
| E3 | 现存唯一波动原语是 `vol_target_scale`（消费外部 Σ），**无 `estimate_volatility` / `atr`** | 全仓 `*.py` grep `\bATR\b\|average_true_range\|true_range\|realized_volatility`：仅 `tests/test_p047_position_sizing.py` 2 处**注释**命中，0 处实现 |
| E4 | `SizingState` 无 `to_dict/from_dict`，无往返测试 | [sizing.py L119-125](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L119-L125)；`tests/` grep `round_trip|round-trip` 仅 `docs/` 命中 |
| E5 | `BacktestConfig` 无 sizing 字段 | [config.py L352-436](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L352-L436)（P-048 `risk_overlay` L424 / P-050 三字段 L426-430） |
| E6 | 引擎 cob 计算仅在 scores 模式且仅服务 optimizer | [engine L1325-1345](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1325-L1345)；weights 模式显式 `returns_data = None`（L1323） |
| E7 | 引擎 overlay 位于 optimizer 之后、`build_target_positions` 之前 | [engine L1377-1395](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1377-L1395) |
| E8 | `build_target_positions` 已内建 `value_buffer=0.985` + 整手 | [target_positions.py L43-54](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L43-L54) |

### 2.3 行为锁（零行为判据来源）

| 锁 | 内容 | 依据 |
|---|------|------|
| B1 | `BacktestConfig.sizing = None` 时，`_execute_rebalance` 权重路径与 HEAD 逐值一致 | 新增字段默认 None + 分支短路 |
| B2 | 既有 22 条 golden 期望值零修改（`tests/golden/` 不新增子目录） | P-059 已锁；本批目标是纯函数新符号 + opt-in 接线 |
| B3 | `apply_sizing(method="none")` 仍是输入副本（[V1](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p047_position_sizing.py#L49-L58)） | 契约 I4 |

---

## 3. 取证

### 3.1 E3 静态读码（本仓，T1）

- `SizingConfig` 的 `vol_lookback=60` / `atr_period=14` / `atr_k=2.0` 三字段全仓仅定义处 3 行（[sizing.py L53-55](file:///f:/Coding/Factor_Trading_v3.0/core/sizing.py#L53-L55)），零消费 → 与 P-047 DESIGN 声明一致。
- `apply_sizing` 的裁剪层**无条件**把权重夹到 `[min_weight, max_weight]`（L316-324）。`min_weight` 默认 0.0 → 对负权重（期货/股票负持仓研究模式）会把空头夹成 0，**属静默语义破坏**。这是本批必须显式规避的边界（§7 I2）。
- `apply_sizing` 的 kelly 分支在 `expected_returns is None` 时逐标的写 `no_expected_return` 并 `continue`（L285-287；L270 为分支起点，F-R4 订正），即**静默 no-op**；引擎若无 μ 供给，直接接 kelly 会「配了但什么都没发生」→ 必须 fail-fast（§5.4）。
- `estimate_cov` 的列集来自 `returns_data.columns`（= `dm.stock_codes`，engine L1330-1334 构造），因此 `target_weights.index ⊆ cov.columns` 在纯股票路径恒成立；期货合约代码不在 `stock_codes` 中 → 又一「跳过 sizing」的理由（§6.2）。

### 3.2 E4 闭式推导（不依赖运行）

**样本波动闭式**：收益率 `[0.01, -0.01, 0.02, -0.02]`，`ddof=1` → 均值 0，方差 `(1e-4+1e-4+4e-4+4e-4)/3 = 3.3333e-4`，`σ = 0.0182574`，年化 `×√252 = 0.0182574×15.874508 = 0.289827`。样本数 2 的闭式：`[0.01,-0.01]` → `σ = √2e-4 = 0.0141421`，年化 `0.224499`。

**Wilder ATR 闭式**（`period=3`）：

| 日 | H | L | C | TR |
|---|---|---|---|---|
| 1 | 10.5 | 9.5 | 10.0 | 1.0（首日无 C_prev → H−L） |
| 2 | 11.0 | 10.0 | 10.8 | max(1.0, 1.0, 0.0)=1.0 |
| 3 | 11.2 | 10.5 | 11.0 | max(0.7, 0.4, 0.3)=0.7 |
| 4 | 11.5 | 10.8 | 11.3 | max(0.7, 0.5, 0.2)=0.7 |
| 5 | 11.8 | 11.0 | 11.6 | max(0.8, 0.5, 0.3)=0.8 |

- 前 `period=3` 个 bar（索引 0/1/2）为 NaN；
- `ATR[3] = mean(TR[1..3]) = (1.0+0.7+0.7)/3 = 0.8`；
- `ATR[4] = (ATR[3]·(period−1) + TR[4]) / period = (0.8·2 + 0.8)/3 = 0.8`。

以上两式即 B 组测试的期望值来源，不走实现自证。

### 3.3 单位一致性核查（新发现）

`vol_target_scale` 是**无量纲**函数（`scale = target_vol / σ_p`），单位由调用方保证。引擎侧 Σ 来自**日频**收益率（`self._returns_matrix = self.dm.returns.values`，[engine L345](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L345)），而 `SizingConfig.target_vol=0.15` 是**年化**口径 → 接线必须显式换算，否则 `σ_p≈0.02` 使 `scale` 恒为 1（形同未接）。本批裁决：**接线层把 Σ 年化（`×252`）后传入**，`apply_sizing` 保持无量纲（§6.2 / I4）。
同一问题在 P-048 overlay 路径潜在存在（[risk_overlay.py L268-276](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L268-L276) 传日频 Σ + 年化 `target_vol`），但 `RiskOverlayConfig.target_vol` 默认 `None`（L52）→ 默认路径不触发；登记 **O-P051a-2**，不在本批修。

---

## 4. 缺口清单（G-P051a-*）

| ID | 缺口 | 类型 | 关闭方式 |
|----|------|------|----------|
| G1 | 无波动/ATR 原语实现 | 缺失能力 | 新增 `core/volatility.py`（§5.1 / §6.1） |
| G2 | `apply_sizing` 无引擎消费点 | 断链 | `_execute_rebalance` 插层（§5.2 / 6.2） |
| G3 | `BacktestConfig` 无 sizing 承载 | 配置缺口 | 新增 `sizing: SizingConfig \| None = None`（§5.3） |
| G4 | 引擎无 Σ 供给（weights 模式恒 None） | 输入缺口 | 接线层按 `vol_lookback` 独立构造（§6.2） |
| G5 | 日频 Σ 与年化 `target_vol` 单位不一致 | 正确性陷阱 | 接线层 `×252`（§6.2 / I4） |
| G6 | `zero_vol` 无告警落点 | 可观测性 | 接线层 `logger.warning`（§6.4） |
| G7 | 样本不足无诊断 | 可观测性 | `insufficient_history` + 跳过 sizing（§6.3） |
| G8 | `SizingState` 无 JSON 往返验收 | 验收缺口 | 测试（零 API 变更，§5.7） |
| G9 | 负权重被 `min_weight` 静默截断 | 语义风险 | 短仓/期货路径**跳过 sizing**（§5.5 / I2） |
| G10 | kelly 无 μ 供给时静默 no-op | 静默失败 | `setup()` fail-fast（§5.4） |

---

## 5. 方案矩阵（Step 2 裁决输入）

### 5.1 S-A 波动原语归属与放置（**F-S10-P051-1**）

| 选项 | 位置 | 优点 | 缺点 | 机械判据结果 |
|------|------|------|------|--------------|
| **A** | `core/sizing.py` 追加两函数 | 零新文件；与 `vol_target_scale` 相邻 | 把「价格面板变换」塞进「权重→可执行权重」模块，职责混杂；`sizing.py` 的 Mapping 纯函数定位被稀释 | 不满足「单一职责」 |
| **B（推荐）** | 新建 `core/volatility.py` | 计算核单一职责；P-051b 模板与 P-051c 监控可直接复用；依赖仅 numpy/pandas；与 `timing.py`/`stops.py` 的模块化风格一致 | mypy 文件数 112→113 | ✅ 全部满足 |
| C | `core/data.py` DataManager 方法 | 与 DESIGN_p047 L319「数据层」措辞字面一致 | 计算核埋进 I/O 层，破坏「计算核无 I/O」可审计性；与缓存/PIT 耦合，难单测 | ❌ 违反总纲 §6 门禁精神 |

**归属机械判据（三条全过才归 P-051a）**：
1. 是否需要对数据管道（DataManager / 复权 / 停牌 / PIT）做任何改动？→ **否**（`get_adj_price` 已给 `high/low/close`，`stops.py` 已按同形 bar 帧消费）。
2. 消费方是否落在 P-051a 接线路径？→ **是**（`vol_lookback` 用于 Σ 窗口；ATR 供 P-051b 趋势/时序动量模板）。
3. 是否只依赖 `core` 内既有纯函数/标准库？→ **是**。

**结论**：归 **P-051a**，选 **B**。DESIGN_p047 L319 的「随波动原语批次（**P-051 数据层**）落地」是 P-051 拆批前的假设；拆批后不存在独立「数据层批」，且本批零数据管道改动 → 以机械判据为准。**Step 3 需在 DESIGN 登记对 L319 的订正（D-x）**，并在 PROGRESS P-051a 行注明「波动原语归属已裁决」。

### 5.2 S-B 接线插入点

| 选项 | 位置 | 评价 |
|------|------|------|
| A | optimizer 之后、overlay 之前 | ✅ 满足「overlay 是最后一道缩放」的架构语义；sizing 的 `min_weight>0` 抬升不会被 overlay 之外的动作回补 |
| B | overlay 之后、`build_target_positions` 之前 | 依赖 `prices/total_value` 已在 L1397-1425 算好，diff 更小；但 `min_weight>0` 时 sizing 可在 overlay 减仓后把权重抬回去 → 破坏「overlay 最后」 |
| C | weights 模式内（`set_signal` 侧） | ❌ 只覆盖一种信号模式，scores 模式漏接 |

**推荐 A**：把 `prices` 取价与 `total_value` 计算（当前 L1397-1425）**整体上移**到 overlay 之前，然后在 overlay 之前插入 sizing 段。移动的零行为证据：该段只读 `tracker`/`prices`，唯一副作用是缺价时 `logger.warning + return`（原路径同样在 `build_target_positions` 前 return），输出与当前逐值一致（由 22 条 golden + V12 引擎测试守护）。
**回退（R1）**：若 Step 9 发现上移导致任一 golden 差异，退化为 B（sizing 置于 overlay 之后），并显式约束「`min_weight` 必须为 0 时引擎才启用 sizing」，把约束写进 DESIGN。

### 5.3 S-C 配置承载

- `BacktestConfig.sizing: "SizingConfig | None" = None`（[config.py L423-424](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L423-L424) 的 `risk_overlay` 同构）。
- **类型仅注解 + TYPE_CHECKING 导入**（与 L15-16 同法）：默认值 `None`，运行期不 import `core.sizing`，避免把 numpy/pandas 拉进 `config` 的导入链。
- 引擎内 `from core.sizing import SizingConfig, apply_sizing`（engine → sizing 无环，`risk_overlay.py` 已验证同向依赖）。
- **不新增 CLI 参数**；不写 `core/config.py` 之外的新配置模块。

### 5.4 S-D 引擎支持的 method 子集

| method | 引擎接线 | 理由 |
|--------|----------|------|
| `none` | 支持（默认，零行为） | 兼容 |
| `vol_target` | **支持** | 本批主目标；Σ 由接线层供给 |
| `risk_parity` | **不支持**（`setup()` 抛 `ValueError`） | 只输出 `rc_pct` 诊断，无权重效果；引擎无诊断出口，接了等于静默无效 → 由 P-051b 策略层消费 |
| `kelly` | **不支持**（`setup()` 抛 `ValueError`） | 引擎无 μ 估计器；`expected_returns=None` 时 `apply_sizing` 静默 no-op（L270-277）→ 必须 fail-fast，禁止静默 |

**fail-fast 位置**：`BacktestEngineV2.setup()`（[L237](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L237)）内，`self.cfg.sizing is not None` 时校验 `method ∈ {"none","vol_target"}`，否则 `ValueError("引擎接线仅支持 method ∈ {none, vol_target}；kelly/risk_parity 由策略层消费（P-051b）")`。错误信息须含配置值与本批 ID。

### 5.5 S-E 短仓/期货路径

| 选项 | 做法 | 评价 |
|------|------|------|
| A（推荐） | `allow_short` 为真或存在 `_contract_specs` 时**跳过 sizing**，记 `sizing_skipped_short` 并在 `setup()` 打一次 warning | 零契约变更；不触碰 P-047「不做负权重」边界；P-050 golden 不受影响 |
| B | 给 `apply_sizing` 加 `allow_negative` 参数 | 改 P-047 冻结契约 + golden 面，超出本批 |
| C | 只对正权重子集跑 sizing | 语义破碎（Σ 缺空头腿），禁止 |

**推荐 A**。判据：P-047 DESIGN D2/D3 明确「不做做空/负权重（P-050）」，P-051a 是接线不是契约扩展；短仓 sizing 归 P-058。

### 5.6 S-F `cash_budget_scale` / `pyramid_step` / `holding_age`

均**不接线**：`cash_budget_scale` 与引擎既有 BUY 现金闸门（P-047 A2）+ `build_target_positions` 的 `value_buffer` 重叠；`pyramid_step`/`holding_age` 需要逐持仓持久状态（`SizingState` 存在哪里），属 P-051c 生命周期职责。本批仅保留纯函数与既有测试，不改一行。

### 5.7 S-G `SizingState` JSON 往返

| 选项 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 只加验收测试：`json.dumps(asdict(state))` → `json.loads` → `SizingState(**d)` 相等；不新增生产 API | 最小面积；frozen + 3 个标量字段，`asdict` 足够；与「不过度设计」一致 |
| B | 加 `to_dict/from_dict`（对齐 P-044 `StrategyState`） | 多 2 个公开方法 + 类型分支；当前无持久化调用方 |

**推荐 A**，并在 DESIGN 记一行「若 P-051c 需要持久化，再升级为 to_dict/from_dict」。登记 **O-P051a-1** 跟踪。

---

## 6. 精确语义（IMPL 输入）

### 6.1 `core/volatility.py`

```python
TRADING_DAYS = 252

def estimate_volatility(
    returns: pd.Series | pd.DataFrame,
    *,
    lookback: int = 60,
    annualize: bool = True,
    periods: int = TRADING_DAYS,
) -> pd.Series | pd.DataFrame:
    """样本波动（ddof=1）滚动估计；窗口内不足 lookback 个有效值 → NaN。"""
```

- 仅支持样本标准差（`method="sample"`）；**EWMA 不落本批**（无 λ/span 一手锚点，禁拍脑袋）。若将来需要，另立参数。
- 窗口语义：每个输出点使用**其之前（含当日）** `lookback` 行；窗口内任一 NaN 或行数不足 → NaN（禁止静默 0，RESEARCH_p047 S2）。
- `annualize=True` → `× sqrt(periods)`；`False` → 原始标准差。
- 输入类型保持：Series 进 Series 出，DataFrame 进 DataFrame 出。

```python
def atr(
    high: pd.Series | pd.DataFrame,
    low: pd.Series | pd.DataFrame,
    close: pd.Series | pd.DataFrame,
    *,
    period: int = 14,
) -> pd.Series | pd.DataFrame:
    """Wilder ATR。TR=max(H−L, |H−C_prev|, |L−C_prev|)；首日 C_prev 缺失 → TR=H−L。"""
```

- 前 `period` 个 bar 为 NaN；`ATR[period] = mean(TR[1..period])`；其后 `ATR[t] = (ATR[t−1]·(period−1) + TR[t]) / period`（§3.2 闭式）。
- 输入三方形状必须一致，否则 `ValueError`（fail-fast）。

### 6.2 引擎接线伪码（`_execute_rebalance`，overlay 之前）

```python
# 0) prices / total_value / allow_short 上移（原 L1397-1425 整体前移，行为中性）
prices = self._exec_price(dm, "close").loc[date]
total_value = compute_portfolio_value(...)
stock_short = self.cfg.allows_short(AssetType.STOCK)
allow_short = stock_short or bool(self._contract_specs)

# 1) sizing 层（opt-in；短仓/期货跳过）
sizing_cfg = self.cfg.sizing
if sizing_cfg is not None and sizing_cfg.method != "none":
    if allow_short:
        logger.warning("sizing 跳过：allow_short=True（P-051a 仅长仓股票路径）")
    else:
        window = sizing_cfg.vol_lookback
        if date_index < window:
            logger.warning("sizing 跳过：insufficient_history（%d < %d）", date_index, window)
        else:
            rets = pd.DataFrame(
                self._returns_matrix[date_index - window:date_index],
                index=dm.trade_dates[date_index - window:date_index],
                columns=dm.stock_codes,
            )
            cov_daily = estimate_cov(rets, method=self.cfg.optimizer.cov_method)
            cov_annual = cov_daily.to_numpy() * TRADING_DAYS      # ← R4 / I4：单位对齐
            codes = [str(c) for c in cov_daily.columns]
            result = apply_sizing(
                {str(k): float(v) for k, v in target_weights.items()},
                config=sizing_cfg,
                cov=cov_annual,
                codes=codes,
                total_value=float(total_value),
                prices={str(k): float(v) for k, v in prices.items()},
            )
            if result.diagnostics.reasons.get("portfolio") == "zero_vol":
                logger.warning("sizing zero_vol：Σ 退化，scale=1.0（P-047 F6）")
            target_weights = (
                pd.Series(result.weights).reindex(target_weights.index).fillna(0.0)
            )
```

- **输入完整性**：`codes` 取 `cov_daily.columns`（= `dm.stock_codes`），保证 `target_weights.index ⊆ codes`；期货合约代码不在其中 → 已由 `allow_short` 分支拦截（`_contract_specs` 非空时 `allow_short` 恒真，见 [engine L1405-1406](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1405-L1406)）。
- **`total_value` / `prices` 用于 `min_size/max_size`**；`granularity`/`cash_buffer` 的最终整手仍由 `build_target_positions` 统一出口（P-047 §4 边界 1，不重复落地）。
- **Σ 窗口用 `SizingConfig.vol_lookback`**，与 `cfg.optimizer.cov_lookback` 解耦（sizing 配置自持窗口），代价是 scores 模式可能多算一次 `estimate_cov`（60×N，可接受；Step 3 若需优化可加「lookback 相等则复用「）。
- **不重新归一化**：`apply_sizing` 已保证权重和 ≤1（L346-351），残差留现金。

### 6.3 `insufficient_history` 语义

| 条件 | 行为 |
|------|------|
| `date_index < sizing.vol_lookback` | 跳过 sizing（权重原样），`logger.warning` 含 `insufficient_history` 与两个数值；不改 `target_weights` |
| `estimate_cov` 返回全 0（退化） | 进入 `zero_vol` 分支（§6.4），`scale=1.0` |
| 价格缺失 | `apply_sizing` 内部 `dropped=["no_price"]`，引擎不额外处理（`build_target_positions` 已有不可定价语义） |

诊断出口仅日志（P-051a 不改 `_diagnostics` 结构，避免诊断层契约变更）；结构化落库归 P-051c 监控。

### 6.4 `zero_vol` 告警

- 触发：`result.diagnostics.reasons.get("portfolio") == "zero_vol"`。
- 动作：`logger.warning("sizing zero_vol：...")`，**权重不变**（`vol_target_scale` 已返回原权重 + `scale=1.0`）。
- 频率：每个再平衡日最多 1 条（不加去重状态，保持无状态）。

---

## 7. 不变式（I-P051a-*）

| ID | 不变式 | 验证 |
|----|--------|------|
| I1 | `cfg.sizing is None` ⇒ 22 条 golden 与 HEAD 逐值一致 | `-k golden` 22 通过 + 引擎集成测试 |
| I2 | `allow_short` 或存在期货合约 ⇒ sizing 零作用（权重逐值不变） | 单测：短仓配置 + sizing 配置 → 权重不变 |
| I3 | sizing 生效后 `sum(weights) <= 1.0 + 1e-12`（不加杠杆） | 单测断言 |
| I4 | 引擎传入的 Σ 必须已年化（`×252`），与 `target_vol` 同口径 | 闭式单测：构造已知日频 Σ → `scale = target_vol/(σ_daily·√252)` |
| I5 | 历史不足 ⇒ 跳过 + `insufficient_history` 告警，不抛异常 | 单测（caplog 断言） |
| I6 | `σ_p==0` ⇒ `scale=1.0` + `zero_vol` 告警，权重不变 | 单测（caplog 断言） |
| I7 | `method ∈ {kelly, risk_parity}` 配置 ⇒ `setup()` 抛 `ValueError` | 单测 |
| I8 | `core/volatility.py` 无 I/O、无全局写、无随机、无 logger | AST/grep（`open(|requests.|random|logging` = 0） |
| I9 | `SizingState` JSON 往返逐字段相等 | 单测 |
| I10 | golden 集合仍为 22，`tests/golden/` 无新文件 | `-k golden` 收集数 + 目录断言 |

---

## 8. DoD（可机械验收）

### 8.1 A 组：代码（6 项）

| ID | 验收项 | 证据出口 |
|----|--------|----------|
| A1 | `core/volatility.py` 新增：`TRADING_DAYS` / `estimate_volatility` / `atr`，`__all__` 三项 | 读码 + 单测 |
| A2 | `estimate_volatility` 样本口径 + NaN 语义 + 年化开关 | B1/B2 |
| A3 | `atr` Wilder 口径 + warmup NaN + 形状校验 | B3/B4 |
| A4 | `BacktestConfig.sizing: SizingConfig \| None = None`（TYPE_CHECKING 导入） | 读码 |
| A5 | `setup()` fail-fast：`method ∉ {none, vol_target}` → `ValueError` | B10 |
| A6 | `_execute_rebalance` sizing 段 + prices/total_value 上移 + 两条 warning | B5-B9 + `git diff` |

### 8.2 B 组：测试（12 项）

| ID | 用例 | 期望值来源 |
|----|------|------------|
| B1 | 样本波动闭式 | §3.2（0.224499 / 0.289827） |
| B2 | 窗口不足 / 含 NaN → NaN | 语义（§6.1） |
| B3 | ATR 闭式（period=3） | §3.2（0.8 / 0.8） |
| B4 | ATR warmup 前 3 个 NaN + 形状不一致 ValueError | 语义（§6.1） |
| B5 | `sizing=None` 引擎路径权重逐值不变 | 与 HEAD 行为锁 B1 |
| B6 | `vol_target` 缩放闭式（日频 Σ 年化后 scale 与手算一致） | §3.2 + I4 |
| B7 | `insufficient_history`：`date_index < vol_lookback` → 跳过 + 告警 | caplog |
| B8 | `zero_vol`：全 0 Σ → 权重不变 + 告警 | caplog |
| B9 | 短仓路径跳过 sizing | I2 |
| B10 | `kelly` / `risk_parity` → `setup()` 抛 `ValueError` | I7 |
| B11 | `SizingState` JSON 往返 | I9 |
| B12 | `-k golden` 仍 22；`tests/golden/**` 无新增目录 | I10 |

### 8.3 C 组：门禁（3 项）

| ID | 门禁 | 目标 |
|----|------|------|
| C1 | `pytest -q` 全绿 | 1024 + 本批新增（预计 12，实测为准） |
| C2 | mypy | 112 → 113 files 0 error（新模块入扫描面） |
| C3 | black `core tests` | 155 → 157 unchanged（两新文件一次成型） |

---

## 9. 基线读数与目标

| 读数 | 基线 @`95a6f6c`（代码同 `6fe5e08`） | 本批目标 | 口径 |
|------|--------------------------------------|----------|------|
| pytest 收集数 | **1024** | 1024 + 新增 | `pytest --collect-only -q`（本轮实测） |
| `-k golden` | **22 / 1024** | **22**（零重录） | 本轮实测 |
| mypy | **112 files 0 error** | 113 files 0 | 沿用批次基线命令 |
| black `core tests` | **155 unchanged** | 157 unchanged | 本轮实测（全仓口径 223） |
| `tests/*.py` | **111** | 112 | 本轮实测 |
| `core/*.py` | **44** | 45 | 本轮实测 |
| 工作区 | 干净；HEAD `95a6f6c` | — | `git status --short` 空 |

> 说明：mypy 112 为 P-050 关闭时读数；`95a6f6c` 仅 docs 变更，代码零 diff，故沿用。Step 9 须重跑并以实测为准。

---

## 10. 待裁决（Step 2 前必须收敛）

| ID | 议题 | 推荐 | 备选 | 影响面 |
|----|------|------|------|--------|
| U-P051a-1 | 波动原语归属（F-S10-P051-1） | **P-051a / 新模块 `core/volatility.py`** | `core/sizing.py` 追加；`core/data.py` | §5.1 |
| U-P051a-2 | 接线插入点 | **overlay 之前**（prices/total_value 上移） | overlay 之后 + 约束 `min_weight==0` | §5.2 |
| U-P051a-3 | 引擎 method 子集 | **仅 `none` / `vol_target`**，其余 fail-fast | 四种全接（kelly 需 μ 供给） | §5.4 |
| U-P051a-4 | 短仓/期货路径 | **跳过 sizing + 一次告警** | 扩展 `apply_sizing` 负权重语义 | §5.5 |
| U-P051a-5 | `SizingState` 往返 | **仅验收测试（零 API）** | 加 `to_dict/from_dict` | §5.7 |
| U-P051a-6 | ATR/波动年化常数 | **模块常量 `TRADING_DAYS=252`** | 新增 `SizingConfig.annual_periods` | §6.1 / I4 |
| U-P051a-7 | EWMA 波动 | **不落本批** | 落 EWMA（需 λ 一手锚点） | §6.1 |

**U-P044-3 处置建议**：**不纳入 P-051a**。判据：其触发条件为「P-051（策略模板库）或出现第三处信号实现」（[RESEARCH_p044 L175-179](RESEARCH_p044_strategy_interface.md)）；P-051a 只接线、不新增策略实现，第三处实现出现在 P-051b。建议把 PROGRESS P-051a 行中的「+ U-P044-3」改为「U-P044-3 → P-051b」（台账回写，待用户确认后随 Step 10 一并提交）。

**已裁决登记（本轮建议，待 Step 2 复审确认）**：U-P051a-1..7 全部取推荐列；U-P044-3 转 P-051b。

---

## 11. 与既有批次的边界

| 批次 | 边界 |
|------|------|
| P-047 | 只消费 `SizingConfig` / `apply_sizing` 既有语义；`core/sizing.py` **零 diff**（原语落新模块） |
| P-048 | overlay 仍是最后一道缩放；sizing 在其之前；不修 overlay 年化口径（O-P051a-2） |
| P-050 | 短仓/期货路径跳过 sizing；P-050 账目与 golden 零影响 |
| P-044 | `set_signal` / `_signal_mode` 不改；weights 模式与 scores 模式共用同一 sizing 段 |
| P-051b | 模板消费 `estimate_volatility` / `atr` / `SizingConfig.atr_period/atr_k`；引擎不接 kelly/risk_parity |
| P-051c | 消费 `SizingState`（若需持久化再升级 API）/ `pyramid_step` / `holding_age` |

---

## 12. 十步路线（本批，对齐 `SPEC_PROCESS.md` v1.7.x）

| Step | 产物 | 备注 |
|------|------|------|
| 1 | **本文** | 调研 + 缺口 + 方案矩阵 + 待裁决 |
| 2 | 异构复审（≠ DeepSeek-V4.1-Flash） | 机械复核 §2 行号、§3.2 闭式、§10 裁决 |
| 3 | `DESIGN_p051a_*.md` | D1-D8；含 DESIGN_p047 L319 订正 |
| 4 | 设计异构复审 | — |
| 5 | `IMPL_p051a_*.md` | 逐处代码 + V 规格 |
| 6 | 实现复审 | — |
| 7 | `CHECKLIST_p051a_*.md` | A/B/C 三组 |
| 8 | 一致性审计 | 四文档 + 台账 |
| 9 | TDD 实施 + 门禁 | 1024+ / golden 22 / mypy 113 / black 157 |
| 10 | 提交 + CI + 台账回填 | 用户授权后执行 |

---

## 13. 外部证据登记

本批**不引入外部方法学**：样本标准差与 Wilder ATR 的语义均以 [RESEARCH_p047 §7 S2-S3](RESEARCH_p047_position_sizing.md) 已登记口径为准（S3 的 TR 定义与 Wilder 平滑）。年化常数 252 为 A 股交易日惯例，不声称一手文献。EWMA（RiskMetrics λ=0.94）**不落本批**，故无需锚点。未检索网络，无外部抓取，不冒充 T1。

---

## 14. 本步自检

| 项 | 结果 |
|----|------|
| 行号锚点是否为 HEAD 实读 | ✅ 全部逐字读码（§2/§3/§5） |
| 闭式期望是否手算（非录制） | ✅ §3.2 两式 |
| 是否编造测试/门禁读数 | ✅ 无；pytest 1024 / golden 22 / black 155 / tests 111 / core 44 为本轮实测；mypy 112 沿用 `6fe5e08` 并注明 |
| 是否给出机械判据（F-S10-P051-1） | ✅ §5.1 三条判据 |
| 是否覆盖四项遗留 | ✅ §1.3 L1-L4 一一对应 |
| 是否声明不做 | ✅ §1.4 N1-N8 |
| 是否留待裁决 | ✅ §10 U-P051a-1..7 + U-P044-3 |
| 是否改代码 | ❌ 未改（Step 1 只调研） |

---

## 15. Step 2 异构独立复审（复审方 GLM-5.3-Flash，2026-11-20）

> **复审身份**: GLM-5.3-Flash（≠ Step 1 作者 DeepSeek-V4.1-Flash，RULE-5）。对象：§1-§14 全文读回 + 机械锚点独立重验 + 闭式手算复算 + 基线读数亲手重跑 + 裁决矩阵幻觉扫描。**未采信作者自报，全部结论以复审方独立取证为准。**

### 15.1 机械复核矩阵（复审独立重跑）

| # | 复核项 | 作者声明 | 复审取证 | 结果 |
|---|--------|----------|----------|------|
| 1 | 预留字段零消费 | sizing.py L53-55 仅定义 3 行 | grep 复跑：`vol_lookback`/`atr_period` 命中 L53/L54，`pyramid_step_atr` L68；全仓无其他消费 | ✅ |
| 2 | `apply_sizing` 零生产调用 | §2.2 E1 | grep `from core.sizing import` 全仓 4 命中：engine_v2（仅 `estimate_buy_cash`）/ risk_overlay（仅 `vol_target_scale`）/ test_p047 / tests/_scenarios_trace.py（仅 `estimate_buy_cash`）——**`apply_sizing` 确无生产调用方** | ✅ |
| 3 | `SizingState` 无往返测试 | §2.2 E4 | tests/ grep `round_trip\|to_dict\|from_dict`：命中全为 P-044 `StrategyState` / P-045 `StopState` 等，无 SizingState | ✅ |
| 4 | 代码证据时点 | 「`95a6f6c` 代码与 `6fe5e08` 逐字一致」 | `git diff --stat 6fe5e08..95a6f6c` = 仅 docs/PROGRESS.md + docs/RESEARCH_p046 | ✅ |
| 5 | 基线 pytest / golden | 1024 / 22 | `pytest --collect-only -q` = **1024**；`-k golden` = **22/1024**（复审复跑） | ✅ |
| 6 | 基线 black `core tests` | 155 unchanged | 复审复跑 `black --check core tests` = **155 files unchanged** | ✅ |
| 7 | 基线 tests/core 文件数 | 111 / 44 | 复审复数 = **111 / 44** | ✅ |
| 8 | kelly 静默 no-op | 「L270-277 写 no_expected_return 并 continue」 | 行为属实（L285-287：`reasons[code]="no_expected_return"; continue`），但**行号锚漂移**（见 F-R4）；且 diagnostics 实际有记录，「静默」成立于引擎面（引擎不落日志）而非 SizingResult 面 | ✅ 带订正 |
| 9 | `min_weight` 夹负权重 | L316-324 裁剪层 | 复读 L316-324 属实：`weight < min_weight → base[code]=min_weight`，默认 0.0 会把负权重夹 0 | ✅ |
| 10 | apply_sizing 未知 method 抛错 | L313-314 | 复读属实 | ✅ |
| 11 | weights 模式 `returns_data=None` | engine L1323 | 复读属实 | ✅ |
| 12 | overlay 位置与 prices/total_value 段 | engine L1377-1395 / L1397-1425 / L1405-1406 | 复读属实；上移行为中性论证成立（该段纯读 + 唯一副作用 warning+return，两序可观测行为无差） | ✅ |
| 13 | `_returns_matrix` 日频 | engine L345 | 复读属实 | ✅ |
| 14 | P-048 overlay 单位同源问题 | O-P051a-2 | 独立复算成立：risk_overlay L274-276 传日频 Σ + 年化 target_vol；典型 σ_daily≈0.02 → `min(0.15/0.02,1)=1` → vol 腿实际失效（仅显式配置时）。登记正当，本批不修 | ✅ |
| 15 | 样本波动闭式 | §3.2：0.224499 / 0.289827 | 手算复算：`[0.01,-0.01]` → √2e-4×√252 = 0.0141421×15.874508 = **0.224499** ✓；`[0.01,-0.01,0.02,-0.02]` → √(1e-3/3)×√252 = 0.0182574×15.874508 = **0.289827** ✓ | ✅ |
| 16 | ATR 闭式 | §3.2：TR=[1.0,1.0,0.7,0.7,0.8]，ATR[3]=0.8 | TR 序列手算一致 ✓；但 **seed=mean(TR[1..period]) 与 §6.1「首日 TR=H−L」条款冲突**（见 F-R1） | ⚠️ F-R1 |
| 17 | 引擎 → sizing 无环 | §5.3 | engine_v2 L28 已 `from core.sizing import estimate_buy_cash`（同向依赖先例） | ✅ |
| 18 | U-P044-3 归属判据 | 「触发条件=模板库或第三处实现」 | RESEARCH_p044 L175-179 原文核实；P-051a 无新策略实现 → 转 P-051b 成立 | ✅ |

### 15.2 发现清单

| ID | 级别 | 发现 | 处置要求 |
|----|------|------|----------|
| **F-R1** | **P2** | **ATR seed 约定内部不一致**：§6.1 同时定义「首日 C_prev 缺失 → TR=H−L」（产出 TR[0]）与「ATR[period]=mean(TR[**1**..period])」——TR[0] 在自定 seed 下**永不消费**（死语义）；且与 [RESEARCH_p047 §7 S3](RESEARCH_p047_position_sizing.md) 的自然读法（标准 Wilder：seed=前 period 个 TR **含** TR[0]）冲突。标准 Wilder seed 下 B3 期望应为 **(1.0+1.0+0.7)/3=0.9**，当前 §3.2/B3 锁定的 0.8 是非标准口径 | Step 3 DESIGN 必须二选一并写明依据：①标准 Wilder seed（B3 期望改 0.9，删除死条款）；②显式声明排除 TR[0] 的偏离口径（删除/标注「首日 TR=H−L」条款为不适用）。**收敛前不得进 Step 5** |
| F-R2 | P3 | 引擎对 `method="none"`（非 None）的处置只存在于 §6.2 伪码（全跳过），未入不变式组（I1 只锁 `None`）；且 sizing.py 自身契约有张力——L9「`none` → 完全零行为（返回输入副本）」vs L256「`none`…**但仍施加约束层**」。伪码全跳过 = 引擎面把 `none` 等同 `None`，与 L256 语义相悖 | DESIGN 显式裁决（建议：引擎面 `none` ⇒ 与 `None` 等价全跳过，opt-in 语义优先），并写明与 sizing.py docstring 的关系；I 组补对应用例 |
| F-R3 | P3 | §2.1「`__post_init__` 已含 **6 项**合法性校验」——实读 L70-80 为 **5 项**（kelly_fraction / target_vol / granularity / max_weight / min_weight） | 订正为 5 项 |
| F-R4 | P3 | §3.1 kelly 静默 continue 锚「L270-277」漂移：实际 `no_expected_return` 写入 + continue 在 **L285-287**（L270 为分支起点） | 订正行号；「静默 no-op」表述限定为引擎面（SizingResult.diagnostics 有记录） |
| F-R5 | P3 | **sizing vol_target × overlay target_vol 复合缩放交互未登记**：两层均做 `min(target/σ,1)`，同时启用会双重降杠杆（scale_vol_total = scale_sizing × scale_overlay）。默认均关 → golden 无风险 | DESIGN 补交互条款：允许同时启用但文档化复合语义，或约束互斥（推荐前者 + 文档化，保持层架构正交） |
| F-R6 | P3 | NaN 价格边界：apply_sizing 的 no_price 判定 `price is None or price <= 0.0`（L329-330）**不拦 NaN**（NaN≤0 为 False）；伪码直接传 `prices.items()`，停牌股 NaN 混入时 min_size/max_size 比较静默通过 | DESIGN 一句话钉死：伪码传参前过滤 NaN（或显式声明依赖 `tradable_mask` 保证——`daily_signal[tradable_mask].dropna()` 已排除不可交易股，需论证充分性） |

### 15.3 观察项（不计数，CHECKLIST 精确表述用）

| ID | 内容 |
|----|------|
| O-R1 | `atr_period`/`atr_k` 在 P-051a 后**仍零消费**（消费拆分：`vol_lookback`→引擎接线、`atr_*`→P-051b 模板）。CHECKLIST 遗留 L1 闭合语义须按此精确表述，禁止「预留字段全部闭环」的过度声明 |
| O-R2 | 「两新文件」= `core/volatility.py` + `tests/test_p051a_*.py`，与 §9 计数（core 44→45 / tests 111→112 / black 155→157）自洽 ✅ |

### 15.4 裁决矩阵幻觉扫描（U-P051a-1..7 + U-P044-3）

| 裁决 | 推荐 | 幻觉检查 | 结论 |
|------|------|----------|------|
| U-P051a-1 归属 | P-051a + 新模块 | 三判据逐一有已验证代码事实（`get_adj_price` L501-548 实读 / stops 同形 bar 先例 L17+L48-55 / core-only 依赖） | ✅ 无幻觉 |
| U-P051a-2 插入点 | overlay 前 | 「min_weight>0 抬回被减权重」经 L316-324 实读验证；overlay 最后语义经 DESIGN_p048 D1 L43 原文验证 | ✅ 无幻觉 |
| U-P051a-3 method 子集 | 仅 none/vol_target | kelly 静默 no-op 经 L285-287 实读验证（行号订正 F-R4）；risk_parity 仅诊断经 L306-311 实读验证 | ✅ 无幻觉 |
| U-P051a-4 短仓跳过 | 跳过 + 告警 | P-047「不做负权重」边界 + 裁剪层夹 0 事实双锚 | ✅ 无幻觉 |
| U-P051a-5 SizingState 往返 | 仅验收测试 | E4 缺口实存（15.1 #3）；frozen+3 标量字段，asdict 足够 | ✅ 无幻觉 |
| U-P051a-6 年化常数 | 模块常量 252 | 避免 SizingConfig 契约变更；I4 闭式自洽 | ✅ 无幻觉 |
| U-P051a-7 EWMA | 不落本批 | RESEARCH_p047 S2 明文「method=sample\|ewma」，但无 λ/span 一手锚点 → 缓议正确 | ✅ 无幻觉 |
| U-P044-3 | 转 P-051b | RESEARCH_p044 L175-179 原文核实 | ✅ 无幻觉 |

### 15.5 复审结论

**有条件通过（0 P1 / 1 P2 / 5 P3 / 2 观察）**。

- **0 方向性推翻**：波动原语归 P-051a（新模块）、插入点（overlay 前）、method 子集（none/vol_target + fail-fast）、短仓跳过、`SizingState` 仅测试、U-P044-3 转 P-051b——全部经受独立复核成立；
- **1 P2（F-R1）**：ATR seed 约定必须在 Step 3 DESIGN 内收敛（二选一 + B3 期望值随动），收敛前不得进 Step 5 TDD；
- **5 P3**：F-R2（none 语义钉死）/ F-R3（校验计数订正）/ F-R4（行号订正）/ F-R5（双层缩放交互）/ F-R6（NaN 价格）随 DESIGN 一并处置；
- Step 1 文档的 §3.1/§2.1 两处行号/计数订正（F-R3/F-R4）授权随 Step 3 修订一并落盘（本复审不改 Step 1 正文，保持取证时点原貌）。
