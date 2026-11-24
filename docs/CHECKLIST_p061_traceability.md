# CHECKLIST：P-061 全周期可追溯性与可视化审计

> **批次**：**P-061**（B1 报告 / B2 采集 / B3 视图，三批同属本批次）
> **上游**：[DESIGN_p061](DESIGN_p061_observability_traceability.md)（§15 DoD / §12 G1-G14 / §13 I1-I12 / §11 37 例 / §18-§19 修订）· [IMPL_p061](IMPL_p061_traceability.md)（§4 卡片 / §5 S5-1..S5-5 / §9 修订）· [REVIEW_p061_step2](REVIEW_p061_step2.md) · [REVIEW_p061_step4](REVIEW_p061_step4.md) · [REVIEW_p061_step6](REVIEW_p061_step6.md) · [RESEARCH_p061](RESEARCH_p061_observability_traceability.md)
> **作者**：DeepSeek-V4.1-Flash（Step 6/8/9/10 由非作者执行，异构成立，RULE-5）
> **状态**：**批次关闭并推送（2026-11-24，CI run 45412361688 四 job 全绿）**；**64/64 ✅**；F1 三批 commit `7bf6b38`（B2）/ `64552d6`（B1）/ `cc36422`（B3）+ docs 关闭 `05f627b`；Step 10 验收 PASS-WITH-COMMENTS（§12）
> **实测列规则（RULE-1）**：仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **行号口径**：本文件引用行号 @`4367775`（P-060a 关闭基线，工作区干净）

**基线读数（@`4367775`）**：collect **1557**（1556 passed + 1 skipped）/ golden **22** / `-k p059` **63** / covA 四包 **10714/12165 = 88.07%**（core 8165/9117 = 89.56% / live 87.95% / services 74.54% / strategies 93.54%）/ 不变式 **11** / 契约 **6** / 场景 **18 条 7 层** / mypy **160 files 0 error** / black **330 unchanged**。

**本批目标读数**：collect **1594**（1557 + 37）/ `-k p061` **37** / golden **22（零重录）** / p059 **63** / 四包逐包 **≥ 基线 −0.5pp**（新增 `core/trace.py` 自身 **≥80%**）/ mypy **162 files**（+`core/trace.py`、`scripts/trace_report.py`）/ black **336**（330 + 2 源 + 4 测试）。

---

## 1. A 组：DESIGN §15 DoD（6 项）

| ID | 验收项 | DoR | 证据出口 | 实测 |
|----|--------|-----|----------|------|
| A1 | **G1-G14 全绿**且读数留档（含新增 G11 lint-imports / G12 零行为 / G13 对齐 / G14 依赖） | S5-5 | 十四条命令逐条复跑 | ✅ G1-G14 全绿：1594 / 22 / 63 / 37 / 162·0 / 336 / core 89.82%·trace 94.53% / 11 / 6 / 18 条 7 层 / 3 kept / 三 CSV sha256 一致 / residual<1e-8 / uv exit 0 |
| A2 | **37 例全绿**，`-k p061` 收集数 **= 37**（±0），全部带 `T-` ID | S5-1..S5-4 | `pytest -q -k p061` + `--collect-only` | ✅ `-k p061` 37 passed（1557 deselected） |
| A3 | **零行为**：同 cfg 对跑（`audit_trace_dir=None` vs `<tmp>`），`trades.csv`/`portfolio_snapshots.csv`/`pending_order_events.csv` **sha256 相同**；`input_fingerprint` 必异属预期 | S5-3 | 两次 run + sha256 | ✅ T-B01：`trades.csv` / `portfolio_snapshots.csv` / `pending_order_events.csv` sha256 相同；指纹必异 |
| A4 | **对齐**：样例 run `alignment.residual < 1e-8`；五问（为什么买/为什么卖/订单卡点/NAV 差异/可否复现）全部可答 | S5-4 | `alignment.json` + T-D01 | ✅ T-D01：`alignment.reconcile.residual == 0` < 1e-8；五问逐条断言通过 |
| A5 | **覆盖率**：`core/trace.py` 自身 **≥80%**；四包逐包 ≥ 基线 −0.5pp | S5-5 | covA JSON | ✅ `core/trace.py` 259/274 = 94.53%；四包 89.82 / 87.95 / 74.54 / 93.54 |
| A6 | **生产改动面**仅 `core/config.py` / `core/engine_v2.py` / `cli.py`（+B3 `web/` 标注）；其余零 diff | S5-3/S5-4 | `git diff --stat` | ✅ `git diff --stat` 仅 `core/config.py` + `core/engine_v2.py` + `cli.py` + web 5 页各 +1 行 |

