# RESEARCH：升级总纲 §7 十四项开放问题调研

> **定位**: `UPGRADE_MASTER_PLAN.md` 的 pre-batch RESEARCH 阶段产物（非单个 SPEC 批次）。为 P-042~P-058 的立项裁决提供证据、选项与推荐，不替代用户决策。
> **日期**: 2026-11-17 · **总纲基线**: `693b82e`（复审修订后）· **代码基线**: P-041 关闭（`0196e24` 功能提交；门禁 778 / golden 13·765 / mypy 103 files 0 / tests 87 / uv 0）
> **方法**: 官方监管文件/交易所规则/厂商文档 + 社区实践/论坛 + 本仓库代码锚点（E1/E3）。**E5 推测未入结论**；厂商/社区口径均标注来源与不确定性。
> **前置警示**: 2026 年 A 股程序化交易通道发生结构性变化——**miniQMT 被多家券商关停、QMT 标准版收紧文件/网络权限**。总纲初稿 F6/P-053 的「Windows + xtquant 常驻网关」假设已不稳健，**Q1/Q14 必须先裁决，才能立项 P-053**。

---

## 0. 结论速览（14 项推荐）

| # | 开放问题 | 推荐结论 | 置信度 | 需用户确认 |
|---|----------|----------|--------|------------|
| 1 | QMT 仅 Windows + 客户端依赖 | 不做单一 QMT 绑定；P-053 先过「通道可行性门」，按 券商机构 API / QMT 标准版 / PTrade / CTP 四选一或组合，适配器隔离 | 高 | 已裁决（D1：多通道预留） |
| 2 | 「毫秒级」预期 | 分四级 SLA：源 3s（L1）/10–50ms（L2）、总线 p99≤20ms、WS p99≤50ms、下单确认 p99≤100ms；不承诺「毫秒级交易」 | 高 | 是 |
| 3 | 做空账目 U-P031-1 | **期货保证金账目优先**（IF/IC/IM），股票负持仓降为研究模式；转融券暂停后个股做空实盘不可依赖 | 高 | 已裁决（D3：期货优先） |
| 4 | CTP 范围 | 锁定期货/期权；A 股现货走券商 API/QMT/PTrade；CTP 用 openctp（Linux/Windows，Python 3.7–3.13） | 高 | 是 |
| 5 | 舆情合规与成本 | 一期**开源优先**（AKShare/交易所/巨潮公告）；Tushare 新闻可选（约 1000 元/年）；无社交爬虫；预算 0–4000 元/年 | 中高 | 是 |
| 6 | 数据源统一 | 以 `DataProvider` 为唯一端口，data.py/data_v3.py 降为适配器；矩阵指纹 + golden **默认零重录**，重录须显式裁决 | 高 | 是 |
| 7 | PyPortfolioOpt | **不进核心运行时**；核心用 cvxpy/scipy 自研，PyPortfolioOpt 仅 `[research]` extra 做参考解对拍 | 高 | 是 |
| 8 | regime 防过拟合 | 滚动重估 + 滤波概率（非平滑）+ BIC 选态 + 样本外/PBO；禁止全样本拟合与在线学习 | 高 | 是 |
| 9 | 合规定位与报备 | 定位**自用工具**；实盘前完成券商程序化交易报告；下单速率远低于高频阈值（300/s、20000/日）；API 仅本机/内网 | 高 | 已裁决（D2） |
| 10 | parity 阈值 | 分层阈值：同数据重放持仓/现金精确；回测↔paper 权重 L1≤1e-6、均价≤5bps；paper↔live 均价≤10bps（流动）/30bps（小盘）、成交率≥95% | 中高 | 是 |
| 11 | 多策略共享账户 | 虚拟子账户 + 下单前资金/持仓预留 + 跨策略净额 + 分层优先级/FIFO + 单策略 kill switch | 高 | 是 |
| 12 | 公司行为/交易日历 | 本地快照 + 每日更新；实盘以柜台为准，研究以 AKShare/交易所为主、Tushare 可选；对账先归因公司行为 | 高 | 是 |
| 13 | 可观测性栈 | 最小栈：结构化日志 + 轻量 metrics + IM/邮件告警；Prometheus/Grafana 后置 | 高 | 是 |
| 14 | QMT Python/extra 隔离 | 独立 `[qmt]` extra + Windows venv；不假设 3.12；QMT 内置 3.6.x 与主代码不兼容，需独立移植层或放弃集成 | 高 | 已裁决（D4） |

> **P0 四项已于 2026-11-17 裁决（D1-D4）**：P-053 可立项，但仍先交付通道可行性门 + `MockLiveBridge` 骨架；真实通道按账户可用性逐个接入。

### 0.1 用户裁决（2026-11-17）

| ID | 事项 | 裁决 |
|----|------|------|
| **D1** | Q1/Q14 交易通道 | **多通道预留**：机构 API / QMT / PTrade / CTP / 半自动全部保留适配器，不锁定单一券商或终端 |
| **D2** | Q9 合规定位 | **自用工具 + 完成程序化报备** |
| **D3** | Q3 做空路线 | **期货账目优先，股票融券仅研究** |
| **D4** | Q14 QMT 隔离 | **接受独立 Windows venv + 可能的 3.6 移植层** |

**配套数据策略**: **宜粗不宜细**，先把框架跑通；数据优先级 = 开源（AKShare/交易所/巨潮）> synthetic fixture > 付费（Tushare 可选）> 本地在建管道（`E:\Macro_Data` / `E:\FinDatasets` / `F:\Open_Data`，**仅分析、暂不接入**）。

---

## 1. 方法与证据分级

| 级别 | 本次用法 | 说明 |
|------|----------|------|
| E1 | 官方监管文件、交易所规则、厂商文档、PyPI 元数据、本仓库可重放命令 | 可直接引用；链接见 §7 |
| E2 | 未使用 | 本次为案头调研，无账户/柜台环境，不伪造运行时探针 |
| E3 | 代码锚点（`core/`、`pyproject.toml`、CI） | 与 P-041 基线一致 |
| E4 | 盲区扫描（安全/合规/日历/公司行为） | 已在总纲 §10 记录；本文补充外部证据 |
| E5 | 推测 | **未入结论**；社区传闻/单一来源均标「待券商确认」 |

**局限**: 未接触用户实际券商账户，无法确认其 QMT/PTrade/机构 API 权限；凡涉及「你的账户能否开通」均列为待确认，不作为既定事实。

---

## 2. 关键背景：2026 年交易通道变局（Q1/Q14 前置）

### 2.1 时间线（外部证据）

