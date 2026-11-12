# RESEARCH：P-023 质量护栏（F-A1 静默空回测 + U-006-R mypy 盲区）

> **批次**: P-023 · **T1**（`core/engine_v2.py` / `core/data_v3.py` 行为变更 + 盲区清零；判档规则 1 Layer-1 + 规则 2「行为契约变更」强制升级）
> **上游**: [PROGRESS §1.4](PROGRESS.md) U-006-R / F-A1(P-012)；[CHECKLIST_p007 §9.3](CHECKLIST_p007_mypy_layerb.md) F-A1（权威来源）
> **下游**: [DESIGN_p023_quality_guardrails.md](DESIGN_p023_quality_guardrails.md) → [IMPL_p023_quality_guardrails.md](IMPL_p023_quality_guardrails.md) → [CHECKLIST_p023_quality_guardrails.md](CHECKLIST_p023_quality_guardrails.md)
> **代码证据时点**: HEAD `c2a1918`（2026-11-12，工作区干净）
> **状态**: Step 1 调研完稿

---

## 1. 背景与目标

两项技术债在 P-007 层 B 收口时挂起（Q4=B），前置条件已随 P-012 L5 接口治理与 P-021/P-022 收口解除：

- **F-A1（静默空回测）**：P-007 层 B 为「空 `factor_files`」加了 fail-fast 守卫，但守卫对「注入 `factor_pipeline` / `factor_combiner`」路径豁免；豁免路径下若信号未就绪，`run()` 仍走完全程并返回**完整结果字典**（0 快照 / 0 交易）。P-007 记为「已知限制（自我责任）」，本批实测证明为**确定性缺陷**且有三处缺失守卫。
- **U-006-R（mypy 盲区残差）**：`mypy --explicit-package-bases --check-untyped-defs core` 现存 **4 errors 2 files**（P-012/P-011 实施后由 8 降至 4）；门禁命令不含 `--check-untyped-defs`，故 CI 始终绿。本批复评并清零。

**目标**：① 注入式工作流信号未就绪时 fail-fast（不再返回假成功结果）；② 空快照不得产出「成功」结果；③ U-006-R 4 项清零且既有 647 项测试零回归；④ F-A1 的台账来源标注失准一并订正。

**出界（不回答）**：`run()` 逐日 `except Exception: continue` 的 retry 语义重构（U-P023-1）；`--check-untyped-defs` 是否纳入 CI 门禁（U-P023-2）；`EngineV3Vector` 的信号路径；真实数据下的因子质量。

---