## 2. B 组：交付物（9 项）

| ID | 验收项 | DoR | 证据出口 | 实测 |
|----|--------|-----|----------|------|
| B1 | `core/trace.py`：`TraceConfig(out_dir: Path \| None)`、`TraceCollector`（enabled/on_* /finalize(remaining_orders)）、`classify_reject`、`REJECT_REASONS`/`CLOSE_REASONS`、`TRACE_SCHEMA_VERSION` | S5-2 | 读码 + T-A01 | ✅ `core/trace.py`：TraceConfig（Path.None）/ Collector / finalize(remaining_orders) / classify_reject / 两闭集 / SCHEMA=1.0；T-A01 绿 |
| B2 | `scripts/trace_report.py`：CLI `--run-dir/--out/--check`，退出码 0/1，**两级产物**（核心缺→1；辅助缺→missing[]+0），HTML 单文件离线；B1 期 schema 常量临时自带，S5-2 后**收敛为 `from core.trace import`**（F-S8-P061-1） | S5-1 | 读码 + T-C01..C08 | ✅ `scripts/trace_report.py`：CLI 0/1、两级产物、HTML 单文件；已收敛 `from core.trace import`；T-C01..C08 绿 |
| B3 | `core/config.py` +`audit_trace_dir`/`audit_trace_full`（默认 `None`/`False`）；`cli.py` +`--audit-trace-dir`/`--audit-trace-full` | S5-3 | 读码 + T-B15 | ✅ `core/config.py` +`audit_trace_dir`/`audit_trace_full`；`cli.py` +`--audit-trace-dir`/`--audit-trace-full`；T-B15 绿 |
| B4 | `core/engine_v2.py`：S1-S8 全部只读追加；注入优先级 `trace_collector > cfg.audit_trace_dir > None`；run 末 `finalize(remaining_orders)` 终扫 | S5-3 | 读码 + Step 6 逐点复核 | ✅ S1-S8 只读追加；注入优先级 collector > cfg > None；run 末终扫；T-B01..B15 绿 |
| B5 | `tests/test_p061_trace_collector.py`：**10 例**（T-A01..A10） | S5-2 | `--collect-only` | ✅ `test_p061_trace_collector.py` 10 passed |
| B6 | `tests/test_p061_trace_seams.py`：**15 例**（T-B01..B15） | S5-3 | `--collect-only` | ✅ `test_p061_trace_seams.py` 15 passed |
| B7 | `tests/test_p061_trace_report.py`：**8 例**（T-C01..C08） | S5-1 | `--collect-only` | ✅ `test_p061_trace_report.py` 8 passed |
| B8 | `tests/test_p061_trace_e2e.py`：**4 例**（T-D01..D04） | S5-4 | `--collect-only` | ✅ `test_p061_trace_e2e.py` 4 passed |
| B9 | 契约：每例 docstring 首行 `T-ID \| oracle=`；复用既有夹具（不新增第五套生成器）；不复制外部源码（X1-X14 仅对照） | B5-B8 | 正则扫描 + 读码 | ✅ 37 例 docstring 首行均 `T-… / oracle=`；仅复用 `_scenarios_builder` 既有夹具，未新增第五套 |

