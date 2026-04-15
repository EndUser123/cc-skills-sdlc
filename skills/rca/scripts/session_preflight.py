#!/usr/bin/env python3
"""
Session preflight check for rca.

Verifies rca package is installed and provides session management utilities.
"""

import subprocess
import sys

try:
    from rca.session import ProblemType, manage_active_session
except ImportError:
    print("Auto-installing rca...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rca"])
    from rca.session import manage_active_session


def run_session(query: str):
    session_id, state = manage_active_session(query, source="rca")
    return session_id, state


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "debug issue"
    run_session(query)
