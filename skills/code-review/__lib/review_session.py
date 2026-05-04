"""Review session management for code review skill."""

import uuid
from pathlib import Path

# GTO skill coverage logging
from pathlib import Path as _Path
import sys as _sys

_gto_lib = _Path("P:/.claude/skills")
if str(_gto_lib) not in _sys.path:
    _sys.path.insert(0, str(_gto_lib))
from gto.lib.skill_coverage_detector import _append_skill_coverage


class ReviewSession:
    """Manages code review session state and file operations."""

    def __init__(self, base_dir: str = "P:/.claude/.evidence/code-review"):
        self.base_dir = Path(base_dir)
        self.session_id = str(uuid.uuid4())[:8]
        self.session_dir = self.base_dir / self.session_id
        self.work_file = self.session_dir / "work.md"
        self.findings_file = self.session_dir / "p1_findings.md"
        self.review_file = self.session_dir / "review.md"

    def setup(self, target: str = "") -> None:
        """Initialize the review session directory and work file."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

        if target:
            self._write_work(target)
        else:
            self.work_file.write_text("# Review Target\n\nNo target specified.\n")

    def _write_work(self, target: str) -> None:
        """Resolve target and write work.md."""
        target_path = Path(target)
        files = []

        if target_path.is_file():
            files = [target_path]
        elif target_path.is_dir():
            files = list(target_path.rglob("*.py")) + list(target_path.rglob("*.js"))
        elif "*" in target:
            import glob

            files = [Path(f) for f in glob.glob(target, recursive=True)]

        content = f"# Review Target\n\nTarget: {target}\n\n"
        if files:
            content += f"Files ({len(files)}):\n"
            for f in files[:50]:
                content += f"- {f}\n"
            if len(files) > 50:
                content += f"- ... and {len(files) - 50} more\n"

        self.work_file.write_text(content)

    def get_session_dir(self) -> str:
        """Return the session directory path."""
        return str(self.session_dir)

    def write_findings(self, findings: str) -> None:
        """Write Phase 1 findings."""
        self.findings_file.write_text(findings)

    def write_review(self, review: str) -> None:
        """Write final review report."""
        self.review_file.write_text(review)
        # GTO skill coverage logging
        try:
            _append_skill_coverage(
                target_key="skills/code-review",
                skill="/code-review",
                terminal_id="cli",
                git_sha=None,
            )
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    session = ReviewSession()
    session.setup(sys.argv[1] if len(sys.argv) > 1 else "")
    print(session.get_session_dir())
