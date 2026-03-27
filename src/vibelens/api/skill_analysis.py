"""Skill analysis endpoints — LLM-powered workflow pattern detection and skill recommendations."""

from fastapi import APIRouter, Header, HTTPException

from vibelens.deps import get_skill_analysis_store, is_demo_mode, is_test_mode
from vibelens.llm.backend import InferenceError
from vibelens.models.skill.skills import SkillAnalysisResult
from vibelens.schemas.skills import SkillAnalysisMeta, SkillAnalysisRequest
from vibelens.services.skill import analyze_skills
from vibelens.services.skill.mock import build_mock_skill_result

router = APIRouter(prefix="/skills/analysis", tags=["skill-analysis"])


@router.post("")
async def skill_analysis(
    body: SkillAnalysisRequest, x_session_token: str | None = Header(None)
) -> SkillAnalysisResult:
    """Run skill analysis on specified sessions.

    Args:
        body: Request with session IDs and analysis mode.
        x_session_token: Browser tab token for upload scoping.

    Returns:
        SkillAnalysisResult with patterns and mode-specific output.
    """
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="session_ids must not be empty")

    if is_test_mode() or is_demo_mode():
        return build_mock_skill_result(body.session_ids, body.mode)

    try:
        return await analyze_skills(body.session_ids, body.mode, session_token=x_session_token)
    except ValueError as exc:
        status = 503 if "inference backend" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except InferenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/history")
async def skill_analysis_history() -> list[SkillAnalysisMeta]:
    """List all persisted skill analyses, newest first."""
    return get_skill_analysis_store().list_analyses()


@router.get("/{analysis_id}")
async def skill_analysis_load(analysis_id: str) -> SkillAnalysisResult:
    """Load a persisted skill analysis by ID.

    Args:
        analysis_id: Unique analysis identifier.

    Returns:
        Full SkillAnalysisResult.
    """
    result = get_skill_analysis_store().load(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return result


@router.delete("/{analysis_id}")
async def skill_analysis_delete(analysis_id: str) -> dict[str, bool]:
    """Delete a persisted skill analysis.

    Args:
        analysis_id: Unique analysis identifier.

    Returns:
        Success status.
    """
    deleted = get_skill_analysis_store().delete(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return {"deleted": True}
