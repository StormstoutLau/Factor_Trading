# P-007 层 A（非引擎 mypy 清理） · 调研文档

> **文档编号**: RESEARCH_p007_mypy_layera
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 1 完稿；Step 2 Review **通过**（2026-11-09；0 项阻断，3 项 P3 已回写，见 §6）
> **上游**: `docs/PROGRESS.md` §1.4 P-007；[RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md) §TD-9 关联基线
> **下游**: [DESIGN_p007_mypy_layera.md](DESIGN_p007_mypy_layera.md) → [IMPL_p007_mypy_layera.md](IMPL_p007_mypy_layera.md) → [CHECKLIST_p007_mypy_layera.md](CHECKLIST_p007_mypy_layera.md)
> **档位**: T1（改动覆盖 `core/` 多文件，Layer-1）
> **范围**: **层 A 非引擎**——`core/` 下除 `engine_v2.py` / `engine_v3_vector.py` / `factory.py` 外的 16 个文件，共 **26 errors**
> **证据时点**: 本仓读数 @ `8082784`；外部来源读取日 2026-11-09
> **规范版本**: `F:\Spec_Workflow\SPEC_PROCESS.md` **v1.7.2**

---

## 1. 问题定义

P-007 的目标是把 `mypy --explicit-package-bases core` 的 **119 errors** 清零，使 `mypy-check` 门禁转绿并关闭 U-006。

本轮只做**层 A**：非引擎的 16 个文件 / 26 errors（占 22%）。层 B（引擎三件套 93 errors / 78%）另立批次——其 48 处 `union-attr` 集中在 `engine_v2.py`，需改 Optional 判定，风险与本层不可同日而语。

### 1.1 分层依据（E1）

| 层 | 文件 | errors | 占比 | 主要形态 |
|----|------|--------|------|----------|
| **A（本批）** | 16 个非引擎文件 | **26** | 21.8% | 注解补充、Any 收窄、重复定义、Optional 判空 |
| B（另批） | `engine_v2.py` 54 / `engine_v3_vector.py` 26 / `factory.py` 13 | 93 | 78.2% | `union-attr` 48（engine_v2）、`index` 15（v3_vector）、`no-any-return` 9（factory） |

### 1.2 层 A 的 26 项完整分类（本轮核心产出）

> 按**修复性质**分三类：A 真实缺陷（运行时必崩）/ B 潜在缺陷（依赖调用方保证）/ C 纯类型注解（运行时正常）。分类依据为逐行读码，非错误码字面推断。

#### A 类：真实缺陷（4 处 / 6 errors）

| # | 位置 | 错误码 | 缺陷实质 | 当前是否可触发 |
|---|------|--------|----------|----------------|
| A-1 | `risk_monitor.py:724` | `name-defined` + `no-redef`×2（L723/L724） | `remove_monitor()` 内使用**从未定义**的 `RiskAction`（L713 实际用的是 `MonitorAction`）→ 名称为真缺陷；L723/L724 另把「清空列表」写成**带注解的赋值**（`self._x: list[...] = []`），Python 运行时合法（函数内注解被忽略），但 mypy 判定为与 L713/L714 重复声明 | **调用 `remove_monitor()` 即 `NameError`**（由 `RiskAction` 触发）；`no-redef` 两项本身不崩。全仓 0 调用、0 测试覆盖 → 未暴露 |
| A-2 | `global_contagion.py:631` | `attr-defined` | `analyze_market_contagion()` 调用 `monitor.evaluate(...)`，但 `GlobalContagionMonitor` 与基类 `BaseRiskMonitor` **均无 `evaluate` 方法**（基类只有 `monitor()` 抽象方法，`risk_monitor.py:119-122`） | **调用即 `AttributeError`**；全仓 0 调用 → 未暴露 |
| A-3 | `engine_plugins.py:381` | `call-arg` | `create_trigger()` 以 3 个位置参数调用 `PluginRegistry.create(name, config=None, **kwargs)`（`registry.py:135`）——第三个位置参数无对应形参 | **调用 `create_trigger()` 即 `TypeError`**；`create_optimizer`（2 参数）无此问题 |
| A-4 | `data.py:312` | `no-redef` | `_load_auxiliary_data` **重复定义**：L184 与 L312 同名，后者覆盖前者。**生效版本（L312）丢失了 L184 的安全默认值逻辑** | **不崩，但行为退化**：辅助数据文件缺失时 `_suspend_data` 等保持 `None`（L312 不赋值），getter 返回 `None` 且**每次访问都重试加载**（因 `is None` 恒真），造成重复 IO 与重复警告日志 |

