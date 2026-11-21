# CHECKLIST：P-052 实盘安全闸门（safety / circuit_breaker / compliance / guard 扩展 / live 适配层）

> **批次**: P-052 · **Step 7** · 日期 2026-11-21 · **判档 P2**
> **上游**: [IMPL_p052](IMPL_p052_live_safety_gate.md)（C-1..C-15 / 13 项逐处代码 / 70 例映射 / D-1..D-6 偏差）；[DESIGN_p052](DESIGN_p052_live_safety_gate.md)（D1-D14 + D-G1..D-G9 / I1-I12 / §5 阈值表）；[REVIEW_p052_step6](REVIEW_p052_step6_impl.md)（1 P1+2 P2+4 P3 → 7/7 修复，0 P1 残留）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **状态**: Step 9 执行完成（2026-11-21），M12 + T9 + C6 + I12 + DG9 + D14 = **62 项全部 ✅**，`[待 Step 9]` 清零
> **基线读数（@`1f950c6`，P-051c 关闭态 2026-11-21）**: pytest **1144** / `-k golden` **22** / mypy **122 files 0** / black `--check .` **247** / `tests/*.py` **124** / `core/*.py` **48**
> **目标读数**: pytest **1214**（+70）/ `-k golden` **22**（零重录）/ mypy **125 files 0**（`live` 纳入则 128）/ black **261 unchanged**（+14）/ `tests/*.py` **132** / `core/*.py` **51**

---

