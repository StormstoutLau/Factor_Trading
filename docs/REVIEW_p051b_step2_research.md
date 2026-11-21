# REVIEW：P-051b Step 2 异构独立复审（调研文档）

> **复审对象**: [RESEARCH_p051b_strategy_templates.md](RESEARCH_p051b_strategy_templates.md)（§1-§18，1126 行）· 代码时点 HEAD `9c914df`
> **复审方**: GLM-5.3-Flash（**异构**于 Step 1 调研作者 DeepSeek-V4.1-Flash，RULE-5 满足）
> **复审日期**: 2026-11-21
> **复审方法**: 独立取证——不采信作者转录：代码实读 / grep 复跑 / 闭式手算 / 基线复测（collect-only 实跑）
> **阅读范围**: §17.4 最小必读清单 + §17 / §18 全文 + §13.7 引用纪律抽查 + 独立取证扩展

---

## 0. 判定

| 项 | 结论 |
|----|------|
| **P1 缺陷** | **0 条** → Step 2 出口达标，**可进 Step 3** |
| P3 备注 | 4 条（均不阻断，已给出 Step 3 动作） |
| §17.4 五条质疑 | 5/5 全部关闭（1/2/4 由 §18 回答，复审确认；3/5 由复审独立关闭，见 §3） |
| §18 三项缺口闭合真实性 | **逐项复核通过，无幻觉**（见 §2） |

---

## 1. 独立取证记录（复审者自证，非采信作者）

