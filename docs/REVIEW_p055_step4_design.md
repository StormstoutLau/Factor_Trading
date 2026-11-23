# REVIEW：P-055 Step 4 设计复审（DESIGN_p055 异构对码）

> **批次**: P-055 · **Step 4 设计 Review** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **复审基座**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash）→ **异构成立（RULE-5 单向）**
> **复审对象**: [DESIGN_p055_microservices](DESIGN_p055_microservices.md)（1056 行：拓扑/运行时补齐/G17 WS/G18 入口/部署/门禁/基准/D1-D14/I1-I12/U-D1..D5）
> **方法**: ① 引用可解析性抽查（uvicorn 实装源码 / ws_hub / config / bus / ledger_store / gateway / api / auth / outbox_relay / market_gateway 逐一对码）；② D1-D14 决策逐条可实施性复核；③ 独立新发现扫描（payload 形状、停机收尾、心跳格式、门禁边集）；④ 与 RESEARCH/REVIEW Step2/PROGRESS 一致性
> **裁决口径**: 文档级 P1 → Step 4 不通过；P2 → PASS 但修正回写 + Step 5 前置承接；P3 → 文字级修正

---

## 1. 引用核验表（对码实证）

> 方式：复审独立 read/grep 源码与 .venv 实装包，逐条比对行号与结论。

