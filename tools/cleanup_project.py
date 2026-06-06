#!/usr/bin/env python3
"""
项目文件清理脚本

清理范围:
1. data_analysis/ 中的临时分析脚本
2. test/ 中的临时测试文件  
3. __pycache__/ 缓存目录
4. 旧的报告文件(.md)

保留的核心文件:
- 核心模块: config.py, data.py, engine.py, factor.py 等
- README.md, requirements.txt
- 主要文档: ARCHITECTURE_ANALYSIS.md, REFACTORING_SUMMARY.md
"""

import os
import shutil
from pathlib import Path
import sys


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent


def get_files_to_cleanup():
    """定义需要清理的文件列表"""
    root = get_project_root()
    
    # 1. 需要删除的分析脚本 (data_analysis/)
    analysis_scripts_to_remove = [
        # 临时分析脚本
        "align_index_to_real.py",
        "analyze_all_dates.py",
        "analyze_backtest_results.py",
        "analyze_data_adapter.py",
        "analyze_datamanager_matching.py",
        "analyze_index_constituents.py",
        "analyze_industry_mapping.py",
        "analyze_list_date.py",
        "analyze_list_date_alignment.py",
        "analyze_market_data.py",
        "analyze_st_data_sources.py",
        "analyze_stock_name_detailed.py",
        "analyze_stock_suspended.py",
        "analyze_suspend_factor_timing.py",
        "calc_hs300_simple.py",
        "calc_index_market_value.py",
        "check_suspend_data.py",
        "convert_factor_csv_to_pkl.py",
        "download_csi500_etf.py",
        "download_st_data_akshare.py",
        "extract_and_analyze.py",
        "factor_alignment_integration.py",
        "factor_date_alignment.py",
        "generate_backtest_report.py",
        "index_alignment_analysis.py",
        "normalize_indices.py",
        "pending_compatibility_analysis.md",
        "predictive_listing_filter.py",
        "process_auxiliary_data.py",
        "quick_backtest_test.py",
        "run_backtest_skip_suspend.py",
        "test_actual_data_alignment.py",
        "test_factor_alignment.py",
        "test_pending_compatibility.py",
        "test_real_factor.py",
        "test_suspend_align.py",
        "validate_returns_consistency.py",
        "verify_engine_integration.py",
        "verify_index_calculation.py",
        "visualize_data.py",
        # 报告文件
        "all_dates_structure_analysis.md",
        "datamanager_data_matching_strategy.md",
        "factor_alignment_report.md",
        "factor_test_report.md",
        "list_date_analysis_report.md",
        "returns_validation_report.md",
        "st_data_generation_report.md",
        "st_data_source_analysis.md",
        "stock_name_analysis_report.md",
        "suspend_factor_timing_analysis.md",
    ]
    
    # 2. 根目录下旧的总结文件
    old_summary_files = [
        "CLEANUP_SUMMARY.md",
        "TEST_SUMMARY.md",
        "universe_filter_analysis_summary.md",
        "universe_filter_cleanup_summary.md",
    ]
    
    # 3. __pycache__ 目录
    pycache_dirs = [
        root / "__pycache__",
        root / "data_analysis" / "__pycache__",
        root / "test" / "__pycache__",
        root / "filter" / "__pycache__",
    ]
    
    # 4. test/ 目录中的临时测试文件
    test_files_to_remove = []
    test_dir = root / "test"
    if test_dir.exists():
        for f in test_dir.iterdir():
            if f.is_file() and f.name not in ["__init__.py", "conftest.py"]:
                test_files_to_remove.append(f)
    
    return {
        "analysis_scripts": [(root / "data_analysis" / f, f) for f in analysis_scripts_to_remove],
        "old_summaries": [(root / f, f) for f in old_summary_files],
        "pycache_dirs": [(d, str(d)) for d in pycache_dirs],
        "test_files": [(f, f.name) for f in test_files_to_remove],
    }


def cleanup_files(dry_run=True):
    """执行清理"""
    files_to_cleanup = get_files_to_cleanup()
    
    print("="*70)
    print("项目文件清理" + " (模拟运行)" if dry_run else " (实际执行)")
    print("="*70)
    
    total_files = 0
    total_size = 0
    
    # 1. 清理分析脚本
    print("\n【1】清理 data_analysis/ 临时分析脚本...")
    for filepath, filename in files_to_cleanup["analysis_scripts"]:
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  {'[将删除]' if not dry_run else '[将删除]'} {filename} ({size/1024:.1f} KB)")
            total_files += 1
            total_size += size
            if not dry_run:
                filepath.unlink()
    
    # 2. 清理旧的总结文件
    print("\n【2】清理根目录旧总结文件...")
    for filepath, filename in files_to_cleanup["old_summaries"]:
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  {'[将删除]' if not dry_run else '[将删除]'} {filename} ({size/1024:.1f} KB)")
            total_files += 1
            total_size += size
            if not dry_run:
                filepath.unlink()
    
    # 3. 清理 __pycache__
    print("\n【3】清理 __pycache__ 缓存目录...")
    for dirpath, dirname in files_to_cleanup["pycache_dirs"]:
        if dirpath.exists():
            size = sum(f.stat().st_size for f in dirpath.rglob('*') if f.is_file())
            file_count = len(list(dirpath.rglob('*')))
            print(f"  {'[将删除]' if not dry_run else '[将删除]'} {dirname} ({file_count} 文件, {size/1024:.1f} KB)")
            total_files += file_count
            total_size += size
            if not dry_run:
                shutil.rmtree(dirpath)
    
    # 4. 清理 test/ 临时文件
    print("\n【4】清理 test/ 临时测试文件...")
    for filepath, filename in files_to_cleanup["test_files"]:
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"  {'[将删除]' if not dry_run else '[将删除]'} {filename} ({size/1024:.1f} KB)")
            total_files += 1
            total_size += size
            if not dry_run:
                filepath.unlink()
    
    # 5. 检查空目录
    print("\n【5】检查空目录...")
    root = get_project_root()
    empty_dirs = []
    for dirpath in [root / "demo", root / "debug"]:
        if dirpath.exists() and not any(dirpath.iterdir()):
            empty_dirs.append(dirpath)
            print(f"  [空目录] {dirpath.name}")
    
    print("\n" + "="*70)
    print(f"统计: {total_files} 个文件/目录, 总计 {total_size/1024/1024:.2f} MB")
    print("="*70)
    
    if dry_run:
        print("\n这是模拟运行，使用 --execute 参数执行实际清理:")
        print(f"  python {Path(__file__).name} --execute")
    else:
        print("\n[OK] 清理完成!")
        if empty_dirs:
            print(f"\n注意: 发现 {len(empty_dirs)} 个空目录，可手动删除:")
            for d in empty_dirs:
                print(f"  - {d}")
    
    return total_files, total_size


def main():
    """主函数"""
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("\n[注意] 模拟运行模式 - 不会实际删除文件\n")
    
    cleanup_files(dry_run=dry_run)


if __name__ == "__main__":
    main()
