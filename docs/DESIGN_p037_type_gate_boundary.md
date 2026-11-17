# DESIGN：P-037 类型门禁边界收口

> **批次**: P-037 · **Step 3 设计** · 日期 2026-11-17 · 来源日期 2026-11-17（读取日）
> **判档**: **T1**（追加 mypy target = 变更 CI 门禁判据；判档规则 2）
> **作者基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构；复审会话须先自报基座，无法证实则登记 U-P037-3 而非默认异构）
> **上游**: [RESEARCH_p037](RESEARCH_p037_type_gate_boundary.md)（§4 20 条 10 簇 / §5 C1-C2 / §6 M-A / §11 Step 2 复审 pass：2 P2 + 5 P3 当轮回写）
> **代码证据时点**: HEAD `ad7815d`；门禁现状 `.github/workflows/tests.yml` L46 = 10 面

---

## 1. 设计目标

把类型门禁的最后两个 Python 目录纳入，并真修到 0：

| 目标 | 判据 |
|------|------|
| G1 门禁覆盖 | target **10 面 → 12 面**：追加 `tools examples`（DESIGN-D2） |
| G2 真修非压制 | 20 条（3.12 口径 19 + 3.10 追加 1）全部按根因修复；**新增 `# type: ignore` = 0**；不新增 `[[tool.mypy.overrides]]` |
| G3 行为守恒 | golden 13 零重录；pytest **760 不变**（X=0）；`except Exception` 恒 22；生产面 10 面 diff 为空（除门禁行） |
| G4 多口径一致 | 修复后 `mypy tools examples` 在 **三口径**（3.12+2.4.6 / 3.12+2.5.5 / 3.10+2.2.6）均 0 |
| G5 可回退 | 单批单提交（代码 + tests.yml + adapter + 本批文档），revert 即回到 10 面 |

---

## 2. 决策详述

### D1 范围：`tools` + `examples`，剔除 `demo` / `memory`

- `demo/` 与 `memory/` **零 `.py` 文件**（mypy exit 2）→ 无可纳入对象（RESEARCH §2.3）。
- `tools`（4 文件 / 5 errors）与 `examples`（7 文件 / 14 errors）为实际范围。
- **被拒绝的替代方案**：
  - 仅纳入 `tools`（11 面）：`examples` 是 README Quick Start 入口，保护价值更高；14 条规模可控 → 拒绝，代价 = 门禁边界留半成品。
  - 用 `ignore_errors` 纳入：与 P-036 刚拆除的同型假绿（U-P024-4）冲突 → 禁止。

### D2 target 最终形态与单批边界

**最终 target（12 面）**：

```
core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
```

- **单批实施**（不分 B1/B2）：20 条 / 10 文件，规模 ≈ P-036 的 B1（14 条），无相互依赖，拆批只增加提交与 CI 次数。
- `tests.yml` L46 与 `spec_runner_adapter.py` L67 **同提交**同步（P-036 F-S9-P036-1 教训：`test_p024_ci_gate_alignment` 会强制比对两载体）。
- **被拒绝的替代方案**：「按目录拆 B1=`tools` / B2=`examples`」——代价 = 2 次提交 + 2 次 CI + 2 次文档回填，收益仅为回退粒度；本批 20 条同源风险（均为示例/工具脚本），拆批收益不抵成本 → 拒绝。

### D3 修复策略分层（沿 P-036 D3，L4 上限 = 0）

| 层 | 本批使用 | 数量 |
|----|---------|------|
| **L1 根因收窄（缺陷修复）** | #6 `PositionTracker` 构造（call-arg + arg-type **同根 2 条**，见 D4-C1） | **2 条 / 1 簇** |
| **L2 访问点窄化** | #7-#11 的 `assert`（全部 U-a：`setup()` 或手动赋值前提） | **9 条 / 5 组** |
| **L3 注解/签名修正** | #1（返回注解 + 2 处入参连带，共 3 条错误同根）/ #2 / #3（3 条）/ #4（局部改名）/ #12 / #13（**仅 3.10**） | **7 条（3.12）+ 1 条（3.10）** |
| **值层改写（D4-C2）** | #5 `UniverseFilterConfig.from_universe_config`（非注解级，见 D4） | **1 条** |
| **L4 忽略** | **不使用**（新增 = 0） | **0** |

> **计数自洽（Step 4 F-S4-P037-3 订正）**：3.12 口径 = 2（L1）+ 9（L2）+ 7（L3）+ 1（C2）= **19**；3.10 口径 = 19 + 1（#13）= **20**。原表「1 + 9 + 9 + 0」把 #6 按「簇」、L2/L3 按「条」混计，已订正为统一按**错误条数**。

