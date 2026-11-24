# REVIEW：P-060 Step 2 异构复审记录

> **复审对象**: [RESEARCH_p060_module_verification](RESEARCH_p060_module_verification.md)（Step 1 调研，U-P060-1..6 已闭合）
> **复审依据**: RESEARCH §12 复审输入 7 项
> **作者 / 复审人**: 作者 DeepSeek-V4.1-Flash；主审 **GLM-5.3-Flash** + 3 个独立上下文子代理（静态映射 / 锚点联网核验 / 文档一致性）→ **RULE-5（reviewer ≠ author）满足**
> **日期**: 2026-11-24
> **结论**: **PASS —— 可进入 Step 3 DESIGN**（4 处修订已落 RESEARCH，2 项移交 Step 3，详见 §6）

---

## 1. 复审范围与方法

| 项 | RESEARCH §12 输入 | 方法 | 执行者 |
|---|---|---|---|
| 1 | E1 重放 | 后台顺序实跑 5 条命令，JSON 精确对账 | 主审（后台） |
| 2 | 静态映射复核（11 零引用模块 + 抽查） | 全仓 Grep/Read 独立取证 | 子代理 A（Explore）+ 主审补充 |
| 3 | 缺口定性 / 重复计数 | 文档逐项核对 + 算术复算 | 主审（子代理 B 两轮仅返回位置索引未产出结论，**由主审替代完成并如实披露**） |
| 4 | 外部锚点复核（A1-A5 + A10-A38 抽检 8 条） | WebFetch 联网逐条核对原文 | 子代理 C（general-purpose） |
| 5 | 裁定复核（U-P060-4/5/6 可执行性） | 文档逐条评估 | 主审 |
| 6 | 范围守卫 | `git status` / `git diff --stat` | 主审 |
| 7 | 门禁算术 | collect 与覆盖率目标估算对账 | 主审 |

## 2. 项 1 + 7：E1 重放对账（@`b1afe29`，工作树仅 docs 变更）

| 读数 | 调研基线 | Step 2 重放 | 判定 |
|---|---|---|---|
| `-k golden` | 22 | **22 passed**（28.93s） | ✓ |
| `-k p059` | 63 | **63 passed**（48.77s） | ✓ |
| 全量 | 1502 passed + 1 skipped | **1502 passed + 1 skipped**（138.03s） | ✓ |
| 覆盖率 A 总量 | 85.80%（10437/12165） | **85.80%（10432/12165）**（183.49s） | ✓ 两位小数一致 |
| ├ core | 86.52%（9117 stmts） | 86.46%（7883/9117） | −5 行，见 F-6 |
| ├ live | 87.95% | **87.95%（1489/1693）** | ✓ 逐位一致 |
| ├ services | 74.54% | **74.54%（814/1092）** | ✓ 逐位一致 |
| ├ strategies | 93.54% | **93.54%（246/263）** | ✓ 逐位一致 |
| 覆盖率 B 总量 | 44.07%（2499/5670） | **44.07%（2499/5670）** | ✓ 逐位一致 |
| ├ filter / agents | 44.44% / 43.96% | **44.44%（591/1330）/ 43.96%（1908/4340）** | ✓ 逐位一致 |
| 加权全模块 | 72.53%（12936/17835） | 72.51%（12931/17835） | ✓ −0.02pp（F-6 传导） |

**抽查文件（covA JSON）**：`market_gateway` **0%（0/63）**、`bus` 64（100/157）、`trading_worker` 64（58/91）、`ws_routes` 74（96/130）、`api` 76（131/172）、`factor` 65（178/275）、`rebalance` 35（53/153）、`tracker` 79（276/350）、`execution` 85（139/164）——**与 §3.3/§3.5 全部对上**。

**门禁算术（项 7）**：B1 预估 35-45 例 / B2 预估 30-40 例 → 终态 collect ≈ 1503 + 65-85；I10 单轮 183.49s ≤ 300s 余量 116s。**通过**。

## 3. 项 2：静态映射复核

11 个零引用模块全部**证实**（含修正后定性）：