> **A-4 的严重性说明**：这不是「删掉重复定义」就能收口的类型问题。两版对比见 §1.3，须在 DESIGN 裁决「删除死代码保持现状」还是「恢复安全默认值（改变运行时行为）」。

#### 1.3 A-4 两版实现差异（逐项对照，E3）

| 数据类别 | L184（死代码，永不执行） | L312（生效） | 差异后果 |
|----------|--------------------------|--------------|----------|
| 前置检查 | 无 | 有 `_load_basic_data()` | L312 更稳 |
| 停牌数据缺失 | `pd.DataFrame(True, ...)` + 警告 | **不赋值** | L312 下 `suspend` 返回 `None` |
| 行业数据缺失 | `pd.DataFrame(1, ...)` + 警告 | **不赋值** | 同上 |
| ST 数据缺失 | `pd.DataFrame(False, ...)` + 警告 | **不赋值** | 同上（`st` 允许 `Optional`） |
| 市值数据缺失 | `pd.DataFrame(1e9, ...)` + 警告 | **不赋值** | 同上（`mktcap` 允许 `Optional`） |

#### B 类：潜在缺陷（4 处 / 4 errors）

| # | 位置 | 错误码 | 缺陷实质 | 触发条件 |
|---|------|--------|----------|----------|
| B-1 | `live_bridge.py:174` | `union-attr` | `intent.asset_type` 类型为 `str \| AssetType`，代码直接取 `.value` | 若调用方传入 `str`，`str` 无 `.value` → `AttributeError`。S1 原文：「If you access the attribute of a value with a union type … **the operation can fail at runtime**」 |
| B-2 | `portfolio.py:223` | `index` | `returns` 声明为 `Optional[...]`，未判空即 `returns[selected_stocks]` | 调用方传 `None` → `TypeError` |
| B-3 | `portfolio.py:300` | `union-attr` | `expected_returns.values`（`Any \| None`） | 同上 |
| B-4 | `portfolio.py:355` | `index` | 与 B-2 同形态（另一 `optimize` 重载内） | 同上 |

> `portfolio.py` 存在 5 个同名 `optimize` 重载（L110/152/195/259/327），B-2/B-3/B-4 分属其中 3 个。是否加防御取决于各重载的上游契约，须在 DESIGN 逐方法判断。

#### C 类：纯类型注解（16 errors，运行时行为不变）

| # | 位置 | 错误码 | 修复方式 | 风险 |
|---|------|--------|----------|------|
| C-1 | `config.py:199` | `no-any-return` | 返回处加 `cast` 或收窄来源类型 | 低 |
| C-2 | `walk_forward.py:250` | `no-any-return` | 同上 | 低 |
| C-3 | `walk_forward.py:258` | `no-any-return` | 同上 | 低 |
| C-4 | `execution.py:235` | `no-any-return` | 同上 | 低 |
| C-5 | `pending.py:538` | `no-any-return` | 同上 | 低 |
| C-6 | `config_v2.py:237` | `no-any-return` | 同上（该模块为 TD-2 冻结资产，改动须限于注解） | 低 |
| C-7 | `rebalance.py:202` | `return-value` | `float(x)` 转原生类型（numpy `floating[Any]` → `float`） | 低 |
| C-8 | `pending.py:462` | `assignment` | 同上（`floating[Any]` 赋给 `int` 目标） | 低 |
| C-9 | `global_contagion.py:192` | `assignment` | 变量被赋两种类型，需拆分变量或扩展注解 | 低 |
| C-10 | `factor.py:338` | `assignment` | `X = []` 后赋值 ndarray；改初值注解或重命名 | 低 |
| C-11 | `factor.py:343` | `call-overload` | 同 C-10 的连带（mypy 仍视 `X` 为 list） | 低 |
| C-12 | `factor.py:352` | `assignment` | 同 C-10 | 低 |
| C-13 | `attribution.py:335` | `var-annotated` | `sectors: set[str] = ...` | 低 |
| C-14 | `global_contagion.py:346` | `var-annotated` | `results: dict[...] = ...` | 低 |
| C-15 | `tracker.py:335` | `var-annotated` | `sector_exposure: dict[...] = ...` | 低 |
| C-16 | `walk_forward_engine.py:290` | `arg-type` | `if __name__ == "__main__"` 测试块内 `base_engine_class=None`；**非生产路径**，建议删除该块或修正调用 | 极低 |

