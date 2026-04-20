"""Dynamic Context Generator for NTP v1.1.

Produces AST-based workspace summary, template routing decision, and SOP.
Guards against venv/stdlib directories to prevent context-window blow-up.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Any


SKIP_DIRS = {"venv", "env", ".venv", ".env", "__pycache__", ".git", ".ruff_cache", ".mypy_cache"}


def _ast_summary(root: str | Path, max_files: int = 60) -> str:
    """Walk root, skipping venv/stdlib, and return an AST-derived summary."""
    root = Path(root)
    lines: list[str] = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Guard: prevent descending into venv/stdlib/__pycache__
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        dirpath = Path(dirpath)
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            if count >= max_files:
                break
            filepath = dirpath / filename
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=str(filepath))
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                rel = filepath.relative_to(root)
                line = f"  {rel}: classes={classes}, funcs={funcs}"
                lines.append(line)
                count += 1
            except Exception:
                pass
            if count >= max_files:
                break

    if not lines:
        return "  (no Python files found — empty workspace)"
    return "\n".join(lines)


def _default_sop(mode: str, scope: str, query: str) -> str:
    """Return the SOP string for the given mode/scope."""
    return (
        f"MODE={mode}, SCOPE={scope}\n"
        "1. Generate a RUN ID and set DESIGN_RUN_ID env var.\n"
        "2. Run generate_context.py to get AST workspace summary and SOP.\n"
        "3. Draft design_draft_<RUNID>.json matching DesignPayload schema.\n"
        "4. Run validate_design.py to verify schema and logic.\n"
        "5. On SUCCESS: ADR auto-saved, .verified_<RUNID> flag written.\n"
        "6. On FAIL: fix JSON and retry (max 3 attempts).\n"
        f"USER_QUERY: {query}"
    )


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: generate_context.py <mode> <scope> <query> [run_id]", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    scope = sys.argv[2]
    query = sys.argv[3]
    run_id = sys.argv[4] if len(sys.argv) > 4 else ""

    # Discover workspace root (parent of skills/design_v1.1)
    skill_dir = Path(__file__).parent
    # design_v1.1/design/generate_context.py  →  design_v1.1/ → skills/ → package root
    package_root = skill_dir.parent.parent
    workspace = package_root.parent

    ast_summary = _ast_summary(workspace, max_files=60)
    sop = _default_sop(mode, scope, query)

    # Template routing
    if mode == "system":
        template = "system_precedent_deep"
    elif mode == "rca":
        template = "rca_fast"
    elif mode == "component":
        template = "component_domain"
    else:
        template = "system_precedent_deep"

    output = {
        "run_id": run_id,
        "workspace": str(workspace),
        "ast_summary": ast_summary,
        "template": template,
        "sop": sop,
        "mode": mode,
        "scope": scope,
        "user_query": query,
    }

    import json
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
