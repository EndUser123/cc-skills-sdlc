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
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
LOG_APPEND = SCRIPTS_DIR / "wiki_log_append.py"
AUTO_LINK = SCRIPTS_DIR / "wiki_after_write.py"
CONTRADICTION = SCRIPTS_DIR / "wiki_contradiction_scan.py"


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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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
    args = p.parse_args(argv)

    page = Path(args.page)
    steps: dict = {}

    # 1. Read-back verify (gate for all subsequent steps)
    steps["1_verify"] = step_verify(page)
    verify_ok = steps["1_verify"]["ok"]

    # 2. qmd update — must run before step 3 (auto-link) so QMD sees the new page
    if verify_ok and not args.skip_qmd:
        steps["2_qmd_update"] = run_subprocess(["qmd", "update"], timeout=120)
    elif verify_ok:
        steps["2_qmd_update"] = {"ok": True, "skipped": "--skip-qmd"}
    else:
        steps["2_qmd_update"] = {"ok": False, "skipped": "verify failed"}

    # 3. Auto-link (queries QMD — depends on step 2)
    if verify_ok:
        steps["3_auto_link"] = run_subprocess(
            ["python", str(AUTO_LINK), str(page)], timeout=30
        )
    else:
        steps["3_auto_link"] = {"ok": False, "skipped": "verify failed"}

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

    # 5. Log append (always try — even if earlier steps failed, the page exists)
    if verify_ok:
        steps["5_log_append"] = run_subprocess(
            ["python", str(LOG_APPEND), "--page", str(page), "--notes", args.notes],
            timeout=15,
        )
    else:
        steps["5_log_append"] = {"ok": False, "skipped": "verify failed"}

    overall_ok = all(s.get("ok") for s in steps.values())
    report = {"ok": overall_ok, "page": str(page), "steps": steps}
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())