**硬约束**：
1. `assert` 只能指向**已成立的运行期事实**（`setup()` 已调用 / 手动赋值 / 构造期 raise）；不得掩盖真实 None 分支。
2. 注解修正目标为**运行期真值类型**；禁止 `cast(Any, ...)`。**被拒绝的替代方案**：对 9 条 union-attr 统一 `cast(IDataManager, engine.dm)`——代价 = 掩盖真实 None 分支（P-036 R-P036-2 同型风险）→ 拒绝，改用 `assert`。
3. `trace()` 放宽必须**连带** `complete_step` / `record_error` 入参（F-S2-P037-1 实证：否则新增 2 条 arg-type）。

### D4 行为变更裁决

| # | 位置 | 现网 | 修复后 | 性质 | 裁决依据 |
|---|------|------|--------|------|---------|
| **C1** | `examples/full_backtest_2020_2026_simple.py:124` | `PositionTracker(initial_capital)` → **运行期 TypeError（自 `c7a0f29` 起即不可运行）** | `PositionTracker(dm.n_stocks, initial_capital)` | 缺陷修复 | 现网崩溃 → 修复而非保留（P-036 D4 原则的镜像：崩溃不掩盖，但**可修的真缺陷要修**） |
| **C2** | 同上:116 | `UniverseFilter(dm, config.universe)` 传错配置类型（duck-typing 下仍可运行，但前缀/NA 等字段语义按 `UniverseConfig` 取值） | `UniverseFilterConfig.from_universe_config(config.universe)` | 值层改写（**逐字段值等价**，非「与默认构造等价」） | `from_universe_config` 的 21 字段全部取自源对象（`universe_filter_clean.py:68-90`），故转换后字段值 = 原 duck-typed 传参的取值；**目标默认构造不同**（`excluded_prefixes=["300","688"]` / `exclude_na_factors=False` / `na_factor_names=["factor_value"]`，L44-49）——因此不能表述为「与默认构造等价」（Step 4 F-S4-P037-1 订正） |

**D4 的替代方案（被拒绝）**：保留 C1 崩溃不修（仅压 mypy）→ 代价 = 示例长期不可用且掩盖真缺陷，与「类型门禁的目的」相悖 → 拒绝；C2 改为 `cast(UniverseFilterConfig, config.universe)` → 代价 = 运行期拿到错误类型（`exclude_stock_prefixes` 为 list 而非 bool），静态绿但语义错 → 拒绝。

- 除 C1/C2 外 **18 条零行为变更**；公开签名零变更（`PositionTracker.__init__` 等生产签名不动）。
- **C2 的导入位置为硬约束**：`from filter.universe_filter_clean import UniverseFilterConfig`（`filter/__init__.py` 不导出该符号——F-S2-P037-2）。

### D5 不扩做（显式边界）

| 项 | 裁决 | 理由 |
|----|------|------|
| 为 `demo/` / `memory/` 造门禁对象 | 不做 | 零 `.py` 文件 |
| 给 `tools` / `examples` 补 `__init__.py` | 不做 | `--explicit-package-bases` 已可直检；补包结构改变 import 语义 |
| 改 `[tool.mypy]`（`strict` / `warn_unused_ignores` / `disallow_untyped_defs`） | 不做 | 同 P-036 D7；会引入未知数量新错误 |
| 重写陈旧示例（迁到 `setup()` 模式） | 不做 | 超题干；只做类型面 + C1 |
| 引入 `TypedDict` 重构 `benchmark.py` | 不做 | `list[dict[str, Any]]` 已是最小改动 |
| 新增 pytest | 不做（X=0） | 示例不纳入测试；C1 以 Step 9 探针留证 |
| 扩 `tests/` 到 mypy target | 不做 | 显式未覆盖项（P-036 同口径） |

---

## 3. 不变式 I1-I6

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | golden 13 条**零重录** | `pytest -q -k golden` + `git status --short tests/golden/` |
| I2 | 公开签名**参数名 / 默认值 / 函数名零变更**；`def` 行差异**仅注解**——本批 `^-\s*def ` = **2**（`complete_step` / `record_error` 的参数注解放宽，注解就在 def 行；`trace()` 的返回注解在续行 L164，不触 def 行）（Step 4 F-S4-P037-2 订正：原写「= 0」与 D3 硬约束 3 冲突） | `git diff` 逐行比对 |
| I3 | `except Exception`（P-029 口径）恒 **22**；零新增 `except` | AST 脚本 + `^\+.*except` = 0 |
| I4 | pytest **760 不变**（X=0）；`tests/` .py 84 不变 | 全量 `pytest -q` |
| I5 | 单批**原子提交**：代码 10 文件 + `tests.yml` + adapter 同提交；CI 四 job 全绿 | `git show --stat` + `gh run view` |
| I6 | `mypy tools examples` **三口径均 0**；既有 10 面**仍 0**；新增 `# type: ignore` = 0 | 三环境复跑 + `Grep` |

