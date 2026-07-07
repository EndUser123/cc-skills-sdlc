import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from complexity_scanner import scan_complexity, rank_hotspots

if "--churn" in sys.argv[1:]:
    _files = [ln.strip() for ln in Path(__file__).parent.parent.joinpath('scan_targets.txt').read_text().splitlines() if ln.strip()]
    _rows = rank_hotspots(_files, since_days=90, min_cc=5, top_n=10)
    print("Top %d churn x complexity hotspots (last 90d):" % len(_rows))
    for _r in _rows:
        print("  score=%(hotspot_score)d  CC=%(max_cc)d  churn=%(churn)d  %(file_path)s" % _r)
    sys.exit(0)

files = Path(__file__).parent.parent.joinpath('scan_targets.txt').read_text().splitlines()
findings = scan_complexity(files, min_cc=5)
findings.sort(key=lambda f: f['complexity'], reverse=True)

# Group by package (index 3 after splitting by sep)
by_pkg = {}
for f in findings:
    sep = '\\' if '\\' in f['file_path'] else '/'
    parts = f['file_path'].split(sep)
    pkg = parts[3] if len(parts) > 3 else parts[-1]
    by_pkg.setdefault(pkg, []).append(f)

print(f'Total findings: {len(findings)}')
print()
for pkg, fs in sorted(by_pkg.items(), key=lambda x: max(f['complexity'] for f in x[1]), reverse=True)[:10]:
    top = fs[0]
    print(f"  {pkg}: {len(fs)} findings, worst CC={top['complexity']} ({top['description']})")

# Save full results
artifacts = Path('P:\\\\\\Users/brsth/.claude/.artifacts/default/refactor')
artifacts.mkdir(parents=True, exist_ok=True)
artifacts.joinpath('scan_results.json').write_text(json.dumps(findings, indent=2))
print(f'\nFull results: {artifacts}/scan_results.json')
