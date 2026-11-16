# DESIGN：P-036 mypy 检查面扩展

> **批次**: P-036 · **Step 3 设计** · 日期 2026-11-17 · 来源日期 2026-11-17（读取日）
> **判档**: **T1**（门禁判据面变更；SPEC_PROCESS 判档规则 2）
> **作者基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构，RULE-5）
> **上游**: [RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md)（§4 两方案读数 / §5 R1' 控变量定论 / §6 A-B-C 分级 / §7 方案矩阵 / §11 B0 记录 / §12 Step 2 异构复审 pass：1 P2 + 3 P3 当轮回写）
> **代码证据时点**: HEAD `775358c`；B0 已落地（`mypy~=2.4.1` + 锁/本地 2.4.1）

---

## 1. 设计目标

在 **B0（mypy 版本定版，已完成）** 之后，把类型门禁的检查面从 `core` 扩展到全部生产面，并把各面错误**真修到 0**，分三批可独立验收：

| 目标 | 判据 |
|------|------|
| G1 门禁覆盖 | CI `mypy` 步骤 target 扩展至 `core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library` |
| G2 真修非压制 | 零裸 `# type: ignore`；每个修复可追溯到类型根因 |
| G3 行为守恒 | golden 13 零重录；`pytest` 全绿；公开签名零变更；`except Exception` 恒 22 |
| G4 双口径一致 | 修复后每批 target 在 **pandas 2.2.3 与 3.1.1** 双口径下均 0 error |
| G5 可回退 | B1/B2/B3 各自原子提交（代码 + 门禁 target + 文档），可单独 revert |

---

## 2. 决策详述

### D1 基线口径固定：CI 口径为准，双口径验证为回归保护

Step 3 重测发现**读数对 pandas 版本敏感 2 条**（Step 1/2 未识别）：

| 口径 | pandas | mypy | 合并读数 | 差异构成 |
|------|--------|------|----------|----------|
| **CI 口径（判据基准）** | 3.1.1 | 2.4.1 | **129 errors / 25 files** | — |
| 本地口径 | 2.2.3 | 2.4.1 | **131 errors / 25 files** | `no-any-return` 34→**38** / `call-overload` 4→**2**（全在 `agents/`，净 +2） |

**决策**：门禁判据以 CI 口径（pip 解析最新 = 当前 3.1.1）为准；**每批验收必须双口径复跑**（本地 2.2.3 + 隔离 venv 3.1.1），避免「本地绿 / CI 红」。此差异登记为 **O-D3-P036-1**（pandas 类型推断差异，随 pandas 版本变化，不追平）。

### D2 门禁 target 最终形态与三批边界

**最终 target（10 面）**：`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`

`web`（9 files）与 `factor_library`（2 files）当前 **0 error**——纳入成本为零，收益是**锁死未来回归**。

| 批 | target 增量 | 错误数（CI 口径） | 根因簇（行距 ≤5 估算） | 依据 |
|----|-------------|------------------|----------------------|------|
| **B1 小模块** | `scripts` + `cli.py` + `strategy_evaluation` + `order_strategy` + `batch_backtest` +（`web`/`factor_library` 零成本） | **14**（5+3+3+2+1+0+0） | ~10 | 低风险、无副作用面，先打通「修 → 扩 target → CI 绿」完整链路 |
| **B2 agents** | `agents` | **96**（本地 98） | ~56（含 `guru_agent_v2` 14 簇） | 占总量 73%；含 50 条 A 级 `union-attr`；单独立批便于独立验收与回退 |
| **B3 filter + 去豁免** | `filter` + 移除 `[[tool.mypy.overrides]] filter.*` | **21** | ~13（`universe_filter_clean` 4 簇） | 与 override 移除绑定（U-P036-2 / U-P024-4 关闭） |

**注**：B1 = 14、B2 = 96、B3 = 21，合计 **131**（本地口径）；CI 口径 B2 为 94，合计 129。两口径差异全在 B2（`no-any-return` +4 / `call-overload` −2）。

### D3 修复策略分层（优先级从高到低）

| 层 | 手段 | 适用 | 约束 |
|----|------|------|------|
| **L1 根因收窄** | 在构造期/入口把 `Optional[T]` 收窄为 `T`（None 时 `raise` 或显式降级） | 同一属性被多处解引用（如 `guru_agent_v2.guru_data` 26 条 → 1 处守卫） | 引入 `raise`/早退属**行为变更**，须逐项裁决并登记（R-P036-1） |
| **L2 访问点窄化** | `assert x is not None` / 局部变量 + `if` / `isinstance` 收窄 | 调用点已有运行时前提（如 `if x is None: build()` 之后） | `assert` 仅用于**已成立的运行期事实**；不得用 `assert` 掩盖真实 None 分支 |
| **L3 注解/签名修正** | 显式变量注解（`var-annotated`）、`cast` 到真实类型、修正返回类型 | `no-any-return` / `var-annotated` / `call-overload` | `cast` 目标必须是**运行期真值类型**；禁止 `cast(Any, ...)` 式逃避 |
| **L4 忽略（受限）** | `# type: ignore[code]` + 理由 | 仅当第三方桩缺陷且无法绕开 | 必须带具体 code（禁裸 ignore）+ 行内理由；总数上限 **3**，超出须回 DESIGN 裁决 |