| 时间 | 事件 | 来源 |
|------|------|------|
| 2024-10-08 | 《证券市场程序化交易管理规定（试行）》施行，程序化交易须**先报告、券商核查后向交易所报告、客户收到确认后方可交易** | 证监会〔2024〕8 号 |
| 2025-07-07 | 沪深北《程序化交易管理实施细则》施行；高频认定 = 单账户每秒申报+撤单 **≥300 笔** 或 全日 **≥20000 笔**；高频额外报告（服务器所在地、测试报告、应急方案） | 上交所/人民网 |
| 2025-10-09 | 《期货市场程序化交易管理规定（试行）》施行；期货客户交易前向期货公司报告 | 证监会〔2025〕12 号 |
| 2026-07 | 多家券商停止 miniQMT 新申请；存量用户分批清理（社区口径） | miniqmt.com / 迅投社区 |
| 2026-08-28 | 中证协+中基协《证券公司交易信息系统接入管理规范（试行）》发布并施行；券商接入业务须向中证协备案，强调验资验券、阈值管理、异常监测、非法接入阻断 | 中证金牛座/AMAC |
| 2026-10-21 | 华鑫证券公告：**2026-10-30 收盘后关闭 miniQMT**（个人及普通机构） | 华鑫证券官网 |
| 2026 年内 | 部分券商 QMT 标准版关闭内置 Python 的**本地文件读写与外部网络连接**；第三方库走白名单 | 东方财富财富号/社区/券商通知转述 |

> **判断**: miniQMT（本地 Python + `xtquant` 直连）正在退出；QMT 标准版（大 QMT）保留但变成**封闭沙箱**；PTrade 是**券商云端沙箱**；只有券商机构 API / CTP 才支持真正的外部程序接入。这直接推翻总纲初稿「Windows 网关 + xtquant 常驻 + Redis/WS 集成」的默认路径。

### 2.2 四类通道能力矩阵

| 通道 | 运行位置 | Python | 外部文件/网络 | 与本地平台集成 | 品种 | 门槛/可行性 |
|------|----------|--------|----------------|----------------|------|-------------|
| **miniQMT（xtquant）** | Windows 本机 | 3.6–3.13（PyPI 最新 250807.1.2） | 允许（但通道在关停） | 可（HTTP/gRPC/文件桥） | 股票/ETF/可转债/两融（券商权限） | **新申请已停；存量清退中** |
| **QMT 标准版内置 Python** | Windows 本机 QMT 客户端 | 3.6.x（官方文档 3.6，API 文档 3.6.8） | **2026 起多地关闭**；库白名单 | **不可**（封闭沙箱） | 股票/两融/部分期货期权（券商配置） | 10–50 万资产，需券商开通 |
| **PTrade** | 券商云端容器 | 券商白名单 | **不可**（单文件、库裁剪、无外网） | **不可** | 股票/ETF/LOF/可转债/两融/股指期货（版本差异） | 10–50 万资产，需券商开通 |
| **券商机构 API**（宽睿 OES/华锐/恒生 UFT 等） | 券商机房/托管 | C/C++/Java/Python | 允许（专线/网关） | 可 | 股票/两融/期权等 | **高**（部分要求 300 万资产/机构资质） |
| **CTP**（openctp/vnpy_ctp） | 本地/托管 | 3.7–3.13 | 允许 | 可 | **仅期货/期货期权** | 期货账户 + 程序化报备 |

**结论**: 若目标是「本地平台 + FastAPI/WS + 自动下单」的一体化架构，**只有券商机构 API 或 CTP（期货）能完整满足**；若只有 QMT/PTrade，则平台必须降级为「研究/回测/监控 + 订单清单生成 + 人工确认」，交易在终端内闭环。

### 2.3 实施粒度与数据策略（用户裁决）

- **宜粗不宜细**: 接口/契约/骨架先落地；生产级数据、性能优化、多源容灾后置。
- **每批必须有无外部数据的 synthetic fixture + golden/重放测试**；数据源不可用时自动降级，禁止因数据缺失阻断开发。
- **数据优先级**: 开源（AKShare/交易所公告/巨潮）→ synthetic fixture → 付费（Tushare 可选）→ 本地在建管道（`E:\Macro_Data` / `E:\FinDatasets` / `F:\Open_Data`，**仅分析、暂不接入**）。
- **不做（本周期）**: 社交爬虫、生产级多源容灾、Grafana/Loki/Tempo 全栈、复杂多用户权限系统。

---

## 3. 逐项分析

### Q1. QMT 仅 Windows + 客户端依赖：部署拓扑怎么定？

**框架现状（E3）**
- `core/live_bridge.py` 仅有 `LiveTradingBridge` ABC（L69-128）+ `MockLiveBridge`（L144-242），无任何真实柜台子类；`live/` 目录不存在。
- `web/server.py` 仅静态文件服务器；无 FastAPI/WS。
- `docker-compose.yml` 单镜像，无 Redis/服务拆分。

**外部证据（E1/E4）**
- xtquant PyPI：**Windows x64 only**，Python 3.6–3.13，最新 `250807.1.2`（2026-07-21）。
- 华鑫证券 2026-10-21 公告：2026-10-30 收盘后关闭 miniQMT。
- QMT 官方 FAQ：同一 `session_id` 两次进程 connect 需间隔 >3 秒；重连需更换 `session_id`。
- QMT 标准版内置 Python 3.6.x；券商库白名单；2026 起关闭文件读写/外网。
- PTrade：策略跑在券商云容器，单文件、库裁剪、无外网、不能用本地 IDE。
- 券商机构 API：宽睿 OES 提供 C/Java/Python API；部分券商量化服务门槛 300 万。

**选项**
| 选项 | 拓扑 | 优点 | 缺点 |
|------|------|------|------|
| A. Windows xtquant 网关 | Windows 网关进程 + Linux 服务层（Redis/gRPC） | 复用现有 ABC；本地可调试 | miniQMT 关停；不可持续 |
| B. QMT 标准版封闭策略 | 策略整体搬进 QMT 沙箱 | 合规、券商管控 | 3.6 语法、无文件/网络、无法与平台集成 |
| C. PTrade 云端 | 策略搬进券商云 | 免运维、托管 | 单文件、无外网、无法集成 |
| D. 券商机构 API | 券商网关/托管 + 本地平台 | 真正外部接入、低延迟 | 门槛高、审批长、券商绑定 |
| E. CTP（仅期货） | Linux/Windows 网关 | 开源、可集成、低延迟 | 仅期货/期权 |
| F. 半自动 | 平台生成订单清单 → 人工在 QMT/PTrade 执行 | 合规、零对接 | 非自动 |