## 3. C 组：不变式（DESIGN §13 I1-I12，12 项）

| ID | 验收项 | DoR | 证据出口 | 实测 |
|----|--------|-----|----------|------|
| C1 | **I1** 默认关闭、零 I/O（`audit_trace_dir=None` 不建目录/不写文件） | S5-2 | T-A01 / T-B01 | ✅ T-A01 零文件零目录；T-B01 关闭 run 不产 audit 目录 |
| C2 | **I2** 关闭时既有产物**字节级不变** | S5-3 | G12 / T-B01 | ✅ T-B01 三 CSV sha256 逐字节一致 |
| C3 | **I3** 不改 `Trade`/`PendingOrder` 字段；`core/pending.py` **零 diff** | S5-2/S5-3 | `git diff` 守卫 | ✅ `core/pending.py` 零 diff；T-B02 成交一致 |
| C4 | **I4** 同输入 → 同 `trace_id` 序列与同文件字节（不含时间戳/随机） | S5-4 | T-D02 / T-C08 | ✅ T-D02 三表字节相同；T-C08 HTML/JSON 两次字节相同 |
| C5 | **I5** 只追加；仅末日末行允许覆写（S8 显式设计） | S5-3 | T-A07 / T-B12 | ✅ T-A07 末日覆写为覆盖非追加；T-B12 末行=快照末行 |
| C6 | **I6** 拒单原因闭集；越界记 `unknown` 并计数 | S5-2 | T-A03 | ✅ T-A03 8 组分支 → 闭集确定值；越界 → unknown |
| C7 | **I7** 平仓原因闭集（本批 `rebalance/final_liquidation/delisted/unknown`；`stop_*` 保留不产生） | S5-3 | T-B10/B11 | ✅ T-B10 final_liquidation；T-B11 delisted；闭集 3 值 + unknown |
| C8 | **I8** 视图只读、离线、无网络（无 `http(s)://`、无 `<script src>`） | S5-1 | T-C04 | ✅ T-C04 HTML 无 `http(s)://`、无 `<script`、含内联 SVG |
| C9 | **I9** 残差阈值 `1e-8`，与 `change_report.RESIDUAL_TOL` 同源 | S5-2 | T-A09 / G13 | ✅ `RESIDUAL_TOL` 1e-8 与 `change_report` 同源；T-A09；T-D01 residual 0 |
| C10 | **I10** 零新增依赖（`pyproject.toml`/`uv.lock` 零 diff） | S5-1..S5-4 | G14 / `uv lock --check` | ✅ `pyproject.toml`/`uv.lock` 零 diff；`uv lock --check` exit 0 |
| C11 | **I11** seam 不改控制流/返回值（G1-G3 全绿 + A3 对跑） | S5-3 | G1-G3 / T-B01 | ✅ G1-G3 全绿 + T-B01 对跑；seam 无分支改写 |
| C12 | **I12** trace 写入失败不影响回测（`OSError` 仅 warning） | S5-3 | 只读目录注入变体 | ✅ 读码：`run()` 内 `finalize` 包 `try/except OSError` → `logger.warning`（DD12） |

## 4. D 组：T-ID 逐组验收（20 行 / 37 例）

> 例数合计 **37** = T-A **10** + T-B **15** + T-C **8** + T-D **4**。

