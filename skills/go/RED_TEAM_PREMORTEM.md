# /go Red-Team Premortem

## Scope

This packet covers the consolidated `/go` command after removing `/go-ct`, `/go-ef`, and `/go-pi` as public skills. `/go` is now the only public orchestration surface, with `--dispatch pi|claude|local` and default `pi`.

## Findings

| Risk | Failure Path | Guard | Evidence |
|---|---|---|---|
| Stale variant command references | Docs or code still point users to deleted `/go-ct`, `/go-ef`, or `/go-pi` skills | Public reference scan excludes compatibility aliases in enforce internals | `rg`/PowerShell scan over skills/docs/commands/hooks for deleted names |
| Pi adapter stranded under deleted skill | `/go --dispatch pi` depends on scripts removed with `/go-pi` | Pi adapter scripts live under `skills/go/scripts/adapters/pi/` | `skills/go/tests/test_pi_resolve_model.py`, `skills/go/tests/test_pi_review_transcript.py` |
| Dispatch default drifts | `GO_DISPATCH` or parser changes make default non-pi | Parser precedence test: CLI, env, default | `skills/go/tests/test_orchestrate_dispatch.py` |
| Review/QA runs before simplify | Review passes inspect pre-simplification output and miss simplification failures | Common tail order is verify -> simplify -> review -> QA -> artifacts | `test_common_tail_runs_simplify_before_review_and_qa` |
| Worktree creation silently fails | `git worktree add` exits non-zero but pipeline continues against an invalid worktree | Non-zero worktree add raises and orchestrator returns `<promise>BLOCKED</promise>` | `test_create_worktree_blocks_when_git_worktree_add_fails`, `test_orchestrate_returns_blocked_when_worktree_creation_fails` |
| Run state collisions | Missing `RUN_ID`/`GO_RUN_ID` reuses a constant run id | Runtime env generates UUID run ids | `test_ensure_runtime_env_generates_nonconstant_run_id` |
| Enforcement still points at deleted skill hooks | Stop hook tests invoke `skills/go-ct` after deletion | Stop hook moved to `skills/go/hooks/Stop_enforce_gate.py`; enforce config canonical id is `go` | `enforce/tests/test_enforce.py` |

## Follow-Up Watchlist

- Add a real non-interactive Claude dispatch implementation if `--dispatch claude` is expected to execute without human/tool orchestration.
- Decide whether enforce internals should eventually drop `go-ef` as a compatibility alias after local ledgers/configs have aged out.
- Add an integration test with `pi` mocked on PATH if subprocess command shape keeps changing.
