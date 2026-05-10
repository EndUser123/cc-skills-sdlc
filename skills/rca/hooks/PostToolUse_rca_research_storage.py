#!/usr/bin/env python3
"""
PostToolUse: Auto-store research results from WebSearch/WebFetch.

When external library research is triggered (via auto-research), this hook
automatically stores the fetched documentation in the library docs cache.

This closes the loop: trigger → fetch → store (automatic).
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Environment-configurable paths
CLAUDE_HOME = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
STATE_DIR = Path(os.environ.get("DEBUG_RCA_STATE_DIR", CLAUDE_HOME / "state" / "rca"))
STATE_FILE = STATE_DIR / "rca_workflow.json"

# Import auto-logging decorator (optional)
_hooks_lib = CLAUDE_HOME / "hooks" / "__lib"
if _hooks_lib.exists():
    sys.path.insert(0, str(_hooks_lib))
    try:
        from hook_base import hook_main
    except ImportError:
        hook_main = lambda f: f  # Fallback: no-op decorator
else:
    hook_main = lambda f: f  # Fallback: no-op decorator

# Import research storage (optional - from rca package)
store_research_result = None
try:
    _hook_dir = Path(__file__).parent.parent.parent.parent / "src"
    if str(_hook_dir) not in sys.path:
        sys.path.insert(0, str(_hook_dir))
    from rca.research_with_cache import store_research_result
except ImportError:
    CSF_SRC = os.environ.get("CSF_SRC", "P:\\\\\\__csf/src")
    if os.path.exists(CSF_SRC):
        sys.path.insert(0, CSF_SRC)
        try:
            from rca.research_with_cache import store_research_result
        except ImportError:
            store_research_result = None
    else:
        store_research_result = None


def extract_library_from_research(query: str, results: list) -> str | None:
    """Extract library name from research query or results.

    Args:
        query: The search query used
        results: Search results (list of dicts with 'url', 'title', etc.)

    Returns:
        Library name if detected, None otherwise
    """
    # Fast-moving libraries from auto_research.py
    fast_moving = {
        "fastapi",
        "django",
        "flask",
        "starlette",
        "aiohttp",
        "httpx",
        "torch",
        "tensorflow",
        "keras",
        "scikit-learn",
        "numpy",
        "pandas",
        "openai",
        "anthropic",
        "langchain",
        "llama-index",
        "chromadb",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "pytest",
        "uvicorn",
        "yt-dlp",
        "yt_dlp",
        "ytdl",
        "youtube-dl",
        "youtube_dl",
        "click",
        "typer",
        "rich",
        "asyncio",
        "trio",
        "curio",
        "requests",
        "urllib3",
        "boto3",
        "botocore",
        "azure",
        "google-cloud",
    }

    query_lower = query.lower()

    # Check query for library names
    for lib in fast_moving:
        if lib.replace("_", "-") in query_lower.replace("_", "-"):
            return lib

    # Check results titles/URLs for library names
    for result in results[:5]:
        url = result.get("url", "")
        title = result.get("title", "").lower()

        for lib in fast_moving:
            if lib.replace("_", "-") in url.replace("_", "-") or lib in title:
                return lib

    return None


def extract_content_from_results(results: list) -> str:
    """Extract documentation content from search results.

    Args:
        results: Search results list

    Returns:
        Concatenated content from results
    """
    content_parts = []

    for result in results[:5]:
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("content", result.get("snippet", ""))

        if title:
            content_parts.append(f"## {title}\n")
        if snippet:
            content_parts.append(f"{snippet}\n")
        if url:
            content_parts.append(f"Source: {url}\n")

    return "\n".join(content_parts)


@hook_main
def main():
    """Entry point - store research results from WebSearch/WebFetch."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({}))
        sys.exit(0)

    # Check if RCA workflow is active
    if not STATE_FILE.exists():
        print(json.dumps({}))
        sys.exit(0)

    # Only process WebSearch and WebFetch tools
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("WebSearch", "WebFetch", "mcp__web-reader__webReader"):
        print(json.dumps({}))
        sys.exit(0)

    # Check if auto-research was triggered
    try:
        state = json.loads(STATE_FILE.read_text())
        research_trigger = state.get("research_trigger", {})
        if not research_trigger.get("should_research"):
            print(json.dumps({}))
            sys.exit(0)
    except (OSError, json.JSONDecodeError):
        print(json.dumps({}))
        sys.exit(0)

    # Extract research data
    tool_output = payload.get("tool_output", "")
    tool_input = payload.get("tool_input", {})

    # Parse results based on tool type
    results = []
    query = ""

    if tool_name == "WebSearch":
        query = tool_input.get("query", "")
        # WebSearch returns text; try to parse structured results
        if isinstance(tool_output, str):
            # Try to extract results from output
            # Format varies, so store raw output as content
            results = [{"title": f"Search: {query}", "content": tool_output, "url": ""}]
    elif tool_name in ("WebFetch", "mcp__web-reader__webReader"):
        url = tool_input.get("url", "")
        # Store fetched content
        results = [{"title": f"Fetched: {url}", "content": tool_output, "url": url}]

    if not results:
        print(json.dumps({}))
        sys.exit(0)

    # Extract library name
    library = extract_library_from_research(query or research_trigger.get("query", ""), results)

    if not library:
        print(json.dumps({}))
        sys.exit(0)

    # Extract content
    content = extract_content_from_results(results)

    # Extract sources
    sources = [r.get("url", "") for r in results if r.get("url")]

    # Store in cache if available
    stored = False
    if store_research_result and content:
        try:
            stored = store_research_result(
                library=library,
                content=content,
                sources=sources,
                version=str(datetime.now(UTC).year),
            )
        except Exception:
            pass

    # Update state to reflect research was stored
    if stored:
        try:
            state["research_stored"] = {
                "library": library,
                "stored_at": datetime.now().isoformat(),
                "sources_count": len(sources),
            }
            STATE_FILE.write_text(json.dumps(state, indent=2))

            print(
                json.dumps(
                    {"message": f"✅ Research stored for {library} ({len(sources)} sources)"}
                )
            )
        except Exception:
            pass
    else:
        print(json.dumps({}))

    sys.exit(0)


if __name__ == "__main__":
    main()
