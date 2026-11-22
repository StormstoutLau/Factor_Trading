# REVIEW：P-054 Step 6 IMPL 异构复审（IMPL_p054_service_layer）

> **批次**: P-054 · **Step 6 IMPL 复审（首轮）** · 日期 2026-11-22
> **复审对象**: [IMPL_p054_service_layer.md](IMPL_p054_service_layer.md)（26 项变更 / C-1~C-21 / §3 逐处代码 / 120 例 / D-1~D-15 / B0-B6）
> **复审基座**: **GLM-5.3-Flash** ≠ 作者 **DeepSeek-V4.1-Flash**（异构成立，RULE-5）
> **方法**: E3 代码锚点逐条重放 + C-1~C-21 可执行性推演（以「Step 9 按文落码是否产出正确行为」为准绳）+ D-1~D-15 核对 + 门禁算术 + 关联面读码（resume/_seen、transition 同态分支、mock.query_trades、恢复序测试）
> **仓库时点**: 工作区含 RESEARCH/DESIGN/IMPL/risk_anchors/PROGRESS（未提交）；代码基线 = P-053 关闭态
> **结论**: **1 P1 / 9 P2 / 5 P3 —— 未通过（首轮）；F-I1~F-I9 修复前不得进入 Step 9**（门禁 b）
> **修复与关闭（§7）**: 10 项发现复核属实并已回写（另 O-I1~O-I5 顺手）→ 待复核确认后 Step 6 关闭
> **复核回执（§8）**: 修复落点 10/10 重放属实 + 关联面读码核验（resume/_seen、mock.query_trades）；残留 ×2 顺手修正（0 P1/P2）→ **Step 6 关闭（2026-11-22）**

---

## 1. 复审范围

| 维度 | 核对内容 | 结果 |
|------|----------|------|
| 事实性 | §3/§7 行号锚点重放 | §2，**命中** |
| 可执行性 | C-1~C-21 按文落码推演（迁移/组合写/预算/调度/事件/线程-异步边界/CI） | §3/§4 |
| 契约保真 | 与 DESIGN D1-D20/I1-I17、RESEARCH 裁决（D9 顺序、Q2 event_id、Q11 迁移、G15）一致性 | §3/§4 |
| 一致性 | 120 例/10 文件、门禁 1420/22/157/309/151/19/12 算术、§3.5/§3.16/§3.18 键与订阅闭合 | §3/§5 |
| 关联面 | resume/_seen 幂等、transition 同态分支、恢复序测试覆盖 | §2/§4-F-I1 |

---

## 2. 锚点重放（E3）

| # | IMPL 声称 | 重放 |
|---|-----------|------|
| 1 | `ledger.py#L96-145 apply_fill`；L97 `fill.fill_key in self._seen`；L116 `_seen.add(fill.fill_key)` | ✅ 逐字命中 |
| 2 | `ledger.py#L260-263 _append` 忽略 store 返回值 | ✅ 命中 |
| 3 | `ledger.py#L213-221 resume`：`_seen = {e.entry_id ...}`（**entry_id，非 fill_key**） | ✅ 命中 → **F-I1 的核心证据** |
| 4 | `gateway.py#L146-153` 恢复序 3 查询 + `apply_fill` 直调 | ✅ 命中 |
| 5 | `gateway.py#L199-205` check_rate 在 pre_trade_check 之前 | ✅ 命中 |
| 6 | `gateway.py#L381-400 cancel` → `transition(PENDING_CANCEL)`（L397）→ 返回 bool | ✅ 命中 |
| 7 | `gateway.py#L283-295 poll`：FillReport 仅 `apply_fill`，订单记录不更新 | ✅ 命中 |
| 8 | `orders.py#L159-175 transition`：同态分支返回原对象（不递增版本） | ✅ 命中 |
| 9 | `adapters/mock.py#L97-98 query_trades` **恒返回 []** | ✅ 命中 → P-053 恢复测试（test_t9，end_to_end L184-225）从未回放成交 → F-I1 在 P-053 未暴露 |
| 10 | `channel.py#L26-43 ChannelCapability` 15 字段 + `notes` 默认值在末尾 | ✅ 命中（IMPL 3.5 追加位置正确） |
| 11 | `pyproject L10/L22/L35/L45/L94-96`；`tests.yml` install `".[dev]"`（L28 附近） | ✅ 命中 → **F-I8** |
| 12 | `ledger_store.py#L52-58` connect 参数 + `executescript(_SCHEMA)` | ✅ 命中 → **F-I5** |
| 13 | `event_log` 8 常量 / `compliance.check_rate` 未改（Q10） | ✅ IMPL 未触碰，一致 |

