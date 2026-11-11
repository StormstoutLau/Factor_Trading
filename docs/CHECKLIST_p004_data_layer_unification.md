# CHECKLIST：P-004 数据层统一（B1 端口注入 / B2 死 API 删除 / B3 协议对齐）

> **批次**: P-004 · T1
> **上游**: [IMPL_p004_data_layer_unification.md](IMPL_p004_data_layer_unification.md)（T-1~T-7 / V1-V8）；[DESIGN_p004_data_layer_unification.md](DESIGN_p004_data_layer_unification.md)（D1-D6 / I1-I6）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 7 完稿（零预填）

---

## 1. 验收项

### A 组：B1 端口注入（D1 / D2 / I2 / I3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | provider 构造与单一映射来源（D2） | 静态：存在 `_build_provider`；`price_map` 由 cfg 五字段生成；`aux_map` **过滤 falsy**；`_PRICE_KINDS` 被 `_load_price_data` / `preload_data` / `_build_provider` 三处引用，无第二份 kind 列表 | [待 Step 9] |
| A-2 | 默认配置可构造且 mktcap 不崩（F-D-R5-P004-1，V3） | 运行：`DataManager(BacktestConfig(data_dir=<含 close 的 tmp>))` → 不抛 `ValueError`；`dm.mktcap is None`；`dm.industry is None`；`dm.suspend` / `dm.st` 形状正确且全 0 | [待 Step 9] |
| A-3 | 价格读取走端口且文案保留（T-2，V1） | 静态：`_load_basic_data` / `_load_price_data` 内无 `pd.read_pickle`、无 `close_path.exists()`；未知 kind 仍抛 `未知的价格类型: …`；运行：五价格属性可读 | [待 Step 9] |
| A-4 | 辅助数据 cfg 守卫与默认值（T-3，I3） | 静态：suspend/st/industry/mktcap 四分支均有 `if self.cfg.*_file:` 守卫后才调 `load_aux`；运行：缺失语义与 P-010 一致（suspend/st 全 0、industry/mktcap None） | [待 Step 9] |
| A-5 | 归一化与股票池（T-4） | 静态：`_load_and_align_data(self, data, label="aux")` 无 `pd.read_pickle`；`universe` 经 `self._provider.load_universe()`；运行：幂等 guard 生效（连续 3 次访问 industry，读盘计数 = 1） | [待 Step 9] |
| A-6 | DI 注入可用（T-7，V7） | 运行：`test_data_manager_accepts_injected_provider` 通过；注入自定义 provider 后 `stock_codes` 来自注入数据 | [待 Step 9] |

### B 组：B2 死 API 删除（D3 / I6）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | V3 四个死 API 归零（V6） | `Grep` 全仓 `*.py`：`from_data_manager` / `_load_from_data_manager` / `to_data_manager_compatible` / `from_hdf5` **0 代码命中** | [待 Step 9] |
| B-2 | `AbstractDataManager` 删除（V6） | `Grep 'AbstractDataManager' --glob '*.py'` = **0 命中**（含定义与引用） | [待 Step 9] |
| B-3 | 兼容测试同步删除 | `tests/test_data_v3_compatibility.py` 无 `test_to_data_manager_compatible`；文件其余用例保持并通过 | [待 Step 9] |
| B-4 | 删除后无未使用导入 / 构造不破 | `black --check` 无变更；`mypy core` 0 errors；`DataLoaderV3.load()`（`cls()` 无参）仍可用 | [待 Step 9] |

### C 组：B3 协议对齐（D4 / I6 / V7）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | `get_adj_price` 形参一致 | 静态：协议与实现均为 `(self, price_type, adjustment_type)`；默认值均 `price_type="close"` / `adjustment_type="hfq"` | [待 Step 9] |
| C-2 | `load_factor` 形参一致 | 静态：协议与实现均为 `(self, factor_file)` | [待 Step 9] |
| C-3 | `universe_status` 纳入协议 | 静态：`IDataManager` 含 `universe_status` 属性；`EXPECTED_MEMBERS[IDataManager]` 含 `"universe_status"` | [待 Step 9] |
| C-4 | 四签名契约测试 | 运行：`EXPECTED_SIGNATURES` 覆盖 `get_adj_price` / `load_factor` / `get_data_info` / `get_asset_info`；`test_protocol_signatures` 通过 | [待 Step 9] |
| C-5 | 关键字调用可用（F-R5-P004-2 回归） | 运行探针：`dm.get_adj_price("close", adjustment_type="hfq")` 与 `dm.load_factor(factor_file="x.pkl")` 均不抛 `TypeError` | [待 Step 9] |

### D 组：零行为回归与门禁（I1 / I4 / I5 / V1 / V2 / V4 / V5 / V8）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 全量测试终态（I1，V1） | `pytest tests`（Agg，项目解释器 3.12.10）= **636 passed**；B1 后持平 635、B2 后 634、B3 后 636（逐批实读） | [待 Step 9] |
| D-2 | golden 全过（I5，V2） | `tests/test_golden_baseline.py` 参数化 **G1-G7** 7/7 通过（数值/计数） | [待 Step 9] |
| D-3 | 复权口径不变（I4，V4） | `test_adjustment`(11) + `test_adjustment_semantics`(2) = 13 项通过 | [待 Step 9] |
| D-4 | 门禁（V5） | `mypy --explicit-package-bases core` = 0 errors；`black --check core tests` 无变更 | [待 Step 9] |
| D-5 | 外部对拍回归（V8，可选） | `verify_p015.py` 五 case → `28 断言（失败 0）+ 豁免 1`，exit 0 | [待 Step 9] |

### E 组：文档与治理

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 批次登记 | `PROGRESS.md` §3.22 Step 9 记录 + `CHANGELOG.md` Fixed 条目 | [待 Step 9] |
| E-2 | 变更面受控 | `git diff --stat` 仅含 `core/data.py`、`core/data_v3.py`、`core/interfaces.py`、`tests/test_contract_conformance.py`、`tests/test_data_v3_compatibility.py`、`tests/test_data_aux_defaults.py`（1 行 wrapper）+ docs；无 `.github/` | [待 Step 9] |
| E-3 | 外部锚点可核（F1-F4） | IMPL §1：≥3 条外部引用均带 ID/日期/版本 + 验证表；未验证项标 `未验证` | [待 Step 9] |
| E-4 | 提交切分与回退 | B1 / B2 / B3 三个独立提交；任一可单独 `git revert` | [待 Step 9] |

---

## 2. 统计

- 总数：**24 项**（A6 / B4 / C5 / D5 / E4）
- 状态：**0/24**（Step 7 时点全 `[待 Step 9]`，零预填）
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