**推荐**
1. **不做单一 QMT 绑定**。P-053 改名为「交易通道网关」，第一步交付**通道可行性门**（`ChannelCapability`）：账户层级、可用 API、品种、速率限制、合规报备状态。
2. 默认支持两类适配器：`BrokerApiBridge`（机构 API，完整集成）与 `CtpBridge`（期货，完整集成）；`TerminalBridge`（QMT/PTrade）仅做**订单清单/人工确认**的半自动适配。
3. Windows 仅作为「通道要求的宿主」存在；服务层保持 Linux；跨进程用 REST/gRPC/Redis，**每账户单写者**，凭据不跨进程共享。
4. 若用户只有 QMT/PTrade：明确接受「平台不自动下单」，WS 只推送研究/监控/订单建议，不推送交易执行状态。

**对总纲影响**: §2.1 LIVE 层、§3 F6、§5 P-053、§7 D1/D4 已改写；P-053 前置增加「通道可行性门」。

**待确认**: 你的券商/账户能开通哪一类通道？是否有 300 万级机构 API 资格？是否接受半自动？

---

### Q2. 「毫秒级」预期管理

**框架现状（E3）**
- 数据为批量 pkl/NumPy；V2 逐日 bar 循环；无流式契约、无 tick 处理。
- `engine_v3_vector.py` 是向量化回测，不是实时路径。

**外部证据（E1）**
- 上交所历史数据接口：Level-1 快照间隔 **3 秒或 5 秒**（个股及部分指数 3 秒，部分指数 5 秒）。
- 上交所 Level-2 产品：十档盘口 + 逐笔成交 + 订单关联。
- QMT 官方 FAQ：`get_full_tick` 盘中 **50ms** 更新一次，无需订阅、无品种数量限制；`subscribe_quote` 首次订阅耗时长、有最大订阅数。
- 券商实测口径（社区）：L2 Tick 从交易所→券商网关→本地 QMT 常见 **10–50ms**；L1 3 秒快照不适合高频。
- FastAPI 多 worker：内存广播只在单进程有效；跨 worker 需 Redis pub/sub 或 Streams；Redis pub/sub 在 5000 连接压测下可能成为瓶颈，建议 Streams + 批量拉取/按主题分片。

**推荐 SLA（写入 P-054 验收）**
| 层 | 指标 | 目标 |
|----|------|------|
| 行情源 | L1 快照 | 3s（部分指数 5s），不承诺更快 |
| 行情源 | L2 逐笔/十档 | 10–50ms（券商/网络决定） |
| 网关→总线 | 解析+入队 p99 | ≤20ms |
| 总线→WS 客户端 | 端到端 p99 | ≤50ms |
| 下单确认 | 委托→柜台确认 p99 | ≤100ms（柜台决定，不保证） |

> 对外表述统一为「**毫秒级内部推送，行情源受交易所频率限制**」；禁止使用「毫秒级交易」营销口径。

**对总纲影响**: §3 F7「延迟现实」保留并量化；P-054 增加延迟基准与分位报告。

**待确认**: 是否接受「L1 3s / L2 10–50ms」为现实上限？

---

### Q3. 做空账目（U-P031-1）：本周期做不做？

**框架现状（E3）**
- `tracker.py` 为多头账目；U-P031-1 记录「中性策略负持仓账目（保证金/借券/负市值盯市）」为 P2。
- `execution_policy.py` 有 `T0FuturesPolicy`（L259），但无期货保证金/逐日结算/强平账目。
- `OrderIntent` 支持 SELL/BUY；`LiveOrder.side` 预留 `SELL_SHORT/BUY_TO_COVER`，但后端未实现。

**外部证据（E1）**
- 证监会 2024-07-10：批准中证金融**暂停转融券**，自 2024-07-11 实施；存量合约可展期但不得晚于 2024-09-30 了结。
- 2024-07-22 起融券保证金比例由 80% 上调至 100%，私募基金由 100% 上调至 120%。
- 新华网 2024-08：融券余额降至约 **137 亿元**，较峰值下降逾九成；转融券余额跌破百亿。
- 上海证券报 2025-11：市场中性策略「只能用股指期货对冲」，对冲端集中在 IF/IC/IM。
- 中证网 2024-08：量化多空/中性策略迭代方向——空头端加入多品种股指期货，降低单一对冲端波动。
- 券商研报：IC/IM 空头部分向 IF 转移，参考比例 30–50%；「买期货 + 融券卖 ETF」需基差收益覆盖融券成本。
- 中金所：保证金制度、持仓限额（客户某一合约单边 600 张）、强制平仓、每日无负债结算；IF/IH/IC/IM 保证金约 12–14%（券商在交易所基础上加收）。

**选项**
| 选项 | 内容 | 适用 |
|------|------|------|
| A. 股票负持仓账目 | 借券费、保证金、召回、负市值盯市 | 回测研究；实盘不可依赖 |
| B. 期货保证金账目 | 保证金、逐日结算、变动保证金、强平、换月、基差 | **实盘对冲/月差必需** |
| C. 两者都做 | A+B | 工作量最大 |

**推荐**
1. **期货账目优先**：把 P-050 改为「空头与期货账目」，先交付 IF/IC/IM 的保证金、逐日结算、强平、换月、基差；这是市场中性/月差实盘化的硬前置。
2. 股票负持仓作为**回测研究模式**（P-050B，可后置）：用于因子多空组合的真实性检验，不假设实盘可融券。
3. P-058 截面多空模板**默认用股指期货对冲**；股票融券仅作为可选开关，并在报告中标注「研究假设」。
4. 回测 golden 不受影响：新增账目走独立 golden；纯多头既有 golden 零重录。

**对总纲影响**: §5 P-050 内容/验收、P-058 模板口径、F5 模板说明；§1.4 U-P031-1 的关系描述需改写。

**待确认**: 是否接受「期货优先、股票负持仓降为研究」？若坚持股票融券实盘，需先确认券源与费率。

---

### Q4. CTP 范围：只做期货/期权？

**框架现状（E3）**
- `core/config.AssetType` 含 `STOCK/FUTURE/OPTION`；`execution_policy.T0FuturesPolicy` 存在。
- 无 CTP 适配器、无期货账目、无换月/限仓逻辑。

**外部证据（E1）**
- CTP 仅覆盖期货/期货期权；A 股现货/两融不走 CTP。
- `openctp-ctp`：Python ≥3.7，支持 3.12/3.13，Linux glibc 2.17+，BSD-3；`ctp-python` 支持 3.7–3.13。
- 《期货市场程序化交易管理规定（试行）》2025-10-09 施行；期货客户交易前向期货公司报告，期货公司核查后向交易所报告并确认。

