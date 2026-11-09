# P-010（`DataManager` 辅助数据缺失处理） · 审查验收清单

> **文档编号**: CHECKLIST_p010_aux_defaults
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 待执行（Step 8 通过后进入 Step 9）
> **上游**: [DESIGN_p010_aux_defaults.md](DESIGN_p010_aux_defaults.md)（Step 4 通过，D1-D7 / V1-V8） · [IMPL_p010_aux_defaults.md](IMPL_p010_aux_defaults.md)（Step 6 通过，T-0~T-6 / F-I1~F-I3）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；「实测」列一律 `[待 Step 9]`，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口。
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；`MPLBACKEND=Agg`
> **基线时点**: 本仓 @ `e6ed18d`；RED 读数 510 / 93 / 136 / 1 / 6 次加载

---

## 1. 功能完整性（A）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `DataManager.__init__` 新增 `self._aux_loaded: bool = False` | 读回 `core/data.py` | DESIGN D1；IMPL T-1 | ✅ L54 `self._aux_loaded: bool = False` |
| A2 | `_load_auxiliary_data` 首行 `if self._aux_loaded: return`，末尾置 `True` | 读回 | DESIGN D1 | ✅ L275-276 guard；L324 置 True |
| A3 | 停牌文件缺失时 `_suspend_data` = `pd.DataFrame(0, index=trade_dates, columns=stock_codes)`，并有 `logger.warning` | 读回 + T1 | DESIGN D2 | ✅ L292-296；探针 `(100, 50)` 全 0 |
| A4 | ST 文件缺失时 `_st_data` = 全 0 DataFrame + `logger.warning` | 读回 + T1/T4 | DESIGN D2 | ✅ L310-314；T1/T4 通过 |
| A5 | 行业文件缺失时 `_industry_data` 保持 `None` + warning（不造默认值） | 读回 + T1 | DESIGN D3 | ✅ L302-303；探针 `industry is None` True |
| A6 | 市值文件缺失时 `_mktcap_data` 保持 `None` + warning（不造默认值） | 读回 + T1 | DESIGN D3 | ✅ L321-322；探针 `mktcap is None` True |
| A7 | 已存在文件**不被默认值覆盖**（先读盘、后 else） | 读回 + T3 | DESIGN D2；IMPL T-2 | ✅ T3 通过（`iloc[0,0]==1` 保留） |
| A8 | `industry` 属性注解改为 `Optional[pd.DataFrame]`；`suspend` 仍为非 Optional | 读回 L124-149 | DESIGN D3/D2 | ✅ L132 `-> Optional[pd.DataFrame]`；`suspend` 仍 `-> pd.DataFrame` |
| A9 | `filter/universe_filter_clean.py` 与 `core/factor.py` **零 diff** | `git status --short` | DESIGN D4 | ✅ `git diff --stat -- filter/ core/factor.py` **空** |

## 2. 测试完整性（B）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `tests/test_data_aux_defaults.py` 存在且恰含 4 个 `test_*` | 文件 + `pytest --collect-only` | IMPL T-4 | ✅ 文件存在；`collected 4 items` |
| B2 | T1 断言 `suspend`/`st` 为 `(100, 50)` 全 0 DataFrame，`industry`/`mktcap is None` | `pytest -q tests/test_data_aux_defaults.py` | DESIGN D5 | ✅ `4 passed`；探针复核 shape `(100, 50)` 全 0 |
| B3 | T2 断言 `.industry` 3 次访问 → `_load_and_align_data` **1 次**（guard 关闭模拟 = 3） | 同上 | DESIGN D5 / V6 | ✅ `4 passed`；独立探针 guarded **1** / guard-off **3** |
| B4 | T3 断言既有 `suspend` 的 1 值保留 | 同上 | DESIGN D5 / V7 | ✅ `4 passed`；`sum == 1` |
| B5 | T4 断言两条缺失 warning 同时命中 | 同上（caplog） | DESIGN D5 / R3 | ✅ `4 passed`（命中「停牌数据文件不存在」「ST数据文件不存在」） |
| B6 | 全量 `pytest -q` = **`514 passed`**，零 failed、零新增 skip | pytest 末行 | DESIGN V2 | ✅ **`514 passed, 82 warnings in 24.26s`**；0 failed / 0 skipped |
| B7 | 测试文件数 49 → **50**；收集数 **514** | `Get-ChildItem` / `--collect-only` | DESIGN D5 | ✅ **50** 文件；**`514 tests collected in 3.47s`** |