### 1.4 影响面汇总

| 维度 | 内容 |
|------|------|
| 文件 | 16 个（含 1 个冻结资产 `config_v2.py` 仅动注解） |
| 语义改动 | **A 类 4 处 + B 类 4 处为「潜在语义改动」**——其中 A-1/A-2/A-3 修复方向取决于 Q2（修实现 / 删死代码），A-4 取决于 Q1（保持现状 / 恢复默认值），B 类取决于 Q3（加防御 / assert / 仅改注解）；**最终语义面由 DESIGN 裁决** |
| 纯注解 | 16 处 |
| 门禁影响 | 层 A 完成后 mypy 由 `119 → 93`，**仍 fail**；**U-006 不关闭** |
| 测试面 | 现有 507 passed 必须保持；A 类缺陷当前无测试覆盖，是否补测待 DESIGN |
| 引擎文件 | **零改动**（`engine_v2.py` / `engine_v3_vector.py` / `factory.py`） |

---

## 2. 外部来源调研（Step 1，F1/F2/F3）

| ID | 来源 | 等级 | F1 日期 | F2 版本 | 关键事实 | 可解析 ID |
|----|------|------|---------|---------|----------|-----------|
| S1 | mypy《Error codes enabled by default》 | **T1** | 读取 2026-11-09 | stable docs | ① `attr-defined`：检查属性在目标类/模块存在，缺失引用被赋予 `Any`（可能掩盖错误）；② `union-attr`：**「If you access the attribute of a value with a union type, mypy checks that the attribute is defined for *every* type in that union. Otherwise the operation can fail at runtime. This also applies to optional types.」**；③ `var-annotated`：类型无法从初值推断时要求注解；④ `index`：索引操作的类型检查；⑤ `call-arg`：调用参数个数/名称检查 | https://mypy.readthedocs.io/en/stable/error_code_list.html |
| S2 | mypy《Error codes for optional checks》 | **T1** | 读取 2026-11-09 | stable docs | `no-any-return`：「Check that function does not return Any value」——**仅在启用 `warn_return_any` 时触发**，非默认 | https://mypy.readthedocs.io/en/stable/error_code_list2.html |
| S3 | 本仓 `[tool.mypy]` 配置 | **E3** | @ `8082784` | — | `warn_return_any = true`（`pyproject.toml:108`）、`disallow_untyped_defs = false`、`ignore_missing_imports = true` | `pyproject.toml:106-111` |

**F3 降级链**：**无降级**——S1/S2 均 `WebFetch` 直读官方文档原文命中。

### 2.1 来源适用边界

| 关系 | 说明 |
|------|------|
| S1 → A-2 / B-1 的定级 | S1 明文「[union-attr] … the operation can fail at runtime」直接支撑「B 类为潜在运行时缺陷」而非「类型洁癖」 |
| S1 → A-1 的定级 | `name-defined` 章节原文：「Mypy expects that all references to names have a corresponding definition in an active scope … **This can catch missing definitions, missing imports, and typos.**」——官方明确该检查用于捕获缺失定义/拼写错误，直接支撑 A-1 的「`RiskAction` 系未定义名称」判定 |
| S2 + S3 → C 类 6 项 `no-any-return` | 该错误码**非 mypy 默认**，由本仓 `warn_return_any = true` 主动开启。故这 6 项是「本仓自选的严格度」而非工具强加；若将来降低严格度可整体消除，但本批**不采取**该路径（降严格度等于掩盖问题） |
| `no-redef` 未在 S1/S2 单列 | 该错误码属 mypy 默认核心检查，官方错误码章节未提供独立页面（E4：文档覆盖盲区），A-1/A-4 的判定改由读码 + Python 覆写语义支撑 |
| **不外推** | S1/S2 不提供「哪些错误应优先修」的判断；A/B/C 分类完全由本仓读码得出 |

---

## 3. 本仓事实（E1/E3，@ `8082784`）

