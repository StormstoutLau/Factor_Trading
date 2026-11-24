# DESIGN：P-060 模块级模拟数据验证扩面（unit → integration → full）

> **批次**: **P-060**（P-060a / P-060b / P-060c 三批，U-P060-2）
> **档位**: **T1**（实现落在 `tests/` + `scripts/coverage_snapshot.py`；**零生产代码改动**，见 DD9）
> **上游**: [RESEARCH_p060](RESEARCH_p060_module_verification.md)（U-P060-1..6 全闭合）、[REVIEW_p060_step2](REVIEW_p060_step2.md)（PASS，F-1/F-3/F-4/F-7 已回写）、[P-059 DESIGN](DESIGN_p059_data_validation.md)（体例与资产基座）
> **基线**: `b1afe29`；collect **1503**（1502+1 skip）/ golden **22** / `-k p059` **63** / covA **85.80%**（10432/12165）/ covB **44.07%**（2499/5670）
> **作者**: DeepSeek-V4.1-Flash（Step 4 必须 reviewer ≠ 作者，RULE-5）
> **状态**: Step 3 DESIGN 定稿 → 待 Step 4 设计复审

---

## 1. 目标与非目标

### 1.1 目标（可验收）

| # | 目标 | 验收读数 |
|---|---|---|
| O1 | 生产四包行覆盖率从 **85.80%** 提升到 **≥88.0%** | covA JSON：covered/total ≥ 10705/12165 |
| O2 | 三个结构空洞补齐：`market_gateway` 0%→**≥75%**、`rebalance` 34.6%→**≥80%**、`factor` 64.7%→**≥80%** | covA 单文件读数 |
| O3 | 可选配置分支与异常契约有独立 oracle（非 golden） | 每模块 ≥1 个闭式/不变量断言（I4） |
| O4 | 新增 `-k p060` 聚合门禁，用例自带 T-ID 可追溯 | `pytest -k p060` 收集数 = 计划数 |
| O5 | 覆盖率快照可一键复现，棘轮可判定 | `scripts/coverage_snapshot.py --check` exit 0 |
| O6 | 106 模块三标签分类完成，legacy 不进入覆盖率考核 | `docs/MODULE_CLASSIFICATION_p060.md` 覆盖 106/106 |

### 1.2 非目标（明确不做）

1. **不改生产代码**（DD9）：全部测试侧替身；确需 seam 走 U-P060-5 白名单 + 单列 U 项。
2. **不新增 golden**、不重录 golden 22（I1）。
3. **不改 P-059 场景库**（18 条、63 用例、断言原语、`verify_scenario.py` 语义，I3）。
4. **不设 CI 硬门禁、不新增 CI job**（DD7）：覆盖率仅本地/手动快照；CI 接入留 U-P060-7。
5. **不追求 filter/agents 覆盖率**（S10）：只做分类 + 契约声明。
6. **不引入 Hypothesis / 新依赖**（S12）。

---

## 2. 设计决策（DD1-DD10）

| ID | 决策 | 依据 |
|---|---|---|
| **DD1** | **复用既有四套夹具**：unit 用内存 `pd.DataFrame`/`pd.Series`；集成用 `_synth_fixture` + `_scenarios_cases`；契约用 `_synthetic_data`；**不新增第五套生成器** | S11 / G-P060-10 |
| **DD2** | **扁平命名** `tests/test_p060<a|b|c>_<topic>.py`，用例函数 `test_p060a_u01_<slug>`；docstring 首行固定格式 **`T-ID | oracle=closed-form|cross-check|invariant|manual|contract|boundary|state|manual-calendar|priority|pending-semantics`**（F-16 / F-S7-P060a-3） | 与 P-059 扁平先例一致；便于 `-k`、映射与 Step 6 抽检；实测新增 5 类限定变体 |
| **DD3** | **oracle 阶梯强制**：计算类必须闭式/手算（S4）；行为类用不变量或独立重算；golden **不得**作为唯一 oracle | S2 / A2 |
| **DD4** | **覆盖率脚本独立于 pytest**：`scripts/coverage_snapshot.py` 只跑命令、解析 JSON、比较基线；不写 conftest、不进 addopts | U-P060-6 / A28 |
| **DD5** | **分支覆盖独立命令**：`--cov-branch` 单跑，产物 informational，不 blocking；不与行覆盖合并门禁 | U-P060-6 / I10 |
| **DD6** | **三标签分类**：`production` / `library` / `legacy-research`；legacy 仅契约/能力声明，不追覆盖率 | S10 / G-P060-11 |
| **DD7** | **本批不动 CI**：`.github/workflows/tests.yml` 零 diff；快照由本地命令 + CHECKLIST 记录 | U-P060-3（非硬门禁）/ 降低 CI 结构风险 |
| **DD8** | **缺陷独立 commit**：P1/P2 当批修但单 commit + 复现用例 + PROGRESS 条目，复用全部门禁 G1-G10 | U-P060-4 / F-8 |
| **DD9** | **零生产改动**：`core/ live/ services/ strategies/ filter/ agents/` 的 `git diff` 必须为空；例外走白名单审批 | U-P060-5 |
| **DD10** | **测试确定性与时长**：无网络/当前时间/随机；单文件 ≤10s，全量 ≤300s | S3 / I7 / I10 |