| ID | 目标与 oracle | 例数 | 证据出口 | 实测 |
|----|---------------|------|----------|------|
| D1 | **T-A01/A02** 禁用零 I/O；`order_seq` 唯一且稳定（contract + closed-form） | 2 | `test_p061_trace_collector` | ✅ T-A01/A02 passed |
| D2 | **T-A03** `classify_reject` 8 分支 → 闭集确定值（cross-check） | 1 | 同上 | ✅ T-A03 passed（8 分支） |
| D3 | **T-A04/A05** 日末差分三态；fallback 双登记（state） | 2 | 同上 | ✅ T-A04/A05 passed |
| D4 | **T-A06/A07** direct 哨兵与 `orders≠fills`；末日覆写（boundary） | 2 | 同上 | ✅ T-A06/A07 passed |
| D5 | **T-A08/A09/A10** 4 文件列序；residual 闭式 0/非 0；full 行集（contract + closed-form + boundary） | 3 | 同上 | ✅ T-A08/A09/A10 passed |
| D6 | **T-B01** 同 cfg 对跑三 CSV sha256（`enable_pending_orders=True`）（contract） | 1 | `test_p061_trace_seams` | ✅ T-B01 passed（sha256 一致） |
| D7 | **T-B02/B03** fill↔trades 一致；与 P-059 `TraceRecorder` 日桶对拍（cross-check） | 2 | 同上 | ✅ T-B02/B03 passed |
| D8 | **T-B04** S1 每日记录、`N_days=5` 触发日 1/6/11/16（state） | 1 | 同上 | ✅ T-B04 passed（triggered 索引 0/5/10/15） |
| D9 | **T-B05/B06** 三因可区分；`cash_short` 保留→次日 filled（state + boundary） | 2 | 同上 | ✅ T-B05/B06 passed |
| D10 | **T-B07/B08** clamp/无持仓终态；过期 + collector `retry_count=2`（state） | 2 | 同上 | ✅ T-B07/B08 passed（retry_count=2） |
| D11 | **T-B09/B10/B11** fallback 双登记；强平 direct；退市金额（state + closed-form） | 3 | 同上 | ✅ T-B09/B10/B11 passed |
| D12 | **T-B12/B13** 末日末行=强平后快照；事件总线共存（boundary + contract） | 2 | 同上 | ✅ T-B12/B13 passed |
| D13 | **T-B14/B15** 终扫 expired；manifest 新字段 + 指纹稳定（state + contract） | 2 | 同上 | ✅ T-B14/B15 passed |
| D14 | **T-C01/C02** 对齐 exit 0；篡改 exit 1（contract） | 2 | `test_p061_trace_report` | ✅ T-C01/C02 passed |
| D15 | **T-C03/C04** 两级产物；HTML 无外链（boundary + contract） | 2 | 同上 | ✅ T-C03/C04 passed |
| D16 | **T-C05/C06** 四段渲染 + 来源标注；L1-L6 交叉校验（contract） | 2 | 同上 | ✅ T-C05/C06 passed |
| D17 | **T-C07/C08** `--check` 不写 HTML；两次生成字节相同（contract） | 2 | 同上 | ✅ T-C07/C08 passed |
| D18 | **T-D01** 五问逐条可答（manual） | 1 | `test_p061_trace_e2e` | ✅ T-D01 passed（五问） |
| D19 | **T-D02/D03** 两次运行字节相同；lint-imports 通过（invariant + contract） | 2 | 同上 | ✅ T-D02/D03 passed（lint-imports 3 kept） |
| D20 | **T-D04** trace 开启增量耗时 <10%（boundary） | 1 | 同上 | ✅ T-D04 passed（取 3 轮最小值，增量 < 10%） |

## 5. E 组：门禁与静态检查（14 项）

