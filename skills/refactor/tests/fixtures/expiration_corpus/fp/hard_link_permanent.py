"""Fixture (FP): permanent ceiling comment with NO `revisit:` tag.

Modeled verbatim on plugins/cc-skills-media/skills/video-vision/scripts/crv_run.py:45.
Current real-world ponytail convention: rationale + ceiling, no date.
Permanent by design (hard link is the correct primitive on NTFS for a cached
exe) and MUST NOT be flagged.
"""
from __future__ import annotations
import os
from pathlib import Path


def link_exe(src_exe: Path, dst: Path) -> None:
    # ponytail: hard link, free + no privilege on NTFS — copy would double disk
    # and symlink needs admin. Upgrade path: none, this is the floor.
    os.link(src_exe, dst)
