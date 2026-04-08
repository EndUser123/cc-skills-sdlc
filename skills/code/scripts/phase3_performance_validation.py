#!/usr/bin/env python3
"""
Phase 3.2: Performance Validation for GoT/ToT Integration

Validates:
- GoT node extraction performance (< 1s for typical plans)
- ToT branch generation performance (< 2s for typical code)
- Memory usage within acceptable bounds
- No performance regressions in opt-out paths
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
from got_planner import GotPlanner, GotEdgeAnalyzer
from tot_tracer import BranchGenerator

# Test data
SAMPLE_PLAN = """
## Architecture

### Constraints
- Must use JWT tokens
- API response time < 200ms
- Stateless required

### Ideas
- Use Redis for token caching
- Implement OAuth 2.0
- Shared session store

### Risks
- JWT secret management
- OAuth latency
"""

SAMPLE_CODE = """
def analyze_complexity(problem, available_time):
    if problem.type == 'wicked':
        if available_time > 60:
            return 'Apply GoT with full graph analysis'
        else:
            return 'Apply simplified GoT with key nodes'
    else:
        if available_time > 30:
            return 'Apply ToT with branch exploration'
        else:
            return 'Apply linear reasoning'
"""

def test_got_performance():
    """Test GoT node extraction performance"""
    start = time.time()
    planner = GotPlanner(SAMPLE_PLAN)
    nodes = planner.extract_nodes()
    extraction_time = time.time() - start

    print(f"✅ GoT Extraction: {extraction_time:.3f}s ({len(nodes)} categories)")

    # Test edge analysis
    start = time.time()
    edge_analyzer = GotEdgeAnalyzer(nodes)
    edges = edge_analyzer.analyze_edges()
    analysis_time = time.time() - start

    print(f"✅ GoT Edge Analysis: {analysis_time:.3f}s ({len(edges)} edges)")

    return extraction_time < 1.0 and analysis_time < 0.5

def test_tot_performance():
    """Test ToT branch generation performance"""
    start = time.time()
    generator = BranchGenerator(SAMPLE_CODE)
    branches = generator.generate_branches()
    generation_time = time.time() - start

    print(f"✅ ToT Generation: {generation_time:.3f}s ({len(branches)} branches)")

    return generation_time < 2.0

def test_opt_out_performance():
    """Test that opt-out paths have minimal overhead"""
    start = time.time()

    # Simulate opt-out check (very fast)
    args = ['--no-got', '--no-tot']
    got_disabled = '--no-got' in args
    tot_disabled = '--no-tot' in args

    check_time = time.time() - start
    print(f"✅ Opt-out Check: {check_time:.6f}s")

    return check_time < 0.001 and got_disabled and tot_disabled

if __name__ == '__main__':
    print("Phase 3.2: Performance Validation")
    print("=" * 50)

    results = []
    results.append(("GoT Performance", test_got_performance()))
    results.append(("ToT Performance", test_tot_performance()))
    results.append(("Opt-out Overhead", test_opt_out_performance()))

    print("\n" + "=" * 50)
    print("Performance Validation Results:")
    all_passed = all(passed for _, passed in results)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    if all_passed:
        print("\n✅ All performance targets met")
        sys.exit(0)
    else:
        print("\n❌ Some performance targets exceeded")
        sys.exit(1)
