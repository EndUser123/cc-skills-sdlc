"""Fixture (FP): permanent ceiling comment with NO `revisit:` tag.

Modeled verbatim on plugins/cc-skills-utils/skills/main/scripts/wiki_health_check.py:214.
This is the CURRENT real-world ponytail convention: a rationale + a known ceiling,
no expiration date. It is permanent by design (md5 is correct for non-security
digests) and MUST NOT be flagged by the expiration scanner.
"""
from __future__ import annotations
import hashlib


def stable_digest(payload: bytes) -> str:
    # ponytail: not security, just a stable digest — md5 is faster than sha256
    # and collision safety is irrelevant here (content-addressed cache key).
    h = hashlib.md5()
    h.update(payload)
    return h.hexdigest()
