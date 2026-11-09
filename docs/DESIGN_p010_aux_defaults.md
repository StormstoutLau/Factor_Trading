# P-010（`DataManager` 辅助数据缺失处理） · 设计文档

> **文档编号**: DESIGN_p010_aux_defaults
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿；Step 4 Review 结果见 §6
> **上游**: [RESEARCH_p010_aux_defaults.md](RESEARCH_p010_aux_defaults.md)（Step 2 通过，P1-P15 / D-1~D-4）
> **下游**: [IMPL_p010_aux_defaults.md](IMPL_p010_aux_defaults.md) → [CHECKLIST_p010_aux_defaults.md](CHECKLIST_p010_aux_defaults.md)
> **证据时点**: 本仓读数 @ `e6ed18d`；解释器 Python 3.12.10
> **档位**: T1（`core/data.py` 行为变更 + 1 个新测试文件）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | 幂等性（D-1） | `DataManager.__init__` 增加 `self._aux_loaded: bool = False`；`_load_auxiliary_data` 首行 `if self._aux_loaded: return`，末尾置 `True` | P4/P6/P15 |
| **D2** | 停牌/ST 默认值（D-3） | 文件缺失时构造 `pd.DataFrame(0, index=trade_dates, columns=stock_codes)`（配置约定 `0=正常`）并 `logger.warning` | P7/P9 |
| **D3** | 行业/市值（D-4） | **保持 `None`**，不构造默认值；`industry` 属性注解改为 `Optional[pd.DataFrame]`，`suspend` 保持非 Optional | P8/P11 |
| **D4** | 消费方 | `filter/universe_filter_clean.py` 与 `core/factor.py` **零改动**；现有 `is not None` 分支保留（对 `industry`/`mktcap` 仍生效） | P10/P11 |
| **D5** | 测试 | 新增 `tests/test_data_aux_defaults.py` **4 项**；510 → **514** | P12/P13 |
| **D6** | 已知行为变更 | 停牌数据缺失时 `_build_next_day_tradable_mask` 的**最后一天**由 True 变为 False（有数据路径的既有语义）；其余掩码数值不变 | P10 |
| **D7** | 幂等边界 | 首次加载后新出现的辅助文件**不会**被自动重载（需新建 `DataManager`）；在 docstring 中声明 | P1 |

---

## 2. 逐项决策与依据

### D1 幂等 guard

**现状**：`_load_auxiliary_data` 无「已加载」状态；`st` 属性在 `st.pkl` 缺失时每次访问都重入，重读 `suspend.pkl` + `industry.pkl`（实测 3 次访问 → 6 次读盘；100 次 → 206 次 / 144.90 ms）。

**决定**：

```python
# __init__ 追加
self._aux_loaded: bool = False

def _load_auxiliary_data(self):
    if self._aux_loaded:
        return
    ...
    self._aux_loaded = True
```

**理由**：辅助数据在一次回测生命周期内是静态的；守卫是 O(1) 布尔判断，语义与 `_prices` 的 dict 缓存一致。**不做**文件级 mtime 失效（无需求，且会引入 stat 调用）。

**被拒方案**：`functools.lru_cache` 装饰方法（`self` 可哈希但缓存跨实例泄漏、且无参无法区分实例状态）；逐文件 `loaded` 标记（4 个布尔，冗余）。

### D2 停牌/ST 默认值按 `0=正常`

**依据**：`core/config.py:339/341` 明确 `1=停牌/ST, 0=正常`；`universe_filter_clean` 的掩码均以 `== 0` 判定可交易/非 ST。

**决定**：

```python
self._suspend_data = pd.DataFrame(0, index=self._trade_dates, columns=self._stock_codes)
self._st_data = pd.DataFrame(0, index=self._trade_dates, columns=self._stock_codes)
```

并在构造前 `logger.warning(f"停牌数据文件不存在: {path}，按 0=正常 处理")`（ST 同）。

