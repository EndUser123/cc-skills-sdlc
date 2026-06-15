#!/usr/bin/env python3
"""
Stop hook for /go — shared enforce layer.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforce.stop_gate import load_config_for_skill, evaluate_gates


def main() -> None:
    skill_id = "go"
    try:
        config = load_config_for_skill(skill_id)
    except KeyError:
        print("ERROR: no enforce config for " + skill_id, file=sys.stderr)
        sys.exit(2)

    exit_code, message = evaluate_gates(skill_id, config, os.environ)
    if message:
        print(message, file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

