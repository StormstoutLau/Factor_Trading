# RUNBOOK：P-055 微服务化部署（Mode S / Mode R）

> 批次 P-055 · 2026-11-23 · 配套 [IMPL_p055](IMPL_p055_microservices.md) §3.11 / [DESIGN_p055](DESIGN_p055_microservices.md) §4
> 本文只写操作步骤与红线；架构理由见 DESIGN。

## 1. 前置与证书

1. Docker Desktop（Mode S）或 Docker + 原生 Python 3.11（Mode R）。
2. 生成 30 天自签证书（容器与原生进程通用）：

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -keyout deploy/certs/key.pem -out deploy/certs/cert.pem \
  -subj "/CN=localhost"
```

3. `cp .env.services.example .env.services`，至少改 `P054_API_KEY`（≥16 字符）。
4. 红线：**证书与 `.env.services` 不入库**（`.gitignore` 已覆盖 `deploy/certs/*.pem`、`.env.services`）。

## 2. Mode S（synthetic / CI，全容器）

```bash
docker compose -f deploy/compose.services.yaml up -d --build
docker compose -f deploy/compose.services.yaml ps
curl -k https://127.0.0.1:8054/health/live
curl -k https://127.0.0.1:8054/health/ready
```

- 顺序由 `depends_on.condition: service_healthy` 保证：redis → trading → api。
- SQLite 位于 named volume `p055-data`（`/app/run`）；**禁止**改为 Windows→WSL bind mount（WAL 跨挂载文件锁不可靠）。
- 观测（可选）：`docker compose -f deploy/compose.services.yaml --profile obs up -d`，Prometheus 抓 `https://api:8054`（自签跳过校验），端口只发布到 `127.0.0.1:9090`。
- 查看日志：`docker compose -f deploy/compose.services.yaml logs -f trading api`。

## 3. Mode R（真实 QMT/CTP，Windows 原生 + 仅 Redis 容器）

1. 启动 Redis：`docker run -d --name p055-redis -p 127.0.0.1:6379:6379 redis:7 --appendonly yes`。
2. SQLite 路径必须是 **NTFS 原生盘**（如 `D:\p055\live_ledger.db`），禁止放在 WSL 挂载路径。
3. 用 NSSM 注册三个服务（示例）：

```powershell
nssm install P055Trading "D:\venv\Scripts\python.exe" "-m services.trading_worker"
nssm install P055Market  "D:\venv\Scripts\python.exe" "-m services.market_gateway"
nssm install P055Api     "D:\venv\Scripts\python.exe" "-m services.api_worker"
nssm set P055Trading AppStopMethodConsole 15000
nssm set P055Market  AppStopMethodConsole 15000
nssm set P055Api     AppStopMethodConsole 15000
nssm start P055Trading; nssm start P055Market; nssm start P055Api
```

- NSSM 停机首步发 Control-C，应用把信号转为 `stop_event` 后按「置位 → 停心跳 → join(5s) → gateway.shutdown」收尾。
- 任务计划仅作回退：其停止通常等价 SIGKILL，`finally` 不执行，可能出现未发送 outbox（重启后由 relay 续发）。
- `P054_ALLOW_PLAINTEXT_LOOPBACK=1` 仅允许 `P054_API_HOST=127.0.0.1`；对外必须 TLS。

## 4. 备份与恢复

```bash
sqlite3 /app/run/live_ledger.db ".backup '/backup/live_ledger-$(date +%F).db'"
```

- 在线备份用 `.backup`（WAL 安全），不要直接复制 `-wal/-shm`。
- 恢复顺序：停 trading → 停 api → 还原 db → 启动 trading（`start()` 重放/对账）→ 确认 `/health/ready` 200 → 启 api。
- outbox 未发送时不要删 Streams；relay 以 `ORDER BY seq` 续发（at-least-once）。

## 5. 证书轮换

1. 生成新证书到 `deploy/certs/`（覆盖前先备份）。
2. Mode S：`docker compose -f deploy/compose.services.yaml restart api`。
3. Mode R：`nssm restart P055Api`。
4. 校验：`curl -k https://127.0.0.1:8054/health/live` 200；`openssl s_client -connect 127.0.0.1:8054 -servername localhost </dev/null 2>/dev/null | openssl x509 -noout -dates`。

## 6. 故障排查

| 症状 | 判定 | 处置 |
|------|------|------|
| `/health/ready` 503 `stale_trading` | `p054:trading:heartbeat` 缺失或滞后 > `P054_READY_STALENESS_SECONDS` | 检查 trading 进程与 relay/consumer 线程；`redis-cli GET p054:trading:heartbeat` |
| 503 `stale_consumer` | consumer 心跳缺失 | 检查 `p054-consumer` 线程与 Streams 消费组 |
| 503 `recovery_incomplete` | `recovery_state` 非 complete/degraded_positions | 查 trading 启动日志；必要时重跑 `gateway.start()` |
| WS 关闭码 4401 | ticket 无效/过期/已用 | 重新 `POST /api/ws-ticket` 后连接 |
| WS 关闭码 4503 | 未就绪（recovery 未完成） | 先修复 readiness |
| WS 关闭码 1013 | 慢消费者（订单队列满 >5 s） | 客户端加速消费或重连走快照 |
| 容器启动即退出 | 证书路径/属主/卷权限 | `docker compose logs api`；确认 `/app/run` 属主 appuser（uid 10001） |
| 进程启动即静默退出（code 0、无日志） | 入口模块缺 `if __name__ == "__main__": main()` 守卫（Step 10 F-B9 已修，防回归用例 `test_entry_modules_have_main_guard`） | 确认模块末尾守卫存在；`python -m services.trading_worker --once` 应完成一轮 poll |
| 启动报 `FileExistsError: live_ledger.db.lock` | 上次运行被强杀（TerminateProcess）残留单写者锁（`O_EXCL` 保护正确；正常停机自动删） | 确认无 trading 进程后 `rm live_ledger.db.lock` 再启动（F-B10） |
| 卷属主错误（R1） | named volume 首启 copy-up 属主异常 | `docker compose down -v` 后重建，或 `chown -R 10001:10001 /app/run` |

## 7. 跨机只读回退（仅文档化，不建读模型）

Q19 已裁决：**不建 Redis 读模型**。跨机只读需求按以下顺序降级：

1. 同机多 API 容器（推荐）：共享 named volume，读 `mode=ro`。
2. 跨机：仅通过内部 API（`/api/snapshot`、`/api/orders`、`/api/events`）读取，不直连 SQLite。
3. 触发重评：若出现「跨机低延迟读」硬需求，另立批次评估只读副本/读模型（本批不做）。

> 策略/风控进程化的触发条件（U-P055-2，不在本批实施）：独立部署/扩缩、不同语言运行时、单笔决策 P99 需跨机隔离、出现第二个同步闸门消费方——满足任一再评估。
