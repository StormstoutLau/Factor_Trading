# REVIEW：P-055 Step 2 调研复审（RESEARCH_p055 + 决策专项）

> **批次**: P-055 · **Step 2 调研 Review** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **复审基座**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash）→ **异构成立（RULE-5 单向）**
> **复审对象**: [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G16/方案 A/验收读数）+ [RESEARCH_p055_decision_anchors](RESEARCH_p055_decision_anchors.md)（U-P055-1/2/4/6 五维评分）
> **前置**: 用户已裁决 **A/A/A/A**（2026-11-23），已回写两文档
> **方法**: ① 引用 ID 可解析性抽查；② G1-G16 逐条对码复核（file:line 实证）；③ 新发现扫描（复审独立 grep/read，不依赖作者结论）；④ 五维评分算术复核；⑤ 两文档 + PROGRESS 一致性
> **裁决口径**: 文档级 P1 → Step 2 不通过；代码级新发现 → 并入 RESEARCH（G17+），Step 3 承接，不阻塞 Step 2

---

## 1. 引用核验表（可解析性）

> 口径（SPEC Step 2）：每条引用 ID 可解析；不可解析只能标「未验证」，禁止标 ✅。抽查 T1 关键项 + 全部 T3 项的标注合规性。

| # | 引用 | 验证方式 | 状态 | 备注 |
|---|------|----------|------|------|
| S1(anchors) | InfoQ Prime Video 报道 | 本复审会话检索摘要（标题/日期/90% 结论一致） | ✅ | 原文 AWS 博客抓取失败已走降级链，标注 T2 ✓ |
| S3(anchors) | Twilio Segment「Goodbye Microservices」 | 本复审会话直取（导航 + AI 摘要；2018-07-10 日期一致） | ✅ | 全文未直取；二手数字（140/3 FTE/1h）已标「二手数字」✓ |
| S5(anchors) | Shopify Engineering 模块化单体 | 本复审会话直取（「boundaries were defined and respected」原文一致） | ✅ | 发布日期未取到，表内标「未标注」✓ |
| S6(anchors) | arXiv:2308.15281 | 本复审会话直取摘要页（作者 Su/Li/Taibi、2023-08-29、回退五因一致） | ✅ | DOI 可解析 |
| S9(anchors) | Microsoft Learn Windows containers | 本复审会话直取（L91 表行「Containers don't support GUI」原文一致） | ✅ | |
| S11(anchors) | qmt-bridge 2.0.0 PyPI | 本复审会话直取（「只能在 Windows 上运行，且必须依赖 QMT 客户端保持登录」原文一致） | ✅ | |
| S12(anchors) | Docker WSL2 best practices | 本复审会话直取（avoid `/mnt/c` 原文一致） | ✅ | |
| S13(anchors) | SQLite 官方论坛 fc32d5d561 | 本复审会话直取全文（Keith Medcalf「interposer/proxy filesystems」+ Warren Young 反驳 + walbanger 测试，均与引用一致） | ✅ | 正反双方均收录，未断章 ✓ |
| S15(anchors) | Docker Compose production | 主文档 Step 1 会话直取（restart/多文件一致） | ✅ | |
| S18(anchors) | pytest-benchmark 指南 | 检索摘要（30% swings / min:15% 一致） | ✅（摘要级） | T3 已标 |
| S19(anchors) | Google Benchmark Reducing Variance | 检索摘要（固定频率/稳定系统一致） | ✅（摘要级） | |
| S20(anchors) | SQLite WAL | 主文档 Step 1 会话直取（同机/单写者/只读条件/checkpoint 逐条对上） | ✅ | |
| S22(anchors) | eastondev 3.5× 对比 | 检索摘要表格（「低（約 3.5 倍遅い）」一致） | ✅（摘要级） | T3 已标 |
| S23(anchors) | 华为云 import-linter 实践 | 本复审会话直取全文（layers 契约/CI lint-imports/动态导入限制逐条一致） | ✅ | |
| S4/S10/S14/S21(anchors) | 二手/社区项 | 检索摘要或未直取全文 | ⚠️ 未验证（全文级） | 均已标 T3 且关键数字标注二手来源；**合规**（未标 ✅） |

**结论**：引用链合规；无「不可解析却标 ✅」违例；二手数字均有标注。

---

## 2. G1-G16 逐条对码复核

> 方式：复审独立重新 grep/read 源码（`e67ebbe`），逐条比对行号与结论。

| G | 作者结论 | 复核结果 | 证据（复审实证） |
|---|----------|----------|------------------|
| G1 consumer 未启动 | `assemble` 建 consumer（L41）、`start_threads` 仅 relay（L45-51） | **属实** | 复审重读 trading_worker.py：threads 列表仅含 relay ✓ |
| G2 heartbeat/readiness | Heartbeat 无实例；`health_ready` 不传 heartbeats（api.py L165-170）；`evaluate_readiness` None 即跳过（L33-40） | **属实** | 复审重读 ✓ |
| G3 market 只跑一次 | main() 仅 run_once()；无循环/`--embedded` | **属实** | 复审重读 market_gateway.py L71-91 ✓；另证 `run_embedded` 全仓无调用方 ✓ |
| G4 无优雅停机 | 无 signal handler；IMPL C-20 要求未落 | **属实** | 复审 grep `signal` in services/ = **0 命中** ✓ |
| G5 部署资产回测化 | compose 无服务定义；Dockerfile `.[dev]` + CMD pytest | **属实** | 复审重读两文件 ✓ |
| G6 import-linter 缺失 | 依赖/配置/CI job 全无 | **属实** | 复审 grep 全仓 = 仅 docs 提及 ✓ |
| G7 跨进程基准缺失 | J6 为 InMemoryBus 进程内 | **属实** | 复审读 test_p054_end_to_end.py（FakeBus/InMemory）✓ |
| G8 TLS/loopback 冲突 | `allow_plaintext_loopback` 强制 127.0.0.1 | **属实** | config.py L66-72 model_validator ✓ |
| G9 SQLite 跨挂载风险 | WAL 同机约束/只读条件/长读事务 | **属实** | 与 S20 官方原文逐条对应 ✓ |
| G10 真实网关不能容器化 | QMT 仅 Windows | **属实** | S9（GUI 禁容器）+ S11（xtquant Windows-only）双锚 ✓ |
| G11 trading 无健康探针 | 心跳未写 → healthcheck 无依据 | **属实** | 依赖 G2 成立 ✓ |
| G12 metrics 默认要 auth | metrics_require_auth=True | **属实** | config.py L21 + api.py L245-254 ✓ |
| G13 组合根例外 | trading_worker 必须 import live | **属实** | 复审 grep services→live 惰性导入 = 7 行 2 处（trading_worker×6 + api×1）✓ |
| G14 `--bus fake` 未落 | 入口无开关 | **属实** | trading_worker main() 无 argparse ✓ |
| G15 策略/风控未进程化 | 库内调用 | **属实** | strategies/ 无独立入口 ✓ |
| G16 无抓取资产 | 无 prometheus.yml | **属实** | 复审 glob ✓ |

**文档级结论**：G1-G16 **16/16 属实，0 幻觉，0 行号漂移**。

---

## 3. 复审新发现（作者未覆盖，复审独立扫描产出）

> 扫描面：三入口真实可启动性 / WS 端到端可达性 / 装配完整性 / 主循环行为。以下按 G 编号续排（G17-G19），并入 RESEARCH §3；另对 G4 补充忙等实证。

### F-R1（**P1**）→ **G18：api_worker.main() 真实 uvicorn 下不可启动（factory 误用）**

- **事实链**：[api_worker.py#L52-L62](../services/api_worker.py#L52-L62) 构造 `kwargs = {"factory": True, ...}` 后 `uvicorn.run(app, **kwargs)`，其中 `app` 是 **create_app() 返回的实例**。
- **uvicorn 0.54.0 实证**（.venv 实装源码）：`import_from_string` 对非字符串**原样返回**（importer.py L10-11）；`Config.load()` 拿到实例后**无条件无参调用** `self.loaded_app()`（config.py L513-514）→ FastAPI 实例缺 `scope/receive/send` → TypeError → `factory=True` 分支 `logger.error + sys.exit(STARTUP_FAILURE=3)`（config.py L516-518）。
- **后果**：API worker 进程**启动即退出码 3**；P-054 全部 120 例不覆盖（`# pragma: no cover`），Step 10 探针未跑真实 uvicorn。
- **修复方向（Step 3 定稿）**：A. 删除 `"factory": True`（实例直跑；uvicorn 对「调用失败且非 factory」静默回退为实例模式——config.py L519-523 else 分支仅在调用成功时告警）；B. 或 import string `"services.api:create_app"` + create_app 支持无参（settings 默认 None 已支持，但 key 走不安全默认值，需 env 兜底）。**倾向 A（最小改动 + 保留显式 settings）**。

### F-R2（**P1**）→ **G18（同条合并）：TLS 模式启动即崩（ssl_context_factory 签名失配）**

- **事实链**：[api_worker.py#L33-41](../services/api_worker.py#L33-L41) 的 `tls_context_factory()` 为**零参**函数；uvicorn 0.54 协议为**双参** `Callable[[Config, Callable[[], ssl.SSLContext]], ssl.SSLContext]`，且在 `Config.load()` 内**直接双参调用**（config.py L246 签名 + L477 `context = self.ssl_context_factory(self, default_factory)`）。
- **后果**：配置 TLS 时在 **app 加载之前** TypeError（0参函数收到 2 个位置参数）→ 进程崩溃。
- **测试盲区**：[test_p054_api_auth.py#L166](../tests/test_p054_api_auth.py#L166) 仅断言 `pickle.dumps(tls_context_factory)`（可 pickle），从未以 uvicorn 真实签名调用。
- **修复方向**：签名改 `tls_context_factory(config, default_factory)` 并转发 `build_ssl_context(...)`；或用 uvicorn 提供的 `default_ssl_context_factory()` 语义。与 F-R1 同属「入口未真实验证」，合并为 G18。

### F-R3（**P1**）→ **G17：FastAPI 进程零 WS 端点（ConnectionHub 从未挂载）**

- **事实链**：复审 grep `websocket|ws_route|add_websocket|include_router`（-i）在 **services/ 全目录 0 命中**；[ws_hub.py](../services/ws_hub.py) 为纯组件（ConnectionHub/ConnectionState，无 FastAPI/Starlette 耦合）；[api.py](../services/api.py) 11 端点全为 REST（P-054 IMPL §3.17 口径）。
- **根因**：P-054 IMPL §3.17（api.py=11 REST 端点）与 §3.18（ws_hub=组件）**均未定义「谁把 hub 挂到 ASGI app」**；120 例全部为组件级/Hub 直测，J 组端到端也未经过 HTTP 升级握手。
- **后果**：部署态 API worker **只提供 REST**；F7 的 WS seq 连续性/snapshot+delta/慢消费者 1013 在真实进程**不可达**。P-054 Step 10 的 WS 探针走 Hub 直连，掩盖了该缺口。
- **归属**：组装缺口，P-055 部署批次必须承接（挂载设计 + 真实握手探针）。**这是本批「进程边界」验收的前置**。

### F-R4（**P2**）→ **G19：api_worker 装配缺口（publisher/tickets/hub/bus 全缺省）**

- **事实链**：[api_worker.py#L50-L51](../services/api_worker.py#L50-L51) 仅 `create_app(settings=settings)`：
  - `publisher=None` → broadcast-pause 有 None 防护（api.py L240）**不崩但静默降级**为单 worker 内存标志，跨 worker 暂停语义丢失（F-I9 落码层残留，与 F-A2 修复不完整同型）；
  - `ticket_store=None` → 默认 [InMemoryTicketStore](../services/auth.py#L77)；**RedisTicketStore 已实现（auth.py L97）但无接线** → 多 worker 部署下 A worker 签发的 ticket 在 B worker 不可消费；
  - 无 `ConnectionHub` 实例/订阅任务（依赖 G17 挂载设计）。
- **归属**：与 P-054 F-A4（trading_worker 装配）同型的 api_worker 版缺口；P-055 承接。

### F-R5（**P2**）→ **G4 扩展：trading_worker 主循环忙等**

- **事实链**：[trading_worker.py#L85-L89](../services/trading_worker.py#L85-L89) `while True: gateway.poll()` **无 sleep**；`poll()` 实现为 drain_reports + apply，无内部等待（[gateway.py#L329-L347](../live/gateway.py#L329-L347) 复审实证）→ 主线程 100% CPU 空转。
- **对照**：IMPL §3.21 规定 0.5s 轮询 + 6s 巡检，均未落（与 RESEARCH §2.2「巡检未接」一致，但作者未指出忙等本身）。

---

## 4. 文档修正（复审回写，已完成）

| # | 修正 | 落点 |
|---|------|------|
| R-1 | §2.1 api_worker 行状态「完整」→「REST 可跑；WS 未挂载 + 入口 factory/TLS 两处启动缺陷 + 装配缺省（G17-G19）」 | RESEARCH §2.1 |
| R-2 | §2.2 补「WS 端点挂载缺失」「主循环忙等」两行 | RESEARCH §2.2 |
| R-3 | 发现表追加 G17/G18（P1）/G19（P2），标注「Step 2 复审新增」 | RESEARCH §3 |
| R-4 | G4 行补忙等证据 | RESEARCH §3 |
| R-5 | §7 验收读数补三项：api_worker 真实 uvicorn 启动探针 / WS 握手挂载探针 / 主循环 CPU 占用读数 | RESEARCH §7 |
| R-6 | U-P055-1/2/4/6 标注用户裁决 A（2026-11-23） | RESEARCH §6 + anchors §10 |

---

## 5. 判定

| 层面 | 结论 |
|------|------|
| **引用可解析性** | 合规（无违例标 ✅；二手数字已标注） |
| **G1-G16 对码** | **16/16 属实，0 幻觉** |
| **评分算术** | 五组总分复算全一致（22/15/16、22/16/17、24/17/9、24/14/18、22/16/17）；适用性边界已声明 |
| **两文档一致性** | 推荐/结论/键表口径一致（S 编号跨文档引用清晰） |
| **文档级 P1** | **0**（唯一失实点 api_worker「完整」为 P2 级描述错误，已回写 R-1） |
| **代码级新发现** | **G17/G18 = P1 ×2**（WS 零端点 / api_worker 不可启动）+ G19 = P2 + G4 扩展（忙等）→ 全部并入 RESEARCH，**Step 3 DESIGN 硬承接** |

**判定：Step 2 复审 PASS（文档 0 P1；2 个 P1 为代码缺口并入 G 表，属 P-055 验收面而非调研失实）→ Step 2 关闭，进入 Step 3 DESIGN。**

---

## 6. 状态链

- **2026-11-23**：用户裁决 A/A/A/A 定案（U-P055-1/2/4/6）→ 回写两文档；GLM-5.3-Flash 完成对码复审（本文件）→ G17-G19 并入 RESEARCH + 6 项修正回写 → Step 2 关闭。
- **下一步**：Step 3 DESIGN（拓扑/运行时补齐/WS 挂载设计/部署编排/依赖门禁/基准脚本定稿；P1 发现 G17/G18 列为 B0 级前置修复项）。
- **零代码变更 / 未提交**：本步仅文档。
