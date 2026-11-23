# RESEARCH：P-055 关键决策外部锚点与多维评估（U-P055-1/2/4/6）

> **批次**: P-055 · **Step 1 补充调研** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **主文档**: [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G16 / 方案 A / 验收读数）
> **目的**: 为上一轮 4 个高影响决策提供**外部案例 / 社区实践 / 官方文档**锚点，按「兼容性 / 维护 / 短期落地 / 长期演进 / 升级潜力」多维评分，给出可解释的决策建议，避免拍脑袋。
> **方法**: 官方文档（T1）+ 学术论文（T1）+ 工程博客/行业报道（T2）+ 社区案例（T3）+ 仓内代码事实（E3）；评分 1-5；每条结论标来源与置信度。
> **零代码变更**：本文件只做调研与建议；Step 9 才落码；未提交。

---

## 0. 决策建议速览

| ID | 问题 | 推荐 | 置信度 | 一句话理由 | 关键锚点 |
|----|------|------|--------|------------|----------|
| **U-P055-1** | 部署形态 | **A 双模式**（Mode S 全容器 + Mode R Windows 原生应用 + 仅 Redis 容器） | **高** | QMT 是 GUI 桌面程序，Windows 容器不支持 GUI；WSL bind mount 性能/锁风险高；社区已有「Windows 中转 + 局域网 API」先例 | S9/S10/S11/S12/S13/S14 |
| **U-P055-2** | 策略/风控是否拆进程 | **A 不拆**（保持库内调用，文档化拆分触发条件） | **高** | Segment 140+ 服务回归单体、Prime Video 成本 -90%、Shopify 模块化单体、arXiv 综述列出回退五因；本仓单团队/同机 SQLite/同步事前风控 | S3/S5/S6/S7/S8/S16/S17 |
| **U-P055-6** | SQLite 卷策略 | **A named volume / 原生本地盘**（reader 同目录 rw + 应用层只读） | **高** | SQLite WAL 要求同机本地文件系统；Docker 官方建议避免 `/mnt/c`；Windows volume 有 locked 案例；Linux 命名卷实践可用 | S12/S13/S14/S20/S22 |
| **U-P055-4** | 延迟基准门禁 | **A 报告制**（本地/按需跑，CI 不设阈值；可选 nightly 非阻塞） | **中高** | 共享 CI runner 抖动可达 30%+；当前 CI 无 redis service；脚本可随时升级为 SLO | S18/S19 |

> 推荐组合：**A / A / A / A**。若您选择其他组合，§7 给出对应的 DESIGN 影响与代价。

---

## 1. 评分口径与证据分层

### 1.1 维度定义

| 维度 | 含义 | 5 分（优） | 1 分（不可接受） |
|------|------|------------|------------------|
| **兼容性** | 与现有代码、QMT/xtquant、SQLite WAL、Windows/CI 的兼容程度 | 无需特殊适配 | 与硬约束直接冲突 |
| **维护成本** | 日常部署、排障、升级、文档的负担（分数越高越省） | 单一路径、自动恢复 | 多路径漂移、手工操作多 |
| **短期落地** | P-055 批次内可完成度与风险（分数越高越快越稳） | 改动小、可增量 | 需大重构/不可控 |
| **长期演进** | 1-3 年内在规模、团队、功能上的扩展空间 | 可持续演进 | 很快撞墙 |
| **升级潜力** | 未来引入新服务/跨机/新技术的空间 | 接口清晰、可替换 | 锁定死路 |

### 1.2 证据分层

| Layer | 定义 | 本文件示例 |
|-------|------|------------|
| **T1** | 官方文档/标准/学术论文/仓内源码 | Microsoft Windows containers、Docker 官方、SQLite 官方、arXiv、仓内代码 |
| **T2** | 厂商工程博客/行业媒体/包官方元数据 | AWS/InfoQ、Twilio Segment、Shopify Engineering、PyPI |
| **T3** | 社区论坛/个人博客/二手总结 | Docker 论坛、miniQMT QA、pytest-benchmark 指南、华为云博客 |

> 评分是**本项目特定**的（自用、单机/内网、3s/笔行情、单写者 SQLite、Windows QMT），不是通用架构排名。

---

## 2. U-P055-1 部署形态

### 2.1 选项

| 选项 | 做法 |
|------|------|
| **A 双模式** | Mode S（synthetic/开发/CI）：全容器 redis+trading+api+market，SQLite 用 named volume；Mode R（真实 QMT/CTP）：应用全部 Windows 原生，仅 Redis 走 Docker Desktop/WSL2 |
| B 全容器 | 所有环境统一 compose；QMT/CTP 联调时再例外 |
| C 全原生 | 不用 compose，进程脚本 + runbook；Redis 也原生/手工 |

### 2.2 外部案例与事实

| # | 事实 | 来源 | 对本决策的含义 |
|---|------|------|----------------|
| 1 | **miniQMT/xtquant 只能在 Windows 运行，且必须依赖 QMT 客户端保持登录**；社区方案 QMT Bridge 在 Windows 机器上跑 QMT 客户端 + FastAPI，通过局域网 HTTP/WS 给 Mac/Linux 使用 | S11（qmt-bridge PyPI 2.0.0） | 真实交易链路必须 Windows 原生；「Windows 中转 + 其他进程远程」是成熟社区模式（双模式的先例） |
| 2 | QMT 可在云服务器部署（部分券商），最低 2C4G、建议 4C8G；需注意防火墙 | S10（miniQMT QA，2026-04） | Mode R 不一定是本机，也可以是 Windows 云主机；仍属「Windows 原生」 |
| 3 | **Windows 容器不支持 GUI/交互桌面；需要桌面的应用不能容器化** | S9（Microsoft Learn） | QMT 客户端是 GUI 桌面程序 → 不能走 Windows 容器；全容器方案在真实模式下不成立 |
| 4 | Docker Desktop WSL2：**避免 `/mnt/c` 等 Windows 文件系统 bind mount**；从 Linux 文件系统挂载性能高得多 | S12（Docker 官方 WSL2 best practices） | Mode S 的 SQLite 不应放 Windows 目录 bind mount；用 named volume（WSL2 VM 内 ext4） |
| 5 | Docker Compose 可用于单服务器生产；用 `restart` 策略、多 compose 文件覆盖 | S15（Docker 官方 production） | Mode S 用 compose 是官方支持的合理路径 |
| 6 | SQLite 论坛：Linux 容器不像网络文件系统那样必然破坏锁（系统调用直达宿主内核）；但 **网络/代理文件系统**可能锁不可靠；Windows volume 有 `database is locked` 案例 | S13/S14 | 不能一刀切说「Docker 不能跑 SQLite」；要区分 Linux 本地卷 vs Windows/网络挂载 |
| 7 | QMT 客户端安装/权限细节（C 盘安装常需管理员权限） | S21（迅投知识库） | Mode R 的部署 runbook 需写清权限/安装路径 |

> **适用性边界**：QMT Bridge 是「Windows 中转 + 跨机 HTTP/WS」方案，本仓 Mode R 是「同机 Windows 原生」；引用它只证明「Windows 原生约束成立、中转模式可行」，不代表本仓要跨机。QMT 云服务器同理：证明 Windows 原生可部署，不改变 Q19 同机 SQLite 约束。

### 2.3 多维评分

| 选项 | 兼容性 | 维护 | 短期 | 长期 | 升级潜力 | 总分 | 关键依据/风险 |
|------|--------|------|------|------|----------|------|----------------|
| **A 双模式** | **5** | 3 | 4 | **5** | **5** | **22** | 兼容 QMT/SQLite/CI；代价是两套模式文档需防漂移 |
| B 全容器 | 2 | **4** | 3 | 3 | 3 | 15 | QMT GUI 不能容器化；SQLite 跨 WSL 挂载风险；真实模式必然破例 |
| C 全原生 | **5** | 2 | **5** | 2 | 2 | 16 | 兼容性最好、最快；但无 compose/健康检查/可复现 CI，长期运维负担大 |

**评分说明**：A 的兼容性 5 来自「QMT 原生 + Linux 容器」双路径都能落地；维护 3 是因为两套模式需要同一 env/runbook 防漂移；短期 4 是因为 Mode S 可增量交付 compose、Mode R 只需 runbook；长期/升级 5 是因为两条路径可独立演进。B 的兼容性 2 是硬伤（QMT GUI 不能容器化，S9）；C 的维护 2 是手工进程管理、无自动恢复。

### 2.4 建议与条件

**推荐 A（置信度高）**：

- **Mode S** 用 compose 交付可复现的开发/CI 拓扑；SQLite 用 **named volume**（WSL2 VM 内 ext4），不用 `/mnt/c` bind mount（S12）。
- **Mode R** 应用三进程全部 Windows 原生；Redis 走 Docker Desktop/WSL2 的 `127.0.0.1:6379`；SQLite 留 NTFS 本地盘。QMT 客户端保持登录（S11）。
- 两模式共享同一套 `P054_*` env 契约与同一镜像（Mode R 也可直接用 venv 跑同一代码），差异只在「进程管理 + SQLite 位置 + Redis 位置」，用 runbook 固化。
- **如果选 B**：真实模式仍必须把 trading 拉回 Windows 原生，B 最终退化为 A，且多一次返工；不建议。
- **如果选 C**：放弃 compose 的可复现性/健康检查/重启策略，「部署」验收弱化；只能在 Mode R 作为补充，不能作为主方案。

**残余风险**：双模式文档漂移；用同一 compose 文件 + 同一 env 样例 + runbook 的「差异表」控制。

---

## 3. U-P055-2 策略/风控是否拆进程

### 3.1 选项

| 选项 | 做法 |
|------|------|
| **A 不拆** | 策略引擎/风控保持库内调用；进程边界只保留 trading/api/market/redis |
| B 拆策略+风控 | 按总纲六服务全拆；策略产信号经 Streams，风控走 gRPC/HTTP 同步 |
| C 只拆风控 | 事前同步风控独立进程；策略仍库内 |

### 3.2 外部案例与事实

| # | 事实 | 来源 | 对本决策的含义 |
|---|------|------|----------------|
| 1 | **Segment 从 100+ 微服务回到单体**：每个目的地一个服务，重复代码/N× 相同 bug/运维噩梦；迁移后可靠性与开发速度提升 | S3（Twilio Segment，2018-07-10）；S4（二手总结：140+ 服务、3 名全职运维、共享库需部署 140+ 服务、测试 1 小时） | 「按集成/功能拆细」会制造大量同构服务与运维负担；本仓策略/风控数量有限，拆细收益低 |
| 2 | **Prime Video VQA 从 serverless/微服务迁到单体，基础设施成本降 90%+**；原文强调「微服务/serverless 是工具，是否优于单体要 case-by-case」 | S1（InfoQ 2023-05）；S2（Docker 博客转述）；原始 AWS 博客抓取失败（见 §9） | 单体不是倒退；在负载形态适合时，单进程/少进程更省成本 |
| 3 | **Shopify 选择模块化单体**：保留一个代码库，但强制组件边界与公开 API；可支撑千人级开发 | S5（Shopify Engineering） | 「模块化 + 强制边界」能获得接近微服务的边界收益，而不付分布式成本；本仓用 import-linter 正是这个方向 |
| 4 | 学术综述《Back to the Future: From Microservice to Monolith》总结回退五因：**成本、复杂度、可扩展性、性能、组织**；并给出六项注意（停止新增服务、合并测试路径、统一存储、消息总线原则、放弃多技术栈、模块化设计） | S6（arXiv:2308.15281，2023-08-29） | 五因中本仓至少命中「复杂度/性能/组织」三项；六项注意中「统一存储/消息总线/模块化」正好对应本批设计 |
| 5 | **MonolithFirst**：成功微服务多始于「过大后拆分」的单体；从零微服务多陷麻烦；先粗粒度服务、边界稳定后再拆 | S16（Fowler，2015-06-03） | 本仓尚未经历真实负载检验，边界未稳定；先模块化单体更稳 |
| 6 | **MicroservicePremium**：微服务自带自动部署/监控/故障处理/最终一致性成本；无复杂度驱动不要上 | S17（Fowler，2015-05-13） | 单团队/自用/单机，无团队规模与独立伸缩驱动 |
| 7 | 风控是**事前同步闸门**，下单路径要求尽量短 | 仓内总纲 F6 L217；P-052 `pre_trade_check` 纯内存 | 拆网络进程会增加一次 RPC + 超时/重试/降级，直接损害 submit 延迟与确定性 |

> **适用性边界**：Segment/Prime Video/Shopify 的团队规模与业务领域与本仓不同；可迁移的是**决策原则**（成本/复杂度/边界稳定性/模块化），不是服务数量或组织形态。本仓的直接约束仍是：单团队、自用/内网、3s/笔行情、SQLite 同机单写者、事前同步风控。

### 3.3 多维评分

| 选项 | 兼容性 | 维护 | 短期 | 长期 | 升级潜力 | 总分 | 关键依据/风险 |
|------|--------|------|------|------|----------|------|----------------|
| **A 不拆** | **5** | **5** | **5** | 3 | 4 | **22** | 与现有库/同步风控/SQLite 完全兼容；长期靠模块化边界与拆分触发条件补足 |
| B 拆策略+风控 | 2 | 2 | 2 | **5** | **5** | 16 | 分布式事务/超时/重试/观测/契约测试成本；SQLite 仍单机；submit 路径变长 |
| C 只拆风控 | 3 | 3 | 3 | 4 | 4 | 17 | 风控 RPC 进入下单关键路径；需要熔断/降级/超时语义；收益不明确 |

**评分说明**：A 的长期 3 不是否定，而是承认「未来规模/团队变化可能需要拆分」；升级 4 是因为 `Strategy` Protocol、`pre_trade_check` 方法、6 类事件契约已留缝。B/C 的长期 5 只在「真的需要独立伸缩/合规边界」时成立；当前没有该驱动，反而立即增加延迟与失败模式。

### 3.4 建议与条件

**推荐 A（置信度高）**：

- 保持 `strategies/` 与 `core/guard_pipeline.py`/`live/safety_gate.py` 库内调用；P-055 只做部署与边界门禁。
- **为未来拆分留缝**（不实现）：
  - `Strategy.generate_signals` 已是 Protocol（P-044），未来可包成独立进程；
  - `SafetyGate.pre_trade_check` 是显式方法，未来可替换为 gRPC 客户端（但要先定义超时/失败关闭语义）；
  - 事件契约（`live/events.py` 6 类）与 Stream 键已稳定，未来可承载「信号事件」。
- **拆分触发条件**（写入 DESIGN §未来演进）：
  1. 策略回测/实盘吞吐导致交易进程 CPU 持续饱和，且策略可独立伸缩；
  2. 风控需要独立合规审计边界或多账户共享；
  3. 需要跨机部署（账本仍留单机，API 走内部 API）；
  4. 团队规模导致独立发布节奏。
- **如果选 B/C**：需新增 gRPC/HTTP 契约、超时/重试/熔断、分布式追踪、契约测试、独立部署单元；P-055 工期与风险显著上升，且不解决 SQLite 同机约束。

---

## 4. U-P055-6 SQLite 卷策略

### 4.1 选项

| 选项 | 做法 |
|------|------|
| **A named volume / 原生盘** | Mode S：Docker named volume（WSL2 VM 内 ext4）；Mode R：Windows NTFS 本地目录；reader 同目录 rw + 应用层 `mode=ro`/`query_only` |
| B reader 只读挂载 | API 容器 ro 挂载数据库目录；应用层只读 |
| C 共享 Windows 目录 | Windows 目录 bind mount 进 WSL 容器，trading/api 共享 |

### 4.2 外部案例与事实

| # | 事实 | 来源 | 对本决策的含义 |
|---|------|------|----------------|
| 1 | WAL 下 readers 不阻塞 writer、writer 不阻塞 readers；但**同一时刻只有一个 writer** | S20（SQLite WAL 官方） | reader 可并发；writer 必须单实例 |
| 2 | **所有使用同一数据库的进程必须在同一台主机；WAL 不能工作在网络文件系统上** | S20 | 跨机/网络共享直接排除 |
| 3 | 只读 WAL 数据库可打开的条件：`-shm`/`-wal` 已存在或可创建（或 immutable） | S20 | ro 挂载不是天然可用；需实测/预创建 |
| 4 | 长读事务会阻止 checkpoint 推进 | S20 | API 查询要短事务；避免长游标 |
| 5 | SQLite 论坛：**Linux 容器不是天然代理**（系统调用直达宿主内核，默认 seccomp 允许 `flock`/`fcntl`）；但**网络/代理文件系统**（SMB/CIFS、部分 Docker 设置）可能锁不可靠；有论坛用户对 Docker 做过大量损坏测试未复现损坏 | S13（SQLite 官方论坛，2023-03） | 不能一刀切；Linux 本地卷可用，Windows/网络挂载要谨慎 |
| 6 | Docker 社区案例：SQLite 数据库放在 **Windows shared volume** 上出现 `database is locked` | S14（Docker 论坛，2016-05-27） | 直接支持「不要共享 Windows 目录」 |
| 7 | Docker 官方 WSL2 最佳实践：**避免 `/mnt/c` bind mount**；Linux 文件系统性能高得多；Linux 容器只有在 Linux 文件系统上才收到 inotify 事件 | S12 | Mode S 用 named volume / WSL2 内目录，不用 `/mnt/c` |
| 8 | Mac/Windows(WSL2) 的 bind mount 性能明显低于 named volume（社区测试约 3.5×） | S22（T3 社区对比） | 即使锁没问题，性能也不建议 Windows bind mount |

### 4.3 多维评分

| 选项 | 兼容性 | 维护 | 短期 | 长期 | 升级潜力 | 总分 | 关键依据/风险 |
|------|--------|------|------|------|----------|------|----------------|
| **A volume/原生盘** | **5** | **5** | **5** | **5** | 4 | **24** | 与 WAL 同机约束一致；Linux 卷/Docker 官方推荐；风险最低 |
| B reader ro 挂载 | 3 | 4 | 3 | 4 | 3 | 17 | 需实测 `-shm/-wal` 可访问；权限/升级容易踩坑 |
| C 共享 Windows 目录 | 1 | 2 | 4 | 1 | 1 | 9 | 官方 WAL 网络文件系统警告 + Docker 论坛 locked 案例；损坏/锁风险最高 |

**评分说明**：A 的升级潜力 4（不是 5）是因为未来若跨机仍需内部 API/迁移；B 的兼容性 3 是因为 ro 挂载必须满足 `-shm/-wal` 存在或可创建；C 的短期 4 是「直接用 Windows 目录」最省事，但长期/升级 1 是锁失败与损坏风险，不能以短期便利换数据安全。

### 4.4 建议与条件

**推荐 A（置信度高）**：

- Mode S：`p055-data` **named volume**；trading/api 都挂同一卷；API 以 rw 挂载 + 应用层 `mode=ro`/`query_only`（P-054 已有只读 preflight）。
- Mode R：SQLite 在 Windows 本地 NTFS 目录；**禁止**把该目录 bind mount 给 WSL 容器；API 也在 Windows 原生。
- **Step 9 必做探针**（证明不是纸面结论）：
  1. `PRAGMA journal_mode` 返回 `wal`；
  2. `-wal`/`-shm` 文件存在且 reader 可打开；
  3. writer 连续写 1000 条 + reader 并发读 1000 次，0 `SQLITE_BUSY`（或记录重试次数）；
  4. `PRAGMA wal_checkpoint(PASSIVE)` 成功；
  5. 容器重启后 reader 仍可打开（卷持久化）。
- **如果选 B**：先做上述探针；若 ro 挂载下 `-shm` 不可写/不可 mmap，则回退 A。
- **如果选 C**：不建议；若坚持，需接受锁失败/损坏风险，并把 SQLite 换成 client/server 数据库（超出本批）。

---

## 5. U-P055-4 跨进程延迟基准门禁

### 5.1 选项

| 选项 | 做法 |
|------|------|
| **A 报告制** | 本地/按需跑 `scripts/p055_bench_e2e.py`，输出 p50/p95/p99 报告；CI 不设阈值；可选 nightly 非阻塞 |
| B CI SLO | CI 启 redis service，跑跨进程基准，超阈值失败 |
| C 仅进程内 | 沿用 P-054 进程内基线，不做跨进程 |

### 5.2 外部案例与事实

| # | 事实 | 来源 | 对本决策的含义 |
|---|------|------|----------------|
| 1 | 共享 CI runner 是多租户，CPU/缓存/内存带宽竞争会导致 **30%+ 波动**，无代码变化也会漂移；建议用同 runner 基线 + 宽松阈值（如 min 15%） | S18（pytest-benchmark 指南，2026） | CI 设严格 SLO 易误红；本仓 CI 还是 GitHub 共享 runner |
| 2 | 降低基准方差需要 **固定 CPU 频率、稳定系统负载、专用机器**；官方明确「具体做法因发行版/桌面环境而异」 | S19（Google Benchmark: Reducing Variance） | 本仓 CI 无法保证；报告制更现实 |
| 3 | 跨进程基准还要叠加容器调度、Redis 网络栈、uvicorn worker 启动抖动 | 本仓事实 + S15 | 阈值门禁的噪声源更多 |
| 4 | 当前 CI 只有 `test`（3.11/3.12）+ `lock-check`，**无 redis service**；单测走 FakeBus | 仓内 [tests.yml](../.github/workflows/tests.yml) | 加 CI SLO 需新增 redis service + 基准 job，工期/稳定性成本上升 |
| 5 | P-054 已有进程内三段基准（亚毫秒），可作为「代码回归」的稳定基线；跨进程基准补「部署后真实链路」 | [REVIEW_p054_step10 §2](REVIEW_p054_step10_acceptance.md) | 两层基准分工：进程内守代码，跨进程守部署 |

### 5.3 多维评分

| 选项 | 兼容性 | 维护 | 短期 | 长期 | 升级潜力 | 总分 | 关键依据/风险 |
|------|--------|------|------|------|----------|------|----------------|
| **A 报告制** | **5** | **5** | **5** | 4 | **5** | **24** | 不改 CI、不引入抖动；后续可升级 SLO；风险是缺自动回归告警 |
| B CI SLO | 2 | 2 | 2 | 4 | 4 | 14 | 需 redis service + 阈值调参；共享 runner 误红风险高 |
| C 仅进程内 | **5** | **5** | **5** | 2 | 1 | 18 | 不满足总纲「端到端延迟基准」验收；无法发现部署层退化 |

**评分说明**：A 的长期 4（不是 5）是缺少自动回归告警，靠人工跑；升级 5 是因为脚本/报告格式不变即可加 `--assert-p99` 升级为 SLO。B 的兼容性/维护 2 是因为当前 CI 无 redis service，且共享 runner 抖动大；C 的长期 2 是明确不满足验收。

### 5.4 建议与条件

**推荐 A（置信度中高）**：

- 单元测试保留进程内微基准（确定性、FakeBus），守住代码层回归；
- `scripts/p055_bench_e2e.py` 作为**可复现验收出口**：真实 Redis + 进程边界，1k/10k，四段 p50/p95/p99，0 丢失、pending 归零；报告入库（`docs/` 或 CI artifact）。
- **可选 nightly**：非阻塞 job 启 redis service 跑一遍，失败只告警不挡 PR；等 runner 稳定后再升级为 SLO。
- **升级路径**：若未来有专用 runner/固定频率，可把 p99 阈值（例如 <50ms）设为门禁；脚本与报告格式不变，只加 `--assert-p99`。
- **如果选 B**：需接受误红与调参成本；建议至少用「同 runner 基线 + 15% 相对阈值」，不要用绝对毫秒。
- **如果选 C**：明确不满足总纲验收，需在 Step 10 登记偏差。

---

## 6. 总体方案多维评估（P-055 三条路线）

| 路线 | 兼容性 | 维护 | 短期 | 长期 | 升级潜力 | 总分 | 说明 |
|------|--------|------|------|------|----------|------|------|
| **A 部署化模块化单体（推荐）** | **5** | 3 | 4 | **5** | **5** | **22** | 4 进程 + Redis；补运行时；compose 双模式；import-linter；跨进程基准 |
| B 六服务网络拆分 | 2 | 2 | 2 | **5** | **5** | 16 | 策略/风控独立进程；分布式事务/超时/观测成本；SQLite 仍同机 |
| C 只修运行时、不做部署 | **5** | 3 | **5** | 2 | 2 | 17 | 修 consumer/heartbeat/market 即止；不满足「部署」验收，长期运维弱 |

**结论**：A 在兼容性、短期落地、升级潜力上均衡最优；B 只在「大规模多团队」长期场景胜出，与本仓现状不符；C 短期最快但验收不完整。**推荐 A**。

---

## 7. 若用户选择非推荐组合：影响与代价

| 选择 | 对 DESIGN 的影响 | 主要代价 |
|------|------------------|----------|
| U-P055-1 = B 全容器 | 需为 QMT 增加 Windows 容器/远程桥接方案；SQLite 需跨 WSL 挂载或改为 client/server | QMT GUI 不支持容器（S9）；WAL 风险；真实模式仍要破例 |
| U-P055-1 = C 全原生 | 删除 compose 交付；改为 NSSM/任务计划 + runbook | 无健康检查/重启策略/可复现 CI；「部署」验收弱化 |
| U-P055-2 = B/C | 新增 gRPC/HTTP 契约、超时/重试/熔断、分布式追踪、契约测试；拆分策略/风控服务 | 工期显著增加；submit 路径变长；SQLite 仍单机；运维复杂度上升 |
| U-P055-6 = B | API ro 挂载；需预创建 `-shm/-wal` 并实测 mmap 写权限 | 权限/升级易碎；可能回退 A |
| U-P055-6 = C | 需要迁移到 client/server 数据库或接受锁失败 | 超出 P-055 范围；数据损坏风险 |
| U-P055-4 = B | CI 加 redis service + 基准 job + 阈值 | 误红/调参；CI 时长增加 |
| U-P055-4 = C | Step 10 登记「未做跨进程基准」偏差 | 不满足总纲验收 |

---

## 8. 来源清单（Layer / 日期 / 版本）

| # | 来源 | Layer | 发布/更新日 | 读取日 | 版本 | 用途 |
|---|------|-------|-------------|--------|------|------|
| S1 | [InfoQ: Prime Video Switched from Serverless to EC2 and ECS to Save Costs](https://www.infoq.com/news/2023/05/prime-ec2-ecs-saves-costs/) | T2（行业媒体） | 2023-05 | 2026-11-23 | 页面 | Prime Video 90% 成本下降、EC2/ECS 重构 |
| S2 | [Docker: You Want Microservices—But Do You Need Them?](https://www.docker.com/blog/do-you-really-need-microservices/) | T2（厂商博客） | 未标注 | 2026-11-23 | 页面 | Prime Video 单体案例转述；「case-by-case」 |
| S3 | [Twilio Segment: Goodbye Microservices](https://www.twilio.com/en-us/blog/developers/best-practices/goodbye-microservices) | T2（公司工程博客） | 2018-07-10 | 2026-11-23 | 页面 | Segment 从微服务回单体；运维复杂度/可靠性 |
| S4 | [软件信札：Microservices: The Pattern Everyone Copied Wrong](https://www.softwareletters.com/p/sl-93-microservices-the-pattern-everyone-copied-wrong) | T3（二手总结） | 未标注 | 2026-11-23 | 页面 | Segment 140+ 服务、3 FTE 运维、共享库部署、测试 1h（二手数字，标注使用） |
| S5 | [Shopify Engineering: Deconstructing the Monolith](https://engineering.shopify.com/deconstructing-monolith-designing-software-maximizes-developer-productivity) | T2（公司工程博客） | 未标注 | 2026-11-23 | 页面 | 模块化单体 + 强制边界；千人级代码库 |
| S6 | [Su, Li, Taibi: Back to the Future: From Microservice to Monolith (arXiv:2308.15281)](https://arxiv.org/abs/2308.15281) | **T1**（学术论文） | 2023-08-29 | 2026-11-23 | v1 | 回退五因（成本/复杂度/可扩展性/性能/组织）+ 六项注意 |
| S7 | [Fowler: MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) | **T1**（领域权威） | 2015-06-03 | 2026-11-23 | 页面 | 先单体、边界稳定后再拆 |
| S8 | [Fowler: MicroservicePremium](https://martinfowler.com/bliki/MicroservicePremium.html) | **T1**（领域权威） | 2015-05-13 | 2026-11-23 | 页面 | 无复杂度驱动不要上微服务 |
| S9 | [Microsoft Learn: Using Windows Containers to Containerize Existing Applications](https://learn.microsoft.com/en-us/virtualization/windowscontainers/quick-start/lift-shift-to-containers) | **T1**（官方文档） | 未标注（适用 WS2016-2025） | 2026-11-23 | 页面 | Windows 容器不支持 GUI/交互桌面 |
| S10 | [miniQMT 知识问答 QA](https://miniqmt.com/pages/qa/knowledge-qa.html) | T3（社区知识库） | 2026-04（页面注明） | 2026-11-23 | 页面 | QMT 可云服务器部署；2C4G 最低/4C8G 建议 |
| S11 | [qmt-bridge 2.0.0 — PyPI](https://pypi.org/project/qmt-bridge/2.0.0/) | T2（包官方元数据） | 2.0.0 发布日（页面） | 2026-11-23 | 2.0.0 | miniQMT 仅 Windows + 客户端登录；Windows 中转 + 局域网 HTTP/WS |
| S12 | [Docker Docs: WSL 2 best practices](https://docs.docker.com/desktop/features/wsl/best-practices/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页 | 避免 `/mnt/c` bind mount；Linux FS 性能更高 |
| S13 | [SQLite User Forum: Linux process cannot write to sqlite database](https://www.sqlite.org/forum/forumpost/fc32d5d561?t=h) | **T1**（官方论坛，含 SQLite 开发者回复） | 2023-03-16 | 2026-11-23 | 帖子 | Linux Docker 非天然代理；网络/代理 FS 锁风险；Docker 损坏测试未复现 |
| S14 | [Docker Community Forums: Sqlite db locked when on a windows volume](https://forums.docker.com/t/sqlite-db-locked-when-on-a-windows-volume/13757) | T3（社区） | 2016-05-27 | 2026-11-23 | 帖子 | Windows volume 上 `database is locked` |
| S15 | [Docker Docs: Use Compose in production](https://docs.docker.com/compose/how-tos/production/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页 | 单服务器 compose、restart、多文件覆盖 |
| S16 | 同 S7（MonolithFirst） | **T1** | 2015-06-03 | 2026-11-23 | 页面 | 服务边界稳定前不拆 |
| S17 | 同 S8（MicroservicePremium） | **T1** | 2015-05-13 | 2026-11-23 | 页面 | 分布式系统额外成本 |
| S18 | [pytest-benchmark: The Complete Performance Testing Guide (2026)](https://qaskills.sh/blog/pytest-benchmark-performance-testing-guide) | T3（社区指南） | 2026 | 2026-11-23 | 页面 | 共享 CI runner 30%+ 波动；宽松阈值 |
| S19 | [Google Benchmark: Reducing Variance](https://google.github.io/benchmark/reducing_variance.html) | **T1**（官方文档） | 未标注 | 2026-11-23 | 文档页 | 固定 CPU 频率/稳定系统以降方差 |
| S20 | [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html) | **T1**（官方文档） | 未标注 | 2026-11-23 | 文档页 | 同机/单写者/只读 WAL/checkpoint 约束 |
| S21 | [迅投知识库：常见问题](https://dict.thinktrader.net/nativeApi/question_function.html) | T2（厂商文档镜像/知识库） | 未标注 | 2026-11-23 | 页面 | QMT 安装路径/管理员权限 |
| S22 | [Docker 挂载方式比较（Volume vs Bind Mount）](https://eastondev.com/blog/ja/posts/dev/20251217-docker-mount-comparison/) | T3（社区测试） | 2025-12-17 | 2026-11-23 | 页面 | Mac/Win bind mount 约 3.5× 慢于 volume |
| S23 | [华为云：用 import-linter 为 Python 项目声明分层契约并拦截架构腐化](https://bbs.huaweicloud.com/blogs/0eaba719fabd4bc3b24193fa7e65d3c9) | T3（社区实践） | 2026-10-29 | 2026-11-23 | 页面 | `layers`/`forbidden`、CI `lint-imports`、动态/字符串导入限制、固定版本 |

---

## 9. 降级链记录

| 目标 | 首选 | 降级 | 结果 |
|------|------|------|------|
| Prime Video 原始 AWS 博客 | aws.amazon.com 原文 | 抓取仅返回版权页 → InfoQ 报道 + Docker 博客转述 | 采用「90% 成本下降 + case-by-case」；标注 T2 |
| Segment 原文全文 | Twilio 博客正文 | 抓取仅导航 + AI 摘要 → 搜索摘要 + 二手总结（S4） | 一手确认迁移事实；140+/3 FTE/1h 测试标为二手数字 |
| Shopify 发布日期 | 页面元数据 | 未取到日期 → 标「未标注」 | 仅用于「模块化单体 + 强制边界」定性结论 |
| SQLite 在 Docker 的锁行为 | 单一结论 | 官方论坛正反双方（S13）→ 区分 Linux 本地卷/网络代理/Windows volume | 结论改为「Linux 本地卷可用、Windows/网络挂载有风险」 |
| named volume 性能 | 官方基准 | 社区测试（S22） | 仅作辅助，不作硬结论 |
| import-linter 精确配置 | readthedocs 全文（bot 拦截） | PyPI 元数据 + 华为云实践博客（S23） | 版本/契约/CI 用法已取；语法 Step 3 本地验证 |

> 注：S23 = [华为云：用 import-linter 为 Python 项目声明分层契约并拦截架构腐化](https://bbs.huaweicloud.com/blogs/0eaba719fabd4bc3b24193fa7e65d3c9)（2026-10-29，T3 社区实践）；补充：静态导入分析、`layers`/`forbidden`、CI `lint-imports`、动态/字符串导入无法可靠识别、建议固定版本。

---

## 10. 状态链

- **Step 1 补充调研完成（2026-11-23）**：4 个高影响决策均有 ≥2 外部锚点 + 仓内事实；多维评分与建议已落盘；**推荐 A/A/A/A**。
- **用户裁决（2026-11-23）**：**U-P055-1/2/4/6 全部采纳推荐 = A/A/A/A 定案**（双模式部署 / 不拆策略风控 / named volume 或原生盘 / 基准报告制）；U-P055-3/5/7/8 留 Step 3 工程定案。
- **Step 2 复审（2026-11-23，GLM-5.3-Flash 异构 ✅）**：引用可解析性合规、评分算术复算一致 → 本专项 0 P1；详见 [REVIEW_p055_step2](REVIEW_p055_step2_research.md) §1/§5。
- **零代码变更 / 未提交**：本步仅新增文档。
