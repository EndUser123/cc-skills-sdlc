"""Dynamic Context Generator for NTP v1.1.

Produces AST-based workspace summary, template routing decision, and SOP.
Enriches context with import statements, key constants, and call-graph depth
to enable claim verification in downstream ADR generation.
Guards against venv/stdlib directories to prevent context-window blow-up.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any


SKIP_DIRS = {"venv", "env", ".venv", ".env", "__pycache__", ".git", ".ruff_cache", ".mypy_cache"}

# Patterns for extracting numeric constants that indicate rate limits, timing, or capacity
_CONSTANT_PATTERNS = (
    re.compile(r"^(SLEEP|MAX_|MIN_|TIMEOUT|COOLDOWN|RATE|LIMIT|THRESHOLD|BATCH|MAX_WORKERS|CONCURRENT|INTERVAL|DELAY|RETRY|BACKOFF|CAPACITY)"),
)


def _extract_imports(tree: ast.AST) -> list[str]:
    """Extract top-level import statements from an AST."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
    return sorted(set(imports))


def _extract_constants(tree: ast.AST, source: str) -> dict[str, Any]:
    """Extract module-level numeric constants that indicate timing, rate, or capacity config."""
    constants: dict[str, Any] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    name = target.id
                    # Only capture constants matching timing/rate/capacity patterns
                    if any(pat.match(name) for pat in _CONSTANT_PATTERNS):
                        try:
                            value = ast.literal_eval(node.value)
                            constants[name] = value
                        except (ValueError, TypeError):
                            pass
    return constants


def _extract_call_depth(func_name: str, tree: ast.AST) -> int:
    """Estimate call depth for a function (how many other functions it calls)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            calls = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
            return len(calls)
    return 0


def _ast_summary(root: str | Path, max_files: int = 60) -> str:
    """Walk root, skipping venv/stdlib, and return an enriched AST summary.

    Each file entry now includes imports, key constants, and call depth
    in addition to class and function names.
    """
    root = Path(root)
    lines: list[str] = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
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
                    source = fh.read()
                tree = ast.parse(source, filename=str(filepath))

                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                imports = _extract_imports(tree)
                constants = _extract_constants(tree, source)

                rel = filepath.relative_to(root)

                # Build enriched line
                parts = [f"  {rel}:"]
                if classes:
                    parts.append(f"classes={classes}")
                if funcs:
                    parts.append(f"funcs={funcs}")
                if imports:
                    # Show only top-level packages, not submodules
                    top_imports = sorted({imp.split(".")[0] for imp in imports})
                    parts.append(f"imports={top_imports}")
                if constants:
                    parts.append(f"constants={constants}")

                lines.append(" ".join(parts))
                count += 1
            except Exception:
                pass
            if count >= max_files:
                break

    if not lines:
        return "  (no Python files found — empty workspace)"
    return "\n".join(lines)


def _detect_domain(query: str) -> str:
    """Detect the technical domain from the query to select verification requirements."""
    q = query.lower()

    browser_keywords = ("selenium", "playwright", "puppeteer", "browser", "webdriver",
                        "geckodriver", "chromium", "firefox", "chrome", "dom", "page load")
    perf_keywords = ("throughput", "latency", "speed", "performance", "bottleneck",
                     "slow", "fast", "faster", "optimization", "concurrent", "parallel",
                     "batch", "rate limit", "429", "sleep", "timeout")
    api_keywords = ("api", "endpoint", "rest", "graphql", "http", "request",
                    "response", "fetch", "curl", "oauth", "auth")

    if any(kw in q for kw in browser_keywords):
        return "browser_automation"
    if any(kw in q for kw in perf_keywords):
        return "performance"
    if any(kw in q for kw in api_keywords):
        return "api_integration"
    return "general"


def _build_sop(mode: str, scope: str, query: str, domain: str) -> str:
    """Return the SOP string with domain-specific verification requirements."""
    base = (
        f"MODE={mode}, SCOPE={scope}, DOMAIN={domain}\n"
        "1. Generate a RUN ID and set DESIGN_RUN_ID env var.\n"
        "2. Run generate_context.py to get enriched AST workspace summary and SOP.\n"
        "3. Draft design_draft_<RUNID>.json matching DesignPayload schema.\n"
    )

    # Domain-specific verification step
    if domain == "browser_automation":
        verify = (
            "4. CLAIM VERIFICATION (mandatory before validation):\n"
            "   a. Read the actual source file(s) that the ADR proposes to change.\n"
            "   b. Verify each API call exists in the target framework's documentation.\n"
            "   c. Do NOT prescribe APIs from a different framework (e.g., Playwright\n"
            "      APIs for a Selenium codebase, or vice versa).\n"
            "   d. State the fallback chain position of the targeted component.\n"
            "   e. Record each verified claim in the claim_verification field.\n"
        )
    elif domain == "performance":
        verify = (
            "4. CLAIM VERIFICATION (mandatory before validation):\n"
            "   a. Identify where time is actually spent by reading sleep/cooldown constants.\n"
            "   b. State the fallback chain position — is the targeted component the\n"
            "      primary path or a fallback? What % of requests reach it?\n"
            "   c. Do NOT rank patterns by effort alone — rank by impact on the\n"
            "      measured bottleneck.\n"
            "   d. Fill the bottleneck_evidence field with your measurement basis.\n"
            "   e. Record each verified claim in the claim_verification field.\n"
        )
    elif domain == "api_integration":
        verify = (
            "4. CLAIM VERIFICATION (mandatory before validation):\n"
            "   a. Read the actual API client code to verify endpoint names and methods.\n"
            "   b. Check that error handling covers the API's documented failure modes.\n"
            "   c. Verify authentication method matches what the API expects.\n"
            "   d. Record each verified claim in the claim_verification field.\n"
        )
    else:
        verify = (
            "4. CLAIM VERIFICATION (mandatory before validation):\n"
            "   a. Read the actual source file(s) that the ADR proposes to change.\n"
            "   b. Verify each factual claim against the codebase (file paths, function\n"
            "      names, API signatures, data flow).\n"
            "   c. Record each verified claim in the claim_verification field.\n"
        )

    finish = (
        "5. Run validate_design.py to verify schema, logic, and claim evidence.\n"
        "6. On SUCCESS: ADR auto-saved, .verified_<RUNID> flag written.\n"
        "7. On FAIL: fix JSON and retry (max 3 attempts).\n"
        f"USER_QUERY: {query}"
    )

    return base + verify + finish


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
    package_root = skill_dir.parent.parent
    workspace = package_root.parent

    ast_summary = _ast_summary(workspace, max_files=60)
    domain = _detect_domain(query)
    sop = _build_sop(mode, scope, query, domain)

    # Template routing — mode + domain override
    if domain == "browser_automation":
        template = "system_precedent_deep_api_verified"
    elif domain == "performance":
        template = "system_precedent_deep_profiled"
    elif domain == "api_integration":
        template = "system_precedent_deep_api_verified"
    elif mode == "system":
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
        "domain": domain,
        "sop": sop,
        "mode": mode,
        "scope": scope,
        "user_query": query,
    }

    import json
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
