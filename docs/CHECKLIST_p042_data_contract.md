# CHECKLIST：P-042 数据契约统一（B4 收口 + 流式契约）

> **批次**: P-042 · **T1**（Layer-1：`core/`、`tests/`；契约变更）
> **上游**: [IMPL_p042](IMPL_p042_data_contract.md)（§3 实现规格 / §4 V1-V16 / §9 Step 6 pass：1 P2 + 3 P3）；[DESIGN_p042](DESIGN_p042_data_contract.md)（D1-D7 / I1-I12 / §10 Step 4 pass：1 P2 + 3 P3）；[RESEARCH_p042](RESEARCH_p042_data_contract.md)（§6 B1-B4 / §7 S1-S10 / §13 Step 2 pass）
> **状态**: **Step 9 完成（2026-11-18），待 Step 10 ADD 审计；D4 待 CI 回填**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止预填
> **基线读数（@`9f0dbeb`）**: pytest **778** / golden **13 passed, 765 deselected** / black `core tests` **124**（全仓 **191**）/ mypy **103 files 0** / AST `except Exception` **22** / `tests/*.py` **87** / `uv lock --check` exit **0**
> **目标读数**: pytest **794** / golden 13 零重录 / black **129**（全仓 **196**）/ mypy **104 files 0** / AST **22** / `tests/*.py` **91** / uv exit **0**

---

## 1. A 组：代码变更（8 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `DataProvider` 含 4 方法：`load_price` / `load_aux` / `load_universe` / `load_factor(name: str) -> pd.DataFrame` | B1 落码 | 读码 + `dir(DataProvider)` | ✅ 读码 L18-35：4 方法；契约测试 `6 passed` |
| A2 | `PklDataProvider.load_factor`：`exists()` 检查 + 逐字 `FileNotFoundError("因子文件不存在: …")` | A1 落码 | 读码 + V2 | ✅ 读码 L82-86；V2 PASS |
| A3 | `DataManager.load_factor` 唯一读取入口为 `self._provider.load_factor`；`grep "pd.read_pickle" core/data.py` = **0** | A1/A2 落码 | grep + V3 | ✅ grep **0**；V3 PASS |
| A4 | `load_factor` 的 `except FileNotFoundError: raise` 分支存在；缺失文件不产生 `logger.error` | A3 落码 | 读码 + V2 | ✅ L621-622 命中；V2 PASS |
| A5 | `DataManager.load_aux_raw(kind)` 实现为 `return self._provider.load_aux(kind)`，缺失返回 `None` | B1 落码 | 读码 | ✅ L187-193 逐字 |
| A6 | agents 两处改为 `load_aux_raw("industry"/"mktcap")`；`grep "data_dir" agents/agent_framework.py` = **0**；`grep "import pickle"` = **0** | A5 落码 | grep + V5/V6 | ✅ 两 grep **0**；V5/V6 PASS |
| A7 | `IDataManager` +10 只读属性；`TYPE_CHECKING` 块含 `UniverseSnapshot` | B2 落码 | 读码 + V7 | ✅ L52-100 + L19；V7 PASS |
| A8 | `FactorPipeline.__init__` 注解为 `IDataManager`；`engine_v2.py` 无 `cast(`（含导入移除） | A7 落码 | grep + mypy | ✅ `cast(` **0**；mypy 0 |