---

## 3. 文件布局

```
tests/
  test_p060a_execution_cost.py        # T-A01..A05
  test_p060a_factor_branches.py       # T-A06..A10
  test_p060a_rebalance_triggers.py    # T-A11..A15
  test_p060a_tracker_api.py           # T-A16..A19
  test_p060a_registry_diagnostics.py  # T-A20..A23
  test_p060b_market_gateway.py        # T-B01..B05
  test_p060b_bus_protocol.py          # T-B06..B09
  test_p060b_trading_worker.py        # T-B10..B12
  test_p060b_ws_api.py                # T-B13..B16
  test_p060b_adapters_frames.py       # T-B17..B19
  test_p060c_layer_gates.py           # T-C01..C04
scripts/
  coverage_snapshot.py                # 新增：快照 + 棘轮比较（唯一新脚本）
docs/
  coverage_baseline.json              # 新增：四包 + 分支基线（小文件，入仓）
  MODULE_CLASSIFICATION_p060.md       # Step 9 产出（B4）
```

> 合计 **11 个测试文件 + 1 脚本 + 2 文档**；预计 **104 例**（P-060a 参数化细化 54、P-060b 38、P-060c 12；Step 5 记录 F-18）。

---

## 4. P-060a 单元层（core，54 例 / core ≥88%）

### 4.1 execution 成本与校验（5 组，T-A01..A05）

| T-ID | 目标 | oracle（闭式） |
|---|---|---|
| T-A01 | 佣金下限：`amount=1000, rate=0.0003` → 佣金 `max(0.3,5)=5`，加滑点 `1000×0.001=1` → **成本 6.0** | 手算 |
| T-A02 | 印花税单边：买入 10000 → `5+10=15`；卖出 → `5+10+10=25`；差值 = 印花税 10 | 手算对拍 |
| T-A03 | 期货资产：`exchange_fee>0` 计入、`stamp_tax` 恒 0（即使 SELL） | 自定义 `AssetCost` 闭式 |
| T-A04 | **零金额公式一致性**：`_calculate_cost(0)` 由 `max(0×rate, commission_min)` 推导 = **5.0**；docstring 标 `oracle=closed-form(pending-semantics)` + 「引擎不生成 0 金额订单（S09 已证拒绝路径）」；**该断言只锁定公式一致性，不认定业务期望**；U-P060-8 若裁定为缺陷 → 断言改 0.0 + 回归用例（DD8） | 公式推导（F-12 已收窄） |
| T-A05 | 价格校验：`reference<=0` → False；偏差 0.19 → True；0.20 → True（严格 `>0.2` 才拒）；0.21 → False | 边界闭式 |

> 附加：`simulate_market_impact` 3 组（adv≤0→0；ratio×0.01；cap 0.05）并入 T-A05，标注「公共 API、无生产调用」。
> 异常旁路：`execute` 失败 → `(False, None)` + sink 收到 `("execution", exc)`，并入 T-A03。

### 4.2 factor 可选分支（5 组，T-A06..A10）

