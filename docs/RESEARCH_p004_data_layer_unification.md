# RESEARCH：P-004 数据层统一（DataManager / DataLoaderV3 / DataProvider）

> **批次**: P-004 · **T1**（触及 `core/data.py`、`core/data_v3.py`、`core/data_provider.py`、`core/interfaces.py`、`core/engine_v2.py`、`core/factory.py`、`filter/`，Layer-1）
> **上游**: [PROGRESS.md](PROGRESS.md) §1.4 P-004（唯一 P2，前置已解除）；[RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md) TD-1；[RESEARCH_bias_interface.md](RESEARCH_bias_interface.md) §12.4（U-9 B-A 边界表）
> **代码证据时点**: HEAD `3af285a`（E1 2026-11-11）
> **状态**: Step 1-2 完稿 + Step 2 Review 通过（§8）+ **RULE-5 异构复审 pass**（§9：0 P1/P2，3 P3 登记并已回写，3 观察）；待进 Step 3

---

## 1. 背景与目标

TD-1 将数据层登记为「已规划未执行的迁移」：`core/data.py` 的 `DataManager`（V1，生产主力）与 `core/data_v3.py` 的 `DataLoaderV3`（V3）并存。P-012 的 U-9 裁决（B-A）只交付了 `DataProvider` 端口 + `PklDataProvider` 适配器 + 契约测试，并把**消费方迁移、两实现合并、旧实现删除**明确划归 P-004（[RESEARCH_bias_interface.md](RESEARCH_bias_interface.md) §12.4.3 边界表）。

**目标**（按边界表）：① 确定并执行 `DataManager` ↔ `DataLoaderV3` 的合并方向；② 消费方迁移；③ 删除旧实现。

**职责外（不回答）**：网络/API 数据源接入；V3 引擎取价与掩码语义（P-012 D9 已排除）；P-005 的 DuckDB 存储迁移；因子数据库结构。

**能力边界（回答不了）**：本批不引入第二套真实数据源，因此「适配器可替换性」只由 `MockDataProvider` 契约测试证明，不由生产切换证明。

---

