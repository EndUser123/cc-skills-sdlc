---
name: tilldone
description: Run a command on each package in a target directory until phase states stop changing (till-done) or for a fixed count. Works with any slash command or CLI tool.
---
# /tilldone — Batch Convergence Runner

## Purpose

Run a command on each package in a target directory with two modes:
- **Till-done**: Run until phase states in `references/changelog.md` stop changing (convergence)
- **Count**: Run exactly N passes per package

Stops on first stable package, reports, then continues to the next.

## Usage

```bash
/tilldone P:\\\\\\packages --command "/gitready"                    # till-done
/tilldone P:\\\\\\packages --command "/gitready" --count 3          # 3 passes
/tilldone P:\\\\\\packages --command "/gitready" --dry-run          # preview targets
/tilldone P:\\\\\\packages --command "/gitready" -- --publish --finalize  # pass flags
```

## Execution Steps

When `/tilldone` is invoked:

### Step 1: Discover targets
- Scan target directory for subdirs with a `.git/` folder
- Skip hidden dirs (starting with `.`)
- Output: list of package names

### Step 2: Loop over each package
For each package (in sorted order):

**If --count N was specified:**
- Run the command N times
- No convergence check

**If till-done (default):**
1. Read `references/changelog.md` → parse phase states (format: `- PHASE X.Y: Name -- STATUS`)
2. Run the command once
3. Re-read `references/changelog.md` → parse phase states again
4. If states are identical → **stable**, move to next package
5. If states changed → repeat (up to 20 iterations)
6. If not stable after 20 → mark unstable, move to next

---

## PHASE GATE: Generation vs. Validation Separation

**STOP — Before executing validation checks:**

The steps above (Step 2.1–2.6) are **generation** — running the command, observing state changes. The following step (Step 2.7 convergence check) is **validation** — determining whether the generated state meets the stability criterion.

Do NOT mix generation output with validation reasoning in the same prose block. If you are describing what the command did AND whether it passed in the same sentence, you are mixing phases.

**Separation rule:**
- Generation phase: "Run the command. Read the new state. Compare."
- Validation phase: "Does the new state match the previous state?" → stable/unstable verdict

---

### Step 2.7: Convergence Determination (VALIDATION PHASE — gate after generation)

After re-reading `references/changelog.md` and comparing phase states:

```
IF states are identical → [STOP GATE] → "stable" → move to next package
IF states changed       → [STOP GATE] → "unstable — repeating" → loop back to Step 2.1
IF not stable after 20  → [STOP GATE] → "unstable (max iterations)" → move to next package
```

**The convergence verdict is a separate step that follows generation, not a commentary on it.**

### Step 3: Run the command
The command is run via `Skill` tool invocation — I execute it directly, not via subprocess.

For `/gitready`, use the Skill tool. For other slash commands, use Skill tool.

### Step 4: Report
After each package:
```
pkg-name: stable (N iters) | unstable (20 iters) | error (reason)
```

Final summary:
```
Total: X stable, Y errors, Z unstable
```

## Convergence Detection

Phase state format in `references/changelog.md`:
```
- PHASE 1: Diagnose and Prep -- COMPLETED
- PHASE 6: GitHub Publication -- SKIPPED
```

Parse all `- PHASE ... -- STATUS` lines. Compare dict of `{phase_name: status}` before and after command run. Identical = stable.

## Exit Codes
- `0` — all packages stable
- `1` — one or more packages did not converge

## Examples

```bash
# Polish all packages with gitready until phases settle
/tilldone P:\\\\\\packages --command "/gitready" -- --publish --finalize

# Run exactly 3 passes on each package
/tilldone P:\\\\\\packages --command "/gitready" --count 3

# Preview what would run
/tilldone P:\\\\\\packages --command "/gitready" --dry-run

# Run refactor on all packages
/tilldone P:\\\\\\worktrees --command "/refactor" --count 1
```

## STOP GATE: Prohibited Behaviors

These behaviors violate the generation–validation separation and must trigger STOP:

- **E1**: Claim code absent without confirmed tool failure (Read/Grep/git)
- **E4**: Answer without reading relevant source files first
- **E5**: "I assume", "I think", "probably" without tool verification
- **Mixing phases**: Describing what the command did AND giving a stability verdict in the same sentence
- **Premature closure**: Claiming convergence before comparing both state snapshots

---

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check CLAUDE.md → Ask user |
| Directory not ignored | Add to .gitignore + commit |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |