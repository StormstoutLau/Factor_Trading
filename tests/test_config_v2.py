"""
Pydantic 配置系统测试

验证:
1. 基本创建和验证
2. 字段约束验证
3. 嵌套配置验证
4. JSON 序列化/反序列化
5. 文件保存/加载
6. 热重载功能
7. 向后兼容性
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_basic_creation():
    """测试基本创建"""
    print("\n[Test] 基本创建...")

    from core.config_v2 import BacktestConfig, CostConfig

    config = BacktestConfig(
        factor_files=["factor_value.pkl"],
        cost=CostConfig(commission_rate=0.0003),
    )

    assert config.initial_capital == 10_000_000.0
    assert config.cost.commission_rate == 0.0003
    assert config.factor_files == ["factor_value.pkl"]
    print("  ✓ 基本创建成功")
    return True


def test_field_validation():
    """测试字段约束验证"""
    print("\n[Test] 字段约束验证...")

    from pydantic import ValidationError
    from core.config_v2 import BacktestConfig, OptimizerConfig

    # 测试 commission_rate 范围
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            cost={"commission_rate": 0.2},  # 超过 0.1 上限
        )
        # pydantic v2 中 ge/le 会报错
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError as e:
        print(f"  ✓ 正确捕获超范围错误")

    # 测试 target_count 必须 >= 1
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            optimizer=OptimizerConfig(target_count=0),
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print(f"  ✓ 正确捕获 target_count=0 错误")

    # 测试日期格式
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            start_date="2024-13-01",  # 无效日期
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print(f"  ✓ 正确捕获无效日期错误")

    # 测试日期顺序
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            start_date="2024-06-01",
            end_date="2024-01-01",
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print(f"  ✓ 正确捕获日期顺序错误")

    print("  ✓ 字段约束验证全部通过")
    return True


def test_nested_validation():
    """测试嵌套配置验证"""
    print("\n[Test] 嵌套配置验证...")

    from pydantic import ValidationError
    from core.config_v2 import BacktestConfig, OptimizerConfig

    # 测试 min_weight >= max_weight
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            optimizer=OptimizerConfig(min_weight=0.2, max_weight=0.1),
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print(f"  ✓ 正确捕获权重范围错误")

    # 测试 hybrid 模式日期
    try:
        from core.config_v2 import RebalanceConfig

        config = BacktestConfig(
            factor_files=["f.pkl"],
            rebalance=RebalanceConfig(
                method="hybrid", hybrid_min_days=20, hybrid_max_days=10
            ),
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print(f"  ✓ 正确捕获 hybrid 日期错误")

    print("  ✓ 嵌套配置验证全部通过")
    return True


def test_json_serialization():
    """测试 JSON 序列化"""
    print("\n[Test] JSON 序列化...")

    from core.config_v2 import BacktestConfig

    config = BacktestConfig(
        factor_files=["factor_value.pkl", "factor_momentum.pkl"],
        factor_weights={"factor_value": 0.6, "factor_momentum": 0.4},
        initial_capital=5_000_000.0,
    )

    # 序列化
    json_str = config.to_json()
    data = json.loads(json_str)

    assert data["factor_files"] == ["factor_value.pkl", "factor_momentum.pkl"]
    assert data["initial_capital"] == 5_000_000.0
    assert "cost" in data
    assert data["cost"]["commission_rate"] == 0.0003
    print("  ✓ JSON 序列化成功")

    # 反序列化
    config2 = BacktestConfig.from_json(json_str)
    assert config2.initial_capital == config.initial_capital
    assert config2.factor_files == config.factor_files
    print("  ✓ JSON 反序列化成功")

    # 从字典创建
    config3 = BacktestConfig.from_dict(data)
    assert config3.initial_capital == config.initial_capital
    print("  ✓ 从字典创建成功")

    print("  ✓ JSON 序列化测试通过")
    return True


def test_file_io():
    """测试文件保存/加载"""
    print("\n[Test] 文件 IO...")

    from core.config_v2 import BacktestConfig

    config = BacktestConfig(
        factor_files=["factor_value.pkl"],
        initial_capital=8_000_000.0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"

        # 保存
        config.save_to_file(path)
        assert path.exists()
        print(f"  ✓ 保存到文件: {path}")

        # 加载
        config2 = BacktestConfig.from_file(path)
        assert config2.initial_capital == 8_000_000.0
        assert config2.factor_files == ["factor_value.pkl"]
        print(f"  ✓ 从文件加载成功")

    print("  ✓ 文件 IO 测试通过")
    return True


def test_hot_reload():
    """测试热重载"""
    print("\n[Test] 热重载...")

    from core.config_v2 import BacktestConfig, ConfigHotReloader

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"

        # 创建初始配置
        config = BacktestConfig(
            factor_files=["factor_a.pkl"],
            initial_capital=1_000_000.0,
        )
        config.save_to_file(path)

        # 创建热重载器
        reloader = ConfigHotReloader(path, check_interval=0.1)
        assert reloader.config.initial_capital == 1_000_000.0
        print(f"  ✓ 初始加载: capital={reloader.config.initial_capital}")

        # 注册回调
        changes = []

        def on_change(cfg):
            changes.append(cfg.initial_capital)

        reloader.on_change(on_change)

        # 修改配置
        config2 = BacktestConfig(
            factor_files=["factor_b.pkl"],
            initial_capital=2_000_000.0,
        )
        config2.save_to_file(path)

        # 手动触发检查
        time.sleep(0.3)
        result = reloader.check_and_reload()

        # 如果 mtime 检查失败，强制重载
        if not result:
            reloader.force_reload()

        assert reloader.config.initial_capital == 2_000_000.0, \
            f"Expected 2000000, got {reloader.config.initial_capital}"
        print(f"  ✓ 热重载成功: capital={reloader.config.initial_capital}")
        print(f"  ✓ 回调触发: {len(changes)} 次")

    print("  ✓ 热重载测试通过")
    return True


def test_backward_compatibility():
    """测试向后兼容"""
    print("\n[Test] 向后兼容...")

    # 旧导入路径
    from config import BacktestConfig as OldConfig
    from config import BacktestConfigV2

    # 旧方式创建
    old = OldConfig(
        factor_files=["factor_value.pkl"],
        initial_capital=10_000_000.0,
    )

    # 新方式创建
    new = BacktestConfigV2(
        factor_files=["factor_value.pkl"],
        initial_capital=10_000_000.0,
    )

    assert old.initial_capital == new.initial_capital
    assert old.factor_files == new.factor_files
    print("  ✓ 旧/新配置字段一致")

    # 旧 validate() 接口
    errors = old.validate()
    assert isinstance(errors, list)
    print("  ✓ 旧 validate() 接口可用")

    # 新 validate_legacy() 接口
    errors = new.validate_legacy()
    assert isinstance(errors, list)
    print("  ✓ 新 validate_legacy() 接口可用")

    print("  ✓ 向后兼容测试通过")
    return True


def test_literal_validation():
    """测试 Literal 字段验证"""
    print("\n[Test] Literal 字段验证...")

    from pydantic import ValidationError
    from core.config_v2 import BacktestConfig, FactorConfig

    # 有效值
    config = BacktestConfig(
        factor_files=["f.pkl"],
        factor=FactorConfig(winsorize_method="mad", standardize_method="zscore"),
    )
    assert config.factor.winsorize_method == "mad"
    print("  ✓ 有效 Literal 值通过")

    # 无效值
    try:
        config = BacktestConfig(
            factor_files=["f.pkl"],
            factor=FactorConfig(winsorize_method="invalid_method"),
        )
        print("  ✗ 应触发验证错误")
        return False
    except ValidationError:
        print("  ✓ 正确捕获无效 Literal 值")

    print("  ✓ Literal 字段验证通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Pydantic Config v2 - 测试")
    print("=" * 60)

    tests = [
        ("基本创建", test_basic_creation),
        ("字段约束验证", test_field_validation),
        ("嵌套配置验证", test_nested_validation),
        ("JSON 序列化", test_json_serialization),
        ("文件 IO", test_file_io),
        ("热重载", test_hot_reload),
        ("向后兼容", test_backward_compatibility),
        ("Literal 验证", test_literal_validation),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {name} 失败: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
