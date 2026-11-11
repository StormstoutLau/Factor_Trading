# CHECKLIST：P-004 数据层统一（B1 端口注入 / B2 死 API 删除 / B3 协议对齐）

> **批次**: P-004 · T1
> **上游**: [IMPL_p004_data_layer_unification.md](IMPL_p004_data_layer_unification.md)（T-1~T-7 / V1-V8）；[DESIGN_p004_data_layer_unification.md](DESIGN_p004_data_layer_unification.md)（D1-D6 / I1-I6）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 7 完稿（零预填）→ Step 9 实施完成（24/24 ✅，§2）→ **Step 10 ADD 审计通过（§9，P1=P2=P3=0）**；签字表 §10

---

## 1. 验收项

### A 组：B1 端口注入（D1 / D2 / I2 / I3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | provider 构造与单一映射来源（D2） | 静态：存在 `_build_provider`；`price_map` 由 cfg 五字段生成；`aux_map` **过滤 falsy**；`_PRICE_KINDS` 被 `_load_price_data` / `preload_data` / `_build_provider` 三处引用，无第二份 kind 列表 | ✅ E3 @`bb50009`：[data.py](../core/data.py#L80-L109)；`price_map = {kind: getattr(config, f"{kind}_file") for kind in _PRICE_KINDS}`（L87）+ `if name` 过滤；`_PRICE_KINDS` 定义 L27 / 生成 L87 / 校验 L295 / 循环 L678（三处引用） |
| A-2 | 默认配置可构造且 mktcap 不崩（F-D-R5-P004-1，V3） | 运行：`DataManager(BacktestConfig(data_dir=<含 close 的 tmp>))` → 不抛 `ValueError`；`dm.mktcap is None`；`dm.industry is None`；`dm.suspend` / `dm.st` 形状正确且全 0 | ✅ E1：探针 → `mktcap is None: True` / `industry is None: True` / `suspend: (2, 2) 0` / `st: (2, 2) 0`；`aux_keys: ['industry','st','suspend']`（mktcap 已过滤）；`test_data_aux_defaults` **4 passed** |
| A-3 | 价格读取走端口且文案保留（T-2，V1） | 静态：`_load_basic_data` / `_load_price_data` 内无 `pd.read_pickle`、无 `close_path.exists()`；未知 kind 仍抛 `未知的价格类型: …`；运行：五价格属性可读 | ✅ E3 @`bb50009`：[data.py](../core/data.py#L232-L246) 仅 `self._provider.load_price("close")`；[L274-L304](../core/data.py#L274-L304) 无 `read_pickle`/`exists()`；E1 探针 → `ValueError text: 未知的价格类型: volume`；五价格 `[(3, 2)] × 5` |
| A-4 | 辅助数据 cfg 守卫与默认值（T-3，I3） | 静态：suspend/st/industry/mktcap 四分支均有 `if self.cfg.*_file:` 守卫后才调 `load_aux`；运行：缺失语义与 P-010 一致（suspend/st 全 0、industry/mktcap None） | ✅ E3 @`bb50009`：[data.py](../core/data.py#L353-L397) 四分支逐 `if self.cfg.*_file:` 守卫；E1 默认值读数同 A-2 |
| A-5 | 归一化与股票池（T-4） | 静态：`_load_and_align_data(self, data, label="aux")` 无 `pd.read_pickle`；`universe` 经 `self._provider.load_universe()`；运行：幂等 guard 生效（连续 3 次访问 industry，读盘计数 = 1） | ✅ E3 @`bb50009`：[data.py](../core/data.py#L391) 签名与无读盘；[L193-L200](../core/data.py#L193-L200) `universe` 走端口；E1 `test_auxiliary_load_is_idempotent` 通过（计数 = 1） |
| A-6 | DI 注入可用（T-7，V7） | 运行：`test_data_manager_accepts_injected_provider` 通过；注入自定义 provider 后 `stock_codes` 来自注入数据 | ✅ E1：`test_data_manager_accepts_injected_provider` 通过；独立探针 → `DI stock_codes: ['A', 'B']` |

### B 组：B2 死 API 删除（D3 / I6）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | V3 四个死 API 归零（V6） | `Grep` 全仓 `*.py`：`from_data_manager` / `_load_from_data_manager` / `to_data_manager_compatible` / `from_hdf5` **0 代码命中** | ✅ E1：`Grep` 四词元 `--glob '*.py'` = **0 命中** |
| B-2 | `AbstractDataManager` 删除（V6） | `Grep 'AbstractDataManager' --glob '*.py'` = **0 命中**（含定义与引用） | ✅ E1：`Grep 'AbstractDataManager' --glob '*.py'` = **0 命中**（含定义与引用） |
| B-3 | 兼容测试同步删除 | `tests/test_data_v3_compatibility.py` 无 `test_to_data_manager_compatible`；文件其余用例保持并通过 | ✅ E1：该文件 **5 passed**（6 − 1）；`test_to_data_manager_compatible` 已不存在 |
| B-4 | 删除后无未使用导入 / 构造不破 | `black --check` 无变更；`mypy core` 0 errors；`DataLoaderV3.load()`（`cls()` 无参）仍可用 | ✅ E1：`black` 110 unchanged；`mypy` 36 files 0 issues；探针 `DataLoaderV3.load(p)` → `n_dates=2` |

### C 组：B3 协议对齐（D4 / I6 / V7）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | `get_adj_price` 形参一致 | 静态：协议与实现均为 `(self, price_type, adjustment_type)`；默认值均 `price_type="close"` / `adjustment_type="hfq"` | ✅ E3 @`bb50009`：[interfaces.py](../core/interfaces.py#L56) 与 [data.py](../core/data.py#L483) 均 `(self, price_type: str = "close", adjustment_type: str = "hfq")`；E1 `test_protocol_signatures` 通过 |
| C-2 | `load_factor` 形参一致 | 静态：协议与实现均为 `(self, factor_file)` | ✅ E3：[interfaces.py](../core/interfaces.py#L70) 与 [data.py](../core/data.py#L539) 均 `(self, factor_file: str)` |
| C-3 | `universe_status` 纳入协议 | 静态：`IDataManager` 含 `universe_status` 属性；`EXPECTED_MEMBERS[IDataManager]` 含 `"universe_status"` | ✅ E3：[interfaces.py](../core/interfaces.py#L47) 属性已声明；`EXPECTED_MEMBERS` 已含之，`test_protocol_members` 通过 |
| C-4 | 四签名契约测试 | 运行：`EXPECTED_SIGNATURES` 覆盖 `get_adj_price` / `load_factor` / `get_data_info` / `get_asset_info`；`test_protocol_signatures` 通过 | ✅ E1：四签名全覆盖，`test_contract_conformance.py` **6 passed**（含 `test_protocol_signatures`） |
| C-5 | 关键字调用可用（F-R5-P004-2 回归） | 运行探针：`dm.get_adj_price("close", adjustment_type="hfq")` 与 `dm.load_factor(factor_file="x.pkl")` 均不抛 `TypeError` | ✅ E1：`get_adj_price("close", adjustment_type="hfq")` → `(2, 2)`；`load_factor(factor_file="factor_x.pkl")` → `(1, 2)`，均无 `TypeError` |

### D 组：零行为回归与门禁（I1 / I4 / I5 / V1 / V2 / V4 / V5 / V8）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 全量测试终态（I1，V1） | `pytest tests`（Agg，项目解释器 3.12.10）= **636 passed**；B1 后持平 635、B2 后 634、B3 后 636（逐批实读） | ✅ E1：B1 `635 passed`（80.59s）→ B2 `634 passed`（66.52s）→ B3 **`636 passed`**（74.25s），均 `MPLBACKEND=Agg` |
| D-2 | golden 全过（I5，V2） | `tests/test_golden_baseline.py` 参数化 **G1-G7** 7/7 通过（数值/计数） | ✅ E1：该文件 **9 passed**（G1-G7 参数化 7 + 集合完整性/schema 2） |
| D-3 | 复权口径不变（I4，V4） | `test_adjustment`(11) + `test_adjustment_semantics`(2) = 13 项通过 | ✅ E1：`test_adjustment` **11** + `test_adjustment_semantics` **4** = **15 passed**（**Step 9 实读更正**：原 DoD 写 2 / 合计 13，实际 4 个用例） |
| D-4 | 门禁（V5） | `mypy --explicit-package-bases core` = 0 errors；`black --check core tests` 无变更 | ✅ E1：`black` → `110 files would be left unchanged`；`mypy` → `Success: no issues found in 36 source files` |
| D-5 | 外部对拍回归（V8，可选） | `verify_p015.py` 五 case → `28 断言（失败 0）+ 豁免 1`，exit 0 | ✅ E1：`--case-dir B1..B5` → `共 28 项断言（失败 0 项）+ 豁免登记 1 项`，**exit 0** |

### E 组：文档与治理

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 批次登记 | `PROGRESS.md` §3.22 Step 9 记录 + `CHANGELOG.md` Fixed 条目 | ✅ `PROGRESS.md` §3.22 已追加 Step 9 行；`CHANGELOG.md` `Fixed` 已加 P-004 条目 |
| E-2 | 变更面受控 | `git diff --stat` 仅含 `core/data.py`、`core/data_v3.py`、`core/interfaces.py`、`tests/test_contract_conformance.py`、`tests/test_data_v3_compatibility.py`、`tests/test_data_aux_defaults.py`（1 行 wrapper）+ docs；无 `.github/` | ✅ E1：`git diff --stat 6ab9561..HEAD`（实施三提交）= 上述 **6 文件**（`+134/−154`），无 `.github/`；docs 回写见本批后续提交 |
| E-3 | 外部锚点可核（F1-F4） | IMPL §1：≥3 条外部引用均带 ID/日期/版本 + 验证表；未验证项标 `未验证` | ✅ IMPL §1：E1-E7 七条均带 ID/发布日/版本 + 引用验证表；E8 标 `未验证` 且声明不用于结论 |
| E-4 | 提交切分与回退 | B1 / B2 / B3 三个独立提交；任一可单独 `git revert` | ✅ E1：`3ddc895`（B1）/ `8b72145`（B2）/ `bb50009`（B3），三批文件面无重叠（B1 data.py+aux 测试、B2 data_v3+interfaces+兼容测试、B3 interfaces+契约测试） |

---

## 2. 统计

- 总数：**24 项**（A6 / B4 / C5 / D5 / E4）
- 状态：**24/24 ✅**（逐项绑证据，RULE-2 逐项核对；Step 9 实读回填）
- 发现：**P1 = 0 / P2 = 0 / P3 = 1**（F-S9-P004-1：V4/D-3 的 `test_adjustment_semantics` 计数由 2 更正为实读 4，合计 13→15；已同步 DESIGN §5 V4 / IMPL §4 V4 与本表）
- 覆盖映射：D1→A-2/A-3；D2→A-1/A-3/A-4；D3→B-1~B-4；D4→C-1~C-5；D5→（出界，无验收行）；D6→E-3；I1→D-1；I2→A-1/A-3；I3→A-2/A-4；I4→D-3；I5→D-2；I6→B-1~B-2/C-4

---

## 3. 后续章节

Step 8 一致性 Review（§8）、Step 10 ADD 审计（§9）、RULE-5 复审（如需，§9.4）、签字表（§10）在对应步骤完成后追加；Step 9 实施记录与 F5 红/绿读数回填 [IMPL §8](IMPL_p004_data_layer_unification.md)。

---

## 8. Step 8 一致性 Review

**执行时点**: 2026-11-11，四文档完稿后的独立 pass；**[RULE-4] 自查（单视角）**；代码证据时点 HEAD `c4aad0b`（其后工作区仅 docs 变更）。

### 8.1 机械校验读数

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | **14 个唯一相对链接目标全部存在，0 broken**——docs 6（[PROGRESS](PROGRESS.md)、[RESEARCH_tech_debt_cleanup](RESEARCH_tech_debt_cleanup.md)、[RESEARCH_bias_interface](RESEARCH_bias_interface.md)、[RESEARCH_p004](RESEARCH_p004_data_layer_unification.md)、[DESIGN_p004](DESIGN_p004_data_layer_unification.md)、[IMPL_p004](IMPL_p004_data_layer_unification.md)）+ `../core` 5（`data.py` / `data_v3.py` / `data_provider.py` / `interfaces.py` / `engine_v2.py`）+ `../agents/agent_framework.py` + `../filter/universe_filter_clean.py` + `../tests/test_contract_conformance.py` |
| 预填检查（RULE-1） | 验收区 24 项 = **24 处 `[待 Step 9]`**；全文 `✅` 仅 L5 规则声明行本身（合法；§8 本节的 ✅ 属校验读数，非验收实测列） |
| ID 引用闭环 | U-P004-1~4 ×7、F-D-R5-P004-1 ≥3、F-R5-P004-2 ≥3、`_PRICE_KINDS` ×4（RESEARCH/DESIGN/IMPL/CHECKLIST）、G1-G7 ×4、D1-D6 / I1-I6 / T-1~T-7 / V1-V8 均跨文档 ≥2 处；0 悬空 ID |

### 8.2 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH §6 B1 → DESIGN §4.1 → IMPL T-1~T-4 → CHECKLIST A 组 | 一一对应（A-1~A-6） |
| RESEARCH §6 B2① 死 API → DESIGN §4.2 → IMPL T-5 → CHECKLIST B 组 | 一一对应（B-1~B-4） |
| RESEARCH §6 B2② agents 直读 → DESIGN D5 **主动收窄出界**（B4 承接） | 显式登记（§1 出界清单）；CHECKLIST 无对应行 = 一致 |
| RESEARCH §6 B3① 协议对齐 → DESIGN D4 → IMPL T-6~T-7 → CHECKLIST C 组 | 一一对应（C-1~C-5） |
| RESEARCH §6 B3②③ 多资产成员去留 / 消费方类型标注迁移 → DESIGN | **原未显式裁决**（F-S8-P004-2）→ Step 8 补登 DESIGN §1 出界清单（B4 承接） |
| DESIGN D1-D6 → CHECKLIST | D1→A-2/A-3；D2→A-1/A-3/A-4；D3→B-1~B-4；D4→C-1~C-5；D5→出界（§2 已注「无验收行」）；D6→E-3 |
| DESIGN I1-I6 → CHECKLIST | I1→D-1；I2→A-1/A-3；I3→A-2/A-4；I4→D-3；I5→D-2；I6→B-1~B-2/C-4 |
| DESIGN V1-V8 → CHECKLIST | V1→D-1；V2→D-2；V3→A-2；V4→D-3；V5→D-4；V6→B-1/B-2；V7→A-6/C 组头；V8→D-5 |

### 8.3 一致性发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P004-1 | P3 | IMPL §4 验证项 V 编号与 DESIGN 同 ID 异义（IMPL 初稿：契约=V5 / 门禁=V7+V8 / 对拍=V9；DESIGN 权威：门禁=V5 / 契约=V7 / 对拍=V8），CHECKLIST 引用随之漂移 + D 组头残留「V1-V4 / V7-V9」，共 6 处 | 已修：IMPL §4 重排为 **V1-V8**（与 DESIGN 同编号同义，附更正注）；CHECKLIST 头部 / A-6 / C 组头 / D-4 / D-5 / D 组头六处同步 |
| F-S8-P004-2 | P3 | RESEARCH §6 B3 的两个扩展子项（「多资产成员按是否接线决定去留」「消费方类型标注迁移到协议」）在 DESIGN 既未纳入 D4 也未入 §1 出界清单（静默收窄） | 已修：DESIGN §1 出界清单补登（Step 8 补登注），留 B4 单独取证；本批零行为判据不受影响 |
| （笔误） | P3 | IMPL T-1 标题「D5-R5 观察 1」ID 形态错误（D5 为 agents 直读决策，与 kind 白名单无关） | 已修：「DESIGN §9 观察 1」 |

**Step 8 结论：通过**（0 P1 / 0 P2 / 3 P3 均已修；可进入 Step 9 实施）。

---

## 9. Step 10 ADD 审计

**执行时点**: 2026-11-11，Step 9 完成、终态 `bb50009` 后单独执行（RULE-1 未与实施同一次写入）；**[RULE-4] 自查（单视角）**声明。审计对象 = B1/B2/B3 三实施提交（`3ddc895` / `8b72145` / `bb50009`）对照 DESIGN §4/§5 与 IMPL T-1~T-7。

### 9.1 四阶段

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 六项决策均可证伪：D1（DI 探针可构造）/ D2（`aux_keys` 过滤可观测）/ D3（grep 计数可复核）/ D4（形参名序列断言）/ D5（agents 文件不在 diff）/ D6（`G7.json` 存在且参与参数化） |
| Phase 1 完整性 | ✅ D1→`__init__` 注入 + `_build_provider`（data.py L37-46 / L80-109）；D2→`price_map`/`aux_map` 单一来源 + `_PRICE_KINDS` 三处引用；D3→六行删除清单逐项落地；D4→协议两处形参改名 + `universe_status` + `EXPECTED_SIGNATURES` 四签名；D5→`agents/` 零改动（出界登记兑现）；D6→golden 9 passed 含 G7 |
| Phase 2 忠实度 | ✅ `git diff 6ab9561..bb50009 -- core/` 与 DESIGN §4.1-§4.3 逐条对应；变更面恰为 6 文件（`+134/−154`，无 factory/engine_v2/agents/examples）；6 个生产构造点零改动（I2） |
| Phase 3 必要性 | ✅ 新增对象仅规格内四项（`_build_provider` / `_PRICE_KINDS` / `EXPECTED_SIGNATURES`+`test_protocol_signatures` / `_MockProvider`+DI 测试）；无新依赖；`from pathlib import Path` 随最后使用点（`_load_and_align_data` 形参）一并移除 |
| Phase 4 语义 | ✅ 意图 = 数据层统一且零行为——B1 全量持平 635、golden G1-G7 数值不变、V8 外部对拍 28 断言 0 失败；两处已登记异常路径漂移（价格缺失文案 → pandas 原生 `FileNotFoundError` / `industry_file` falsy → 静默 None）均无测试与现实覆盖（DESIGN §4.1/§6 声明） |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| 全量 pytest 逐批（E1） | I1 / V1 / D-1 | ✅ 635（80.59s）→ 634（66.52s）→ **636**（74.25s） |
| F5 红/绿探针 ×3（E1） | IMPL §8.2 | ✅ B1 `TypeError` / B2 `hasattr`×4 / B3 `2 failed` → 全绿 |
| 行为探针 ×6（E1） | A-2 / A-3 / A-5 / A-6 / C-5 / B-4 | ✅ 默认值四项 / DI `['A','B']` / 五价格 / 原文案 / 关键字双调用 / `load()` 往返 |
| golden 参数化（E1） | I5 / V2 / D-2 | ✅ 9 passed（G1-G7 数值/计数 + 集合完整性/schema） |
| 外部对拍（E1） | V8 / D-5 | ✅ 28 断言（失败 0）+ 豁免 1，exit 0 |
| 门禁 black/mypy（E1） | V5 / D-4 / B-4 | ✅ 110 files unchanged / 36 source files 0 issues |
| 死 API grep（E1） | I6 / V6 / B-1~B-2 | ✅ 五词元 `--glob '*.py'` = 0 命中 |
| 静态读码 @`bb50009`（E3） | A-1 / A-4 / A-5 / C-1~C-3 | ✅ 行锚逐条绑定（data.py L27/L87/L193-200/L232-246/L274-304/L353-397/L391/L483/L539；interfaces L47/L56/L70） |
| diff 全文审读（E3） | Phase 2 / E-2 变更面 | ✅ 与规格逐字对应；6 文件无超纲 |
| 盲区扫描（E4；范围 = B1 读取四路径 × B2 删除面 × B3 协议面 × 导入/docstring 残留） | 全组 | **发现 2 项观察**（§9.3），均不阻断 |
| E5 推测 | — | 无 |

### 9.3 E4 盲区观察（登记，不阻断）

| # | 发现 | 处置 |
|---|------|------|
| 观察 1 | `data_v3.py` L27 类 docstring 仍声明「5. 向后兼容 DataManager 接口」——B2 删除兼容 API 后该声明失实（DESIGN §4.2 删除清单只列 `__init__` docstring 行，未列类 docstring；属规格外文档残留，零行为影响） | 登记；留 B4/后续文档批清理（审计期不改代码，避免出格变更） |
| 观察 2 | `data.py` L14 `import pickle` 与 L16 `from functools import lru_cache` 为**删除前即存在**的未使用导入（`pickle.` / `lru_cache` 全文件 0 使用点）；本批 diff 未触及任何使用点，非本批引入；black/mypy 均不报 | 登记；属 TD-5 范畴零散清理，不并入本批 |

### 9.4 审计结论

**P1 = 0 / P2 = 0 / P3 = 0**；E4 发现 2 项观察（文档残留类，登记不阻断）。ADD 通过。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §7-§8](RESEARCH_p004_data_layer_unification.md)（RULE-4 自查·单视角） | 2026-11-11 |
| RULE-5 异构复审（调研稿） | pass | [RESEARCH §9](RESEARCH_p004_data_layer_unification.md)（复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；0 P1/P2，3 P3 登记回写） | 2026-11-11 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §8](DESIGN_p004_data_layer_unification.md)（RULE-4 自查·单视角） | 2026-11-11 |
| RULE-5 异构复审（设计稿） | pass | [DESIGN §9](DESIGN_p004_data_layer_unification.md)（0 P1，1 P2 cfg-falsy 守卫已修入 §4.1，1 P3 更正） | 2026-11-11 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §7](IMPL_p004_data_layer_unification.md)（RULE-4 自查·单视角） | 2026-11-11 |
| Step 7 验收清单 | 通过（零预填） | §1-§3（24 项，实测列全 `[待 Step 9]`） | 2026-11-11 |
| Step 8 一致性 Review | 通过 | §8（机械校验 + 对齐矩阵 8 行；F-S8-P004-1/2 + 1 笔误已修） | 2026-11-11 |
| Step 9 TDD 实施 | 完成 | [IMPL §8](IMPL_p004_data_layer_unification.md)（F5 红→绿三批 + 6 探针；CHECKLIST 24/24 ✅） | 2026-11-11 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵；E4 2 观察登记） | 2026-11-11 |
