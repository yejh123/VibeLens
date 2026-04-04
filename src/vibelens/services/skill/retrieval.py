"""Skill retrieval mode — recommend existing skills from the featured catalog.

Contains shared infrastructure (caching, session loading, parsing, validation)
used by all three skill analysis modes.
"""

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from vibelens.deps import get_central_skill_store, get_skill_analysis_store
from vibelens.llm.backend import InferenceBackend, InferenceError
from vibelens.llm.prompts.skill_retrieval import (
    SKILL_RETRIEVAL_PROMPT,
    SKILL_RETRIEVAL_SYNTHESIS_PROMPT,
)
from vibelens.models.inference import InferenceRequest
from vibelens.models.skill import (
    SkillAnalysisResult,
    SkillMode,
    SkillRetrievalOutput,
    WorkflowPattern,
)
from vibelens.models.trajectories import Trajectory
from vibelens.services.analysis_shared import (
    build_system_kwargs,
    extract_all_contexts,
    get_cached,
    require_backend,
    run_batches_concurrent,
    save_analysis_log,
    truncate_digest_to_fit,
)
from vibelens.services.context_params import PRESET_CONCISE
from vibelens.services.friction.digest import format_batch_digest
from vibelens.services.session_batcher import SessionBatch, build_batches
from vibelens.utils.json_extract import extract_json as _extract_json
from vibelens.utils.log import get_logger

logger = get_logger(__name__)

FEATURED_SKILLS_PATH = Path(__file__).resolve().parents[4] / "featured-skills.json"
CANDIDATE_PREFILTER_THRESHOLD = 200
PREFILTER_TOP_K = 100
SKILL_LOG_DIR = Path("logs/skill")
RETRIEVAL_OUTPUT_TOKENS = 8192
RETRIEVAL_SYNTHESIS_OUTPUT_TOKENS = 8192
RETRIEVAL_TIMEOUT_SECONDS = 300

_cache: dict[str, tuple[float, BaseModel]] = {}


