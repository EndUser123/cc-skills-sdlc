import sys, json
from pathlib import Path
sys.path.insert(0, '.')
from scripts.complexity_scanner import scan_complexity

files = list(Path('P:\\\\\\packages/cc-skills-sdlc/skills/t').rglob('*.py'))
files = [str(f) for f in files if '__pycache__' not in str(f)]
print(f'Scanning {len(files)} files in skills/t...')

findings = scan_complexity(files, min_cc=5)
findings.sort(key=lambda f: f['complexity'], reverse=True)

print(f'\n{len(findings)} complexity findings in skills/t\n')
for f in findings:
    path_str = f['file_path']
    # Strip the base path to get relative path
    sep = '\\' if '\\' in path_str else '/'
    parts = path_str.split(sep)
    # Find 't' in the path and get what comes after
    try:
        idx = parts.index('t')
        rel = sep.join(parts[idx+1:])
    except (ValueError, IndexError):
        rel = path_str
    print(f"CC={f['complexity']:3d}  {rel}:{f['line_number']}  {f['description']}  [{f['severity']}]")