## 1. M 组：模块与代码（12 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| M1 | `core/safety.py` 新建：`KillLevel/KillAction` 两枚举 + `KillEntry/KillState/KillCommand/KillDecision` 四契约 + `initial_kill_state/apply_command/effective_kill/allows/to_dict/from_dict` 六函数 + `FaultType/FaultAction/FaultPolicy` + `default_fault_policy/decide_fault`；**零 I/O、无 `datetime.now`、无随机**（I1）；`FaultPolicy` 含 `max_retries`（F-D7） | 无 | 读码 + K1-K14 | ✅ `core/safety.py` L16/L24 两枚举、L36/L49/L56/L69 四契约、L78/L83/L102/L121/L128/L146 六函数、L169/L178/L190/L197/L223 S7；grep `datetime.now|time.time|random.|open(` 仅命中 L3 docstring |
| M2 | `core/circuit_breaker.py` 新建：`CircuitState/CircuitConfig/CircuitSnapshot/CircuitDecision` + `evaluate_circuit/allows_open/allows_close`；**判定顺序 = 严重度优先**（HALTED 先于 DERISK_ONLY，D-1）；基准 ≤0 视为未触发（F-D9）；零 I/O（I1） | 无 | 读码 + B1-B9 | ✅ `core/circuit_breaker.py` L9/L18/L27/L37 四契约、L45 `evaluate_circuit`（L52 rejects 先判）、L78/L83；B1-B9 全绿 |
| M3 | `core/compliance.py` 新建：`AbnormalTradeType`（8 值）+ `ProgrammaticTradingReport`（含 21 字段 + `missing_required`）+ `RateLimitConfig/RateLedger` + `day_key/record/cancel_ratio/check_rate/ledger_to_dict/ledger_from_dict` + `build_audit_payload` + `AUDIT_RETENTION_YEARS_DEFAULT/MAX`；**零项目内 import**（C-8/D-2）；秒级只查当前秒桶（F-I2）；零 I/O（I1） | 无 | 读码 + C1-C10 | ✅ `core/compliance.py` L18 八值枚举、L32/L77/L87 三契约、L96-L160 七函数、L169/L170 常量；grep `^from core|^import core` 无命中；L128 只查当前秒桶 |
| M4 | `core/guard_pipeline.py` 扩展：`GuardContext` **+9 字段且全部带默认**（I11）+ 5 新 Guard（`MaxOrderValue/PriceBand/IndustryExposure/OrderRate/SelfTrade`）+ `GuardPipeline.live_safe()` 八件套；`PriceBandGuard` 不 import `filter`（D-G6/F-D5）；既有 6 Guard 与三预设零改动 | 无 | 读码 + G1-G15 + 既有 guard 测试 | ✅ `GuardContext` 9 字段全带 `field(default_factory=...)`/字面默认；5 Guard 类齐备；`live_safe()` 八件套；grep `from filter` 无命中；G1-G15 全绿 + 既有 guard 测试在全量 1214 中零回归 |
| M5 | `core/engine_plugins.py`：`GuardPlugin.__init__` 增 `on_error: str = "open"`，异常分支按参数返回 `(True, [])` 或 `(False, ["guard_error: …"])`；**默认 open → 既有 P-026 行为不变** | M4 | 读码 + 既有插件测试 | ✅ `core/engine_plugins.py` `GuardPlugin.__init__` 含 `on_error="open"`；异常分支 `if self.on_error == "closed"` 返回阻断；全量 1214 零回归 |
| M6 | `core/event_log.py`：`EventType` +8 审计常量 + 模块级 `AUDIT_EVENT_TYPES` frozenset；**`EventLogEntry`/`append` 签名零改动**（I12）；旧 JSONL 可读 | 无 | 读码 + A1-A6 | ✅ `EventType` 增 `AUDIT_INTENT..AUDIT_CIRCUIT` 8 常量 + `AUDIT_EVENT_TYPES` frozenset(8)；`EventLogEntry`/`append` 未改（A2 断言签名 = `[self,event_type,payload,source]`）；A1-A6 全绿 |
| M7 | `core/interfaces.py`：`AuthConfig` frozen dataclass（`mode/api_key_env/bind_host/require_tls/allowed_origins/enable_401_403` 六字段带默认）；仅契约，无中间件实现（归 P-054） | 无 | 读码 + S1-S2 | ✅ `core/interfaces.py` 末尾 `@dataclass(frozen=True) class AuthConfig` 六字段；`from dataclasses import dataclass` 已补；S1/S2 全绿 |
| M8 | `live/__init__.py` + `live/safety_store.py` 新建：`SafetyStateStore.save`（临时文件 + `flush` + `fsync` + `os.replace`）与 `load`（缺失/损坏/非 dict → `None`）；`live/__init__` 仅 docstring | 无 | 读码 + L8 | ✅ `live/safety_store.py` L12 类，`save` 用 `mkstemp+fsync+os.replace`、`load` 捕获 `JSONDecodeError/OSError` 返 `None`；`live/__init__.py` 仅 docstring；L8/E4 全绿 |
| M9 | `live/safety_gate.py` 新建：`SafetyDecision` + `SafetyGate`（`pre_trade_check` 顺序 kill→circuit→rate→guard、**方向分流**（F-I1）、HOLD 特判、fail-closed；`gate_kill/update_equity/on_order_result/cancel_all`；`_restore/_persist` 四段容错）；**不 import `filter`/`services`** | M1-M8 | 读码 + L1-L10 | ✅ `live/safety_gate.py` L58 `SafetyDecision`、L69 `SafetyGate`；`is_open_direction = action in ("BUY","SELL_SHORT")` 分流；HOLD 特判在前；`except Exception` → `guard_error`；grep `from filter/import filter` 无命中；L1-L10 + E1-E4 全绿 |
| M10 | `docs/RUNBOOK_p052_fault_handling.md` 新建：四类故障处置表 / 一键停机 / 恢复 / 演练模板 / 升级路径五节齐全，与 `default_fault_policy` 动作一致 | 无 | 读文档 + K13/K14 | ✅ RUNBOOK 五节齐；四类动作与 `default_fault_policy` 一致（DISCONNECT 重试 3→PAUSE_NEW+RECONCILE、REJECT 1→PAUSE_NEW、PARTIAL_FILL→RECONCILE、COUNTER_RESTART→CANCEL_ALL+RECONCILE+HALT）；K13/K14 全绿 |
| M11 | `.github/workflows/tests.yml` mypy 目标命令含 `live`（当前 L46 不含，D-6） | 无 | 读文件 | ✅ `tests.yml` L46 目标串末尾已加 `live`；配套 `scripts/spec_runner_adapter.py` GATES `mypy-check` 同步加 `live`（`test_ci_mypy_flags_match_local_gate` 全绿） |
| M12 | **零改动**：`core/engine_v2.py`、`core/engine_v3_vector.py`、`core/sizing.py`、`core/stops.py`、`core/live_bridge.py`、`filter/limit_rules.py`、`tests/_golden_cases.py`、`core/__init__.py`（I8） | 无 | `git diff --stat` | ✅ `git diff --stat` 对 8 文件输出为空（2026-11-21 实测，EXIT=0） |