## 2. 本仓事实（P1-P9）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **数据层实为三个构件、两种角色**：`DataManager` 是业务门面（**24 个公开成员** = 16 属性 + 8 方法，覆盖价格/辅助数据/复权/因子/资产信息/股票池状态）；`DataLoaderV3` 是 NumPy 物化器（**10 个公开成员**：`get_slice`/索引映射/`save`/`load`/资产信息），**不是门面替代品**；`DataProvider` 是 3 方法存储端口 | E3 @`3af285a` [data.py](../core/data.py) L28-181；[data_v3.py](../core/data_v3.py) L19-70；[data_provider.py](../core/data_provider.py) L18-31 |
| **P2** | **「V3 可替代 V1」不成立**：`DataLoaderV3.from_data_manager` 的**外部调用为 0**（仅定义 `:59` 与内部 `:69`）；`to_data_manager_compatible` 仅 1 处测试调用；`from_hdf5` 形参只存储、无任何读取 | E1 `Grep 'from_data_manager\|from_pandas_dataframes'`；E1 `Grep 'to_data_manager_compatible\|from_hdf5'`；E3 [data_v3.py](../core/data_v3.py) L30-38、L210 |
| **P3** | **端口覆盖不足**：`DataProvider` 仅 `load_price(kind)` / `load_aux(kind)` / `load_universe()`，缺 `returns`、`load_factor`、`get_adj_price`、`universe_status`、`data_dir`；且**生产引用为 0**（唯一 importer 是 `tests/test_contract_conformance.py:10`） | E3 [data_provider.py](../core/data_provider.py) L18-31；E1 `Grep 'core\.data_provider\|PklDataProvider'` = 3 行（含自身 docstring） |
| **P4** | **消费面已扩大**：以 `DataManager` 为词元的引用（含 `IDataManager`/`AbstractDataManager`/`MockDataManager`）共 **170 处 / 35 文件** = 生产 **62 / 16** + 测试 **108 / 19**（TD-1 报告 2026-08-15 读数为 38 = 12 + 26） | E1 `Grep -c 'DataManager' --glob '*.py'`（§4 读数 A/B） |
| **P5** | **隐性耦合三处**：① `engine_v2.py:610` 以 `getattr(dm, "universe_status", {})` 消费，协议无此成员；② `agent_framework.py:967/977` 直接用 `dm.data_dir` 拼 `industry.pkl`/`mktcap.pkl`，绕过加载器；③ `filter/universe_filter_clean.py` 内 `dm.*` 访问 **38 行（53 处匹配）**，其中辅助/价格字段 **15 处**（`suspend`/`st`/`industry`/`mktcap`/`open`/`close`/`adj_factor`），依赖 P-010/P-012 的语义——**R5 复审更正**：初稿「38 处 / 18 处」为行/处混用与手工计数偏差 | E3 @`3af285a` [engine_v2.py](../core/engine_v2.py) L610；[agent_framework.py](../agents/agent_framework.py) L967/977；[universe_filter_clean.py](../filter/universe_filter_clean.py) L173-361 |
| **P6** | **I/O 逻辑重复但语义分层不同**：`DataManager._load_price_data`（`:268-304`）做「cfg 文件映射 → `read_pickle` → DatetimeIndex → 日期过滤 → 列序对齐 → 缓存」；`PklDataProvider.load_price`（`:60-64`）只做「默认文件映射 → `read_pickle`」；**安全默认值只在 DataManager**（`:336-368`：suspend/st 缺失→全 0；industry/mktcap 缺失→None），provider 对所有缺失一律 None | E3 [data.py](../core/data.py) L253-311、L313-370；[data_provider.py](../core/data_provider.py) L60-73 |
| **P7** | **协议面 8 vs 实现面 24，且两处签名不一致**：`IDataManager` 仅声明 8 成员；`tests/test_contract_conformance.py:27-36` 以 `EXPECTED_MEMBERS` 锁死集合。**R5 复审补发现 + DESIGN 期补核**：① 协议 `get_adj_price(..., adjustment=...)`（interfaces.py L51）≠ 实现 `get_adj_price(..., adjustment_type=...)`（data.py L465-466）；② 协议 `load_factor(name)`（interfaces.py L63）≠ 实现 `load_factor(factor_file)`（data.py L521）。按协议关键字调用均会 TypeError；生产全为位置调用未爆，mypy 对方法形参名不敏感故 0 errors | E3 [interfaces.py](../core/interfaces.py) L25-88、L437-457；[test_contract_conformance.py](../tests/test_contract_conformance.py) L26-36；[data.py](../core/data.py) L465-466、L521 |
| **P8** | **构造点 6 处**：`factory.py:123`（唯一工厂 lambda）、`engine_v2.py:205`（缺省回退 new）、`agent_framework.py:1219`、`multi_strategy_engine.py:510`、`examples/full_backtest_demo.py:255`、`examples/full_backtest_2020_2026_simple.py:69` | E1 `Grep 'DataManager\('` 后人工筛除协议/ABC/`Mock`/docstring 匹配（§4 读数 C） |
| **P9** | **回归护栏充足**：`pytest tests` **635 passed**（`MPLBACKEND=Agg`）+ **7 份 golden 基线（G1-G7；G1-G6 由 P-013、G7 由 P-014 落地，`tests/test_golden_baseline.py` 参数化重放）**；无测试断言 DataManager 的「文件不存在」错误文案（改文案风险低） | E1 `pytest`（§4 读数 D）；E1 `Grep '价格文件不存在\|未知的价格类型'` = 0 测试命中；E3 `Glob tests/golden/*.json` = G1-G7 |

---

## 3. 外部来源

**本批不新增外部检索**。沿用的端口-适配器依据为 P-012 已落档锚点：**A39**（端口-适配器，核心只依赖端口）、**A40**（Qlib `DataLoader` 抽象 + Handler 分层）、**A41**（LEAN 配置切换数据源与 Time Frontier），出处见 [RESEARCH_bias_interface.md](RESEARCH_bias_interface.md) §12.4.1。

按 SPEC_PROCESS v1.7.2 §契约取证字段形态：**F1 / F2 / F3 = N/A（本批无新外部来源）**；**F4 = N/A（新增外部引用 0 条 < 3）**；**F5 = N/A（无外部契约变更）**。

---

## 4. 本轮 E1 取证（2026-11-11 @`3af285a`）