async def analyze_retrieval(
    session_ids: list[str], session_token: str | None = None
) -> SkillAnalysisResult:
    """Run retrieval-mode skill analysis: recommend existing skills from catalog."""
    cache_key = _skill_cache_key(session_ids, SkillMode.RETRIEVAL)
    cached = get_cached(_cache, cache_key)
    if cached:
        return cached

    backend = require_backend()
    contexts, loaded_ids, skipped_ids = extract_all_contexts(
        session_ids, session_token, PRESET_CONCISE
    )

    if not contexts:
        raise ValueError(f"No sessions could be loaded from: {session_ids}")

    # Collect all trajectories for pattern validation
    all_trajectories: list[Trajectory] = []
    for ctx in contexts:
        all_trajectories.extend(ctx.trajectory_group)

    installed_skills = _gather_installed_skills()
    skill_candidates = _load_skill_candidates()

    batches = build_batches(contexts)
    logger.info("Skill retrieval: %d sessions → %d batch(es)", len(loaded_ids), len(batches))

    run_timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_dir = SKILL_LOG_DIR / run_timestamp

    tasks = [
        _infer_retrieval_batch(backend, batch, installed_skills, skill_candidates, log_dir, idx)
        for idx, batch in enumerate(batches)
    ]
    batch_results, batch_warnings = await run_batches_concurrent(tasks, "retrieval")

    total_cost = sum(cost for _, cost in batch_results)

    # Single batch: use directly; multiple batches: synthesize
    if len(batch_results) == 1:
        llm_output = batch_results[0][0]
    else:
        llm_output, syn_cost = await _synthesize_retrieval(
            backend, batch_results, len(loaded_ids), log_dir
        )
        total_cost += syn_cost

    validated_patterns = _validate_patterns(llm_output.workflow_patterns, all_trajectories)

    skill_result = _build_retrieval_result(
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


async def _infer_retrieval_batch(
    backend: InferenceBackend,
    batch: SessionBatch,
    installed_skills: list[dict],
    skill_candidates: list[dict],
    log_dir: Path,
    batch_index: int,
) -> tuple[SkillRetrievalOutput, float]:
    """Run LLM inference for one retrieval batch.

    Args:
        backend: Configured inference backend.
        batch: Session batch with pre-extracted contexts.
        installed_skills: Already-installed skills to avoid duplicates.
        skill_candidates: Featured skill catalog entries.
        log_dir: Timestamped directory for saving prompts and outputs.
        batch_index: Zero-based batch index for file naming.

    Returns:
        Tuple of (parsed retrieval output, cost in USD).
    """
    digest = format_batch_digest(batch)
    session_count = len(batch.session_contexts)

    # Pre-filter candidates per batch using batch-specific keywords
    candidates = skill_candidates
    if len(candidates) > CANDIDATE_PREFILTER_THRESHOLD:
        candidates = _prefilter_candidates(candidates, digest)

    prompt = SKILL_RETRIEVAL_PROMPT
    system_kwargs = build_system_kwargs(prompt.output_model, backend)
    system_prompt = prompt.render_system(**system_kwargs)

    # Truncate digest to fit context budget
    non_digest_overhead = prompt.render_user(
        session_count=session_count,
        session_digest="",
        installed_skills=installed_skills if installed_skills else None,
        skill_candidates=candidates if candidates else None,
    )
    digest = truncate_digest_to_fit(digest, system_prompt, non_digest_overhead)

    user_prompt = prompt.render_user(
        session_count=session_count,
        session_digest=digest,
        installed_skills=installed_skills if installed_skills else None,
        skill_candidates=candidates if candidates else None,
    )

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=RETRIEVAL_OUTPUT_TOKENS,
        timeout=RETRIEVAL_TIMEOUT_SECONDS,
        json_schema=prompt.output_model.model_json_schema(),
    )

    if batch_index == 0:
        save_analysis_log(log_dir, "retrieval_system.txt", system_prompt)
    save_analysis_log(log_dir, f"retrieval_user_{batch_index}.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, f"retrieval_output_{batch_index}.txt", result.text)

    retrieval_output = _parse_retrieval_output(result.text)
    cost = result.cost_usd or 0.0
    return retrieval_output, cost


async def _synthesize_retrieval(
    backend: InferenceBackend,
    batch_results: list[tuple[SkillRetrievalOutput, float]],
    session_count: int,
    log_dir: Path,
) -> tuple[SkillRetrievalOutput, float]:
    """Merge retrieval results from multiple batches via LLM synthesis.

    Args:
        backend: Configured inference backend.
        batch_results: Per-batch retrieval outputs and costs.
        session_count: Total number of sessions analyzed.
        log_dir: Timestamped directory for saving prompts and outputs.

    Returns:
        Tuple of (merged SkillRetrievalOutput, synthesis cost in USD).
    """
    batch_data = [
        {
            "summary": output.summary,
            "user_profile": output.user_profile,
            "workflow_patterns": [
                {"title": p.title, "description": p.description, "gap": p.gap}
                for p in output.workflow_patterns
            ],
            "recommendations": [
                {
                    "skill_name": r.skill_name,
                    "match_reason": r.match_reason,
                    "confidence": r.confidence,
                }
                for r in output.recommendations
            ],
        }
        for output, _ in batch_results
    ]

    prompt = SKILL_RETRIEVAL_SYNTHESIS_PROMPT
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
        max_tokens=RETRIEVAL_SYNTHESIS_OUTPUT_TOKENS,
        timeout=RETRIEVAL_TIMEOUT_SECONDS,
        json_schema=prompt.output_model.model_json_schema(),
    )

    save_analysis_log(log_dir, "retrieval_synthesis_system.txt", system_prompt)
    save_analysis_log(log_dir, "retrieval_synthesis_user.txt", user_prompt)

    result = await backend.generate(request)
    save_analysis_log(log_dir, "retrieval_synthesis_output.txt", result.text)

    synthesis_output = _parse_retrieval_output(result.text)
    cost = result.cost_usd or 0.0
    return synthesis_output, cost


def _load_skill_candidates() -> list[dict]:
    """Load skill candidates from the featured skills catalog.

    Returns a list of dicts with name, summary, and tags for each candidate.
    The LLM picks from these candidates when recommending skills.
    """
    if not FEATURED_SKILLS_PATH.is_file():
        return []
    try:
        raw = FEATURED_SKILLS_PATH.read_text(encoding="utf-8")
        catalog = json.loads(raw)
        return [
            {
                "name": entry.get("slug", entry.get("name", "")),
                "summary": entry.get("summary", ""),
                "tags": entry.get("tags", []),
            }
            for entry in catalog.get("skills", [])
            if entry.get("summary")
        ]
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to load featured skills catalog for retrieval candidates")
        return []


