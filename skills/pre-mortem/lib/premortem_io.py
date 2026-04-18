"""Pre-mortem I/O utilities - file-based work passing between phases.

This module provides file-based work passing to avoid token costs of passing
full context through the orchestrator. Each phase reads from files and
writes outputs to files, with the orchestrator only passing filenames.

File layout per pre-mortem session:
    P:/.claude/.evidence/pre-mortem/pre-mortem-{timestamp}/
        work.md          - original work input
        p1_findings.md  - Phase 1 output
        p2.md      - Phase 2 output
        p3.md      - Phase 3 output (final)

Session registry (compact resilience):
    P:/.claude/.evidence/pre-mortem/sessions.json
    Maps terminal_id -> session_dir for recovery after compaction.

Usage:
    from premortem_io import PreMortemSession

    # Normal start: creates new session
    session = PreMortemSession.find_or_create_session()

    # After compaction: recovers existing session_dir for this terminal
    session = PreMortemSession.find_or_create_session()
    session.write_work("some work content")
    # spawn phases, each reads from session files
    session.get_work_file()      # -> path to work.md
    session.get_phase_file(1)    # -> path to p1.md
"""

from __future__ import annotations

import re
import hashlib
import json
import os
import shutil
import socket
import sys as _sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

# Cross-platform file locking
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# Windows file locking
try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# GTO skill coverage for GTO session tracking — imported lazily inside write_phase
# to avoid hard dependency on gto package being present at module load time

# Staging root - consistent with GTO's .evidence pattern
# Uses P:\.claude\.evidence\pre-mortem (not Path.home()) to match SKILL.md paths
STAGING_ROOT = Path(__file__).parent.parent.parent.parent / ".evidence" / "pre-mortem"
PHASES = Literal[1, 2, 3]


def _get_terminal_id() -> str:
    """Get terminal ID for session isolation.

    Delegates to canonical_terminal_id() from core.terminal_id (search-research
    package) for a collision-resistant, consistent terminal identifier.
    Falls back to pid+ns hash if the canonical function is unavailable.

    Returns:
        Terminal identifier string.
    """
    try:
        import sys

        # search-research is at P:/packages/search-research/src
        # Go up from .claude/skills/pre-mortem/lib/ to P:\
        search_research_root = (
            Path(__file__).parent.parent.parent.parent.parent / "packages" / "search-research" / "src"
        )
        if str(search_research_root) not in sys.path:
            sys.path.insert(0, str(search_research_root))
        from core.terminal_id import canonical_terminal_id

        return canonical_terminal_id()
    except (socket.gaierror, OSError, ModuleNotFoundError):
        # Fallback: hostname + pid (same algorithm as state_manager._resolve_terminal_id)
        hostname = socket.gethostname()
        pid = os.getpid()
        return f"{hostname}-{pid}"


