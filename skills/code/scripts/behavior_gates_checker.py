#!/usr/bin/env python3
"""
Behavior Gates Checker for /code skill

Detects implementation commitments vs guidance patterns to ensure proper
delegation in execution models (subagents, teams, hybrid).

This module provides pattern matching for behavioral gates to detect:
1. Direct implementation commitments ("I'll fix the code") - should delegate
2. Directive guidance ("you should modify the function") - user implements
3. TDD context awareness - distinguishes test-writing from implementation
4. /code skill context - workflow and phase terminology
"""

import json
import re
from pathlib import Path
from typing import Literal


class BehaviorGatesChecker:
    """
    Checker for behavioral gates in agent responses.

    Detects patterns that indicate whether an agent is making
    implementation commitments (should delegate) vs providing guidance.
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize behavior gates checker.

        Args:
            config_path: Path to behavior_gates_config.json (default: skills/code/behavior_gates_config.json)
        """
        if config_path is None:
            # Default to code skill config
            config_path = Path(__file__).parent.parent / "behavior_gates_config.json"

        with open(config_path) as f:
            self.config = json.load(f)

        # Compile regex patterns from config
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns from config for efficient matching."""
        self.agreement_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config["agreement_patterns"]["direct_commitments"]
        ]

        self.agreement_exclusions = {
            "test_writing": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["agreement_patterns"]["excluded_patterns"]["test_writing"]
            ],
            "guidance_and_planning": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["agreement_patterns"]["excluded_patterns"]["guidance_and_planning"]
            ],
            "questions": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["agreement_patterns"]["excluded_patterns"]["questions"]
            ],
            "delegation": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["agreement_patterns"]["excluded_patterns"]["delegation"]
            ],
        }

        self.guidance_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config["guidance_patterns"]["direct_guidance"]
        ]

        self.guidance_exclusions = {
            "test_suggestions": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["guidance_patterns"]["excluded_patterns"]["test_suggestions"]
            ],
            "explanations": [
                re.compile(pattern, re.IGNORECASE)
                for pattern in self.config["guidance_patterns"]["excluded_patterns"]["explanations"]
            ],
        }

        self.tdd_red_indicators = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config["tdd_context"]["red_phase_indicators"]
        ]

        self.tdd_implementation_indicators = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config["tdd_context"]["implementation_phase_indicators"]
        ]

    def check_text(
        self,
        text: str,
        context: str | None = None
    ) -> dict:
        """
        Check text for behavioral gate patterns.

        Args:
            text: Text to check (agent response or message)
            context: Optional context (e.g., "TDD RED", "subagent dispatch")

        Returns:
            Dict with:
                - has_agreement: bool - Direct implementation commitments detected
                - has_guidance: bool - Directive guidance to user detected
                - tdd_phase: "red" | "implementation" | "unknown" - TDD context
                - excluded_by: list[str] - Patterns that excluded matches
                - recommendations: list[str] - Actionable recommendations
        """
        result = {
            "has_agreement": False,
            "has_guidance": False,
            "tdd_phase": "unknown",
            "excluded_by": [],
            "recommendations": [],
        }

        # Detect TDD context
        result["tdd_phase"] = self._detect_tdd_phase(text)

        # Check for agreement patterns (implementation commitments)
        agreement_found = False
        for pattern in self.agreement_patterns:
            if pattern.search(text):
                agreement_found = True
                break

        # Check agreement exclusions (even if main pattern didn't match)
        agreement_excluded = self._check_agreement_exclusions(text)

        # Set agreement status based on pattern match and exclusions
        if agreement_found and not agreement_excluded:
            result["has_agreement"] = True
        elif agreement_excluded:
            result["excluded_by"].extend(agreement_excluded)

        # Check for guidance patterns (directive guidance)
        guidance_found = False
        for pattern in self.guidance_patterns:
            if pattern.search(text):
                guidance_found = True
                break

        # Check guidance exclusions (even if main pattern didn't match)
        guidance_excluded = self._check_guidance_exclusions(text)

        # Set guidance status based on pattern match and exclusions
        if guidance_found and not guidance_excluded:
            result["has_guidance"] = True
        elif guidance_excluded:
            result["excluded_by"].extend(guidance_excluded)

        # Generate recommendations based on detected patterns and context
        if result["has_agreement"]:
            if result["tdd_phase"] == "red":
                result["recommendations"].append(
                    "TDD RED phase detected - test-writing is appropriate, may delegate test creation"
                )
            else:
                result["recommendations"].append(
                    "Implementation commitment detected - consider delegating to subagent"
                )

        if result["has_agreement"] and result["tdd_phase"] == "implementation":
            result["recommendations"].append(
                "TDD GREEN/REFACTOR phase detected - implementation work should delegate to subagent"
            )

        return result

    def _detect_tdd_phase(self, text: str) -> Literal["red", "implementation", "unknown"]:
        """
        Detect TDD phase from text.

        Returns:
            "red" - Test-writing phase
            "implementation" - Implementation phase (GREEN/REFACTOR)
            "unknown" - Cannot determine
        """
        for pattern in self.tdd_red_indicators:
            if pattern.search(text):
                return "red"

        for pattern in self.tdd_implementation_indicators:
            if pattern.search(text):
                return "implementation"

        return "unknown"

    def _check_agreement_exclusions(self, text: str) -> list[str]:
        """
        Check if agreement pattern matches are excluded.

        Returns:
            List of exclusion categories that matched
        """
        excluded = []

        for category, patterns in self.agreement_exclusions.items():
            for pattern in patterns:
                if pattern.search(text):
                    excluded.append(category)
                    break

        return excluded

    def _check_guidance_exclusions(self, text: str) -> list[str]:
        """
        Check if guidance pattern matches are excluded.

        Returns:
            List of exclusion categories that matched
        """
        excluded = []

        for category, patterns in self.guidance_exclusions.items():
            for pattern in patterns:
                if pattern.search(text):
                    excluded.append(category)
                    break

        return excluded


def main() -> int:
    """
    CLI entry point for behavior gates checker.

    Usage:
        python behavior_gates_checker.py "text to check"
        python behavior_gates_checker.py --config path/to/config.json "text to check"
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Check text for behavioral gate patterns"
    )
    parser.add_argument(
        "text",
        help="Text to check for behavioral patterns"
    )
    parser.add_argument(
        "--config",
        help="Path to behavior_gates_config.json",
        default=None
    )
    parser.add_argument(
        "--context",
        help="Optional context (e.g., 'TDD RED', 'subagent dispatch')",
        default=None
    )

    args = parser.parse_args()

    checker = BehaviorGatesChecker(config_path=args.config)
    result = checker.check_text(args.text, context=args.context)

    # Print results
    print("Behavior Gates Check Results:")
    print(f"  Agreement (implementation commitment): {result['has_agreement']}")
    print(f"  Guidance (directive to user): {result['has_guidance']}")
    print(f"  TDD Phase: {result['tdd_phase']}")

    if result['excluded_by']:
        print(f"  Excluded by: {', '.join(result['excluded_by'])}")

    if result['recommendations']:
        print("\nRecommendations:")
        for rec in result['recommendations']:
            print(f"  - {rec}")

    return 0


if __name__ == "__main__":
    exit(main())
