---
name: design_v1.1
description: >
  Native tool-gated architecture skill. Use for system design,
  architecture decisions, root cause analysis (RCA), and lifecycle/sequencing workflows.
enforcement: strict
workflow_steps:
  - Generate RUN ID and set DESIGN_RUN_ID env var
  - Run generate_context.py to get AST workspace summary and SOP
  - Draft design_draft_<RUNID>.json matching DesignPayload schema
  - Run validate_design.py to verify schema and logic
  - On SUCCESS: ADR auto-saved, .verified_<RUNID> flag written
  - On FAIL: fix JSON and retry (max 3 attempts)
hooks:
  pre_response:
    - command: "python .claude/skills/design/hooks/stop_if_unverified.py"
---

# /design_v1.1 Protocol – NTP v1.1

You are operating under a strict **Native Tool-Gated Architecture Protocol**.

## Invocation

The user will invoke you like this:

```
/design_v1.1 [mode] [scope] "optional query"
```

- **Modes:** `system`, `rca`, `component`
- **Scope:** `backend`, `frontend`, `data`, `all`

If the user omits mode or scope, default to:
- `mode = system`
- `scope = all`

## Mandatory First Step

Before you do ANY reasoning or drafting, you MUST:

1. Extract `mode`, `scope`, and `query` from the user's `/design_v1.1` command.
2. Generate a new RUN ID for this session (e.g. UUID or high-entropy token).
3. Set the environment variable `DESIGN_RUN_ID` to that RUN ID.
4. Run the Dynamic Context Generator:

```bash
python .claude/skills/design/generate_context.py "[mode]" "[scope]" "<user_query>" "[RUN_ID]"
```

Read its output **fully**. It contains:
- an AST-based summary of the workspace (skipping venv/stdlib),
- a template routing decision,
- and your **Standard Operating Procedure (SOP)**.

You MUST follow its SOP exactly.

## Drafting and Validation (Tool-Gated Loop)

Once you have the SOP:

1. Draft a **single JSON file** named:

   ```
   design_draft_[RUN_ID].json
   ```

   The JSON MUST strictly match `DesignPayload` in `schemas.py`.
   - Populate the `cap` object carefully.
   - Populate `critic_findings` with at least one finding, even if `severity = "low"`.
   - Populate `adr_markdown` with a complete ADR.

2. Validate using the tool:

   ```bash
   python .claude/skills/design/validate_design.py "design_draft_[RUN_ID].json" "[mode]" "[RUN_ID]"
   ```

   - If it prints errors, **do not** answer the user.
   - You MUST fix `design_draft_[RUN_ID].json` and re-run the validator.
   - You are strictly limited to **3 validation attempts per RUN ID**.
     If validation fails 3 times, stop and ask the user for help.

3. On **SUCCESS**, the validator will:
   - auto-save the ADR to `docs/architecture/ADR-<MODE>-<timestamp>.md`,
   - write a `.verified_[RUN_ID]` file for the stop hook to detect.

Only AFTER a SUCCESSFUL validation are you allowed to answer the user.

## Final Response

When validation has passed:
- DO NOT print the full ADR in the chat.
- Summarize:
  - the ADR title and key decision,
  - the status of the Contract Authority Packet (CAP),
  - whether any critic findings remain,
  - and where the ADR was saved on disk.

Example:

> Validation succeeded for RUN ID XYZ.  
> ADR saved to `docs/architecture/ADR-SYSTEM-1732050800.md`.  
> CAP is closed for all identified boundaries.  
> No high or critical critic findings remain.

If validation has not passed, you MUST NOT answer the user with an ADR.
