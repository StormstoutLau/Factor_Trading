# P-036 mypy 检查面扩展 · 批次总结报告（十步终态）

> **批次**: P-036 · mypy 检查面扩展（U-P024-3 取证批，含 B0 版本定版与 U-P024-4 filter 假绿拆除）· **T1**（判档规则 2：扩面 = 变更 CI 门禁判据）
> **状态**: **Step 1-10 全通过 + U-P036-6 异构终审 pass，批次关闭**（2026-11-17）
> **审计基线**: 实施前 HEAD `65da5f9` → 代码终态 `f1fdab4`（5 提交）→ 文档终态 `519ca61`；复审谱系：Step 2/4/6/8 = **GLM-5.3-Flash（异构）**，Step 10 = DeepSeek 同基座（§11）+ **U-P036-6 异构终审 = GLM-5.3-Flash（异构成立）**
> **配套文档**: [RESEARCH](RESEARCH_p036_mypy_check_surface_expansion.md) / [DESIGN](DESIGN_p036_mypy_check_surface_expansion.md) / [IMPL](IMPL_p036_mypy_check_surface_expansion.md) / [CHECKLIST](CHECKLIST_p036_mypy_check_surface_expansion.md)（§10 Step 9 / §11 Step 10 / §12 异构终审）

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | ① U-P024-3——类型门禁 target 仅 `core`（37 files），`agents`/`filter`/`scripts`/`batch_backtest`/`strategy_evaluation`/`cli.py` 零覆盖；② U-P024-4——`filter` 21 条真实类型错误被 `[[tool.mypy.overrides]] filter.* ignore_errors` **假绿**（P-024 遗留）；③ U-P024-1——`mypy>=1.5.0` 无上限，门禁读数随 CI 解析漂移 |
| **核心手段** | **B0 钉版**（`mypy~=2.4.1`，锁 2.1.0→2.4.1）→ **三批 red→green**（B1 14 / B2 96 / B3 21 = **131 条**，修复四层策略 L1 根因收窄 > L2 assert 窄化 > L3 注解修正 > L4 忽略=0）→ **门禁 `core` 单面 → 10 面**（CI `tests.yml` L46 + 本地 `spec_runner_adapter.py` L67 双载体同提交）→ **删 filter override**（三条件顺序） |
| **行为变更** | 仅 **C1-C4** 四项：C1 `run_factors` fail-fast（`ValueError("未提供因子数据库")`）/ C2 `tracker.cash`→`_cash`（**静默影子属性**——动态调资一直无效，探针实证）/ C3 删 `period=`（现网 TypeError）/ C4 `int(trade_qty)`；其余 127 条注解级零行为变更 |
| **代码规模** | 代码 5 提交：+27/−18、+82/−61、+36/−34、+3/−3、+6/−6；全区间 15 提交（含 Step 5-8 文档 8 提交）；新增 `# type: ignore` = **0**（既有带 code 4 处保留） |
| **测试** | **760 passed 不变**（X=0，不新增测试）；测试文件 84 / `test_*.py` 81 不变；golden **13 零重录** |
| **门禁** | mypy **1 面 → 10 面**，三口径均 0（py3.12+numpy 2.4.6 / py3.12+2.5.5 / py3.10+2.2.6，92 files）；black **121**；AST `except Exception` 恒 **22**；`uv lock --check` exit 0；签名差异恰 **7 def 行 + 1 参数注解行** |
| **质量结论** | 全程 **0 P0/P1**；各轮 P2 ×9 + P3 ×20 全部当轮处置或登记（观察 ≥8 项）；**异构复审贯穿全程**（Step 2/4/6/8 + 终审四轮 GLM）；65/65 验收项全 ✅ |

一句话：**「门禁的真实性 = 覆盖面 × 无假绿 × 版本确定」——扩 10 面只是第一步，拆掉 override 假绿、钉住 mypy 版本、并让 CI 与本地双载体逐字一致，门禁才从装饰变成约束；131 条里还藏着 2 个真缺陷（静默调资失效 + 现网 TypeError），类型检查抓的是测试抓不到的病。**

---

## 2. 背景与谱系

