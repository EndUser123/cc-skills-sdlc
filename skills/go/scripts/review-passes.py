#!/usr/bin/env python3
"""Generate 7-pass review files at the appropriate depth."""
import json, os, pathlib, subprocess, sys

state_dir = pathlib.Path(os.environ["GO_STATE_DIR"])
run_id = os.environ["RUN_ID"]
terminal_id = os.environ.get("TERMINAL_ID", "unknown")

# Determine review depth from diff-summary
depth = "full"
diff_summary = state_dir / f"diff-summary_{run_id}.json"
if diff_summary.exists():
    d = json.loads(diff_summary.read_text())
    depth = d.get("review_depth", "full")
    docs_only = d.get("docs_only", False)
else:
    docs_only = False

PASSES_STANDARD = ["correctness", "scope", "tests", "regressions", "pr-ready"]
PASSES_QUICK = ["correctness", "pr-ready"]
PASSES_FULL = ["correctness", "scope", "tests", "simplicity", "regressions", "maintainability", "pr-ready"]

# Adversarial break-case patterns (from transcript analysis)
ADVERSARIAL_PATTERNS = [
    ("pure-plan-only", "Plan-mode response with no concrete deliverable"),
    ("fake-plan-analytical", "Wrapped analytical content posing as plan output"),
    ("marker-camouflage", "Rationale markers used without actual reasoning"),
    ("rationalale-camouflage", "Explanatory language hiding no-op or stub"),
    ("minimal-malformed-plan", "Plan token present but content is trivial/incomplete"),
]


def _load_active_task() -> dict:
    active = state_dir / f"active-task_{run_id}.json"
    if not active.exists():
        return {}
    try:
        payload = json.loads(active.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload.get("task", payload)


def _changed_files() -> tuple[list[str], list[str]]:
    errors = []
    changed: set[str] = set()
    for command in (
        ["git", "diff", "--name-only", "HEAD", "--"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        proc = subprocess.run(command, shell=False, text=True, capture_output=True)
        if proc.returncode != 0:
            errors.append((proc.stderr or proc.stdout or "").strip() or f"command failed: {' '.join(command)}")
            continue
        changed.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(changed), errors


def _matches(pattern: str, filename: str) -> bool:
    normalized_pattern = pattern.replace("\\", "/").strip("/")
    normalized_file = filename.replace("\\", "/").strip("/")
    return (
        normalized_file == normalized_pattern
        or normalized_file.endswith("/" + normalized_pattern)
        or normalized_file.startswith(normalized_pattern.rstrip("/") + "/")
    )


def _review_findings(task: dict, changed: list[str], errors: list[str]) -> list[str]:
    findings = [f"review diff collection failed: {error}" for error in errors]
    forbidden = task.get("forbidden_files", [])
    for pattern in forbidden:
        for filename in changed:
            if _matches(pattern, filename):
                findings.append(f"Forbidden file changed: {filename} matches {pattern}")

    scope_in = task.get("scope_in", [])
    if scope_in and changed:
        out_of_scope = [
            filename
            for filename in changed
            if not any(_matches(pattern, filename) for pattern in scope_in)
        ]
        for filename in out_of_scope:
            findings.append(f"Changed file outside scope_in: {filename}")
    return findings


def _build_pass_content(pass_name: str, depth: str, findings: list[str], changed: list[str]) -> str:
    status = "REVIEW_REQUIRED" if findings else "PASS"
    parts = [f"# Review Pass: {pass_name}\n", f"Status: {status}\n"]

    if pass_name == "correctness":
        parts.append("## Checklist\n- Code behaves as specified in acceptance criteria\n- No obvious logic errors\n- Edge cases handled\n")
    elif pass_name == "scope":
        parts.append("## Checklist\n- Only scope_in files modified\n- No forbidden_files touched\n- Changes align with task objective\n")
        if depth == "full":
            parts.append("## Adversarial Check\n")
            for case_name, description in ADVERSARIAL_PATTERNS:
                parts.append(f"- [ ] Check for: {case_name} — {description}\n")
    elif pass_name == "tests":
        parts.append("## Checklist\n- Tests cover acceptance criteria\n- No test commented-out or skipped\n- New tests pass locally\n")
    elif pass_name == "simplicity":
        parts.append("## Checklist\n- No over-engineering\n- No speculative abstractions\n- Abstractions justified by actual duplication\n")
    elif pass_name == "regressions":
        parts.append("## Checklist\n- Existing tests still pass\n- No breaking API changes without deprecation path\n")
    elif pass_name == "maintainability":
        parts.append("## Checklist\n- No complex nested conditionals without explanation\n- No magic numbers\n- Naming is descriptive\n")
    elif pass_name == "pr-ready":
        parts.append("## Checklist\n- Commit message follows conventional-commits\n- PR title and body artifacts generated\n- No secrets or credentials in diff\n")

    parts.append("\n## Changed Files\n")
    if changed:
        for filename in changed:
            parts.append(f"- {filename}\n")
    else:
        parts.append("- No changed files detected\n")

    parts.append("\n## Findings\n")
    if findings:
        for finding in findings:
            parts.append(f"- REVIEW_REQUIRED: {finding}\n")
    else:
        parts.append("- No blocking findings recorded\n")
    return "".join(parts)


if depth == "quick":
    passes = PASSES_QUICK
elif depth == "standard":
    passes = PASSES_STANDARD
else:
    passes = PASSES_FULL

task = _load_active_task()
changed_files, collection_errors = _changed_files()
findings = _review_findings(task, changed_files, collection_errors)
failed = bool(findings)
for pass_name in passes:
    pass_file = state_dir / f"review-pass-{pass_name}_{run_id}.md"
    pass_findings = findings if pass_name in {"correctness", "scope", "pr-ready"} else []
    content = _build_pass_content(pass_name, depth, pass_findings, changed_files)
    pass_file.write_text(content, encoding="utf-8")
    if "REVIEW_REQUIRED" in content:
        failed = True

summary = {
    "run_id": run_id,
    "review_depth": depth,
    "review_passes": passes,
    "changed_files": changed_files,
    "findings": findings,
    "failed": failed
}
summary_path = state_dir / f"review-summary_{run_id}.json"
summary_path.write_text(json.dumps(summary, indent=2) + "\n")
sys.exit(1 if failed else 0)