| 读数 | 命令 | 结果 |
|------|------|------|
| **A（引用总量）** | `Grep -c 'DataManager' --glob '*.py'` | **170 处 / 35 文件**；生产 **62 / 16**（`core` 33 = data 1 + data_v3 6 + data_provider 1 + engine_v2 8 + interfaces 4 + factory 11 + factor 2；`agents` 16；`examples` 10；`batch_backtest` 2；`web` 1）；测试 **108 / 19** |
| **B（V3 引用）** | `Grep -c 'DataLoaderV3' --glob '*.py'` | **72 处 / 14 文件**：生产 26 / 5（`data_v3.py` 14、`engine_v3_vector.py` 5、`tools/benchmark.py` 3、`export_case.py` 2、`core/__init__.py` 2 注释）；测试 46 / 9 |
| **C（构造点）** | `Grep 'DataManager\(' --glob '*.py'` | 真实构造：生产 **6 处**（P8）；测试 **37 处 / 13 文件**（40 词元命中 − `MockDataManager(` 2 − `_FakeDataManager(` 1；`IDataManager(` 0）——**R5 复审更正**：初稿两版（27/13、27/10）均未复现 |
| **D（基线）** | `pytest tests`（项目解释器 3.12.10，`MPLBACKEND=Agg`） | **`635 passed, 152 warnings in 64.22s`**（本批复跑，@`3af285a`） |
| **E（死 API）** | `Grep 'from_data_manager\|to_data_manager_compatible\|from_hdf5'` | `from_data_manager` 外部调用 **0**；`to_data_manager_compatible` 调用方 **1**（`tests/test_data_v3_compatibility.py:78`）；`from_hdf5` 仅 `:30/:35/:38` 形参存储 |

> 读数 A 的「生产/测试」拆分口径：路径以 `tests/` 开头记为测试，其余记为生产（含 `examples/`、`web/`、`batch_backtest/`）。

---

## 5. 成员级消费方图（仅生产，@`3af285a`）

| `DataManager` 成员 | 生产消费方（file:line） | 备注 |
|--------------------|--------------------------|------|
| `trade_dates` | `engine_v2` 247/318/319/334/898；`factory` 241；`filter` 184/195/261/265/273/276/289/295/320/344/361/392/435/476；`agents` 1249/96/145/154/225/272/708/840/904/914；`examples` ×6 | 最高频成员 |
| `stock_codes` | `engine_v2` 899；`filter` 173/184/196/261/265/273/276/289/295/317/320/330/344/361/392/435/476/538/580；`agents` 1220/1222 | 次高频 |
| `n_stocks` | `engine_v2` 261；`factory` 243；`agents` 98 | |
| `returns` | `engine_v2` 274/732；`agents` 110 | 引擎逐日净值口径 |
| `load_factor` | `engine_v2` 293；`agents` 333/392/476/532/557/951；`examples` | 协议内成员 |
| `get_adj_price` | `engine_v2` 351/352；`agents` 185/302/374/435/436/736/867/960/1320-1323/1420 | P-012 三口径消费点 |
| `get_data_info` | `engine_v2` 1166 | 报告字段 |
| `universe_status` | `engine_v2` 610（`getattr`） | **协议外**隐性耦合 |
| `suspend` / `st` | `filter` 180/181/210/256/258/280/281 | 掩码语义 |
| `industry` / `mktcap` | `filter` 337-355；`factor` 315/316/328/329 | 过滤 + 中性化 |
| `open` / `close` / `adj_factor` | `filter` 199/200/202/210 | 涨跌停判定 |
| `universe` | `data_v3.py` 123-126 | 仅 `from_data_manager` 死路径 |
| `data_dir` | `agent_framework` 967/977 | 绕过加载器直读 pkl |
| `get_asset_info` / `configure_asset(s)` | **生产 0**（仅测试） | 多资产能力未接线 |
| `preload_data` / `clear_cache` | **生产 0**（仅测试） | |

`DataLoaderV3` 成员消费方：`price_data`/`mask_data`/`factor_data` → `engine_v3_vector` 272-374；`get_slice`/`get_date_index`/`get_stock_index` → `engine_v3_vector`、测试；`save`/`load` → 测试；`from_data_manager` → **0 生产**。

---