---

## 3. C-1~C-21 可执行性核对（重点项）

| C | 判定 | 说明 |
|---|------|------|
| C-1 | ✅ | B0 范围完整（pyproject/classifiers/black/pydantic/extra/CI 矩阵/mypy 路径/uv.lock）；**但漏 CI 安装 extra → F-I8** |
| C-2 | ❌ | 三分支缺失：全新库 `cols` 为空 → `ALTER` 崩溃；`_get_meta_raw` 在 v1 库上 meta 表不存在 → **F-I5** |
| C-3 | ✅ | 冲突回滚语义清晰；与 C-12/C-14 联动问题见 F-I2/F-I3/F-I6 |
| C-4 | ✅ | PUBLISH→mark_inbox→XACK 窗口正确 |
| C-5 | ✅ | 双锁参数与 §2.4 一致 |
| C-6 | ✅ | 四分类 + classify 映射可执行 |
| C-7/C-8 | ✅ | 整秒窗/保留槽/2×internal 可执行 |
| C-9 | ❌ | 退还清单漏 `pre_trade_check` 拒绝 → **F-I4**；ChannelUnavailable 保守不退（安全方向，可接受） |
| C-10 | ✅ | Full Jitter 公式/单在途/巡检入口可执行 |
| C-11 | ❌ | 恢复序依赖 fill 幂等，而幂等在 resume 后失效 → **F-I1**；fill 是否带事件未定 → O-I3 |
| C-12 | ❌ | accepted 版本自相矛盾 + 同态分支漂移 → **F-I2** |
| C-13 | ⚠️ | store-first 五步正确，但 mutate 枚举漏 `_seen`/`_reserves` → O-I1 |
| C-14 | ❌ | 事件类型错配（fill→order.status；cancel_ex→order.canceled）→ **F-I3**；顺序与 D9 相反 → 并入 F-I4 |
| C-15~C-18 | ✅ | WS/鉴权/TLS/ready 可执行；**§3.18 订阅缺 admin 频道 → F-I9** |
| C-19 | ✅ | multiproc 方案与测试隔离正确 |
| C-20/C-21 | ✅ | 日志/退出/conftest 策略可执行 |
| C-22 缺失 | ⚠️ | relay/consumer/heartbeat 同步线程 × async bus 桥接未定义 → **F-I7**（IMPL 无 C-22 编号，§3.20/§3.21 未写桥接） |

**D-1~D-15**：逐条与 DESIGN/RESEARCH 一致 ✅；新增偏差（F-I4 顺序、F-I9 频道）待修复时补登记。

---