## 2. 本仓事实（P1-P13）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **立项来源两行**：`U-006-R`（mypy 盲区 4 errors 2 files，T3「评估决策 + 可选小修，零行为」）与 `F-A1(P-012)`（注入式工作流未注入信号 → 静默空回测，T3「小修 + 1 测试」） | E3 [PROGRESS.md](PROGRESS.md) §1.4 L65-L66 @`c2a1918` |
| **P2** | **来源标注失准（编号撞车）**：PROGRESS 写「P-012 CHECKLIST §11 P3 发现」，但 ① P-012 CHECKLIST §11 是「后续行动」表（L486），全文无「静默空回测」；② P-012 的 `F-A1` 是同名**另一发现**（§9.2 L306：`limit_check_price` 文档列名遗漏）；③「静默空回测」的权威来源实为 **P-007 CHECKLIST §9.3 L210** | E1 `Select-String "F-A1"`：P-012 CHECKLIST = **3** 处（均指另一发现，L289/L306/L333）/ P-007 CHECKLIST = **4** 处；E3 两文档对应行 |
| **P3** | **守卫历史（F-S9-1）**：P-007 初版无条件守卫使 13 个既有用例失败（注入 `factor_pipeline` + `factor_combiner` 后**手工注入信号**、`factor_files` 为空），故收紧为「无注入 pipeline/combiner **且** `factor_files` 为空」 | E3 [IMPL_p007 §9 F-S9-1](IMPL_p007_mypy_layerb.md) |
| **P4** | **三条静默路径（读码）**：① `setup()` 守卫 L187-L195 对注入路径放行；② `_precompute_factors()` L286-L288 在 `factor_files` 为空时仅 `logger.warning` 后 `return`，`_composite_signal` 保持 `None`；③ `run()` L319-L330 逐日 `try/except Exception: continue`，吞掉 `_process_trading_day` L361 的 `assert ... signal_df is not None`（`AssertionError` 无消息） | E3 [engine_v2.py](../core/engine_v2.py) L187-L195 / L283-L307 / L319-L330 / L354-L361 @`c2a1918` |
| **P5** | **第四处缺失守卫**：`_generate_results()` L1135-L1136 只查 `tracker`/`executor`，不查 `snapshots` 是否为空 → 零快照仍生成完整报告并返回 | E3 engine_v2.py L1133-L1140 @`c2a1918` |
| **P6** | **探针 A 复现（注入 pipeline+combiner，`factor_files=[]`）**：`setup()` **OK** → `run()` **OK** → `snapshots=0` / `trades=0` / `_composite_signal=NoneType` / **ERROR×4**（消息为空串）+ WARNING×1（「未指定因子文件」） | E2 `%TEMP%\p023_fa1_probe.py` 场景 A |
| **P7** | **探针 C（仅注入 pipeline、不注入 combiner）**：与 A 完全同形——守卫的 `and` 条件使「只注入一个组件」即放行，且 `_precompute_factors` 因 `factor_files` 空而**从未调用**注入的 pipeline | E2 探针场景 C |
| **P8** | **探针 D（对照：正规用法，`factor_files=["dummy.pkl"]`）**：`setup()` OK → `run()` OK → `snapshots=5` / `trades=8` / `_composite_signal=DataFrame` | E2 探针场景 D |
| **P9** | **探针 E**：`setup()` 成功后直接调 `_generate_results()` **不抛异常**，返回完整结果字典（信号仍为 `None`） | E2 探针场景 E |
| **P10** | **既有 13 用例形态**：`FactorCombiner([], {})` 注入 + `engine.setup()` + **setup 之后**手工赋值 `engine._composite_signal = pipeline.process(signal).fillna(0)` 再 `run()`；`test_06_engine_v2_setup` 只 setup 不注入不 run | E3 [test_real_ashare_backtest.py](../tests/test_real_ashare_backtest.py) L111-L204；[test_real_ashare_strict_validation.py](../tests/test_real_ashare_strict_validation.py) L315/L456/L588 |
| **P11** | **U-006-R 残差 4 条（实测）**：① `data_v3.py:130` `enumerate(self.dates)` 收到 `ndarray \| None`；② `data_v3.py:131` 同（`self.stocks`）；③ `engine_v2.py:224` `FactorPipeline(self.dm, ...)` 收到 `IDataManager \| DataManager`，形参要求 `DataManager`；④ `engine_v2.py:293` `self.dm.load_factor(...)` 于 `IDataManager \| None` 上访问 | E1 `mypy --explicit-package-bases --check-untyped-defs core` → `Found 4 errors in 2 files (checked 36 source files)` |
| **P12** | **`FactorPipeline` 要求具体类**：`__init__(data_manager: DataManager, ...)`，且 `process()` 使用 `self.dm.industry` / `self.dm.mktcap`（`DataManager` 独有属性，`IDataManager` 协议未声明）→ 不能把形参注解改为协议 | E3 [factor.py](../core/factor.py) L32 / L315 / L329；[interfaces.py](../core/interfaces.py) L25-L81 |
| **P13** | **`DataLoaderV3.dates/stocks` 声明 Optional**：`__init__` 声明 `Optional[np.ndarray]`，`_load_from_pandas` L111-L112 赋 `ndarray`，`_build_maps()` L128-L131 为唯一 `enumerate` 点且仅由 `_load_from_pandas` 调用 | E3 [data_v3.py](../core/data_v3.py) L44-L45 / L111-L112 / L128-L131 @`c2a1918` |

