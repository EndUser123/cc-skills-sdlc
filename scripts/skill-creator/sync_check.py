#!/usr/bin/env python3
"""Source plugin version tracking for the skill-creator local fork.

Detects when the upstream plugin cache has been updated, so local
modifications (claude-p-only) can be cherry-picked onto the new version.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Upstream plugin cache location — find the latest version subdirectory
def _find_plugin_cache() -> Path:
    base = Path("C:/Users/brsth/.claude/plugins/cache/claude-plugins-official/skill-creator/")
    if not base.exists():
        return base
    # Pick the most recently modified subdirectory (assumed to be latest version)
    candidates = [d for d in base.iterdir() if d.is_dir() and len(d.name) == 12]
    if not candidates:
        return base
    latest = max(candidates, key=lambda d: d.stat().st_mtime)
    return latest

PLUGIN_CACHE = _find_plugin_cache()

# Scripts within the plugin we track (key files that affect our fork)
TRACKED_FILES = [
    "skills/skill-creator/scripts/improve_description.py",
    "skills/skill-creator/scripts/run_loop.py",
    "skills/skill-creator/scripts/run_eval.py",
    "skills/skill-creator/scripts/utils.py",
    "skills/skill-creator/scripts/generate_report.py",
]

# Local fork location
LOCAL_FORK = Path(__file__).parent
TRACKING_FILE = LOCAL_FORK / ".fork_metadata.json"


def source_hashes(plugin_dir: Path) -> dict[str, str]:
    """Return {rel_path: sha256[:12]} for all tracked files in the plugin cache."""
    result = {}
    for rel in TRACKED_FILES:
        p = plugin_dir / rel
        if p.exists():
            result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        else:
            result[rel] = ""
    return result


def save_tracking(hashes: dict[str, str]) -> None:
    """Write current hashes to the tracking file."""
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKING_FILE.write_text(json.dumps(hashes, indent=2))


def load_tracking() -> dict[str, str]:
    """Load saved hashes from the tracking file."""
    if TRACKING_FILE.exists():
        return json.loads(TRACKING_FILE.read_text())
    return {}


def check_for_updates(verbose: bool = True) -> tuple[bool, dict[str, str]]:
    """Check if the plugin cache has been updated.

    Returns (updated: bool, hashes: dict).
    If updated is True, the plugin was updated since the last save.
    """
    current = source_hashes(PLUGIN_CACHE)
    stored = load_tracking()

    if not stored:
        # First run — save and return no-update
        save_tracking(current)
        if verbose:
            print("sync_check: first run, tracking plugin version", file=sys.stderr)
        return False, current

    changed = {rel: current[rel] for rel in current if current[rel] != stored.get(rel)}

    if changed:
        if verbose:
            for rel, new_hash in changed.items():
                old = stored.get(rel, "(new)")
                print(f"sync_check: {rel} changed {old} → {new_hash}", file=sys.stderr)
        return True, current
    return False, current


def sync_and_update(verbose: bool = True) -> None:
    """Check for updates and save the new state. Called at fork script startup."""
    updated, hashes = check_for_updates(verbose)
    save_tracking(hashes)
    if updated and verbose:
        print("sync_check: plugin updated — re-run with --sync to merge changes", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check plugin cache version")
    parser.add_argument("--check", action="store_true", help="Only check, don't save")
    parser.add_argument("--force-save", action="store_true", help="Save current state")
    args = parser.parse_args()

    updated, hashes = check_for_updates()
    if args.check:
        print(json.dumps({"updated": updated, "hashes": hashes}, indent=2))
    elif args.force_save:
        save_tracking(hashes)
        print("sync_check: state saved", file=sys.stderr)
    else:
        sync_and_update()
