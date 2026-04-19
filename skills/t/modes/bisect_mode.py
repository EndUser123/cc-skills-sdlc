#!/usr/bin/env python3
"""Bisect mode for /t skill - Regression hunting via git bisect."""

import subprocess
from dataclasses import dataclass


@dataclass
class BisectResult:
    """Results from git bisect execution."""
    bad_commit: str = ""
    bad_commit_message: str = ""
    good_commit: str = ""
    test_command: str = ""
    steps_taken: int = 0
    success: bool = False
    error_message: str = ""


def run_bisect(
    good_commit: str | None = None,
    bad_commit: str | None = None,
    test_command: str | None = None
) -> BisectResult:
    """
    Run git bisect to find the commit that introduced a bug.

    Workflow:
        1. Prompt for good/bad commits and test command if not provided
        2. Start bisect: git bisect start
        3. Mark bad commit: git bisect bad [bad_commit]
        4. Mark good commit: git bisect good [good_commit]
        5. Run automated bisect: git bisect run [test_command]
        6. Get result: git bisect log (finds the bad commit)
        7. Reset: git bisect reset (cleanup)

    Args:
        good_commit: Commit hash where test passed (default: prompt user)
        bad_commit: Commit hash where test failed (default: HEAD)
        test_command: Command to test each commit (default: prompt user)

    Returns:
        BisectResult with findings
    """
    result = BisectResult()

    # Prompt for missing parameters
    if not bad_commit:
        print("Enter bad commit (where test fails) [default: HEAD]:")
        bad_commit_input = input().strip()
        bad_commit = bad_commit_input if bad_commit_input else "HEAD"

    if not good_commit:
        print("Enter good commit (where test passed) [e.g., HEAD~20, v1.0.0]:")
        good_commit = input().strip()
        if not good_commit:
            result.error_message = "Good commit is required"
            return result

    if not test_command:
        print("Enter test command (must return 0 for pass, non-zero for fail):")
        print("Example: python -m pytest tests/test_feature.py -v")
        test_command = input().strip()
        if not test_command:
            result.error_message = "Test command is required"
            return result

    result.bad_commit = bad_commit
    result.good_commit = good_commit
    result.test_command = test_command

    try:
        # Step 1: Start bisect
        print(f"Starting git bisect between {good_commit} (good) and {bad_commit} (bad)...")
        subprocess.run(
            ["git", "bisect", "start"],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Step 2: Mark bad commit
        print(f"Marking {bad_commit} as bad...")
        subprocess.run(
            ["git", "bisect", "bad", bad_commit],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Step 3: Mark good commit
        print(f"Marking {good_commit} as good...")
        subprocess.run(
            ["git", "bisect", "good", good_commit],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Step 4: Run automated bisect
        print(f"Running test command: {test_command}")
        print("(This may take several minutes depending on commit history)")
        bisect_run = subprocess.run(
            ["git", "bisect", "run", test_command],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes
        )

        if bisect_run.returncode == 0:
            result.success = True

            # Get the bad commit hash and message
            log_output = subprocess.run(
                ["git", "bisect", "log"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse log output to extract commit hash and message
            # Format: "git bisect start bad <hash>\n# first bad commit: [<hash>] <message>"
            lines = log_output.stdout.strip().split('\n')
            for line in lines:
                if line.strip().startswith("# first bad commit:"):
                    # Extract hash from: "# first bad commit: [abc123] Commit message"
                    parts = line.split("]", 1)
                    if len(parts) == 2:
                        hash_part = parts[0].split("[")[-1].strip()
                        message_part = parts[1].strip()
                        result.bad_commit = hash_part
                        result.bad_commit_message = message_part
                        break

            # Get bisect stats (steps taken)
            replay_output = subprocess.run(
                ["git", "bisect", "replay"],
                capture_output=True,
                text=True,
                timeout=30
            )
            # Count "git bisect" commands in replay to estimate steps
            result.steps_taken = replay_output.stdout.count("git bisect")

        else:
            result.error_message = f"Bisect run failed: {bisect_run.stderr}"

    except subprocess.TimeoutExpired:
        result.error_message = "Bisect operation timed out (>10 minutes)"
    except subprocess.CalledProcessError as e:
        result.error_message = f"Git command failed: {e.stderr}"
    except Exception as e:
        result.error_message = f"Unexpected error: {e}"

    finally:
        # Step 5: ALWAYS reset bisect state
        try:
            subprocess.run(
                ["git", "bisect", "reset"],
                capture_output=True,
                timeout=30
            )
            print("\nGit bisect state reset complete")
        except Exception:
            print("\nWarning: Failed to reset git bisect state (may need manual cleanup)")

    return result


def format_bisect_report(result: BisectResult) -> str:
    """Format bisect results as a readable report."""
    lines = [
        "# Git Bisect Report",
        ""
    ]

    if result.success:
        lines.extend([
            "## Status: ✅ Found Bad Commit",
            "",
            f"**Bad Commit:** `{result.bad_commit}`",
            f"**Message:** {result.bad_commit_message}",
            f"**Good Commit:** `{result.good_commit}`",
            f"**Test Command:** `{result.test_command}`",
            f"**Steps Taken:** {result.steps_taken}",
            "",
            "## Analysis",
            "",
            f"The bug was introduced in commit `{result.bad_commit}`.",
            "Use this information to:",
            f"- Review the commit: `git show {result.bad_commit}`",
            "- Analyze what changed between this and the previous commit",
            "- Consider reverting or fixing the specific change",
            "",
            "## Next Steps",
            "",
            "1. [Analyze] Use `/debug` to analyze the bad commit diff",
            "2. [Revert] Use `/git-revert` to revert the bad commit",
            "3. [Fix] Create a fix commit for the issue",
        ])
    else:
        lines.extend([
            "## Status: ❌ Bisect Failed",
            "",
            f"**Error:** {result.error_message}",
            "",
            "## Troubleshooting",
            "",
            "Common issues:",
            "- Good commit not specified or not found",
            "- Test command returns wrong exit codes (must be 0=pass, non-zero=fail)",
            "- Git history is not linear (merge conflicts, rebases)",
            "- Bisect state was already active (try: `git bisect reset`)",
            "",
            "## Manual Bisect",
            "",
            "If automated bisect fails, you can run manual bisect:",
            "1. `git bisect start <bad> <good>`",
            "2. For each commit checked:",
            "   - Run your test command",
            "   - Mark `git bisect good` or `git bisect bad`",
            "3. When bisect identifies the commit, run `git bisect reset`"
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    # Test the bisect mode
    print("Git Bisect Mode Test")
    print("=" * 50)

    # Run bisect with prompts
    result = run_bisect()
    print(format_bisect_report(result))