---

## 4. 验证契约 V1-V5

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| **V1** | 目标面全绿 | `mypy ... tools examples`（三口径） | 0 error（`Success ... 103 source files` 相邻数值以实测为准） |
| **V2** | 既有面回归 | 10 面（含 `tools examples`）全量 `mypy` | 0 error |
| **V3** | 门禁双载体 | `tests.yml` L46 与 adapter L67 | 12 面字符串**逐字一致**；`grep '\|\| true'` = 0 |
| **V4** | C1 缺陷修复 | `%TEMP%` 探针：修复后 `PositionTracker(dm.n_stocks, 1e7)` 可构造 | 构造成功 + `get_cash()==1e7` |
| **V4b** | C2 逐字段等价 | `%TEMP%` 探针：`UniverseFilterConfig.from_universe_config(cfg)` 的 21 字段与 `cfg` 对应字段逐一比对（`exclude_stock_prefixes` 按 `bool()`、`excluded_prefixes` / `na_factor_names` 按 `list()`） | 21/21 一致；且**不等于**默认构造（至少 `excluded_prefixes` 差异可证） |
| **V5** | 行为守恒 | golden / pytest / AST / 签名 | I1-I4 全部成立 |

### 红态口径（Step 9 必须出示修复前读数）

| 口径 | 红态 |
|------|------|
| 本机 3.12 + numpy 2.4.6 | **19 errors / 10 files（checked 11）** |
| r2 3.12 + numpy 2.5.5 | **19 errors / 10 files（checked 11）** |
| r310 3.10 + numpy 2.2.6 | **20 errors / 10 files（checked 11；追加 `demo.py:79`）** |

---

## 5. 风险与未决

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| R-P037-1 | 风险 | 两目录无 `__init__.py`，三 leg 模块解析可能不同 | Step 9 三口径复跑；CI 三 leg 为最终判据 |
| R-P037-2 | 风险 | 示例端到端运行依赖真实数据，类型通过 ≠ 可运行 | 本批只承诺类型面 + C1 可构造性（O-P037-1） |
| R-P037-3 | 风险 | `trace()` 连带放宽遗漏 → 新增 2 条 arg-type | D3 已写入硬约束；V2 以「0 error」兜底 |
| R-P037-4 | 风险 | `list[dict[str, Any]]` 削弱 `benchmark.py` 类型约束 | 接受（非生产面）；必要时单独立项 TypedDict |
| R-P037-5 | 风险 | `filter` 包根不导出 `UniverseFilterConfig` | D4 硬约束锁定导入路径；Step 9 探针复核 |
| U-P037-1 | 未决 | U-P036-4 题干含零 Python 文件的 `demo`/`memory` | 关批时改台账措辞 |
| U-P037-2 | 未决 | `examples` 是否存在其他陈旧 API 用法（运行期） | pending（触发：用户实际运行示例报错） |
| U-P037-3 | 未决 | RULE-5 异构性未证实（Step 2 复审基座 UNKNOWN） | Step 10 前由异构基座会话补做终审 |
| O-P037-1 | 观察 | 示例端到端运行无 CI 覆盖 | 登记 |
| O-P037-2 | 观察 | `tests/test_distillation_isolation.py` 间接获得静态保护 | 登记（正面） |

---

## 6. 实施顺序与回退点

```text
修 20 条（10 文件）→ 本地三口径 `mypy tools examples` = 0
  → 本地 12 面 = 0（既有 10 面不回归）
  → tests.yml L46 + adapter L67 同提交追加 `tools examples`
  → pytest 760 / golden 13 / black / AST 22 / uv lock 复验
  → 单提交 → CI 四 job 绿
```

- **回退点**：单提交 revert 即回到 10 面门禁 + 修复前代码。
- **顺序敏感**：C2 的导入路径、`trace()` 的连带入参、`engine.dm` 的 `assert` 前提（5 组逐组核）——三项须在 Step 9 逐项留证。

---

## 7. 下一 Step

**Step 4 设计 Review（须异构基座，先自报）**：核 ① D1 范围与题干收窄是否合规；② D3 分层是否可机械执行、L4=0 是否成立；③ D4 的 C1/C2 定性是否有据；④ D5 是否越界；⑤ V1-V5 可重放、I1-I6 覆盖 P-036 既有约束。

---

## 8. Step 4 设计 Review 记录（2026-11-17）

