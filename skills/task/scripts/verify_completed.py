#!/usr/bin/env python3
"""Verify completed tasks have real evidence (file / commit / pickaxe / grep).

Reads a task list from a file (one '#ID. [completed] subject' per line, as
produced by `/task list --status completed`) and checks each completed task
against git evidence across all plugin submodules.

Verification ladder (strongest signal first):
  1. FILE existence  — a file named in the subject exists in some submodule
  2. COMMIT message  — a distinctive identifier appears in a commit message
  3. PICKAXE         — git log -S<token> finds the commit that introduced a
                       code-level identifier (catches work hidden under generic
                       auto-commit messages like 'chore: update files')
  4. GREP            — git grep finds the identifier in current code on HEAD

Output: three buckets per task.
  VERIFIED   — evidence found
  UNVERIFIED — a signal was extracted and searched, but no match (probably
               done, but not proven; needs manual check)
  NO_SIGNAL  — subject too vague to extract a file or identifier (needs manual
               or LLM judgment)

Honesty contract: UNVERIFIED is NOT 'done'. Do not collapse UNVERIFIED into a
completion claim. Only VERIFIED authorizes deletion confidence.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

P_ROOT = Path("P:/")
MARKET = P_ROOT / "packages" / ".claude-marketplace" / "plugins"


def discover_submodules() -> list[Path]:
    subs = []
    if not MARKET.exists():
        return subs
    for d in sorted(MARKET.iterdir()):
        if d.is_dir() and ((d / ".git").exists() or (d / ".git").is_file()):
            subs.append(d)
    local = P_ROOT / ".claude"
    if local.exists():
        subs.append(local)
    return subs


# Domain markers -> preferred submodule name (narrows pickaxe/grep cost).
DOMAIN_MAP = [
    ("/go ", "cc-skills-sdlc"), ("/go:", "cc-skills-sdlc"), ("/task", "cc-skills-sdlc"),
    ("/design", "cc-skills-sdlc"), ("/code", "cc-skills-sdlc"), ("/tdd", "cc-skills-sdlc"),
    ("/wiki", "cc-skills-sdlc"), ("/main", "cc-skills-utils"),
    ("/debrief", "cc-skills-analysis"), ("/recap", "cc-skills-analysis"),
    ("/skill-audit", "cc-skills-analysis"), ("/improve", "cc-skills-analysis"),
    ("/red-team", "red-team"), ("/pre-mortem", "red-team"),
    ("/ai-api", "cc-skills-ai-api"), ("/ai-cli", "cc-skills-ai-api"),
    ("search-research", "search-research"), ("chs", "search-research"),
    ("cks", "search-research"),
    ("file_lock", ".claude"), ("Stop.py", ".claude"), ("hook_ledger", ".claude"),
    ("sync.py", "cc-skills-utils"), ("plugin-doctor", "cc-skills-utils"),
    ("plugin-audit-and-fix", "cc-skills-utils"), ("wiki_health", "cc-skills-utils"),
    ("main_health", "cc-skills-utils"), ("capability_claim", "cc-skills-sdlc"),
    ("go_delegation", "cc-skills-sdlc"), ("Stop_enforce", "cc-skills-sdlc"),
    ("omission_audit", "cc-skills-sdlc"), ("discovery-agent", "cc-skills-sdlc"),
    ("refactor-discovery", "cc-skills-sdlc"), ("subagent-routing", "cc-skills-sdlc"),
    ("gto_adapter", "cc-skills-analysis"), ("chs-eval", "search-research"),
    ("QMD", "cc-skills-sdlc"), ("BM25", "cc-skills-sdlc"),
    ("ast_code", "search-research"), ("crawl_to_qmd", "cc-skills-sdlc"),
    ("report-contracts", "cc-skills-analysis"), ("stop_block_log", ".claude"),
    ("Report", "cc-skills-analysis"), ("video-vision", "cc-skills-media"),
]

FILE_TOKEN_RE = re.compile(r"[a-z_][a-z0-9_/\.]*\.(?:py|json|md|yaml|toml|sh|txt)", re.I)
IDENT_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9]*[_-][A-Za-z0-9]+[A-Za-z0-9_-]*|__[a-z]+__|[a-z]+_[a-z_]+"
)
STOPWORDS = {
    "task", "phase", "test", "tests", "update", "fix", "add", "wire", "the", "and",
    "for", "with", "into", "from", "plugin", "skill", "hook", "gate", "new", "all",
    "verify", "run", "check", "set", "drop", "remove", "delete", "rename", "migrate",
    "commit", "bump", "cache", "version", "report", "doc", "docs", "ref", "refs",
    "rollback", "flag", "field", "fields", "worker", "main", "self", "block", "sync",
    "agent", "agents", "telemetry", "schema", "ledger", "contract", "contracts",
    "preflight", "audit", "calibrat", "tdd", "red", "green", "suite", "regression",
    "stale", "drift", "fp", "tier", "rc", "part", "step", "ce",
}


def _run(cmd: list[str], cwd: Path, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
        return r.stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def load_index(submodules: list[Path]) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """Pre-load commit messages + tracked files per submodule (one pass each)."""
    logs: dict[str, list[str]] = {}
    files: dict[str, set[str]] = {}
    for sm in submodules:
        if not sm.exists():
            continue
        out = _run(["git", "log", "--all", "--format=%s"], sm, timeout=15)
        lines = [l.strip().lower() for l in out.splitlines() if l.strip()]
        if lines:
            logs[sm.name] = lines
        out = _run(["git", "ls-files"], sm, timeout=10)
        basenames = {Path(l).name for l in out.splitlines() if l.strip()}
        if basenames:
            files[sm.name] = basenames
    return logs, files


def route(subject: str, tid: str, submodules: list[Path]) -> Path | None:
    s = f" {subject} #{tid} "
    for marker, name in DOMAIN_MAP:
        if marker in s:
            for sm in submodules:
                if sm.name == name:
                    return sm
    m = re.search(r"cc-aca-([a-z]+)", subject)
    if m:
        target = f"cc-aca-{m.group(1)}"
        for sm in submodules:
            if sm.name == target:
                return sm
    return None


def extract(subject: str) -> tuple[set[str], set[str]]:
    files = set(FILE_TOKEN_RE.findall(subject))
    keywords: set[str] = set()
    for c in IDENT_RE.findall(subject):
        cl = c.lower().replace("-", "_")
        if len(cl) < 4 or cl in STOPWORDS:
            continue
        keywords.add(c)
    return files, keywords


def pickaxe(token: str, sm: Path) -> str | None:
    """git log -S<token> — find commits that added/removed the token in diff content."""
    out = _run(["git", "log", "--all", "--oneline", "-1", f"-S{token}"], sm, timeout=12)
    if out.strip():
        return f"{sm.name}: {out.strip().splitlines()[0][:70]}"
    return None


def git_grep(token: str, sm: Path) -> str | None:
    """git grep current code on HEAD for the token."""
    out = _run(["git", "grep", "-l", token], sm, timeout=8)
    if out.strip():
        first = out.strip().splitlines()[0]
        return f"{sm.name}: {first[:70]}"
    return None


def verify_task(tid: str, subject: str, submodules: list[Path],
                logs: dict[str, list[str]], files: dict[str, set[str]]) -> tuple[str, str]:
    file_tokens, keywords = extract(subject)
    if not file_tokens and not keywords:
        return "NO_SIGNAL", "subject too vague to auto-extract"
    sm = route(subject, tid, submodules)
    # 1. FILE existence
    for f in file_tokens:
        basename = Path(f).name
        for name, basenames in files.items():
            if basename in basenames:
                return "VERIFIED", f"FILE {basename} tracked in {name}"
    # 2. COMMIT message (routed submodule first, then all)
    sm_name = sm.name if sm else None
    for kw in keywords:
        kwl = kw.lower()
        if sm_name and sm_name in logs:
            for msg in logs[sm_name]:
                if kwl in msg:
                    return "VERIFIED", f"COMMIT[{kw}] {sm_name}: {msg[:60]}"
        for name, msgs in logs.items():
            if name == sm_name:
                continue
            for msg in msgs:
                if kwl in msg:
                    return "VERIFIED", f"COMMIT[{kw}] {name}: {msg[:60]}"
    # 3. PICKAXE (expensive — only on the unverified tail, routed submodule first)
    targets: list[Path] = ([sm] if sm else []) + [s for s in submodules if s != sm]
    for kw in list(keywords)[:5]:
        for t in targets[:4]:
            hit = pickaxe(kw, t)
            if hit:
                return "VERIFIED", f"PICKAXE[{kw}] {hit}"
    # 4. GREP current code
    for kw in list(keywords)[:5]:
        for t in targets[:4]:
            hit = git_grep(kw, t)
            if hit:
                return "VERIFIED", f"GREP[{kw}] {hit}"
    return "UNVERIFIED", f"files={list(file_tokens)[:2]} kws={list(keywords)[:3]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tasks_file", help="File with '#ID. [completed] subject' lines")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    src = Path(args.tasks_file)
    if not src.exists():
        print(f"MISSING: {src}", file=sys.stderr)
        return 2

    submodules = discover_submodules()
    if not submodules:
        print("No plugin submodules found under P:/packages/.claude-marketplace/plugins",
              file=sys.stderr)
        return 3

    print(f"Loading git index across {len(submodules)} submodules...", file=sys.stderr)
    logs, files = load_index(submodules)
    print(f"  {sum(len(v) for v in logs.values())} commits, "
          f"{sum(len(v) for v in files.values())} files indexed", file=sys.stderr)

    verified, unverified, no_signal = [], [], []
    total = 0
    for line in src.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#?(\d+)\.\s*\[completed\]\s*(.+)", line.strip())
        if not m:
            continue
        total += 1
        tid, subject = m.group(1), m.group(2).strip()
        verdict, evidence = verify_task(tid, subject, submodules, logs, files)
        if verdict == "VERIFIED":
            verified.append((tid, subject, evidence))
        elif verdict == "UNVERIFIED":
            unverified.append((tid, subject, evidence))
        else:
            no_signal.append((tid, subject))

    print(f"\nChecked {total} completed tasks")
    print(f"  VERIFIED:   {len(verified)}/{total}")
    print(f"  UNVERIFIED: {len(unverified)}/{total}  (signal searched, no match — manual check)")
    print(f"  NO SIGNAL:  {len(no_signal)}/{total}  (subject too vague — manual/LLM check)")
    if total:
        rate = 100 * len(verified) // total
        print(f"  Verified rate: {rate}%")

    if args.verbose or unverified:
        print(f"\n=== UNVERIFIED ({len(unverified)}) — do NOT assume done ===")
        for tid, subject, evidence in unverified:
            print(f"  #{tid} {subject[:55]}  ({evidence[:50]})")
    if args.verbose and no_signal:
        print(f"\n=== NO SIGNAL ({len(no_signal)}) ===")
        for tid, subject in no_signal[:20]:
            print(f"  #{tid} {subject[:65]}")

    # Exit code: 0 if all verified, 1 if any unverified/no-signal (caller can decide)
    return 0 if not (unverified or no_signal) else 1


if __name__ == "__main__":
    sys.exit(main())
