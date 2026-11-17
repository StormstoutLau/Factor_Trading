# P-037 类型门禁边界收口 · 批次总结报告（十步终态）

> **批次**: P-037 · 类型门禁边界收口（U-P036-4 承接批）· **T1**（判档规则 2：追加 target = 变更 CI 门禁判据）
> **状态**: **Step 1-10 全通过 + U-P037-3 异构终审 pass（GLM-5.3-Flash），批次关闭**（2026-11-17）
> **审计基线**: 实施前 HEAD `ad7815d` → 代码终态 `22644e3`（单提交）→ 文档终态 `b9ed589`；复审谱系：Step 2 基座 `UNKNOWN`（异构未证实）、Step 4/6/8/10 = DeepSeek 同基座（独立上下文），**仅 U-P037-3 终审异构成立（GLM-5.3-Flash，第 3 次承接，先例 U-P036-6 / U-P034-3）**
> **配套文档**: [RESEARCH](RESEARCH_p037_type_gate_boundary.md)（§11 Step 2） / [DESIGN](DESIGN_p037_type_gate_boundary.md)（§8 Step 4） / [IMPL](IMPL_p037_type_gate_boundary.md)（§9 Step 6 / §11 Step 9） / [CHECKLIST](CHECKLIST_p037_type_gate_boundary.md)（§9 Step 9 / §10 Step 10 / §12 异构终审）

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | U-P036-4 显式登记的边界遗留——`tools/` `examples/` `demo/` `memory/` 四目录未纳入类型门禁；**题干收窄**：`demo/` 与 `memory/` 零 `.py` 文件（mypy exit 2）→ 实际范围 = `tools`（4 文件 / 5 errors）+ `examples`（7 文件 / 14 errors） |
| **核心手段** | **题干收窄**（U-P037-1）→ **20 条单批真修**（13 行 / 10 簇；修复四层：L1 根因收窄 ×2 / L2 U-a assert ×9 / L3 注解修正 ×7+1（3.10）/ 值层改写 ×1 / **L4 忽略 = 0**）→ **门禁 10 面 → 12 面**（`tests.yml` L46 + `spec_runner_adapter.py` L67 双载体同提交） |
| **行为变更** | 仅 **C1-C2** 两项：C1 `PositionTracker(config.initial_capital)` → `PositionTracker(dm.n_stocks, initial_capital)`（**缺陷修复——该示例自 `c7a0f29` 起构造即 TypeError，自诞生不可运行**）；C2 duck-typing `UniverseFilter(dm, config.universe)` → `UniverseFilterConfig.from_universe_config(...)`（值层改写，逐字段值等价、非与默认构造等价）；其余 18 条零行为变更 |
| **代码规模** | 代码单提交 `22644e3`：12 文件 **+34/−24**（10 代码 + 2 门禁载体）；新增 `# type: ignore` = **0**；不新增 `[[tool.mypy.overrides]]` |
| **测试** | **760 passed 不变**（X=0）；测试文件 84 不变；golden **13 零重录**（`tests/golden/` diff 空） |
| **门禁** | mypy **10 面 → 12 面**，三口径均 0（py3.12+numpy 2.4.6 / py3.12+2.5.5 / py3.10+2.2.6，**103 files**）；black **121**（全仓 188）；AST `except Exception` 恒 **22**；`uv lock --check` exit 0；`^-\s*def ` = **2**（仅两处参数注解）；零改动面（`core`/`tests`/`pyproject.toml`/`uv.lock`）diff 空 |
| **质量结论** | 全程 **0 P0/P1**；P2 ×9 + P3 ×22 = **31 项全部当轮处置或登记**；38/38 验收项全 ✅；**异构复审仅在终审成立**——Step 2/10 自报 UNKNOWN、Step 4/6/8 同源，如实登记 U-P037-3 而非默认异构，终审由 GLM-5.3-Flash 承接（E1-E5 五项全过 + 1 P3 口径精化） |

一句话：**「门禁收口的最后一公里」——19+1 条里 18 条是注解卫生与 U-a 窄化，但藏着 1 个自诞生即 TypeError 的 Quick Start 示例（C1）和 1 处 duck-typing 语义漂移（C2）；把 README 入口的 examples 放进类型门禁，类型检查才真正覆盖用户会踩到的第一行代码。**

---

## 2. 背景与谱系

### 2.1 上游与触发