## 2. B 组：测试（V1-V16 + 2 取证项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | V1 端口读取因子逐值相等（`assert_frame_equal`） | A2 落码 | `test_p042_data_contract.py` | ✅ PASS |
| B2 | V2 缺失文件抛 `FileNotFoundError` 且文案含 `因子文件不存在:` | A2 落码 | 同上 | ✅ PASS |
| B3 | V3 `DataManager.load_factor` 触发 `provider.load_factor` 恰 1 次，且对齐到 3 个交易日 | A3 落码 | 同上 | ✅ PASS |
| B4 | V4 asof 对齐 / 首因子日前 NaN / 缺列填 0 三语义非回归 | 无（现状即正确） | 同上 | ✅ PASS（实现前后均 PASS） |
| B5 | V5 agents 成功路径：`_industry_data` / `_mktcap_data` 为门面返回值，`failure_stats == {}` | A6 落码 | 同上 | ✅ PASS |
| B6 | V6 agents 失败路径：行业读取抛错 → `{"industry_cache": 1}`，缓存 `None` | A6 落码 | 同上 | ✅ PASS |
| B7 | V7 12 个消费成员 ⊆ `dir(IDataManager)` 且 ⊆ `dir(DataManager())` | A7 落码 | 同上 | ✅ PASS（含 2 条 `not in` 断言） |
| B8 | V8 跨 symbol `seq` = 1/2/3；冻结赋值抛 `FrozenInstanceError`；协议 4 方法齐备 | B3 落码 | `test_p042_streaming_contract.py` | ✅ PASS |
| B9 | V9 `snapshot()` = 每 symbol 最新事件 | B3 落码 | 同上 | ✅ PASS |
| B10 | V10 `poll()` 首返 3 条按序、再返 `[]`、新事件仅返增量 | B3 落码 | 同上 | ✅ PASS |
| B11 | V11 `subscribe(["A"])` 后发 B 返回 `None` 且不占 seq；发 A 正常 | B3 落码 | 同上 | ✅ PASS |
| B12 | V12 `close()` 幂等；关闭后 publish `RuntimeError`、poll `[]`、snapshot `{}` | B3 落码 | 同上 | ✅ PASS |
| B13 | V13 同合成数据两实例指纹相等且以 `sha256:` 开头 | B4 落码 | `test_p042_fingerprint.py` | ✅ PASS |
| B14 | V14 改 close 单值 → 指纹变化 | B4 落码 | 同上 | ✅ PASS |
| B15 | V15 改 `factor_value.pkl` 单值 → 指纹变化 | B4 落码 | 同上 | ✅ PASS |
| B16 | V16 合成夹具写全 10 个 pkl；`n_stocks=5` / `n_dates=20` / `suspend.shape=(20,5)` / `industry`、`mktcap` 非空 | B4 落码 | 同上 | ✅ PASS（实现前亦 PASS，F-S9-P042-1） |
| B17 | 红态留证：IMPL §4.5 预测 `1 passed, 15 failed` | 五个新文件已写、实现未落 | pytest 输出逐字 | ✅ 实测 **`9 failed, 2 passed`**（data_contract+fingerprint；V4/V16 PASS）+ **`1 error`**（streaming：`ModuleNotFoundError`） |
| B18 | 既有测试订正后通过：契约测试成员集合 3→4 / 9→19；P-029 三用例保持原断言 | A1/A5/A7 落码 | `pytest tests/test_contract_conformance.py tests/test_p029_silent_exception_governance.py -q` | ✅ 红 `2 failed, 15 passed` → 绿 `33 passed in 3.00s`（五文件合计） |

## 3. C 组：不变式（DESIGN I1-I12）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1/I2** `core/data.py` 无 `pd.read_pickle`；`_provider.load_factor` 恰 1 处 | B1 落码 | grep | ✅ **0** / **1** |
| C2 | **I3** 注入 provider 后价格与因子读取均被观测（V3 + 既有 DI 测试） | B1 落码 | pytest | ✅ V3 PASS；契约测试 6 passed |
| C3 | **I4** `IDataManager` ⊇ 12 消费成员（V7） | B2 落码 | pytest | ✅ V7 PASS |
| C4 | **I5** 同数据指纹稳定、价格/因子单值变则变（V13-V15） | B4 落码 | pytest | ✅ V13-V15 PASS |
| C5 | **I6** seq 单调 / snapshot+delta 重放 / 空 poll（V8-V12） | B3 落码 | pytest | ✅ V8-V12 PASS |
| C6 | **I7** golden **13 零重录**；`git status --short tests/golden/` 为空 | 全量实现 | `pytest -k golden` + git | ✅ `13 passed, 781 deselected`；目录净 |
| C7 | **I7** pytest **794 passed**（778 + 16） | 全量实现 | 全量末行 | ✅ `794 passed, 172 warnings in 48.96s` |
| C8 | **I7** mypy **104 source files 0** | 全量实现 | CI 逐字命令 | ✅ `Success: no issues found in 104 source files` |
| C9 | **I8** 无 `live/`；`uv.lock` diff 空；`grep "from_data_manager\|AbstractDataManager"` = 0 | 全量实现 | `git status` + grep | ✅ 无 `live/`；两文件无 diff；grep **0** |
| C10 | **I9** `IDataManager` 成员不含 `load_aux_raw` / `data_fingerprint`（V7 内置断言） | B2/B4 落码 | V7 | ✅ V7 PASS |
| C11 | **I10** `grep "data_dir" agents/agent_framework.py` = **0** | A6 落码 | grep | ✅ **0** |
| C12 | **I11** `filter/**`、`core/data_v3.py`、`core/manifest.py`、`tests/golden/**` 零 diff | 全量实现 | `git diff --stat` | ✅ 四类均无 diff |
| C13 | **I12** 复权/对齐/缺失语义零变更：V4 + `test_adjustment*` + `test_data_aux_defaults` 全绿 | 全量实现 | pytest | ✅ V4 PASS；全量 794 含相关用例 |