class PreMortemSession:
    """Manages file-based work passing for a single pre-mortem session."""

    def __init__(self, staging_root: Path | None = None):
        """Initialize a new pre-mortem session.

        Args:
            staging_root: Override staging root directory.
                         Defaults to P:/.claude/.evidence/pre-mortem/
        """
        self.staging_root = staging_root or STAGING_ROOT
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.staging_root / f"pre-mortem-{self.timestamp}"
        # Avoid timestamp collisions if two sessions start in the same second
        while self.session_dir.exists():
            self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.session_dir = self.staging_root / f"pre-mortem-{self.timestamp}"
        self._files: dict[str, Path] = {}

    @classmethod
    def _sessions_file(cls, staging_root: Path | None = None) -> Path:
        """Return path to the sessions registry file."""
        root = staging_root or STAGING_ROOT
        return root / "sessions.json"

    @classmethod
    def _load_registry(cls, staging_root: Path | None = None) -> dict[str, dict]:
        """Load the sessions registry.

        Returns:
            Registry dict mapping terminal_id -> session info dict.
        """
        registry_file = cls._sessions_file(staging_root)
        if registry_file.exists():
            try:
                return json.loads(registry_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    @staticmethod
    def _atomic_write_json(path: Path, data: dict) -> None:
        """Atomically write JSON to a file using temp file + fsync + rename.

        On POSIX: write temp file, fsync() to disk, rename for atomicity.
        On Windows: os.replace() is best-effort atomic; the temp file pattern
        ensures a valid file is always available even if rename fails.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Ensure data is on disk before rename on POSIX
        if os.name != "nt":
            fd = os.open(tmp, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        os.replace(tmp, path)

    def _save_registry(self, staging_root: Path | None = None) -> None:
        """Save this session to the registry.

        Uses file locking to prevent TOCTOU races between concurrent processes.
        The lock is acquired before read-modify-write and released after write.
        """
        terminal_id = _get_terminal_id()
        registry_file = self._sessions_file(staging_root)

        # Ensure parent dir exists before locking
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = registry_file.with_suffix(".lock")

        import time as _time

        def _acquire_msvcrt_lock(lock_fd: int, max_retries: int = 50) -> None:
            """Acquire non-blocking lock with retry on Windows.

            LK_NBLCK fails immediately if the lock is held. Retry with a short
            sleep to allow the holding process to release it. Max wait ~2.5s (50×50ms).
            """
            for _ in range(max_retries):
                try:
                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    _time.sleep(0.05)
            raise RuntimeError(f"Failed to acquire lock on {lock_path} after {max_retries} retries")

        try:
            with open(lock_path, "w") as lock_file:
                if HAS_FCNTL:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                elif HAS_MSVCRT:
                    _acquire_msvcrt_lock(lock_file.fileno())
                try:
                    registry = PreMortemSession._load_registry(staging_root)
                    registry[terminal_id] = {
                        "session_dir": str(self.session_dir),
                        "timestamp": self.timestamp,
                        "last_used": datetime.now().isoformat(),
                    }
                    self._atomic_write_json(registry_file, registry)
                finally:
                    if HAS_FCNTL:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    elif HAS_MSVCRT:
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            raise RuntimeError(f"Failed to acquire lock on {lock_path}") from None

    @classmethod
    def find_or_create_session(cls, staging_root: Path | None = None) -> PreMortemSession:
        """Find or create a pre-mortem session for the current terminal.

        This is the primary entry point. It checks the sessions registry for
        an existing session for this terminal_id. If found and the session_dir
        still exists, returns a PreMortemSession pointing to that directory.
        Otherwise creates a new session and registers it.

        Args:
            staging_root: Override staging root directory.

        Returns:
            PreMortemSession instance (new or recovered).
        """
        terminal_id = _get_terminal_id()
        registry = cls._load_registry(staging_root)
        entry = registry.get(terminal_id)

        if entry:
            session_dir = Path(entry["session_dir"])
            # Validate session_dir stays within staging_root (SEC-001: prevent path traversal)
            root = staging_root or STAGING_ROOT
            try:
                resolved_dir = session_dir.resolve()
                resolved_root = root.resolve()
                # Ensure session_dir is under staging_root using relative_to (cross-platform safe).
                # Note: the `!= resolved_root` guard is a micro-optimization, not a semantic requirement.
                # relative_to() returns "." (not "." as str) when both paths are identical — it does NOT raise.
                # The `!=` check avoids the relative_to() call in the equal-path case, but functionally
                # "relative_to() returns a non-empty dotted name" vs "returns ." is the real signal.
                # Both conditions here are technically redundant together (either would suffice), but
                # keeping both communicates intent clearly.
                is_safe = resolved_dir != resolved_root and resolved_dir.relative_to(resolved_root)
            except (OSError, ValueError):
                is_safe = False

            if is_safe and session_dir.exists() and session_dir.is_dir():
                instance = cls(staging_root)
                instance.session_dir = session_dir
                instance.timestamp = entry.get(
                    "timestamp", session_dir.name.replace("pre-mortem-", "")
                )
                instance._files = {}
                # TEST-003: validate recovered session has all expected files
                work_file = session_dir / "work.md"
                p1_file = session_dir / "p1_findings.md"
                if not work_file.exists():
                    # Stale entry — work.md missing, fall through to new session.
                    # Distinction: a stale entry = registry points to a deleted/moved session dir.
                    # This is case (a) — silently recover by creating new session.
                    registry.pop(terminal_id, None)
                elif not p1_file.exists():
                    # Incomplete session — p1 missing, fall through to new session
                    registry.pop(terminal_id, None)
                else:
                    # RISK-006: detect pre-fix sessions that lack specialists/ subdirectory.
                    # These sessions were created before the session-scoped redirect and
                    # cannot be resumed for Phase 2 critique (specialists/ glob would find 0 files).
                    specialists_dir = session_dir / "specialists"
                    if not specialists_dir.exists():
                        raise RuntimeError(
                            f"Session {session_dir.name} was created before the specialists/ "
                            f"redirect and cannot be resumed. Start a new session instead."
                        )
                    p2_file = session_dir / "p2.md"
                    if not p2_file.exists():
                        # Phase 2 not started — fall through to new session
                        registry.pop(terminal_id, None)
                    else:
                        instance._files = {
                            "work": work_file,
                            "p1": p1_file,
                            "p2": p2_file,
                            "p3": session_dir / "p3.md",
                        }
                        # COMP-002 / 1a: refresh last_used on every recovery
                        instance._save_registry()
                        return instance
            else:
                # session_dir missing or hostile — remove stale entry
                if entry:
                    registry.pop(terminal_id, None)

        # No existing session - create new one
        instance = cls(staging_root)
        instance.setup()
        instance._save_registry(staging_root)
        # Prune sessions older than 7 days opportunistically
        cleanup_old_sessions(age_days=7)
        return instance

    def setup(self) -> PreMortemSession:
        """Create session directory and initialize file paths.

        Returns:
            Self for chaining.

        Raises:
            OSError: If directory creation fails.
        """
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._files = {
            "work": self.session_dir / "work.md",
            "p1": self.session_dir / "p1_findings.md",
            "p2": self.session_dir / "p2.md",
            "p3": self.session_dir / "p3.md",
        }
        # Pre-create specialists/ so Phase 1 dispatch (Step 5) never silently fails
        # due to missing directory. Idempotent via exist_ok=True.
        self.get_specialists_dir()

        # NOTE: The Phase 1 orchestrator dispatches Task agents and immediately runs
        # consolidation in the same response — it cannot actually wait for agents to
        # complete. The fix is in p1_initial_review.md Step 5 post-dispatch block:
        # after the dispatch loop, the orchestrator checks whether specialist JSONs
        # are already available (from a prior interrupted run or background completion).
        # If all dispatched specialists have valid JSONs, it proceeds to consolidation.
        #
        # HOW HANDOFF INTEGRATES: The handoff system (PreCompact capture ->
        # UserPromptSubmit inject) DOES track orchestrator state via
        # pending_operations extracted from the transcript, including the Task()
        # dispatch call (captured as "command: Task tool invocation"). On restore,
        # the compact-restore block shows current_task, progress_state=in_progress,
        # and continuation_rule=Continue. However, Task() with run_in_background:true
        # returns a task ID immediately (transcript marks it "completed"), while
        # the background agent continues asynchronously — the transcript cannot
        # distinguish "agents still running" from "agents finished during compaction."
        # The JSON availability check is the completion detector that complements
        # the handoff's state restoration.
        # If partial or none, it prints guidance to re-run /pre-mortem. The manifest
        # (dispatch_manifest.json) ensures already-dispatched agents are skipped on re-run.
        self._save_registry()
        self._write_source_metadata()
        return self

    def _git_sha(self) -> str:
        """Get current HEAD git SHA for this project."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.session_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _write_source_metadata(self) -> None:
        """Write source_metadata.json capturing git state at session start."""
        meta = {
            "git_sha": self._git_sha(),
            "work_md5": None,
            "work_path": str(self._files["work"]),
            "created_at": self.timestamp,
        }
        meta_file = self.session_dir / "source_metadata.json"
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # --- Evidence citation validation (TASK-001) ---

    SEVERITY_PAT = re.compile(r'\[[A-Z]+\]\s*\[(?:HIGH|CRITICAL)(?:/CRITICAL)?\]', re.IGNORECASE)
    CITATION_PAT = re.compile(r'file:line\s+\d+', re.IGNORECASE)

    def _validate_evidence_citations(self, p1_findings_path: str | Path | None = None) -> None:
        """Raise ValueError if HIGH/CRITICAL findings lack file:line citations.

        Args:
            p1_findings_path: Path to p1_findings.md. Defaults to self.p1 path.

        Raises:
            ValueError: If any HIGH/CRITICAL finding lacks a file:line citation
                        in the surrounding 4-line context window.
        """
        p1_path = Path(p1_findings_path) if p1_findings_path else self._files["p1"]
        content = p1_path.read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if self.SEVERITY_PAT.search(line):
                context = '\n'.join(lines[max(0, i - 2):i + 6])
                if not self.CITATION_PAT.search(context):
                    raise ValueError(
                        f"HIGH/CRITICAL finding without file:line citation at line {i + 1}: "
                        f"{line.strip()[:80]}"
                    )

    def _update_work_hash(self) -> None:
        """Update stored work.md MD5 in registry entry (PRE-4: idempotency guard)."""
        work_path = self._files.get("work")
        if not work_path or not work_path.exists():
            return
        md5 = hashlib.md5(work_path.read_bytes()).hexdigest()
        terminal_id = _get_terminal_id()
        staging_root = self.staging_root or STAGING_ROOT
        registry_file = staging_root / "sessions.json"
        # Ensure session is registered first (terminal_id must exist in registry
        # before we can update its work_md5 field)
        if terminal_id not in PreMortemSession._load_registry(staging_root):
            self._save_registry(staging_root)
        registry = PreMortemSession._load_registry(staging_root)
        registry[terminal_id]["work_md5"] = md5
        self._atomic_write_json(registry_file, registry)
        # Also backfill work_md5 in source_metadata.json for staleness detection
        self._update_source_metadata_work_md5(md5)

    def _update_source_metadata_work_md5(self, md5: str) -> None:
        """Backfill work_md5 into source_metadata.json after work.md is written."""
        meta_file = self.session_dir / "source_metadata.json"
        if not meta_file.exists():
            return
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["work_md5"] = md5
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    def _work_hash_changed(self) -> bool:
        """Return True if work.md content hash differs from stored hash (PRE-4)."""
        work_path = self._files.get("work")
        if not work_path or not work_path.exists():
            return False
        terminal_id = _get_terminal_id()
        registry = self._load_registry(self.staging_root or STAGING_ROOT)
        stored = registry.get(terminal_id, {}).get("work_md5")
        if not stored:
            return True  # No prior hash — treat as changed
        current = hashlib.md5(work_path.read_bytes()).hexdigest()
        return current != stored

    def write_work(self, content: str) -> Path:
        """Write the original work input to a file.

        Args:
            content: The work to critique.

        Returns:
            Path to the work file.

        Raises:
            OSError: If write fails.
        """
        self._ensure_files()
        path = self._files["work"]
        path.write_text(content, encoding="utf-8")
        self._update_work_hash()
        return path

    def read_work(self) -> str:
        """Read the original work input.

        Returns:
            Work content as string.
        """
        self._ensure_files()
        return self._files["work"].read_text(encoding="utf-8")

    def write_phase(self, phase: PHASES, content: str) -> Path:
        """Write a phase's output to a file.

        Args:
            phase: Phase number (1, 2, or 3).
            content: The phase's output text.

        Returns:
            Path to the phase file.

        Raises:
            OSError: If write fails.
            ValueError: If phase is not 1, 2, or 3.
        """
        self._ensure_files()
        key = f"p{phase}"
        path = self._files[key]
        path.write_text(content, encoding="utf-8")
        # Phase 1: validate HIGH/CRITICAL evidence citations
        if phase == 1:
            self._validate_evidence_citations(path)
        # Phase 3: log GTO skill coverage (supplementary)
        if phase == 3:
            try:
                import sys as _sys_importer

                _gto_lib = Path(__file__).parent.parent.parent / "skills" / "gto" / "lib"
                if str(_gto_lib) not in _sys_importer.path:
                    _sys_importer.path.insert(0, str(_gto_lib))
                from gto.lib.skill_coverage_detector import _append_skill_coverage as _asc

                _asc(
                    target_key=f"pre-mortem/{self.session_dir.name}",
                    skill="/pre-mortem",
                    terminal_id=_get_terminal_id(),
                    git_sha=None,
                )
            except (ImportError, AttributeError) as e:
                import sys as _sys_err

                print(
                    f"[premortem_io] skill_coverage_detector unavailable: {e}",
                    file=_sys_err.stderr,
                )
        return path

    def read_phase(self, phase: PHASES) -> str:
        """Read a phase's output.

        Args:
            phase: Phase number (1, 2, or 3).

        Returns:
            Phase output as string.
        """
        self._ensure_files()
        key = f"p{phase}"
        return self._files[key].read_text(encoding="utf-8")

    def get_work_file(self) -> Path:
        """Get path to the work input file."""
        self._ensure_files()
        return self._files["work"]

    def get_phase_file(self, phase: PHASES) -> Path:
        """Get path to a phase output file.

        Args:
            phase: Phase number (1, 2, or 3).

        Returns:
            Path to the phase file.
        """
        self._ensure_files()
        key = f"p{phase}"
        return self._files[key]

    def get_session_dir(self) -> Path:
        """Get the session directory path."""
        return self.session_dir

    def get_specialists_dir(self) -> Path:
        """Get the specialists subdirectory path, creating it if needed."""
        d = self.session_dir / "specialists"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def cleanup(self) -> dict[str, list[str]]:
        """Remove the session directory and all files.

        Returns:
            Cleanup results dict with 'removed' and 'errors' keys.
        """
        removed = []
        errors = []
        if self.session_dir.exists():
            try:
                shutil.rmtree(self.session_dir)
                removed.append(str(self.session_dir))
            except OSError as e:
                errors.append(f"{self.session_dir}: {e}")
        # Remove from registry
        terminal_id = _get_terminal_id()
        registry_file = self._sessions_file()
        registry = self._load_registry()
        if terminal_id in registry:
            del registry[terminal_id]
            registry_file.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return {"removed": removed, "errors": errors}

    def _ensure_files(self) -> None:
        """Ensure files dict is initialized."""
        if not self._files:
            self.setup()


def get_recent_sessions(limit: int = 10) -> list[dict]:
    """Get list of recent pre-mortem sessions.

    Args:
        limit: Maximum number of sessions to return.

    Returns:
        List of session info dicts with 'path', 'timestamp', 'work_preview'.
    """
    if not STAGING_ROOT.exists():
        return []

    sessions = []
    for d in sorted(STAGING_ROOT.iterdir(), key=lambda d: d.name, reverse=True):
        if d.is_dir() and d.name.startswith("pre-mortem-"):
            work_file = d / "work.md"
            preview = ""
            if work_file.exists():
                try:
                    text = work_file.read_text(encoding="utf-8")
                    preview = text[:100].replace("\n", " ")
                except OSError:
                    pass
            sessions.append(
                {
                    "path": str(d),
                    "timestamp": d.name.replace("pre-mortem-", ""),
                    "work_preview": preview,
                }
            )
        if len(sessions) >= limit:
            break

    return sessions


def cleanup_old_sessions(age_days: int = 7, dry_run: bool = False) -> dict[str, list[str]]:
    """Remove session directories older than age_days.

    Args:
        age_days: Remove sessions older than this many days.
        dry_run: If True, return what would be removed without removing it.

    Returns:
        Dict with 'removed' (list of removed dir paths) and 'errors' (list of error messages).
    """
    if not STAGING_ROOT.exists():
        return {"removed": [], "errors": []}

    cutoff = datetime.now() - timedelta(days=age_days)
    removed = []
    errors = []
    registry = PreMortemSession._load_registry()

    for d in STAGING_ROOT.iterdir():
        if not (d.is_dir() and d.name.startswith("pre-mortem-")):
            continue
        # RISK-005 fix: use registry last_used instead of directory mtime for cleanup.
        # A session is active if it has a registry entry with recent last_used.
        # Only clean up dirs where the registry entry (if any) is also old.
        session_str = str(d)
        stale_tids = [
            tid for tid, entry in registry.items() if entry.get("session_dir") == session_str
        ]
        if stale_tids:
            # Has registry entry — check last_used from registry, not directory mtime
            entry = registry.get(stale_tids[0], {})
            last_used_str = entry.get("last_used")
            if last_used_str:
                try:
                    last_used = datetime.fromisoformat(last_used_str)
                except (ValueError, TypeError):
                    last_used = None
            else:
                last_used = None
            if last_used is not None and last_used >= cutoff:
                # Active session — skip even if directory mtime is old
                continue
            # Registry entry is old or missing last_used — proceed with cleanup
        else:
            # No registry entry — fall back to mtime for orphaned directories
            try:
                mtime = datetime.fromtimestamp(d.stat().st_mtime)
            except OSError:
                continue
            if mtime >= cutoff:
                continue
            # stale_tids already computed above for skip check — reuse for registry cleanup
        if dry_run:
            removed.append(str(d))
        else:
            # SEC-002: validate dir is within staging_root before rm
            try:
                resolved_d = d.resolve()
                resolved_root = STAGING_ROOT.resolve()
                if not resolved_d.is_relative_to(resolved_root):
                    errors.append(f"Skip path outside staging_root: {d}")
                    continue
            except (OSError, ValueError):
                errors.append(f"Could not resolve path: {d}")
                continue
            try:
                shutil.rmtree(d)
                removed.append(str(d))
            except OSError as e:
                errors.append(f"{d}: {e}")
            # Remove registry entries for this directory (stale_tids already computed above)
            for tid in stale_tids:
                registry.pop(tid, None)
    if not dry_run and (removed or registry):
        sessions_file = PreMortemSession._sessions_file()
        if registry:
            PreMortemSession._atomic_write_json(sessions_file, registry)
        else:
            # Clean up orphaned sessions.json if no entries remain
            if sessions_file.exists():
                try:
                    sessions_file.unlink()
                except OSError:
                    pass
    return {"removed": removed, "errors": errors}