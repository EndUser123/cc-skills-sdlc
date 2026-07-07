"""Fixture (TP): plugin version-bump coordinator with an EXPIRED workaround tag.

Modeled on plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py:130.
The ceiling comment is real; the `revisit: 2026-06-01` tag is the proposed
expiration convention. Today is 2026-07-07 -> the tag expired 36 days ago.
A correct expiration scanner MUST flag this.
"""
from __future__ import annotations
import os
from pathlib import Path

# ponytail: global bump lock — shared files (marketplace.json + installed_plugins.json)
# are global, so two terminals bumping *different* plugins still race. Per-plugin locks
# would be wrong; one global lock is correct and smaller.
# ceiling=simple, revisit: 2026-06-01
_BUMP_LOCK_FILE = Path("P:/.claude/state/bump.lock")
_BUMP_LOCK_TIMEOUT = 60  # seconds; bumps are fast, 60s means another process is stuck


def acquire_bump_lock() -> int:
    fd = os.open(_BUMP_LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
        os.lockf(fd, os.LOCK_EX, 0)  # blocking; bump callers are coordinated
    except OSError:
        pass
    return fd
