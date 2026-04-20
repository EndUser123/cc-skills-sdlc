"""
Context generator for /tdd v3.2.

- Creates per-run directory under .claude-state/tdd/<run_id>/
- Creates an O(1) .active_run pointer
- Detects test command
- Caps workspace scan depth to protect context windows
"""

import sys
import os
import ast
import re
import uuid
import json
import secrets
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_models import SessionState

STATE_ROOT = Path(os.getcwd()) / ".claude-state" / "tdd"
ACTIVE_PTR = STATE_ROOT / ".active_run"
STALE_THRESHOLD_SECONDS = 3600

_SKIP_DIRS = frozenset(
    {
        ".claude",
        ".claude-state",
        "venv",
        ".venv",
        "node_modules",
        "__pycache__",
        ".git",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
    }
)


def _clean_stale_runs() -> None:
    if not STATE_ROOT.exists():
        return
    now = time.time()
    for run_dir in STATE_ROOT.iterdir():
        if not run_dir.is_dir():
            continue
        session_file = run_dir / "session.json"
        try:
            mtime = (
                session_file.stat().st_mtime
                if session_file.exists()
                else run_dir.stat().st_mtime
            )
        except OSError:
            mtime = 0
        if now - mtime > STALE_THRESHOLD_SECONDS:
            shutil.rmtree(run_dir, ignore_errors=True)


def _get_active_run() -> str | None:
    """O(1) active session check via pointer file."""
    if ACTIVE_PTR.exists():
        return ACTIVE_PTR.read_text(encoding="utf-8").strip()
    return None


def _detect_test_command(root_dir: Path) -> str:
    checks = [
        ("pytest.ini", "pytest"),
        ("setup.cfg", "pytest"),
        ("pyproject.toml", "pytest"),
        ("conftest.py", "pytest"),
        ("jest.config.js", "npx jest"),
        ("jest.config.ts", "npx jest"),
        ("vitest.config.ts", "npx vitest run"),
        ("go.mod", "go test ./..."),
        ("Cargo.toml", "cargo test"),
    ]
    for filename, command in checks:
        if (root_dir / filename).exists():
            return command

    pkg_json = root_dir / "package.json"
    if pkg_json.exists():
        try:
            with pkg_json.open("r", encoding="utf-8") as f:
                pkg = json.load(f)
            if "test" in pkg.get("scripts", {}):
                return "npm test"
        except Exception:
            pass
    return "pytest"


def _scan_python(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        return [
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
    except Exception:
        return []


def _scan_js_ts(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        names = re.findall(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
            r"(?:export\s+)?class\s+(\w+)|"
            r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(",
            text,
        )
        return [n for group in names for n in group if n]
    except Exception:
        return []


def _scan_go(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return re.findall(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\(", text)
    except Exception:
        return []


_SCANNERS = {
    ".py": _scan_python,
    ".ts": _scan_js_ts,
    ".tsx": _scan_js_ts,
    ".js": _scan_js_ts,
    ".go": _scan_go,
}


def _get_workspace_summary(root_dir: str, max_depth: int = 3) -> str:
    """Capped workspace scanning to protect context window limits."""
    summaries: list[str] = []
    base_path = Path(root_dir).resolve()

    for root, dirs, files in os.walk(root_dir):
        rel = Path(root).resolve().relative_to(base_path)
        depth = len(rel.parts)
        if depth >= max_depth:
            dirs[:] = []  # Stop descending

        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for file in files:
            scanner = _SCANNERS.get(os.path.splitext(file)[1])
            if scanner:
                path = os.path.join(root, file)
                names = scanner(path)
                if names:
                    summaries.append(f"  {path}: {', '.join(names)}")
    return "\n".join(summaries) if summaries else "  (no source files found)"


def main() -> None:
    mode = (sys.argv[1].lower() if len(sys.argv) > 1 and sys.argv[1] else "feature")
    task = sys.argv[2] if len(sys.argv) > 2 else "Perform TDD."
    run_id = sys.argv[3] if len(sys.argv) > 3 else str(uuid.uuid4())

    cwd = Path(os.getcwd())
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    _clean_stale_runs()

    old_id = _get_active_run()
    if old_id:
        print(f"WARNING: Replacing active session {old_id[:8]}…")
        shutil.rmtree(STATE_ROOT / old_id, ignore_errors=True)

    run_dir = STATE_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Set the O(1) active pointer (atomic write via temp + replace)
    tmp_ptr = ACTIVE_PTR.with_suffix(".tmp")
    tmp_ptr.write_text(run_id, encoding="utf-8")
    tmp_ptr.replace(ACTIVE_PTR)

    test_cmd = _detect_test_command(cwd)
    session = SessionState(
        run_id=run_id,
        mode=mode,  # type: ignore[arg-type]
        task=task,
        cwd=str(cwd),
        test_command=test_cmd,
        phase="init",
        hmac_secret=secrets.token_hex(32),
    )
    (run_dir / "session.json").write_text(
        session.model_dump_json(indent=2), encoding="utf-8"
    )

    workspace = _get_workspace_summary(str(cwd))

    print(
        f"""
╔══════════════════════════════════════════════════╗
║  TDD SESSION INITIALIZED (NTP v3.2)              ║
╠══════════════════════════════════════════════════╣
║  RUN ID       : {run_id}
║  MODE         : {mode.upper()}
║  TASK         : {task}
║  TEST COMMAND : {test_cmd}
╚══════════════════════════════════════════════════╝

WORKSPACE SYMBOLS (Depth Capped):
{workspace}

═══ STANDARD OPERATING PROCEDURE ═══
1. DISCOVER
   Read relevant source and test files.

2. RED PHASE — Write failing tests, then run:
   python .claude/skills/tdd/run_phase.py --run-id "{run_id}" --phase red

3. GREEN PHASE — Implement minimal code to pass, then run:
   python .claude/skills/tdd/run_phase.py --run-id "{run_id}" --phase green

4. REFACTOR (optional but enforced if claimed) — then run:
   python .claude/skills/tdd/run_phase.py --run-id "{run_id}" --phase refactor

5. DRAFT EVIDENCE
   Create {run_dir}/evidence.json matching TddEvidence schema.

6. VALIDATE
   python .claude/skills/tdd/validate_tdd.py "{run_id}"

Note: You may pass --override-cmd "pytest path/to/file.py" to run_phase.py
to run a more specific test command.
"""
    )


if __name__ == "__main__":
    main()