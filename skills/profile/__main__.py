"""Profile skill - Performance baseline and comparison for modernization workflows."""

from __future__ import annotations

import sys
from pathlib import Path

# Add lib directory to path for imports
lib_dir = Path(__file__).parent / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

from profiler import Profiler


def main() -> int:
    """Main entry point for /profile skill.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Performance baseline and comparison tool for modernization workflows"
    )
    parser.add_argument("target", help="File or directory to profile")
    parser.add_argument("--baseline", action="store_true", help="Establish performance baseline")
    parser.add_argument("--compare", action="store_true", help="Compare against saved baseline")

    args = parser.parse_args()

    # Validate arguments
    if args.baseline and args.compare:
        print("❌ Error: Cannot use --baseline and --compare together")
        return 1

    if not args.baseline and not args.compare:
        print("❌ Error: Must specify either --baseline or --compare")
        return 1

    profiler = Profiler()
    target_path = Path(args.target)

    if not target_path.exists():
        print(f"❌ Error: Target not found: {target_path}")
        return 1

    try:
        if args.baseline:
            # Baseline mode
            print(f"📊 Establishing performance baseline for: {target_path.name}")
            metrics = profiler.measure(target_path)
            profiler.save_baseline(target_path, metrics)

            print("\\n✅ Baseline saved successfully")
            print(f"   Target: {target_path}")
            print(f"   Timestamp: {metrics.get('timestamp')}")

            if "import_time_ms" in metrics:
                print(f"   Import Time: {metrics['import_time_ms']:.1f}ms")
            if "complexity" in metrics:
                cc = metrics["complexity"]
                print(f"   Complexity: CC {cc['average_cc']:.1f} (avg), {cc['max_cc']} (max)")
            if "lines_of_code" in metrics:
                print(f"   Lines of Code: {metrics['lines_of_code']}")

        elif args.compare:
            # Compare mode
            print(f"📊 Comparing performance for: {target_path.name}")
            current_metrics = profiler.measure(target_path)
            comparison = profiler.compare(target_path, current_metrics)

            if "error" in comparison:
                print(f"⚠️  {comparison['error']}")
                print(f"   {comparison.get('fallback', '')}")
                print(f"\\n💡 Suggestion: Run /profile {target_path} --baseline first")
                return 1

            print("\\n📈 Performance Comparison")
            print(f"   Baseline: {comparison.get('baseline_timestamp')}")
            print(f"   Current: {comparison.get('current_timestamp')}")

            # Show deltas for each metric
            if "import_time_ms" in comparison:
                imp = comparison["import_time_ms"]
                status = "✅" if imp["improved"] else "❌"
                print(f"\\n{status} Import Time:")
                print(f"   {imp['baseline']:.1f}ms → {imp['current']:.1f}ms")
                print(f"   Delta: {imp['delta_ms']:+.1f}ms ({imp['pct_change']:+.1f}%)")

            if "complexity" in comparison:
                comp = comparison["complexity"]
                status = "✅" if comp["improved"] else "❌"
                print(f"\\n{status} Complexity:")
                print(f"   CC {comp['baseline']:.1f} → CC {comp['current']:.1f}")
                print(f"   Delta: {comp['delta']:+.1f} ({comp['pct_change']:+.1f}%)")

            if "lines_of_code" in comparison:
                loc = comparison["lines_of_code"]
                status = "✅" if loc["improved"] else "❌"
                print(f"\\n{status} Lines of Code:")
                print(f"   {loc['baseline']} → {loc['current']}")
                print(f"   Delta: {loc['delta']:+d} ({loc['pct_change']:+.1f}%)")

            # Overall assessment
            improvements = sum(
                1
                for m in [comparison.get(k) for k in ["import_time_ms", "complexity", "lines_of_code"]]
                if m and m.get("improved", False)
            )
            total_metrics = sum(1 for m in [comparison.get(k) for k in ["import_time_ms", "complexity", "lines_of_code"]] if m)

            if improvements == total_metrics:
                print("\\n✅ Result: ALL METRICS IMPROVED")
            elif improvements > 0:
                print(f"\\n⚠️  Result: {improvements}/{total_metrics} metrics improved")
            else:
                print("\\n❌ Result: REGRESSION - All metrics degraded")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