### 2.1 两次误诊史（为何取证先行）

| 轮次 | 假说 | 证伪方式 |
|------|------|---------|
| P-024 | filter 渗入 21 条 = pandas 3.1.1 类型桩 | Step 1：pandas 2.2.3 与 3.1.1 均无 `py.typed`（`.pyi` 同 41 个） |
| P-024 一度钉 `~=2.1.0` | 2.1.0 vs 2.4.1 读数差 = 版本行为 | X1-X4 隔离实验证伪 → 撤回 |
| Step 3 记「CI 口径 129」 | 双口径差异 = pandas | **F-S4-P036-4（P2）**：p036r2 钉 numpy 重放——差异变量是 **numpy 桩版本**（2.4.6=131 / 2.5.5=129）；真 CI 口径 = 本地 = **131，双口径收敛** |
| 主环境 core=0 之谜 | —— | **R1'**（Step 2 控变量）：干净缓存下 2.1.0/2.4.1 **均渗入** filter 21 条；主环境「0」为未归因站点现象（U-P036-5 维持 pending） |

### 2.2 治理谱系

P-007/P-024（core 清零 + 假门禁拆除 + override 引入）→ P-026/P-027/P-029（静默失败治理，`except` 计量 22）→ P-034（lock-check job + 760 基线）→ P-035（台账纪律扩展）→ **P-036（本批：扩面 + 真修 + 去假绿）**。

---

## 3. 设计口径（DESIGN D1-D7）

| ID | 裁决 | 落地 |
|----|------|------|
| D1 | 基线口径 = CI 对齐口径；复刻 venv 钉 `numpy==2.4.6` | Step 4 更正后双口径收敛；Step 9 再扩**三口径**（F-S9-P036-2） |
| D2 | 三批边界 14/96/21，最终 target 10 面 | 三批逐字落地；十面串四处逐字一致 |
| D3 | 修复四层：L1 根因 > L2 assert（仅 U-a）> L3 注解 > L4 忽略（上限 3） | 实际 L1 仅 C1 一处；L2 全部有运行期前提（审计逐组读码）；**L4 新增 = 0** |
| D4 | 现网崩溃 → 保持 fail-fast，**禁止默认值降级**（P-025 先例） | C1 fail-fast；C2/C3 判缺陷修复（非类型修复） |
| D5 | override 移除三条件同批原子（filter 0 → 删 → core 仍 0） | `eb3ae55` 顺序执行留证 |
| D6 | O-P036-5 不立项（不为未归因现象造调查批） | U-P036-5 维持 pending |
| D7 | 不引入 `warn_unused_ignores`/`strict`/`disallow_untyped_defs` | pyproject `[tool.mypy]` 五行未动 |

**不变式 I1-I7 全部成立**（golden 13 零重录 / 签名 7+1 / AST 22 / pytest 760 / 原子提交 / 多口径 0 / 新增 ignore 0）；验证契约 V1-V6 可重放且全部复跑通过。

---

## 4. 实施（三批 + 兼容修复）

### 4.1 B1（14 条 / 8 面，`e2dafff`）
`strategy_evaluation`（`row: dict[str, Any]`、`half_life/turnover: float`）+ `order_strategy`（`fill_timestamps: list | None`、`total_impact: float`）+ `verify_p015`（`-> np.ndarray | None` 三错同根）+ `_spec`（局部注解 + `np.asarray`）+ `engine.py`（**C1**）+ `cli.py`（`factor_weights={}` + dm 断言）。次生修改批内闭合（3 处 fill_timestamps assert / `return None` / `_run_single_factor` 独立守卫）。

### 4.2 B2（96 条 / 9 面，`e781b75`）
11 文件按簇：`guru_agent_v2` **25 条一处收窄**（保留既有 raise）+ `agent_framework` 17 + `style_reflection_engine` 8（1 根因）+ `strategy_allocator` 9（`np.asarray` ×8）+ `sentiment_framework` 5 + `auto_parameter_optimizer` 8 + `assumption_monitor` 9 + `multi_strategy_engine` 6（**C2**）+ `style_drift_analysis` 5 + `hierarchical_bayesian_agent` 2 + `research_team_v2` 1（**C3**）；**C4** 在 agent_framework。

