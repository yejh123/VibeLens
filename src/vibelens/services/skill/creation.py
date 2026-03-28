"""Skill creation mode — generate new skill definitions from workflow patterns."""

import json
import time

from vibelens.deps import get_skill_analysis_store
from vibelens.llm.prompts.skill_creation import SKILL_CREATION_PROMPT
from vibelens.models.inference import InferenceRequest
from vibelens.models.prompts import AnalysisPrompt
from vibelens.models.skill.skills import SkillAnalysisResult, SkillMode
from vibelens.services.friction.signals import build_step_signals
from vibelens.services.skill.digest import digest_step_signals_for_skills
from vibelens.services.skill.retrieval import (
    _build_result,
    _cache,
    _gather_installed_skills,
    _get_cached,
    _load_sessions,
    _log_prompt,
    _log_response,
    _parse_llm_output,
    _require_backend,
    _skill_cache_key,
    _validate_patterns,
)


async def analyze_creation(
    session_ids: list[str], session_token: str | None = None
) -> SkillAnalysisResult:
    """Run creation-mode skill analysis: generate new skill definitions."""
    cache_key = _skill_cache_key(session_ids, SkillMode.CREATION)
    cached = _get_cached(cache_key)
    if cached:
        return cached

    backend = _require_backend()
    loaded_trajectories, loaded_ids, skipped_ids = _load_sessions(session_ids, session_token)

    if not loaded_trajectories:
        raise ValueError(f"No sessions could be loaded from: {session_ids}")

    signals = build_step_signals(loaded_trajectories)
    digest = digest_step_signals_for_skills(signals)

    prompt = SKILL_CREATION_PROMPT
    installed_skills = _gather_installed_skills()
    user_prompt = _render_creation_prompt(prompt, digest, len(loaded_ids), installed_skills)

    system_prompt = prompt.render_system()
    request = InferenceRequest(system=system_prompt, user=user_prompt)
    _log_prompt(system_prompt, user_prompt, loaded_ids, SkillMode.CREATION)

    result = await backend.generate(request)
    _log_response(result.text, loaded_ids, SkillMode.CREATION)

    llm_output = _parse_llm_output(result.text)
    validated_patterns = _validate_patterns(llm_output.workflow_patterns, loaded_trajectories)

    skill_result = _build_result(
        SkillMode.CREATION,
        validated_patterns,
        llm_output,
        loaded_ids,
        skipped_ids,
        backend,
        result.cost_usd,
    )
    get_skill_analysis_store().save(skill_result)

    _cache[cache_key] = (time.monotonic(), skill_result)
    return skill_result


def _render_creation_prompt(
    prompt: AnalysisPrompt, digest: str, session_count: int, installed_skills: list[dict]
) -> str:
    """Render creation-specific user prompt."""
    output_schema = json.dumps(prompt.output_model.model_json_schema(), indent=2)
    return prompt.render_user(
        session_count=session_count,
        session_digest=digest,
        output_schema=output_schema,
        installed_skills=installed_skills if installed_skills else None,
    )
