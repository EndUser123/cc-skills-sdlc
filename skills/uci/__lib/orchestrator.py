"""
Parallel Agent Orchestrator for Unified Code Inspection

Orchestrates parallel execution of adversarial review agents:
- Launches all selected agents in single message with multiple Task calls
- Collects JSON outputs from each agent
- Aggregates findings by severity
- Applies token constraints
- Logs API responses with rotation (30-day retention)
- Sanitizes API keys and sensitive data from logs
- Zero-tool-use validation gate (from /cco pattern)
- Path scoping for venv/node_modules exclusion (from /cco pattern)
- Cross-file analysis integration (from /meta-review pattern)
- Context-aware filtering for solo-dev constraints (from /r pattern)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# GTO skill coverage logging
from pathlib import Path as _Path
import sys as _sys

_gto_lib = _Path("P:/.claude/skills")
if str(_gto_lib) not in _sys.path:
    _sys.path.insert(0, str(_gto_lib))
from gto.lib.skill_coverage_detector import _append_skill_coverage

from .agent_registry import AGENT_REGISTRY, select_agents
from .blind_spot_detector import BlindSpotDetector
from .context_filter import PathScopeFilter, SoloDevContextFilter
from .cross_file_analysis import CrossFileAnalyzer
from .memory_integration import (
    AgentConsensus,
    CrossFileMetadata,
    MemoryIntegration,
    ReviewMetadata,
)

# Direct class reference for linter (prevents unused import removal)
_MEMORY_CLASSES = (AgentConsensus, CrossFileMetadata, ReviewMetadata)

logger = logging.getLogger(__name__)


@dataclass
class ResultEnvelope:
    """
    Result envelope from subagent to prevent context overflow.

    Subagents write detailed output to disk and return only this small
    envelope to the orchestrator. The orchestrator then selectively
    reads artifacts only when needed.
    """

    status: str  # "done", "blocked", "retry"
    artifact: Optional[str] = None  # relative/path/to/output/file.json
    summary: str = ""  # ≤3 lines, no code blocks
    metrics: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if envelope has required fields."""
        return self.status in ("done", "blocked", "retry")


@dataclass
class AgentResult:
    """Result from a single agent execution."""

    agent_name: str
    status: str  # "success", "error", "timeout"
    findings: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    token_count: int = 0
    execution_time: float = 0.0
    envelope: Optional[ResultEnvelope] = None  # Result envelope if used


@dataclass
class OrchestratorConfig:
    """Configuration for orchestrator behavior."""

    log_dir: Path = field(default_factory=lambda: Path(".claude/.state/uci"))
    log_retention_days: int = 30
    max_concurrent_agents: int = 12
    agent_timeout_seconds: int = 300
    sanitize_patterns: List[str] = field(
        default_factory=lambda: [
            r"sk_live_[a-zA-Z0-9]{20,}",  # SkillsMP API keys
            r"Bearer\s+[a-zA-Z0-9-._~+/]+=*",  # Bearer tokens
            r"api[_-]?key\s*[:=]\s*[\"']?[a-zA-Z0-9-._~+/]+",  # API keys
            r"password\s*[:=]\s*[\"'][^\"']+[\"']",  # Passwords
            r"secret\s*[:=]\s*[\"'][^\"']+[\"']",  # Secrets
        ]
    )
    # Zero-tool-use failure gate threshold (from /cco pattern)
    max_failed_agent_percentage: float = 0.5  # Stop if >50% agents fail tool use check
    enable_cross_file_analysis: bool = True  # Enable cross-file analysis (from /meta-review)
    enable_context_filtering: bool = True  # Enable solo-dev context filtering (from /r)