> **基座披露（RULE-5 诚实声明）**：复审执行会话第 0 步逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.`——**与作者同源 → RULE-5 异构不成立**。本轮为**同基座独立上下文复审**（RULE-4 披露）；U-P037-3 扩记为「Step 2 复审自报 UNKNOWN + Step 4 复审自报 DeepSeek 同源 → 连续两轮异构未证实」。
> **复审时点**：HEAD `ad7815d`（DESIGN 未提交态）；复审方式 = 独立会话 + 三口径实跑 + 源码逐行读码。

### 8.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | `demo`/`memory` 零 `.py` | Count=0（memory 仅 json） | ✅ |
| A | 12 面串 = 现 10 面 + ` tools examples` | 逐字一致，顺序不变 | ✅ |
| A | 分层计数 | **不自洽**（1+9+9 ≠ 19 按条计） | ❌ F-S4-P037-3 |
| A | C1 签名 / `n_stocks` property / 惯例 | `tracker.py:165` / `data.py:120` / `engine_v2.py:270` | ✅ |
| A | C2 等价性论证 | 3 字段与目标默认不同（L44-49） | ❌ F-S4-P037-1 |
| B | 5 组 assert 前提行 | single L60 / fixed L74 / minimal L70 / 2020_2026 L78 / simple L106 | ✅ 全 U-a |
| B | `complete_step` / `record_error` 调用点 | 全仓仅 2 处（L269 / L272，同文件） | ✅ 放宽无外部破坏 |
| B | I2「`^-\s*def ` = 0」 | **不可达**（两处注解放宽在 def 行上） | ❌ F-S4-P037-2 |
| B | 103 source files | 12 面实跑 `checked 103 source files` | ✅ |
| C | C1 归因（自 `c7a0f29` 即不可运行） | 与 RESEARCH §5.1 一致 | ✅ |
| C | 缺锚点表 / 每决策被拒方案 ≥2 | 仅 D1 满足 | ⚠️ F-S4-P037-3/5 |
| D | T1 判档 / 题干收窄不冲突 | 成立 | ✅ |

### 8.2 发现与当轮处置（5 项：2 P2 + 3 P3）

| ID | 级别 | 发现 | 当轮处置 |
|----|------|------|---------|
| **F-S4-P037-1** | **P2** | D4-C2 论证失实：「`exclude_stock_prefixes=[]` 为假值 → 与默认构造等价」不成立——目标默认 `excluded_prefixes=["300","688"]` / `exclude_na_factors=False` / `na_factor_names=["factor_value"]`（`universe_filter_clean.py:44-49`）与源 `UniverseConfig` 默认值不同 | D4-C2 改述为「**逐字段值等价**（21 字段取自源对象）」；新增 **V4b** 探针出口 |
| **F-S4-P037-2** | **P2** | I2「`^-\s*def ` = 0」与 D3 硬约束 3 冲突——`complete_step` L189 / `record_error` L198 的 `step: ExecutionStep` 就在 def 行，放宽必删 2 行 | I2 改写为「`= **2**`（仅参数注解放宽；参数名/默认值/函数名零变更）」 |
| F-S4-P037-3 | P3 | D3 分层计数单位混用：L1 实为 **2 条**（call-arg + arg-type 同根）、L2 9 条、L3 7 条（3.12）→ 2+9+7+1(C2)=19；3.10 +1=20 | D3 表按**错误条数**重列 + 计数自洽注 |
| F-S4-P037-4 | P3 | D3-L3 把 #5（实参改写）与纯注解并列，与 D4-C2「值层改写」矛盾 | D3 单列「值层改写（D4-C2）」行；L3 数量改为 7+1 |
| F-S4-P037-5 | P3 | 缺「被拒方案 ≥2 / 锚点」形态（`SPEC_STANDARD` §11.8 要求；外部权威源 `SPEC_PROCESS` v1.7.2 Step 3 要求「被拒方案 + 理由 + 代价」） | D2 / D3 硬约束 2 / D4 各补被拒方案与代价；**锚点声明**：本批为仓内工程约束型决策（判据来自 `tests.yml` / adapter / mypy 输出），**无外部 T1/T2 锚点——标 `[无外部锚点-自证]`** |

### 8.3 结论

**复审结论**：**pass（带 2 P2 + 3 P3 全部当轮回写）**——D1/D5/I 其余项/V/判档复核通过；两项 P2 属「论证失实」与「不变式不可达」，已在本文档修正，**准予进入 Step 5 IMPL**。
**RULE-5**：连续两轮同基座/未证实 → U-P037-3 维持 pending，Step 10 前须由用户指定的异构基座会话补做终审。