| # | 核查项 | 复审方法 | 结果 |
|---|--------|----------|------|
| V1 | E5 `set_signal` 权重校验 | 实读 [engine_v2.py L614-656](../core/engine_v2.py#L614-L656) | index fail-fast L632、未知标的 L634、非负 L640、行和 `> 1.0 + 1e-9` L642、缺列补 0 L637——**与文档逐字一致** |
| V2 | E7 registry | 实读 [registry.py L225-230 / L341-359](../core/registry.py#L341-L359) | `get_strategy_registry()` / `register_strategy` 均在引用行号处，**行号精确** |
| V3 | E2/E4 `MarketView` | 实读 [strategy.py](../core/strategy.py) | 5 字段 frozen dataclass；L288 `reindex`、L289 `get_adj_price("close","raw")`、L300 `returns_matrix.iloc[i - returns_window : i]`——**行号精确**（文档引 L299-300，切片实际在 L300，±1 行内） |
| V4 | U-P051b-8 依据 | 实读 [validation.py L17 / L51](../core/validation.py#L17) | `MULTIPLE_TESTING_SUPPORTED = False`、`n_trials: None`——**属实** |
| V5 | §18.1 A3 grep | 复审者**独立复跑**同 pattern 全仓 grep | **0 命中** ✓ |
| V6 | §18.1 A1/A2 构造点穷举 | 全仓 grep `MarketView\(` | 全仓仅 **3 处**（strategy.py:302 生产 + test_p044:112/277 测试），三处均为**关键字**构造（测试文件实读确认）✓ |
| V7 | E6 基线读数 | 本机 `.venv` 实跑 `pytest --collect-only -q` | 总数 **1040** ✓；`-k golden` → **22/1040** ✓（4.78s / 4.67s） |
| V8 | golden 机制 | 实读 [_golden_cases.py](../tests/_golden_cases.py) | 单一来源：`CASE_IDS = G1..G7` 显式清单 + 共享构造器；新增 golden 必须改该文件 + `scripts/record_golden.py` 录制——**结构上可保证 I8** |
| V9 | F4 引用纪律 | 抽查 §13.7 | 引用带 DOI/arXiv 号，且「摘要级 / 未取得」单列段落**限定引用强度**——标注纪律符合 SPEC F4 |
| V10 | 工作区状态 | `git status` / `git log -1` | HEAD `9c914df`，仅调研文档 1 个未跟踪文件——**与文档「代码证据时点」声称一致** |

---

## 2. §18 三项缺口闭合复核（无幻觉确认）

### 2.1 缺口 1（A1 additive）——**成立**

- V5/V6 已独立复验静态面。动态面（A4-A6 探针）脚本已删、输出为作者转录，**不可重放**——但语义可从第一性原理演绎复验：
  - `hash(view)`：frozen dataclass 的 `__hash__` 对逐字段 tuple 求哈希，`pd.Series.__hash__ is None` → **加字段前后均 TypeError** ✓；
  - `view == other`：逐字段 tuple 比较，Series `==` 返回元素级 Series → truth 值歧义 **ValueError**（加字段前后同）✓；
  - `runtime_checkable` Protocol 只检查方法存在性，与 dataclass 字段数无关 → **`isinstance` 判定不受加字段影响** ✓（§17.4 质疑 1 的剩余面关闭）。
- 结论：A1 真 additive 维持；「末位 + 默认值」实施注意点正确且必要。

### 2.2 缺口 2（`history` 契约）——**定稿自洽**

- 9 条款与 E4 同窗论证（`iloc[i-W:i]` ↔ `returns_window`）一致；最小窗长 `W ≥ max(ma_n, entry_n, exit_n, max(lookbacks), atr_period+1)` 与 §18.3 各模板需求逐项吻合（ts_momentum 需 120、trend 需 60、grid 需 15 ≥ 14+1）✓。
- 「dict vs 三个独立字段」「不用 HistoryWindow 类」的成本收益论证成立（mypy 文件数 +1、比较语义再定义成本真实存在）。

### 2.3 缺口 3（四模板闭式）——**手算逐项复核通过**

复审者独立手算（禁录制纪律）：

| 模板 | 复算内容 | 结果 |
|------|----------|------|
| mean_reversion | sample variance（ddof=1）推导：var = k(n−k)d²/[n(n−1)] → z² = (n−k)(n−1)/(n·k) | **与文档公式一致** ✓ |
| mean_reversion k 表 | k=1→√18.05=4.2485 / k=2→√8.55=2.9240 / k=3→√5.3833=2.3202 / k=4→√3.8=1.9494 / k=15→√0.31667=0.5627 / k=16→√0.2375=0.4873 | **六行全对** ✓；entry(≥2.0)/exit(≥−0.5) 判定方向全对 ✓ |
| mean_reversion 不变量 | k=1 → z=−(n−1)/√n；n=20 → −19/√20 = −4.248529 | ✓ |
| ts_momentum | 9 个收益值逐一复算（A: −0.10/+0.50/+0.125；B: +0.60/+0.3333/+0.1429；C: −0.25/−0.0625/+0.0714）→ 票数 2/3/1 → min_votes=2 入选 A、B | ✓ 输出 {A:0.5, B:0.5} 和=1 ✓ |
| trend_breakout | 入场 11>max(high)=10 且 11>MA60=10；拒绝 10.5<11（双条件反伪通过设计）；出场 8.5<min(low[-10:])=9 | ✓ |
| grid_atr | TR=max(1.0,0.5,0.5)=1.0；全 TR 相等 → 任意种子 ATR=1.0（15 日 ≥ atr_period+1=15 ✓）；权重表 j=floor((B−P)/1) 逐行对；归一 1/3+1=4/3 → 缩放 3/4 → {0.25,0.75} 和=1；止损 10×0.8=8.0 优先于加仓 | ✓ |

**ddof 假设检查**：公式依赖 sample std（ddof=1），文档 L1055 已显式声明「std 用 ddof=1」（pandas `.std()` 默认）——假设已声明，无缺陷。

---

## 3. §17.4 / §18.6 两条核心质疑关闭（复审者独立关闭）

### 质疑 3：等权 `1/n` 与 `≤1+1e-9` 的浮点相容 → **相容，无缺陷**

- 校验式实读：`(values.sum(axis=1) > 1.0 + 1e-9).any()`（engine_v2.py L642），方向为 `>` 且容差 1e-9。
- IEEE 754 双精度下 n 份 `1/n` 求和误差上界 O(n·2⁻⁵²) ≈ n×2.2e-16：
  - n=3：`1/3` 双精度值三连加依 round-half-even **精确收敛到 1.0**；
  - 任意现实 n（≤10³）：误差 ≤ ~1e-13，**比 1e-9 容差小 4 个数量级**；
  - grid_atr 归一（1/3×3/4=0.25、1×3/4=0.75，和=1.0）同样 ≤ 数 ulp。
- 非负性 ✓（1/n>0）；NaN 面 ✓（`signals_frame` 物化 0.0 + `set_signal` `fillna(0.0)` 双保险）。

### 质疑 5：是否新增 golden → **零新增可达**

- golden 为**显式 case 清单制**（V8）：新增 golden 必须修改 `_golden_cases.py` 并显式录制，不存在隐式生成路径。
- §18.3 全部测试面为**闭式断言**（手算数值 + 不变量），不录制任何行为基线 → I8（零新增、22 条零重录）结构性可达。
- 22 条零重录由 V7 独立复测背书。

---

## 4. P3 备注（不阻断，附 Step 3 动作）

| ID | 备注 | Step 3 动作 |
|----|------|-------------|
| P3-1 | §18.1 A4-A6 探针证据为转录级（脚本已删、不可重放）；结论已由复审者第一性原理演绎复验维持 | DESIGN 时把「hash/== 语义不变」固化为正式 pytest 回归断言，替代一次性探针 |
| P3-2 | mean_reversion / ts_momentum 的 z 值与收益**只吃 history（≤t−1）**、不吃当日 `prices`（§18.3.5 断言 6 显式证明）——自洽且无前视，但相对引擎 `next_open` 节奏多滞后一 bar（保守方向，非缺陷） | Step 3 评估是否将当日收盘并入窗口；若并入须同步改断言 6 表述 |
| P3-3 | §18.3.1 边界约定「sign(0)→0 票」在样例中未被覆盖（无一收益恰为 0），断言清单亦无 sign(0) 用例 | 测试规格补 1 条 sign(0) 边界用例，避免约定沦为未测条款 |
| P3-4 | 基线 1040/22 以 collect-only 复测通过；「pytest 1040 全绿」运行态未在本机重跑（以 CI 记录为准） | Step 9 门禁时以实跑读数为准 |

---

## 5. 出口与移交

- **Step 2 出口「0 P1」达标**，本批可进入 Step 3（DESIGN）。
- Step 3 必做输入：U-P051b-1..6 定稿（U-P051b-7 已由用户裁决）、`history` 契约按 §18.2 落条款、四模板闭式按 §18.3 写入测试规格（含 P3-3 的 sign(0) 补例）、声明式四问（U-P051b-10）。
- 移交声明：本报告全部证据为复审者独立取得（V1-V10），未复用作者探针输出；外部引用真实性未全量回源（抽查 V9 通过，标注纪律符合 F4）。
