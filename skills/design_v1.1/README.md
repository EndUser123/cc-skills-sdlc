# design_v1.1 — NTP v1.1 Architecture Skill

Native Tool-Gated Protocol implementation for Claude Code architecture workflows.

## What is NTP v1.1?

**Native Tool-Gated Protocol** ensures the model cannot answer design questions until a validator passes. Every design run:

1. Generates a per-run UUID (RUN ID) set as `DESIGN_RUN_ID`
2. Runs `generate_context.py` for AST workspace summary and SOP
3. Drafts `design_draft_<RUNID>.json` against `DesignPayload` schema
4. Validates via `validate_design.py` — schema + business logic
5. **SUCCESS**: ADR auto-saved to `docs/architecture/`, `.verified_<RUNID>` flag written
6. **FAIL**: Fix JSON and retry (max 3 attempts per RUN ID)
7. The `stop_if_unverified.py` hook blocks any ADR output unless `.verified_<RUNID>` exists

## Files

```
design_v1.1/
├── hooks/
│   ├── preflight_require_design.py   # Routes design-style queries into NTP
│   └── stop_if_unverified.py         # Blocks ADR output without verified flag
└── design/
    ├── SKILL.md                      # Skill entry point (strict enforcement)
    ├── schemas.py                    # DesignPayload, CAP, ContractBoundary, CriticFinding
    ├── template_routing.py           # (mode, scope) → TemplateProfile
    ├── generate_context.py           # AST walker with venv guard
    ├── validate_design.py            # Schema + logic validation, ADR save, flag write
    └── test_validate_design.py       # Smoke tests
```

## Invocation

```
/design_v1.1 [mode] [scope] "optional query"
```

- **Modes**: `system`, `rca`, `component`
- **Scope**: `backend`, `frontend`, `data`, `all`
- Defaults: `mode=system`, `scope=all`

## Key Design Decisions

| Concern | Decision |
|---------|----------|
| venv/stdlib blow-up | `generate_context.py` skips `venv`, `env`, `.venv`, `__pycache__`, `.git`, etc. |
| Max retries | 3 per RUN ID — attempt counter stored in `.attempt_<RUNID>` |
| Flag location | `.verified_<RUNID>` written to `skills/design/` (where stop hook reads it) |
| ADR location | `docs/architecture/ADR-<MODE>-<timestamp>.md` |
| CAP boundaries | Full boundary model with producer/consumer/freshness_authority/failure_behavior |

## Activation Layers

```
.design_v1.1.md (command)
  └── junction: .claude/skills/design_v1.1 → packages/cc-skills-sdlc/skills/design_v1.1
        └── SKILL.md (enforcement=strict, pre_response hook)
```

## Smoke Tests

```bash
cd P:/packages/cc-skills-sdlc/skills/design_v1.1/design
python -m pytest test_validate_design.py -v
```