## 6. 方案矩阵（7 维，按 SPEC_PROCESS §11.8）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **M-A 门面保留 + 端口注入（推荐）** | `DataManager` 保留为唯一业务门面，构造时注入 `DataProvider`（缺省 `PklDataProvider`，`file_map` 由 `cfg` 生成）；价格/辅助/股票池读取改走端口；日期过滤、列对齐、缓存、安全默认值仍留门面；删除 `DataLoaderV3` 三个死 API | 中（1 文件核心改动 + 1 文件删码） | 中-高：**单一 I/O 实现**，不改变任何消费方 | 低 | **高**（对外 API 零变化） | 高 | 1 批 | 长期 |
| M-B 端口扩全 + 消费方迁移 | 把 `returns`/`load_factor`/`get_adj_price`/`universe_status`/`data_dir` 全部纳入端口，`engine_v2`/`filter`/`factor`/`agents` 改依赖端口，`DataManager` 降为默认实现 | 高（6 生产文件 + 19 测试文件） | 高：真正的可替换数据源 | 中 | **低**（大面积改签名） | 中 | 多批 | 长期 |
| M-C `DataLoaderV3` 取代 `DataManager` | V2 引擎改用 NumPy 数组接口 | 极高 | 负：需补因子加载/复权/辅助数据/资产信息 | 高 | **极低** | 低 | — | — |
| M-D 维持现状 + 文档标注 | 只更正 TD-1/ARCHITECTURE 表述 | 0 | 低 | 高（双轨继续） | 高 | 低 | 0 | 债务不变 |

**判定**：

- **M-C 证伪**：`DataLoaderV3` 缺 5 类能力（P1/P3），且其唯一的 DataManager 兼容入口 `from_data_manager` 零调用（P2）——「合并到 V3」在现有 API 面不可达。
- **M-B 不作为首批**：一次性改 6 生产 + 19 测试文件，与 P-012 六层归因「每次行为变更单独批次」的纪律冲突，且行为差异无法归因。
- **M-A 路线首批为 B1**：只合并 I/O 实现，不动消费方；以 635 passed + 7 份 golden 数值不变作为零行为判据。
- **M-D 否决**：不满足 P-004 判据（消费方迁移 / 旧实现删除）。

**建议批次切分**（供 DESIGN 采纳）：

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1** | `DataManager` 注入 `DataProvider`；价格/辅助/股票池读取改走端口；安全默认值/对齐/缓存留门面 | 零行为 | `635 passed` + golden **G1-G7** 数值不变 |
| **B2** | 删除 `DataLoaderV3` 死 API（`from_data_manager`/`_load_from_data_manager`/`to_data_manager_compatible`/`from_hdf5`）；`agent_framework` 两处 `data_dir` 直读改走端口 | 零行为 | 同上 + 死 API 引用归零 |
| **B3** | 协议治理：`IDataManager` 与实现面对齐（至少纳入 `universe_status`；多资产成员按是否接线决定去留）；消费方类型标注迁移到协议 | 零行为 | 契约测试扩展通过；`mypy` 0 |
| **B4（可选）** | 端口扩全（M-B 的存储侧），把 `returns`/`get_adj_price` 派生逻辑抽为纯函数供端口复用 | 零行为 | 同上 |

> 「删除旧实现」在本批语境下 = 删除重复 I/O 路径与死 API；**删除 `DataManager` 类本身不在可达范围**（P1/P3），如需最终移除须先执行 M-B 并把 24 个公开成员逐个迁走——登记为 U-P004-1。

---

## 7. 未决项登记（四元块）

- **U-P004-1 合并终局方向（门面保留 vs 类移除）**
  - 判据：若 `DataManager` 的 24 个公开成员全部可由端口 + 纯函数表达，且消费方改依赖协议后测试全绿，则可移除类；否则保留为门面
  - 触发条件：B1-B3 落地后（Step 9 完成）
  - 当前倾向：**保留门面**（M-A）；类移除需单独批次，不并入 P-004
  - 证据等级：E3（P1-P3 能力缺口）

- **U-P004-2 端口边界（存储读取 vs 派生计算）**
  - 判据：`MockDataProvider` 能否在不实现 `returns`/复权的情况下支撑 `engine_v2` 契约测试
  - 触发条件：Step 3 DESIGN
  - 当前倾向：端口只管**存储读取 + 原始快照**；`returns`/`get_adj_price` 等派生留门面（避免端口变成第二个门面）
  - 证据等级：E3（P3/P6）