| T-ID | 目标 | oracle |
|---|---|---|
| T-A06 | `_winsorize_mad`：`[1,2,3,100]`，n=3 → median 2.5 / MAD 1.0 / 界 `[-0.5,5.5]`；输出全部 ∈ 界内且单调不减 | 对拍（注意 tanh 软截断会压缩界内值，**不得**断言原值保持） |
| T-A07 | `_winsorize_percentile`：0..9、pct=(0.05,0.95) → 界 `[0.45,8.55]` | 分位闭式 |
| T-A08 | `_winsorize_sigma`：std=0 行原样；正常行界 `mean±n·std` | 公式 |
| T-A09 | `_fill_missing` 3×3 矩阵：`median/mean/zero` × mask(`DataFrame`/`Series`/`None`)；**不可交易 NaN 必须保留** | 手算填充值 + 掩码语义 |
| T-A10 | `_neutralize` 退化列（常数列/全 NaN）→ 不抛错 + `neutralize_skip_counts` 对应桶 +1；`reverse_factor` 前后 Spearman = **−1**；`_standardize` 均值≈0/方差≈1 | `invariant` + `cross-check`（F-16 标注统一） |

### 4.3 rebalance 触发器（5 组，T-A11..A15）

| T-ID | 目标 | oracle |
|---|---|---|
| T-A11 | `FixedInterval` 四频率（daily/weekly/monthly/N_days）在固定 20 日索引上的日期集合 | 手算日历表 |
| T-A12 | `Conditional` 三触发：信号 L2 变化≥阈值 / 回撤≥阈值 / 波动率≥阈值；**首次调用无 last → 不触发但更新状态** | 手算 + 状态断言 |
| T-A13 | `_calculate_signal_change`：无交集 → **1.0**；相同 → 0；`[1,0] vs [0,1]` → √2 | 闭式 |
| T-A14 | `Hybrid`：`min_days` 抑制；fixed 优先；conditional 次之；`max_days` 兜底；`last=None` 时跳过间隔判断 | 状态机表 |
| T-A15 | `build_trigger` 未知 method → 返回 `FixedIntervalTrigger`；`RebalanceCalendar` 的 `dates/stats/next` 与空边界 | 行为 + 边界 |

### 4.4 tracker 公共 API（4 组，T-A16..A19）

| T-ID | 目标 |
|---|---|
| T-A16 | `get_position_weights`：`total<=0` → 空 Series；空仓 → 空；多头计入；`allow_negative_stock` 下负股计入；期货用 **notional_value** |
| T-A17 | `get_sector_exposure`：`total<=0` → `{}`；industry 缺失 → skip；期货 0 持仓 → skip；同行业累加 = 权重和 |
| T-A18 | 期货逐日结算：无 specs/无期货→None；盈亏入金、保证金重算、settle_base 重置、proxy 回退（P-050 D2） |
| T-A19 | `validate_positions` / `get_performance_metrics` / `reset`：错误清单、指标口径（年化/回撤）、重置后净值 = 初始资金 |

### 4.5 registry / diagnostics / event_log（4 组，T-A20..A23）

| T-ID | 目标 |
|---|---|
| T-A20 | `PluginRegistry`：register 重名策略、unregister 不存在 → False、get 未注册 → None、create 工厂异常透传 |
| T-A21 | `create_or_default`：未注册时用 default；config 透传 |
| T-A22 | 六类注册装饰器（optimizer/trigger/filter/guard/agent/strategy）幂等与覆盖语义 |
| T-A23 | `diagnostics` 错误分类分支（ValueError/KeyError/其他）+ `event_log` 轮转/上限 + 订阅/重置（`change_report` 属 P-060c，见 F-S7-P060a-5） |

---

## 5. P-060b 集成层（services/live，目标 38 例）

### 5.1 market_gateway（5 组，T-B01..B05）——0%→≥75%

| T-ID | 目标 | oracle |
|---|---|---|
| T-B01 | `SyntheticSource` 确定性：同 seed 两实例序列**逐值相等**；`tick_seq` 从 1 严格单调；价格下限 0.01 | 确定性 + 不变量 |
| T-B02 | `ts` 口径：`hz=2 → seq/2`；`hz=0 → float(seq)`；默认 `hz=2.0` | 闭式 |
| T-B03 | `MarketGateway.run_once`：publish 载荷键固定 `type/tick_seq/ticks[{symbol,last,ts}]`；空 ticks **不** publish；返回 `len(ticks)` | 协议契约 |
| T-B04 | `serve`：`hz<=0 → interval=1.0`；`stop_event` 预置 → 零轮；`bus=None` 不发心跳；`bus` 有 → `set_key(heartbeat_key, ttl)` | **monkeypatch 注入 fake bus（测试侧，不改生产签名）**；白名单仅在 monkeypatch 不可行时启用且须先提 U 项（F-13） |
| T-B05 | `_build_from_env` + `_parse_args`：env 覆盖（空段过滤、hz、channel）、CLI 四参数、`--once/--embedded` | 环境矩阵 |