### 4.3 B3（21 条 / 10 面 + 删 override，`eb3ae55`）
`universe_filter_clean` 13（`_prefix_info` 注解 + filter_stocks assert + 两方法三局部合并 assert）+ `prefix`/`na_factor`/`market_cap`/`industry` 返回注解 `-> BaseFilter` + 四工厂 dict 注解 + `custom.py` `filter_obj: BaseFilter` + 删 `Literal` 死 import；override 三条件顺序删除。

### 4.4 CI 桩兼容（`43ed468` + `f1fdab4`）
三主提交首推 CI 红：3.12 leg 实装 **numpy 2.5.5**（零参 `ndarray.cumsum()` 桩 `call-overload` 3 条）→ 改 `np.cumsum(...)`；3.10 leg 实装 **numpy 2.2.6 / pandas 2.3.3**（形状/标量 7 条）→ 6 处收窄（`np.full`/`np.zeros`/`max(0.0, 1.0 - float(std)*5)`/`float(...)` ×3）。复刻 venv `%TEMP%\p036r2`（3.12+2.5.5）与 `%TEMP%\p036r310`（uv 装 3.10.20+2.2.6+2.3.3+pydantic 2.14.3）逐条复现后修复——**「双口径」升级为三口径**。

---

## 5. 门禁与 CI 终态

| 门禁 | 读数 |
|------|------|
| mypy 10 面（三口径） | 均 `Success: no issues found in 92 source files` |
| `mypy core`（去 override 后） | `Success: no issues found in 37 source files` |
| pytest / golden | **760 passed** / **13 passed, 747 deselected**（`tests/golden/` 零改动） |
| black / AST / uv | **121** / **22** / exit **0** |
| CI 终态 run | `44029888652`（代码 `f1fdab4`）+ `44030760894`/`44031073193`（docs）+ `44036545497`/`44036869462`（Step 10/终审 docs）——**四 job 全绿** |

---

## 6. 发现台账（全程 0 P0/P1）

| 轮次 | P2 | P3 | 代表项 |
|------|----|----|--------|
| 设计期（Step 3） | 1 | 2 | F-D3-P036-1 读数对桩敏感（Step 4 改判 numpy） |
| Step 2 复审 | 1 | 3 | F-S2-P036-2 R1 归因证伪 → R1' |
| Step 4 复审 | 2 | 2 | F-S4-P036-4 双口径收敛（numpy）/ F-S4-P036-3 D4 改写（禁默认值降级） |
| Step 6 复审 | 2 | 4 | F-S6-P036-1 filter_stocks 分组 / F-S6-P036-2 工厂返回注解补录（I2 5→8 处） |
| Step 8 复审 | 0 | 1 | F-S8-P036-1「8 处 def 行」精化为 7+1 |
| Step 9 实施 | 3 | 4 | **F-S9-P036-1 门禁双载体遗漏 / -2 CI 桩版本 / -4 C2 静默影子属性** |
| Step 10 审计 | 0 | 3 | F-S10-P036-1/-2 口径落点注 / -3 分级统计笔误（3 P2 + 4 P3） |
| U-P036-6 终审 | 0 | 1 | F-U6-P036-1 §11.2 交叉引用覆盖面（当轮精化） |

观察 ≥8 项登记（含 O-U6-P036-1 方法归属澄清：`update_belief` 真实 owner 为 `HierarchicalBayesianEngine`，`_execute_trade` 属 `MultiAgentBacktestEngine`——文档锚点本就未误归属）。

---

## 7. 提交链与 CI（`65da5f9..HEAD`，17 提交）