**推荐**
1. 锁定 CTP = 期货/期货期权；A 股现货走券商 API/QMT/PTrade。
2. `[ctp]` 独立 extra；CTP 网关可跑 Linux，适合股指期货对冲与月差。
3. 期货程序化报备纳入 P-056 验收；CTP 网关必须支持报备字段（交易软件名称/版本/开发主体、执行方式）。
4. 月差/换月模板必须包含：主力合约切换、保证金变化、限仓、交割月规则。

**对总纲影响**: §3 F6 CTP 边界保留并补报备；P-056 前置/验收。

**待确认**: 是否已有期货账户与程序化报备？若无，CTP 线后置。

---

### Q5. 舆情数据合规与成本

**框架现状（E3）**
- `agents/sentiment_framework.py` 只有打分框架；`risk_monitor.SentimentMonitor` 接收外部 `social_sentiment` 参数，无数据接入。
- 无公告/新闻/研报抓取、无 PIT 存储、无模型版本管理。

**外部证据（E1）**
- Tushare：`dividend`（分红送股）需 ≥2000 积分；`trade_cal` 需 2000 积分；`pro_bar` 复权需 2000 积分；新闻资讯为**单独权限约 1000 元/年**（快讯/长篇/新闻联播，400 次/分钟）；套餐 2999 元/年起。
- AKShare：免费开源；`tool_trade_date_hist_sina`（交易日历）、`stock_history_dividend_detail`/`stock_fhps_em`（分红配送）、`stock_notice_report`（沪深 A 股公告大全）；数据来自交易所/新浪/东财等公开源。
- 巨潮资讯（cninfo）提供公告检索页面；交易所官网披露公告原文。

**推荐**
1. **开源优先**: 一期（P-049）以 AKShare/交易所/巨潮公告为主线；Tushare 新闻（约 1000 元/年）为**可选增强**；研报需授权；**不做股吧/雪球爬虫**。
2. AKShare 作为免费兜底（公告/日历/分红），但需接受其源站变更与限频；关键数据仍以 Tushare/交易所为准。
3. PIT 三时间戳：`publish_time`（公告/新闻发布时间）、`fetch_time`（抓取时间）、`effective_time`（可用时点，默认次日开盘）；所有因子按 `effective_time` 对齐。
4. 预算：0–4000 元/年（开源 0；新闻 1000；Tushare 套餐/积分可选）；LLM 推理成本另计，优先词典/FinBERT，LLM 仅对高置信事件抽取。
5. 合规：不转售/不公开原始数据；只存衍生因子；保留数据源条款与授权记录。
6. **粒度**: 先用 synthetic 公告 fixture 跑通「解析→事件→因子→PIT」链路，再接 AKShare；Tushare 后置。

**对总纲影响**: §3 F1 舆情落地、P-049 前置/验收；§7.5 结论。

**待确认**: 是否采购 Tushare 新闻（约 1000 元/年）？不采购则全程开源 + synthetic。

---

### Q6. 数据源统一：data.py / data_v3.py 收敛与 golden

**框架现状（E3）**
- `core/data.py`（pkl 批量、懒加载+缓存）、`core/data_v3.py`（NumPy，供 V3）、`core/data_provider.py`（`DataProvider` Protocol + `PklDataProvider`，P-012 标注「本批不接线」）、`core/universe_data.py`（股票池快照）。
- golden：`tests/golden/` G1-G7 七份 JSON；`-k golden` 收集 13 项；CI 只跑 pytest+mypy+uv lock。

**外部实践**
- 数据层收敛的通行做法是 Strangler/Adapter：先定义端口，再让旧实现适配，逐路径迁移；用数据指纹（矩阵 sha256）+ 契约测试保证语义不变。
- 直接重写两个加载器会同时改变索引/复权/对齐语义，golden 必然漂移，且难以归因。

**推荐**
1. P-042 只做三件事：①`DataProvider` 成为唯一端口；②`data.py`/`data_v3.py` 变成适配器（保持行为）；③新增 `IStreamingFeed` 契约与契约测试。
2. 引入**数据指纹**：open/high/low/close/adj_factor/volume/amount 矩阵 sha256 写入 `manifest.py`；P-042 前后指纹必须一致。
3. golden **默认零重录**；若指纹变化，必须产出 `change_report`（行级差异 + 归因），并由用户显式裁决重录。
4. 不在 P-042 改复权/股票池语义；这些留给后续批次单独立项。
5. **粒度**: 先用本地 CSV/Parquet + synthetic fixture 跑通契约与 golden；本地在建管道（`E:\Macro_Data` / `E:\FinDatasets` / `F:\Open_Data`）仅记录、不写适配器、不读目录。

**对总纲影响**: §5 P-042 内容/验收；§4 manifest 行。

**待确认**: 是否接受「默认零重录 + 指纹门禁」？

---

### Q7. PyPortfolioOpt：引入还是自研？

**框架现状（E3）**
- `core/portfolio.py`：4 优化器（EqualW/MinVar/MVO/RiskPar）+ 3 协方差估计器（sample/ledoit_wolf/ewma）+ `round_lot_optimize`（L394）；cvxpy/scipy/sklearn 已声明。
- 无 BL/HRP/最大夏普；无换手/行业/跟踪误差约束的统一建模。

**外部证据（E1）**
- PyPortfolioOpt：PyPI 最新发布 **2026-02-26**，MIT；支持 BL/HRP/ERC/收缩；文档 1.5.4。
- skfolio：arXiv 2507.04176（2025），sklearn 风格 API，支持 BL/HRP/prior/预选；活跃。
- riskfolio-lib：功能全但依赖重、版本 pin 紧。

**选项**
| 选项 | 优点 | 缺点 |
|------|------|------|
| A. PyPortfolioOpt 进核心 | 成熟、开发快 | 新依赖、约束定制受限、与现有 cvxpy 体系重复 |
| B. 核心自研 + PyPortfolioOpt 仅对拍 | 约束可控、纯函数、可审计、零运行时新依赖 | 开发量较大 |
| C. skfolio 进核心 | sklearn 生态、模型选择方便 | 新依赖、团队需熟悉 |

**推荐**
- **B**：核心用 cvxpy/scipy 自研 BL/HRP/最大夏普/约束；PyPortfolioOpt 放 `[research]` extra，仅用于参考解对拍与 golden。
- 理由：本项目强调「纯函数核 + 可单独验证审计 + 低耦合」；优化器是核心计算，不能把约束能力外包给第三方 API；且 PyPortfolioOpt 的 HRP/BL 可作为对拍基准。
- 若后续需要 skfolio 的模型选择/预选，再评估 `[research]` extra，不进核心。

**对总纲影响**: §3 F2 选型、P-046 前置/验收；§7.7 结论。

**待确认**: 是否接受「核心自研 + PyPortfolioOpt 仅对拍」？

---

### Q8. regime 自适应防过拟合