### 5.2 bus 协议（4 组，T-B06..B09）

| T-ID | 目标 |
|---|---|
| T-B06 | `SyncRedisBus` 协议级 fake：publish JSON 序列化、`stream_add` 字段、`stream_read/ack/autoclaim/pending` 往返 |
| T-B07 | `InMemoryBus` 与 `SyncRedisBus`（fake 后端）**同消息同结果**（差异对拍） |
| T-B08 | `AsyncRedisBus` / `InMemoryBusAdapter` 委托一致性（同 4 个原语） |
| T-B09 | `get_key` 缺失 → None；`delete_key`/`close` 幂等；连接失败 → 异常类型 + 消息关键词（S6），不静默 |

> 真实 Redis：`P060_REDIS_URL` 存在则跑真路径，否则 `pytest.skip("no redis")` 并在 CHECKLIST 记录。**不新增依赖**。

### 5.3 trading_worker（3 组，T-B10..B12）

| T-ID | 目标 |
|---|---|
| T-B10 | 组装路径：`--with-market` 时导入 `run_embedded` 并起线程（注入 fake `serve`，断言调用一次） |
| T-B11 | 缺 config / 非法 args → 明确异常 + 非零退出（不静默） |
| T-B12 | 一次 tick 循环：心跳 `set_key` + 订单流转到 bus stream（fake bus） |

### 5.4 ws_routes / api（4 组，T-B13..B16）

| T-ID | 目标 |
|---|---|
| T-B13 | `mount_ws` 注册 `/ws/orders`、`/ws/market`（路由表断言） |
| T-B14 | 鉴权失败 → close code 4xxx + 不订阅；慢消费者 → 丢弃/分片策略（读码后定断言） |
| T-B15 | hub 缺失 → 不挂载或降级（断言不抛错） |
| T-B16 | `api` 非主路径端点状态码（404/405/422）+ 异常 → 500 且 event_log 落账 |

### 5.5 live adapters 录制帧（3 组，T-B17..B19）

| T-ID | 目标 |
|---|---|
| T-B17 | `ctp` 录制帧字段映射（不触网、不 import SDK 时降级） |
| T-B18 | `broker_api` 未知帧忽略 + 错误帧 → 诊断 |
| T-B19 | 能力声明：无 SDK 环境下 `connect` 抛明确异常（类型+关键词），不得静默成功 |

---

## 6. P-060c 全量层与遗留（目标 12 例 / 文档为主）

| T-ID | 交付 | 验收 |
|---|---|---|
| T-C01 | `scripts/coverage_snapshot.py`：`--packages production|all`、`--branch/--no-branch`、`--check docs/coverage_baseline.json`、`--json-out` | 两次运行结果一致；`--check` exit 0/1 语义明确 |
| T-C02 | `docs/coverage_baseline.json`：四包 + 分支基线（A/B 两口径） | 与 Step 2 读数一致（85.80/44.07/87.95/74.54） |
| T-C03 | `test_p060c_layer_gates.py`：① 四包基线常量自洽（covered≤total、百分比复算）；② `-k p060` 收集数 = 计划数；③ golden 22 快照名清单不变；④ `verify_scenario --list` = 18 | 4 例 |
| T-C04 | `docs/MODULE_CLASSIFICATION_p060.md`：106 模块 × 三标签 + 依据；filter 6 子模块契约测试（`_synthetic_data` 掩码语义） | 106/106 覆盖；契约 3 例 |

---

## 7. 覆盖率目标与增量预算（F-9 定稿）

| 包 | 基线 covered/total | 基线 % | 目标 % | 需增行 | 计划增行（来源） |
|---|---|---|---|---|---|
| core | 7883/9117 | 86.46% | **≥88.0%** | +140 | execution +30 / factor +45 / rebalance **+70** / tracker +10 / registry +5 = **+160** |
| services | 814/1092 | 74.54% | **≥85.0%** | +115 | market_gateway +50 / bus +25 / worker +20 / ws_routes +10 / api +15 = **+120** |
| live | 1489/1693 | 87.95% | **≥90.0%** | +35 | adapters 帧映射 + 能力降级 = +35 |
| strategies | 246/263 | 93.54% | **≥93.5%（不降）** | 0 | 不新增 |
| **四包** | **10432/12165** | **85.80%** | **≥88.0%**（10705） | +273 | 计划 +315 → **88.34%**（10747） |

