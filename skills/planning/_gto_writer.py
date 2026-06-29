import json
out = "C:/Users/brsth/.claude/plans/reviews/gto-finding-lifecycle-refactor/failure-modes.json"
data = {"findings": [
    {
      "id": "FM-001",
      "severity": "high",
      "title": "args.terminal_id is mutated mid-run, breaking the terminal-scoped isolation claim",
      "location": "orchestrator.py:606-612 (terminal_id swap); settings.py:33 (path derivation); state.py:99-104 (execution-state write)",
      "description": "Plan State model (line 60) asserts all finding-lifecycle state is terminal-scoped with no cross-terminal sharing. This is FALSE in the swap path. At orchestrator.py:606-612, when the per-invocation terminal_id fails to resolve a transcript but session_id does, args.terminal_id is reassigned to canonical_tid. Consequences: (1) run_state.json was saved at line 573 under the ORIGINAL terminal_id (state.run_id at line 567 captured the original), but subsequent save_state calls (lines 988, 994) write under the MUTATED id, leaving state files in TWO terminal scopes. (2) save_carryover (line 980) writes to the MUTATED terminal carryover.json, but load_carryover_open_only (line 761) loaded from the ORIGINAL terminal carryover.json. A run can READ terminal A carryover and WRITE terminal B, dropping A open findings silently and polluting B. (3) sync_to_execution_state writes execution-state.json to artifacts_dir.parent (state.py:99), the terminal_id dir, so the swapped run overwrites a DIFFERENT terminal execution-state.json. CHANGE-002 threads ResolveCtx with args.session_id but never addresses the terminal_id swap interaction. No plan test covers this path.",
      "suggested_fix": "Either (a) freeze terminal_id at the start of run() into a local constant used for ALL path derivation and state writes, using args.session_id alone for the registry reverse-lookup with no args.terminal_id mutation, OR (b) if the swap is intentional, re-derive settings.paths and reload state/carryover AFTER the swap so all downstream writes target the canonical terminal. Add a test that runs the swap path and asserts carryover read+write target the SAME terminal_id. Correct the State-model isolation claim or remove the swap."
    },
]}
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
import os
print("WROTE", os.path.getsize(out), "bytes")
