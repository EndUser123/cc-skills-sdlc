from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evidence_gate.py"


PLAN = """---
status: implementation-ready
unresolved_blockers: 0
---
# Goal
Do the thing.
## Current State With Evidence
The current implementation is documented by source inspection.
## Design Decisions and Invariants
Keep the behavior bounded.
## Implementation Changes
### TASK-1: Change
**Acceptance:** the behavior is verified.
## Test Matrix
Run the focused test.
## Contract Boundary Matrix
| Boundary | Producer | Consumer | Test |
|---|---|---|---|
| runtime path | source | hook | focused test |
## Assumptions / Defaults
No critical assumptions remain.
## Open Questions
None.
## Evidence Ledger
| Claim | Type | Evidence | Falsifier |
|---|---|---|---|
| The path is wired | verified | source inspection | hook does not fire |
## Falsifiers
- The focused test fails on the real path.
"""


def _write_plan(tmp_path: Path, text: str = PLAN) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_evidence_gate_passes_and_binds_hash(tmp_path: Path) -> None:
    path = _write_plan(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--write-artifact"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    artifact = json.loads((tmp_path / "plan.md.evidence-gate.json").read_text(encoding="utf-8"))
    assert artifact["verdict"] == "PASS"
    assert artifact["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_evidence_gate_blocks_missing_ledger(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, PLAN.replace("## Evidence Ledger", "## Notes"))
    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert '"verdict": "BLOCKED"' in result.stdout