---

## 2. T 组：测试（8 文件 / 70 条）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| T1 | `tests/test_p052_safety_kill.py` **K1-K14（14 条）**：空状态 / 三级生效 / 优先级 GLOBAL>ACCOUNT>STRATEGY / **低层 disable 不解除高层（I3）** / 同键覆盖 / blocked_actions 含 CLOSE / `allows` 三动作 / 序列化往返 + 未知枚举抛 / `decide_fault` 断线 3 次与重启 0 次边界 | M1 | pytest | ✅ `pytest tests/test_p052_safety_kill.py -q` → **14 passed** |
| T2 | `tests/test_p052_circuit_breaker.py` **B1-B9（9 条）**：NORMAL / 日亏损 / 回撤 / 连续拒单 HALTED / **严重度优先（D-1）** / 基准 0 不触发 / 等号边界 / `allows_open` / `allows_close`（DERISK True、HALTED False） | M2 | pytest | ✅ `pytest tests/test_p052_circuit_breaker.py -q` → **9 passed** |
| T3 | `tests/test_p052_compliance.py` **C1-C10（10 条）**：`missing_required` 全缺/齐全/纯空白 / 秒级同秒阻断（F-I2）/ 跨秒放行 / 日累计 / 跨日重置 / 撤单率样本不足 / 超限 / 保留常量 5·20 | M3 | pytest | ✅ `pytest tests/test_p052_compliance.py -q` → **10 passed** |
| T4 | `tests/test_p052_guard_extensions.py` **G1-G15（15 条）**：5 Guard 正反例 + 边界（等号放行、None warning、空列表放行、样本不足不判、pv≤0 跳过）+ `live_safe()` 组件与顺序 | M4 | pytest | ✅ `pytest tests/test_p052_guard_extensions.py -q` → **15 passed** |
| T5 | `tests/test_p052_eventlog_audit.py` **A1-A6（6 条）**：8 常量与 frozenset 一致 / append 签名不变（I12）/ `audit.*` replay / seq 单调（I6）/ payload 强制两键 / 重复键抛 ValueError | M6 | pytest | ✅ `pytest tests/test_p052_eventlog_audit.py -q` → **6 passed**（A6 重复键被 Python 绑定 `TypeError` 或守卫拦截） |
| T6 | `tests/test_p052_live_safety_gate.py` **L1-L10（10 条）**：放行审计 / **kill 阻开仓放平仓** / **DERISK 阻 BUY 放 SELL、HALTED 全停** / rate 阻断 / guard 阻断 / 异常 fail-closed / HOLD 特判 / **落盘恢复含权益基准（F-I3）** / `cancel_all` 返笔数 / `update_equity` 切日重置 | M8/M9 | pytest | ✅ `pytest tests/test_p052_live_safety_gate.py -q` → **10 passed** |
| T7 | `tests/test_p052_end_to_end.py` **E1-E4（4 条）**：意图→gate→`MockLiveBridge` 下单（断言 `get_placed_orders()`）/ kill 后不下单 / 连续拒单→HALTED 后拒单 / 重启后 kill 仍生效 | M9 + M1 | pytest | ✅ `pytest tests/test_p052_end_to_end.py -q` → **4 passed** |
| T8 | `tests/test_p052_auth_contract.py` **S1-S2（2 条）**：`AuthConfig` 默认值 / `api_key_env` 约定 | M7 | pytest | ✅ `pytest tests/test_p052_auth_contract.py -q` → **2 passed** |
| T9 | 用例合计 **70**（14+9+10+15+6+10+4+2）；总 pytest = 1144+70 = **1214**；8 新文件无 `skip`/`xfail` | T1-T8 | pytest 计数 | ✅ 8 文件收集 **70 passed**；全量 **1214 passed**；新文件 grep `skip|xfail` 无命中 |