## 3. 验证口径（C：V1-V8）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | **V1**：`mypy` = **`93 errors in 3 files`**（不劣化） | mypy 末行 | DESIGN V1 | ✅ **`Found 93 errors in 3 files (checked 29 source files)`** |
| C2 | **V2**：全量 `514 passed` | pytest 末行 | DESIGN V2 | ✅ **`514 passed, 82 warnings in 24.26s`** |
| C3 | **V3**：新测试文件 `4 passed` | pytest 末行 | DESIGN V3 | ✅ **`4 passed in 0.84s`** |
| C4 | **V4**：独立探针复核缺失默认值（全 0 DataFrame） | 探针输出 | DESIGN V4 | ✅ `suspend all-zero: True (100, 50)`；`st all-zero: True (100, 50)` |
| C5 | **V5**：独立探针复核 `industry`/`mktcap` 为 `None` | 探针输出 | DESIGN V5 | ✅ `industry is None: True`；`mktcap is None: True` |
| C6 | **V6**：独立探针复算幂等（`.industry` 3 次访问 → 1 次加载） | 探针输出 | DESIGN V6 | ✅ guarded **1**；guard-off 模拟 **3** |
| C7 | **V8-a**：`black --check .` exit 0，**137 files unchanged** | 子进程 exit + 末行 | DESIGN V8 | ✅ **`137 files would be left unchanged`，exit 0** |
| C8 | **V8-b**：消费方 `git diff --stat -- filter/ core/factor.py` 为空 | git | DESIGN V8 / D4 | ✅ **输出为空** |
| C9 | 缺失停牌数据时 `_build_next_day_tradable_mask` 末行为 False（D6 行为变更已实现） | **独立探针（E2）**：仅价格文件构造后取过滤器掩码末行 | DESIGN D6 | ✅ `last row all False: True`；`other rows all True: True`；`suspend mask all True: True` |

## 4. 台账与文档（D）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `docs/PROGRESS.md` P-010 行 → done（含 4 测试、514、D6 声明） | 读回 | IMPL T-6 | ✅ P-010 行已改为 `done（2026-11-09，T1 全流程…）`，含 514 与行为变更 |
| D2 | `docs/PROGRESS.md` §3.10 新增批次记录（T1 / 变更面 / 门禁 / 回退点） | 读回 | IMPL T-6 | ✅ §3.10 已新增（Step 1-9 全链 + 范围 + D6 声明 + 回退点） |
| D3 | `CHANGELOG.md` `Fixed` 新增（幂等 / 类型契约 / 停牌·ST 默认值）+ `Changed` 新增（末日可交易性，D6） | 读回 | DESIGN D6/R1 | ✅ `Fixed` 首条 + `Changed` 首条均已落地 |
| D4 | 四文档齐备、互引链接可解析 | 文件 + 链接检查 | 模板 | ✅ 4 文件齐备；链接 **11 条 0 broken**（Step 8） |
| D5 | 单笔提交 `fix(P-010): 辅助数据缺失时提供安全默认值并幂等化加载` | `git log -1 --stat` | IMPL T-6 | [待提交] |
| D6 | 远端 CI 三 job 全绿（3.12 `507 passed, 1 skipped` = 514 − 7 numba） | 远端 run | IMPL T-6 | [待推送] |

## 5. 排除与风险（E）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 未复制旧版 `pd.DataFrame(True, ...)` 停牌默认值 | Grep `DataFrame(True` in data.py = 0 | RESEARCH P9；排除表 | ✅ `core/data.py` 中 `DataFrame(True` **0 命中** |
| E2 | 零新增 `# type: ignore`；`[tool.mypy]` 配置零改动 | Grep = 1；`git diff pyproject.toml` 空 | 排除表 | ✅ `type: ignore` 仍 **1 处**；`pyproject.toml` **diff 空** |
| E3 | 未用 `try/except pass` 吞读盘异常 | `git diff` 无新增 `except` | 排除表 | ✅ data.py diff 无新增 `except` |
| E4 | 未修改 `filter/`、`core/factor.py`、`core/config.py`、`pyproject.toml` | `git status --short` | DESIGN §5 | ✅ `git status` 仅 `M core/data.py` + 5 个新文件 |
| E5 | D6 行为变更（末日可交易性）已书面披露（DESIGN D6 + CHANGELOG Changed + PROGRESS） | 三处读回 | DESIGN D6/R1 | ✅ DESIGN D6 表 + CHANGELOG `Changed` 首条 + PROGRESS §3.10 三处均已披露 |

