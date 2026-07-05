#!/usr/bin/env python3
"""Prompt secret scrubber for /go (SEC-2).

Pure function. Redacts known secret-token prefixes (sk-ant-, sk-cp-, sk-proj-,
plus configured extras) from a prompt before it is written to run state or
handed to a worker subprocess. Idempotent. Fails-closed: a malformed pattern
triggers broad redaction of any long token-shaped substring rather than
passing the secret through unchanged.
"""
from __future__ import annotations

import re
import sys

# Seed patterns (kind, regex). Anthropic key prefixes per gitleaks config
# (memory: gitleaks_secret_scanner_setup).
_DEFAULT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic-key", r"sk-(?:ant|cp|proj)-[A-Za-z0-9_\-]{8,}"),
)

# Extra patterns appended at call time via scrub(text, extra=(...)). Reserved
# for callers that need ad-hoc redaction beyond the seed set without editing
# this module. Empty by default.

# Fail-closed fallback: any 32+ char token-shaped run gets broadly redacted.
# Threshold is high enough to avoid normal words/IDs but catch leaked secrets.
_BROAD_FALLBACK = re.compile(r"[A-Za-z0-9_\-]{32,}")


def _compile_all(extra: tuple[tuple[str, str], ...]) -> list[tuple[str, "re.Pattern[str]"]]:
    patterns = _DEFAULT_PATTERNS + extra
    return [(kind, re.compile(pat)) for kind, pat in patterns]


def scrub(text: str, extra: tuple[tuple[str, str], ...] = ()) -> str:
    """Redact known secret patterns from text. Idempotent. Fails-closed.

    Idempotent because the replacement token ``[REDACTED:<kind>]`` contains no
    secret-prefix substring, so a second pass is a no-op. Fail-closed because a
    malformed configured pattern triggers broad redaction rather than leaking.
    """
    if not text:
        return text
    try:
        compiled = _compile_all(extra)
    except re.error:
        # Malformed configured pattern → never pass secrets through. Log to
        # stderr (the hook/subprocess diagnostics stream) and broad-redact.
        print("scrub_prompt: malformed pattern; using broad fallback", file=sys.stderr)
        return _BROAD_FALLBACK.sub("[REDACTED]", text)
    out = text
    for kind, pat in compiled:
        out = pat.sub(f"[REDACTED:{kind}]", out)
    return out


if __name__ == "__main__":
    # Self-check: redaction, idempotency, normal-prompt passthrough.
    sample = "key=sk-ant-DEADBEEF12345678 then do work"
    once = scrub(sample)
    twice = scrub(once)
    assert once != sample and "sk-ant-" not in once, "seed redaction failed"
    assert "[REDACTED:anthropic-key]" in once
    assert twice == once, "not idempotent"
    assert scrub("a normal prompt with no secrets") == "a normal prompt with no secrets"
    print("scrub_prompt self-check OK")