| ID | 断言 | 证据 |
|----|------|------|
| P1 | `mypy --explicit-package-bases core` = **`119 errors in 19 files`** | E1 |
| P2 | 非引擎 16 文件 = **26 errors**；引擎 3 文件 = **93 errors**（engine_v2 54 / engine_v3_vector 26 / factory 13） | E1 分组统计 |
| P3 | 层 A 错误码分布：`no-any-return` 6、`assignment` 4、`var-annotated` 3、`no-redef` 3、`union-attr` 2、`index` 2、`name-defined` 1、`attr-defined` 1、`call-arg` 1、`return-value` 1、`call-overload` 1、`arg-type` 1 | E1 |
| P4 | `remove_monitor()` 全仓 **0 调用**（仅 `risk_monitor.py:720` 定义） | E1 Grep |
| P5 | `analyze_market_contagion()` 全仓 **0 调用**（仅 `global_contagion.py:622` 定义） | E1 Grep |
| P6 | `BaseRiskMonitor` 仅有抽象方法 `monitor()`，无 `evaluate()` | E3 `risk_monitor.py:110-131` |
| P7 | `PluginRegistry.create` 签名为 `create(self, name: str, config: Optional[Any] = None, **kwargs: Any) -> T` | E3 `registry.py:135` |
| P8 | `data.py` 存在两个 `_load_auxiliary_data`（L184-231 / L312-340），后者覆盖前者；`__init__` 中四个辅助数据属性均初始化为 `None`（L50-53） | E3 |
| P9 | 辅助数据 getter 逻辑为 `if self._x is None: self._load_auxiliary_data(); return self._x`（L124-149）→ 加载后仍为 `None` 时**每次访问都重试** | E3 |
| P10 | `LiveOrder.asset_type` 声明为 `str`（`live_bridge.py:50`），但构造处传入 `str(intent.asset_type.value)` | E3 |
| P11 | `portfolio.py` 有 5 个同名 `optimize` 方法（L110/152/195/259/327） | E1 |
| P12 | `factor.py` 的 `X = []` 无注解（L310），后续 3 处被赋值为 ndarray（L338/343/352） | E3 |
| P13 | `walk_forward_engine.py:290` 位于 `if __name__ == "__main__"` 块内 | E3 |
| P14 | 当前全量 `507 passed`；`mypy-check` 门禁 verdict = fail(119) | E1（P-003 交付基线） |
| P15 | `config_v2.py` 为 TD-2 冻结资产（module docstring 已声明 FROZEN，见 P-002 交付） | E3 |
| P16 | A-1/A-2/A-3 三处缺陷均无测试覆盖（对应函数全仓 0 调用） | E1 + E3 |

---

## 4. 未决点（移交 DESIGN）

| ID | 未决点 | 候选 | 判断依据 |
|----|--------|------|----------|
| Q1 | A-4 `data.py` 重复定义的处理方向 | ① 删 L184 保留 L312 现状；② 删 L184 并把安全默认值合并进 L312（改变行为）；③ 删 L312 保留 L184（恢复原意图但丢前置检查） | 「修 mypy」与「修行为」的边界；改行为须有测试支撑 |
| Q2 | A-1/A-2/A-3 三个死路径缺陷的处置 | ① 修实现使其可用；② 删除死函数；③ 修实现并补测试 | 三处均 0 调用——保留未必有收益，删除可能误删未来接口 |
| Q3 | B 类是否加防御 | ① 全部加 `None`/`isinstance` 判定；② 加 `assert` 声明上游契约；③ 仅改注解声明 Optional | 加防御=改运行时行为；assert 在 `-O` 下失效；仅改注解可能掩盖真实风险 |
| Q4 | 是否为 A/B 类补测试 | ① 全部补；② 仅 A-4 补（影响生产路径）；③ 不补，靠类型检查 | 当前 507 passed 不含这些路径；补测会扩大本批范围 |
| Q5 | C 类 `no-any-return` 的修法 | ① `cast(T, x)`；② 收窄上游类型；③ `# type: ignore` | 本仓无 `type: ignore` 惯例（全仓仅 1 处）；③ 违背清理初衷 |
| Q6 | `config_v2.py`（TD-2 冻结资产）是否可改 | ① 允许纯注解改动；② 完全不动该文件 | 冻结语义是「不新增功能/不接生产」，注解修正是否越界须明确 |

---

## 5. 与其他批次的关系

| 批次 | 关系 |
|------|------|
| P-003（TD-9 black） | 已完成；本批改动的 16 文件均已在 P-003 中格式化，无格式回流风险 |
| P-007 层 B | 本批完成后剩 93 errors；层 B 需在 `engine_v2` 插入 Optional 判定，风险高 |
| P-004 / P-005 | 无直接依赖；本批不改数据层/存储层接口 |
| TD-2 冻结 | `config_v2.py` 受冻结约束（Q6） |