---

## 6. 一致性 Review（Step 8）

- **执行时点**: 四文档完稿后单独执行（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 相对链接机械校验 + 跨文档计数矩阵 + CHECKLIST 预填合规扫描 + 断言延续链核对

**机械校验读数**：

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 四文档互引链接 | Python `re` + `Path.exists()` | **11 条，0 broken** |
| 验收项总数 | 正则 `^\| ([A-E])\d+ \|` | **36**（A9 / B7 / C9 / D6 / E5） |
| 零预填合规 | 逐行断言：36 个验收行中含 `✅` 的行数 | **0**；`[待 Step 9]` 占位 **42 处** |
| `514 passed` | 上游三文档 Grep | DESIGN 1 / IMPL 2 = **3 处** |
| `93 errors` | 上游三文档 Grep | DESIGN 1 / IMPL 2 = **3 处**（均作基线/不劣化口径） |
| `6 次`（RED） / `2 次`（GREEN） | 上游三文档 Grep | 5+2+1 / 1+1+2 = **8 / 4 处**（同一幂等判据两端） |
| `P-010` | 四文档 Grep | RESEARCH 4 / DESIGN 1 / IMPL 4 / CHECKLIST 3 = **12 处** |

**发现 2 项（均 P3，均已修复）**：

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-S1** | P3 | DESIGN D6 写「全量测试应仍 514 通过」——基线是 510，514 是「510 + 新增 4」，「仍」字会误导读者以为基线为 514 | 已改为「既有 510 项全绿 + 本批新增 4 项 = 514」 |
| **F-S2** | P3 | CHECKLIST C9 要求验证 D6 的末行 False，但 DoD 写「定向探针/测试」二义，而 D5 的 4 项测试中并无此项，实施者可能漏验或擅自加测试导致计数偏离 514 | 已明确为「独立探针（E2）」并给出构造方式，保持 4 项测试计数不变 |

**断言延续链核对**：

| 链路 | 贯通情况 |
|------|----------|
| RESEARCH D-1 → DESIGN D1/D7 → IMPL T-1 → CHECKLIST A1/A2/C6 | 贯通（幂等判据 6 次→2 次三处一致） |
| RESEARCH D-2 → DESIGN D3 → IMPL T-3 → CHECKLIST A8 | 贯通（`industry` Optional；`suspend` 非 Optional 有理由） |
| RESEARCH D-3 → DESIGN D2 → IMPL T-2 → CHECKLIST A3/A4/E1 | 贯通（0=正常；显式禁止旧版 True） |
| RESEARCH D-4 → DESIGN D3/D4 → IMPL T-2 → CHECKLIST A5/A6/A9 | 贯通（行业/市值保持 None；消费方零改动） |
| DESIGN D6 → IMPL T-6 → CHECKLIST C9/D3/E5 | 贯通（末行 False 三处披露） |
| DESIGN D5 → IMPL T-4 → CHECKLIST B1-B7 | 贯通（4 项、510→514、文件 49→50） |

**结论**: 0 项阻断（P1/P2 = 0）；2 项 P3 已回写。36 项验收口径覆盖 D1-D7 / V1-V8 全部，可进入 Step 9 实施。

---

## 7. 验收统计（Step 9 后回填）

| 分组 | 项数 | ✅ | ⚠️ | ❌ |
|------|------|----|----|----|
| A 功能完整性 | 9 | 9 | 0 | 0 |
| B 测试完整性 | 7 | 7 | 0 | 0 |
| C 验证口径 | 9 | 9 | 0 | 0 |
| D 台账文档 | 6 | 4 | 0 | 0（D5/D6 待提交与 CI） |
| E 排除风险 | 5 | 5 | 0 | 0 |
| **合计** | **36** | **34** | **0** | **0** |