**单文件关键目标**：`market_gateway` 0→**≥75%**（+50/63）；`rebalance` 34.6→**≥80%**（53→122，**+70**）；`factor` 64.7→**≥80%**（178→220，**+42**，预算取 45）。

> 增量按「补齐未覆盖行的主要分支」估算，不做逐行承诺；Step 9 以实际 covA JSON 回填。**若未达 O2：在 CHECKLIST 登记残余缺口（G-P060-13）+ PROGRESS 记读数，不放宽标准（F-15 / U-P060-9）**。
>
> **基线口径（F-14）**：本文采用 Step 2 重放 JSON（10432/12165）；RESEARCH §3.1 的 10437 为首次采集，两次差 5 行（0.04pp）。`docs/coverage_baseline.json`（T-C02）以 **Step 2 重放 JSON** 为准，并在文件内记 `source=step2-replay`。

---

## 8. 门禁（G1-G10 + 诊断项）

| # | 门禁 | 命令 | 通过条件 |
|---|---|---|---|
| G1 | 全量 | `python -m pytest tests/ -q` | 全绿；collect ≥1503 |
| G2 | golden | `pytest -q -k golden` | **22**，零重录 |
| G3 | P-059 | `pytest -q -k p059` | **63**，场景文件零改动 |
| G4 | P-060 聚合 | `pytest -q -k p060` | 全绿；收集数 = 计划数 |
| G5 | 类型 | `python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples live services`（与 CI 一致，**不含 tests**） | 0 error；files **160 → 161**（新增 `scripts/coverage_snapshot.py` 须全量类型标注，F-11 修正） |
| G6 | 格式 | `black --check .` | 全绿；新增 11 个测试文件 + 1 脚本计入（基线 325 → **337**） |
| G7 | 覆盖率棘轮 | `scripts/coverage_snapshot.py --check` | 四包任一 **≥ 基线 −0.5pp** |
| G8 | 不变式 | `pytest -q tests/test_invariants.py` | 全绿 |
| G9 | 契约 | `pytest -q tests/test_contract_conformance.py` | 全绿 |
| G10 | 场景入口 | `python scripts/verify_scenario.py --list` | 18 条 / 7 层 |

**诊断项（不 blocking）**：D1 行覆盖 JSON 存档；D2 分支覆盖 JSON（`--cov-branch` 独立轮）；D3 `-k p060` 逐文件时长。

**F-8 定稿**：缺陷修复 commit **复用 G1-G10 全集**；若修复导致 golden 必须重录 → 停工升级用户裁决（I1 不可破）。

---

## 9. 分支覆盖落地（U-P060-6）

1. **命令**：`python -m pytest tests/ -q --cov=core --cov=live --cov=services --cov=strategies --cov-branch --cov-report=json:<tmp>`，**独立执行**，不写入 `pyproject.toml` 的 `addopts`（A28：CLI 覆盖 `.coveragerc`）。
2. **产物**：JSON 存 `%TEMP%` + `docs/coverage_baseline.json` 追加 `branch` 小节；不 blocking。
3. **误报**：`while True:`/`if 0:` 不处理（结构性 partial 自动识别）；生成器表达式/条件循环用 `# pragma: no branch`；若设 `[report] partial_branches` 必须保留 pragma 正则（A27 修正）。
4. **基线记录（F-17）**：分支覆盖**首次采集时点 = P-060c 完成后**（T-C01 就跑一次 `--branch`）；P-060a/b 只记录行覆盖快照。采集结果写入 `docs/coverage_baseline.json` 的 `branch` 小节并标 `source=p060c-first`，本批只记趋势，不设阈值。

---

## 10. 生产 seam 与零改动声明（U-P060-5 / DD9）

