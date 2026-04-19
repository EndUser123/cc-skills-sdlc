#!/usr/bin/env python3
"""
Router for /t skill - detects user intent and routes to appropriate mode.

Detects whether the user wants:
- Discovery mode: What tests exist? What's missing?
- Execution mode: Run tests with analytics (default)
- Bisect mode: When did this break?
"""



def detect_mode_from_prompt(user_input: str) -> str:
    """
    Detect testing intent from natural language prompt.

    Args:
        user_input: The user's natural language prompt

    Returns:
        'smart' | 'discovery' | 'execution' | 'bisect' | 'comprehensive'
    """
    if not user_input:
        return 'smart'  # Smart orchestration by default if no prompt context

    input_lower = user_input.lower()

    # Discovery keywords (highest priority)
    discovery_keywords = [
        'what', 'missing', 'coverage', 'gaps', 'discover', 'exist',
        'what tests', 'which tests', 'test coverage', 'coverage report',
        'test discovery', 'find tests', 'list tests', 'show tests'
    ]
    if any(kw in input_lower for kw in discovery_keywords):
        return 'discovery'

    # Bisect keywords (second priority)
    bisect_keywords = [
        'when', 'break', 'bisect', 'regression', 'last working',
        'worked before', 'worked yesterday', 'introduced', 'bad commit',
        'find bad commit', 'locate commit', 'blame', 'culprit'
    ]
    if any(kw in input_lower for kw in bisect_keywords):
        return 'bisect'

    # Comprehensive keywords (run everything)
    comprehensive_keywords = [
        'comprehensive', 'full analysis', 'everything', 'all modes',
        'discovery and execution', 'test everything'
    ]
    if any(kw in input_lower for kw in comprehensive_keywords):
        return 'comprehensive'

    # Smart orchestration (default for general testing)
    # Keywords that suggest just running tests without specific discovery/bisect intent
    execution_keywords = [
        'run', 'execute', 'test this', 'quick test', 'fast test'
    ]
    if any(kw in input_lower for kw in execution_keywords):
        return 'execution'

    # Default to smart orchestration
    return 'smart'


def get_conversation_context() -> str:
    """
    Get conversation context from Claude Code environment.

    Returns the user's original prompt text that invoked this skill.
    """
    import os
    import sys

    # Claude Code passes the full prompt as command arguments
    # For skills, we can access via sys.argv
    if len(sys.argv) > 1:
        # Join all arguments after the skill name
        return " ".join(sys.argv[1:])

    # Fallback: read from environment if set
    return os.environ.get("CLAUDE_PROMPT", "")


if __name__ == "__main__":
    # Test the router with sample prompts
    test_prompts = [
        ("what tests exist?", "discovery"),
        ("coverage report", "discovery"),
        ("when did this break?", "bisect"),
        ("regression hunting", "bisect"),
        ("run tests", "execution"),
        ("", "smart"),  # Fixed: empty input defaults to smart mode
        ("comprehensive analysis", "comprehensive"),
    ]

    print("Testing router mode detection:")
    for prompt, expected in test_prompts:
        result = detect_mode_from_prompt(prompt)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{prompt}' -> {result} (expected: {expected})")
