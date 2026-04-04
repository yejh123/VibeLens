"""Skill creation mode — two-step pipeline: proposals then deep creation.

Pipeline:
1. analyze_proposals: load sessions → extract contexts → batch → concurrent
   LLM proposal calls → optional synthesis → SkillProposalResult
2. deep_create_skill: single LLM call per approved proposal → SkillCreation
3. analyze_creation: backward-compat wrapper calling both steps
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from vibelens.deps import get_skill_analysis_store
from vibelens.llm.backend import InferenceBackend, InferenceError
from vibelens.llm.prompts.skill_deep_creation import SKILL_DEEP_CREATION_PROMPT
from vibelens.llm.prompts.skill_proposal import (
    SKILL_PROPOSAL_PROMPT,
    SKILL_PROPOSAL_SYNTHESIS_PROMPT,
)
from vibelens.models.inference import InferenceRequest
from vibelens.models.skill import (
    SkillAnalysisResult,
    SkillCreation,
    SkillDeepCreationOutput,
    SkillMode,
    SkillProposalOutput,
    SkillProposalResult,
)
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

PROPOSAL_OUTPUT_TOKENS = 4096
PROPOSAL_TIMEOUT_SECONDS = 300
PROPOSAL_SYNTHESIS_OUTPUT_TOKENS = 8192
PROPOSAL_SYNTHESIS_TIMEOUT_SECONDS = 300
PROPOSAL_CACHE_TTL_SECONDS = 3600
DEEP_CREATION_OUTPUT_TOKENS = 4096
DEEP_CREATION_TIMEOUT_SECONDS = 300

# Proposal pipeline internals
_proposal_cache: dict[str, tuple[float, SkillProposalResult]] = {}


async def analyze_creation(
    session_ids: list[str], session_token: str | None = None
) -> SkillAnalysisResult:
    """Backward-compatible creation: proposals then deep creation for each.

    Preserves the existing POST /skills/analysis endpoint with mode=creation.

    Args:
        session_ids: Sessions to analyze.
        session_token: Browser tab token for upload scoping.

    Returns:
        SkillAnalysisResult with generated_skills populated.
    """
    cache_key = _skill_cache_key(session_ids, SkillMode.CREATION)
    cached = get_cached(_cache, cache_key)
    if cached:
        return cached

    # Shared log directory for the entire creation pipeline
    run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_dir = SKILL_LOG_DIR / run_timestamp

    # Step 1: Generate proposals
    proposal_result = await analyze_proposals(session_ids, session_token, log_dir=log_dir)

    # Step 2: Deep create each proposal concurrently
    creation_tasks = [
        deep_create_skill(
            proposal_name=p.name,
            proposal_description=p.description,
            proposal_rationale=p.rationale,
            addressed_patterns=p.addressed_patterns,
            session_ids=session_ids,
            session_token=session_token,
            proposal_confidence=p.confidence,
            log_dir=log_dir,
            proposal_index=idx,
        )
        for idx, p in enumerate(proposal_result.proposals)
    ]

    generated_skills: list[SkillCreation] = []
    creation_warnings: list[str] = list(proposal_result.warnings)
    if creation_tasks:
        results = await asyncio.gather(*creation_tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, SkillCreation):
                generated_skills.append(result)
            else:
                name = proposal_result.proposals[idx].name
                creation_warnings.append(f"Deep creation failed for '{name}': {result}")
                logger.warning("Deep creation failed for proposal '%s': %s", name, result)

    skill_result = SkillAnalysisResult(
        mode=SkillMode.CREATION,
        workflow_patterns=proposal_result.workflow_patterns,
        generated_skills=generated_skills,
        summary=proposal_result.summary,
        user_profile=proposal_result.user_profile,
        session_ids=proposal_result.session_ids,
        sessions_skipped=proposal_result.sessions_skipped,
        warnings=creation_warnings,
        backend_id=proposal_result.backend_id,
        model=proposal_result.model,
        cost_usd=proposal_result.cost_usd,
        created_at=datetime.now(UTC).isoformat(),
    )
    get_skill_analysis_store().save(skill_result)

    _cache[cache_key] = (time.monotonic(), skill_result)
    return skill_result


async def analyze_proposals(
    session_ids: list[str],
    session_token: str | None = None,
    log_dir: Path | None = None,
) -> SkillProposalResult:
    """Run the proposal step: detect patterns and generate lightweight proposals.

    Args:
        session_ids: Sessions to analyze.
        session_token: Browser tab token for upload scoping.
        log_dir: Shared log directory. Created if None.

    Returns:
        SkillProposalResult with proposals and metadata.

    Raises:
        ValueError: If no sessions could be loaded or no backend configured.
        InferenceError: If LLM backend fails.
    """
    cache_key = _skill_cache_key(session_ids, SkillMode.CREATION) + ":proposals"
    cached = _get_cached_proposals(cache_key)
    if cached:
        return cached

    backend = require_backend()
    contexts, loaded_ids, skipped_ids = extract_all_contexts(
        session_ids, session_token, PRESET_MEDIUM
    )

    if not contexts:
        raise ValueError(f"No sessions could be loaded from: {session_ids}")

    batches = build_batches(contexts)
    logger.info("Skill proposals: %d sessions → %d batch(es)", len(loaded_ids), len(batches))

    if log_dir is None:
        run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_dir = SKILL_LOG_DIR / run_timestamp

    installed_skills = _gather_installed_skills()

    tasks = [
        _infer_proposal_batch(backend, batch, installed_skills, log_dir, idx)
        for idx, batch in enumerate(batches)
    ]
    batch_results, batch_warnings = await run_batches_concurrent(tasks, "proposal")

    total_cost = sum(cost for _, cost in batch_results)

    # Single batch: use directly; multiple batches: synthesize
    if len(batch_results) == 1:
        proposal_output = batch_results[0][0]
    else:
        proposal_output, syn_cost = await _synthesize_proposals(
            backend, batch_results, len(loaded_ids), log_dir
        )
        total_cost += syn_cost

    # Collect all trajectories for pattern validation
    all_trajectories = []
    for ctx in contexts:
        all_trajectories.extend(ctx.trajectory_group)

    validated_patterns = _validate_patterns(proposal_output.workflow_patterns, all_trajectories)

    result = SkillProposalResult(
        session_ids=loaded_ids,
        workflow_patterns=validated_patterns,
        proposals=proposal_output.proposals,
        summary=proposal_output.summary,
        user_profile=proposal_output.user_profile,
        sessions_skipped=skipped_ids,
        warnings=batch_warnings,
        backend_id=backend.backend_id,
        model=backend.model,
        cost_usd=total_cost if total_cost > 0 else None,
        batch_count=len(batches),
        created_at=datetime.now(UTC).isoformat(),
    )

    _proposal_cache[cache_key] = (time.monotonic(), result)
    return result


async def deep_create_skill(
    proposal_name: str,
    proposal_description: str,
    proposal_rationale: str,
    addressed_patterns: list[str],
    session_ids: list[str],
    session_token: str | None = None,
    proposal_confidence: float = 0.0,
    log_dir: Path | None = None,
    proposal_index: int | None = None,
) -> SkillCreation:
    """Generate full SKILL.md content for one approved proposal.

    Args:
        proposal_name: Kebab-case skill name.
        proposal_description: One-line trigger description.
        proposal_rationale: Why this skill would improve workflow.
        addressed_patterns: Pattern titles this proposal addresses.
        session_ids: Sessions to use as evidence.
        session_token: Browser tab token for upload scoping.
        proposal_confidence: Confidence from proposal step (0.0-1.0).
        log_dir: Shared log directory. Created if None.
        proposal_index: Index for log file naming when called from analyze_creation.

    Returns:
        SkillCreation with full SKILL.md content.

    Raises:
        ValueError: If no sessions could be loaded or no backend configured.
        InferenceError: If LLM backend fails.
    """
    backend = require_backend()
    contexts, loaded_ids, skipped_ids = extract_all_contexts(
        session_ids, session_token, PRESET_MEDIUM
    )

    if not contexts:
        raise ValueError(f"No sessions could be loaded from: {session_ids}")

    # Build digest from all contexts (no batching needed for single-skill creation)
    digest = build_digest_from_contexts(contexts)
    installed_skills = _gather_installed_skills()

    system_kwargs = build_system_kwargs(SKILL_DEEP_CREATION_PROMPT.output_model, backend)
    system_prompt = SKILL_DEEP_CREATION_PROMPT.render_system(**system_kwargs)

    # Truncate digest to fit context budget
    non_digest_overhead = SKILL_DEEP_CREATION_PROMPT.render_user(
        proposal_name=proposal_name,
        proposal_description=proposal_description,
        proposal_rationale=proposal_rationale,
        addressed_patterns=addressed_patterns,
        session_digest="",
        installed_skills=installed_skills if installed_skills else None,
    )
    digest = truncate_digest_to_fit(digest, system_prompt, non_digest_overhead)

    user_prompt = SKILL_DEEP_CREATION_PROMPT.render_user(
        proposal_name=proposal_name,
        proposal_description=proposal_description,
        proposal_rationale=proposal_rationale,
        addressed_patterns=addressed_patterns,
        session_digest=digest,
        installed_skills=installed_skills if installed_skills else None,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=DEEP_CREATION_OUTPUT_TOKENS,
        timeout=DEEP_CREATION_TIMEOUT_SECONDS,
        json_schema=SKILL_DEEP_CREATION_PROMPT.output_model.model_json_schema(),
    )

    if log_dir is None:
        run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_dir = SKILL_LOG_DIR / run_timestamp

    suffix = f"_{proposal_index}" if proposal_index is not None else ""
    save_analysis_log(log_dir, f"deep_creation{suffix}_system.txt", system_prompt)
    save_analysis_log(log_dir, f"deep_creation{suffix}_user.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, f"deep_creation{suffix}_output.txt", result.text)

    deep_output = _parse_deep_creation_output(result.text)

    return SkillCreation(
        name=deep_output.name,
        description=deep_output.description,
        skill_md_content=deep_output.skill_md_content,
        rationale=deep_output.rationale,
        confidence=proposal_confidence,
    )


def _get_cached_proposals(cache_key: str) -> SkillProposalResult | None:
    """Return cached proposal result if still valid."""
    entry = _proposal_cache.get(cache_key)
    if not entry:
        return None
    cached_at, result = entry
    if time.monotonic() - cached_at > PROPOSAL_CACHE_TTL_SECONDS:
        del _proposal_cache[cache_key]
        return None
    return result


async def _infer_proposal_batch(
    backend: InferenceBackend,
    batch: SessionBatch,
    installed_skills: list[dict],
    log_dir: Path,
    batch_index: int,
) -> tuple[SkillProposalOutput, float]:
    """Run LLM inference for one proposal batch.

    Args:
        backend: Configured inference backend.
        batch: Session batch with pre-extracted contexts.
        installed_skills: Already-installed skills to avoid duplicates.
        log_dir: Timestamped directory for saving prompts and outputs.
        batch_index: Zero-based batch index for file naming.

    Returns:
        Tuple of (parsed proposal output, cost in USD).
    """
    digest = format_batch_digest(batch)
    session_count = len(batch.session_contexts)

    system_kwargs = build_system_kwargs(SKILL_PROPOSAL_PROMPT.output_model, backend)
    system_prompt = SKILL_PROPOSAL_PROMPT.render_system(**system_kwargs)

    # Truncate digest to fit context budget
    non_digest_overhead = SKILL_PROPOSAL_PROMPT.render_user(
        session_count=session_count,
        session_digest="",
        installed_skills=installed_skills if installed_skills else None,
    )
    digest = truncate_digest_to_fit(digest, system_prompt, non_digest_overhead)

    user_prompt = SKILL_PROPOSAL_PROMPT.render_user(
        session_count=session_count,
        session_digest=digest,
        installed_skills=installed_skills if installed_skills else None,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=PROPOSAL_OUTPUT_TOKENS,
        timeout=PROPOSAL_TIMEOUT_SECONDS,
        json_schema=SKILL_PROPOSAL_PROMPT.output_model.model_json_schema(),
    )

    if batch_index == 0:
        save_analysis_log(log_dir, "proposal_system.txt", system_prompt)
    save_analysis_log(log_dir, f"proposal_user_{batch_index}.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, f"proposal_output_{batch_index}.txt", result.text)

    proposal_output = _parse_proposal_output(result.text)
    cost = result.cost_usd or 0.0
    return proposal_output, cost


async def _synthesize_proposals(
    backend: InferenceBackend,
    batch_results: list[tuple[SkillProposalOutput, float]],
    session_count: int,
    log_dir: Path,
) -> tuple[SkillProposalOutput, float]:
    """Merge proposals from multiple batches via LLM synthesis.

    Args:
        backend: Configured inference backend.
        batch_results: Per-batch proposal outputs and costs.
        session_count: Total number of sessions analyzed.
        log_dir: Timestamped directory for saving prompts and outputs.

    Returns:
        Tuple of (merged SkillProposalOutput, synthesis cost in USD).
    """
    batch_data = [
        {
            "summary": output.summary,
            "user_profile": output.user_profile,
            "workflow_patterns": [
                {"title": p.title, "description": p.description, "gap": p.gap}
                for p in output.workflow_patterns
            ],
            "proposals": [
                {
                    "name": p.name,
                    "description": p.description,
                    "rationale": p.rationale,
                    "addressed_patterns": p.addressed_patterns,
                }
                for p in output.proposals
            ],
        }
        for output, _ in batch_results
    ]

    system_kwargs = build_system_kwargs(SKILL_PROPOSAL_SYNTHESIS_PROMPT.output_model, backend)
    system_prompt = SKILL_PROPOSAL_SYNTHESIS_PROMPT.render_system(**system_kwargs)
    user_prompt = SKILL_PROPOSAL_SYNTHESIS_PROMPT.render_user(
        batch_count=len(batch_results),
        session_count=session_count,
        batch_results=batch_data,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=PROPOSAL_SYNTHESIS_OUTPUT_TOKENS,
        timeout=PROPOSAL_SYNTHESIS_TIMEOUT_SECONDS,
        json_schema=SKILL_PROPOSAL_SYNTHESIS_PROMPT.output_model.model_json_schema(),
    )

    save_analysis_log(log_dir, "proposal_synthesis_system.txt", system_prompt)
    save_analysis_log(log_dir, "proposal_synthesis_user.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, "proposal_synthesis_output.txt", result.text)

    synthesis_output = _parse_proposal_output(result.text)
    cost = result.cost_usd or 0.0
    return synthesis_output, cost


def _parse_proposal_output(text: str) -> SkillProposalOutput:
    """Parse LLM output text into SkillProposalOutput.

    Args:
        text: Raw LLM output text.

    Returns:
        Validated SkillProposalOutput instance.

    Raises:
        InferenceError: If parsing or validation fails.
    """
    if not text or not text.strip():
        raise InferenceError("LLM returned empty response for skill proposals.")

    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
        return SkillProposalOutput.model_validate(data)
    except json.JSONDecodeError as exc:
        preview = json_str[:500] if len(json_str) > 500 else json_str
        raise InferenceError(
            f"Proposal output is not valid JSON. Preview: {preview!r}. Error: {exc}"
        ) from exc
    except ValidationError as exc:
        raise InferenceError(
            f"Proposal JSON does not match SkillProposalOutput schema: {exc}"
        ) from exc


def _parse_deep_creation_output(text: str) -> SkillDeepCreationOutput:
    """Parse LLM output text into SkillDeepCreationOutput.

    Args:
        text: Raw LLM output text.

    Returns:
        Validated SkillDeepCreationOutput instance.

    Raises:
        InferenceError: If parsing or validation fails.
    """
    if not text or not text.strip():
        raise InferenceError("LLM returned empty response for deep skill creation.")

    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
        return SkillDeepCreationOutput.model_validate(data)
    except json.JSONDecodeError as exc:
        preview = json_str[:500] if len(json_str) > 500 else json_str
        raise InferenceError(
            f"Deep creation output is not valid JSON. Preview: {preview!r}. Error: {exc}"
        ) from exc
    except ValidationError as exc:
        raise InferenceError(
            f"Deep creation JSON does not match SkillDeepCreationOutput schema: {exc}"
        ) from exc