- 本设计**不修改任何生产文件**；测试侧优先：`monkeypatch`、`unittest.mock`、fake bus/gateway、`tmp_path`。
- **实现单轨（F-13 定稿）**：P-060a/b **一律**用 monkeypatch/mock 注入；**本批默认不启用白名单**。仅当 monkeypatch 不可行（跨 import 位置、全局句柄无法拦截）才提 U 项，**禁止先改生产签名再补审批**。
- 若实测确需 seam，必须**四条全满足**才可提 U 项：① 真实生产语义（Clock/RNG seed/Transport 端口）；② 测试侧替换跨模块/import 位置失效；③ 改动 ≤ 接口参数注入（无测试开关、无 mock wrapper、不重排架构）；④ 单独 commit + T1 复审。
- **禁止**：为测试新增 `_test` 开关、暴露私有属性、在 `__init__` 里加 `testing=False` 分支。

---

## 11. 不变式映射（I1-I10）

| I | 设计落点 |
|---|---|
| I1 | G2；T-C03③ 断言 golden 清单不变 |
| I2 | G1；collect 只增 |
| I3 | G3；P-059 文件零 diff |
| I4 | §4/§5 每个 `production` 模块 ≥1 非 golden oracle（DD3） |
| I5 | T-A03/T-A10/T-B09/T-B11/T-B19：raise 路径有测试或标注不可达 |
| I6 | 零依赖；`pyproject.toml`/`uv.lock` 零 diff（S12） |
| I7 | T-B01 确定性；unit 重复 3 次一致 |
| I8 | G7 棘轮（≥基线−0.5pp） |
| I9 | T-C04 分类清单；变更须裁决 |
| I10 | DD10；单轮 183s 基线，预算 300s |

---

## 12. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 补测变成**行为锁定**（固化错误行为） | 中 | 高 | oracle 阶梯（DD3）；Step 6 复审抽检 ≥20% 用例的期望来源 |
| 覆盖率**注水**（只测 getter/构造） | 中 | 中 | 每模块 ≥1 分支/边界用例；O2 单文件目标 |
| 真实 Redis/CTP 环境缺失 | 高 | 低 | 协议级 fake + skip 理由；不新增依赖 |
| 测试时长突破 I10 | 低 | 中 | 单文件 ≤10s；禁止网络/重 IO |
| 分类争议（filter/agents） | 中 | 低 | T-C04 显式清单 + 用户裁决 |
| 发现 P1/P2 缺陷打断批次 | 中 | 中 | DD8：独立 commit + 复现用例，复用 G1-G10 |

**回滚**：每批独立 commit；新增文件可整体 revert；不触碰既有测试与生产代码，回滚无副作用。

---

## 13. DoD（Step 10 验收口径）

1. G1-G10 全绿，读数留档（CHECKLIST_p060）。
2. covA **≥88.0%**（10705/12165），core ≥88 / services ≥85 / live ≥90 / strategies ≥93.5；`market_gateway` ≥75%、`rebalance` ≥80%、`factor` ≥80%。
3. **P-060c 完成后**分支覆盖 JSON 已采集并写入基线 `branch` 小节（informational，source=p060c-first）。
4. `-k p060` 收集数 = 计划数（±0），全部用例带 T-ID。
5. `git diff` 生产四包 + filter/agents **为空**（DD9）；`pyproject.toml`/`uv.lock` 为空（I6）。
6. golden **22** 零重录；p059 **63**；`verify_scenario --list` **18**。
7. `docs/MODULE_CLASSIFICATION_p060.md` 覆盖 **106/106** 模块。
8. PROGRESS 记录三批读数与残余缺口（若未达 O1/O2，登记而非放宽）。

---

## 14. IMPL 任务映射（B 批 → T 组）

| 批 | T 组 | 文件数 | 预计用例 |
|---|---|---|---|
| P-060a | T-A01..A23 | 5 | 54 |
| P-060b | T-B01..B19 | 5 | 38 |
| P-060c | T-C01..C04 | 1 + 1 脚本 + 2 文档 | 12 |
| **合计** | — | **11 + 1** | **104** |

> 每批独立 commit；P-060a 完成即跑 G1-G10 快照，P-060b 完成再跑，P-060c 收口。

---

## 15. Step 4 设计复审输入

1. **规格映射**：RESEARCH S1-S12 ↔ 本文 DD1-DD10 / §4-§6，是否有未覆盖规格。
2. **oracle 质量**：T-A01/A02/A04/A13、T-B02/B03 的闭式推导是否正确（重点 T-A04 零金额语义是否应登记缺陷而非锁定）。
3. **覆盖率算术**：§7 的 +315 行 → 88.34% 是否成立；`rebalance +70` 与 `factor +42` 的行数假设是否可达（Conditional 60 + Hybrid 35 + Calendar 55 的可执行面）。
4. **门禁可行性**：G4 收集数断言、G5 mypy 口径、G7 脚本 `--check` 语义。
5. **零改动守卫**：DD9 与 T-B04/T-B10 的 fake 注入是否会被判为 seam。
6. **范围**：是否误将 filter/agents 纳入覆盖率考核（应为 P3 分类）。
7. **与 P-059 边界**：是否重复场景层工作；P-059 资产是否零改动。

