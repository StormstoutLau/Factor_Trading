#!/usr/bin/env python3
"""
Factor Trading v3.2 — CLI Runner
================================

Command-line interface for the Factor Trading framework.

Usage:
    python cli.py run              # Run a single backtest
    python cli.py test             # Run all tests
    python cli.py analyze          # Analyze backtest results
    python cli.py info             # Show system information
    python cli.py dashboard        # Launch Streamlit dashboard
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def cmd_run(args: argparse.Namespace) -> None:
    """Run a single backtest."""
    print("=" * 70)
    print("  Factor Trading v3.2 — Backtest Runner")
    print("=" * 70)

    try:
        from core.config import BacktestConfig, FactorConfig, OptimizerConfig, RebalanceConfig, CostConfig
        from core.engine import BacktestEngine

        data_dir = args.data_dir or "./demo_data"
        config = BacktestConfig(
            data_dir=Path(data_dir),
            factor_files=args.factors.split(",") if args.factors else ["factor_value.pkl"],
            factor_weights=None,
            factor=FactorConfig(
                winsorize_method=args.winsorize,
                standardize_method=args.standardize,
                fill_method=args.fill,
                neutralize=not args.no_neutralize,
            ),
            optimizer=OptimizerConfig(
                method=args.optimizer,
                target_count=args.target_count,
            ),
            rebalance=RebalanceConfig(
                method="fixed",
                frequency=args.rebalance,
            ),
            cost=CostConfig(
                commission_rate=args.commission,
                stamp_tax_rate=0.001,
                slippage_pct=0.001,
            ),
            initial_capital=args.capital,
            start_date=args.start_date,
            end_date=args.end_date,
        )

        print(f"\n  Data Dir:    {data_dir}")
        print(f"  Factors:     {config.factor_files}")
        print(f"  Capital:     ¥{config.initial_capital:,.0f}")
        print(f"  Period:      {config.start_date} ~ {config.end_date}")
        print(f"  Optimizer:   {args.optimizer} (top {args.target_count})")
        print(f"  Rebalance:   {args.rebalance}")
        print(f"  Winsorize:   {args.winsorize}")
        print(f"  Neutralize:  {not args.no_neutralize}")
        print()

        engine = BacktestEngine(config)
        engine.setup()

        print(f"  Trade dates: {len(engine.dm.trade_dates)}")
        print(f"  Date range:  {engine.dm.trade_dates[0]} ~ {engine.dm.trade_dates[-1]}")
        print("\n  Running backtest...")

        results = engine.run()

        pv = results.get("portfolio_value")
        if pv is not None and len(pv) > 0:
            import pandas as pd
            import numpy as np

            total_return = (pv.iloc[-1] / pv.iloc[0] - 1) * 100
            days = len(pv)
            annual_return = total_return * (252 / days)
            cummax = pv.cummax()
            max_dd = ((pv - cummax) / cummax).min() * 100
            daily_ret = pv.pct_change().dropna()
            annual_vol = daily_ret.std() * np.sqrt(252) * 100
            sharpe = annual_return / annual_vol if annual_vol > 0 else 0

            print("\n" + "=" * 50)
            print("  BACKTEST RESULTS")
            print("=" * 50)
            print(f"  Total Return:   {total_return:+.2f}%")
            print(f"  Annual Return:  {annual_return:+.2f}%")
            print(f"  Annual Vol:     {annual_vol:.2f}%")
            print(f"  Sharpe Ratio:   {sharpe:.2f}")
            print(f"  Max Drawdown:   {max_dd:.2f}%")
            print(f"  Trading Days:   {days}")
            print(f"  Final Value:    ¥{pv.iloc[-1]:,.0f}")
            print("=" * 50)

            # Save results
            if args.output:
                result_df = pd.DataFrame({
                    "date": pv.index,
                    "portfolio_value": pv.values,
                })
                result_df.to_csv(args.output, index=False)
                print(f"\n  Results saved to: {args.output}")
        else:
            print("\n  Backtest failed: no portfolio value data.")

    except FileNotFoundError as e:
        print(f"\n  Error: Data file not found — {e}")
        print(f"  Tip: Place data files in '{data_dir}' or use --data-dir.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  Error: {e}")
        sys.exit(1)


def cmd_test(args: argparse.Namespace) -> None:
    """Run test suite."""
    import subprocess

    print("=" * 70)
    print("  Factor Trading v3.2 — Test Runner")
    print("=" * 70)

    pytest_args = ["pytest", "tests/", "-q", "--tb=short"]
    if args.verbose:
        pytest_args = ["pytest", "tests/", "-v", "--tb=short"]
    if args.coverage:
        pytest_args.extend(["--cov=core", "--cov=agents", "--cov-report=term-missing"])

    print(f"\n  Running: {' '.join(pytest_args)}\n")
    result = subprocess.run(pytest_args, cwd=str(_project_root))
    sys.exit(result.returncode)


def cmd_analyze(args: argparse.Namespace) -> None:
    """Analyze backtest results."""
    import pandas as pd
    import numpy as np

    results_path = Path(args.results)
    if not results_path.exists():
        print(f"Error: Results file not found: {results_path}")
        sys.exit(1)

    df = pd.read_csv(results_path)
    if "portfolio_value" not in df.columns:
        print("Error: CSV must contain 'portfolio_value' column.")
        sys.exit(1)

    pv = df.set_index("date")["portfolio_value"] if "date" in df.columns else df["portfolio_value"]
    pv = pd.Series(pv.values) if not isinstance(pv, pd.Series) else pv

    total_return = (pv.iloc[-1] / pv.iloc[0] - 1) * 100
    days = len(pv)
    annual_return = total_return * (252 / days)
    cummax = pv.cummax()
    max_dd = ((pv - cummax) / cummax).min() * 100
    daily_ret = pv.pct_change().dropna()
    annual_vol = daily_ret.std() * np.sqrt(252) * 100
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    sortino = annual_return / (daily_ret[daily_ret < 0].std() * np.sqrt(252)) if len(daily_ret[daily_ret < 0]) > 0 else 0
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
    win_rate = (daily_ret > 0).sum() / len(daily_ret) * 100

    print("=" * 60)
    print("  PERFORMANCE ANALYSIS")
    print("=" * 60)
    print(f"  Total Return:     {total_return:+.2f}%")
    print(f"  Annual Return:    {annual_return:+.2f}%")
    print(f"  Annual Volatility:{annual_vol:.2f}%")
    print(f"  Sharpe Ratio:     {sharpe:.2f}")
    print(f"  Sortino Ratio:    {sortino:.2f}")
    print(f"  Calmar Ratio:     {calmar:.2f}")
    print(f"  Max Drawdown:     {max_dd:.2f}%")
    print(f"  Win Rate:         {win_rate:.1f}%")
    print(f"  Trading Days:     {days}")
    print(f"  Start Value:      ¥{pv.iloc[0]:,.0f}")
    print(f"  Final Value:      ¥{pv.iloc[-1]:,.0f}")
    print("=" * 60)


def cmd_info(args: argparse.Namespace) -> None:
    """Show system information."""
    import platform
    import importlib.metadata
    from datetime import datetime

    print("=" * 60)
    print("  Factor Trading v3.2 — System Info")
    print("=" * 60)
    print(f"  Python:       {platform.python_version()}")
    print(f"  Platform:     {platform.system()} {platform.release()}")
    print(f"  Time:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Core module count
    core_dir = _project_root / "core"
    if core_dir.exists():
        py_files = list(core_dir.glob("*.py"))
        print(f"  Core Modules: {len(py_files)}")

    # Test count
    tests_dir = _project_root / "tests"
    if tests_dir.exists():
        test_files = list(tests_dir.glob("test_*.py"))
        print(f"  Test Files:   {len(test_files)}")

    # Key deps
    deps = ["numpy", "pandas", "scipy", "cvxpy", "duckdb", "pydantic", "matplotlib"]
    print(f"  Dependencies:")
    for dep in deps:
        try:
            ver = importlib.metadata.version(dep)
            print(f"    {dep:<15} {ver}")
        except importlib.metadata.PackageNotFoundError:
            print(f"    {dep:<15} NOT INSTALLED")

    print("=" * 60)


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Launch Streamlit dashboard."""
    import subprocess

    dashboard_path = _project_root / "web" / "streamlit_app" / "main.py"
    if not dashboard_path.exists():
        print(f"Error: Dashboard not found: {dashboard_path}")
        sys.exit(1)

    print(f"  Launching Streamlit Dashboard...")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"  Press Ctrl+C to stop\n")

    result = subprocess.run(
        ["streamlit", "run", str(dashboard_path), "--server.port", str(args.port)],
        cwd=str(_project_root),
    )
    sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Factor Trading v3.2 — CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py run --factors factor_value.pkl
  python cli.py test --verbose
  python cli.py analyze --results output/portfolio.csv
  python cli.py info
  python cli.py dashboard
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── `run` command ─────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser("run", help="Run a backtest")
    run_parser.add_argument("--data-dir", default="./demo_data", help="Data directory")
    run_parser.add_argument("--factors", help="Comma-separated factor files")
    run_parser.add_argument("--capital", type=float, default=10_000_000, help="Initial capital")
    run_parser.add_argument("--start-date", default="2020-01-01", help="Start date")
    run_parser.add_argument("--end-date", default="2024-12-31", help="End date")
    run_parser.add_argument("--optimizer", default="equal_weight", choices=["equal_weight", "min_variance", "mean_variance", "risk_parity"])
    run_parser.add_argument("--target-count", type=int, default=30, help="Target stock count")
    run_parser.add_argument("--rebalance", default="monthly", choices=["daily", "weekly", "monthly", "quarterly"])
    run_parser.add_argument("--winsorize", default="mad", choices=["mad", "percentile", "std", "none"])
    run_parser.add_argument("--standardize", default="zscore", choices=["zscore", "rank", "minmax", "none"])
    run_parser.add_argument("--fill", default="median", choices=["median", "mean", "industry", "none"])
    run_parser.add_argument("--no-neutralize", action="store_true", help="Skip industry neutralization")
    run_parser.add_argument("--commission", type=float, default=0.0003, help="Commission rate")
    run_parser.add_argument("--output", help="Save results to CSV")

    # ── `test` command ────────────────────────────────────────────────────────
    test_parser = subparsers.add_parser("test", help="Run test suite")
    test_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    test_parser.add_argument("--coverage", action="store_true", help="Generate coverage report")

    # ── `analyze` command ─────────────────────────────────────────────────────
    analyze_parser = subparsers.add_parser("analyze", help="Analyze backtest results")
    analyze_parser.add_argument("--results", required=True, help="Path to results CSV")

    # ── `info` command ────────────────────────────────────────────────────────
    subparsers.add_parser("info", help="Show system information")

    # ── `dashboard` command ───────────────────────────────────────────────────
    dash_parser = subparsers.add_parser("dashboard", help="Launch Streamlit dashboard")
    dash_parser.add_argument("--port", type=int, default=8501, help="Server port")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "run": cmd_run,
        "test": cmd_test,
        "analyze": cmd_analyze,
        "info": cmd_info,
        "dashboard": cmd_dashboard,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()