**框架现状（E3）**
- `walk_forward.py`（Rolling/Expanding + Purge Gap）、`walk_forward_engine.py`、`style_drift_analysis.py`、`adaptive_agent.py`；无 HMM/regime 模块。

**外部实践（E1/E4）**
- 常见错误：全样本 HMM 拟合、使用平滑概率（smoothed）、中心化指标窗口 → 前视。
- 正确做法：扩展/滚动窗口重估、**滤波概率**（filtered）、BIC/AIC 选态、deflated Sharpe/PBO、样本外验证、处理 label switching、集成 HMM 降低单模型不稳定。
- HMM 的已知局限：初值敏感、转移概率平稳假设、易过拟合。

**推荐**
1. P-057 采用：2–4 态 Gaussian HMM；BIC 选态；**滚动重估**（如 5 年窗口、月度重估）；只用滤波概率；样本外 + Purge Gap；报告 PBO/Deflated Sharpe。
2. 按态切换**参数集**而非在线学习；切换需滞回（避免抖动）与最小持有期。
3. 若样本外提升不显著（如 Sharpe 提升 <0.2 或 PBO>0.5），不启用 regime 切换。
4. 策略生命周期（P-051）先于 P-057；regime 是增强，不是前置。

**对总纲影响**: §3 F5 regime 段、P-057 验收；§7.8 结论。

**待确认**: 是否接受「不显著就不启用」的保守门槛？

---

### Q9. 合规定位与报备

**框架现状（E4）**
- `core/` 内 `kill_switch/emergency/circuit_breaker/fat_finger/auth/token/jwt/secret` **0 命中**；无报备台账、无异常交易监控、无鉴权。
- CI 无安全/合规 job。

**外部证据（E1）**
- 证监会〔2024〕8 号：程序化交易前须报告账户基本信息、资金/杠杆、交易策略类型及主要内容、指令执行方式、最高申报速率、单日最高申报笔数、交易软件名称/版本/开发主体等；券商核查后向交易所报告，客户收到确认后方可交易。
- 沪深北实施细则（2025-07-07）：高频 = 单账户每秒申报+撤单 ≥300 笔或全日 ≥20000 笔；高频额外报告服务器所在地、测试报告、应急方案；交易所实时监控异常交易。
- 上交所异常交易实时监控细则：虚假申报、拉抬打压、维持价格/交易量、自买自卖/互为对手方、严重异常波动股票申报速率异常等。
- 期货程序化交易规定（2025-10-09）：期货客户交易前向期货公司报告，期货公司核查后向交易所报告并确认。
- 券商外接新规（2026-08-28）：券商接入业务须向中证协备案；强调验资验券、阈值管理、异常监测、非法接入阻断；私募管理人需登记且首只产品备案满一年等。

**推荐**
1. **定位自用工具**，不对外提供服务；若未来对外，另做持牌/适当性/等保评估（不在本升级范围）。
2. 实盘前完成券商程序化交易报告；报告字段由平台自动导出（账户、策略、软件版本、最高速率、单日笔数）。
3. 设计速率上限：默认 **≤1 笔/秒、≤1000 笔/日**，远低于高频阈值；保留可配置上限与熔断。
4. API/WS 仅绑定 `127.0.0.1`/内网；API Key/JWT + TLS；禁止公网暴露。
5. 审计日志 append-only，建议保留 **≥5 年**（监管/券商要求以实际为准）；记录操作者、时间源、策略版本、订单全链路。
6. 异常交易自检：自成交拦截、撤单率监控、瞬时速率监控、涨跌停价格带校验。

**对总纲影响**: §3.0 S4、F6/F7、P-052/P-053/P-054；§7.9 结论。

**待确认**: 确认自用定位；确认券商报备流程与所需材料；确认是否涉及期货报备。

---

### Q10. parity 阈值

**框架现状（E3）**
- `change_report.py`（六层归因 + residual 双门）、`manifest.py`、`invariants.py`（I1-I7）、golden G1-G7；无回测↔paper↔实盘 parity 阈值。
- `execution.py` 有 VWAP/TWAP/Close 模拟；无实盘成交回填与滑点归因。

**外部实践（E1）**
- 滑点是回测/实盘差异的最大来源；5bps/笔的未建模滑点可吞掉高频策略一半利润；买卖价差常占年 PnL 的 5–15%；实盘低于回测 20–50% 常见。
- 通行做法：分层对账（持仓/现金/权重/成交价/成交率），按流动性分档设阈值，超阈值先归因再停机。

**推荐（写入 P-053 验收）**
| 对比 | 持仓 | 现金 | 权重 L1 | 成交均价 | 成交率 |
|------|------|------|---------|----------|--------|
| 同数据重放（backtest↔backtest） | 精确 | 精确 | ≤1e-9 | 精确 | — |
| 回测↔paper（同日同信号） | 精确 | ≤1 元 | ≤1e-6 | ≤5bps（流动）/≤20bps（小盘） | ≥98% |
| paper↔live | 精确（公司行为除外） | ≤0.01% NAV | ≤1e-4 | ≤10bps（流动）/≤30bps（小盘） | ≥95% |

补充：
- 至少 **20 个交易日 / 100 笔** paper 才允许小资金灰度。
- 每日生成 parity 报告；连续 2 日超阈值 → 自动降级/停机并告警。
- 滑点按「决策价→成交价」归因，区分价差/冲击/延迟；成本漂移纳入策略生命周期。

**对总纲影响**: §4 差分审计行、P-053 验收；§7.10 结论。

**待确认**: 阈值是否按账户规模/标的流动性再校准？

---

### Q11. 多策略共享账户

**框架现状（E3）**
- `agents/strategy_allocator.py` 是 Agent 层权重分配；`agents/multi_strategy_engine.py` 是多策略引擎；`tracker.py` 是单组合账目；`live_bridge.py` 是单账户接口。
- 无虚拟子账户、无资金预留、无跨策略净额、无冲突仲裁。

**外部实践（E1）**
- 多账户管理（MAM/PAMM）与主从账户：按权益/余额/固定手数分配；子账户隔离可防止单策略回撤/强平污染其他策略。
- 多策略组合通常设中央 Portfolio Manager：净额计算、组合级暴露上限、跨策略相关性监控、订单净额规则。

**推荐**
1. 账本维护**每策略虚拟子账户**（虚拟现金、虚拟持仓、P&L、回撤）；主账户为唯一真实资金池。
2. 下单前**资金/持仓预留**；跨策略先**净额**（A 多 1000 股、B 空 800 股 → 净买 200 股）再发单，降低费用与冲击。
3. 冲突仲裁：策略分层（核心/卫星/实验）+ 同层 FIFO；单策略 kill switch 不影响其他策略；每日按虚拟子账户对账。
4. 禁止无政策交叉补贴；若需调剂，走显式资金划拨事件并留痕。