| ID | 验收项（门禁） | 命令 / 方法 | 通过条件 | 实测 |
|----|----------------|-------------|----------|------|
| E1 | **G1** 全量 | `pytest tests/ -q` | 全绿；collect **1594**（≥1557） | ✅ 1593 passed + 1 skipped；collect 1594（`MPLBACKEND=Agg` 同 CI） |
| E2 | **G2** golden | `pytest -q -k golden` | **22**，零重录 | ✅ 22 passed（零重录） |
| E3 | **G3** P-059 | `pytest -q -k p059` | **63**，场景零改动 | ✅ 63 passed |
| E4 | **G4** P-061 聚合 | `pytest -q -k p061` | **37**（= 计划数） | ✅ 37 passed |
| E5 | **G5** 类型 | CI 同款 mypy（十四目录，不含 tests） | **0 error**；files **162** | ✅ 162 source files / 0 error |
| E6 | **G6** 格式 | `black --check .` | 全绿；**336**（330 + 6） | ✅ 336 unchanged |
| E7 | **G7** 覆盖率 | covA JSON | 四包逐包 **≥ 基线 −0.5pp**；`core/trace.py` **≥80%** | ✅ core 8540/9508=89.82%；live 87.95%；services 74.54%；strategies 93.54%；trace.py 94.53% |
| E8 | **G8** 不变式 | `pytest -q tests/test_invariants.py` | 全绿（基线 **11**） | ✅ 11 passed |
| E9 | **G9** 契约 | `pytest -q tests/test_contract_conformance.py` | 全绿（基线 **6**） | ✅ 6 passed |
| E10 | **G10** 场景入口 | `python scripts/verify_scenario.py --list` | **18 条 / 7 层** | ✅ 18 条；层覆盖 7/7 |
| E11 | **G11** 依赖方向 | `lint-imports` | C1/C2/C3 全绿 | ✅ C1/C2/C3 3 kept, 0 broken |
| E12 | **G12** 零行为 | 同 cfg 对跑 + sha256 | 三 CSV 一致；指纹必异 | ✅ T-B01 三 CSV sha256 一致；`input_fingerprint` 必异 |
| E13 | **G13** 对齐 | 样例 run `alignment.json` | `residual < 1e-8` | ✅ T-D01 `alignment.reconcile.residual == 0` |
| E14 | **G14** 依赖零增量 | `git diff -- pyproject.toml uv.lock` + `uv lock --check` | 零 diff；exit 0 | ✅ 两文件零 diff；`uv lock --check` exit 0 |

## 6. F 组：提交与文档（3 项）

| ID | 验收项 | DoR | 证据出口 | 实测 |
|----|--------|-----|----------|------|
| F1 | 提交原子：**6 新增 + 8 修改** = `core/trace.py`、`scripts/trace_report.py`、4 测试文件（新增）+ `core/config.py`、`core/engine_v2.py`、`cli.py`（B2 修改）+ `web/streamlit_app/pages/01..05` 五处标注（B3 修改，F-S8-P061-2）；**须用户明确授权后才可 commit**；B1/B2/B3 各自独立 commit | E1-E14 + 用户授权 | `git show --stat` | ✅ 用户授权（2026-11-24）后按依赖序三批独立 commit：`7bf6b38`（B2 采集+seam）/ `64552d6`（B1 报告）/ `cc36422`（B3 视图+e2e）；每批前 black + 子集验证（25 / 8 / 4 passed） |
| F2 | CI：本批**不改 workflows**；若用户指示 push，CI 四 job 全绿后回填 run id | F1 | `gh run view` | ✅ push `4367775..05f627b`；CI run **45412361688** 四 job 全绿（arch-check 51s / test 3.11 4m7s / lock-check 8s / test 3.12 5m7s） |
| F3 | 文档回填：本文件 **64** 项实测列；PROGRESS §3.112 Step 7-10 条目；IMPL §5 门禁表；CHANGELOG 按仓库惯例判定 | F2 | 读回 | ✅ 本文件 64/64；PROGRESS §3.112 Step 7-10 + F1/F3 已登记；CHANGELOG [Unreleased] ### Added 增 P-061 条目；IMPL §5 门禁表与 §11 记录同源（Step 9 读数已落） |

---

## 7. 范围外与遗留登记（不参与 64 项计数）