| 模块 | 复审判定 |
|---|---|
| `services/market_gateway.py` | 证实：生产调用方 `trading_worker`（`run_embedded`，[trading_worker.py:211-218](../services/trading_worker.py#L211-L218)）；测试侧仅 [test_p055_entrypoint.py:76-79](../tests/test_p055_entrypoint.py#L76-L79) **read_text 断言 `__main__` 守卫、不 import** → 覆盖 0% 一致（F-5） |
| `services/ws_routes.py` | 证实：[api.py:87-97](../services/api.py#L87-L97) lifespan 导入 + [:287-291](../services/api.py#L287-L291) `mount_ws(app)` 间接挂载 |
| `filter/base.py` | 证实：`extended/industry/market_cap/na_factor/prefix` 均 `from .base import`（相对导入 5 子模块）；tests 零 import |
| filter 5 子模块 | 证实：仅 [filter/__init__.py](../filter/__init__.py#L30-L100) 集中导出；tests 全文搜索零 import |
| agents 三模块 | **修正（F-4）**：非严格「全仓零调用」——`test_compatibility.py:43-46` 字符串清单 + `style_drift_analysis.py:528` 包内 `from adaptive_agent import AdaptiveAgent`（顶层绝对导入、函数内死路径）；无功能调用，legacy 结论不变 |

**新发现（F-3）**：[engine_plugins.py:361-383](../core/engine_plugins.py#L361-L383) 注册 `Fixed/Conditional/HybridTrigger` 工厂（生产引用存在），但默认引擎路径仅选择 `FixedIntervalTrigger` → Conditional/Hybrid 执行体仍未覆盖；`RebalanceCalendar`（[rebalance.py:301](../core/rebalance.py#L301)）全仓无生产引用。§3.3 定性已修订。

## 4. 项 4：外部锚点复核（13 条）

| ID | 状态 | 说明 |
|---|---|---|
| A1 | 证实* | "Write *lots* of small and fast unit tests…*very few* high-level tests"；正文抓取在 Integration 章节前截断 |
| A2 / A4 | 证实† | Crossref DOI 元数据：Barr et al. TSE 41(5):507-525 2015 / Inozemtseva & Holmes ICSE'14:435-445 |
| A3 | 证实† | Crossref：CSUR 51(1) pp.1-27，online 2018-01-04 / print 2019-01（RESEARCH 已补日期注记） |
| A5 | **unreachable** | 两次抓取异常返回无关片段 → 已标注，Step 3 不依赖其原文细节 |
| A11 | **unreachable** | raw 两次空返回（本机直连亦超时）→ 已标注 |
| A12 | 证实 | SEV-5 "Cosmetic issues…Create a JIRA ticket and assign to owner" |
| A15 | 证实 | "fix it right there and then"；"another day often doesn't come" |
| A16 | **unreachable** | StackExchange CAPTCHA 拦截 → 已标注 |
| A19 | 证实 | "Code that is warped out of shape solely to accomodate testing objectives"（含原拼写） |
| A27 | **修正（F-1）** | `while True:` / `if 0:` 属结构性 partial，**工具自动识别不标记**，无需 pragma；生成器表达式与条件循环才需 → RESEARCH 已改 |
| A36 | 证实 | pip `branch = true`，全文无 `fail_under` |
| A38 | 证实 | requests 仅 `omit`，未启用 branch |

† = IEEE/ACM 页面拦截，改经 Crossref API（同一 DOI 注册元数据）核验。

## 5. 项 3 + 5：一致性与裁定复核（主审完成）

1. **缺口计数** ✓：G-P060-1..12 恰 12 条 = P1×5（1/3/4/6/8）+ P2×5（2/5/7/9/10）+ P3×2（11/12）；抽查 G-P060-3/4/6 证据数字与 §3.1/§3.3 一致。
2. **与 P-059 无重复计数** ✓：G-P060-12 是对 P-059 登记项（DESIGN_p059 §17.2.4）的**收编**，P-059 已关闭，编号体系独立。
3. **B1/B2 目标自洽** ✓：B1 core ≥88%（从 86.46% 需 +1.54pp ≈ +140 行，与 35-45 例量级相符）；B2 services ≥85%（`market_gateway` 63 stmts 0%→80% 单项贡献 ~4.2pp，叠加 bus/worker/ws/api 可达）——偏雄心但可行（F-9）。
4. **U-P060-4**：语义清晰（同批次内独立 commit）；Step 3 需定义缺陷修复 commit 的门禁范围（F-8）。
5. **U-P060-5**：四条准入可执行（每条均有可判定的技术条件 + A17-A26 支撑）✓。
6. **U-P060-6 vs I10**：原口径含糊 → 已澄清为「单轮全量 ≤300s；分支覆盖独立轮单独计时」（F-7）。

## 6. 发现清单与处置

| ID | 级别 | 发现 | 处置 |
|---|---|---|---|
| F-1 | minor | A27 表述错误：`while True` 不需 pragma（结构性 partial 自动识别） | **已落 RESEARCH §9.1.3**（锚点行 + 落地规则 ③） |
| F-3 | minor | rebalance 定性修正：三触发器经 engine_plugins 注册但未选中；`RebalanceCalendar` 无生产引用；无「波动触发器」类 | **已落 RESEARCH §3.3 + G-P060-11** |
| F-4 | minor | agents 三模块「全仓零调用」过强（字符串清单 + 包内死路径互引） | **已落 RESEARCH §3.2 注 + G-P060-11** |
| F-7 | minor | I10「全量 ≤300s」未定义单轮/累计，与分支覆盖独立轮冲突 | **已落 RESEARCH §8 I10** |
| F-5 | note | `market_gateway` 测试零引用成立（read_text 非 import） | RESEARCH §3.2 注 ✓，无需行动 |
| F-6 | note | core 包两次运行 −5 行（86.52→86.46%），动态路径微差；总量 2dp 不变 | 记录在案；I8 棘轮以 2dp 快照为准 |
| F-8 | note | U-P060-4 修复 commit 的门禁范围未定义 | **移交 Step 3**：DESIGN 明确「缺陷修复 commit 复用 10 门禁全集」 |
| F-9 | note | B2 services ≥85% 偏雄心 | **移交 Step 3**：DESIGN 定稿时给出逐文件增量估算 |
| F-2 | note | 锚点可达性分层（A5/A11/A16 unreachable；A2-A4 Crossref 核验） | **已落 RESEARCH §9.1 可达性注记** |
| F-10 | note | 一致性子代理未产出结论，由主审替代 | **如实披露于 §1**；不影响判定独立性（锚点/映射由独立子代理完成） |

## 7. 结论

1. **E1 全部复现**（唯一偏差为 core −5 行、2dp 不变），静态映射 11/11 证实，锚点 9/13 原文证实 + 3 unreachable 标注 + 1 处修正。
2. **4 处修订已落 RESEARCH**（F-1/F-3/F-4/F-7），范围守卫 ✓（工作树零代码变更）。
3. **判定：PASS** → Step 3 DESIGN 可启动，输入 = RESEARCH（含修订）+ 本记录移交项（F-8/F-9）。
4. 证据文件（不入仓）：`%TEMP%\e1_step2.log`、`cov_a_step2.json`、`cov_b_step2.json`。