- P-036 把门禁从 `core` 单面扩至 **10 面**（拆 filter 假绿 + 钉 mypy 2.4.1 + 131 条真修），显式登记 U-P036-4「`tools/` / `examples/` / `demo/` / `memory/` 是否纳入」为边界遗留，触发条件「任一目录出现生产调用」。
- Step 1 取证：生产面对 `tools`/`examples` 的 import **0 命中**（仅 `tests/test_distillation_isolation.py` 3 处测试引用）→ **触发条件未成立**，本批属**用户裁决的主动扩做**（M-C「维持 pending」被拒：门禁边界留半成品，后续每次扩面评估都要重新取证）。
- 假绿禁区：M-D「用 `ignore_errors` 纳入」**直接禁止**——P-036 刚拆掉同型假绿（U-P024-4），重蹈覆辙不可接受。

### 2.2 治理谱系

P-007/P-024（core 清零）→ P-026/P-027/P-029（静默失败治理）→ P-034（lock-check + 760 基线）→ P-035（台账纪律）→ P-036（扩 10 面 + 去假绿）→ **P-037（本批：12 面，边界收口完成——全仓非测试 Python 目录全部纳入门禁）**。

### 2.3 题干收窄（U-P037-1）

U-P036-4 题干列四目录；Step 1 实测 `demo/` 与 `memory/` **零 `.py` 文件**（mypy exit 2 `There are no .py[i] files`）→ 非 Python 目录，纳入无对象。实际范围 = `tools` + `examples`；U-P036-4 关闭时台账措辞同步收窄。

---

## 3. 设计口径（DESIGN D1-D5）

| ID | 裁决 | 落地 |
|----|------|------|
| D1 | 范围 = `tools` + `examples`，剔除 `demo`/`memory` | 被拒：仅纳入 `tools`（examples 是 README Quick Start 入口，保护价值更高）/ `ignore_errors` 纳入（假绿禁区） |
| D2 | target 最终 12 面，**单批实施**（不分 B1/B2） | 被拒：按目录拆两批——2 次提交 + 2 次 CI 的成本不抵回退粒度收益；双载体同提交（P-036 F-S9-P036-1 教训） |
| D3 | 修复四层（L4 上限 = 0）+ 三硬约束（assert 仅 U-a / 禁 `cast(Any, ...)` / `trace()` 三处连带） | 计数自洽 2+9+7+1=19（3.12）、+1=20（3.10）；Step 4 订正原「1+9+9」混计 |
| D4 | C1 缺陷修复（崩溃不掩盖但**可修的要修**）/ C2 值层改写（**逐字段值等价**，非「与默认构造等价」——Step 4/8 两次订正） | 被拒：C1 仅压 mypy 不修（示例长期不可用）/ C2 用 `cast`（静态绿语义错——`exclude_stock_prefixes` list ≠ bool） |
| D5 | 七项不扩做（demo/memory 门禁对象 / `__init__.py` / `[tool.mypy]` 加严 / 重写陈旧示例 / TypedDict / 新增 pytest（X=0）/ `tests/` 入 target） | 全部守住，Step 10 审计 Phase 1 确认零扩做 |

**锚点声明**：本批为仓内工程约束型决策（判据来自 `tests.yml` / adapter / mypy 输出），**无外部 T1/T2 锚点——`[无外部锚点-自证]`**（Step 4 F-S4-P037-5 补录）。

**不变式 I1-I6 全部成立**（golden 13 零重录 / `^-\s*def ` = 2 / AST 22 / pytest 760 / 原子提交 / 三口径 0）；验证契约 V1-V5（含 V4b 逐字段等价探针）可重放且全部复跑。

---

## 4. 实施（单批 20 条 / 13 行 / 10 文件）

