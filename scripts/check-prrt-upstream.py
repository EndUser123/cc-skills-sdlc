"""Check if pr-review-toolkit upstream has updates available.

Compares the SHA stored in upstream/pr-review-toolkit/SHA against
the cache directory at the Anthropic plugins cache path.

Exit codes: 0=current, 1=update available, 2=check failed
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CACHE_ROOT = Path(
    "C:/Users/brsth/.claude/plugins/cache/claude-plugins-official/pr-review-toolkit"
)
LOCAL_SHA_FILE = Path(__file__).resolve().parent.parent / "upstream" / "pr-review-toolkit" / "SHA"
LAST_CHECKED_FILE = LOCAL_SHA_FILE.parent / "LAST_CHECKED"


def get_local_sha() -> str | None:
    if not LOCAL_SHA_FILE.exists():
        return None
    return LOCAL_SHA_FILE.read_text().strip()


def get_latest_upstream_sha() -> tuple[str | None, list[str]]:
    """Return (latest_sha, all_shas) from cache directory listing."""
    if not CACHE_ROOT.exists():
        return None, []
    shas = [p.name for p in CACHE_ROOT.iterdir() if p.is_dir()]
    if not shas:
        return None, []
    latest = max(shas, key=lambda s: (CACHE_ROOT / s).stat().st_mtime)
    return latest, shas


def main() -> int:
    args = sys.argv[1:]
    show_diff = "--diff" in args

    local_sha = get_local_sha()
    if local_sha is None:
        print("ERROR: No local SHA found at upstream/pr-review-toolkit/SHA")
        return 2

    latest_sha, all_shas = get_latest_upstream_sha()
    if latest_sha is None:
        print(f"CURRENT: {local_sha} (no upstream cache found)")
        _update_last_checked()
        return 0

    if latest_sha == local_sha:
        print(f"CURRENT: {local_sha}")
        _update_last_checked()
        return 0

    print(f"UPDATE AVAILABLE: {local_sha} -> {latest_sha}")

    if show_diff and len(all_shas) > 1:
        new_dir = CACHE_ROOT / latest_sha
        old_dir = CACHE_ROOT / local_sha if (CACHE_ROOT / local_sha).exists() else None

        agents_dir = new_dir / "agents"
        if agents_dir.exists():
            print("\nUpstream agents:")
            for f in sorted(agents_dir.glob("*.md")):
                print(f"  {f.name}")

        if old_dir and old_dir.exists():
            old_agents = old_dir / "agents"
            if old_agents.exists():
                old_names = {f.name for f in old_agents.glob("*.md")}
                new_names = {f.name for f in agents_dir.glob("*.md")}
                added = new_names - old_names
                removed = old_names - new_names
                if added:
                    print(f"\n  Added: {', '.join(sorted(added))}")
                if removed:
                    print(f"  Removed: {', '.join(sorted(removed))}")

    _update_last_checked()
    return 1


def _update_last_checked() -> None:
    LAST_CHECKED_FILE.write_text(
        datetime.now(timezone.utc).isoformat() + "\n"
    )


if __name__ == "__main__":
    sys.exit(main())