class ParallelAgentOrchestrator:
    """
    Orchestrates parallel execution of adversarial review agents.

    The orchestrator is responsible for:
    1. Selecting agents based on mode and filters
    2. Generating prompts for each agent
    3. Collecting and parsing agent outputs
    4. Aggregating findings by severity
    5. Logging and sanitizing sensitive data
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.log_dir = self.config.log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._sanitize_regex = re.compile(
            "|".join(
                f"(?P<match{i}>{pattern})"
                for i, pattern in enumerate(self.config.sanitize_patterns)
            ),
            re.IGNORECASE,
        )
        # Initialize Memory Integration for CKS cross-session learning
        self.memory = MemoryIntegration(enabled=True)
        # Initialize PathScopeFilter for venv/node_modules exclusion
        self.path_filter = PathScopeFilter()
        # Initialize SoloDevContextFilter for enterprise pattern filtering
        self.context_filter = SoloDevContextFilter()
        # Initialize CrossFileAnalyzer for import graph and taint analysis
        self.cross_file_analyzer: Optional[CrossFileAnalyzer] = None
        # Initialize BlindSpotDetector for cross-session category coverage
        self.blind_spot_detector: Optional[BlindSpotDetector] = None

    def _validate_agent_tool_use(
        self,
        agent_results: List[AgentResult],
    ) -> tuple[List[AgentResult], Dict[str, Any]]:
        """
        Zero-tool-use gate validation (from /cco pattern).

        Validates that agents actually executed work by checking for tool use evidence.
        Agents with tool_use_count == 0 are considered invalid and excluded from synthesis.

        Args:
            agent_results: List of AgentResult objects from agent execution

        Returns:
            Tuple of (filtered_results, validation_stats) where:
                - filtered_results: List of AgentResult objects that passed validation
                - validation_stats: Dict with validation statistics
        """
        total_agents = len(agent_results)
        invalid_agents = []
        valid_results = []

        for result in agent_results:
            # Check if agent has tool use evidence
            # For ResultEnvelope pattern, check if envelope metrics indicate tool use
            has_tool_use = False

            if result.envelope and result.envelope.is_valid():
                # Check envelope metrics for tool use evidence
                metrics = result.envelope.metrics
                # Look for tool_use_count or other evidence of actual work
                if metrics.get("tool_use_count", 0) > 0:
                    has_tool_use = True
                # Also consider findings with locations as evidence of work
                elif result.findings:
                    # Check if findings have actual locations (line numbers)
                    for finding in result.findings:
                        location = finding.get("location", "")
                        if ":" in location:  # Has file:line format
                            has_tool_use = True
                            break
            else:
                # Legacy format: check if findings have locations
                for finding in result.findings:
                    location = finding.get("location", "")
                    if ":" in location:  # Has file:line format
                        has_tool_use = True
                        break

            if has_tool_use:
                valid_results.append(result)
            else:
                invalid_agents.append(result.agent_name)
                logger.warning(
                    f"Agent '{result.agent_name}' returned 0 tool uses — "
                    f"invalid type or unresolvable. Excluding from synthesis."
                )

        # Calculate validation statistics
        failed_percentage = len(invalid_agents) / total_agents if total_agents > 0 else 0
        should_stop = failed_percentage > self.config.max_failed_agent_percentage

        validation_stats = {
            "total_agents": total_agents,
            "valid_agents": len(valid_results),
            "invalid_agents": len(invalid_agents),
            "invalid_agent_names": invalid_agents,
            "failed_percentage": round(failed_percentage * 100, 1),
            "should_stop_synthesis": should_stop,
            "threshold_percentage": round(self.config.max_failed_agent_percentage * 100, 1),
        }

        # Log validation result
        if invalid_agents:
            logger.info(
                f"Zero-tool-use gate: {len(invalid_agents)}/{total_agents} agents invalid "
                f"({validation_stats['failed_percentage']}%)"
            )

        return valid_results, validation_stats

    def select_agents(
        self,
        mode: str = "standard",
        include: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
        change_type: Optional[str] = None,
        file_extensions: Optional[Set[str]] = None,
    ) -> List[str]:
        """Select agents to run based on mode and filters."""
        return select_agents(mode, include, exclude, change_type, file_extensions)

    def generate_agent_prompts(
        self,
        agents: List[str],
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate prompts for each agent.

        Args:
            agents: List of agent names
            context: Context dict with keys:
                - git_diff: Git diff output
                - file_list: List of changed files
                - target_scope: Git scope being reviewed
                - mode: Review mode

        Returns:
            Dict mapping agent name to prompt string
        """
        prompts = {}

        # Build common context header
        context_header = self._build_context_header(context)

        for agent_name in agents:
            agent_config = AGENT_REGISTRY.get(agent_name, {})
            agent_focus = agent_config.get("focus", "")
            token_limit = agent_config.get("token_limit", 10)

            prompt = f"""You are reviewing SOURCE CODE for {agent_focus}.

{context_header}

## ADVERSARIAL REVIEW FRAMEWORK

This is a CRITICAL, ADVERSARIAL PASS to find failure modes in the code. Think like a hostile but fair reviewer who wants to break the artifact.

**Adversarial Mindset:**
- Assume hostile inputs, malformed data, and edge cases
- Look for failure modes, not just correctness issues
- Consider concurrent access, race conditions, and timing attacks
- Question assumptions about external systems, file paths, and state
- Assume nothing works as intended unless explicitly verified

**Detection Focus:**
- State-transition bugs: invalid states, missing validation, illegal transitions
- Invariants violations: ID collision, referential integrity, uniqueness
- I/O assumption bugs: path validation, file existence, external service assumptions
- Logic errors: off-by-one, wrong operators, inverted conditionals
- Performance issues: N+1 patterns, bottlenecks, async issues

TOKEN CONSTRAINTS:
- Return at most {token_limit} findings total
- Prioritize: blockers > high > medium > low
- If you find more than 3 instances of the same pattern, group as one finding with count
- Keep each field concise (problem < 80 chars, recommendation < 120 chars)

For each issue, provide:
{{
  "id": "{agent_name.upper()[:4]}-XXX",
  "severity": "blocker|high|medium|low",
  "location": "file:line",
  "problem": "What is wrong (brief)",
  "impact": "Why it matters (brief)",
  "recommendation": "Specific fix (brief)"
}}

Respond ONLY with valid JSON array. No prose."""
            prompts[agent_name] = prompt

        return prompts

    def _build_context_header(self, context: Dict[str, Any]) -> str:
        """Build common context header for all agent prompts."""
        lines = [
            f"Review scope: {context.get('target_scope', 'unknown')}",
            f"Review mode: {context.get('mode', 'standard')}",
        ]

        if "file_list" in context:
            files = context["file_list"]
            if isinstance(files, list):
                # Apply path scoping filter (from /cco pattern)
                if self.config.enable_context_filtering:
                    filtered_files = self.path_filter.filter_paths(files, max_files=100)
                    excluded_stats = self.path_filter.get_excluded_count(files)

                    lines.append(
                        f"\nChanged files ({len(filtered_files)} shown, {sum(excluded_stats.values())} excluded):"
                    )
                    for f in filtered_files[:20]:  # Limit to first 20 files
                        lines.append(f"  - {f}")
                    if len(filtered_files) > 20:
                        lines.append(f"  ... and {len(filtered_files) - 20} more")

                    # Log exclusion statistics
                    if sum(excluded_stats.values()) > 0:
                        logger.info(f"Path scoping: excluded {excluded_stats}")
                else:
                    lines.append(f"\nChanged files ({len(files)}):")
                    for f in files[:20]:  # Limit to first 20 files
                        lines.append(f"  - {f}")
                    if len(files) > 20:
                        lines.append(f"  ... and {len(files) - 20} more")

        if "git_diff" in context:
            diff = context["git_diff"]
            if isinstance(diff, str) and len(diff) > 10000:
                # Truncate large diffs
                lines.append(f"\nGit diff (truncated to 5000 chars):\n{diff[:5000]}...")
            else:
                lines.append(f"\nGit diff:\n{diff}")

        # Add path scoping directive if enabled
        if self.config.enable_context_filtering:
            lines.append("\n" + generate_filter_prompt_directive())

        return "\n".join(lines)

    def parse_agent_output(
        self,
        agent_name: str,
        output: str,
    ) -> AgentResult:
        """
        Parse agent output into structured findings.

        Handles both legacy JSON output and Result Envelope format.

        Args:
            agent_name: Name of the agent
            output: Raw output string from agent

        Returns:
            AgentResult with parsed findings and optional envelope
        """
        result = AgentResult(agent_name=agent_name, status="success", envelope=None)

        try:
            # Try to parse as Result Envelope first (new format)
            output_stripped = output.strip()
            if output_stripped.startswith("{") and "artifact" in output_stripped:
                envelope_data = json.loads(output_stripped)

                # Validate envelope fields
                if "status" in envelope_data and "artifact" in envelope_data:
                    # Read full findings from artifact
                    artifact_path = envelope_data.get("artifact", "")
                    artifact_data = self.read_agent_artifact(artifact_path)

                    if artifact_data and "findings" in artifact_data:
                        result.findings = artifact_data["findings"]
                        result.envelope = ResultEnvelope(
                            status=envelope_data.get("status", "done"),
                            artifact=envelope_data.get("artifact"),
                            summary=envelope_data.get("summary", ""),
                            metrics=envelope_data.get("metrics", {}),
                        )
                        result.token_count = len(output.split())
                    else:
                        result.status = "error"
                        result.error_message = f"Failed to read artifact: {artifact_path}"

                    return result

            # Legacy format: Try to parse as JSON array
            findings = json.loads(output_stripped)

            if isinstance(findings, list):
                result.findings = findings
                result.token_count = len(output.split())
            elif isinstance(findings, dict):
                # Some agents might return a dict with "findings" key
                result.findings = findings.get("findings", [])
                result.token_count = len(output.split())
            else:
                result.status = "error"
                result.error_message = f"Unexpected output type: {type(findings)}"

        except json.JSONDecodeError as e:
            result.status = "error"
            result.error_message = f"JSON parse error: {e}"
            # Try to extract any valid JSON from the output
            try:
                # Look for JSON array in the output
                match = re.search(r"\[.*\]", output, re.DOTALL)
                if match:
                    findings = json.loads(match.group(0))
                    if isinstance(findings, list):
                        result.findings = findings
                        result.status = "partial"
                        result.error_message = "Extracted partial JSON from output"
            except Exception:
                pass

        return result

    def aggregate_findings(
        self,
        agent_results: List[AgentResult],
        mode: str = "standard",
        file_list: Optional[List[str]] = None,
        git_scope: str = "",
        session_id: str = "",
        line_counts: Optional[Dict[str, int]] = None,
        cross_file_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate findings from all agents by severity.

        Supports both legacy AgentResult objects and ResultEnvelope pattern.
        Applies zero-tool-use gate before aggregation.

        Enhanced metadata extraction for CKS cross-session learning:
        - ReviewMetadata: Review context (mode, files, languages, git scope)
        - AgentConsensus: Which agents confirmed each finding
        - CrossFileMetadata: Import graph, circular deps, taint paths

        Args:
            agent_results: List of AgentResult objects (with optional envelopes)
            mode: Review mode (triage/standard/deep/comprehensive)
            file_list: List of files being reviewed
            git_scope: Git diff scope (e.g., "main...HEAD")
            session_id: Unique session identifier
            line_counts: Optional dict mapping file paths to line counts
            cross_file_stats: Optional cross-file analysis statistics

        Returns:
            Dict with aggregated findings, statistics, and enhanced metadata
        """
        # Apply zero-tool-use gate (from /cco pattern)
        validated_results, validation_stats = self._validate_agent_tool_use(agent_results)

        # Check if too many agents failed validation
        if validation_stats["should_stop_synthesis"]:
            logger.error(
                f"Zero-tool-use gate: {validation_stats['failed_percentage']}% agents failed, "
                f"exceeds threshold of {validation_stats['threshold_percentage']}%. "
                f"Stopping synthesis."
            )
            return {
                "findings": [],
                "statistics": {
                    **validation_stats,
                    "synthesis_stopped": True,
                    "reason": "Too many agents failed zero-tool-use validation",
                },
            }

        all_findings = []
        stats = {
            "total_agents": len(agent_results),
            "validated_agents": validation_stats["valid_agents"],
            "invalid_agents": validation_stats["invalid_agents"],
            "successful_agents": 0,
            "error_agents": 0,
            "total_findings": 0,
            "by_severity": {
                "blocker": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "by_agent": {},
            "envelope_metrics": {
                "agents_with_envelopes": 0,
                "total_artifact_bytes": 0,
                "total_findings_from_artifacts": 0,
            },
            "validation": validation_stats,
        }

        for result in validated_results:
            if result.status == "success":
                stats["successful_agents"] += 1
            else:
                stats["error_agents"] += 1

            # Track envelope metrics if present
            if result.envelope and result.envelope.is_valid():
                stats["envelope_metrics"]["agents_with_envelopes"] += 1
                stats["envelope_metrics"]["total_artifact_bytes"] += result.envelope.metrics.get(
                    "artifact_bytes", 0
                )
                stats["envelope_metrics"]["total_findings_from_artifacts"] += (
                    result.envelope.metrics.get("finding_count", 0)
                )

            all_findings.extend(result.findings)
            stats["by_agent"][result.agent_name] = len(result.findings)

        # Count by severity
        for finding in all_findings:
            severity = finding.get("severity", "").lower()
            if "blocker" in severity:
                stats["by_severity"]["blocker"] += 1
            elif "high" in severity or "critical" in severity:
                stats["by_severity"]["high"] += 1
            elif "medium" in severity or "med" in severity:
                stats["by_severity"]["medium"] += 1
            elif "low" in severity:
                stats["by_severity"]["low"] += 1

        stats["total_findings"] = len(all_findings)

        # Sort findings by severity (blockers first)
        severity_order = {"blocker": 0, "high": 1, "critical": 1, "medium": 2, "med": 2, "low": 3}
        all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "").lower(), 99))

        # Store high-confidence findings to CKS for cross-session learning
        # Extract enhanced metadata for CKS storage
        review_metadata: Optional[ReviewMetadata] = None
        agent_consensus: Optional[AgentConsensus] = None
        cross_file_metadata: Optional[CrossFileMetadata] = None

        # Count storeable findings (severity ≥ high, confidence ≥ 80%)
        storeable_count = sum(
            1
            for f in all_findings
            if f.get("severity", "").lower() in ("blocker", "high", "critical")
            and f.get("confidence", 100) >= 80
            and ":" in f.get("location", "")
        )

        if storeable_count > 0:
            # Extract review metadata from context
            if file_list:
                try:
                    review_metadata = self.memory.extract_review_metadata(
                        file_list=file_list,
                        mode=mode,
                        git_scope=git_scope,
                        session_id=session_id,
                        line_counts=line_counts,
                    )
                except Exception as e:
                    logger.warning(f"Failed to extract review metadata: {e}")

            # Extract agent consensus from validated results
            try:
                agent_consensus = self.memory.extract_agent_consensus(
                    validated_results=validated_results,
                )
            except Exception as e:
                logger.warning(f"Failed to extract agent consensus: {e}")

            # Build cross-file metadata from analyzer statistics
            if cross_file_stats:
                try:
                    cross_file_metadata = CrossFileMetadata(
                        import_graph_nodes=cross_file_stats.get("total_modules", 0),
                        import_graph_edges=cross_file_stats.get("total_imports", 0),
                        circular_dependencies=cross_file_stats.get("circular_dependencies", []),
                        taint_paths=cross_file_stats.get("taint_paths", []),
                        hot_spots=cross_file_stats.get("hot_spots", []),
                    )
                except Exception as e:
                    logger.warning(f"Failed to build cross-file metadata: {e}")

            # Format storage prompt with enhanced metadata
            try:
                storage_prompt = self.memory.format_storage_prompt(
                    findings=all_findings,
                    review_metadata=review_metadata,
                    validated_results=validated_results,
                    cross_file_metadata=cross_file_metadata,
                )
                stats["memory_storage"] = {
                    "eligible_for_storage": storeable_count,
                    "total_findings": len(all_findings),
                    "storage_prompt_generated": True,
                    "enhanced_metadata_extracted": {
                        "review_metadata": review_metadata is not None,
                        "agent_consensus": agent_consensus is not None,
                        "cross_file_metadata": cross_file_metadata is not None,
                    },
                }
                logger.info(
                    f"{storeable_count} findings eligible for CKS storage with enhanced metadata"
                )
            except Exception as e:
                logger.warning(f"Failed to generate storage prompt: {e}")
                stats["memory_storage"] = {
                    "eligible_for_storage": storeable_count,
                    "total_findings": len(all_findings),
                    "note": "Enhanced metadata extraction failed",
                }

        return {
            "findings": all_findings,
            "statistics": stats,
        }

    # GTO skill coverage logging
    try:
        _append_skill_coverage(
            target_key="skills/uci",
            skill="/uci",
            terminal_id="cli",
            git_sha=None,
        )
    except Exception:
        pass

    def sanitize_log(self, content: str) -> str:
        """
        Sanitize sensitive data from log content.

        Args:
            content: Raw log content

        Returns:
            Sanitized content with sensitive data redacted
        """

        def replace_match(match):
            return f"[REDACTED:{match.lastgroup}]"

        return self._sanitize_regex.sub(replace_match, content)

    def write_agent_log(
        self,
        agent_name: str,
        prompt: str,
        output: str,
        result: AgentResult,
    ) -> Path:
        """
        Write sanitized agent execution log.

        Args:
            agent_name: Name of the agent
            prompt: Prompt sent to agent
            output: Raw output from agent
            result: Parsed agent result

        Returns:
            Path to log file
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = self.log_dir / f"agent-{agent_name}-{timestamp}.jsonl"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "status": result.status,
            "finding_count": len(result.findings),
            "token_count": result.token_count,
            "execution_time": result.execution_time,
        }

        if result.error_message:
            log_entry["error"] = result.error_message

        # Write sanitized log
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
            f.write("// PROMPT\n")
            f.write(self.sanitize_log(prompt) + "\n")
            f.write("// OUTPUT\n")
            f.write(self.sanitize_log(output) + "\n")

        return log_file

    def write_agent_artifact(
        self,
        agent_name: str,
        findings: List[Dict[str, Any]],
        prompt: str = "",
        output: str = "",
    ) -> str:
        """
        Write detailed agent output to artifact file for later retrieval.

        This implements the Result Envelope Pattern: subagents write
        detailed findings to disk, returning only a small envelope.

        Args:
            agent_name: Name of the agent
            findings: List of finding dicts
            prompt: Original prompt (for debugging)
            output: Raw output (for debugging)

        Returns:
            Relative path to artifact file (from .claude/.state/uci/)
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        artifact_file = self.log_dir / f"artifact-{agent_name}-{timestamp}.json"

        artifact_data = {
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "findings": findings,
            "finding_count": len(findings),
        }

        # Include debug data if requested (truncated to prevent bloat)
        if prompt:
            artifact_data["prompt_preview"] = prompt[:500] + "..." if len(prompt) > 500 else prompt
        if output:
            artifact_data["output_preview"] = output[:500] + "..." if len(output) > 500 else output

        with open(artifact_file, "w", encoding="utf-8") as f:
            json.dump(artifact_data, f, indent=2)

        # Return relative path from state dir
        return f"uci/artifact-{agent_name}-{timestamp}.json"

    def read_agent_artifact(
        self,
        artifact_path: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Read agent artifact from disk.

        Args:
            artifact_path: Relative path to artifact file

        Returns:
            Artifact data dict, or None if file not found
        """
        # Convert relative path to absolute
        full_path = self.log_dir.parent / artifact_path

        try:
            with open(full_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read artifact {artifact_path}: {e}")
            return None

    def create_result_envelope(
        self,
        agent_name: str,
        findings: List[Dict[str, Any]],
        status: str = "done",
        prompt: str = "",
        output: str = "",
    ) -> ResultEnvelope:
        """
        Create result envelope for subagent output.

        The envelope contains only a small summary; detailed findings
        are written to disk as an artifact.

        Args:
            agent_name: Name of the agent
            findings: List of finding dicts
            status: "done", "blocked", or "retry"
            prompt: Original prompt (optional, for debugging)
            output: Raw output (optional, for debugging)

        Returns:
            ResultEnvelope with artifact path
        """
        # Write detailed findings to artifact
        artifact_path = self.write_agent_artifact(agent_name, findings, prompt, output)

        # Generate summary (≤3 lines, no code blocks)
        finding_count = len(findings)
        high_count = sum(
            1 for f in findings if f.get("severity", "").lower() in ("high", "blocker", "critical")
        )

        summary_lines = [
            f"{agent_name}: {finding_count} findings",
            f"{high_count} high-severity issues" if high_count > 0 else "No critical issues",
        ]

        # Get artifact size for metrics
        full_artifact_path = self.log_dir / artifact_path.replace("uci/", "")
        artifact_bytes = full_artifact_path.stat().st_size if full_artifact_path.exists() else 0

        return ResultEnvelope(
            status=status,
            artifact=artifact_path,
            summary="\n".join(summary_lines),
            metrics={
                "artifact_bytes": artifact_bytes,
                "finding_count": finding_count,
                "high_severity_count": high_count,
            },
        )

    def analyze_cross_file(
        self,
        file_list: List[str],
        project_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Perform cross-file analysis (from /meta-review pattern).

        Runs import graph analysis, circular dependency detection, and taint
        propagation analysis to identify cross-file issues.

        Args:
            file_list: List of file paths to analyze
            project_root: Root directory of the project (defaults to current dir)

        Returns:
            Dict with cross-file findings and statistics
        """
        if not self.config.enable_cross_file_analysis:
            return {
                "enabled": False,
                "reason": "Cross-file analysis disabled in config",
            }

        project_root = Path(project_root) if project_root else Path.cwd()

        # Initialize cross-file analyzer
        if self.cross_file_analyzer is None:
            self.cross_file_analyzer = CrossFileAnalyzer(project_root)

        # Generate cross-file findings
        cross_file_findings = self.cross_file_analyzer.generate_cross_file_findings(
            file_list=file_list
        )

        # Get import graph statistics
        graph_stats = self.cross_file_analyzer.get_statistics()

        return {
            "enabled": True,
            "findings": cross_file_findings,
            "statistics": graph_stats,
            "total_cross_file_findings": len(cross_file_findings),
        }

    def rotate_logs(self) -> int:
        """
        Remove logs older than retention period.

        Returns:
            Number of logs removed
        """
        cutoff_date = datetime.now() - timedelta(days=self.config.log_retention_days)
        removed = 0

        for log_file in self.log_dir.glob("agent-*.jsonl"):
            try:
                # Extract timestamp from filename
                match = re.search(r"(\d{8}-\d{6})", log_file.name)
                if match:
                    file_date = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
                    if file_date < cutoff_date:
                        log_file.unlink()
                        removed += 1
            except Exception as e:
                logger.warning(f"Failed to process log file {log_file}: {e}")

        return removed

    def generate_task_calls(
        self,
        agents: List[str],
        prompts: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Generate Task tool call specifications for parallel execution.

        This is the core method that creates the specifications for parallel
        agent execution. The caller (typically the skill itself) will use
        these specifications to make actual Task tool calls.

        Args:
            agents: List of agent names to execute
            prompts: Dict mapping agent name to prompt string

        Returns:
            List of dicts with Task tool call specifications. Each dict has:
                - subagent_type: The agent type to dispatch
                - prompt: The prompt to send
                - description: Human-readable description
        """
        task_calls = []

        for agent_name in agents:
            agent_config = AGENT_REGISTRY.get(agent_name, {})
            subagent_type = agent_config.get("subagent_type", "general-purpose")

            task_calls.append(
                {
                    "subagent_type": subagent_type,
                    "prompt": prompts.get(agent_name, ""),
                    "description": f"{agent_name.replace('-', ' ')} review",
                }
            )

        return task_calls

    def create_execution_plan(
        self,
        mode: str = "standard",
        include: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
        change_type: Optional[str] = None,
        file_extensions: Optional[Set[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create complete execution plan for parallel agent review.

        This is the main entry point that orchestrates the entire process:
        1. Selects agents based on mode/filters
        2. Generates prompts for each agent
        3. Creates Task tool call specifications
        4. Returns complete execution plan

        Args:
            mode: Review mode (triage|standard|deep|comprehensive)
            include: Set of agents to include (overrides mode)
            exclude: Set of agents to exclude
            change_type: Change type for custom selection
            file_extensions: File extensions for triggered agents
            context: Review context (git diff, file list, etc.)

        Returns:
            Execution plan dict with:
                - agents: List of selected agent names
                - prompts: Dict of agent prompts
                - task_calls: List of Task tool call specifications
                - metadata: Execution metadata
        """
        context = context or {}

        # Retrieve context from CKS for cross-session learning
        review_scope = context.get("target_scope", "unknown")
        file_list = context.get("file_list", [])

        try:
            # Run memory retrieval synchronously (currently returns immediately)
            import asyncio

            memory_context = asyncio.run(
                self.memory.retrieve_context(review_scope, file_list, mode)
            )

            # Add memory context to the prompt context if available
            if memory_context and memory_context.has_context():
                context["memory_context"] = memory_context.format_for_prompt()
                logger.info(
                    f"Retrieved {len(memory_context.similar_findings)} similar findings from CKS"
                )
            else:
                context["memory_context"] = "No relevant past context found."
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            context["memory_context"] = "Memory context unavailable."

        # Select agents
        agents = self.select_agents(mode, include, exclude, change_type, file_extensions)

        # Apply per-agent triggers (additive - fires on top of mode selection)
        triggered = get_triggered_agents(
            file_paths=file_list,
            current_mode=mode,
            current_agents=agents,
        )
        for agent in triggered:
            if agent not in agents:
                agents.append(agent)

        # Generate prompts
        prompts = self.generate_agent_prompts(agents, context)

        # Generate task call specifications
        task_calls = self.generate_task_calls(agents, prompts)

        return {
            "agents": agents,
            "prompts": prompts,
            "task_calls": task_calls,
            "metadata": {
                "mode": mode,
                "agent_count": len(agents),
                "triggered_agents": triggered,
                "timestamp": datetime.now().isoformat(),
                "context_keys": list(context.keys()),
            },
        }

    def detect_blind_spots(
        self,
        file_paths: list[str],
        covered_categories: set[str],
        project_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Detect blind spots - categories with risk signals but no recent coverage.

        This runs AFTER agent execution to detect categories that should have been
        checked based on code risk patterns, but weren't covered in this session
        or recent history.

        Args:
            file_paths: Code files that were reviewed
            covered_categories: Categories that were checked this session
            project_root: Project root for state files

        Returns:
            Dict with blind_spot_report and is_meaningful flag
        """
        # Initialize on first use (lazy loading)
        if self.blind_spot_detector is None:
            self.blind_spot_detector = BlindSpotDetector()

        # Run blind spot detection
        report = self.blind_spot_detector.detect_blind_spots(
            file_paths=file_paths,
            covered_categories=covered_categories,
            project_root=project_root,
        )

        # Render the report
        report_text = self.blind_spot_detector.render_report(report)

        return {
            "blind_spot_report": report,
            "report_text": report_text,
            "is_meaningful": report.is_meaningful,
            "coverage_summary": report.coverage_summary,
            "findings_count": len(report.findings),
        }
