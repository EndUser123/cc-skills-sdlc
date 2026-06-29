import json, os
out = "C:/Users/brsth/.claude/plans/reviews/gto-finding-lifecycle-refactor/failure-modes.json"
findings = []
findings.append({"id": "FM-002", "severity": "high", "title": "Concurrent runs race on carryover.json", "location": "orchestrator.py:68", "description": "test with backtick ` and apostrophe like don't in content", "suggested_fix": "fix it"})
with open(out, "w", encoding="utf-8") as f:
    json.dump({"findings": findings}, f, indent=2)
print("OK", os.path.getsize(out))