- **U-P004-3 `DataLoaderV3` 死 API 处置**
  - 判据：外部调用归零实证（已达成：`from_data_manager` 0、`to_data_manager_compatible` 1 测试、`from_hdf5` 0）
  - 触发条件：B2 实施
  - 当前倾向：删除三个入口；`to_data_manager_compatible` 的测试改为断言删除（或迁移到新契约）
  - 证据等级：E1（§4 读数 E）

- **U-P004-4 agents 越界直读 `data_dir`**
  - 判据：`agent_framework.py:967/977` 是否纳入 B2
  - 触发条件：B2 设计
  - 当前倾向：纳入 B2（改走 `provider.load_aux`，语义等价：缺失返回 None 时保持现有跳过逻辑）
  - 证据等级：E3（P5）

---

## 8. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明：与正文同会话，无第二视角；RULE-5 复审按惯例留待用户指派（若要求）。

- [x] 引用可解析：全部为仓内文件 + `@3af285a` 时点行号（`data.py` L253-311 / `data_v3.py` L19-70 / `data_provider.py` L18-31 / `engine_v2.py` L610 / `agent_framework.py` L967-977）
- [x] 无未标注推测：P1-P9 均有 E1 命令读数或 E3 行号；§6 的「零行为」标注为**待 Step 9 实测**的判据，不是既成结论
- [x] 门禁 (a) FALSIFIED：**有 1 项**——TD-1 报告「`DataLoaderV3` 是按 V1 替代品设计的，接口兼容设计已就位」被 §4 读数 E 证伪（`from_data_manager` 外部调用 0；V3 无因子/复权/辅助数据能力）。该表述需在 DESIGN/IMPL 中更正，并回写 TD-1 注记
- [x] 门禁 (b) CONFLICT / STEP_GAP_OPEN：**有 1 项**——P-012 §12.4.3 边界表写「P-004 负责 `DataManager` ↔ `DataLoaderV3` 合并」，但合并到 V3 不可达（M-C 证伪）；本批按 M-A 重新定义为「I/O 实现合并 + 门面保留」，属对边界表的**方向细化**，不推翻 U-9 裁决。已登记 U-P004-1
- [x] 门禁 (c) 阻断性断言双源：P2（V3 不可替代）**双证**（E1 零调用 + E3 16 vs 30 成员能力差）；P6（默认值只在门面）**双证**（E3 两处实现 + P-010 测试 `test_data_aux_defaults.py`）
- [x] 门禁 (d) 假设区：唯一假设「M-A 零行为」已转为 B1 验收判据（635 passed + golden 逐字节），Step 9 实测；不预填

**Step 2 Review 结论：通过**（含 1 项 FALSIFIED 表述更正、1 项边界方向细化，均不阻断）。可进入 Step 3 DESIGN。

---

## 9. RULE-5 异构复审（用户指派 2026-11-11）

**复审基座声明**：复审方 GLM-5.3-Flash ≠ 调研作者 DeepSeek-V4.1-Flash（异构性成立）。复审权限单向：只标记问题，不改判作者结论。复审对象 = 本文档 Step 1-2 稿（基线 `3af285a`，复审时点工作区含本文档未提交稿）。

### 9.1 E1 独立重放

| # | 项 | 读数 | 与初稿 |
|---|----|------|--------|
| 1 | git 基线 | HEAD = `3af285a`；工作区 = 本文档未提交稿 + PROGRESS §3.22 | 一致（复审对象为未提交稿，已在声明注明） |
| 2 | DataManager 词元 | **170 处 / 35 文件**（count 独立重放） | ✅ 复现 |
| 3 | 生产/测试拆分 | 生产 62 / 16（examples 10 + agents 16 + batch 2 + core 33 + web 1）+ 测试 108 / 19 | ✅ 复现 |
| 4 | DataLoaderV3 词元 | **72 处 / 14 文件** | ✅ 复现 |
| 5 | 死 API | `from_data_manager` 外部调用 0；`to_data_manager_compatible` 测试调用 1；`from_hdf5` 仅 `:30/:35/:38` | ✅ 复现 |
| 6 | pytest（Agg） | **`635 passed, 152 warnings in 78.45s`**（独立复跑） | ✅ 计数一致，时长漂移正常 |
| 7 | filter 辅助字段 | universe_filter_clean.py 七字段 **15 行/15 匹配**；`dm.*` 全量 **38 行 / 53 匹配** | ❌ 初稿「38 处 / 18 处」→ 已更正（F-R5-P004-3） |
| 8 | 测试构造点 | `DataManager(` 词元 40 处/15 文件 − Mock 2 − Fake 1 = **37 处 / 13 文件** | ❌ 初稿「27 处/10 文件」→ 已更正（F-R5-P004-1） |