| ID | 事项 | 级别 | 处置 |
|----|------|------|------|
| **U-P061-7** | P-045 `core/stops.py` 接入回测主链 | 独立批次 | 本批**不做**；`CLOSE_REASONS` 仅 3 值 + `unknown`，`stop_*` 保留不产生 |
| **U-P061-10** | B3 是否引入 Lightweight Charts | 决策 | 本批**不引入**（V1 内联 SVG）；`--sqlite`（Datasette）同属可选，不交付 |
| **U-P061-6** | CI 接入 trace 自检 | 决策 | 本批**不接入**（三期后再议） |
| **G-09** | Streamlit 5 页为 demo 假数据 | 遗留 | B3 仅加「demo 数据」标注，**不改业务逻辑** |
| **engine_v3_vector** | 无订单/成交，不可追溯 | 范围外 | 本批不覆盖 |
| **F-20 语义** | `retry_count` = collector 自计数（非引擎字段） | 口径 | 已在 DESIGN §7.1 / IMPL T-B08 固化；Step 10 复查无误读 |
| **F-18 语义** | 两级产物：核心缺→exit 1；辅助缺→missing[]+0 | 口径 | RESEARCH S9 / DESIGN §9.1 / IMPL T-C03 三处已同步；Step 8 复核一致性 |

## 8. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **64**（A 6 + B 9 + C 12 + D 20 + E 14 + F 3 = 64，逐表行数机械计数） |
| Step 7 实测列状态（产出时） | `[待 Step 9]` **61** + `[待 Step 10]` **3**；`✅` **0**；`❌` **0** |
| Step 9 实测列状态（回填后） | `✅` **61** + `[待 Step 10]` **3** = 64；`❌` **0**；机检脚本按 ID 精确替换 **61/61** 次 |
| Step 10 目标状态 | `✅` **64**；`[待 Step 9]` **0**；`[待 Step 10]` **0**；`❌` **0**；**64 = 64 ✓** |
| 用例计数 | **37** = T-A 10 + T-B 15 + T-C 8 + T-D 4 |
| D 组计数 | **20 行**（A 5 + B 8 + C 4 + D 3） |
| 目标计数链 | collect **1594** = 1557 + 37；black **336** = 330 + 2 源 + 4 测试；mypy **162** = 160 + 2；四包阈值 = 各包基线 −0.5pp；`core/trace.py` ≥80% 自身 |

> **RULE-2 统计溯源**：64 = 6 + 9 + 12 + 20 + 14 + 3；61 + 3 = 64；37 = 10 + 15 + 8 + 4；20 = 5 + 8 + 4 + 3；1594 = 1557 + 37；336 = 330 + 6；162 = 160 + 2。
> **RULE-5 声明**：Step 1/3/5/7 作者 **DeepSeek-V4.1-Flash**；Step 2/4/6 复审为 **GLM-5.3-Flash**（≠ 作者）；Step 8/9/10 计划由非作者执行。

---

## 9. Step 7 → Step 8 交接

1. **核计数链**：1557 + 37 = **1594**；10 + 15 + 8 + 4 = **37**；330 + 6 = **336**；160 + 2 = **162**；64 = 6 + 9 + 12 + 20 + 14 + 3；61 + 3 = 64。绝对基线以 Step 9 独立复跑为准。
2. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **61**、`[待 Step 10]` 须为 **3**；任何 `✅` 出现即违规。
3. **核 ID 口径**：D 组 20 行覆盖全部 37 例；T-B14 含 F-17 终扫断言；T-B08 用 collector `retry_count`（F-20）；T-C03 用两级产物（F-18）；T-B04 用 `N_days=5`（F-21）。
4. **核 B1 schema 归属（已知待核，非缺陷）**：IMPL §1.1 将 `core/trace.py` 归 B2，但 B1 报告需要列名常量；若 B1 在脚本内自带常量则与 B2 存在**临时重复**，Step 8 需确认是否改为「B1 仅引用字面量、B2 起单一来源」，并登记 F 号。
5. **核不做清单**：不接 P-045 stops；不引入 SQLite/Datasette/Lightweight Charts；不改 CI；不改 Streamlit 业务逻辑；不覆盖 `engine_v3_vector`；不重录 golden；不改 P-059 资产；不新增依赖。
6. **核三处一致**：两级产物规则（RESEARCH S9 / DESIGN §9.1 / IMPL T-C03）、`retry_count` 事实源（DESIGN §7.1 / IMPL T-B08）、`TraceConfig.out_dir` 类型（DESIGN §5.1 / IMPL T-A01）。

