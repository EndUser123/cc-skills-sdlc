#!/usr/bin/env python3
"""
Test code for state-machine prototype agent validation.

Contains intentional state-transition bugs for testing.
"""


class Snapshot:
    """Snapshot with state management bugs."""

    def __init__(self):
        self.status = "pending"
        self.data = None

    def mark_complete(self):
        """BUG: No state validation - can mark any state as complete."""
        self.status = "complete"

    def mark_failed(self):
        """BUG: No state validation - can mark complete snapshot as failed."""
        self.status = "failed"

    def set_data(self, data):
        """BUG: No state check - can set data in any state."""
        self.data = data


class Decision:
    """Decision with ID collision bug."""

    def __init__(self):
        self.id = None
        self.status = "draft"

    def publish(self):
        """BUG: ID assignment not atomic with state change."""
        import time

        self.id = int(time.time() * 1000)  # Collision risk
        self.status = "published"


class TranscriptProcessor:
    """Processor with path validation bug."""

    def __init__(self, transcript_path):
        self.transcript_path = transcript_path
        self.status = "initialized"

    def process(self):
        """BUG: Path existence checked but not validated after."""
        import os

        if os.path.exists(self.transcript_path):
            # TOCTOU: File could be deleted between check and read
            with open(self.transcript_path) as f:
                content = f.read()
            self.status = "processed"
        else:
            self.status = "failed"


def mark_snapshot_status(snapshot, new_status):
    """BUG: Direct state change without validation."""
    # BUG: No check of current state
    # BUG: No validation that new_status is valid
    snapshot.status = new_status


def evidence_freshness_check(evidence, max_age_seconds=300):
    """BUG: TOCTOU race condition."""
    import time

    # Check freshness
    age = time.time() - evidence["timestamp"]
    is_fresh = age < max_age_seconds

    if is_fresh:
        # BUG: Evidence could expire between check and use
        return evidence["data"]
    else:
        return None