---

## 6. Step 2 Review（独立 pass）

- **执行时点**: 正文完稿后单独执行，未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 重跑 E1 计数与分组 + 逐条复核 26 项分类的「可触发」判断 + 二次直读 S1 的 `name-defined` / `var-annotated` / `index` 段落

**发现 3 项（均 P3，均已修复）**：

| ID | 发现 | 处理 |
|----|------|------|
| **F-R1** | A-1 表述不精确：初稿写「L723/L724 把清空列表误写成带注解属性声明」，未区分 `name-defined`（真崩）与 `no-redef`（不崩，仅重复声明）。带注解赋值在函数内被 Python 忽略，不构成运行时缺陷 | 已拆分表述：`RiskAction` 为真缺陷（NameError），`no-redef` 两项本身不崩 |
| **F-R2** | §1.4 写「语义改动 A 类 4 处 + B 类 4 处」，但其中 7 处的语义方向尚未裁决（取决于 Q1-Q3），写成既定事实会误导读者以为本批必然改行为 | 已改为「潜在语义改动」，并逐项标注依赖的未决点 |
| **F-R3** | §2.1 称 `name-defined` 「未在本轮引用的原文段落中」，实际 S1 有独立章节且明确写「This can catch missing definitions, missing imports, and typos」——该原文正是 A-1 判定的官方依据 | 已改为逐字引用并说明其对 A-1 的支撑关系 |

**复核结果**：

| 断言 | 复核方式 | 结果 |
|------|----------|------|
| P2 分层计数 | `mypy` 输出按文件名分流 | 非引擎 **26** / 引擎 **93**（54+26+13），合计 119 ✓ |
| P3 错误码分布 | `Group-Object` 统计 | `no-any-return` 6 / `assignment` 4 / `var-annotated` 3 / `no-redef` 3 / `index` 2 / `union-attr` 2 / 其余 6 类各 1 = **26** ✓ 与正文逐字一致 |
| 文件数 | 同上 | **16** 个文件（risk_monitor 3 / portfolio 3 / factor 3 / global_contagion 3 / pending 2 / walk_forward 2 / 其余 9 文件各 1）✓ |
| A 类 6 errors | 逐项加总 | A-1（name-defined 1 + no-redef 2）+ A-2（1）+ A-3（1）+ A-4（1）= **6** ✓ |
| B 类 4 errors | 同上 | live_bridge（1）+ portfolio（index 2 + union-attr 1）= **4** ✓ |
| C 类 16 errors | 26 − 6 − 4 | **16** ✓（no-any-return 6 + assignment 4 + var-annotated 3 + return-value 1 + call-overload 1 + arg-type 1） |
| P4/P5 零调用 | `Grep 'remove_monitor\|analyze_market_contagion'` | 各仅 1 处**定义**、0 处调用 ✓ |
| P6 基类无 evaluate | 读 `risk_monitor.py:110-131` | 仅 `monitor()` 抽象方法 ✓ |
| P7 create 签名 | 读 `registry.py:135` | `create(self, name, config=None, **kwargs)` ✓ |
| P8/P9 data.py | 读 L184-231 / L312-340 / L50-53 / L124-149 | 两版差异与 getter 重试逻辑均成立 ✓ |
| S1 二次直读 | 读 `name-defined`（L42-50）、`var-annotated`（L136）、`index`（L265）章节标题与正文 | 命中，无降级 ✓ |

**F3 降级链复核**：S1/S2 均直读原文，无搜索摘要替代。

**结论**: 0 项阻断（P1/P2 = 0）；3 项 P3 已回写；26 项分类可逐项复核，可进入 Step 3 设计。

---

## 7. 结论

层 A 的 26 个 mypy error **不是同质的类型洁癖**：

- **4 处是真实缺陷**（NameError / AttributeError / TypeError / 行为退化），全部因「零调用 + 零覆盖」而长期未暴露；
- **4 处是潜在缺陷**（union/optional 未设防），触发取决于调用方；
- **16 处是纯注解**，运行时正常。

因此本批的产出不应只以「error 数下降」衡量——A 类 4 处与 A-4 的行为退化是实质性修复。同时须如实承认：**层 A 完成后 `mypy-check` 仍 fail(93)，U-006 不关闭**。

六个未决点（Q1-Q6）已移交 DESIGN，其中 Q1（data.py 行为方向）与 Q2（死路径处置）直接决定本批是「纯类型修复」还是「含行为变更」。
