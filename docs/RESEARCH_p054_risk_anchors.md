# RESEARCH：P-054 Step 3 两项风险的补充调研（SQLite WAL 只读 / TLS 最低版本）

> **批次**: P-054 · **补充调研（Step 3 风险锚点）** · 日期 2026-11-22 · **判档 P3**（零代码、零门禁）
> **触发**: [DESIGN_p054 §9](DESIGN_p054_service_layer.md#9-风险与未决) R1（WAL 只读 `-shm` 前提未取证）与 R2（uvicorn 不暴露 `ssl.minimum_version`）
> **方法**: E3 本设计读码 → E1 官方文档直取 → E2 官方源码（tag）→ T3 社区案例（仅作失败模式佐证）
> **基线**: Python **3.11**（Q13/B0）、uvicorn **0.54.0**（RESEARCH §19.2）、SQLite 为 Python 内置（远高于 3.22.0 的只读 WAL 特性）

---

## 0. 结论摘要

1. **R1 结论：设计可保留，但必须把「部署前提 + 启动 preflight」写进规格，而不是当作已成立事实。** SQLite 官方明确：WAL 库的打开进程必须有 `-shm` 写权限；若 `-shm` 不存在，则需数据库目录写权限。官方 3.22.0（2018-01-22）起允许只读打开，条件是「`-shm`/`-wal` 已存在且可读」或「目录可写可创建」或「数据库 immutable」。本仓交易进程持续写库 → **`immutable=1` 禁用**（官方警告会导致错误结果/SQLITE_CORRUPT）。**裁决：`mode=ro` + `PRAGMA query_only=ON` + 同机/同用户/目录可写前提 + 启动 preflight；失败即显式报错并退回内部 API（Q19 Plan B）。**
2. **R2 结论：风险已闭合，且比 DESIGN 原方案更简单。** uvicorn **0.54.0 源码已提供 `ssl_context_factory`**（`Config` 参数，构造器第 218 行），官方文档明确其用途包含「bumping `minimum_version`」，并给出把 `minimum_version` 设为 `TLSv1_3` 的完整示例。**裁决：用 top-level、可 pickle 的 factory 设置 `minimum_version = TLSv1_2` + `maximum_version = MAXIMUM_SUPPORTED` + AEAD-only cipher + 启动断言；不再依赖「cipher 串间接排除 1.0/1.1」。**
3. **额外收获（强化 Q19）**：WAL 的 wal-index 位于共享内存，官方原文「all readers must exist on the same machine」「will not work on a network filesystem」——跨机读**不能**直接挂 SQLite 文件，必须走内部 API。这与 Q19 的原裁决完全一致，且从「工程建议」升级为**官方硬约束**。
4. **两层 TLS 保障**：Python 3.10 起 `SSLContext` 默认最低协议即为 TLS 1.2（What's New 3.10）；Q13 的 Python 3.11 基线使这一默认生效。`ssl_context_factory` 的显式 `minimum_version` 作为第一层，默认值作为第二层。
5. **两项风险的验收均可测试**：R1 → preflight（`PRAGMA journal_mode=='wal'` + 一次 `MAX(seq)` 读 + 失败路径）；R2 → factory 断言（`minimum_version`、`get_ciphers()` 协议集合、pickle 可序列化）+ 可选 TLS1.1 拒绝握手。均落在既有 120 例的 `ledger_store_atomic` / `api_auth` 覆盖项内，不改变用例总数。

---

## 1. 题干（DESIGN §9 原文）

| ID | 风险原文 | 需要回答的问题 |
|----|----------|----------------|
| **R1** | 只读 WAL 连接需 `-shm`/`-wal` 访问（同目录写权限/共享内存），S53 只读节未取证 | 只读连接到底需要什么权限？失败是什么错误？能否用 `immutable=1` 绕过？跨机能不能读？ |
| **R2** | uvicorn 不暴露 `ssl.minimum_version`，只能靠 AEAD-only cipher 间接排除 | uvicorn 是否有受支持的扩展点？如果只有 cipher，能否证明 1.0/1.1 被禁用？ |

---

## 2. R1：SQLite WAL 只读数据库的访问条件

### 2.1 一手事实（官方原文）

**S62《Write-Ahead Logging》§5 Read-Only Databases**：

> "On newer versions of SQLite, a WAL-mode database on read-only media, or a WAL-mode database that lacks write permission, can still be read as long as one or more of the following conditions are met:
> - The `-shm` and `-wal` files already exist and are readable.
> - There is write permission on the directory containing the database so that the `-shm` and `-wal` files can be created.
> - The database connection is opened with the `immutable=1` URI parameter（官方页此条被截断，语义由 S63/S64 互证：数据库不可变）"

同页更早段落：

> "It is not possible to open read-only WAL databases. The opening process must have write privileges for `-shm` wal-index shared memory file associated with the database, if that file exists, or else write access on the directory containing the database file if the `-shm` file does not exist. Beginning with version 3.22.0 (2018-01-22), a read-only WAL-mode database file can be opened if …"

**S62 §2.2 Concurrency**（跨机约束）：

> "the use of shared memory means that **all readers must exist on the same machine**. This is why the write-ahead log implementation **will not work on a network filesystem**."

**S63《Uniform Resource Identifiers》`immutable=1`**：

> "The immutable query parameter is a boolean that signals to SQLite that the underlying database file is held on read-only media and cannot be modified, even by another process with elevated privileges. SQLite always opens immutable database files read-only and it skips all file locking and change detection."
> "**Caution:** Setting the immutable property on a database file that does in fact change can result in **incorrect query results and/or SQLITE_CORRUPT errors**."

**S65 Python `sqlite3` 文档**（只读 URI 的官方用法）：

```python
con = sqlite3.connect("file:tutorial.db?mode=ro", uri=True)
con.execute("CREATE TABLE readonly(data)")
# sqlite3.OperationalError: attempt to write a readonly database
```

### 2.2 外部锚点表

| # | 来源 | Layer | 版本 / 日期 | 读取日 | 用途 |
|---|------|-------|-------------|--------|------|
| **S62** | [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html) | **T1**（官方文档） | 页面未标注；正文引用 3.22.0（2018-01-22） | 2026-11-22 | WAL 只读三条件、`-shm` 写权限、同机/网络文件系统限制 |
| **S63** | [SQLite: Uniform Resource Identifiers](https://www.sqlite.org/uri.html) | **T1**（官方文档） | 页面未标注 | 2026-11-22 | `immutable=1` 语义与「会变化的库」警告 |
| **S64** | [SQLite User Forum: Need help with read only access to database](https://www.sqlite.org/forum/forumpost/4977b5b804e0cd0d?t=h&unf) | **T1**（官方论坛，2021-07-14） | 3.22.0 特性 | 2026-11-22 | 社区同构问题：只读 WAL 依赖 3.22.0+ 的只读支持 |
| **S65** | [Python 3.11 sqlite3 文档](https://docs.python.org/zh-cn/3.11/library/sqlite3.html) | **T1**（官方文档） | Python 3.11 | 2026-11-22 | `uri=True` + `mode=ro` 的官方写法与错误签名 |
| **S66** | [SQL Docs: SQLite "Unable to Open Database File"](https://sqldocs.org/sqlite-unable-to-open-database-file/) | T3（工程博客，实测向） | 未标注 | 2026-11-22 | 失败案例：文件需读、**目录需写**（journal/shm 创建） |
| **S67** | [Sling Academy: SQLite Error: Cannot Open Database in WAL Mode](https://www.slingacademy.com/article/sqlite-error-cannot-open-database-in-wal-mode/) | T3（教程） | 未标注 | 2026-11-22 | WAL 打开失败的常见原因清单（权限/目录） |

> 说明：S66/S67 仅用于「失败模式与错误现象」旁证，不作为结论依据；结论全部由 S62/S63/S65 三条 T1 支撑。

### 2.3 失败模式与错误签名

| 场景 | 预期行为 | 错误签名（Python `sqlite3`） |
|------|----------|------------------------------|
| 目录无写权限、`-shm` 不存在 | 打开失败 | `OperationalError: unable to open database file` |
| 只读连接上执行写 SQL | 拒绝写入 | `OperationalError: attempt to write a readonly database`（S65 原文示例） |
| 对持续变化的库用 `immutable=1` | 读到的数据可能陈旧/错乱，官方警告可致 `SQLITE_CORRUPT` | 不报错但结果不可信（S63） |
| 跨机（网络文件系统）打开 WAL 库 | 不支持 | 打不开/锁异常（S62 §2.2 原文） |
| 同用户、同目录可写（本仓默认） | 正常读，且与写者并发不互相阻塞 | `PRAGMA journal_mode` 返回 `wal` |

### 2.4 候选方案

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（采纳）`mode=ro` + `query_only=ON` + 前提 + preflight** | API worker 以只读 URI 打开；启动校验 `journal_mode=='wal'`、一次 `MAX(seq)` 读；失败显式报错 | 与 Q19 一致；读写并发不阻塞；错误可观测 | 依赖「同机、同用户、目录可写」；不同用户/只读挂载会失败 |
| B `immutable=1` | 只读 URI 加 `immutable=1`，跳过锁与变更检测 | 对真静态库零权限要求 | **禁止**：交易进程持续写入 → 官方警告错误结果/损坏（S63）；且丢失「读到你写的」一致性 |
| C 全部走内部 API | 放弃同机只读 SQLite，API worker 只调用交易进程内部读接口 | 无文件权限耦合 | 多一跳网络/进程调用；Q19 已裁决「同机优先只读」；仅作为 B 失败时的 Plan B |

### 2.5 决策（A + 前置条件 + preflight）

**部署前提（写入 §3.8 校验与 runbook）**：

1. API worker 与交易进程**同一台机器、同一 OS 用户**（或 ACL 至少授予数据库目录 `Modify`）。
2. 数据库目录对 API worker **可写**（用于 `-shm`/`-wal` 的打开/创建），即使它只执行 SELECT。
3. 不使用 `immutable=1`；不把数据库放在网络文件系统/共享盘。
4. 前提不成立时走 **Plan B**：由交易进程暴露内部只读 API（Q19），API worker 不挂 SQLite 文件。

**preflight 规格**（`SqliteLedgerStore.__init__(read_only=True)` 之后调用）：

```python
def assert_readonly_ready(store) -> None:
    try:
        mode = store.conn.execute("PRAGMA journal_mode").fetchone()[0]
    except sqlite3.OperationalError as e:
        # "unable to open database file" → permission；"no such table" → uninitialized
        raise StoreReadOnlyError(reason=classify_open_error(e), detail=str(e)) from e
    if str(mode).lower() != "wal":
        raise StoreReadOnlyError(reason="not_wal", detail=f"journal_mode={mode!r}")
    try:
        store.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM outbox").fetchone()
    except sqlite3.OperationalError as e:
        raise StoreReadOnlyError(reason="uninitialized", detail=str(e)) from e
```

**reason 分类**（F-D9 修复）：`permission`（`unable to open database file`）/ `uninitialized`（`no such table`，交易进程尚未初始化）/ `not_wal` / `internal_api_required`（显式 Plan B）。错误消息按 reason 给出对应修复路径：同用户 / 目录授权 / 先启动 trading_worker / 改用内部 API。

- 失败 → worker **启动失败**（不进入 ready），日志按 `reason` 给出对应修复路径；禁止降级为「假装可读」。
- 成功 → ready 检查继续（Redis/心跳/恢复态）。

### 2.6 验收探针（映射到既有 120 例）

| 探针 | 归属用例 | 断言 |
|------|----------|------|
| 正常 WAL 库只读打开 | `test_p054_ledger_store_atomic`（只读模式项） | preflight 通过；`journal_mode == 'wal'` |
| 写操作被拒 | 同上 | `attempt to write a readonly database`（`query_only` 生效） |
| 并发读者与写者 | 同上 | 写者提交前读者看不到新行，提交后可见；读写互不阻塞 |
| 缺少目录写权限 | 同上（Windows ACL 用 `icacls` 构造；CI 不满足则 skip 并登记） | 抛 `StoreReadOnlyError(reason="permission")`，消息含三条修复路径（同用户 / 目录授权 / 内部 API） |
| 跨机读取 | 文档负例（不写测试） | 引 S62 §2.2，跨机一律内部 API |

---

## 3. R2：uvicorn 的 TLS 最低版本

### 3.1 一手事实

**S68 uvicorn 0.54.0 `uvicorn/config.py`（tag 直取）**：

```python
# L104-L124
def create_ssl_context(certfile, keyfile, password, ssl_version, cert_reqs,
                       ca_certs, ciphers, alpn_protocols=None) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl_version)
    ctx.load_cert_chain(certfile, keyfile, get_password)
    ctx.verify_mode = ssl.VerifyMode(cert_reqs)
    ...
    if ciphers:
        ctx.set_ciphers(ciphers)

# L218（Config 构造器参数）
ssl_context_factory: Callable[[Config, Callable[[], ssl.SSLContext]], ssl.SSLContext] | None = None,
```

→ **0.54.0 已内置扩展点**；`create_ssl_context` 自身不设置 `minimum_version`，所以默认行为由 `ssl.PROTOCOL_TLS_SERVER` 决定。

**S69 uvicorn 文档（settings，HTTPS 节）**：

> "For advanced TLS scenarios that the flags above don't cover (e.g., mutual TLS, certificate pinning, custom `SSLContext.options`), pass an `ssl_context_factory` to `uvicorn.run()` or `Config`."

**S70 uvicorn 文档（deployment，「Customizing the SSL context」）**：

> "For TLS scenarios that the `--ssl-*` flags don't cover (e.g., mutual TLS, custom `SSLContext.options`, **bumping `minimum_version`**, loading certificates from memory), pass an `ssl_context_factory` …"
> 示例：
> ```python
> def ssl_context_factory(config: Config, default_ssl_context_factory: Callable[[], ssl.SSLContext]) -> ssl.SSLContext:
>     context = default_ssl_context_factory()
>     context.minimum_version = ssl.TLSVersion.TLSv1_3
>     return context
> ```
> "The factory is called inside each worker process, so it works with `--reload` and `--workers > 1`. The factory itself must be **picklable** in those modes (a top-level function is fine; lambdas and local closures are not)."

**S71 Python `ssl` 文档**：`SSLContext.minimum_version` / `TLSVersion`（3.7+）；`PROTOCOL_TLS_SERVER` 默认最低版本为 **TLS 1.2**（Python 3.14 文档原文，与 3.10 What's New 一致）。

**S72 Python 3.10 What's New**：

> "`SSLContext` 默认的最低版本协议为 TLS 1.2。"

→ Q13 的 Python 3.11 基线使「默认最低 TLS 1.2」成为第二层保障。

### 3.2 外部锚点表

| # | 来源 | Layer | 版本 / 日期 | 读取日 | 用途 |
|---|------|-------|-------------|--------|------|
| **S68** | [uvicorn 0.54.0 `config.py`](https://raw.githubusercontent.com/encode/uvicorn/0.54.0/uvicorn/config.py) | **T1**（官方源码，tag 锁定） | 0.54.0 | 2026-11-22 | `ssl_context_factory` 存在性；`create_ssl_context` 不设 `minimum_version` |
| **S69** | [uvicorn Settings](https://raw.githubusercontent.com/encode/uvicorn/main/docs/settings.md) | **T1**（官方文档） | main（读取日） | 2026-11-22 | `ssl_context_factory` 的官方入口说明 |
| **S70** | [uvicorn Deployment: Customizing the SSL context](https://raw.githubusercontent.com/encode/uvicorn/main/docs/deployment/index.md) | **T1**（官方文档） | main（读取日） | 2026-11-22 | `minimum_version` 示例、每 worker 调用、**必须可 pickle** |
| **S71** | [Python `ssl` 文档](https://docs.python.org/3/library/ssl.html) | **T1**（官方文档） | 3.11/3.14 | 2026-11-22 | `minimum_version`/`TLSVersion`；`PROTOCOL_TLS_SERVER` 默认 TLS1.2 |
| **S72** | [Python 3.10 What's New](https://docs.python.org/zh-cn/3.10/whatsnew/3.10.html) | **T1**（官方文档） | 3.10 | 2026-11-22 | 默认最低协议 TLS 1.2（Q13 基线的第二层保障） |

### 3.3 候选方案

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（采纳）`ssl_context_factory` + 显式 `minimum_version`** | top-level factory：取默认上下文 → `minimum_version=TLSv1_2` → `maximum_version=MAXIMUM_SUPPORTED` → AEAD cipher → 返回 | 协议级强制；官方支持；`--workers` 兼容；可单测 | 需保证 factory 是 top-level（可 pickle）；需改用程序化 `uvicorn.run` |
| B 仅 `--ssl-ciphers` | AEAD-only cipher 串 | 零代码 | 无协议级声明；是否排除 1.0/1.1 依赖套件细节；不可断言 |
| C 反向代理终止 TLS | nginx/Caddy 配 `ssl_protocols TLSv1.2 TLSv1.3` | 协议控制最成熟 | 多一个组件/端口/证书位置；自用内网收益低；保留为跨机部署选项 |
| D 换 Hypercorn 等 | 依赖其 `ssl_minimum_version` 配置 | 配置直观 | 改服务器栈，超出本批收益 |

### 3.4 决策（A）

**实现规格**：

```python
# services/api_worker.py —— 必须是模块级函数（--workers 下可 pickle）
def build_ssl_context(config, default_factory):
    ctx = default_factory()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES")
    ctx.options |= ssl.OP_NO_COMPRESSION
    return ctx

uvicorn.run(
    "services.api:create_app", factory=True, workers=N,
    ssl_keyfile=..., ssl_certfile=..., ssl_ca_certs=...,
    ssl_cert_reqs=ssl.CERT_REQUIRED if mTLS else ssl.CERT_NONE,
    ssl_context_factory=build_ssl_context,
)
```

**启动断言**（每个 worker）：

1. `ctx.minimum_version == ssl.TLSVersion.TLSv1_2`。
2. `ctx.get_ciphers()` 中每个条目的 `protocol` ∈ `{"TLSv1.2", "TLSv1.3"}`（无 `TLSv1`/`TLSv1.1`）。
3. `pickle.dumps(build_ssl_context)` 成功（`--workers > 1` 前提）。
4. 明文仅 `allow_plaintext_loopback=True` 且绑定 `127.0.0.1`；否则证书/私钥缺失即启动失败。

> TLS 1.3 仍可用（`maximum_version=MAXIMUM_SUPPORTED`），符合 Q16「1.3 优先、1.2 兼容」；不强制只允许 1.3。

### 3.5 验收探针（映射到既有 120 例）

| 探针 | 归属用例 | 断言 |
|------|----------|------|
| factory 设置最低版本 | `test_p054_api_auth`（TLS 配置项） | `minimum_version == TLSv1_2`；`maximum_version == MAXIMUM_SUPPORTED` |
| cipher 协议集合 | 同上 | `get_ciphers()` 的 `protocol` 全为 TLSv1.2/1.3 |
| factory 可 pickle | 同上 | `pickle.dumps` 成功（top-level 函数） |
| 拒绝 TLS 1.1 握手 | 同上（集成项，可用本地 socket + 自签证书；CI 可标记） | 客户端强制 `maximum_version=TLSv1_1` 时握手失败 |
| `--workers 2` 生效 | `test_p054_end_to_end`（双 worker 项） | 两个 worker 均打印 `tls_min=TLSv1.2`，握手成功 |

---

## 4. 对 DESIGN 的回写点

| DESIGN 位置 | 回写内容 |
|-------------|----------|
| §3.8 `ServiceSettings` | 新增 `tls_ciphers` 默认 AEAD-only；校验仍要求证书/私钥成对 |
| §4 **D15** | 改为「`ssl_context_factory` + `minimum_version=TLSv1_2` + AEAD cipher + 启动断言」；注明 Python 3.11 默认 TLS1.2 为第二层 |
| §5 阈值表 | 新增 TLS cipher 串默认值；TLS 最低版本行改为「由 factory 强制」 |
| §6 **I14** | 验证方式改为「factory 断言 + `get_ciphers()` 协议集合 + 可选 TLS1.1 拒绝握手」 |
| §8 偏差 #10 | 由「未取证前提」改为「**已取证**：WAL 只读三条件（S62）+ 同机约束（S62 §2.2）；preflight 失败走内部 API」 |
| §9 **R1** | 状态改为「已缓解：前提 + preflight + Plan B」；补三条失败签名 |
| §9 **R2** | 状态改为「**已关闭**：uvicorn 0.54.0 `ssl_context_factory`（S68-S70）」 |
| §10.2 **B0** | 增加「Python 3.11 → PROTOCOL_TLS_SERVER 默认 TLS1.2」回归确认 |
| §10.2 **B4/B5** | 增加 preflight 用例与 TLS factory 用例（计入既有 120 例） |

---

## 5. 来源清单（S62-S72）

> **编号约定（F-D10 修复）**：S62-S72 的**唯一定义在本表**；主 RESEARCH 不再复用该编号段，后续新来源从 **S73** 起编号。

| # | 来源 | Layer | 发布/更新 | 读取日 | 版本 | 用途 |
|---|------|-------|-----------|--------|------|------|
| S62 | [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html) | **T1** | 未标注（正文引 3.22.0/2018-01-22） | 2026-11-22 | 官方文档 | WAL 只读三条件、`-shm` 写权限、同机/网络文件系统限制 |
| S63 | [SQLite: Uniform Resource Identifiers](https://www.sqlite.org/uri.html) | **T1** | 未标注 | 2026-11-22 | 官方文档 | `immutable=1` 语义与损坏警告 |
| S64 | [SQLite User Forum: read only access](https://www.sqlite.org/forum/forumpost/4977b5b804e0cd0d?t=h&unf) | **T1** | 2021-07-14 | 2026-11-22 | 论坛帖 | 只读 WAL 依赖 3.22.0+ 的社区同构问题 |
| S65 | [Python 3.11 sqlite3](https://docs.python.org/zh-cn/3.11/library/sqlite3.html) | **T1** | Python 3.11 | 2026-11-22 | 3.11 | `uri=True` + `mode=ro` 与只读错误 |
| S66 | [SQL Docs: Unable to Open Database File](https://sqldocs.org/sqlite-unable-to-open-database-file/) | T3 | 未标注 | 2026-11-22 | 博客 | 目录写权限失败案例（旁证） |
| S67 | [Sling Academy: Cannot Open Database in WAL Mode](https://www.slingacademy.com/article/sqlite-error-cannot-open-database-in-wal-mode/) | T3 | 未标注 | 2026-11-22 | 教程 | WAL 打开失败原因（旁证） |
| S68 | [uvicorn 0.54.0 config.py](https://raw.githubusercontent.com/encode/uvicorn/0.54.0/uvicorn/config.py) | **T1** | 0.54.0 tag | 2026-11-22 | 0.54.0 | `ssl_context_factory` 存在；默认上下文不设 `minimum_version` |
| S69 | [uvicorn Settings](https://raw.githubusercontent.com/encode/uvicorn/main/docs/settings.md) | **T1** | main | 2026-11-22 | main | factory 官方入口 |
| S70 | [uvicorn Deployment: Customizing the SSL context](https://raw.githubusercontent.com/encode/uvicorn/main/docs/deployment/index.md) | **T1** | main | 2026-11-22 | main | `minimum_version` 示例、每 worker、可 pickle |
| S71 | [Python ssl](https://docs.python.org/3/library/ssl.html) | **T1** | 3.11/3.14 | 2026-11-22 | 3.11/3.14 | `minimum_version`/`TLSVersion`、默认 TLS1.2 |
| S72 | [Python 3.10 What's New](https://docs.python.org/zh-cn/3.10/whatsnew/3.10.html) | **T1** | 3.10 | 2026-11-22 | 3.10 | `SSLContext` 默认最低协议 TLS1.2 |

> **未取证 / 降级**：uvicorn 0.54.0 的**发布说明**未逐条直取（仅源码 tag 与 main 文档）；`set_ciphers` 对 TLS1.3 套件的作用范围未单独取证——因此本设计不把 cipher 串当作唯一机制，协议级强制由 `minimum_version` 承担。
> **未采用来源**：S66/S67 为 T3，仅作失败现象旁证；`immutable=1` 的社区用法未采纳（与 S63 警告冲突）。

---

## 6. 状态链

**补充调研完成（2026-11-22）**：R1 取得 SQLite 官方 WAL 只读三条件 + 同机硬约束 + `immutable` 禁令（S62/S63/S65），裁决「前提 + preflight + Plan B」；R2 取得 uvicorn 0.54.0 `ssl_context_factory`（S68）与官方 `minimum_version` 示例（S70），裁决「factory + 显式 TLS1.2 + 断言」；另以 S62 §2.2 强化 Q19 跨机边界 → 回写 DESIGN §3.8/§4 D15/§5/§6 I14/§8 #10/§9 R1-R2/§10.2 → 待 Step 4 设计复审一并核对。
