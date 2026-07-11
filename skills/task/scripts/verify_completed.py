#!/usr/bin/env python3
"""DEPRECATED shim — subject-based task verification has been removed.

The old verify_completed.py matched task subjects against git basenames, generic
commit messages, pickaxe hits, and grep matches across the whole monorepo. That
produced systematic false positives (a matching basename in an unrelated repo,
or a generic keyword in any commit, counted as "evidence"). It has been replaced
by deterministic completion receipts keyed by task ID.

Use the receipt-based verifier instead:

    python scripts/task_verify.py verify [task_id ...] [--repo PATH] [--json]
    python scripts/task_verify.py clean   [task_id ...] [--apply]

Receipts are written by:

    python scripts/task_receipt.py write --task-id N --verify "pytest -q"

This shim exists only so old callers fail loudly with a pointer to the new tool
instead of silently running the removed logic. It exits non-zero.
"""
import sys

_DEPRECATION = (
    "verify_completed.py is DEPRECATED and its subject-based logic has been REMOVED\n"
    "(it produced false positives: basename/commit-message/pickaxe/grep matches are\n"
    "not evidence). Use the receipt-based verifier:\n"
    "  python scripts/task_verify.py verify [task_id ...] [--repo PATH] [--json]\n"
    "  python scripts/task_verify.py clean   [task_id ...] [--apply]\n"
    "Receipts: python scripts/task_receipt.py write --task-id N --verify CMD\n"
)


def main() -> int:
    print(_DEPRECATION, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
