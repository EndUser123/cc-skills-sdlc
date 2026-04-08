"""
Shared AID Integration Module for Claude Skills

Provides a common integration layer for AI Distiller (AID) CLI across multiple skills:
- /mermaid-diagrams: Diagram generation via AID
- /refactor: Refactoring analysis via AID
- /perf: Performance analysis via AID
- /discover: Codebase analysis via AID
- /diagnose: Bug hunting via AID
- /rca: Root cause analysis via AID
- /docs: Documentation generation via AID

Version: 1.0.0
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AIDAction(Enum):
    """AI Distiller AI actions for skill integration."""

    # Tier 1: High-value, quick wins
    DIAGRAMS = "prompt-for-diagrams"
    REFACTORING = "prompt-for-refactoring-suggestion"

    # Tier 2: Analysis enhancements
    SECURITY = "prompt-for-security-analysis"
    PERFORMANCE = "prompt-for-performance-analysis"
    COMPLEX_CODEBASE = "prompt-for-complex-codebase-analysis"
    BEST_PRACTICES = "prompt-for-best-practices-analysis"

    # Tier 3: Documentation and bug hunting
    BUG_HUNTING = "prompt-for-bug-hunting"
    SINGLE_FILE_DOCS = "prompt-for-single-file-docs"
    MULTI_FILE_DOCS = "flow-for-multi-file-docs"


@dataclass
class AIDConfig:
    """AID CLI configuration."""

    aid_path: Path = Path.home() / ".aid" / "bin" / "aid.exe"
    timeout: int = 600  # 10 minutes default
    compression_level: str = "moderate"


@dataclass
class AIDResult:
    """Result from AID analysis."""

    success: bool
    output: str
    error: str | None = None
    prompt_file: str | None = None  # Generated prompt file path
    metadata: dict[str, Any] | None = None


class AIDSkillIntegrator:
    """
    Shared AID integration for Claude skills.

    Provides a consistent interface for invoking AID CLI AI actions
    across multiple skills without code duplication.
    """

    def __init__(self, config: AIDConfig | None = None):
        """
        Initialize AID integrator.

        Args:
            config: Optional AID configuration

        Raises:
            RuntimeError: If AID CLI not found or not executable
        """
        self._config = config or AIDConfig()
        self._verify_aid_cli()

    def _verify_aid_cli(self) -> None:
        """Verify AID CLI is available and executable."""
        if not self._config.aid_path.exists():
            raise RuntimeError(
                f"AID CLI not found at {self._config.aid_path}. "
                "Install from: https://github.com/janreges/ai-distiller/releases"
            )

        try:
            result = subprocess.run(
                [str(self._config.aid_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError("AID CLI failed to execute")
        except Exception as e:
            raise RuntimeError(f"AID CLI not executable: {e}")

    def run_ai_action(
        self,
        target_path: str | Path,
        ai_action: AIDAction,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> AIDResult:
        """
        Run AID AI action on target path.

        Args:
            target_path: Path to file or directory
            ai_action: AID AI action to execute
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude

        Returns:
            AIDResult with output or error details
        """
        target = Path(target_path)
        if not target.exists():
            return AIDResult(
                success=False,
                output="",
                error=f"Path not found: {target_path}",
            )

        # Build AID command
        cmd = [
            str(self._config.aid_path),
            str(target),
            "--ai-action",
            ai_action.value,
            "--stdout",
            "--summary-type",
            "off",
        ]

        # Add patterns
        if include_patterns:
            cmd.extend(["--include", ",".join(include_patterns)])
        if exclude_patterns:
            cmd.extend(["--exclude", ",".join(exclude_patterns)])

        # Execute AID CLI
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._config.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AIDResult(
                success=False,
                output="",
                error=f"AID CLI timed out for {ai_action.value}",
            )
        except subprocess.CalledProcessError as e:
            return AIDResult(
                success=False,
                output="",
                error=f"AID CLI failed: {e.stderr}",
            )

        if result.returncode != 0:
            return AIDResult(
                success=False,
                output="",
                error=f"AID CLI failed with code {result.returncode}: {result.stderr}",
            )

        # Extract prompt file path from output (AID generates .md files)
        prompt_file = self._extract_prompt_file(result.stdout)

        return AIDResult(
            success=True,
            output=result.stdout,
            prompt_file=prompt_file,
            metadata={"ai_action": ai_action.value, "target": str(target)},
        )

    def _extract_prompt_file(self, output: str) -> str | None:
        """
        Extract generated prompt file path from AID output.

        AID typically outputs: "Generated prompt: /path/to/prompt.md"
        """
        for line in output.split("\n"):
            if "Generated prompt:" in line or "prompt file:" in line.lower():
                # Extract file path
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[-1].strip()
        return None

    # Convenience methods for common AI actions

    def generate_diagrams(self, target_path: str | Path) -> AIDResult:
        """Generate Mermaid diagrams for codebase."""
        return self.run_ai_action(target_path, AIDAction.DIAGRAMS)

    def analyze_refactoring(self, target_path: str | Path) -> AIDResult:
        """Analyze code for refactoring opportunities with ROI."""
        return self.run_ai_action(target_path, AIDAction.REFACTORING)

    def analyze_performance(self, target_path: str | Path) -> AIDResult:
        """Analyze code for performance issues."""
        return self.run_ai_action(target_path, AIDAction.PERFORMANCE)

    def analyze_security(self, target_path: str | Path) -> AIDResult:
        """Analyze code for security vulnerabilities."""
        return self.run_ai_action(target_path, AIDAction.SECURITY)

    def analyze_codebase(self, target_path: str | Path) -> AIDResult:
        """Perform enterprise-grade codebase analysis."""
        return self.run_ai_action(target_path, AIDAction.COMPLEX_CODEBASE)

    def analyze_best_practices(self, target_path: str | Path) -> AIDResult:
        """Analyze code against best practices."""
        return self.run_ai_action(target_path, AIDAction.BEST_PRACTICES)

    def hunt_bugs(self, target_path: str | Path) -> AIDResult:
        """Systematically search for bugs."""
        return self.run_ai_action(target_path, AIDAction.BUG_HUNTING)

    def generate_docs(self, target_path: str | Path, multi_file: bool = False) -> AIDResult:
        """Generate documentation for code."""
        action = AIDAction.MULTI_FILE_DOCS if multi_file else AIDAction.SINGLE_FILE_DOCS
        return self.run_ai_action(target_path, action)


def create_aid_integrator(config: AIDConfig | None = None) -> AIDSkillIntegrator:
    """
    Factory function to create AID integrator.

    Args:
        config: Optional AID configuration

    Returns:
        AIDSkillIntegrator instance

    Raises:
        RuntimeError: If AID CLI not found or not executable
    """
    return AIDSkillIntegrator(config)