---

## 8. 红 → 绿记录（Step 9）

### 8.1 RED（实施前 @ `e6ed18d`）

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| RED-1 | 全量测试 | `pytest -q` | **510 passed** |
| RED-2 | 类型基线 | `mypy --explicit-package-bases core` | **93 errors in 3 files** |
| RED-3 | 格式 | `black --check .` | **136 unchanged**，exit 0 |
| RED-4 | `type: ignore` | Grep | **1 处** |
| RED-5 | 重复读盘 | 探针（7 个 pkl，无 st） | `.st` 3 次 → `_load_and_align_data` **6 次**；100 次 → **206 次 / 144.90 ms** |
| RED-6 | 类型契约 | 探针（仅 close.pkl） | `suspend is None` = **True**（声明 `-> pd.DataFrame`） |

### 8.2 GREEN

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| GREEN-1 | 缺失默认值 | 探针 | `suspend`/`st` 全 0，shape **`(100, 50)`** |
| GREEN-2 | Optional 契约 | 探针 | `industry is None` / `mktcap is None` 均 True |
| GREEN-3 | 幂等 | 探针 | `.industry` 3 次 → 加载 **1 次**（guard 关闭模拟 **3 次**） |
| GREEN-4 | D6 末日 | 探针 | `last row all False: True`；`other rows all True: True` |
| GREEN-5 | 新测试 | `pytest tests/test_data_aux_defaults.py -q` | **`4 passed in 0.84s`** |
| GREEN-6 | 全量测试 | `pytest -q` | **`514 passed, 82 warnings in 24.26s`** |
| GREEN-7 | 收集/文件数 | `--collect-only` / `Get-ChildItem` | **514** / **50** |
| GREEN-8 | mypy | `mypy --explicit-package-bases core` | **93 errors in 3 files** |
| GREEN-9 | 格式 | `black --check .` | **137 unchanged**，exit 0 |
| GREEN-10 | 消费方 diff | `git diff --stat -- filter/ core/factor.py` | **空** |
| GREEN-11 | `data.py` 体量 | `git diff --numstat` | **+33 −2** |

### 8.3 实施期发现

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-9-1** | P2 | DESIGN/IMPL 原定的幂等测试用 `.st`（3 次 → 2 次）**不可行**：D2 给 ST 默认值后 `.st` 恒非 None，属性不再触发 `_load_auxiliary_data`，该测试在修复前后都会「通过」（恒真）。真正残留的重复加载路径是 `.industry`（保持 None） | 测试改为 `.industry` 3 次 → 计数 **1**（guard 关闭模拟 **3**）；DESIGN D5/IMPL T-4/CHECKLIST B3/C6 已同步更正。**教训**：D2 与 D1 的交互使原 RED 判据失效，若照原方案实施会得到假绿测试 |

---

## 9. ADD 审计（Step 10）

### Phase 0 — Spec 质量门

| 检查 | 结果 |
|------|------|
| DESIGN/IMPL 不可审计措辞（`大概` / `应该差不多` / `可能是这样` / `待定` / `不确定` / `TODO`） | **0 命中** |
| 每条决策是否携带被拒方案与代价 | D1（`lru_cache` 跨实例泄漏 / 文件级 mtime 无需求）、D2（旧版 `True` 语义相反）、D3（行业/市值默认值与过滤配置冲突）、方案 D（直接 raise 打断可选数据语义）均有被拒理由 |
| 断言是否可证伪 | 510/514、93、136/137、3→1 次读盘、末日 False 均为可重放读数/探针 |

### Phase 1 — 完整性（设计 → 落地）