**对总纲影响**: §3 F5 多策略资金分配、F6 账本、P-051/P-053 验收；§7.11 结论。

**待确认**: 是否需要多策略并行？冲突用「分层优先级」还是「纯公平队列」？

---

### Q12. 公司行为/交易日历数据源

**框架现状（E3）**
- 无交易日历模块；日期来自数据文件（`data.py` 对齐、demo 生成周末日历）。
- `data_provider.py` 读取 `adj_factor`；无分红/送转/配股事件表；实盘账本无公司行为事件。
- Tushare/AKShare 均未接入。

**外部证据（E1）**
- Tushare `dividend`（分红送股）需 ≥2000 积分，每日 20–21 点更新；`trade_cal` 需 2000 积分；`pro_bar` 复权需 2000 积分。
- AKShare：`tool_trade_date_hist_sina`（1990 至 2024，需注意更新范围）、`stock_history_dividend_detail`/`stock_fhps_em`、`stock_notice_report`。
- 交易所公告（巨潮/上交所/深交所/北交所）是公司行为与临时休市的权威源。

**推荐**
1. 本地**快照 + 每日增量**：交易日历、公司行为事件表（分红/送转/配股/退市/更名）。
2. 源优先级：**实盘持仓以柜台为准** > Tushare（研究/历史） > AKShare（免费兜底） > 交易所公告（权威校验）。
3. 事件字段：`announce_date`、`record_date`、`ex_date`、`pay_date`、`cash_div`、`stock_div`、`rights_ratio`、`adj_factor`、`source`、`fetch_time`。
4. 对账：持仓数量差异必须先归因公司行为（送转/配股），再判异常；除权日价格/成本同步调整。
5. 日历：包含临时休市、期货夜盘、集合竞价/连续竞价/收盘竞价时段；启动时校验，缺失/冲突告警。
6. 数据源不可用时降级：用本地快照 + 告警，禁止静默使用过期日历。
7. **粒度**: 先用 synthetic 事件表 + AKShare 免费源跑通「日历→公司行为→对账归因」；Tushare 可选；柜台源实盘时再接；本地数据管道不接入。

**对总纲影响**: §3 F6 `session_calendar`/`corporate_actions`、P-053 验收；§7.12 结论。

**待确认**: 是否接受「AKShare/交易所为主、Tushare 可选」？实盘是否以柜台公司行为为准？

---

### Q13. 可观测性栈

**框架现状（E3）**
- `event_log.py`（JSONL + 环形缓冲 + 订阅）、`diagnostics.py`（日级异常四分类）、`manifest.py`；无 metrics/告警/追踪。
- CI 只跑测试/类型/lock。

**外部实践（E1）**
- 交易系统常见栈：Prometheus（指标）+ Grafana（看板）+ Alertmanager（告警）+ Loki（日志）+ Tempo/Jaeger（追踪）。
- 低延迟场景建议：Prometheus 就近采集、Pushgateway 异步、缩短 scrape 间隔但避免压垮系统。
- 最小可行：结构化日志 + Prometheus 指标 + IM/邮件告警即可覆盖「下单延迟/拒单/积压/连接数/对账差异」。

**推荐**
1. **最小栈**：结构化 JSON 日志 + Prometheus 指标 + IM/邮件告警；Grafana 后置，Loki/Tempo 不进 P-054。
2. 指标清单：订单延迟 p50/p95/p99、拒单率、撤单率、成交率、事件积压、WS 连接数、推送延迟分位、数据滞后、对账差异、策略 PnL/回撤。
3. 告警分级：P0（kill switch/柜台断线/对账重大差异）立即 IM+电话；P1（延迟/积压/拒单率）IM；P2 日报。
4. 延迟基准写入 P-054 验收；每月复盘一次。
5. **粒度**: 先交付结构化日志 + 轻量 metrics 接口 + IM 告警；Prometheus/Grafana 可后置，不阻塞 P-054。

**对总纲影响**: §3 F7、P-054 验收；§7.13 结论。

**待确认**: 是否接受最小栈，还是需要 Grafana 全栈？

---

### Q14. QMT Python 版本与 extra 隔离

**框架现状（E3）**
- `pyproject.toml` `requires-python = ">=3.10"`；CI 3.10/3.11/3.12；black target py310-312。
- 无 `[qmt]`/`[ctp]`/`[services]` extra；无 xtquant/vnpy_ctp 声明。

**外部证据（E1）**
- xtquant PyPI：Windows x64，Python **3.6–3.13**，最新 250807.1.2（2026-07-21）。
- QMT 标准版内置 Python **3.6.x**（官方快速开始写 3.6，API 文档 3.6.8）；券商库白名单；2026 起关闭文件读写/外网。
- miniQMT 新申请已停、存量清退（华鑫 2026-10-30 关闭）。
- PTrade：券商云端容器、单文件、库裁剪、无外网。
- QMT 交易连接：同一 `session_id` 两次进程 connect 需 >3 秒；重连需更换 `session_id`。

**推荐**
1. **不假设 3.12**：`[qmt]` extra 独立 venv，Python 版本按可用通道 pin（xtquant 支持 3.6–3.13；建议 3.11 兼顾生态与稳定）。
2. Windows 网关与主包隔离：主包 Linux CI 不安装 xtquant；`pip install -e ".[qmt]"` 仅在 Windows 网关机执行。
3. 若只能使用 QMT 标准版：策略必须 Python 3.6 兼容、单文件/自包含、仅白名单库、无文件/网络；与主代码（3.10+ 语法、pandas/cvxpy 等）不兼容 → 需要**独立移植层**（只保留信号计算的最小副本），或放弃自动集成，改半自动。
4. 若使用 PTrade：同样单文件/无外网，平台只做研究/监控/订单建议。
5. 若使用券商机构 API：可保持主包 3.11/3.12，网关只做协议适配。
6. CTP：`[ctp]` extra，openctp-ctp 支持 3.7–3.13、Linux；可与主包同 Python。

**对总纲影响**: §3 F6 依赖与部署、§6 门禁落地、P-053 前置；§7.14 结论。

**待确认**: 你的可用通道与 Python 版本？是否接受「QMT 标准版仅半自动」？

---

## 4. 对总纲的修订建议（按优先级）