---

## 16. 待办裁决（Step 4 前）

| ID | 事项 | 建议 |
|---|---|---|
| U-P060-7 | CI 是否接入覆盖率 artifact（DD7 本批不动） | 本批 **不接入**；三批稳定后再议 |
| U-P060-8 | T-A04 零金额成本（=5.0）语义是否登记 P3 缺陷 | **T-A04 仅断言公式一致性**并标 `pending-semantics`；Step 6 裁决：非预期 → 按 DD8 改断言 0.0 + 回归用例 |
| U-P060-9 | `rebalance` 80% / `factor` 80% 的行数假设是否可达 | Step 9 以实测为准；不足则登记残余缺口（G-P060-13），不放宽 O2 |

---

## 17. Step 4 复审修订记录（2026-11-24，F-11..F-17）

> 依据 [REVIEW_p060_step4](REVIEW_p060_step4.md)；本节记录作者对每条发现的**定稿处置**，复审结论保留不改。

| 发现 | 级别 | 处置 | 落点 |
|---|---|---|---|
| F-11 | major | **修正复审假设**：CI mypy 命令（[tests.yml:46](../.github/workflows/tests.yml#L46)）**只查 `scripts`、不查 `tests`**，故 11 个测试文件无影响；真实影响面 = 新增 `scripts/coverage_snapshot.py` 必须全量类型标注，files 160→161 / 0 error。**无需改 `pyproject.toml`** | §8 G5 |
| F-12 | minor | T-A04 收窄为「公式一致性 + `pending-semantics`」；不认定业务期望；U-P060-8 裁决后改断言（DD8） | §4.1 T-A04 / §16 |
| F-13 | note | 实现单轨：一律 monkeypatch/mock；本批默认不启用白名单；禁止先改签名再审批 | §10 + §5.1 T-B04 |
| F-14 | note | 基线以 Step 2 重放 JSON 为准；文件内记 `source=step2-replay`；与 RESEARCH 10437 的 5 行差在本文注明 | §7 注 |
| F-15 | note | 未达 O2 → 登记 **G-P060-13** 残余缺口 + PROGRESS，不放宽 | §7 注 |
| F-16 | note | docstring 首行统一 `T-ID \| oracle=...`；T-A04/T-A10 已按新标签修正 | §2 DD2 / §4.1-4.2 |
| F-17 | note | 分支覆盖首次采集固定为 **P-060c 完成后**（source=p060c-first）；P-060a/b 只记行覆盖 | §9 第 4 条 / §13 DoD-3 |
| F-18 | note | **Step 5 参数化细化**：P-060a `42 → 54` 例（子用例参数化拆分），总数 `92 → 104`；覆盖率预算与 O2 不变 | §3 / §4 / §14 |
| F-S7 | note | **Step 8 一致性修复（7 条全闭合，CHECKLIST §9.1）**：① T-A16 重号 → rebalance 对拍组改 **T-A11f**；② IMPL §4/§5 例数同步 16/17/7/4；③ DD2 oracle 词表扩为 **11 值**（+boundary/state/manual-calendar/priority/pending-semantics，docstring 零改动）；④ T-A18 卡片 5 分支 / T-A19a 五类错误；⑤ T-A23 删 `change_report`（属 P-060c）；⑥ §4.4 T-A18 改「期货逐日结算（P-050 D2）」；⑦ IMPL 状态行与本批 G5/G6 口径（160/330） | DD2 / §4.4 / §4.5 |
| F-S9 | note | **Step 9 独立复跑（59/59 ✅，GLM-5.3-Flash ≠ 作者，异构成立）**：G1 1556+1 / G2 22 / G3 63 / G4 54 / G5 160/0 / G6 330 / G7 88.07%（factor 76.7% 登记 G-P060-13） / G8 11 / G9 6 / G10 18/7 / 范围空 / 依赖零 diff；MemoryError 为环境问题 | §8 / §13 |
