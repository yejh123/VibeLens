"""Skill evolvement mode — suggest improvements to existing installed skills.

Two-step pipeline:
1. Select relevant skills (metadata only) via lightweight LLM call
2. Generate evolution suggestions with full SKILL.md content for selected skills
   (batched when many sessions)
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from vibelens.deps import get_central_skill_store, get_skill_analysis_store
from vibelens.llm.backend import InferenceBackend, InferenceError
from vibelens.llm.prompts.skill_evolution import (
    SKILL_EVOLUTION_PROMPT,
    SKILL_EVOLUTION_SYNTHESIS_PROMPT,
)
from vibelens.llm.prompts.skill_evolution_selection import (
    SKILL_EVOLUTION_SELECTION_PROMPT,
)
from vibelens.models.inference import InferenceRequest
from vibelens.models.skill import (
    SkillAnalysisResult,
    SkillEvolutionOutput,
    SkillMode,
    SkillSelectionOutput,
    WorkflowPattern,
)
from vibelens.models.trajectories import Trajectory
from vibelens.services.analysis_shared import (
    build_digest_from_contexts,
    build_system_kwargs,
    extract_all_contexts,
    get_cached,
    require_backend,
    run_batches_concurrent,
    save_analysis_log,
    truncate_digest_to_fit,
)
from vibelens.services.context_params import PRESET_MEDIUM
from vibelens.services.friction.digest import format_batch_digest
from vibelens.services.session_batcher import SessionBatch, build_batches
from vibelens.services.skill.retrieval import (
    SKILL_LOG_DIR,
    _cache,
    _gather_installed_skills,
    _skill_cache_key,
    _validate_patterns,
)
from vibelens.utils.json_extract import extract_json as _extract_json
from vibelens.utils.log import get_logger

logger = get_logger(__name__)

# Must be large enough for the LLM to produce complete edits for large skills
EVOLUTION_OUTPUT_TOKENS = 8192
EVOLUTION_SYNTHESIS_OUTPUT_TOKENS = 8192
EVOLUTION_TIMEOUT_SECONDS = 300


async def analyze_evolvement(
    session_ids: list[str], session_token: str | None = None
) -> SkillAnalysisResult:
    """Run evolvement-mode skill analysis: suggest improvements to installed skills.

    Two-step pipeline:
    1. Select relevant skills from installed catalog (metadata only, single call)
    2. Load full content for selected skills, batch evolution suggestions
    """
    cache_key = _skill_cache_key(session_ids, SkillMode.EVOLUTION)
    cached = get_cached(_cache, cache_key)
    if cached:
        return cached

    backend = require_backend()
    contexts, loaded_ids, skipped_ids = extract_all_contexts(
        session_ids, session_token, PRESET_MEDIUM
    )

    if not contexts:
        raise ValueError(f"No sessions could be loaded from: {session_ids}")

    # Collect all trajectories for pattern validation
    all_trajectories: list[Trajectory] = []
    for ctx in contexts:
        all_trajectories.extend(ctx.trajectory_group)

    run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_dir = SKILL_LOG_DIR / run_timestamp

    # Step 1: Select relevant skills (metadata only, single call with full digest)
    installed_metadata = _gather_installed_skills()
    if not installed_metadata:
        raise ValueError("No installed skills found for evolution analysis.")

    digest = build_digest_from_contexts(contexts)
    selection = await _select_relevant_skills(
        backend, digest, len(loaded_ids), installed_metadata, log_dir
    )

    # Step 2: Load full content for selected skills (shared across batches)
    selected_skills = _gather_selected_skill_contents(selection.relevant_skills)
    if not selected_skills:
        logger.warning("No matching skills found for selection: %s", selection.relevant_skills)
        selected_skills = _gather_all_skill_contents()

    # Step 3: Batch evolution inference
    batches = build_batches(contexts)
    logger.info("Skill evolution: %d sessions → %d batch(es)", len(loaded_ids), len(batches))

    tasks = [
        _infer_evolution_batch(backend, batch, selected_skills, log_dir, idx)
        for idx, batch in enumerate(batches)
    ]
    batch_results, batch_warnings = await run_batches_concurrent(tasks, "evolution")

    total_cost = (selection.cost_usd or 0.0) + sum(cost for _, cost in batch_results)

    # Single batch: use directly; multiple batches: synthesize
    if len(batch_results) == 1:
        llm_output = batch_results[0][0]
    else:
        llm_output, syn_cost = await _synthesize_evolution(
            backend, batch_results, len(loaded_ids), log_dir
        )
        total_cost += syn_cost

    validated_patterns = _validate_patterns(llm_output.workflow_patterns, all_trajectories)

    skill_result = _build_evolution_result(
        validated_patterns,
        llm_output,
        loaded_ids,
        skipped_ids,
        backend,
        total_cost if total_cost > 0 else None,
        batch_count=len(batches),
        warnings=batch_warnings,
    )
    get_skill_analysis_store().save(skill_result)

    _cache[cache_key] = (time.monotonic(), skill_result)
    return skill_result


async def _infer_evolution_batch(
    backend: InferenceBackend,
    batch: SessionBatch,
    selected_skills: list[dict],
    log_dir: Path,
    batch_index: int,
) -> tuple[SkillEvolutionOutput, float]:
    """Run LLM inference for one evolution batch.

    Args:
        backend: Configured inference backend.
        batch: Session batch with pre-extracted contexts.
        selected_skills: Skills with full SKILL.md content (shared across batches).
        log_dir: Timestamped directory for saving prompts and outputs.
        batch_index: Zero-based batch index for file naming.

    Returns:
        Tuple of (parsed evolution output, cost in USD).
    """
    digest = format_batch_digest(batch)
    session_count = len(batch.session_contexts)

    prompt = SKILL_EVOLUTION_PROMPT
    system_kwargs = build_system_kwargs(prompt.output_model, backend)
    system_prompt = prompt.render_system(**system_kwargs)

    # Truncate digest to fit context budget alongside full skill content
    non_digest_overhead = prompt.render_user(
        session_count=session_count,
        session_digest="",
        installed_skills=selected_skills,
    )
    digest = truncate_digest_to_fit(digest, system_prompt, non_digest_overhead)

    user_prompt = prompt.render_user(
        session_count=session_count,
        session_digest=digest,
        installed_skills=selected_skills,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=EVOLUTION_OUTPUT_TOKENS,
        timeout=EVOLUTION_TIMEOUT_SECONDS,
        json_schema=prompt.output_model.model_json_schema(),
    )

    if batch_index == 0:
        save_analysis_log(log_dir, "evolvement_system.txt", system_prompt)
    save_analysis_log(log_dir, f"evolvement_user_{batch_index}.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, f"evolvement_output_{batch_index}.txt", result.text)

    evolution_output = _parse_evolution_output(result.text)
    cost = result.cost_usd or 0.0
    return evolution_output, cost


async def _synthesize_evolution(
    backend: InferenceBackend,
    batch_results: list[tuple[SkillEvolutionOutput, float]],
    session_count: int,
    log_dir: Path,
) -> tuple[SkillEvolutionOutput, float]:
    """Merge evolution results from multiple batches via LLM synthesis.

    Args:
        backend: Configured inference backend.
        batch_results: Per-batch evolution outputs and costs.
        session_count: Total number of sessions analyzed.
        log_dir: Timestamped directory for saving prompts and outputs.

    Returns:
        Tuple of (merged SkillEvolutionOutput, synthesis cost in USD).
    """
    batch_data = [
        {
            "summary": output.summary,
            "user_profile": output.user_profile,
            "workflow_patterns": [
                {"title": p.title, "description": p.description, "gap": p.gap}
                for p in output.workflow_patterns
            ],
            "evolution_suggestions": [
                {
                    "skill_name": s.skill_name,
                    "rationale": s.rationale,
                    "edits": [
                        {
                            "old_string": e.old_string,
                            "new_string": e.new_string,
                            "replace_all": e.replace_all,
                        }
                        for e in s.edits
                    ],
                }
                for s in output.evolution_suggestions
            ],
        }
        for output, _ in batch_results
    ]

    prompt = SKILL_EVOLUTION_SYNTHESIS_PROMPT
    system_kwargs = build_system_kwargs(prompt.output_model, backend)
    system_prompt = prompt.render_system(**system_kwargs)
    user_prompt = prompt.render_user(
        batch_count=len(batch_results),
        session_count=session_count,
        batch_results=batch_data,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=EVOLUTION_SYNTHESIS_OUTPUT_TOKENS,
        timeout=EVOLUTION_TIMEOUT_SECONDS,
        json_schema=prompt.output_model.model_json_schema(),
    )

    save_analysis_log(log_dir, "evolvement_synthesis_system.txt", system_prompt)
    save_analysis_log(log_dir, "evolvement_synthesis_user.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, "evolvement_synthesis_output.txt", result.text)

    synthesis_output = _parse_evolution_output(result.text)
    cost = result.cost_usd or 0.0
    return synthesis_output, cost


class _SelectionResult:
    """Wrapper for skill selection LLM result with cost tracking."""

    def __init__(self, output: SkillSelectionOutput, cost_usd: float | None) -> None:
        self.relevant_skills = output.relevant_skills
        self.reasoning = output.reasoning
        self.cost_usd = cost_usd


async def _select_relevant_skills(
    backend: InferenceBackend,
    digest: str,
    session_count: int,
    installed_metadata: list[dict],
    log_dir: Path,
) -> _SelectionResult:
    """Step 1: LLM call to select which skills are relevant to the session patterns."""
    prompt = SKILL_EVOLUTION_SELECTION_PROMPT
    system_kwargs = build_system_kwargs(prompt.output_model, backend)
    system_prompt = prompt.render_system(**system_kwargs)

    # Truncate digest to fit context budget
    non_digest_overhead = prompt.render_user(
        session_count=session_count,
        session_digest="",
        installed_skills=installed_metadata,
    )
    truncated_digest = truncate_digest_to_fit(digest, system_prompt, non_digest_overhead)

    user_prompt = prompt.render_user(
        session_count=session_count,
        session_digest=truncated_digest,
        installed_skills=installed_metadata,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        json_schema=prompt.output_model.model_json_schema(),
    )

    save_analysis_log(log_dir, "selection_system.txt", system_prompt)
    save_analysis_log(log_dir, "selection_user.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, "selection_output.txt", result.text)

    output = _parse_selection_output(result.text)
    logger.info(
        "Skill selection: %d relevant skills: %s",
        len(output.relevant_skills),
        output.relevant_skills,
    )
    return _SelectionResult(output=output, cost_usd=result.cost_usd)


def _parse_selection_output(text: str) -> SkillSelectionOutput:
    """Parse LLM output into SkillSelectionOutput."""
    if not text or not text.strip():
        raise InferenceError("LLM returned empty response for skill selection.")

    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
        return SkillSelectionOutput.model_validate(data)
    except json.JSONDecodeError as exc:
        preview = json_str[:500] if len(json_str) > 500 else json_str
        raise InferenceError(
            f"Selection output is not valid JSON. Preview: {preview!r}. Error: {exc}"
        ) from exc
    except ValidationError as exc:
        raise InferenceError(
            f"Selection JSON does not match SkillSelectionOutput schema: {exc}"
        ) from exc


def _gather_selected_skill_contents(skill_names: list[str]) -> list[dict]:
    """Load full SKILL.md content for only the selected skills."""
    managed_store = get_central_skill_store()
    skills = managed_store.get_cached()
    name_set = {name.lower() for name in skill_names}
    result = []
    for skill_info in skills:
        if skill_info.name.lower() not in name_set:
            continue
        content = managed_store.read_content(skill_info.name)
        result.append(
            {
                "name": skill_info.name,
                "description": skill_info.description,
                "content": content or "",
            }
        )
    return result


def _gather_all_skill_contents() -> list[dict]:
    """Fallback: load all installed skills with full content."""
    managed_store = get_central_skill_store()
    skills = managed_store.get_cached()
    return [
        {
            "name": s.name,
            "description": s.description,
            "content": managed_store.read_content(s.name) or "",
        }
        for s in skills
    ]


def _parse_evolution_output(text: str) -> SkillEvolutionOutput:
    """Parse LLM output into SkillEvolutionOutput."""
    if not text or not text.strip():
        raise InferenceError("LLM returned empty response for evolution analysis.")

    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
        return SkillEvolutionOutput.model_validate(data)
    except json.JSONDecodeError as exc:
        preview = json_str[:500] if len(json_str) > 500 else json_str
        raise InferenceError(
            f"LLM output is not valid JSON. Preview: {preview!r}. Error: {exc}"
        ) from exc
    except ValidationError as exc:
        raise InferenceError(f"LLM JSON does not match SkillEvolutionOutput schema: {exc}") from exc


def _build_evolution_result(
    validated_patterns: list[WorkflowPattern],
    llm_output: SkillEvolutionOutput,
    loaded_ids: list[str],
    skipped_ids: list[str],
    backend: InferenceBackend,
    cost_usd: float | None,
    batch_count: int = 1,
    warnings: list[str] | None = None,
) -> SkillAnalysisResult:
    """Build a SkillAnalysisResult for evolution mode."""
    return SkillAnalysisResult(
        mode=SkillMode.EVOLUTION,
        workflow_patterns=validated_patterns,
        evolution_suggestions=llm_output.evolution_suggestions,
        summary=llm_output.summary,
        user_profile=llm_output.user_profile,
        session_ids=loaded_ids,
        sessions_skipped=skipped_ids,
        warnings=warnings or [],
        backend_id=backend.backend_id,
        model=backend.model,
        cost_usd=cost_usd,
        batch_count=batch_count,
        created_at=datetime.now(UTC).isoformat(),
    )