---

## 3. C 组：门禁（6 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `.\.venv\Scripts\python.exe -m pytest -q`（`$env:MPLBACKEND='Agg'`） | **1214 passed** | ✅ `1214 passed, 278 warnings in 116.97s`（+70） |
| C2 | golden | `-m pytest -q -k golden` | **22 passed**（零重录，I9） | ✅ `22 passed, 1192 deselected`（零重录） |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core … strategies …`（**含 `live`**，M11） | **125 files 0**（含 live 则 128） | ✅ `Success: no issues found in 128 source files` |
| C4 | black | `-m black .` 后 `-m black --check .`（F-I7） | **261 files unchanged** | ✅ `261 files would be left unchanged`（先 black 格式化 5 个新测试文件） |
| C5 | 无新增/改动 golden | `git status --porcelain tests/golden` | 输出为空 | ✅ 输出为空 |
| C6 | 零新依赖 | `git status --porcelain -- pyproject.toml requirements*.txt` | 输出为空（仅标准库 + 既有 pandas/numpy） | ✅ 输出为空 |

---

## 4. I 组：不变式（12 项，对应 DESIGN I1-I12）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | `core/{safety,circuit_breaker,compliance}.py` 无 I/O、无 `datetime.now`、无随机 | grep 三文件 + 固定 ts 单测 | ✅ grep `datetime.now|time.time|random.|open(|logging` 三文件仅命中 `core/safety.py` L3 docstring；单测全部显式传 `ts` |
| I2 | `pre_trade_check` 任一阻断 → 不发单；异常 → `allowed=False`（fail-closed） | L2-L6 | ✅ L2/L3/L4/L5 阻断断言 + L6 `guard_error` fail-closed；E2/E3 断言 Bridge 无单 |
| I3 | 高层级 kill active 时，低层级 disable 不解除 | K7 | ✅ `test_k7_low_level_disable_does_not_clear_high_level` 全绿 |
| I4 | kill 状态落盘后 `load()` 恢复一致 | K11 + L8 + E4 | ✅ K11 序列化往返、L8 跨实例恢复、E4 重启后 kill 仍阻断 |
| I5 | `DERISK_ONLY` 允许 close 禁止 open；`HALTED` 全禁 | B8/B9 + L3 | ✅ B8/B9 + L3 全绿 |
| I6 | 审计事件 append-only、`seq` 单调、`replay` 一致 | A3/A4 | ✅ A3 replay、A4 `seq == [1,2,3]` |
| I7 | 报告字段对齐第九条/第三十四条（最小必填 6 项） | C1-C3 | ✅ C1 全缺 6 项、C2 齐全空、C3 纯空白计入缺失 |
| I8 | `engine_v2/engine_v3_vector/sizing/stops` 主路径零 diff | M12 `git diff --stat` | ✅ `git diff --stat` 8 文件输出为空 |
| I9 | golden 22 条零重录 | C2 | ✅ `22 passed`（零重录）+ C5 无 golden 变更 |
| I10 | 阈值全部可配置，判定函数体内无硬编码（`FaultPolicy.max_retries`、`CircuitConfig`、`RateLimitConfig`） | B6/C6/C9/K14 + 读码 | ✅ 三配置 dataclass 承载阈值；B6 基准 0、C6 日限、C9 撤单率、K14 重试上限均经参数化验证 |
| I11 | `GuardContext` 新字段全带默认，既有 6 Guard 行为不变 | 既有 guard 测试全绿 + M4 | ✅ 9 新字段全带默认；全量 1214 中既有 guard/插件测试零回归 |
| I12 | `EventLogEntry`/`append` 签名零改动；旧 JSONL 可读 | A2 + 旧日志回放 | ✅ A2 断言签名 `[self,event_type,payload,source]`；A3 读写回放通过 |

---

## 5. DG 组：工程口径 D-G1..D-G9（9 项）

| ID | 决策 | 落实点 | 实测 |
|----|------|--------|------|
| DG1 | **扩展 `GuardPipeline`**（+5 Guard + `live_safe()` 预设），不新建平行网关风控（U-P052-3）；三新 core 模块零项目内依赖（C-8/D-2，M3 已单列） | M4 + G15 + `core/{safety,circuit_breaker,compliance}.py` import 段 | ✅ `guard_pipeline.py` 扩展（无平行网关模块）；G15 八件套顺序断言；三新 core 模块无 `from core` import |
| DG2 | `SafetyGate` fail-closed；`GuardPlugin` 默认 fail-open 不变（U-P052-6） | M5 + M9 + L6 | ✅ M5 默认 `on_error="open"`；M9/L6 实盘 `except → allowed=False` |
| DG3 | 审计只加 `EventType` 常量，不改 `EventLogEntry` schema（U-P052-7） | M6 + A2 | ✅ 仅增 8 常量 + frozenset；A2 签名不变 |
| DG4 | S7 交付 `FaultType/FaultAction` 纯决策（动作表 + 重试上限）+ RUNBOOK + 注入骨架；**重连实现归 P-053**（U-P052-8） | M1 `default_fault_policy` + M10 + K13/K14 | ✅ `default_fault_policy` 四类动作 + `max_retries`；RUNBOOK 五节；K13/K14 边界全绿 |
| DG5 | 熔断阈值经验默认 3%/10%/5，可配置（U-P052-10） | M2 + B* | ✅ `CircuitConfig` 默认 `0.03/0.10/5`；B1-B9 经参数验证 |
| DG6 | `PriceBandGuard` 只消费注入字段，core/live 均不 import `filter`（F-D5） | M4 + M9 import 段 | ✅ grep `from filter|import filter` 于 `guard_pipeline.py` 与 `live/` 均无命中；PriceBand 读 `limit_up/limit_down` |
| DG7 | `cancel_all` 只对 `LiveTradingBridge/MockLiveBridge` 调用（`cancel_orders(None) -> int`，不改 Bridge 抽象）；本批不接真实券商（U-P052-12） | M9 `cancel_all` + L9 | ✅ `cancel_all(bridge, ts)` 调 `cancel_orders(None)` 转 `int`；`core/live_bridge.py` 零 diff；L9 返 2 后返 0 |
| DG8 | 审计保留期默认 **5 年可配置**、常量上限 **20 年**（U-P052-13） | M3 `AUDIT_RETENTION_*` + C10 | ✅ `AUDIT_RETENTION_YEARS_DEFAULT=5` / `_MAX=20`；C10 断言 |
| DG9 | 本批不自动平仓（人工/上层触发） | M9 无平仓调用 + RUNBOOK §5 | ✅ `safety_gate.py` 无平仓/下单调用（仅 `cancel_orders`）；RUNBOOK §5 升级路径人工触发 |

---

## 6. D 组：设计决策 D1-D14（14 项）

| ID | 决策 | 落实点 | 实测 |
|----|------|--------|------|
| D1 | 三模块纯函数、无状态（I1） | M1-M3 | ✅ 三模块仅 dataclass + 纯函数；I1 grep 通过 |
| D2 | kill 三级优先级 GLOBAL>ACCOUNT>STRATEGY | M1 + K2-K6 | ✅ `_LEVEL_ORDER` 顺序判定；K2-K6 全绿 |
| D3 | 低层 disable 不解除高层 | K7 | ✅ K7 全绿 |
| D4 | 熔断映射 + **严重度优先**（daily_loss/max_drawdown→DERISK_ONLY；consecutive_rejects→HALTED） | M2 + B4/B5 | ✅ `evaluate_circuit` L52 rejects 先判；B4/B5 全绿 |
| D5 | kill 默认 `blocked_actions=(OPEN,)`，含 CLOSE 需显式下发 | M1 + K9 + L2 | ✅ `KillEntry/KillCommand` 默认 `(KillAction.OPEN,)`；K9 显式含 CLOSE、L2 默认只阻开仓 |
| D6 | 审计 payload 强制 `operator`/`time_source` | M3 `build_audit_payload` + A5/A6 | ✅ `build_audit_payload` 强制两键；A5/A6 全绿 |
| D7 | 状态落盘原子写 + 逐段容错 | M8 + L8 | ✅ `save` mkstemp+fsync+replace；`_restore` 逐段 try；L8 恢复绿 |
| D8 | 限速默认 1 笔/秒、1000 笔/日（**项目内部默认，非监管要求**）；gate 侧先 check 后 record、秒级当前秒桶（F-I2/C-6） | M3 + C4-C7 + L4 | ✅ `RateLimitConfig` 默认 `1/1000`；`pre_trade_check` 先 `check_rate` 后 `record`；C4/C5/L4 全绿 |
| D9 | 报告最小必填 6 项 | M3 + C1/C2 | ✅ `missing_required` 6 项；C1/C2 全绿 |
| D10 | 5 新 Guard 边界语义（等号/None/空列表/样本不足/pv≤0） | M4 + G1-G14 | ✅ G1-G14 全绿 |
| D11 | `live_safe()` 八件套参数与顺序 | M4 + G15 | ✅ G15 顺序断言全绿 |
| D12 | `decision_id` 由 live 层 `uuid4().hex` 生成（core 保持纯净） | M9 + L1 | ✅ `pre_trade_check` `uuid.uuid4().hex`；core 三模块无 uuid；L1 断言 `decision_id` 非空 |
| D13 | `AuthConfig` 仅契约（实现归 P-054） | M7 + S1/S2 | ✅ 仅 dataclass；S1/S2 全绿 |
| D14 | 保留期 5 年默认 / 20 年上限常量 | M3 + C10 | ✅ 常量齐；C10 全绿 |

**无独立代码落点的裁决**：D-G1..D-G9 已单列 §5；U-P052-1/2/4（方案 A）体现在 M4/M9 的分层与 fail-closed 口径，Step 8 交叉核对。

---

## 7. 出口判定

- **Step 9 判据**：M12 + T9 + C6 + I12 + DG9 + D14 = **62 项全部 ✅**（`[待 Step 9]` 清零）；
- **任一 ❌** → 记录证据并回 Step 5/6（禁止补丁式修复）；
- **实测读数**回填 §8，再进 Step 8 一致性检查（四文档交叉核对）。

## 8. 实测读数（Step 9 回填）

| 指标 | 基线 @`1f950c6` | 目标 | 实测 |
|------|------------------|------|------|
| pytest 全量 | 1144 | 1214 | ✅ **1214**（+70） |
| `-k golden` | 22 | 22（零重录） | ✅ **22**（零重录） |
| mypy | 122 files / 0 | 125（含 live 128）/ 0 | ✅ **128 files / 0** |
| black `--check .` | 247 | 261 unchanged | ✅ **261 unchanged** |
| `tests/*.py` | 124 | 132 | ✅ **132** |
| `core/*.py` | 48 | 51 | ✅ **51** |