- **tools 5 条**：`ui_dashboard.py` `trace() -> ExecutionStep | None`（续行 L164）+ `complete_step` / `record_error` 入参**三处连带**（Step 2 F-S2-P037-1 实证：只放宽返回注解不归零，新增 2 条 arg-type）；`distillation_audit.py` `results: list[dict]`；`benchmark.py` `list[dict[str, Any]]`。
- **examples 15 条**：5 组 `engine.dm` U-a assert（前提 `setup()` L60/L74/L70/L78 与手动赋值 `simple.py` L106，Step 10 盲区逐组核实）+ `signal` assert + C1/C2 + `event_days: np.ndarray | list[int]`（`demo.py` 无 typing import，不引 Any）。
- **#13（仅 3.10）的改法唯一可行解 = L68 声明**：`adj: np.ndarray = np.ones((n_days, n_stocks))`——Step 6 F-S6-P037-1（P2）实测两种直觉改法均不可归零：`np.asarray(adj / adj[-1:])` 在 r310 仍报形状赋值；行内注解触发 `no-redef`（P-036 `_spec.py:68` 同型先例）。
- **C1 用 `dm.n_stocks`**（`core/data.py:120` property）而非 `len(dm.close.columns)`——不强制加载价格数据（Step 2 F-S2-P037-7）。
- **C2 导入硬约束**：`from filter.universe_filter_clean import UniverseFilterConfig`——`filter/__init__.py` 不导出该符号，从包根导入会运行期 ImportError（Step 2 F-S2-P037-2，P2）。
- **实施期 2 发现**：#4 改名 `position` 与同函数 L566 `for stock, position in ...` 冲突 → 改 `held`（F-S9-P037-1）；PowerShell `Select-String` **默认大小写不敏感**使 `Exception` 被 `^\+.*except` 误计 → `-CaseSensitive` 重算 = 0（F-S9-P037-2，口径固化进 CHECKLIST C3）。

---

## 5. 门禁与 CI 终态

| 门禁 | 读数 |
|------|------|
| mypy 12 面（三口径） | 均 `Success: no issues found in 103 source files`（红态 19 / 19 / 20 → 0） |
| `mypy tools examples` | 三口径 `Success ... 11 source files` |
| pytest / golden | **760 passed** / **13 passed, 747 deselected**（`tests/golden/` 零改动） |
| black / AST / uv | **121** / **22**（IMPL_p029 L410 原命令）/ exit **0** |
| 机械面 | `raise+`/`except+`/`type-ignore+` = 0；`^-\s*def ` = 2；零改动面 diff 空；numstat 12 文件与 IMPL §11.1 逐项吻合 |
| CI | 6 runs 全 success（§7）；四 job = `lock-check` + 3.10 / 3.11 / 3.12 |

---

## 6. 发现台账（全程 0 P0/P1；P2 ×9 + P3 ×22 = 31，全部当轮处置或登记）

| 轮次 | P2 | P3 | 代表项 |
|------|----|----|--------|
| Step 1 调研 | 1 | 0 | **F-S1-P037-1 E2 探针实锤 C1 真实缺陷**（PositionTracker 自 `c7a0f29` 即 TypeError） |
| Step 2 复审（UNKNOWN） | 2 | 5 | F-S2-P037-1 `trace()` 三处连带才归零 / -2 `filter` 包根不导出 `UniverseFilterConfig`（运行期 ImportError） |
| Step 4 复审（同源） | 2 | 3 | F-S4-P037-1 C2「与默认构造等价」论证失实 → 逐字段值等价 + V4b / -2 I2「= 0」不可达 → = 2 |
| Step 6 复审（同源） | 1 | 3 | **F-S6-P037-1 #13 两种直觉改法均不可归零 → L68 声明唯一可行** |
| Step 8 复审（同源） | 3 | 4 | F-S8P037-1 RESEARCH §5.2 残留 / -2 #13 仍列被否改法 / -3 PROGRESS 行状态滞后 |
| Step 9 实施 | 0 | 2 | F-S9-P037-1 `held` 改名 / -2 Select-String 大小写陷阱 |
| Step 10 审计（独立会话，UNKNOWN） | 0 | 4 | F-S10-P037-1~4（D1 尾串缩写 / §8.1 assert 构成 / V2 面数自相矛盾 / **台账建行缺口第 6 次**） |
| U-P037-3 终审（GLM，异构成立） | 0 | 1 | **F-U3-P037-1「21 字段」口径精化**——目标类实有 23 字段（21 显式映射 + 2 target-only 同值），等价结论不变 |

观察 O-P037-1/-2 登记（示例端到端无 CI 覆盖 / `test_distillation_isolation` 获静态保护）。U-P036-6 先例为「全程异构 + 同基座终审」，本批镜像为「全程同基座/UNKNOWN + 仅终审异构」——两种谱系均闭合，RULE-5 增益第五次实证。

---

## 7. 提交链与 CI（`ad7815d..b9ed589`，6 提交 + 本报告提交另计）

| 提交 | 内容 | CI run |
|------|------|--------|
| `22644e3` | **代码主提交**（12 文件 +34/−24：10 代码 + tests.yml + adapter） | [`44046313784`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44046313784) ✅ |
| `8a2984d` | Step 1-9 四文档 + CHECKLIST 38/38 + 台账收口 | `44046940864` ✅ |
| `8dffb12` | Step 10 同基座审计（0 P1/P2 + 4 P3） | `44048342761` ✅ |
| `44c3470` | Step 10 CI 读数回填 | `44048757900` ✅ |
| `bdab281` | **U-P037-3 异构终审 pass（GLM-5.3-Flash）——批次关闭** | [`44051202252`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44051202252) ✅ |
| `b9ed589` | 终审 CI 读数回填 | `44051666634` ✅ |