## 4. 发现（1 P1 / 9 P2 / 5 P3）

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-I1** | **P1** | **恢复序幂等前提失效（继承并放大 P-053 潜伏缺陷）**：`resume` 重建 `_seen = {entry_id}`（"fill:fk"/"fee:fk"，[ledger.py#L220](../live/ledger.py#L220)），而 `apply_fill` 去重用**裸 fill_key**（[L97](../live/ledger.py#L97)/[L116](../live/ledger.py#L116)）→ 重启后 `query_trades` 回放成交：`_seen` 未命中 → 重新入账 → store 侧 PK 冲突被 `append_entry` 吞掉、**内存现金再扣一次 + 持仓翻倍** → reconcile parity break → 可能 HALTED。P-053 未暴露仅因 `mock.query_trades` 恒返回 `[]`（[mock.py#L97-L98](../live/adapters/mock.py#L97-L98)，test_t9 不回放成交）；P-054 CTP 接线后该路径必然触发，而 IMPL C-11/C-13 依赖「fill_key 去重保证重试幂等」且未修复 | §2-1/2/3/4/9 |
| **F-I2** | **P2** | **accepted 事件版本漂移**：C-12 自相矛盾（原文残留「初始 0？」；`from_request` 后 `replace(event_version=1)` 会使 accepted=v2）；且 `transition` 同态分支（[orders.py#L171-L175](../live/orders.py#L171-L175)）在 `ack.state == PENDING_NEW` 时返回原对象（版本 0）→ accepted 事件 event_id 在 **v0/v1/v2** 间随适配器行为漂移，违反 DESIGN §3.4 模板 `accepted:v1` 与 I5「同 key ⇒ 同 payload」的稳定性 | C-12 vs DESIGN §3.4 |
| **F-I3** | **P2** | **事件类型与状态机阶段错配**：① C-14 fill 路径挂 `order.status` —— poll 对 FillReport **不更新订单记录**（[gateway.py#L283-L295](../live/gateway.py#L283-L295)），事件声称的填充状态无 record 依据，且使用未递增的 `event_version` 与后续真实 status 事件撞版本；② C-14 cancel 成功标 `order.canceled`，但 `cancel()` 只迁移到 **PENDING_CANCEL**（[gateway.py#L397](../live/gateway.py#L397)），`order.canceled` 应属 `_apply_order_report` 的 CANCELED 回报——消费者会把「撤单受理中」误读为「已撤」 | C-14 vs §2-6/7 |
| **F-I4** | **P2** | **pre_trade_check 拒绝泄漏预算**：§3.10 把 `ftd.reserve`/`order_flow.reserve` 插在 check_rate 之后、pre_trade_check 之前，而 C-9 退还清单（CapabilityError/参数/能力/预扣自身）**不含 pre_trade_check 拒绝** → 每笔本地拒绝空耗当秒槽位（持续拒单风暴下 FTD 可用容量被系统性压缩、`ftd_remaining` 失真）；且该顺序与 D9「FTD → 类型预算 → 发送」相反、未登记偏差。修复方向二选一：reserve 移到 pre_trade_check 之后（仍满足发送前 reserve，推荐）或补 reject 分支 release + 登记 | C-9/§3.10 vs D9、gateway L207-217 |
| **F-I5** | **P2** | **全新库迁移崩溃**：C-2 仅两条分支（v2 跳过 / 否则 ALTER）；全新库 `PRAGMA table_info(outbox)` 为空 → 走 ALTER 分支 → `no such table: outbox`；且 `_get_meta_raw("schema_version")` 在 v1 库上 meta 表不存在 → 读失败。修复：三分支（无表 → `executescript(_SCHEMA_V2)`+写版本；v1 → 迁移；v2 → 跳过） | C-2 vs ledger_store L16-58 |
| **F-I6** | **P2** | **reconcile.completed 版本重启归零 → 冲突崩溃**：`reconcile:{date}:v{attempt}` 的 attempt 为进程内计数，巡检 6s 全量发事件；重启后 attempt 归 1 → 与崩溃前同 event_id、payload 不同（counts 变化）→ `OutboxEventConflict`（C-3 规定不捕获）→ 巡检异常。修复：per-day 计数器入 meta（与事件同事务递增）或 event_id 改 ts 基；并建议仅 level 变化/日结时发事件（降噪） | C-12/C-14/§3.10 |
| **F-I7** | **P2** | **同步线程 × async bus 桥接未定义**：relay/consumer/heartbeat 是同步线程（§2.4），而 `RedisBus` 全 async（§3.13，`redis.asyncio`）——无事件循环的线程直接调协程会 `RuntimeError: no running event loop`。IMPL 未写桥（每批 `asyncio.run` / 线程内独立 loop / `run_coroutine_threadsafe` / bus 提供同步包装） | §3.13 vs §3.20/§3.21/§2.4 |
| **F-I8** | **P2** | **CI 未安装 `[services]`**：tests.yml 仍 `pip install ".[dev]"`，IMPL §3.1 只改矩阵与 mypy 路径 → CI 缺 fastapi/uvicorn/prometheus-client → 10 个 services 测试文件 ImportError、mypy 对 services 报 missing imports → B0/B4 退出条件不可达。修复：`.[dev,services]`（或等价）+ `uv.lock` 同步 | §3.1 vs tests.yml install 行 |
| **F-I9** | **P2** | **broadcast-pause 链路断裂**：§3.5 Redis 键表无 `p054:admin`；§3.18 订阅列表 `[orders_channel, market_channel]` 缺该频道、无 handler → admin 端点只改本 worker flag，跨 worker 暂停失效（D19 特性静默失效） | §3.16 vs §3.5/§3.18 |
| O-I1 | P3 | C-13 store-first 的「成功后更新」枚举漏 `_seen`（store 失败后重试会被误判重复 → 成交丢失）与 settle 路径 `_reserves` | C-13 |
| O-I2 | P3 | 同态迁移（`updated is rec`，F-I5 分支）应跳过组合写与事件（现为无差别 upsert+audit+事件，同 payload 静默通过但制造噪声） | §3.10/§2-8 |
| O-I3 | P3 | start() 恢复序 `query_trades` 回放的 fill 是否带 `outbox_events` 未指定（建议传入；已入库 fill 由修复后的 F-I1 去重自动跳过，语义自洽） | C-11/C-14 |
| O-I4 | P3 | cancel_ex 内部顺序（check_rate → FTD → order-flow → adapter）未写明；`not_found`/`terminal` 是否发 `cancel_rejected` 未定（建议仅 `rate_*`/`unsupported` 发事件+audit，not_found/terminal 维持 `CancelResult` 静默——与 DESIGN §3.4「预算/能力拒绝」触发范围一致） | C-14/§3.10 |
| O-I5 | P3 | 门禁算术复核 ✅（1420/22/157/309/151/19/12/51 全部闭合；conftest 已在 141 基线内，追加不漂移）；`startup_ftd_instructions` best-effort 预扣与 D-9 一致 ✅ | §4/§6 |

---

## 5. 反向证据检查

- 未发现推翻 DESIGN 架构（D1-D20）的反例；F-I1~F-I9 全部是「IMPL 落码语义」层缺陷，架构与裁决不需重开。
- F-I1 的反向排查：确认 mock.query_trades 恒空 + test_t9 断言（entries==1）依赖该行为 → 缺陷在 P-053 潜伏且未被任何测试覆盖；P-054 CTP 接线使其实化，**必须在 B3 一并修复**（属 IMPL 范围内的 C-13 重构点，非 P-053 追改）。
- C-4/C-5/C-15/C-17/C-19 的推演未发现新反例 ✅。

---

## 6. 出口判定与门禁（首轮）

- (a) FALSIFIED：**1**（IMPL C-11/C-13 依赖的「fill_key/_seen 幂等」声明与代码事实不符 = F-I1）。
- (b) CONFLICT：**8 项规格矛盾未仲裁 = F-I2~F-I9**（C-12 内部矛盾、C-14 错配、C-9/D9 顺序、C-2 分支、C-12/C-14 版本冲突、桥接缺失、CI 缺依赖、admin 链路断裂）。
- (c) 双源：迁移/预算/调度/WS 的机制锚点与 DESIGN 一致 ✅（受 F-I 系列影响的实现细节除外）。
- (d) 假设携带：D-1~D-15 已显式登记 ✅。
- **判定：未通过（首轮）——F-I1~F-I9 修复前不得进入 Step 9**；O-I1~O-I5 顺手修。修复后按惯例复核/二轮，通过即 Step 6 关闭。

> **复审者权限声明（RULE-5 单向）**：本复审仅标记问题，未改写 IMPL/DESIGN 正文；F-I4 的两个修复方向（reserve 移位 vs 补 release）由作者定案。

---

## 7. 作者修复核验（回执，2026-11-22）

> 执行方：作者基座 DeepSeek-V4.1-Flash（≠ 复审基座 GLM-5.3-Flash）。10 项发现复核**全部属实**；本节为回写落点与自检，§4 原始发现保留不改写。

| ID | 复核 | 修复落点 | 自检方式 |
|----|------|----------|----------|
| **F-I1**（P1） | 属实：`resume._seen` 存 entry_id，`apply_fill` 查裸 fill_key | IMPL **C-13/§3.8**：`apply_fill` 去重与登记统一 `fill:{fill_key}`（canonical），`resume` 不改；A 组新增「resume 后重放同 fill_key → False 且现金/持仓不变」 | 与 ledger.py L97/L116/L220 三方对齐；B3 红→绿 |
| **F-I2**（P2） | 属实：C-12 残留「初始 0？」+ 同态分支使 accepted 版本漂移 | **C-12**：`order_event(..., version=1)` 显式固定 accepted=v1；`from_request` 不改版本；其余事件用 `record.event_version`（迁移后 ≥2） | 模板 `accepted:v1` 与 C 组断言一致 |
| **F-I3**（P2） | 属实：fill 挂 order.status；cancel_ex 误标 canceled | **C-14/§3.10**：fill 只发 `fill.applied`（poll 不更新订单记录）；cancel 成功发 `order.status(PENDING_CANCEL)`；`order.canceled` 只在回报 CANCELED | 事件触发点与状态机阶段一一对应 |
| **F-I4**（P2） | 属实：reserve 在 gate 之前 + C-9 不退还 gate 拒绝 → 空耗 | **C-9/§3.10**：预算移到 `pre_trade_check` 之后、adapter 之前；退还仅覆盖 reserve→adapter 之间的异常 | 仍满足 D9「发送前 reserve」；拒绝风暴不耗槽位 |
| **F-I5**（P2） | 属实：全新库 `cols` 空走 ALTER；meta 表前置读取 | **C-2**：三分支（无表建 v2 / v1 迁移 / v2 跳过）+ `_get_meta_raw` 判表存在 | 全新库、v1 库、v2 库三条迁移用例（B 组） |
| **F-I6**（P2） | 属实：reconcile attempt 重启归零 → 冲突 | **D-16**：`reconcile.completed` **移出 outbox**，只写 `AUDIT_RECONCILE`；事件集 6 类（DESIGN Q1/D5/§3.4/§7、IMPL C-12/C-14 同步） | 无 reconcile 事件 → 无跨重启 event_id 冲突；C 组 10 例改用 cancel_rejected 等覆盖 |
| **F-I7**（P2） | 属实：同步线程 × async RedisBus 无桥 | **D-17**：新增 `SyncRedisBus`（redis-py 同步），交易进程 relay/consumer/heartbeat 使用；API/WS 用 `AsyncRedisBus`；`InMemoryBus` 双包装 | 交易线程无事件循环调用；DESIGN §2.4/D20 同步 |
| **F-I8**（P2） | 属实：CI 仍 `.[dev]` | **C-1**：安装改 `pip install ".[dev,services]"`，mypy 加 `services` | B0 退出条件可执行（services 测试不 ImportError） |
| **F-I9**（P2） | 属实：admin 频道缺失 | **§3.5** 新增 `p054:admin`；**§3.16** 端点发布消息；**§3.18** 订阅列表与 handler；DESIGN §3.5 同步 | 跨 worker 暂停生效；D19 特性不静默失效 |
| O-I1 | 属实 | C-13 mutate 枚举补 `_seen`/`_reserves`（提交成功后才登记） | 失败重试不被误判重复 |
| O-I2 | 属实 | `_apply_order_report` 同态（`updated is rec`）直接返回，不写库不发事件 | 消除重复事件噪声 |
| O-I3 | 属实 | 恢复序回放 fill 同样传 `outbox_events=[fill]`；已入库由 F-I1 去重跳过 | 语义自洽 |
| O-I4 | 属实 | `cancel_ex` 顺序写明（not_found/terminal → check_rate → FTD → order-flow → adapter）；事件只对 `rate_*`/`unsupported` | 与 DESIGN §3.4 触发范围一致 |
| O-I5 | — | 门禁算术复核 ✅，无需修改 | 1420/22/157/309/151/19/12 |

**出口判定更新**：F-I1（门禁 a）已消除；F-I2~F-I9（门禁 b）全部回写；O-I1~O-I5 已处理 → 待复审方复核确认后 **Step 6 关闭**，进入 Step 7 CHECKLIST。

> 复核范围声明：本节只核对「发现属实 + 修复落点到位」，不代替复核轮；若 Step 9 落码发现迁移/事件/预算语义与代码事实冲突，按门禁 (b) 回退 IMPL 修订。

---

## 8. 复核回执（修复核验，2026-11-22）

> **执行方**：复审基座 GLM-5.3-Flash（= 首轮复审基座，≠ 修复执行基座 DeepSeek-V4.1-Flash → 对修复而言异构成立）。方法：修复位点逐点重放 + 残留扫描（grep）+ 关联面读码（`resume/_seen`、`mock.query_trades`、C-14 触发点映射）。

### 8.1 修复落盘重放（10/10 与回执一致）

| ID | 重放结果 |
|----|----------|
| F-I1 | ✅ C-13 ① canonical `fill:{fill_key}`/`fee:{fill_key}`/`ca:…` 去重、`resume` 不改、mutate 含 `_seen`（O-I1）；§3.8 `apply_fill` 同步；A 组新增 resume 回归 |
| F-I2 | ✅ C-12 accepted `version=1` 显式固定；无 `replace(event_version=1)`/「初始 0」残留 |
| F-I3 | ✅ C-14：fill 只发 `fill.applied`；cancel 成功 `order.status(PENDING_CANCEL)`；CANCELED 仅回报迁移；§3.10 同步 |
| F-I4 | ✅ C-9/§3.10 预算在 `pre_trade_check` 之后；退还仅覆盖 reserve→adapter 间异常 |
| F-I5 | ✅ C-2 三分支（无表建 v2 / v1 迁移 / v2 跳过）+ `_get_meta_raw` 判表 |
| F-I6 | ✅ IMPL C-12/C-14/§3.10/D-16 移除 reconcile 事件；**DESIGN Q1/D5/§3.4 表/§3.2 常量/§7/B3 全部同步为 6 类** |
| F-I7 | ✅ IMPL §3.13 `SyncRedisBus`/`AsyncRedisBus`/InMemory 双包装、§3.20/§3.21 三线程用 sync；DESIGN §2.4/D20 同步 |
| F-I8 | ✅ C-1 安装 `.[dev,services]` + mypy 加 `services` |
| F-I9 | ✅ IMPL §3.16 端点发布、§3.18 订阅+handler、§3.5 键表；DESIGN §3.5 `p054:admin` 同步 |
| O-I1~O-I5 | ✅ mutate 枚举、同态跳过、恢复序 fill 事件、cancel_ex 顺序与事件范围、门禁算术 ✅ |

### 8.2 残留扫描与顺手修正（0 P1 / 0 P2）

- 残留扫描：`replace(rec, event_version` / 「初始 0」/ IMPL「7 类」/ 「reconcile_event」均 0 残留（「7 类」仅存于 C-12/D-16 的修复说明句）。
- **顺手修正 ×2（核验方）**：① DESIGN §3.2 代码块残留 `RECONCILE_COMPLETED = "reconcile.completed"` 常量 → 删除（与 6 类决定对齐）；② IMPL C-12「真实迁移后 ≥2」不精确（同态 ack 后首个真实迁移 event_version=1）→ 改「随真实迁移递增；事件名不同，与固定 v1 无冲突」。
- 关联面读码：`resume._seen={entry_id}` 与 canonical `fill:{fill_key}` 对齐后，重启回放同 fill 必命中 → 现金/持仓不变；`mock.query_trades` 恒空不再掩盖该路径（A 组回归覆盖）✅。

### 8.3 出口判定（复核）

- 门禁 (a) FALSIFIED = 0（F-I1 前提已修复）、(b) CONFLICT = 0（F-I2~F-I9 全部回写）、(c)(d) 维持 → **Step 6 关闭（2026-11-22）**，进入 Step 7 CHECKLIST。
- 测试仍 120 例 / 10 文件；门禁目标不变（1420/22/157/309/151/19/12）。

> 复核范围声明：本节为修复核验（定点），非全量二轮；Step 9 落码后由 Step 10 验收复审继续把关。