| 优先级 | 修订点 | 现状 | 建议 |
|--------|--------|------|------|
| P0 | P-053 定义 | 「QMT 网关」 | 改为「交易通道网关」，首交付**通道可行性门**；QMT/PTrade 仅半自动适配 |
| P0 | P-050 定义 | 「做空账目（股票负持仓）」 | 改为「空头与期货账目」，**期货保证金优先**；股票负持仓降为研究 |
| P0 | F6 部署假设 | Windows xtquant 常驻 | 改为「通道决定宿主」；机构 API/CTP 可 Linux；QMT/PTrade 封闭沙箱 |
| P0 | §3.0 S4 | 合规报告泛化 | 补报告字段、速率上限、异常交易自检、审计留存 |
| P1 | F5 截面多空模板 | 股票融券 | 默认股指期货对冲；股票融券仅研究开关 |
| P1 | F2 选型 | PyPortfolioOpt 进核心 | 核心自研 + PyPortfolioOpt `[research]` 对拍 |
| P1 | P-042 验收 | golden 零重录 | 加数据指纹门禁；重录须 change_report + 显式裁决 |
| P1 | P-049 数据 | 公告/新闻 | 明确**开源优先** + Tushare 可选 + 无社交爬虫 |
| P1 | P-053 验收 | 幂等/对账 | 加 parity 分层阈值、公司行为归因、20 日/100 笔 paper |
| P2 | P-057 验收 | 样本外验证 | 加滚动重估/滤波概率/BIC/PBO |
| P2 | P-054 验收 | 延迟基准 | 四级 SLA（源/总线/WS/下单确认） |
| P2 | P-055 观测 | 未定义 | 最小栈：结构化日志 + Prometheus + IM 告警 |

---

## 5. 裁决记录与剩余待确认

### 5.1 已裁决（2026-11-17）

| ID | 事项 | 裁决 |
|----|------|------|
| **D1** | 交易通道 | **多通道预留**：机构 API / QMT / PTrade / CTP / 半自动均保留适配器 |
| **D2** | 合规定位 | **自用工具 + 完成程序化报备** |
| **D3** | 做空路线 | **期货账目优先，股票融券仅研究** |
| **D4** | QMT 隔离 | **独立 Windows venv + 可能的 3.6 移植层** |
| **D5** | 数据策略 | **宜粗不宜细**；开源（AKShare/交易所/巨潮）> synthetic fixture > 付费（Tushare 可选）> 本地在建管道（仅分析、暂不接入） |

> D1-D5 已回写总纲 §7.1/§7.2、§5 路线图与 §9；P-053 不再被「通道未定」阻断。

### 5.2 剩余待确认（不阻断 P-042 与 P-053 骨架）

1. **数据预算**: 是否采购 Tushare 新闻（约 1000 元/年）与积分套餐？不采购时全程走开源 + synthetic。
2. **舆情范围**: 只做公告/新闻、社交后置，是否接受？
3. **parity 阈值**: §Q10 分层阈值与「paper 20 日/100 笔」是否接受（可用 synthetic paper 预演）？
4. **多策略**: 是否需要虚拟子账户/净额/分层优先级？
5. **公司行为/日历**: 实盘以柜台为准、研究以开源（AKShare）为主 + Tushare 可选，是否接受？
6. **观测栈**: 先最小栈（结构化日志 + 轻量 metrics + IM 告警），Grafana 后置，是否接受？
7. **regime**: 不显著不启用，是否接受？
8. **PyPortfolioOpt**: 仅 `[research]` 对拍，是否接受？

---

## 6. 风险与未决

| 风险 | 影响 | 缓解 |
|------|------|------|
| miniQMT 全面关停 | 原 QMT 网关方案失效 | 通道可行性门；机构 API/CTP/半自动三选一 |
| QMT 标准版 3.6 + 无文件/网络 | 无法集成主平台 | 独立移植层或半自动；不要把主代码塞进沙箱 |
| 程序化交易报备未完成 | 实盘违规/被限制 | 实盘前完成报备；速率限额；审计留痕 |
| 转融券暂停/券源不足 | 股票多空/中性无法实盘 | 股指期货对冲；股票空头仅研究 |
| 数据源变更/限频 | 舆情/日历/分红缺失 | 多源兜底 + 本地快照 + 告警 |
| parity 阈值过严/过松 | 误停机或漏检 | 按流动性分档；先 paper 校准 |
| HMM 过拟合 | regime 切换失效 | 滚动重估/滤波概率/BIC/PBO/样本外 |
| 新依赖引入 | lock/CI 失败 | 全部走 extra + `uv lock` + lock-check |

**未决（需外部确认）**
- 用户券商的 QMT/PTrade/机构 API 实际权限与费率；
- 券商程序化交易报备所需材料与审批时长；
- 期货账户与 CTP 程序化报备状态；
- 数据供应商最终报价与授权范围（Tushare 价格会调整）；
- 券商 QMT 文件/网络限制的正式通知原文（当前为社区/券商转述）。

---

## 7. 来源（访问日期 2026-11-17）