| # | DESIGN 引用 | 验证方式 | 状态 | 备注 |
|---|------------|----------|------|------|
| V1 | uvicorn **0.54.0** 实装（§2.8 行号引用前提） | `.venv` 实测 `uvicorn.__version__` | ✅ | 0.54.0 |
| V2 | config.py L513-518：实例无参调用 → TypeError → factory=True 时 `sys.exit(3)` | 读 .venv `uvicorn/config.py` L511-523 | ✅ | `self.loaded_app = self.loaded_app()`（L514）+ L516-518 |
| V3 | config.py **L519-523 = 「非 factory 回退为实例模式」依据**（§2.8 修复 1） | 读同区间 | ⚠️ **行号错位（F-D2）** | L519-523 的 `else` 是 try/except/**else**：仅**调用成功**时告警；「调用失败且非 factory → 静默保持实例」的实际路径在 **L515-518 except 分支**（`if self.factory:` 为假 → 不退出，`loaded_app` 保持原实例）。结论不变，依据行号需修 |
| V4 | config.py L246 / L477：`ssl_context_factory` 双参协议 | 读 .venv config.py | ✅ | `Callable[[Config, Callable[[], SSLContext]], SSLContext]`（L246）+ `self.ssl_context_factory(self, default_factory)`（L477） |
| V5 | importer.py L10-11：非字符串 import 原样返回 | 读 .venv importer.py | ✅ | L9-11 |
| V6 | `ConnectionHub(orders_max/market_max/slow_seconds/clock)`（§3.4） | ws_hub.py L34-41 | ✅ | 参数名逐一匹配 |
| V7 | `next_frame()` 先 orders 后 market + close 帧 `{"type":"close","code":N}`（D7 理由） | ws_hub.py L22-30 | ✅ | |
| V8 | `broadcast_market` 受 `paused` 控制（D7） | ws_hub.py L45/L49-50/L95 | ✅ | 注释「只影响行情，不触订单」 |
| V9 | `snapshot_and_stream` L155-166 / `heartbeat` L170 / `pong` L180 / `ensure_ready` L183 | grep + read | ✅ | 帧泵依赖的返回语义全部存在 |
| V10 | delta 帧形状 `{"type":"delta","seq","events"}`（L89） | ws_hub.py broadcast_orders 区间 | ✅ | |
| V11 | `evaluate_readiness(store, *, heartbeats=None)` + 键名 `trading/consumer` | api.py L33/L36-39 | ✅ | 与 §3.6 reader 返回 dict 键名一致 |
| V12 | `health_ready` 未传 heartbeats（G2 现状） | api.py L165-170 | ✅ | 引用行号精确 |
| V13 | `create_app` 现 5 参（settings/store/ticket_store/metrics/publisher） | api.py L69-76 | ✅ | §3.5 扩 4 参成立 |
| V14 | `/api/ws-ticket` 端点 | api.py L229 | ✅ | §9 降级链可解析 |
| V15 | broadcast-pause 发布 `{"paused": bool}` | api.py L236-243 | ✅ | admin_subscriber 解键匹配 |
| V16 | §3.7 env 矩阵全部字段「model 已有」 | config.py L15-57 逐一对码 | ✅ | 19 个字段名/默认值全命中；`extra="forbid"` + `from_env`（L13/L75） |
| V17 | `AsyncRedisBus` 存在（§3.4 bus 装配） | bus.py L147-164 | ✅ | `subscribe` 返回 async pubsub；`InMemoryBusAdapter.stream_pending` L197 ✅ |
| V18 | consumer 发布形状 `{"seq","event"}`（订阅任务解键） | outbox_relay.py L109-112 | ✅ | 精确匹配 §2.7 `payload["seq"]/payload["event"]` |
| V19 | market 发布形状 `{"ticks":[{symbol,last,ts}]}` | market_gateway.py L57-68 | ✅ | market_subscriber `payload["ticks"]` 匹配 |
| V20 | `main()` 只 `run_once()` 一次（G3）；`run_embedded` 已存在 | market_gateway.py L71-90 | ✅ | |
| V21 | outbox 列 `created_ts REAL NOT NULL` / `sent_ts REAL`（T2 口径） | ledger_store.py L38/L40 | ✅ | |
| V22 | `SqliteLedgerStore(read_only=True)` + `_open_read_only` + `query_only=ON` + **`is_read_only()`**（I2 断言） | ledger_store.py L161/L191/L200/L225-226 | ✅ | I2 测试可行 |
| V23 | `RedisTicketStore.issue/consume` | auth.py L97/L104/L107 | ✅ | |
| V24 | `TradingGateway(scheduler=)` + `reconcile(*, ts, nav=0.0)` + QueryScheduler | gateway.py L47/L100/L555 | ✅ | §2.6.1 巡检调用签名正确 |
| V25 | `Heartbeat.stop()` 存在（线程收尾） | trading_worker.py L124-125 | ✅ | 但见 F-D6 |
| V26 | pyproject `[services]`/`[dev]` extras + `uvicorn>=0.30.0` | pyproject.toml L58-77 | ✅ | 0.54.0 满足下限 |
| V27 | spec_runner_adapter `GATES` 结构 + `_PY312`（§5.3 gate 增项落点） | scripts L62-68 | ✅ | |
| V28 | services 12 个模块 → 13（§11 读数 6） | 实测文件数 | ✅ | 12 个 .py |
| V29 | metrics.py「12 个指标族」（§4.5） | metrics.py L36-58 逐个数 | ❌ **实际 13 个（F-D3）** | http_requests/ws_connections/ws_slow_consumers/order_events/fills/rate_denied/outbox_pending/consumer_pending/ready/quote_latency/order_latency/e2e_latency/market_dropped |

**结论**：29 项对码 27 ✅ / 1 ⚠️ 行号错位 / 1 ❌ 计数漂移；**无幻觉引用，无不可解析引用**。

---

## 2. D1-D14 决策逐条复核（可实施性）

| D | 复核结果 | 实证 |
|---|----------|------|
| D1 部署形态 | ✅ 与 U-P055-1/6、Q18-Q20 一致 | §2.1/§2.2 |
| D2 策略/风控库内 | ✅ 触发条件已文档化（§3.5） | U-P055-2 |
| D3 SQLite 卷 | ✅ named volume/NTFS；S20 锚一致 | §4.2/§4.3 |
| D4 API 绑定 | ✅ `allow_plaintext_loopback` validator 存在（config.py L66-72 model_validator）→ 容器内 0.0.0.0 必须 TLS，推断成立 | V16 |
| D5 去 factory + WORKERS=1 | ✅ 可实施；结论正确，依据行号 F-D2 修正 | V2/V3 |
| D6 TLS 双参 | ✅ 协议签名实证（V4） | |
| D7 双 Hub | ✅ `next_frame` orders 优先 + paused 属行情（V7/V8）；单 Hub 串流理由成立 | |
| D8 先 accept 再验票 | ✅ ASGI accept 前 close 无法传自定义码 → 4401 只能握手后；代价已声明 | |
| D9 单协程帧泵 | ✅ `wait_for(receive_json, 0.02)` + WebSocketDisconnect/ValueError 捕获完备 | |
| D10 sync heartbeat_reader | ✅ `health_ready` 是 `def`（线程池）→ sync Redis 读合法；键名 trading/consumer 与 evaluate_readiness 一致（V11） | |
| D11 wait(0.2)+巡检 | ✅ `reconcile(*, ts, nav=0.0)` 签名正确（V24）；`QueryScheduler` 已存在且 gateway 支持注入 | |
| D12 market serve() | ✅ run_once 语义不变；心跳键三进程一致（trading/consumer/market:heartbeat） | V20 |
| D13 3 契约+负例 | ✅ 边集与 RESEARCH E3 实测一致；`api._load_store → live.ledger_store` 是 `live.ledger` 兄弟模块不在 forbidden 内（§5.5 自证成立）；负例 `.importlinter` + layers 方向正确。**但 source_modules 缺新模块 ws_routes → F-D1** | |
| D14 双进程基准 | ✅ T2 数据源 outbox 列实证（V21）；打点经包装 bus 可实现，「零改动 services」约束可满足 | |

---

## 3. 复审新发现（独立扫描产出）

### F-D1（**P2**）C3 契约 `source_modules` 缺新增模块 `services.ws_routes`

- §5.2 C3 source_modules = `services.api / api_worker / ws_hub / market_gateway`，但 §2.3 新增 `services/ws_routes.py` 未纳入。
- ws_routes 是 WS 装配层（挂载/鉴权/帧泵/订阅），未来若直接 import `live.*` 无门禁可拦——恰是「services 禁含交易逻辑」最应看住的模块。
- **修正**：Step 5 B2 落契约时 source_modules 补 `"services.ws_routes"`（本复审已同步回写 DESIGN §5.2）。

### F-D2（**P2**）§2.8 修复 1 的 uvicorn 行号引用错位（结论不变）

- 「uvicorn 对『实例调用失败且非 factory』回退为实例模式（0.54 config.py L519-523）」——L519-523 是 try/except/**else** 分支，仅在**调用成功**时告警；调用失败且非 factory 的静默保持实例发生在 **L515-518 except 分支**（`if self.factory:` 为假 → 不 `sys.exit`，`loaded_app` 保持原实例）。
- **影响**：结论（删 `factory=True` 可行且安全）不变；FastAPI 实例 `__call__` 需 3 参 → 无参调用必 TypeError → 进 except → 安全。仅依据行号需改写（本复审已回写 DESIGN §2.8）。

### F-D3（**P2**）§4.5「12 个指标族」实际 13 个

- metrics.py L36-58 共 13 个指标对象（V29 清单）。计数漂移，不影响门禁数字（非基线读数），已回写。

### F-D4（**P2**）§11 读数 15 表述自相矛盾

- 读数 15 写「`live/*` 仅允许 §2.3 之外的零改动」——§2.3 变更清单**无任何 live 条目**，且 §15 结构守卫明确「`live/*` 零 diff」。两处表述应统一为「`live/*` 零 diff」（已回写）。

### F-D5（**P2**，Step 5 B0 前置）心跳值格式与 `Heartbeat.run()` 默认值冲突 → staleness 静默失效

- DESIGN §3.6 声明心跳值统一 `"<unix_ts>:<int>"`，`_fresh()` 解析失败时 `return True`（以 TTL 为准）。
- **实证**：现 `Heartbeat.run()`（trading_worker.py L120-122）以 `beat_once()` 默认 `value="ok"` 写键 → `float("ok")` 解析失败 → `_fresh` 恒 True → **`ready_staleness_seconds=3.0` 完全失效**，退化为 TTL 10 s 语义（滞后 3-10 s 的僵死进程仍判 fresh）。
- **修正（Step 5 B0）**：trading 心跳写 `f"{ts}:{outbox_pending}"`（Heartbeat 构造接受 value provider 或调用点传值）；测试清单补「心跳键值可被 `_fresh` 解析」断言（已回写 DESIGN §2.6.1/§3.6/§15）。

### F-D6（**P2**，Step 5 B0 前置）停机收尾缺 `heartbeat.stop()`

- §2.6.1 伪代码 finally 只 `t.join(timeout=5.0)`；`Heartbeat.run` 自持独立 `self._stop` Event（trading_worker.py L115/L120-121），**stop_event 置位不会让它退出**——不调 `heartbeat.stop()` 则 daemon 线程被进程退出硬杀，且停机瞬间仍可能再刷一次 TTL 键（10 s）。
- **修正（Step 5 B0）**：收尾序列 = `stop_event.set()` → `heartbeat.stop()` → join → `gateway.shutdown()`（已回写 DESIGN §2.6.1）。

### F-D7（P3）§2.3 trading 行漏列 `--once`

- §3.1 `main` 参数含 `--once`（探针用），§2.3 变更清单行未列。文字级（已回写）。

### F-D8（撤回）「PROGRESS 记录 836 行」之说核查不成立

- 复审初记「PROGRESS §3.78 写 DESIGN『836 行』」——复查实际 §3.78 未记录任何行数，该漂移**不存在**，属复审自身引用失误，撤回并留档为自纠记录。

---

## 4. 一致性检查

| 项 | 结果 |
|----|------|
| DESIGN vs 已裁决（A/A/A/A、Q17-Q20、U-P055-1/2/4/6） | ✅ §0.1 全表一致；U-P055-3/5/7/8 定稿与 §5/§4.5/§4.4 落点一致 |
| DESIGN vs REVIEW Step2（G17/G18 承接） | ✅ §2.7/§2.8 逐条承接；G4 忙等（F-R5）→ D11；G19 → §3.4 装配清单 |
| DESIGN vs RESEARCH G1-G19 | ✅ §2.3 变更清单覆盖 G1-G7、G14、G17-G19；G8-G12/G16 由 §4.2/§4.4/§4.5 承接 |
| 内部一致性（决策表↔不变式↔验收读数↔测试清单） | ⚠️ F-D4 一处（已修）；其余 I1-I12 与 §9 降级链/§11 读数/§15 测试清单逐条对得上 |
| 门禁数字 | ✅ services 12→13（V28）；pytest/mypy/black/golden 基线沿用 P-054 关闭读数未动 |
| compose YAML 合并语义 | ✅ api 重写 `depends_on` 已显式含 redis（mapping 浅合并，锚级被覆盖但补齐）；trading/market 继承锚级 redis healthy |
| 三进程心跳键名/格式 | ⚠️ 键名三处一致 ✅；格式统一依赖 F-D5 修正 |

---

## 5. 判定

| 层面 | 结论 |
|------|------|
| **引用可解析性** | 合规：29 项对码 0 幻觉；1 处行号错位（F-D2，结论不变）+ 1 处计数漂移（F-D3） |
| **G17/G18 修复方案可实施性** | **成立**：签名/协议/行为全部实证（V2-V6、V13-V19）；uvicorn 0.54.0 实装确认 |
| **契约边集 vs 实测** | 一致（`live.ledger_store` 兄弟模块豁免自证成立）；缺口 F-D1（ws_routes 未入 source_modules） |
| **运行时设计可实施性** | 成立（V17/V18/V20/V21/V24/V25）；两处实施前置 F-D5/F-D6（心跳格式/停机收尾） |
| **文档级 P1** | **0** |
| **新发现** | **P2×6**（F-D1..F-D6）+ P3×1（F-D7）+ 自纠撤回 1（F-D8，复审引用失误不留档漂移）→ 全部已回写 DESIGN 或标注 Step 5 前置 |

**判定：Step 4 设计复审 PASS（文档 0 P1；P2×6 已回写/承接，无阻断）→ Step 4 关闭，进入 Step 5 实施（B0 → B3）。**

---

## 6. 状态链

- **2026-11-23**：GLM-5.3-Flash 完成 DESIGN 异构复审（本文件）→ 29 项引用对码（27✅/1⚠️/1❌）+ D1-D14 逐条可实施性复核 + 新发现 P2×6/P3×1（另自纠撤回 F-D8：PROGRESS 实未记录行数）→ F-D1..F-D7 已回写 DESIGN（§2.3/§2.6.1/§2.8/§3.6/§4.5/§5.2/§11/§15/§16）。
- **Step 5 前置修复项**（实施时先做）：F-D1（C3 补 ws_routes）、F-D5（心跳值 `<ts>:<pending>`）、F-D6（收尾调 heartbeat.stop()）。
- **下一步**：Step 5 实施（B0 运行时+入口 → B1 WS → B2 门禁+部署 → B3 基准+运维；§15 分阶段输入）。
- **零代码变更 / 未提交**：本步仅文档。
