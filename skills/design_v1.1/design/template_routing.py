"""Template routing for NTP v1.1 — maps (mode, scope) to TemplateProfile."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateProfile:
    name: str
    depth: str  # "precedent" | "fast" | "domain"
    quality_bar: str  # "high" | "medium" | "low"
    traces: int = 1
    challenges: int = 1


def route_template(mode: str, scope: str) -> TemplateProfile:
    """Map mode + scope to a TemplateProfile."""
    mode = mode.lower()
    scope = scope.lower()

    if mode == "system":
        if scope in ("backend", "frontend", "data"):
            return TemplateProfile(
                name="system_precedent_deep",
                depth="precedent",
                quality_bar="high",
                traces=2,
                challenges=2,
            )
        # scope == "all"
        return TemplateProfile(
            name="system_precedent_deep",
            depth="precedent",
            quality_bar="high",
            traces=2,
            challenges=2,
        )

    if mode == "rca":
        return TemplateProfile(
            name="rca_fast",
            depth="fast",
            quality_bar="medium",
            traces=1,
            challenges=1,
        )

    if mode == "component":
        return TemplateProfile(
            name="component_domain",
            depth="domain",
            quality_bar="medium",
            traces=1,
            challenges=1,
        )

    # Fallback
    return TemplateProfile(
        name="system_precedent_deep",
        depth="precedent",
        quality_bar="high",
        traces=2,
        challenges=2,
    )
