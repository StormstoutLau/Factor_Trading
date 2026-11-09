# P-010（`DataManager` 辅助数据缺失处理） · 调研文档

> **文档编号**: RESEARCH_p010_aux_defaults
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 1 完稿；Step 2 Review 结果见 §6
> **上游**: `docs/PROGRESS.md` §1.4 P-010（由 P-007 层 A D1 派生登记）；[IMPL_p007_mypy_layera.md](IMPL_p007_mypy_layera.md) §9 F-I7
> **下游**: [DESIGN_p010_aux_defaults.md](DESIGN_p010_aux_defaults.md) → [IMPL_p010_aux_defaults.md](IMPL_p010_aux_defaults.md) → [CHECKLIST_p010_aux_defaults.md](CHECKLIST_p010_aux_defaults.md)
> **档位**: T1（`core/data.py` 行为变更 + `filter/` 语义面验证）
> **证据时点**: 本仓读数 @ `e6ed18d`；解释器 Python 3.12.10

---

## 1. 问题定义

P-010 登记描述：「`DataManager` 辅助数据缺失时无安全默认值（行为缺口）」。来源是 P-007 层 A 发现 `core/data.py` 曾有两个同名 `_load_auxiliary_data`：

- 被覆盖的旧版本（原 L184-231）在文件缺失时设置安全默认值：停牌 `True` / 行业 `1` / ST `False` / 市值 `1e9`
- 生效版本（现 L264-291）在文件缺失时**直接跳过**，属性保持 `None`

P-007 只删除了死代码（行为不变），并把「行为缺口」登记为本项。本轮需回答三个问题：

1. 缺失数据时当前**真实行为**是什么（是否崩溃 / 是否静默降级）？
2. 旧版本的「安全默认值」是否**语义正确**、能否直接复制？
3. 真正的缺陷是「缺默认值」，还是别的（幂等性 / 类型契约）？

---

## 2. 本仓事实（E1/E3）

| ID | 事实 | 证据 |
|----|------|------|
| P1 | 生效版 `_load_auxiliary_data`（`core/data.py:264-291`）四个分支均为 `if path.exists(): load`，无 `else` 分支，无 `_loaded` 标记 | E3 @`e6ed18d` 读码 |
| P2 | 四个属性初始化为 `None`（L50-53）；`suspend`/`industry` 注解为 `pd.DataFrame`，`st`/`mktcap` 为 `Optional` | E3 @`e6ed18d` |
| P3 | `suspend` 属性：`if self._suspend_data is None: self._load_auxiliary_data()`，随后直接 return；`industry` 同构；`st`/`mktcap` 额外受 `cfg.st_file` / `cfg.mktcap_file` 真值门控 | E3 @`e6ed18d` L124-149 |
| P4 | **幂等性缺陷（实测）**：仅当 `st.pkl` 缺失时，每次访问 `.st` 都会重跑 `_load_auxiliary_data`，**重新读取已存在的 `suspend.pkl` 与 `industry.pkl`** | E1 探针：3 次访问 → `_load_and_align_data` **6 次**调用；100 次访问 → **206 次**、**144.90 ms** |
| P5 | **类型契约缺陷（实测）**：目录仅有 `close.pkl` 时 `dm.suspend is None` 为 **True**，但属性声明 `-> pd.DataFrame` | E1 探针（`tempfile` + `BacktestConfig(data_dir=...)`） |
| P6 | `preload_data()` 亦调用 `_load_auxiliary_data()`（L571），与属性访问叠加会再放大重复 IO | E3 @`e6ed18d` |
| P7 | 配置语义明确：`suspend_file: "1=停牌, 0=正常"`、`st_file: "1=ST, 0=正常"`、`mktcap_file: None`（可选） | E3 `core/config.py:339-342` |
| P8 | 旧版默认值：停牌 `pd.DataFrame(True, ...)`（全 1）、行业 `1`、ST `False`（全 0）、市值 `1e9` | E3 `git show 8082784:core/data.py`（原 L184-231） |
| P9 | **旧版停牌默认值语义错误**：按 P7，`1=停牌`；`universe_filter_clean._build_suspend_mask` 为 `self.dm.suspend == 0`，全 1 → 掩码全 False → **全市场被判定停牌**。旧版并非「安全」默认 | E3 `filter/universe_filter_clean.py:132-140` + P7/P8 |
| P10 | 消费方已全部做 `None` 兜底（不是崩溃）：`_build_suspend_mask` / `_build_st_mask` / `_build_next_day_tradable_mask` / `_build_market_cap_mask` / `_build_industry_mask` 均 `if ... is not None: ... else 全 True + warning`；`_build_limit_masks` 对 ST 兜底为全 0（非 ST 阈值） | E3 `filter/universe_filter_clean.py:132-287` |
| P11 | `factor.py` 的行业/市值中性化均以 `is not None` 门控，缺失即跳过 | E3 `core/factor.py:315,328` |
| P12 | 测试夹具只生成 7 个 pkl：close/open/high/low/stock_adj/suspend/industry，**不含 st/mktcap**；`suspend` 全 0、`industry` 全 1 | E3 `scripts/prepare_test_fixture.py:5-6,86-94` |
| P13 | 当前无任何测试直接实例化 `DataManager`（`tests/*.py` 对 `DataManager` 0 命中），缺失分支由引擎集成测试间接覆盖 | E1 `Grep tests/*.py` |
| P14 | mypy 对 `data.py` 现有 0 error（`-> pd.DataFrame` 返回 `Optional` 未被捕获，因 `_load_auxiliary_data` 为无注解函数） | E1 `mypy --explicit-package-bases core/data.py` → `Success` |
| P15 | 缺失 `st.pkl` 时 `universe_filter_clean` 的 3 处 `.st` 访问（L159-161 条件表达式含 2 次 + L191）均会触发 P4 的重复加载 | E3 读码 + P4 |