全程 **6/6 四 job 全绿、零红跑**（对比 P-036 的 3 次 CI 红为 CI 实装 numpy 桩差异——本批依赖面已被 P-036 三口径围堵，单批一次过）。

---

## 8. 台账收口（PROGRESS §1.4）

| 项 | 终态 |
|----|------|
| U-P036-4（四目录纳入门禁） | **done**（题干收窄 + 12 面双载体，run 44046313784） |
| U-P037-1（`demo`/`memory` 性质） | **done**（零 `.py`，题干正式收窄） |
| U-P037-3（RULE-5 异构终审） | **done**（GLM-5.3-Flash，E1-E5 五项全过，CHECKLIST §12） |
| U-P037-2（examples 运行期陈旧面） | pending（条件触发：用户实际运行示例报错；本批只修 C1 可构造性） |
| R-P037-1~5（五风险） | 全部落地关闭（三口径复跑 / 类型面承诺 / 三处连带硬约束 / Any 可接受 / 导入路径锁定） |
| O-P037-1/-2 | 登记 |

---

## 9. 边界遗留

1. **U-P037-2**：类型通过 ≠ 可运行——`full_backtest_2020_2026_simple.py` 等示例的**运行期语义**（依赖 `data/` / `gurus/` 真实数据）无端到端验证（O-P037-1）；条件触发待用户实际运行反馈。
2. **`benchmark.py` 类型约束削弱**：`list[dict[str, Any]]` 引入 Any 传播（R-P037-4，接受——非生产面）；如需根治单独立项 TypedDict。
3. **`tests/` 未纳入 mypy target**：显式未覆盖项（P-036/P-037 两批同口径；D5 守住不扩做）。
4. **CI numpy 未钉版本**（P-036 遗留延续）：本批以三口径围堵（r2 2.5.5 / r310 2.2.6 复刻 venv），根治属依赖治理，未在本批题干。
5. **方法论注记**：PowerShell `Select-String` 默认大小写不敏感——机械计数口径（`except+` 等）须显式 `-CaseSensitive`，已固化进 CHECKLIST C3。

---

## 10. 启示（六条）

1. **门禁的「最后边界」同样值得收口**：`tools`/`examples` 虽非生产面，但 examples 是 README Quick Start 入口——门禁价值 = 保护面 × 触达率，20 条里就藏着 1 个「自诞生即 TypeError」的示例（C1）：**没有类型门禁的角落，恰是用户最先踩到的代码**。
2. **duck-typing「能跑」≠「语义正确」**：C2 传错配置类型在运行期静默工作（字段语义按源对象取值），显式 `from_universe_config` + 逐字段值等价探针（V4b）才是收口姿势——「值层改写」是注解级修复之外的第二类零风险变更，须单独裁决与探针留证。
3. **修法的可归零性必须三口径实测，不能靠推断**：#13 的两种直觉改法在 r310 都不归零（`np.asarray` 不改形状推断 / 行内注解触发 `no-redef`）——规格层的「想当然」只有实跑能证伪（Step 6 P2 抓住）；三口径复跑是漂移探测器而非形式。
4. **连带面要静态分析 + 探针双验**：`trace()` 只放宽返回注解会**新增** 2 条 arg-type（`complete_step`/`record_error` 入参）——放宽签名必须从调用图出发列全连带，Step 2 独立探针是捕获手段。
5. **同基座复审收益递减但非零，异构终审兜底**：Step 4/6/8 同源仍各抓 1-3 P2（论证失实 / 不变式不可达 / 改法不可行）——独立上下文本身有价值；终审异构再精化 1 P3 口径（「21 字段」隐含 bool 强转 + target-only 字段）。**独立探针的朴素假设失败是口径显性化的机会**——U-P037-3 探针首版两次失败暴露的都是文档已明示但易误读的设计。
6. **机械计数口径要绑定工具行为**：`Select-String` 大小写陷阱让 `except+` = 0 的结论差点被 1 条假命中污染（F-S9-P037-2）——计数命令与预期口径（含 `-CaseSensitive`）应作为可重放命令对写进文档，而非临时补救。