### 9.2 E2/E3 静态取证（盲区补扫）

| # | 发现 | 证据 |
|---|------|------|
| 1 | **协议/实现签名不一致**（初稿 P7 盲区）：协议形参 `adjustment`（interfaces.py L51）≠ 实现形参 `adjustment_type`（data.py L465-466）；ABC `AbstractDataManager`（L452）沿协议名；关键字调用会 TypeError，生产全为位置调用未爆；mypy 对方法形参名不敏感故 0 errors | E3 双文件行号；`Grep 'AbstractDataManager'` = 定义 1 处 |
| 2 | **`AbstractDataManager` 零消费方**：全仓仅 interfaces.py L437 定义，无子类无实例化——死代码 | E1 `Grep 'AbstractDataManager' --glob '*.py'` = 1 行 |
| 3 | **web 1 处词元为 docstring 架构图**（01_Overview.py L96），非代码引用——P4 词元口径已声明故不算错；生产 62 含 1 处 docstring 命中 | E3 Read L94-98 |
| 4 | filter/ 下 custom/extended/industry/na_factor/base 等非 clean 文件**无任何 data_manager 依赖、无生产 import**（疑似孤儿，属 TD-5 范畴）——不影响本批消费方图 | E1 `Grep 'from filter\.(base\|custom\|…)'` = 仅 `__init__.py` 引 prefix/market_cap 函数 |

### 9.3 E4 结论（3 P3 + 3 观察，均不阻断）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-R5-P004-1** | P3 | §4 读数 C 测试构造点「27 处 / 10 文件」（及更早版「27 / 13」）均未复现，实测 **37 处 / 13 文件**——「人工筛除」过程有误 | ✅ 已回写 §4 读数 C |
| **F-R5-P004-2** | P3 | **P7 漏签名核对**：`IDataManager.get_adj_price` 协议形参 `adjustment` ≠ 实现形参 `adjustment_type`（关键字调用 TypeError）；契约测试 `EXPECTED_MEMBERS` 只锁成员名不锁签名 | ✅ 已回写 P7；纳入 **B3 协议治理**（以实现签名为准修订协议 + 契约测试锁签名，同 P-012 D7 `execute_order` 先例） |
| **F-R5-P004-3** | P3 | P5-③ filter 计数「38 处 / 18 处」为行/处混用（实测 38 行 / 53 匹配；辅助字段 15 处） | ✅ 已回写 P5-③ |
| （观察 1） | — | `AbstractDataManager`（interfaces.py L437）零消费方死代码；初稿仅「筛除」未登记待删 | 建议 B2 处置清单纳入（连同其 docstring） |
| （观察 2） | — | 生产 62 词元中 1 处为 web docstring 架构图命中（01_Overview.py L96）；精确代码引用 61 处 | 词元口径已声明，无需改数；DESIGN 引用时注明口径 |
| （观察 3） | — | filter/ 非 clean 模块（custom/extended/industry/na_factor/base）无生产 import，疑似孤儿——**TD-5 范畴，不并入 P-004** | 登记；避免 B2 越界删除 |

> 复核确认：初稿三大主结论（FALSIFIED 判定 P2、M-C 证伪、M-A 路线）经独立重放全部成立；U-P004-1~4 四元块无事实错误。P3 三项均为计数/签名精度问题，已回写，不影响 Step 3 启动。

### 9.4 复审结论

**pass（0 P1 / 0 P2 / 3 P3 登记并已回写 + 3 观察）**。E1 八项独立重放中六项复现、两项计数更正；E2/E3 补扫发现协议签名不一致（F-R5-P004-2，转入 B3）与 `AbstractDataManager` 死代码（观察 1，转入 B2 清单）。Step 3 DESIGN 须吸收：① B2 清单加 `AbstractDataManager`；② B3 契约测试从「成员集合」升级为「成员 + 签名」。