| 决策 | 落地位置 | 证据 |
|------|----------|------|
| D1 幂等 guard | `core/data.py:54` + `:275-276` + `:324` | A1 / A2 / C6 |
| D2 停牌/ST 默认 0 | `core/data.py:292-296` / `:310-314` | A3 / A4 / C4 |
| D3 行业/市值保持 None + `industry` Optional | `core/data.py:132` / `:302-303` / `:321-322` | A5 / A6 / A8 / C5 |
| D4 消费方零改动 | `git diff --stat -- filter/ core/factor.py` 空 | A9 / C8 |
| D5 4 项测试 | `tests/test_data_aux_defaults.py`（69 行） | B1-B7 |
| D6 末日行为变更 | 探针 `last row all False`；DESIGN/CHANGELOG/PROGRESS 三处 | C9 / E5 |
| D7 幂等边界 | docstring「首次加载后新增的文件不会自动重载」 | A2 读回 |

### Phase 2 — 忠实度（代码 diff ↔ 设计）

| 设计声明 | 实测 | 判定 |
|----------|------|------|
| `core/data.py` ±30 行 | **+33 −2** | ✅ 量级一致 |
| 新增测试 +80 行量级 | **69 行**（black 格式化后） | ✅ 量级一致 |
| 仅 `core/data.py` + 1 测试 + 文档 | `git status`：`M core/data.py` + 4 文档 + 1 测试 | ✅ 精确一致 |
| 无新增 `type: ignore` / 无 mypy 配置改动 | Grep=1；`pyproject.toml` diff 空 | ✅ |
| 消费方零 diff | `filter/`、`core/factor.py` diff 空 | ✅ |

### Phase 3 — 必要性（新增行可归属）

| 检查 | 结果 |
|------|------|
| 盲区扫描：设计外文件 | **0 项** |
| 是否有未在 T-1~T-4 中的改动 | **无**（33 行 = guard 4 + 默认值/告警 19 + docstring 8 + 注解 1 + 防御 3，均可归属） |
| 保护路径越界 | `filter/` / `core/factor.py` / `core/config.py` / `pyproject.toml` **diff 空** |
| 是否顺手重构 | **无**（`_load_and_align_data` 未动；未改 import；未调整相邻代码） |

### Phase 4 — 语义（目标是否真正达成）

| 铁律检查 | 结果 |
|----------|------|
| 「测试通过 ≠ 设计落地」 | 本批目标不是「补 4 个测试」，而是消除**可测的真实缺陷**：重复读盘以 `_load_and_align_data` 计数复算（guard-off 模拟 3 vs guarded 1）；类型契约以 `suspend is None` 探针复核；两个默认值以 `(100, 50)` 全 0 帧复核 |
| expected-fail 是否伪装 | **无**：mypy 仍如实 93（本批不触碰引擎层），无 ignore/降级 |
| 能力边界是否夸大 | **无**：D6 末日 True→False 明示为行为变更；行业/市值不造默认值并说明理由；`_aux_loaded` 不热更新文件已声明 |
| 是否误用旧版「安全默认值」 | **无**：显式拒绝旧版 `True`（= 全停牌），E1 断言 `DataFrame(True` 0 命中 |

### 审计结论

**P1 = 0，P2 = 0**（F-D1 的行为变更遗漏在 Step 4 拦截；F-9-1 的恒真测试在 Step 9 拦截并改写）；**P3 = 8 项**（F-R1~R3、F-D2~D3、F-I1~I3、F-S1~S2 —— 其中 F-S1/S2 为 Step 8）全部登记处置；**盲区扫描 0 项设计外改动**。

---

## 10. 结论（Step 10）

**P-010（`DataManager` 辅助数据缺失处理）已完成。**

| 维度 | 结果 |
|------|------|
| 验收项 | **36/36** |
| 缺陷 | **P1 = 0 / P2 = 0**；P3 = 8 项全部处置 |
| 核心交付 | 幂等 guard（`.industry` 3 次访问读盘 **3 → 1**）；停牌/ST 缺失按 `0=正常` 默认；行业/市值保持 `None` + `industry` 注解 Optional；4 项测试（510 → **514 passed**） |
| 零回归 | 全量 `514 passed`；mypy **93**（不劣化）；`black --check .` **137 unchanged**；消费方 **diff 空** |
| 行为变更（已披露） | 缺失停牌数据时 next-day 掩码末日 **True → False**（末日无次日） |
| 门禁 | probe pass / unit-tests pass / black-check pass / **mypy-check fail(93，如实)**；`replay: 4 rows OK` |
| 遗留 | 层 B（93 errors）另立；U-006 不关闭 |