### 监管与交易所
- [证监会〔2024〕8 号《证券市场程序化交易管理规定（试行）》](https://www.gov.cn/gongbao/2024/issue_11426/202406/content_6959680.html)
- [上交所《程序化交易管理实施细则》答记者问（高频 300 笔/秒、20000 笔/日）](https://www.sse.com.cn/aboutus/mediacenter//hotandd/c/c_20250403_10776805.shtml)
- [上交所《程序化交易管理实施细则》全文](http://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml)
- [人民网：沪深北实施细则 2025-07-07 施行](https://finance.people.com.cn/n1/2025/0707/c1004-40516156.html)
- [上交所主板股票异常交易实时监控细则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20250519_10779397.shtml)
- [证监会〔2025〕12 号《期货市场程序化交易管理规定（试行）》](https://www.gov.cn/gongbao/2025/issue_12226/202508/content_7036966.html)
- [中证协/中基协《证券公司交易信息系统接入管理规范（试行）》报道](https://www.cs.com.cn/tj/01/2026/08/31/tjdetail_2026083110035747.html)
- [AMAC《证券公司交易信息系统接入管理规范（试行）》PDF](https://www.amac.org.cn/xwfb/tzgg/202608/P020260902356065183745.pdf)
- [证监会：暂停转融券业务（2024-07-11）](https://www.csrc.gov.cn/csrc/c100028/c7493852/content.shtml)
- [中金所风险控制管理办法](http://www.cffex.com.cn/cn/ssxz/20230414/43079.html)
- [中金所上证50股指期货合约（最低保证金 8%）](http://www.cffex.com.cn/cn/sz50gzqh.html)

### 行情与通道
- [上交所历史数据接口：Level-1 快照 3s/5s](https://www.sseinfo.com/services/assortment/document/interface/c/10747485/files/d054de0ac2094787959b1b32b65ec24a.pdf)
- [上交所 Level-2 产品说明书](https://www.sseinfo.com/services/assortment/market/hqywwd/wdcpsms/c/10782128/files/d5275420908745f0ae72a1b1d3e40903.pdf)
- [xtquant PyPI（Windows x64，Python 3.6–3.13，250807.1.2）](https://pypi.org/project/xtquant/)
- [迅投 FAQ：xtquant 支持的 Python 版本（3.6–3.11，旧版口径）](https://dict.thinktrader.net/nativeApi/question_function.html)
- [迅投 FAQ：get_full_tick 盘中 50ms 更新](https://dict.thinktrader.net/innerApi/question_answer.html)
- [迅投快速开始：QMT 内置 Python 3.6](https://dict.thinktrader.net/innerApi/start_now.html)
- [华鑫证券：2026-10-30 收盘后关闭 miniQMT](https://www.cfsc.com.cn/www/html/132/2026-10-21/5E517A3E129F23CAE06329F7BC0AA46A.html)
- [miniQMT.com：2026-07-06 起全面停止申请](https://miniqmt.com/index.html)
- [迅投社区：MiniQMT 停用与 HTTP 桥接](https://www.xuntou.net/forum.php?mod=viewthread&tid=6801)
- [叩富：QMT 2026 新规与 miniQMT 关停解读](https://licai.cofool.com/ask/qa_7707969.html)
- [WTSolutions：QMT 关闭内置策略文件读写与网络连接](https://invest.wtsolutions.cn/posts/qmt-file-network-restriction/)
- [东方财富财富号：部分券商 QMT 限制文件单与外部通信](https://caifuhao.eastmoney.com/news/20260915102315258429090)
- [PTrade API 文档（业务类型/回测限制）](http://ptradeapi.com/index.html)
- [恒生 PTrade 专业交易系统（品种）](https://www.hs.net/openplat-front/service/serviceDetail/307)
- [宽睿 Quant360-OES（类 CTP 接口，C/Java/Python）](http://www.quant360.com/oes)
- [宽睿量化产品方案](http://www.quant360.com/quantization_scheme)
- [东方财富证券量化服务条件（300 万资产示例）](https://emt.eastmoneysec.com/article/article-info/123025580)
- [QMT 开通门槛（10 万/50 万）](https://licai.cofool.com/ask/qa_3102192_2_1.html)
- [openctp-ctp PyPI（Python ≥3.7、Linux、BSD-3）](https://pypi.org/project/openctp-ctp/)
- [ctp-python PyPI（Python 3.7–3.13）](https://pypi.org/project/ctp-python/6.7.7.post1/)

### 组合优化与 regime
- [PyPortfolioOpt PyPI（2026-02-26 发布）](https://pypi.org/project/pyportfolioopt/)
- [PyPortfolioOpt HRP 文档](https://pyportfolioopt.readthedocs.io/en/latest/OtherOptimizers.html)
- [skfolio 论文 arXiv 2507.04176](https://arxiv.org/html/2507.04176v1)
- [skfolio 官网](https://skfolio.org/)
- [Market Regime Detection Handbook（滚动/滤波/BIC/PBO）](https://www.reignedge.com/library/regime-detection-handbook)
- [Rolling HMM 论文（electronics-15-01334）](http://www.ifc.inaf.it/wp-content/uploads/2026/03/electronics-15-01334.pdf)

### parity / 多策略 / 观测
- [Backtest-live parity（价差贡献 5–15% 年 PnL）](https://marketmaker.cc/en/blog/post/backtest-live-parity/)
- [Quantzee：回测与实盘不匹配](https://quantzee.com/backtest-vs-live-trading-mismatch/)
- [Sub-account 定义（策略隔离）](https://www.forexbite.com/dictionary/sub-account/)
- [FastAPI WebSocket 官方文档（多进程需 Redis/broadcaster）](https://fastapi.tiangolo.com/zh/advanced/websockets/)
- [WebSocket.org：FastAPI 多 worker 与 Redis pub/sub](https://websocket.org/guides/frameworks/fastapi/)
- [Prometheus 交易平台低延迟监控设计](https://devopsrockstar.com/article/designing-prometheus-monitoring-for-financial-trading-platforms-with-low-latency-requirements/)

### 数据
- [Tushare 交易日历（2000 积分）](https://tushare.pro/document/2?doc_id=26)
- [Tushare 分红送股（2000 积分）](https://tushare.pro/document/2?doc_id=103)
- [Tushare 权限与价格（新闻 1000 元/年、套餐 2999 元/年起）](https://tushare.pro/document/1?doc_id=290)
- [Tushare 新闻快讯接口](https://tushare.pro/wctapi/documents/143.md)
- [AKShare 交易日历](https://akshare.akfamily.xyz/data/tool/tool.html)
- [AKShare 教程（分红/公告接口）](https://akshare-hh.readthedocs.io/en/latest/tutorial.html)
- [AKShare 特别说明（数据来源与致谢）](https://akshare.akfamily.xyz/special.html)

### 市场中性/融券
- [新华网：融券余额 137 亿元、较峰值降逾九成](https://www.news.cn/finance/20240821/7824ea96e83e464e91d7549daa873c4e/c.html)
- [中证网：量化多空与市场中性策略迭代（股指期货对冲）](https://www.cs.com.cn/tzjj/smjj/202408/t20240815_6431779.html)
- [上海证券报：市场中性策略只能用 IF/IC/IM 对冲](https://paper.cnstock.com/html/2025-11/25/content_2149956.htm)
- [新浪财经：IF/IC/IM 对冲与保证金](https://finance.sina.com.cn/roll/2026-10-21/doc-inivyxhi6112101.shtml.md)

---

## 8. 自检（RULE-1/2/4/5）

| 项 | 结果 |
|----|------|
| 覆盖度 | §7 的 14 项全部覆盖，0 遗漏 |
| 代码锚点 | `portfolio.py` / `interfaces.py` / `live_bridge.py` / `data_provider.py` / `target_positions.py` / `pyproject.toml` / `tests/golden/` 均已核验 |
| 外部来源 | 官方监管/交易所/厂商文档优先；社区口径标注「社区/待确认」 |
| 推测 | E5 未入结论；未对监管阈值/xtquant 版本作无源断言 |
| 基座披露 | 本文由 DeepSeek-V4.1-Flash 生成；总纲初稿 Qwen4-Max → RULE-5 异构成立于复审环节；本文为 RESEARCH 产物，不替代终审 |
| 待确认 | P0 四项已于 2026-11-17 裁决（D1-D4）；数据策略 D5 已定；剩余 P1/P2 项见 §5.2，不阻断 P-042/P-053 骨架 |
| 裁决回写 | 总纲 §7.1（D1-D4）、§7.2（粒度/数据策略）、§5 路线图、§9 已同步 |