**明确禁止**：`# type: ignore` 无 code；`--follow-imports=silent` 绕过；对 `agents`/`filter` 新增 `ignore_errors`。

### D4 行为变更边界（R-P036-2 裁决）

`union-attr` 50 条中存在两类：

| 类 | 特征 | 处置 |
|----|------|------|
| **U-a 已有运行期前提**（如 `_tradable_mask` 前有 `if ... is None: build_masks()`） | 缺的只是**类型层证明** | 用 L2（`assert`/局部变量）收窄，**零行为变更** |
| **U-b 无任何前提**（如 `guru_data` 直接 `.get()`） | 运行期可能 `AttributeError` | 用 L1 守卫——**必须裁决**：① 上游保证非 None → 构造期 `raise ValueError`（把隐式崩溃变显式）；② 允许缺失 → 给默认值（`{}`）并登记语义 |

**裁决原则**：优先「与现网行为等价」（②默认值）除非上游明确保证；任一 `raise` 新增必须在 IMPL 逐条列出并经 CHECKLIST 验收。**公开签名零变更**为硬约束。

### D5 filter 豁免移除的绑定条件

`[[tool.mypy.overrides]] filter.* ignore_errors` 的移除与 **B3 同批原子提交**，且必须满足：

1. `mypy filter`（无 override）= **0 error**（双口径）；
2. 移除 override 后 `mypy core`（现门禁面）**仍为 0**——因为 filter 已 0，follow 无错误可渗（F-S2-P036-1 的教训：移除前必须已修完，不能只去掉 target）；
3. 注释中的「B3 修完后应移除本 override」一并删除。

### D6 O-P036-5 不单独立项

主环境 `core` 构建恒 0 / `filter` 直检恒 21 的机制未归因——**不影响 CI 门禁语义**（CI 走仓库 config 且无缓存残留），也不影响本批任何判据。维持 `U-P036-5` pending（条件触发：mypy 版本升级 / 需要本地无 override 取证口径）。**不为它造调查批**（避免扩大范围）。

### D7 不引入 `warn_unused_ignores` / `strict`

| 候选 | 裁决 | 理由 |
|------|------|------|
| `warn_unused_ignores = true` | **不做** | 会对现有代码产生未知数量新错误，超出本批题干；且与 D3-L4 的 3 条上限叠加后价值边际 |
| `strict = true` | 不做 | 数百条新错误，无分批可验收性 |
| `disallow_untyped_defs = true` | 不做 | 同上；且 `check_untyped_defs` 已覆盖函数体 |

---

## 3. 不变式 I1-I7

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | golden 13 条**零重录**（类型修复不改变计算结果） | `pytest -k golden` |
| I2 | 公开签名零变更（`execute_order` / `is_valid_price` / 各 agent 公开方法） | `git diff` 中 `^-\s*def ` = 0 |
| I3 | `except Exception`（P-029 十文件口径）恒 **22**；零新增 `except Exception` | AST 脚本 |
| I4 | `pytest` 不减：**760 → 760+X**（X = 本批新增断言，可为 0） | `pytest -q` |
| I5 | 每批代码修复与 `tests.yml` target 扩展**同批原子提交**；CI 四 job 全绿 | CI run |
| I6 | 每批 target 在 **pandas 2.2.3 / 3.1.1 双口径**下均 **0 error** | 主环境 + 隔离 venv |
| I7 | 裸 `# type: ignore` 计数 = **0**；带 code 的 ignore ≤ **3** | `Grep '# type: ignore'"'"'`（无方括号）计数 |

---

## 4. 验证契约 V1-V6

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| **V1** | B1 全绿 | `mypy core scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`（无 override 无关，filter 未纳入） | CI 口径 0 error；本地口径 0 error |
| **V2** | B2 全绿 | 在 V1 基础上加 `agents` | 双口径 0 error |
| **V3** | B3 全绿 + 去豁免 | 加 `filter` 且**删除** `[[tool.mypy.overrides]]` | 双口径 0 error；`mypy core` 仍 0 |
| **V4** | 最终门禁 | `tests.yml` 的 `mypy` 步骤（10 面） | 0 error；CI 四 job 全绿 |
| **V5** | 行为守恒 | golden / pytest / 签名 / except 计数 | I1-I4 全部成立 |
| **V6** | 忽略审计 | `Grep '# type: ignore'` 全仓（限 10 面） | 裸 ignore = 0；带 code ≤ 3 |

### 红态口径（每批 Step 9 必须出示）

| 批 | 红态（修复前） | 绿态 |
|----|---------------|------|
| B1 | `mypy <B1 面>` = **14 errors / 7 files**（实测 @`775358c`，本地口径） | 0 |
| B2 | `mypy agents`（CI 口径）= **94 errors / 11 files**；（本地）= 96 | 0 |
| B3 | `mypy filter` = **21 errors / 7 files**；+ `mypy core`（去 override）= 21 渗入 | 0 / 0 |