---

## 10. Step 8 一致性复审（2026-11-24，GLM-5.3-Flash ≠ 作者，RULE-5）

> 方法：五文档交叉 Grep 机械扫描（旧口径 `36 例 / 334 / X1-X13 / 00_*.py / 两条创建路径` 在 P-061 活跃文档零残留，仅 REVIEW 历史 evidence 行合法保留）+ §9 交接 6 条逐项核 + 计数链复算。**0×P0/P1 + 2×P2 + 3×P3，当轮全闭合**；64 项计数与零预填状态不受影响（复审后机检复跑：逐组行数 6/9/12/20/14/3、`[待 Step 9]` 61 + `[待 Step 10]` 3 不变）。

| ID | 级别 | 发现（证据） | 修订落点 |
|---|---|---|---|
| **F-S8-P061-1** | P2 | B1（`scripts/trace_report.py`）先于 B2（`core/trace.py`）落码，schema 常量必然临时双源；无收敛机制则 B2 后词表漂移（§9 交接第 4 条待核项） | **决策**：B1 临时自带常量 + **S5-2 强制收敛为 `from core.trace import`**；IMPL §4.3 落码要点 + §5 S5-2 验收 + 本文 B2 行 |
| **F-S8-P061-2** | P3 | F1 提交清单「6 新增 + 3 修改」漏 B3 的 `web/streamlit_app/pages/01..05` 五处标注修改 | 本文 F1 改「6 新增 + **8** 修改」 |
| **F-S8-P061-3** | P3 | DESIGN §11.3 T-C03 缺 F-18 两级产物显式化（IMPL T-C03 已有对照组，DESIGN 测试表滞后） | DESIGN §11.3 T-C03 补两级断言 |
| **F-S8-P061-4** | P3 | RESEARCH §13.4.2 `trace_order.retry_count` 来源仍标 "order"，与 DESIGN §7.1（F-20 collector 自计数）不一致 | RESEARCH §13.4.2 改 collector 自计数 |
| **F-S8-P061-5** | P2 | RESEARCH §13.4.3 `qty_by_side` 仍两方向且缺 signed 恒等式说明，与 DESIGN §8 四方向公式（F-13）不一致——期货/融券下 G13 假失败隐患 | RESEARCH §13.4.3 改四方向 + 补 signed 恒等式 |

**三处一致复核结论**：两级产物（RESEARCH S9 ✓ / DESIGN §9.1 ✓ / IMPL T-C03 ✓）；`retry_count` 事实源（DESIGN §7.1 ✓ / IMPL T-B08 ✓ / RESEARCH §13.4.2 本轮修复）；`out_dir: Path | None`（DESIGN §5.1 ✓ / IMPL T-A01 ✓）。
**计数链复算**：1594 = 1557 + 37；37 = 10 + 15 + 8 + 4；336 = 330 + 6；162 = 160 + 2；64 = 6 + 9 + 12 + 20 + 14 + 3；61 + 3 = 64——全部吻合。
**B1 schema 归属裁决**（§9 交接第 4 条）：见 F-S8-P061-1——B1 期允许临时常量，B2 验收强制收敛，消除双源。

---

## 11. Step 9 执行记录（TDD 实现 + 门禁，2026-11-24）

> 执行者 GLM-5.3-Flash / DeepSeek-V4.1-Flash 交替（RULE-5：作者 DeepSeek-V4.1-Flash）；已 commit（`7bf6b38` / `64552d6` / `cc36422`，见 F1）。

**落码顺序（S5-1..S5-5，与 IMPL §5 一致）**：

