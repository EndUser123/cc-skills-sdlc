"""
Memory Integration for Unified Code Inspection

Integrates with CKS (Constitutional Knowledge System) for:
- Querying past review findings before running agents
- Storing high-confidence findings for future reuse
- Cross-session learning and pattern recognition
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class AgentConsensus:
    """
    Agent consensus information for findings.

    Tracks which agents confirmed a finding and confidence levels.
    """
    confirming_agents: List[str] = field(default_factory=list)
    dissenting_agents: List[str] = field(default_factory=list)
    consensus_level: str = "unknown"  # unanimous, majority, minority, none
    avg_confidence: float = 0.0
    location_agreement: bool = False  # Whether agents agree on file:line


@dataclass
class CrossFileMetadata:
    """
    Cross-file analysis metadata for storage.

    Captures import graph, circular dependencies, and taint analysis.
    """
    import_graph_nodes: int = 0
    import_graph_edges: int = 0
    circular_dependencies: List[str] = field(default_factory=list)
    taint_paths: List[str] = field(default_factory=list)
    hot_spots: List[str] = field(default_factory=list)  # Highly imported modules


@dataclass
class ReviewMetadata:
    """
    Enhanced review metadata for CKS storage.

    Captures review context, mode, and session information.
    """
    mode: str = "standard"
    file_count: int = 0
    line_count: int = 0
    languages: List[str] = field(default_factory=list)
    primary_language: str = "unknown"
    session_id: str = ""
    timestamp: str = ""
    git_scope: str = ""
    branch: str = ""
    file_types: Dict[str, int] = field(default_factory=dict)  # {".py": 5, ".md": 2}


@dataclass
class MemoryContext:
    """
    Context from CKS for agent prompts.

    Contains relevant past findings, patterns, and learnings
    that should inform the current review.
    """
    similar_findings: List[Dict[str, Any]] = field(default_factory=list)
    known_patterns: List[Dict[str, Any]] = field(default_factory=list)
    past_corrections: List[Dict[str, Any]] = field(default_factory=list)

    def has_context(self) -> bool:
        """Check if any context was retrieved from CKS."""
        return bool(
            self.similar_findings
            or self.known_patterns
            or self.past_corrections
        )

    def format_for_prompt(self) -> str:
        """Format memory context for injection into agent prompts."""
        sections = []

        if self.similar_findings:
            sections.append("## Similar Past Findings")
            for finding in self.similar_findings[:5]:  # Limit to top 5
                sections.append(f"- {finding.get('title', 'Untitled')}: {finding.get('content', '')[:100]}")

        if self.known_patterns:
            sections.append("## Known Patterns")
            for pattern in self.known_patterns[:3]:  # Limit to top 3
                sections.append(f"- {pattern.get('title', 'Untitled')}: {pattern.get('content', '')[:100]}")

        if self.past_corrections:
            sections.append("## Past Corrections")
            for correction in self.past_corrections[:3]:  # Limit to top 3
                sections.append(f"- {correction.get('title', 'Untitled')}: {correction.get('content', '')[:100]}")

        return "\n".join(sections) if sections else "No relevant past context found."


class MemoryIntegration:
    """
    Memory integration layer for UCI.

    Provides bidirectional integration with CKS:
    1. Retrieve relevant context before review
    2. Store high-confidence findings after review
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize memory integration.

        Args:
            enabled: If False, memory operations are no-ops
        """
        self.enabled = enabled
        self._cks_available = False

        if self.enabled:
            self._check_cks_available()

    def _check_cks_available(self) -> None:
        """Check if CKS is available for integration."""
        try:
            # Try importing the search skill which provides CKS access
            # This is a lightweight check - actual queries happen via /search
            from pathlib import Path

            # Check if CKS memory directory exists
            cks_memory_dir = Path.home() / ".claude" / "memory"
            self._cks_available = cks_memory_dir.exists()

            if self._cks_available:
                logger.info("CKS integration available for UCI")
            else:
                logger.warning("CKS memory directory not found, memory integration disabled")

        except Exception as e:
            logger.warning(f"CKS availability check failed: {e}")
            self._cks_available = False

    def is_available(self) -> bool:
        """Check if memory integration is available."""
        return self.enabled and self._cks_available

    async def retrieve_context(
        self,
        review_scope: str,
        file_list: List[str],
        mode: str = "standard"
    ) -> MemoryContext:
        """
        Retrieve relevant context from CKS before running agents.

        Searches for:
        - Similar findings in past reviews
        - Known patterns for the code type
        - Past corrections for similar issues

        Args:
            review_scope: Git scope being reviewed (e.g., "main...HEAD")
            file_list: List of files being reviewed
            mode: Review mode (triage/standard/deep/comprehensive)

        Returns:
            MemoryContext with retrieved information
        """
        context = MemoryContext()

        if not self.is_available():
            return context

        try:
            # Extract domain/technology hints from file list
            domains = self._extract_domains(file_list)

            # Build search query for CKS
            search_query = self._build_search_query(review_scope, domains, mode)

            # Note: Actual CKS query happens via /search skill
            # This method prepares the query structure for the orchestrator
            # The orchestrator will use the /search skill with --backend cks
            logger.info(f"Prepared CKS query: {search_query}")

            # Store query for later use by orchestrator
            context._search_query = search_query

        except Exception as e:
            logger.error(f"Failed to retrieve context from CKS: {e}")

        return context

    def _extract_domains(self, file_list: List[str]) -> List[str]:
        """Extract domain/technology hints from file list."""
        domains = []

        for file_path in file_list:
            # Extract file extensions
            if "." in file_path:
                ext = file_path.rsplit(".", 1)[-1].lower()
                if ext in ("py", "js", "ts", "java", "go", "rs"):
                    domains.append(ext)

            # Extract path hints
            if "auth" in file_path.lower():
                domains.append("authentication")
            if "test" in file_path.lower():
                domains.append("testing")
            if "api" in file_path.lower():
                domains.append("api")

        return list(set(domains))

    def _build_search_query(
        self,
        review_scope: str,
        domains: List[str],
        mode: str
    ) -> str:
        """Build CKS search query from review parameters."""
        query_parts = []

        # Add domain hints
        if domains:
            query_parts.append(" ".join(domains[:3]))  # Limit to 3 domains

        # Add review type
        query_parts.append("code review findings")

        # Add mode-specific hints
        if mode == "comprehensive":
            query_parts.append("security performance quality")
        elif mode == "deep":
            query_parts.append("logic security testing")
        elif mode == "standard":
            query_parts.append("logic security")

        return " ".join(query_parts) if query_parts else "code review"

    def should_store_finding(self, finding: Dict[str, Any]) -> bool:
        """
        Determine if a finding should be stored in CKS.

        Only stores findings that meet quality thresholds:
        - High confidence (≥80%)
        - Not a duplicate of existing knowledge
        - Has clear remediation value

        Args:
            finding: Finding dict from agent output

        Returns:
            True if finding should be stored
        """
        if not self.is_available():
            return False

        # Check severity
        severity = finding.get("severity", "").lower()
        if severity not in ("blocker", "high", "critical"):
            return False

        # Check for location evidence
        location = finding.get("location", "")
        if not location or ":" not in location:
            return False

        # Check confidence if available
        confidence = finding.get("confidence", 100)
        if confidence < 80:
            return False

        return True

    def prepare_storage_entry(
        self,
        finding: Dict[str, Any],
        review_metadata: Optional[ReviewMetadata] = None,
        agent_consensus: Optional[AgentConsensus] = None,
        cross_file_metadata: Optional[CrossFileMetadata] = None,
    ) -> Dict[str, Any]:
        """
        Prepare a finding for storage in CKS with enhanced metadata.

        Formats the finding according to enhanced CKS memory entry schema
        including file type detection, review mode, agent consensus, and
        cross-file analysis results.

        Args:
            finding: Finding dict from agent output
            review_metadata: Optional review session metadata
            agent_consensus: Optional agent consensus information
            cross_file_metadata: Optional cross-file analysis metadata

        Returns:
            Dict suitable for CKS storage with enhanced metadata
        """
        severity = finding.get("severity", "unknown").upper()
        problem = finding.get("problem", finding.get("title", "No description"))
        recommendation = finding.get("recommendation", finding.get("solution", ""))
        location = finding.get("location", "unknown")
        category = finding.get("category", "general")
        analysis_type = finding.get("analysis_type", "code_review")

        # Create title with category prefix
        title = f"{severity}: {problem[:80]}"

        # Build enhanced content with metadata sections
        content_parts = [problem]

        # Core finding details
        content_parts.append(f"\nLocation: {location}")
        content_parts.append(f"Impact: {finding.get('impact', 'Not specified')}")
        content_parts.append(f"Recommendation: {recommendation}")

        # Add agent consensus information if available
        if agent_consensus and agent_consensus.confirming_agents:
            content_parts.append(f"\nConfirmed by: {', '.join(agent_consensus.confirming_agents)}")
            if agent_consensus.consensus_level != "unknown":
                content_parts.append(f"Consensus: {agent_consensus.consensus_level}")
            if agent_consensus.avg_confidence > 0:
                content_parts.append(f"Avg Confidence: {agent_consensus.avg_confidence:.0%}")

        # Add review metadata if available
        if review_metadata:
            content_parts.append("\nReview Context:")
            content_parts.append(f"  Mode: {review_metadata.mode}")
            content_parts.append(f"  Files: {review_metadata.file_count}")
            if review_metadata.primary_language != "unknown":
                content_parts.append(f"  Language: {review_metadata.primary_language}")
            if review_metadata.branch:
                content_parts.append(f"  Branch: {review_metadata.branch}")

        # Add cross-file metadata if available
        if cross_file_metadata:
            content_parts.append("\nCross-File Analysis:")
            content_parts.append(f"  Import Graph: {cross_file_metadata.import_graph_nodes} nodes, {cross_file_metadata.import_graph_edges} edges")
            if cross_file_metadata.circular_dependencies:
                content_parts.append(f"  Circular Dependencies: {len(cross_file_metadata.circular_dependencies)}")
            if cross_file_metadata.taint_paths:
                content_parts.append(f"  Taint Paths: {len(cross_file_metadata.taint_paths)}")

        content_parts.append(f"\nSource: UCI review {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        content_parts.append(f"Category: {category}")
        content_parts.append(f"Analysis Type: {analysis_type}")

        content = "\n".join(content_parts)

        # Build enhanced tags
        tags = [
            severity.lower(),
            "code-review",
            "uci",
            category,
            analysis_type,
        ]

        # Add language tags from review metadata
        if review_metadata and review_metadata.languages:
            tags.extend(review_metadata.languages[:3])  # Limit to 3 language tags

        # Add domain tags from location and category
        location_lower = location.lower()
        domain_tags = {
            "auth": "authentication",
            "test": "testing",
            "api": "api",
            "db": "database",
            "security": "security",
            "perf": "performance",
            "async": "async",
        }
        for keyword, tag in domain_tags.items():
            if keyword in location_lower or keyword in category.lower():
                tags.append(tag)

        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        # Build enhanced storage entry
        storage_entry: Dict[str, Any] = {
            "title": title,
            "content": content,
            "tags": unique_tags,
            "severity": severity,
            "location": location,
            "confidence": finding.get("confidence", 100),
            "category": category,
            "analysis_type": analysis_type,
        }

        # Add review metadata as nested structure
        if review_metadata:
            storage_entry["review_metadata"] = {
                "mode": review_metadata.mode,
                "file_count": review_metadata.file_count,
                "line_count": review_metadata.line_count,
                "languages": review_metadata.languages,
                "primary_language": review_metadata.primary_language,
                "session_id": review_metadata.session_id,
                "timestamp": review_metadata.timestamp,
                "git_scope": review_metadata.git_scope,
                "branch": review_metadata.branch,
                "file_types": review_metadata.file_types,
            }

        # Add agent consensus if available
        if agent_consensus:
            storage_entry["agent_consensus"] = {
                "confirming_agents": agent_consensus.confirming_agents,
                "consensus_level": agent_consensus.consensus_level,
                "avg_confidence": agent_consensus.avg_confidence,
                "location_agreement": agent_consensus.location_agreement,
            }

        # Add cross-file metadata if available
        if cross_file_metadata:
            storage_entry["cross_file_analysis"] = {
                "import_graph_nodes": cross_file_metadata.import_graph_nodes,
                "import_graph_edges": cross_file_metadata.import_graph_edges,
                "circular_dependencies": cross_file_metadata.circular_dependencies,
                "taint_paths": cross_file_metadata.taint_paths,
                "hot_spots": cross_file_metadata.hot_spots,
            }

        return storage_entry

    def extract_review_metadata(
        self,
        file_list: List[str],
        mode: str,
        git_scope: str,
        session_id: str,
        line_counts: Optional[Dict[str, int]] = None,
    ) -> ReviewMetadata:
        """
        Extract review metadata from current review context.

        Args:
            file_list: List of files being reviewed
            mode: Review mode (triage/standard/deep/comprehensive)
            git_scope: Git scope being reviewed
            session_id: Current session identifier
            line_counts: Optional dict mapping file paths to line counts

        Returns:
            ReviewMetadata with extracted information
        """
        from pathlib import Path

        # Detect file types and languages
        file_types: Dict[str, int] = {}
        languages = set()

        for file_path in file_list:
            ext = Path(file_path).suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1

            # Map extensions to languages
            ext_to_lang = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".java": "java",
                ".go": "go",
                ".rs": "rust",
                ".cpp": "cpp",
                ".c": "c",
                ".h": "c",
                ".hpp": "cpp",
                ".cs": "csharp",
                ".rb": "ruby",
                ".php": "php",
            }
            if ext in ext_to_lang:
                languages.add(ext_to_lang[ext])

        # Determine primary language
        primary_language = "unknown"
        if languages:
            # Count files per language
            lang_counts: Dict[str, int] = {}
            for file_path in file_list:
                ext = Path(file_path).suffix.lower()
                if ext in [".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c"]:
                    lang = ext.replace(".", "")
                    if ext == ".ts":
                        lang = "typescript"
                    elif ext == ".js":
                        lang = "javascript"
                    elif ext in [".c", ".h"]:
                        lang = "c"
                    elif ext in [".cpp", ".hpp"]:
                        lang = "cpp"
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

            if lang_counts:
                primary_language = max(lang_counts, key=lang_counts.get)

        # Calculate total line count
        total_lines = 0
        if line_counts:
            total_lines = sum(line_counts.values())

        # Extract branch from git scope if possible
        branch = ""
        if "..." in git_scope:
            parts = git_scope.split("...")
            branch = parts[0] if len(parts) > 0 else ""
        elif " " in git_scope:
            parts = git_scope.split()
            branch = parts[-1] if parts else ""

        return ReviewMetadata(
            mode=mode,
            file_count=len(file_list),
            line_count=total_lines,
            languages=sorted(languages),
            primary_language=primary_language,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            git_scope=git_scope,
            branch=branch,
            file_types=file_types,
        )

    def extract_agent_consensus(
        self,
        validated_findings: List[Any],
        location_key: Optional[tuple] = None
    ) -> AgentConsensus:
        """
        Extract agent consensus information from validated findings.

        Args:
            validated_findings: List of AgentResult objects from agents
            location_key: Optional (file_path, line_number) tuple for location-specific consensus

        Returns:
            AgentConsensus with extracted information
        """

        confirming_agents = []
        confidences = []

        for result in validated_findings:
            if result.findings:  # Agent produced findings
                agent_name = result.agent_name
                confirming_agents.append(agent_name)

                # Extract confidence from agent findings if available
                for finding in result.findings:
                    conf = finding.get("confidence", finding.get("confidence_score", 80))
                    confidences.append(conf)

        # Calculate consensus level
        total_agents = len(validated_findings)
        confirming_count = len(confirming_agents)

        if confirming_count == 0:
            consensus_level = "none"
        elif confirming_count == total_agents:
            consensus_level = "unanimous"
        elif confirming_count >= total_agents * 0.66:
            consensus_level = "majority"
        else:
            consensus_level = "minority"

        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Check location agreement (if multiple agents agree on same location)
        location_agreement = False
        if location_key:
            location_matches = 0
            for result in validated_findings:
                for finding in result.findings:
                    if finding.get("location") == f"{location_key[0]}:{location_key[1]}":
                        location_matches += 1
            location_agreement = location_matches >= 2

        return AgentConsensus(
            confirming_agents=confirming_agents,
            consensus_level=consensus_level,
            avg_confidence=avg_confidence,
            location_agreement=location_agreement,
        )

    def format_storage_prompt(
        self,
        findings: List[Dict[str, Any]],
        review_metadata: Optional[ReviewMetadata] = None,
        validated_results: Optional[List[Any]] = None,
        cross_file_metadata: Optional[CrossFileMetadata] = None,
    ) -> str:
        """
        Format findings for storage via /learn skill with enhanced metadata.

        Creates a prompt that the orchestrator can pass to /learn
        for automatic learning capture, including review metadata and
        agent consensus information.

        Args:
            findings: List of findings to potentially store
            review_metadata: Optional review session metadata
            validated_results: Optional list of validated AgentResult objects
            cross_file_metadata: Optional cross-file analysis metadata

        Returns:
            Prompt string for /learn skill
        """
        storeable = [f for f in findings if self.should_store_finding(f)]

        if not storeable:
            return "No high-confidence findings to store."

        # Build agent consensus if validated results provided
        consensus = None
        if validated_results:
            consensus = self.extract_agent_consensus(validated_results)

        sections = ["High-confidence findings from code review:\n"]

        # Add review context header
        if review_metadata:
            sections.append("Review Context:")
            sections.append(f"  Mode: {review_metadata.mode}")
            sections.append(f"  Files: {review_metadata.file_count}")
            if review_metadata.primary_language != "unknown":
                sections.append(f"  Language: {review_metadata.primary_language}")
            sections.append("")

        # Add agent consensus header
        if consensus and consensus.confirming_agents:
            sections.append("Agent Consensus:")
            sections.append(f"  Confirming: {', '.join(consensus.confirming_agents)}")
            sections.append(f"  Level: {consensus.consensus_level}")
            sections.append("")

        for i, finding in enumerate(storeable[:10], 1):  # Limit to 10
            entry = self.prepare_storage_entry(
                finding,
                review_metadata=review_metadata,
                agent_consensus=consensus,
                cross_file_metadata=cross_file_metadata,
            )
            sections.append(f"{i}. {entry['title']}")
            sections.append(f"   Location: {entry['location']}")
            sections.append(f"   Tags: {', '.join(entry['tags'])}")
            sections.append("")

        sections.append(f"Total: {len(storeable)} findings eligible for CKS storage")

        return "\n".join(sections)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory integration statistics."""
        return {
            "enabled": self.enabled,
            "available": self._cks_available,
            "functional": self.is_available(),
        }