> **红态不伪造**：B1 的 `web`/`factor_library` 现状即 0 → 属**回归保护**（纳入 target 防未来回归），不计入红态。
>
> **实测读数（@`775358c`，本地 pandas 2.2.3 口径）**：B1 面 `14 errors / 7 files（checked 31 source files）`；B2 `agents` `96 errors / 11 files（14 source files）`；B3 `filter` `21 errors / 7 files（10 source files）`。

---

## 5. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| **R-P036-1** | 风险 | L1 根因收窄可能引入新 `raise`/早退 → 运行期行为变更（`guru_data=None` 时由 `AttributeError` 变 `ValueError` 或默认值语义） | 逐项列于 IMPL §变更表；优先默认值；`raise` 须 CHECKLIST 单列验收 |
| **R-P036-2** | 风险 | `no-any-return` 用 `cast` 可能掩盖真实的 Any 传播链（类型"变绿"但根因仍在） | 修复须说明 Any 来源；`cast` 目标为真实类型；Step 10 盲区扫描单列 |
| **R-P036-3** | 风险 | 双口径差异（D1 的 2 条）可能导致某批本地绿 / CI 红 | 每批双口径复跑（I6）；以 CI 口径为判据 |
| **R-P036-4** | 风险 | B2 的 96 条中可能藏**真实缺陷**（如 `agent_framework.py` 的 `DataManager \| None` 解引用），Step 9 可能从"类型修复"升级为"缺陷修复" | 允许升级；若发现 P1/P2 立即登记并按 P-029/P-031 口径处理（不在本设计预判） |
| U-P036-2 | 未决 | `filter.*` override 移除（B3） | 本批 B3 关闭 |
| U-P036-3 | 未决 | 50 条 `union-attr` 是否全真修（vs assert/cast 掩盖） | 本设计 D4 已裁决分层；Step 9 逐条留证 |
| U-P036-4 | 未决 | `tools/`/`examples/`/`demo/`/`memory/` 不纳入 | 维持 pending（本批显式未覆盖） |
| U-P036-5 | 未决 | 主环境 core-follow = 0 机制未归因 | 维持 pending（D6 不立项） |
| O-D3-P036-1 | 观察 | pandas 2.2.3 vs 3.1.1 的 2 条推断差异（no-any-return +4 / call-overload −2，全在 agents） | 登记不改（D1） |
| O-D3-P036-2 | 观察 | `no-any-return` 38 条（B 方案）占总 29%，属注解卫生；若 B2 成本失控可考虑拆 B2a/B2b（按文件） | 登记（IMPL 阶段视情况） |
| O-D3-P036-3 | 观察 | `guru_agent_v2` 26 条 = 1 根因（`guru_data: Optional[dict]`）；`universe_filter_clean` 12 条 = 3 个 `_*_mask` 属性 | 作为 L1/L2 模板写进 IMPL |

---

## 6. 批量切分与回退点

| 批 | 内容 | 提交单元 | 回退点 |
|----|------|---------|--------|
| **B1** | 修复 14 条 + `tests.yml` target 加 6 面 + 文档 | 1 主提交（代码+workflow）+ 1 回填 | revert 主提交即回到 `core` 单面门禁 |
| **B2** | 修复 96 条 + target 加 `agents` | 1 主提交 + 1 回填 | revert 即回到 B1 状态（agents 不入 target） |
| **B3** | 修复 21 条 + 删 override + target 加 `filter` | 1 主提交 + 1 回填 | revert 即回到 B2 状态（override 与 filter target 一并回退） |

**顺序依赖**：B0（已完成）→ B1 → B2 → B3。B2 与 B3 无相互依赖（可交换），但 B3 必须在 B2 之后**验收**以便 `mypy core` 去 override 的复验在最大 target 下进行。

---

## 7. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-D3-P036-1** | **P2** | **读数对 pandas 版本敏感 2 条**（129 ↔ 131）——Step 1/2 均按单一口径记录，未识别该变量；若按 129 修到 0，本地 pandas 2.2.3 可能残留 2 条 | D1 固定双口径验证；V1-V3 全部双口径断言；登记 O-D3-P036-1 |
| F-D3-P036-2 | P3 | 根因聚类揭示「131 条 ≈ 87 簇」且 **2 个根因占 36 条（27%）**——按条数估算工作量会高估 | D2/D3 按簇设计；IMPL 以簇为任务单元 |
| F-D3-P036-3 | P3 | RESEARCH §7 M-B 的 B1 边界写「小模块 14 条」，未包含 `web`/`factor_library`（0 error）的纳入决策 | D2 明确纳入（零成本锁回归） |

---

## 8. 下一 Step

**Step 4 设计 Review（须异构基座）**：核验 D1 的双口径读数、D3 分层是否可机械执行、D4 的行为变更裁决原则是否越界、V1-V6 是否可复现、I1-I7 是否覆盖 B0 遗留约束。