**严重度重估**：F-A1 由 P3 上调为 **P1**——产品返回的是**完整结果字典**（下游会把 0 收益 0 交易当作成功回测），且 ERROR 消息为空串（`AssertionError` 无消息），可观测性接近零；P6/P7 证明触发面覆盖「注入任一组件 + 空 factor_files」两类合法构造。U-006-R 维持 **P3**（静态盲区，无运行时后果）。

---

## 3. 外部锚点（F1-F4）

### 3.1 降级链（F3）

`typing.cast` 官方页 `https://docs.python.org/3/library/typing.html#typing.cast` **读取失败**（页面 21KB 截断于目录区，未含 `cast` 条目）→ 降级至 mypy 官方 *Type narrowing* 页的 §Casts 节（同主题、维护方为 mypy 核心团队），**命中正文**。无其他降级。

### 3.2 锚点清单与验证表（F1/F2/F4）

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点 |
|----|------|-----------|--------|------|----------|
| **E1** | PEP 20 *The Zen of Python* | Active（Created 2004-08-19） | 2026-11-12 | ✅ 正文 | 「Errors should never pass silently. / Unless explicitly silenced.」——静默空回测属未显式静默的错误通过 |
| **E2** | mypy docs *The mypy command line* — `--check-untyped-defs` | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 该旗标「type checks the body of every function, regardless of whether it has type annotations」；默认不检查无注解函数体 → 即 U-006 盲区定义 |
| **E3** | mypy docs *Type narrowing* — §Casts | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 「mypy casts are only used as hints for the type checker, and they don't perform a runtime type check」→ `cast` 零运行时 |
| **E4** | Python docs *typing* — `typing.cast` | 3.13 docs | 2026-11-12 | ⚠️ 页面截断（目录区后未含 cast 节） | **未采用为判据**；以 E3 替代（F3 降级记录） |

> **F4**：有效外部引用 **3 条**（E1-E3）≥3，已建表。**F1/F2**：每条带发布版本与读取日。**F5**：Step 1 已取得 5 组红灯读数（§5），Step 9 以同探针转绿回填。

---

## 4. 方案矩阵（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 数据风险 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **M-A 双守卫 + 盲区窄化（推荐）** | `run()` 入口信号就绪 `RuntimeError` + `_generate_results()` 空快照 `RuntimeError` + U-006 四项窄化 | 低（2 文件 + 测试） | 高：消除假成功结果 | 低 | 高（setup 语义不变，13 用例不受影响） | 低 | 1 批 | 语义清晰 |
| M-B 仅升级 warning | `_precompute_factors` 的 warning 改为 error 级日志 | 极低 | 低：仍返回假成功 | 低 | 高 | **高**（静默仍在） | 1 批 | 缺陷残留 |
| M-C `setup()` 强制信号就绪 | setup 末尾校验 `_composite_signal is not None` | 低 | 高 | 低 | **低**（13 个既有用例 setup 后注入，全破） | 低 | 需改 13 用例 | 与 P-007 F-S9-1 冲突 |
| M-D 异常分类 + retry 语义重构 | 收窄 `except Exception`、区分可重试异常 | 中高 | 高 | 中 | 中（崩溃行为变化面大） | 中 | 多批 | 过度设计 |

**判定**：
- **M-A 采用**：`run()` 是「信号已就绪」的唯一充分时点（P10 证明 setup 不是）；`_generate_results` 守卫覆盖零交易日形态（P9）。两守卫均为 `RuntimeError`，与 P-007 D3 已有守卫同型同文案族。E1 支撑「不得静默」；E3 支撑 U-006 四项用 `cast`/`assert` 收窄（零运行时）。
- **M-B 否决**：warning 已存在（P6 实测 WARNING×1），问题不是日志级别而是**返回值语义**。
- **M-C 否决**：直接破坏 P10 的 13 个既有用例，与 P-007 F-S9-1 的裁决正面冲突。
- **M-D 出界**：`except Exception: continue` 是 P-007 RESEARCH A26 已登记的 `Catch Generic` 反模式，重构需独立批次（U-P023-1）。

