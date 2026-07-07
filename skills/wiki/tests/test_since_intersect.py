"""test_since_intersect.py - codify the /wiki update --since signal.

The /wiki update Phase-1 Discovery signal #4 is:
  - `git log <sha>..HEAD --name-only --pretty=format:` -> changed files
  - intersect with `Sources:` frontmatter on each `concepts/*.md` page
  - any page citing a changed file is a doc-code-drift refresh candidate

Asserts that the **intersection logic** is correct end-to-end (offline, no real
git required) by constructing a tmp git repo + tmp wiki vault and walking the
pipeline. The wiki skill itself just documents the procedure; this test pins the
core math so a future refactor doesn't silently change the contract.
"""
from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path


def test_setup_helper():  # sanity
    """Sanity: this module can call git on this machine."""
    r = subprocess.run(["git", "--version"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "git version" in r.stdout


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "-C", str(p), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(p), "config", "user.name", "t"], check=True)


def _commit(p: Path, files: dict[str, str], msg: str) -> str:
    for name, body in files.items():
        full = p / name
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(p), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(p), "commit", "-q", "-m", msg], check=True)
    return subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def test_changed_file_list_matches_git_log_since(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    _commit(repo, {"a.py": "v1"}, "init")
    anchor = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    _commit(repo, {"b.py": "v1", "c.md": "v1"}, "add two")
    out = subprocess.run(
        ["git", "-C", str(repo), "log", f"{anchor}..HEAD", "--name-only", "--pretty=format:"],
        capture_output=True, text=True).stdout
    files = {line.strip() for line in out.splitlines() if line.strip()}
    assert files == {"b.py", "c.md"}


def test_intersection_matches_sources_frontmatter(tmp_path):
    """Pages whose `Sources:` cites any file in the changed set are flagged."""
    repo = tmp_path / "r"
    repo.mkdir()
    _init_repo(repo)
    _commit(repo, {"docs/foo.md": "v1", "src/bar.py": "v1"}, "init")
    anchor = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    _commit(repo, {"src/bar.py": "v2"}, "edit bar")
    out = subprocess.run(
        ["git", "-C", str(repo), "log", f"{anchor}..HEAD", "--name-only", "--pretty=format:"],
        capture_output=True, text=True).stdout
    changed = {line.strip() for line in out.splitlines() if line.strip()}
    assert changed == {"src/bar.py"}

    vault = tmp_path / "wiki" / "concepts"
    vault.mkdir(parents=True)
    # Page A: cites bar.py -> MUST be flagged.
    (vault / "alpha.md").write_text(
        "---\ntitle: alpha\nSources:\n  - src/bar.py\n---\n# alpha\n", encoding="utf-8")
    # Page B: cites foo.md (unchanged) -> must NOT be flagged.
    (vault / "beta.md").write_text(
        "---\ntitle: beta\nSources:\n  - docs/foo.md\n---\n# beta\n", encoding="utf-8")
    # Page C: empty sources -> must NOT be flagged.
    (vault / "gamma.md").write_text("---\ntitle: gamma\n---\n# gamma\n",
                                     encoding="utf-8")

    flagged = []
    for page in vault.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        # Naive intersection over the frontmatter "Sources:" line(s).
        m = []
        for ln in text.splitlines():
            if ln.strip().startswith(("- ", "  - ")) or ln.lstrip().startswith("-"):
                pass
            if "Sources" in ln:
                m = ln.split(":", 1)[1] if ":" in ln else ""
        sources_block = ""
        in_sources = False
        for ln in text.splitlines():
            if ln.strip().startswith("Sources"):
                in_sources = True
                continue
            if in_sources and ln.startswith((" ", "\t", "-")):
                sources_block += ln + "\n"
        sources = {s.strip().lstrip("-").strip() for s in sources_block.splitlines() if s.strip()}
        if sources & changed:
            flagged.append(page.stem)
    assert flagged == ["alpha"], f"expected only alpha, got {flagged}"
