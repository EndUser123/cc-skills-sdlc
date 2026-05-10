import json
from pathlib import Path

results = json.loads(Path('P:\\\\\\Users/brsth/.claude/.artifacts/default/refactor/scan_results.json').read_text())

# Filter to cc-skills-sdlc only
cc_sdlc = [f for f in results if 'cc-skills-sdlc' in f['file_path']]
cc_sdlc.sort(key=lambda f: f['complexity'], reverse=True)

print(f"Total cc-skills-sdlc findings: {len(cc_sdlc)}\n")
for f in cc_sdlc[:8]:
    print(f"CC={f['complexity']:3d}  {f['file_path']}:{f['line_number']}")
    print(f"        {f['description']}")
    print(f"        risk={f['risk_score']}/4 severity={f['severity']}")
    print()