---

## 5. 取证读数（Step 1）

| # | 命令/探针 | 读数 |
|---|-----------|------|
| A | `pytest -q`（基线，Agg，Python312 3.12.10） | **647 passed**（P-022 收口态） |
| B | `mypy --explicit-package-bases core`（门禁口径） | **Success: no issues found in 36 source files**（0 errors） |
| C | `mypy --explicit-package-bases --check-untyped-defs core`（盲区口径） | **Found 4 errors in 2 files (checked 36 source files)** |
| D | `black --check core tests cli.py` | **112 files would be left unchanged** |
| E | 探针 A（注入 pipeline+combiner，`factor_files=[]`） | setup OK / run OK / snapshots=0 / trades=0 / signal=NoneType / ERROR×4（空消息） |
| F | 探针 C（仅注入 pipeline） | 同 E（守卫 `and` 放行） |
| G | 探针 D（对照：`factor_files=["dummy.pkl"]`） | snapshots=5 / trades=8 / signal=DataFrame |
| H | 探针 E（setup 后直接 `_generate_results`） | 不抛异常，返回完整结果字典 |

---

## 6. 未决项登记（四元块）

- **U-P023-1 `except Exception: continue` 的 retry 语义**
  - 判据：逐日捕获范围收窄为「可重试异常白名单」，或明确保留 catch-all 并给出理由
  - 触发条件：出现第二例「被 catch-all 吞掉的确定性缺陷」
  - 当前倾向：本批不收窄（P-707 A26 已登记；改动面覆盖全部交易日路径）
  - 证据等级：E3（engine_v2.py L328-L330）

- **U-P023-2 `--check-untyped-defs` 是否纳入 CI 门禁**
  - 判据：`tests.yml` 的 mypy 行含该旗标且 exit 0
  - 触发条件：盲区残差再次 >0，或新增无注解函数 ≥5 个
  - 当前倾向：不纳入（本批清零后残差 0，纳入属扩大门禁面，需独立裁决）
  - 证据等级：E1（tests.yml 当前命令）

- **U-P023-3 零交易日回测的合法形态**
  - 判据：明确「`dm.trade_dates` 为空」时是否应 fail-fast
  - 触发条件：真实数据出现空交易日集
  - 当前倾向：本批由 `_generate_results` 空快照守卫统一 fail-fast（不区分原因）
  - 证据等级：E2（探针 E）

- **U-P023-4 `EngineV3Vector` 信号路径**
  - 判据：v3 向量引擎是否存在同形「信号 None → 静默空回测」
  - 触发条件：v3 路径被外部消费
  - 当前倾向：不查不改（本批范围仅 engine_v2）
  - 证据等级：未取证（出界声明）

---

## 7. 批次切分建议

| 批次 | 内容 | 行为变更 |
|------|------|----------|
| **B1** | `run()` 入口信号就绪守卫（F-A1 主修）+ 2 项测试 | 是（静默→RuntimeError） |
| **B2** | `_generate_results()` 空快照守卫（F-A1 补）+ 2 项测试 | 是（零快照→RuntimeError） |
| **B3** | U-006-R 四项窄化（data_v3 `_build_maps` / engine_v2 L224 cast / L293 别名）+ 无新增测试（由 mypy 读数验收） | 否（零运行时） |
| **B4** | 四文档 + PROGRESS/CHANGELOG + F-A1 来源标注订正 | 文档 |
| **B5** | CI 回收与回填 | 文档 |