**被拒方案（关键）**：复制旧版 `pd.DataFrame(True, ...)`——按 P9 等于「全 1 = 全停牌」，会让 `== 0` 掩码全 False，**全市场不可交易**。旧版默认值方向错误，不得复用。

### D3 行业/市值保持 `None`

**依据**：行业编码无中性值（任意常数都会与 `exclude_industries` 产生任意交互）；`mktcap` 默认 `1e9` 会与用户配置的 `min_market_cap` 冲突（可能把全部股票过滤掉或全部放行）。两者消费方均已 `is not None` 跳过（P10/P11），`None` 即正确语义。

**决定**：保持 `None` + warning；`industry` 注解 `-> Optional[pd.DataFrame]`（诚实契约）；`suspend` 因 D2 后恒为 DataFrame，注解不变。

### D4 消费方零改动

`universe_filter_clean` 的 `else` 分支对 `suspend`/`st` 将变得不可达（属性不再返回 None），但保留不删：① `industry`/`mktcap` 仍走 else；② 删除会扩大 diff 且破坏对自定义 `IDataManager` 实现的兼容（接口层仍可能返回 None）。

### D5 测试设计（4 项）

| ID | 测试 | 构造 | 断言 |
|----|------|------|------|
| T1 | `test_suspend_st_default_zero_frames` | `tmp_path` 仅写 `close.pkl`（50×100 随机价） | `suspend`/`st` 为 DataFrame、`dtype` 可比较、全 0、shape `(100, 50)`；`industry`/`mktcap is None` |
| T2 | `test_auxiliary_load_is_idempotent` | `tmp_path` 仅写 `close.pkl` + `suspend.pkl`（无 `industry.pkl`/`st.pkl`）；monkeypatch `_load_and_align_data` 计数 | 访问 `.industry`（保持 None）**3 次**后计数 **== 1**；guard 关闭模拟时实测 **3** |
| T3 | `test_existing_suspend_not_overwritten` | 写 `close.pkl` + `suspend.pkl`（某格 = 1） | `dm.suspend` 保留该 1，不被默认值覆盖 |
| T4 | `test_missing_aux_logs_warning` | 仅 `close.pkl`；`caplog` | 同时命中「停牌数据文件不存在」与「ST数据文件不存在」 |

**禁止**：用 `pytest.raises` / `monkeypatch` 改断言放宽；测试必须能在修复前失败（T1/T2/T4 在修复前分别为 `None` / 计数 **3** / 无数据层 warning）。

### D6 已知行为变更（必须声明）

| 场景 | 现状 | 本批后 | 判定 |
|------|------|--------|------|
| `suspend.pkl` 缺失 → `_build_next_day_tradable_mask` 最后一天 | True（None 兜底全 True） | **False**（默认 0-frame 走有数据路径，末行置 False） | 更正确（末日无「次日」）；其余日期数值不变 |
| `suspend.pkl` 缺失 → `_build_suspend_mask` | 全 True | 全 True | 不变 |
| `st.pkl` 缺失 → `_build_st_mask` / 涨跌停阈值 | 全 True / 非 ST 阈值 | 全 True / 非 ST 阈值 | 不变 |
| 仓库夹具（suspend/industry 均存在） | — | — | **零变化**（既有 510 项全绿 + 本批新增 4 项 = 514） |

### D7 幂等边界

首次加载后新增文件不会自动重载。声明在 `_load_auxiliary_data` docstring；回测场景数据目录只读，可接受。

---

## 3. 验证契约（V1-V8）

| ID | 断言 | 命令 | 期望 |
|----|------|------|------|
| V1 | 类型不劣化 | `mypy --explicit-package-bases core` | **`93 errors in 3 files`**（与基线逐字一致） |
| V2 | 全量测试 | `pytest -q` | **`514 passed`** |
| V3 | 新测试 | `pytest tests/test_data_aux_defaults.py -q` | **`4 passed`** |
| V4 | 缺失默认值 | 探针 / T1 | `suspend`、`st` 为全 0 DataFrame |
| V5 | Optional 契约 | T1 | `industry`、`mktcap` 为 `None` |
| V6 | 幂等 | T2 | 3 次访问 → `_load_and_align_data` **2 次** |
| V7 | 不覆盖真实数据 | T3 | 既有 1 值保留 |
| V8 | 格式与边界 | `black --check .`；`git diff --stat -- filter/ core/factor.py` | **137 unchanged**（136+1 新测试）；消费方 **diff 空** |

---

## 4. 风险与限制

| ID | 风险 | 影响 | 缓解 |
|----|------|------|------|
| R1 | D6 的末行 False 属行为变更 | 缺失停牌数据的用户，最后一天不可买入 | 语义正确（末日无次日）；在 CHANGELOG「Changed」显式声明 |
| R2 | `_aux_loaded` 后文件更新不重载 | 长驻进程热更新数据会读到旧值 | docstring 声明；回测为一次性进程，无实际影响 |
| R3 | 默认 0-frame 掩盖「数据缺失」 | 用户可能忽略 warning | 每次缺失均 `logger.warning`（非 debug），且 T4 断言日志存在 |
| R4 | `assert` 不在本批使用 | — | 默认值构造前用显式 `if ... is None: return` 处理不可达分支，不引入 assert |

---

## 5. 变更面

| 文件 | 改动 | 行数量级 |
|------|------|----------|
| `core/data.py` | `_aux_loaded` 初始化 + guard + 两个默认值分支 + 两处 warning + `industry` 注解 | ±30 |
| `tests/test_data_aux_defaults.py` | 新增 4 项测试 | +80 |
| 四文档 + `docs/PROGRESS.md` + `CHANGELOG.md` | 台账 | — |
| `filter/`、`core/factor.py`、`core/config.py` | **零改动** | 0 |

---

## 6. Step 4 Review（独立 pass）

> 审查方式：核对 D1-D7 与 RESEARCH P1-P15 / D-1~D-4 的覆盖；复算 D6 的各掩码分支；检查测试 T1-T4 在修复前是否真红；检查是否引入对 `filter/` 的隐式依赖变更。

### 6.1 覆盖核对

| RESEARCH 结论 | DESIGN 决策 | 覆盖 |
|---------------|-------------|------|
| D-1 幂等缺陷 | D1 + D7 | ✅ |
| D-2 类型契约 | D3（`industry` → Optional；`suspend` 因 D2 恒非 None） | ✅ |
| D-3 停牌/ST 缺默认 | D2 | ✅ |
| D-4 行业/市值无可辩护默认 | D3 | ✅ |
| P10 消费方兜底 | D4（零改动） | ✅ |
| P12 夹具无 st/mktcap | D5 T1/T2/T4 构造 | ✅ |

### 6.2 发现项

| ID | 级别 | 位置 | 问题 | 处置 |
|----|------|------|------|------|
| F-D1 | P2 | D2/D6 | 初稿只写「给 0 默认值」，**遗漏了 `_build_next_day_tradable_mask` 末行 True→False 的行为变更**（有数据路径会置末行 False）；若不声明，会被 ADD Phase 4 判为未披露的行为改动 | 已补 D6 行为变更表并进 R1/CHANGELOG 口径 |
| F-D2 | P3 | D3 | 初稿未说明为何 `suspend` 注解不改 Optional，易与 `industry` 处理不一致 | 已补「D2 后恒为 DataFrame」理由 |
| F-D3 | P3 | D5 T2 | 初稿写「删除 st.pkl」——夹具本就不含 st.pkl，表述会误导实施者去复制不存在的文件 | 已改为「复制 7 个夹具 pkl（本就不含 st.pkl）」 |

### 6.3 结论

- P0/P1：**0**
- P2：**1**（F-D1，已回写 D6）
- P3：**2**（F-D2/F-D3，已就地修正）
- 判定：设计可实施，进入 Step 5。
