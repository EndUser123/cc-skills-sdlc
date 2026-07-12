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

    path.write_text(path.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
    import importlib.util

    spec = importlib.util.spec_from_file_location("evidence_gate_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.read_verified_plan(path) is None


def test_evidence_gate_blocks_missing_ledger(tmp_path: Path) -> None:
    path = _write_plan(tmp_path, PLAN.replace("## Evidence Ledger", "## Notes"))
    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert '"verdict": "BLOCKED"' in result.stdout


def test_read_verified_plan_rejects_forged_minimal_sidecar(tmp_path: Path) -> None:
    import importlib.util

    path = _write_plan(tmp_path)
    artifact = path.with_suffix(path.suffix + ".evidence-gate.json")
    artifact.write_text(
        json.dumps({
            "verdict": "PASS",
            "plan_path": str(path.resolve()),
            "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }),
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("evidence_gate_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.read_verified_plan(path) is None