> 顺序约束：B1 → B2 → B3（B3 的行号收窄依赖 B1/B2 落位后的文件形态；若先做 B3 需二次对齐）。

---

## 8. Step 2 Review（独立 pass）

> **执行方式**：正文完稿后重读全文 + 机械复核锚点（RULE-1 时序独立；本会话单 Agent，RULE-4 标注「自查·单视角」）。

### 8.1 机械复核

| # | 断言 | 复核结果 |
|---|------|----------|
| 1 | P2「来源标注失准」 | ✅ **初稿断言有误已修正**：初稿写「P-012 CHECKLIST `F-A1` = 0 命中」，实测 **3 处命中**——但 3 处均指同名另一发现（`limit_check_price` 文档列名，L306）；「P-012 §11 无此内容」与「静默空回测权威源为 P-007 §9.3 L210」两条成立。修正后表述为「编号撞车」而非「不存在」 |
| 2 | P4 行号 | ✅ `engine_v2.py` L187 `if (` / L195 `)` / L286 `if not self.cfg.factor_files:` / L288 `return` / L328 `except Exception as e:` / L330 `continue` / L361 `assert ... signal_id is not None`（实际 `signal_df`）逐行命中 |
| 3 | P5 行号 | ✅ L1135 `if self.tracker is None or self.executor is None:` / L1136 `raise RuntimeError(...)` |
| 4 | P11 四条 | ✅ `mypy --explicit-package-bases --check-untyped-defs core` 末行 `Found 4 errors in 2 files (checked 36 source files)`，四条与 §2 P11 逐字同 |
| 5 | P13 行号 | ✅ `data_v3.py` L44-L45 Optional 声明 / L111-L112 赋值 / L128 `def _build_maps` / L130-L131 `enumerate` 逐行命中 |
| 6 | P12 依据 | ✅ `factor.py` L32 `def __init__(self, data_manager: DataManager, ...)`；L315 `self.dm.industry` / L329 `self.dm.mktcap` 存在；`interfaces.py` `IDataManager` 无 `industry`/`mktcap` 成员 |
| 7 | 外部引用 F4 | ✅ 3 条有效（E1-E3）+ 1 条降级（E4 截断未采用）；E1 PEP 20 正文「Errors should never pass silently」逐字命中；E2 `--check-untyped-defs` 定义命中；E3 Casts「don't perform a runtime type check」命中 |
| 8 | 探针读数可重放 | ✅ 探针脚本路径已记录（`%TEMP%\p023_fa1_probe.py`）；场景 A/C/D/E 四组读数与 §5 E-H 逐字对应 |

### 8.2 门禁四项（SPEC_PROCESS Step 2 门禁）

| 项 | 结论 |
|----|------|
| (a) FALSIFIED 断言已改写 | ✅ 1 项：P2 初稿「0 命中」→ 修正为「3 处命中但全指另一发现（编号撞车）」 |
| (b) CONFLICT 已仲裁 | ✅ 无未仲裁冲突。唯一张力：M-C（setup 校验）与 P-007 F-S9-1（13 用例）冲突 → 已在 §4 判定表否决 |
| (c) 阻断性断言双源 | ✅ 静默空回测由「E3 读码（三条路径）+ E2 探针（四场景）」双源；U-006 残差由「E1 命令输出 + E3 行号定位」双源 |
| (d) 假设转 A/B | ✅ 出界项转 U-P023-1~4 四元块（§6），无裸假设留在结论区 |

### 8.3 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P023-1 | P3 | P2 初稿以 `Grep` 子串计数断言「0 命中」，未核对命中的语义归属——编号撞车（两批复用 `F-A1`）导致误判 | 已改写为「3 处命中但全指另一发现」，并把「编号撞车」列为 PROGRESS 订正理由 |

### 8.4 结论

**通过**——0 P1 / 0 P2 / 1 P3（F-S2-P023-1 已当场修正）；可进入 Step 3 设计。
