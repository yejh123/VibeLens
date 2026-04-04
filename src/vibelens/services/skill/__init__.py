"""Skill-related services — analysis, persistence, and digest formatting."""

from vibelens.models.skill import (
    SkillAnalysisResult,
    SkillCreation,
    SkillMode,
    SkillProposalResult,
)
from vibelens.services.skill.store import SkillAnalysisStore

__all__ = [
    "SkillAnalysisStore",
    "analyze_proposals",
    "analyze_skills",
    "deep_create_skill",
]


async def analyze_skills(
    session_ids: list[str], mode: SkillMode, session_token: str | None = None
) -> SkillAnalysisResult:
    """Dispatch skill analysis to the appropriate mode handler."""
    if mode == SkillMode.RETRIEVAL:
        from vibelens.services.skill.retrieval import analyze_retrieval

        return await analyze_retrieval(session_ids, session_token)
    elif mode == SkillMode.CREATION:
        from vibelens.services.skill.creation import analyze_creation

        return await analyze_creation(session_ids, session_token)
    else:
        from vibelens.services.skill.evolvement import analyze_evolvement

        return await analyze_evolvement(session_ids, session_token)


async def analyze_proposals(
    session_ids: list[str], session_token: str | None = None
) -> SkillProposalResult:
    """Generate lightweight skill proposals from session analysis."""
    from vibelens.services.skill.creation import analyze_proposals as _analyze_proposals

    return await _analyze_proposals(session_ids, session_token)


async def deep_create_skill(
    proposal_name: str,
    proposal_description: str,
    proposal_rationale: str,
    addressed_patterns: list[str],
    session_ids: list[str],
    session_token: str | None = None,
) -> SkillCreation:
    """Generate full SKILL.md content for one approved proposal."""
    from vibelens.services.skill.creation import deep_create_skill as _deep_create

    return await _deep_create(
        proposal_name,
        proposal_description,
        proposal_rationale,
        addressed_patterns,
        session_ids,
        session_token,
    )