| 步 | 交付 | 实测 |
|---|---|---|
| S5-1 | `scripts/trace_report.py`（B1 临时常量）+ `test_p061_trace_report.py` 8 例 | 8 passed；无生产改动 |
| S5-2 | `core/trace.py` + `test_p061_trace_collector.py` 10 例；**报告收敛 `from core.trace import`** | 18 passed；`core/trace.py` 94.53% |
| S5-3 | `core/config.py`（+2 字段）/ `core/engine_v2.py`（S1-S8 + 终扫）/ `cli.py`（+2 参数）+ `test_p061_trace_seams.py` 15 例 | 33 passed；G1-G3/G11/G12 绿 |
| S5-4 | 视图时间轴（B1 已含）+ Streamlit 5 页标注 + `test_p061_trace_e2e.py` 4 例 | 37 passed；G4/G13/G14 绿 |
| S5-5 | 全门禁 G1-G14 + covA 读数 | 见 §5/§8 实测列 |

**门禁读数**：collect **1594**（1593 passed + 1 skipped）/ `-k p061` **37** / golden **22** / p059 **63** / mypy **162·0** / black **336** / 四包 **89.82 / 87.95 / 74.54 / 93.54%** / `core/trace.py` **94.53%** / 不变式 **11** / 契约 **6** / 场景 **18 条 7 层** / lint-imports **3 kept** / `uv lock --check` **exit 0**。

**Step 9 观察（2×P3，处置已落地）**：

| ID | 级别 | 观察 | 处置 |
|---|---|---|---|
| **F-S9-P061-1** | P3 | T-B03 测试函数名含 `p059` 字面量，使 `-k p059` 由 63 变 64（G3 读数漂移） | 改名 `test_t_b03_matches_recorder_buckets`；复跑 **63 passed** |
| **F-S9-P061-2** | P3 | T-D04 在长进程中存在系统性变慢（figure/GC），「3 次中位数」被成对后跑者污染（实测 +23% 假超限）；`finalize` 自身仅 5-15ms（<2%） | 计时口径限定 `engine.run()` + **3 轮取最小值**（交替先后顺序），docstring 说明理由；复跑通过 |

**环境说明**：本机 Tk 数据不完整，`tests/test_invariants.py::test_engine_emits_invariant_report` 在长套件中偶发 `_tkinter.TclError`（单独运行与 `MPLBACKEND=Agg` 下均通过，CI 已设该环境变量）。G1 以 `MPLBACKEND=Agg` 复跑取读数，与本批改动无关。

---

## 12. Step 10 验收与异构复审（2026-11-24）

> 复审人 GLM-5.3-Flash ≠ 批次作者 DeepSeek-V4.1-Flash（RULE-5）；报告见 [REVIEW_p061_step9](REVIEW_p061_step9.md)。

**门禁独立复跑（全部吻合）**：`-k "p061 or golden"` **59** / `-k p059` **63** / 不变式+契约 **17** / mypy **162·0** / black **336** / lint-imports **3 kept** / `uv lock --check` **exit 0** / 场景 **18 条 7 层**。
**DoD §15 六条**：全部 ✅（G1-G14 读数留档 / 37 例计数一致 / T-B01 sha256 / T-D01 residual 0 + 五问 / trace.py 94.53% + 四包不低 0.5pp / diff 面仅三文件 + web 5×+1）。
**发现**：**F-S10-P061-1（P3）**——T-B14 注释声称 run 末终扫，实际走日末差分；终扫 PENDING→dropped 分支无直接断言 → T-A04 追加终扫断言 + T-B14 docstring 修正，复跑 37 绿、black 336。
**判定**：**PASS-WITH-COMMENTS（1×P3 当轮闭合）**；技术工作完成。
**F 组状态（F3 回填后，2026-11-24）**：F1 ✅ 用户已授权，三批 commit `7bf6b38` / `64552d6` / `cc36422` + docs 关闭 `05f627b`；F2 ✅ push + CI run **45412361688** 四 job 全绿；F3 ✅ 本文件 64/64。
