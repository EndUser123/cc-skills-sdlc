# Expiration Corpus — `measured_tp_on_corpus` for the Workaround-Expiration Scanner

## What this corpus measures

Discrimination: can a scanner tell an **expired `ponytail:` workaround** (debt
with a past `revisit: YYYY-MM-DD` date) apart from the four shapes that look
similar but must be left alone?

This is the held-out sample CLAUDE.md requires before any new gate ships, even
advisory:

> **Every new enforcement gate must ship with a `measured_tp_on_corpus` field**
> (real held-out corpus TP/FP) before it can block; a gate that fires 0 real
> positives stays advisory.

The four FP shapes are the realistic failure modes for a naive regex scanner.
A scanner that clears this corpus (3/3 TP flagged, 4/4 FP untouched) has
measured discrimination; one that does not stays advisory.

## Convention under test (proposed)

The current `ponytail:` convention is `# ponytail: <rationale>` — a ceiling
marker with no date. The proposed expiration extension adds an optional
`revisit: YYYY-MM-DD` deadline inside the `ponytail:` block:

```
# ponytail: ceiling=<simple|moderate|strict>, revisit: YYYY-MM-DD
```

A comment with a `revisit:` date whose date is in the past (relative to scan
time) is an **expired workaround** → flag. A `ponytail:` comment without
`revisit:` is **permanent by design** → do not flag.

## Per-file classification

### `tp/` — True Positives (MUST flag)

| File | Real anchor | Date | Why TP |
|------|-------------|------|--------|
| `global_bump_lock_expired.py` | `cc-skills-utils/scripts/plugin-audit-and-fix.py:130` | `2026-06-01` | `ponytail:` block with `revisit: 2026-06-01`; today is `2026-07-07` → expired 36 days. Boundary: well-clear. |
| `fuzzy_cutoff_recently_expired.py` | `cc-skills-utils/skills/main/scripts/wiki_health_check.py:49` | `2026-07-01` | `revisit: 2026-07-01`; expired 6 days. Boundary: just past the line — catches scanners that round the day. |
| `import_resolver_very_old.py` | `cc-aca-epistemic/hooks/pretool/PreToolUse_investigation_gate.py:1054` | `2025-12-01` | `revisit: 2025-12-01`; expired ~7 months. Boundary: long-stale debt, the highest-signal case. |

### `fp/` — False Positives (MUST NOT flag)

| File | Real anchor | Shape | Why FP |
|------|-------------|-------|--------|
| `md5_digest_permanent.py` | `wiki_health_check.py:214` | `ponytail:` + ceiling, NO `revisit:` | Permanent ceiling. No date token ⇒ not debt. |
| `hard_link_permanent.py` | `crv_run.py:45` | `ponytail:` + ceiling, NO `revisit:` | Permanent ceiling. The correct primitive on NTFS. |
| `recap_revisit_if_collision.py` | `recap/models.py:191-202` | `revisit_if: list[str]` dataclass field | Name collision: keyword `revisit` in an identifier, not a `ponytail:` tag. Bare-word match would FP here. |
| `natural_revisit_word.py` | (synthetic prose) | `# TODO: revisit the triage order...` | Word `revisit` in free-form English, no `ponytail:` tag at all. |

## Required scanner behavior (acceptance contract)

A scanner `expire_scan(cwd, today)` returns the set of files flagged. It
passes this corpus iff:

```
tp_flagged  == {tp/global_bump_lock_expired.py,
                tp/fuzzy_cutoff_recently_expired.py,
                tp/import_resolver_very_old.py}
fp_flagged  == {}   # all four fp/* files untouched
```

Hard rules the implementation must satisfy:

1. **Anchor on `ponytail:`** — only match `revisit: <date>` tokens that occur
   inside a `# ponytail:` comment block. Bare-word `revisit` elsewhere is noise
   (see `fp/natural_revisit_word.py`, `fp/recap_revisit_if_collision.py`).
2. **Date comparison is `today`-relative** — the scanner takes `today` as a
   parameter (do not bake in `date.today()`; tests must be deterministic).
3. **Past date ⇒ flag** — `revisit_date < today` flags; `revisit_date >= today`
   does not. Equal-to-today is not yet expired (grace through the deadline day).
4. **No date token ⇒ never flag** — a `ponytail:` comment without `revisit:`
   is permanent (the entire current corpus of ~35 real `ponytail:` comments
   falls in this bucket today).
5. **`revisit_if` identifier is not a tag** — do not match `revisit_if` even
   though it shares the prefix; the token is `revisit:` (colon) inside a
   `ponytail:` block.

## Provenance

Each fixture's header docstring names the real source file and line it was
modeled on, so a future migration can re-ground the corpus against the live
codebase instead of synthetically regenerating it. TP fixtures adapt a real
permanent ceiling into an expired one by adding the proposed `revisit:` tag;
FP fixtures are either verbatim real comments or the real `revisit_if` field.
