# Walk-Forward回测框架实施计划

## 目标
实现真正的训练/验证/测试三期分离回测，与Agent蒸馏隔离机制集成，自动防止数据窥探。

## 架构
- WalkForwardSplitter: 将时间序列分割为多个train/val/test窗口
- WalkForwardEngine: 在每个窗口上运行回测，自动传递period参数
- 与现有Agent蒸馏隔离机制无缝集成

## 任务分解

### Task 1: WalkForwardSplitter窗口分割器
**文件:**
- 创建: `core/walk_forward.py`
- 测试: `tests/test_walk_forward.py`

**步骤:**
1. 实现固定窗口分割（rolling window）
2. 实现扩展窗口分割（expanding window）
3. 支持purge gap（防止训练-测试数据泄漏）
4. 编写测试验证分割正确性

### Task 2: WalkForwardEngine引擎
**文件:**
- 创建: `core/walk_forward_engine.py`
- 修改: `core/engine.py` (添加period传递)
- 测试: `tests/test_walk_forward_engine.py`

**步骤:**
1. 在每个窗口上初始化Agent（重置学习状态）
2. 训练期: 允许Agent在线学习
3. 验证期: 冻结Agent，调参
4. 测试期: 完全冻结，生成预测
5. 汇总所有窗口的测试结果

### Task 3: Agent集成
**文件:**
- 修改: `agents/guru_agent_v2.py`
- 修改: `agents/research_team_v2.py`
- 测试: `tests/test_walk_forward_integration.py`

**步骤:**
1. Agent在窗口切换时自动重置学习状态
2. 验证distillation_config在测试期生效
3. 确保belief冻结机制正确工作

### Task 4: 集成测试
**文件:**
- 测试: `tests/test_walk_forward_full.py`

**步骤:**
1. 使用demo_data运行完整Walk-Forward回测
2. 验证无数据窥探（测试期不使用训练期学习到的参数）
3. 验证结果汇总正确