| 提交 | 内容 | CI run |
|------|------|--------|
| `ec33dd7`/`b277313` | Step 5 IMPL + 回填 | 44021229549 ✅ |
| `61876a9`/`1261865` | Step 6 异构复审 + 回填 | 44023440112 ✅ |
| `97840dd`/`0d9876c` | Step 7 CHECKLIST + 回填 | 44024144262 ✅ |
| `6349a5c`/`7e91932` | Step 8 异构复审 + 回填 | 44025817190 ✅ |
| `e2dafff` | **B1 主提交**（8 面） | 44026780449 ❌（桩） |
| `e781b75` | **B2 主提交**（9 面 + C2/C3/C4） | 44027975513 ❌（桩） |
| `eb3ae55` | **B3 主提交**（10 面 + 删 override） | 44028421866 ❌（桩） |
| `43ed468` | numpy 2.5.5 兼容 | 44028763627 ❌（3.10 leg） |
| `f1fdab4` | py3.10/numpy 2.2.6 兼容 | **44029888652 ✅** |
| `191bbf8`/`83a8d5f` | Step 9 文档 | 44030760894 / 44031073193 ✅ |
| `32e574a`/`519ca61` | Step 10 文档 | 44036545497 / 44036869462 ✅ |
| 终审关闭提交 | §12 + SUMMARY_p036 + 台账 | 见 §3.41.15 |

---

## 8. 台账收口（PROGRESS §1.4）

| 项 | 终态 |
|----|------|
| U-P024-1（mypy 版本上限） | **done**（B0 钉 `~=2.4.1`） |
| U-P024-2（lock-check） | done（P-034 承接） |
| U-P024-3（检查面扩展） | **done**（10 面双载体，run 44029888652） |
| U-P024-4（filter 21 条） | **done**（代码级修复 + override 删除） |
| U-P036-1（版本上界） | **done**（B0） |
| U-P036-2（override 移除） | **done**（B3 三条件） |
| U-P036-3（union-attr 真修） | **done**（U-a assert + 根因收窄 + C2 缺陷修复） |
| U-P036-6（异构终审） | **done**（GLM-5.3-Flash，CHECKLIST §12） |
| U-P036-4（tools/examples 纳入） | pending（条件触发：任一目录出现生产调用） |
| U-P036-5（core-follow=0 机制） | pending（D6 不立项；门禁语义不受影响） |

---

## 9. 边界遗留

1. **CI 依赖未钉版本**：numpy 在 3.12/3.10 leg 分别解析为 2.5.5 / 2.2.6——本批以三口径围堵；若需根治可在 CI 钉 numpy（属依赖治理，未在本批题干）。
2. **U-P036-4**：`tools/` / `examples/` / `demo/` / `memory/` 未纳入门禁（显式未覆盖项）。
3. **U-P036-5**：主环境 core-follow=0 机制未归因（不影响 CI 门禁语义）。
4. **本地 pytest 需 `MPLBACKEND=Agg`**（O-S10-P036-1；CI 已设）。
5. `filter/na_factor.py` `strategy: str` 放宽后，非法 strategy 值由运行期 `strategies[name]` KeyError 兜底（既有行为，未变更）。

---

## 10. 启示（六条）

1. **门禁改动是双载体原子操作**：`tests.yml` 与 `spec_runner_adapter.py` 必须同提交——`test_p024_ci_gate_alignment` 守卫救了一次（F-S9-P036-1，B1 首跑 760→1 failed），先例应固化。
2. **「本地绿 ≠ CI 绿」的结构性来源是依赖未钉**：mypy 桩随 numpy 版本变——复刻环境必须钉到 CI 实装版本，且多口径复跑是漂移探测器而非形式（本批三口径抓出 10 条兼容面）。
3. **根因聚类的杠杆效应真实存在**：131 条中 37 条（28%）由 2 个根因产生（guru_data 25 + mask 12）；按簇修复让 B2 的 96 条在 13 文件内闭合。
4. **类型检查捕获「测试捕获不到」的缺陷**：C2 静默影子属性（`tracker.cash=` 动态建属性、调资静默失效）在任何运行时测试里都表现为「正常」——`attr-defined` 是唯一防线。
5. **同基座终审 + 异构终审双层都有增量**：同基座独立会话抓到 3 P3（含统计笔误），异构终审再抓到 1 P3 交叉引用瑕疵 + 1 项方法归属澄清——RULE-5 的增益在本批第四次实证（P-034 之后）。
6. **区间口径必须双声明**：审计区间（代码 5 提交）与全程区间（15 提交）分开陈述，防止 F-U3-P034-1 同型口径混写复发。