---

## 3. 缺陷分类

| ID | 类型 | 描述 | 级别 | 依据 |
|----|------|------|------|------|
| **D-1** | 真实缺陷（性能/副作用） | `_load_auxiliary_data` **非幂等**：单个可选文件缺失时，任意对缺失属性的访问都会重读全部已存在文件；引擎每次重建过滤器都会重复 IO | P2 | P4 / P6 / P15 |
| **D-2** | 真实缺陷（类型契约） | `suspend` / `industry` 声明 `-> pd.DataFrame`，实际可返回 `None`；mypy 因无注解调用而不报，形成对后续消费者的陷阱 | P2 | P2 / P5 / P14 |
| **D-3** | 行为缺口（有限） | `suspend` / `st` 在配置中为**默认必填**（`suspend.pkl` / `st.pkl`，且 `0=正常` 语义明确），缺失时无默认值，导致兜底逻辑分散在 5 处消费方、warning 重复 | P3 | P7 / P10 |
| **D-4** | 非缺陷（确认） | `industry` / `mktcap` 无可辩护默认值：行业编码无「中性值」，市值默认 `1e9` 会让 `min_market_cap` 过滤产生任意结果；消费方跳过过滤是正确行为 | — | P8 / P11 |

**关键结论**：P-010 登记时假设「旧版默认值是安全的」，实测**不成立**（P9 停牌默认值方向相反）。因此本批不能复制旧版默认值，必须按配置语义重建。

---

## 4. 影响面

| 消费方 | 使用字段 | 现有兜底 | 本批是否改动 |
|--------|----------|----------|--------------|
| `filter/universe_filter_clean.py` | `suspend` / `st` / `mktcap` / `industry` | 全 True + warning（ST 阈值兜底全 0） | **否** |
| `core/factor.py` | `industry` / `mktcap` | `is not None` 跳中性化 | **否** |
| `core/data.py::preload_data` | 四者 | 无（直接调用） | 否（受益于幂等） |
| 其余全仓 | — | `.suspend/.industry/.st/.mktcap` 无其他命中 | — |

> 影响面结论：本批是 `core/data.py` **内部**行为收敛；`filter/` 与 `factor.py` 零改动，掩码数值应与现状逐位一致。

---

## 5. 候选方案

| 方案 | 内容 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A（推荐）** | ① 加 `_aux_loaded` 幂等 guard；② `suspend`/`st` 缺失时给 `0` 值 DataFrame（`0=正常`）并 warning；③ `industry`/`mktcap` 保持 `None`，注解改 `Optional` | 语义与配置注释一致；消除重复 IO；类型契约诚实；消费方零改动 | `suspend`/`st` 的 warning 从消费方上移到数据层（净效果仍有一条） | ✅ 采纳 |
| B | 只加幂等 guard + 全部注解改 `Optional`，不给默认值 | 改动最小 | 未交付「安全默认值」；消费方 5 处兜底与重复 warning 保留 | 部分采纳（D-1/D-2 覆盖，D-3 未解） |
| C | 复制旧版四默认值（停牌 `True` / 行业 `1` / ST `False` / 市值 `1e9`） | 与历史一致 | **停牌语义反了**（P9）；`mktcap=1e9` 会与 `min_market_cap` 冲突；行业 `1` 无依据 | ❌ 拒绝 |
| D | 缺失时直接 `raise` | 早失败 | 辅助数据按设计是可选的（`mktcap_file=None`）；会打断现有夹具与 CI | ❌ 拒绝 |

---

## 6. Step 2 Review（独立 pass）

> 审查方式：逐条复算 P4/P5 探针、核对 P1-P15 行号与 `e6ed18d` 实际内容、检查影响面是否有遗漏的 `.st` 等属性消费者。

### 6.1 复算记录

| 项 | 复算方式 | 结果 |
|----|----------|------|
| P4 重复加载 | 探针：copy 7 个 pkl 到 temp，monkeypatch `_load_and_align_data` 计数，访问 `.st` 3 次 | **6 次**调用（每次 2：suspend + industry）✓ |
| P5 类型契约 | 探针：仅 `close.pkl` | `suspend is None == True` ✓ |
| P9 停牌语义 | 配置注释 `1=停牌` + `_build_suspend_mask` 的 `== 0` | 旧默认全 1 → 全停牌 ✓ |
| 影响面 | Grep `\.suspend\b|\.industry\b|\.st\b|\.mktcap\b` 全仓 | 消费方仅 2 文件 ✓ |

### 6.2 发现项

| ID | 级别 | 位置 | 问题 | 处置 |
|----|------|------|------|------|
| F-R1 | P3 | §3 D-3 | 初稿把 D-3 也列为「P2」，与 D-1/D-2 同级；但 D-3 有消费方兜底、无运行时错误，应为 P3 | 已降级为 P3（正文 D-3 行） |
| F-R2 | P3 | §2 P4 | 初稿只写「重复加载」，未量化；审阅要求给出可重放读数 | 已补 `3 次 → 6 次`、`100 次 → 206 次 / 144.90 ms` |
| F-R3 | P3 | §5 方案 B | 初稿写「B 覆盖 D-1/D-2」，未说明 D-3 未解，易误判等价 | 已在缺点列显式标注 D-3 未解 |

### 6.3 结论

- P0/P1：**0**
- P2：**0**（D-1/D-2 是缺陷分级，不是 Review 发现）
- P3：**3**（F-R1~F-R3，均已就地修正）
- 判定：事实链完整、方案对比可审计，进入 Step 3 设计。
