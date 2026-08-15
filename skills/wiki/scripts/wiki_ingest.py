"""wiki_ingest.py — Post-write pipeline orchestrator for the wiki skill.

Collapses the 5-6 ad-hoc tool calls per page (verify, qmd update, auto-link,
contradiction scan, log append) into one. Steps run in strict order because
auto-link depends on the new page being indexed by QMD first.

CLI:
    python wiki_ingest.py --post-write <page.md> [--notes "<1-line>"] [--skip-qmd]

Pipeline (all steps run; failures are reported but do NOT abort the chain):
  1. Read-back verify (file exists, non-empty, frontmatter has `title:`)
  2. qmd update (single-page refresh so step 3 can see the new page)
  3. wiki_after_write.py <page>      (auto-link — queries QMD)
  4. wiki_contradiction_scan.py <page> (contradiction scan; skip if missing)
  5. wiki_log_append.py --page <page> --notes <notes>  (atomic log entry)

Exit code: 0 if all steps ok, 1 if any step failed. Output: JSON status per step.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
LOG_APPEND = SCRIPTS_DIR / "wiki_log_append.py"
AUTO_LINK = SCRIPTS_DIR / "wiki_after_write.py"
CONTRADICTION = SCRIPTS_DIR / "wiki_contradiction_scan.py"
WIKI_STATE = SCRIPTS_DIR / "wiki_state.py"
# wiki_health_check.py lives in the sibling cc-skills-utils plugin (shared
# scripts). Derive via the shared marketplace root, not a brittle relative path.
_MARKETPLACE_ROOT = SCRIPTS_DIR.parents[3]  # .../plugins/cc-skills-sdlc/skills/wiki/scripts -> plugins
HEALTH_CHECK = _MARKETPLACE_ROOT / "cc-skills-utils" / "skills" / "main" / "scripts" / "wiki_health_check.py"


def _mark_phase(session_id: str | None, phase: str) -> None:
    """Lifecycle state update — HARD GATE per SCHEMA.md §15.

    Per the wiki skill's lifecycle contract, every wiki touch must be tracked.
    Failures are NOT silently swallowed — they raise. The caller (wiki_ingest.py)
    surfaces the failure as a non-zero exit code so operators see lifecycle
    tracking broke.

    Idempotent: auto-inits state file if missing.
    No-op if no session-id is provided (skipping is opt-in via env var absence).
    """
    if not session_id:
        return  # caller opted out by not providing session-id
    # Ensure state file exists (idempotent init)
    init_proc = subprocess.run(
        ["python", str(WIKI_STATE), "init", session_id],
        capture_output=True, text=True, timeout=10,
    )
    if init_proc.returncode != 0:
        raise RuntimeError(
            f"wiki_state.py init failed (exit {init_proc.returncode}); "
            f"stderr_tail: {init_proc.stderr.strip()[-200:]}; "
            f"lifecycle tracking is now broken — refusing to continue"
        )
    mark_proc = subprocess.run(
        ["python", str(WIKI_STATE), "mark", session_id, phase],
        capture_output=True, text=True, timeout=10,
    )
    if mark_proc.returncode != 0:
        raise RuntimeError(
            f"wiki_state.py mark {phase} failed (exit {mark_proc.returncode}); "
            f"stderr_tail: {mark_proc.stderr.strip()[-200:]}; "
            f"lifecycle tracking is now broken — refusing to continue"
        )


def step_verify(page: Path) -> dict:
    if not page.exists():
        return {"ok": False, "error": f"page not found: {page}"}
    text = page.read_text(encoding="utf-8")
    if not text.strip():
        return {"ok": False, "error": "page is empty"}
    head = text[:500]
    if not head.startswith("---") or "title:" not in head:
        return {"ok": False, "error": "missing frontmatter 'title:' field"}
    return {"ok": True, "size": len(text)}


def run_subprocess(cmd: list[str], timeout: int) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "exit": proc.returncode,
            "stdout_tail": proc.stdout.strip()[-300:],
            "stderr_tail": proc.stderr.strip()[-300:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s"}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"binary not found: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="wiki_ingest.py",
        description="Post-write pipeline orchestrator (wiki pages).",
    )
    p.add_argument("--post-write", dest="page", required=True,
                   help="absolute path to the wiki page just written")
    p.add_argument("--notes", default="", help="1-line notes for the log entry")
    p.add_argument("--skip-qmd", action="store_true",
                   help="skip the qmd update step (used for offline testing)")
    p.add_argument("--session-id", dest="session_id", default=os.environ.get("GROK_SESSION_ID", ""),
                   help="session id for lifecycle tracking (defaults to $GROK_SESSION_ID)")
    args = p.parse_args(argv)

    page = Path(args.page)
    steps: dict = {}

    # 0. Lifecycle: mark ingest_started before any work
    _mark_phase(args.session_id, "ingest_started")

    # 1. Read-back verify (gate for all subsequent steps)
    steps["1_verify"] = step_verify(page)
    verify_ok = steps["1_verify"]["ok"]
    if verify_ok:
        _mark_phase(args.session_id, "ingest_completed")

    # 2. qmd document add — must run before step 3 (auto-link) so QMD sees the new page.
    #    "qmd update" was never a valid subcommand; the correct single-page upsert is
    #    "qmd document add" (idempotent — returns ok:true on re-add).
    if verify_ok and not args.skip_qmd:
        steps["2_qmd_update"] = run_subprocess(
            ["qmd", "document", "add", "--collection", "wiki",
             "--document-id", page.stem, "--markdown-file", str(page)],
            timeout=120,
        )
    elif verify_ok:
        steps["2_qmd_update"] = {"ok": True, "skipped": "--skip-qmd"}
    else:
        steps["2_qmd_update"] = {"ok": False, "skipped": "verify failed"}
    if steps.get("2_qmd_update", {}).get("ok"):
        _mark_phase(args.session_id, "qmd_updated")

    # 3. Auto-link (queries QMD — depends on step 2)
    if verify_ok:
        steps["3_auto_link"] = run_subprocess(
            ["python", str(AUTO_LINK), str(page)], timeout=30
        )
    else:
        steps["3_auto_link"] = {"ok": False, "skipped": "verify failed"}
    if steps.get("3_auto_link", {}).get("ok"):
        _mark_phase(args.session_id, "auto_link_run")

    # 4. Contradiction scan (skip if deliverable #2 doesn't exist)
    if verify_ok:
        if CONTRADICTION.exists():
            steps["4_contradiction"] = run_subprocess(
                ["python", str(CONTRADICTION), str(page)], timeout=30
            )
        else:
            steps["4_contradiction"] = {"ok": True, "skipped": "wiki_contradiction_scan.py not present"}
    else:
        steps["4_contradiction"] = {"ok": False, "skipped": "verify failed"}
    if steps.get("4_contradiction", {}).get("ok"):
        _mark_phase(args.session_id, "contradiction_scan_run")

    # 5. Log append (always try — even if earlier steps failed, the page exists)
    if verify_ok:
        steps["5_log_append"] = run_subprocess(
            ["python", str(LOG_APPEND), "--page", str(page), "--notes", args.notes],
            timeout=15,
        )
    else:
        steps["5_log_append"] = {"ok": False, "skipped": "verify failed"}
    if steps.get("5_log_append", {}).get("ok"):
        _mark_phase(args.session_id, "log_appended")

    # 6. Automatic GC of stale completed state files (per SCHEMA.md §15).
    # Runs on every ingest — opportunistic, low cost (single directory scan,
    # single-file stat per candidate). Default TTL: 90 days, override via
    # $GROK_WIKI_STATE_GC_DAYS env var. 0 = disabled.
    gc_days = int(os.environ.get("GROK_WIKI_STATE_GC_DAYS", "90"))
    if gc_days > 0:
        try:
            gc_proc = subprocess.run(
                ["python", str(HEALTH_CHECK),
                 "--lifecycle", "--lifecycle-gc", str(gc_days)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            # Parse the deleted count from the GC output (printed to stderr)
            # wiki_health_check.py prints "GC: deleted N state files older than N days:"
            deleted = 0
            for line in (gc_proc.stderr + gc_proc.stdout).splitlines():
                if "GC: deleted" in line and "state files" in line:
                    try:
                        deleted = int(line.split("deleted")[1].split("state")[0].strip())
                    except (ValueError, IndexError):
                        pass
            steps["6_state_gc"] = {
                "ok": gc_proc.returncode == 0,
                "ttl_days": gc_days,
                "deleted": deleted,
            }
        except Exception as e:
            # GC is opportunistic — never blocks ingest
            steps["6_state_gc"] = {"ok": False, "skipped": f"{type(e).__name__}: {e}"}

    # GC is opportunistic — excluded from overall_ok so it never blocks ingest.
    # Surface that distinction explicitly instead of returning an apparently
    # clean result next to an unlabelled failed step.
    overall_ok = all(s.get("ok") for k, s in steps.items() if k != "6_state_gc")
    optional_failures = [
        key for key, value in steps.items()
        if key == "6_state_gc" and not value.get("ok")
    ]
    report = {
        "ok": overall_ok,
        "page": str(page),
        "steps": steps,
        "optional_failures": optional_failures,
        "warnings": [
            "optional lifecycle GC failed; ingest pipeline completed"
            for _ in optional_failures
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