## 4. D 组：门禁、提交与文档（7 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | black `core tests` **129** / 全仓 **196**；`tests/*.py` **91** | 五文件落盘 | `black --check` 双口径 + 计数 | ✅ `129` / `196` unchanged；**91** |
| D2 | AST `except Exception` 恒 **22**；新增 `# type: ignore` = 0 | B1 落码 | P-029 单行命令 + grep | ✅ AST **22**；ignore **0** |
| D3 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 全量实现 | 命令 + `git diff` | ✅ exit **0**；两文件无 diff |
| D4 | 门禁双载体零 diff；单提交原子（6 生产 + 5 测试侧 + 文档）；CI 四 job 全绿 | D1-D3 通过 | `git show --stat` + `gh run view` | [待 CI] |
| D5 | 文档回填：IMPL §10 实施记录 / PROGRESS §3.48.4 / CHANGELOG / 本文件实测列 46/46 | D4 通过 | 读回 | ✅ IMPL §10 + PROGRESS + CHANGELOG + 46/46（D4 除外） |
| D6 | 未决登记：U-P042-1（异构终审）/ U-P042-6（cast 降级）/ O-P042-1~4 | 文档回填 | 读回 §1.4 | ✅ U-P042-1 pending；U-P042-6 **未触发**（cast 移除成功）；O-P042-1~4 已记 |
| D7 | 派生需求登记：**0**（Step 9 若新增常量/降级策略须回填本行） | Step 9 完成 | 读回 IMPL | ✅ **0**（无新增常量/降级策略） |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **46**（A 8 + B 18 + C 13 + D 7 = 46，机械计数；B17/B18 为取证项非新用例） |
| 实测列回填 | **45/46**（A 8 / B 18 / C 13 / D 6 已回填；D4 待 CI） |

> **RULE-2 统计溯源**：46 = 8 + 18 + 13 + 7（逐表行数，非估计）；用例 16 = B1-B16；取证 2 = B17/B18。
> **RULE-5 声明**：Step 2/4/6/8 复审均自报 DeepSeek-V4.1-Flash（同源）→ 异构未成立；U-P042-1 跟踪。

---

## 6. Step 7 → Step 8 交接

1. 核红态口径：IMPL §4.5 `1 passed, 15 failed` 与 B17 逐字一致。
2. 核计数链：778 + 16 = **794**；124 + 5 = **129**；191 + 5 = **196**；87 + 4 = **91**；103 + 1 = **104**。
3. 核零预填：`[待 Step 9]` = **46** 单元格。
4. 核 ID 不混用：DESIGN 决策 `D1-D7` vs 本文件 **D 组**；引用一律 `DESIGN-D*`。

---

## 7. Step 8 一致性 Review 记录（同基座独立视角，2026-11-18）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P042-1 累计第 4 轮。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 链接校验 | RESEARCH / DESIGN / IMPL / CHECKLIST 四文档互链存在 | ✅ 0 broken |
| 2 | ID 闭环 | A1-A8 / B1-B18 / C1-C13 / D1-D7 连续无跳号；表行 **46** | ✅ |
| 3 | 计数自洽 | 46 = 8 + 18 + 13 + 7；16 用例 + 2 取证 | ✅ |
| 4 | 零预填 | `[待 Step 9]` = **46**；无 `✅` / `❌` | ✅ |
| 5 | U-P042-1 | RESEARCH §9 / DESIGN §10 / IMPL §9 / 本文件 §5 各 ≥1 处 | ✅ |

### 7.2 对齐矩阵

| # | 项 | 判定 | 证据 |
|---|----|------|------|
| 1 | 红态口径 | ✅ | IMPL §4.5「1 passed, 15 failed」与 B17 逐字一致 |
| 2 | 接口签名 | ✅ | DESIGN §3 / IMPL §3.1-3.9 / A1-A8 三处一致（`name: str` / 10 属性 / frozen 5 字段） |
| 3 | 批次边界 | ✅ | DESIGN §4 / IMPL §2 / A-C 组：B1→A1-A6、B2→A7-A8、B3→B8-B12、B4→B13-B16 |
| 4 | 门禁目标 | ✅ | DESIGN §1 / IMPL §7 / 本文件头部一致（794 / 129·196 / 104 / 22 / 91） |
| 5 | 既有测试订正面 | ✅ | DESIGN §5 / IMPL §4.4 / B18 一致（2 文件） |
| 6 | 派生需求 | ✅ | D7 显式登记「0」并给出 Step 9 回填条件 |

### 7.3 发现与当轮处置（0 P1/P2 + 3 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P042-1 | P3 | DESIGN I7 被拆到 C6/C7/C8 + D1/D2/D3 六行，未写映射 → 按 I7 追溯时会断链 | C 组标题与 C6-C8 均标注「I7」，D1-D3 承接 black/AST/uv；§6 交接第 2 项给出计数链 |
| F-S8-P042-2 | P3 | IMPL §4.4 的既有测试订正无 V 编号，B 组易漏验 | 新增 B18 承接（取证项，不计入 16 用例） |
| F-S8-P042-3 | P3 | C10（I9）初稿只写「`dir` 断言」，但 V7 未含非成员断言 → 验收无可执行载体 | IMPL §4.1 V7 增 `"load_aux_raw" not in` / `"data_fingerprint" not in` 两条；C10 证据出口改为 V7 |

### 7.4 结论

**Step 8 Review pass（0 P1/P2 + 3 P3 当轮处置）**——46 项可执行、DoR/DoD 齐备、四文档口径闭环；**准予进入 Step 9 TDD 实施**。
**RULE-5**：第 4 轮同基座 → U-P042-1 pending（终审 GLM-5.3-Flash）。