def _prefilter_candidates(candidates: list[dict], digest: str) -> list[dict]:
    """Keyword-based pre-filtering for large skill catalogs.

    Extracts keywords from the digest (tool names, user topics, alpha tokens)
    and scores each candidate by keyword overlap in name + summary + tags.

    Args:
        candidates: Full list of skill candidate dicts.
        digest: Session digest text used for keyword extraction.

    Returns:
        Top PREFILTER_TOP_K candidates sorted by relevance score.
    """
    keywords = _extract_digest_keywords(digest)
    if not keywords:
        return candidates[:PREFILTER_TOP_K]

    scored: list[tuple[int, dict]] = []
    for candidate in candidates:
        searchable = " ".join(
            [
                candidate.get("name", ""),
                candidate.get("summary", ""),
                " ".join(candidate.get("tags", [])),
            ]
        ).lower()
        score = sum(1 for kw in keywords if kw in searchable)
        scored.append((score, candidate))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [candidate for _, candidate in scored[:PREFILTER_TOP_K]]


def _extract_digest_keywords(digest: str) -> set[str]:
    """Extract keywords from a session digest for candidate matching.

    Pulls tool names from "TOOL FREQUENCY:" blocks, user topics,
    and alpha tokens longer than 3 characters.

    Args:
        digest: Session digest text.

    Returns:
        Set of lowercase keywords.
    """
    keywords: set[str] = set()

    # Extract tool names from TOOL FREQUENCY lines (e.g. "  Edit: 15")
    for match in re.finditer(r"^\s+(\w+):\s+\d+", digest, re.MULTILINE):
        keywords.add(match.group(1).lower())

    # Extract user topics from USER TOPICS lines
    topic_match = re.search(r"USER TOPICS:\s*(.+)", digest)
    if topic_match:
        topic_text = topic_match.group(1)
        for token in re.findall(r"[a-zA-Z]{4,}", topic_text):
            keywords.add(token.lower())

    # Extract general alpha tokens from fn= tool calls
    for match in re.finditer(r"fn=(\w+)", digest):
        keywords.add(match.group(1).lower())

    return keywords


def _skill_cache_key(session_ids: list[str], mode: SkillMode) -> str:
    """Generate a cache key from sorted session IDs and mode."""
    sorted_ids = ",".join(sorted(session_ids))
    raw = f"skill:{mode}:{sorted_ids}"
    return f"skill:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _gather_installed_skills() -> list[dict]:
    """Collect installed skill metadata from the central store."""
    managed_store = get_central_skill_store()
    skills = managed_store.get_cached()
    return [{"name": s.name, "description": s.description} for s in skills]


def _parse_retrieval_output(text: str) -> SkillRetrievalOutput:
    """Parse LLM output into SkillRetrievalOutput."""
    if not text or not text.strip():
        raise InferenceError(
            "LLM returned empty response. Check logs for the prompt that was sent."
        )

    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
        return SkillRetrievalOutput.model_validate(data)
    except json.JSONDecodeError as exc:
        preview = json_str[:500] if len(json_str) > 500 else json_str
        raise InferenceError(
            f"LLM output is not valid JSON. Preview: {preview!r}. Error: {exc}"
        ) from exc
    except ValidationError as exc:
        raise InferenceError(f"LLM JSON does not match SkillRetrievalOutput schema: {exc}") from exc


def _validate_patterns(
    patterns: list[WorkflowPattern], trajectories: list[Trajectory]
) -> list[WorkflowPattern]:
    """Validate workflow pattern step references against loaded trajectories."""
    valid_step_ids = {step.step_id for t in trajectories for step in t.steps}
    validated: list[WorkflowPattern] = []
    for pattern in patterns:
        filtered_refs = [
            ref
            for ref in pattern.example_refs
            if ref.start_step_id in valid_step_ids
            and (ref.end_step_id is None or ref.end_step_id in valid_step_ids)
        ]
        pattern.example_refs = filtered_refs
        validated.append(pattern)
    return validated


def _build_retrieval_result(
    validated_patterns: list[WorkflowPattern],
    llm_output: SkillRetrievalOutput,
    loaded_ids: list[str],
    skipped_ids: list[str],
    backend: InferenceBackend,
    cost_usd: float | None,
    batch_count: int = 1,
    warnings: list[str] | None = None,
) -> SkillAnalysisResult:
    """Build a SkillAnalysisResult for retrieval mode."""
    return SkillAnalysisResult(
        mode=SkillMode.RETRIEVAL,
        workflow_patterns=validated_patterns,
        recommendations=llm_output.recommendations,
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
