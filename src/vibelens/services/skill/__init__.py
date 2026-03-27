"""Skill-related services — analysis, persistence, and digest formatting."""

from vibelens.models.skill.skills import SkillAnalysisResult, SkillMode
from vibelens.services.skill.digest import digest_step_signals_for_skills
from vibelens.services.skill.store import SkillAnalysisStore

__all__ = [
    "SkillAnalysisStore",
    "analyze_skills",
    "digest_step_signals_for_skills",
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
