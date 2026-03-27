"""Session batcher — group sessions into LLM-sized batches.

Groups extracted session contexts into batches for concurrent LLM calls.

Packing priority (highest → lowest):
1. Continued-trajectory chains — sessions linked via last/continued refs
2. Same-project, time-nearest sessions
3. Cross-project, time-nearest sessions

Budget is token-based: each batch is packed as close to max_batch_tokens
as possible without exceeding it.

Oversized handling: when a single session's context exceeds the budget,
its text is split at step boundaries into multiple parts, each fitting
within the budget. Parts use suffixed IDs (e.g., session_id__part1).

Reusable by friction analysis, skill analysis, and other batch-inference modules.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from vibelens.deps import get_settings
from vibelens.llm.tokenizer import count_tokens
from vibelens.services.context_extraction import SessionContext
from vibelens.utils.log import get_logger

logger = get_logger(__name__)

NO_PROJECT = "__unknown__"
STEP_BOUNDARY_PATTERN = re.compile(r"\n\n(?=\[step_id=)")


@dataclass
class SessionBatch:
    """A batch of session contexts sized for one LLM call."""

    batch_id: str
    session_contexts: list[SessionContext]
    total_tokens: int
    project_paths: set[str] = field(default_factory=set)


@dataclass
class _Chain:
    """A chain of linked sessions treated as an atomic packing unit.

    Sessions linked via continued_trajectory_ref form a chain that
    must stay together in the same batch to preserve conversation flow.
    Unlinked sessions become single-item chains.
    """

    contexts: list[SessionContext]
    tokens: int
    project: str
    timestamp: datetime | None


def build_batches(
    session_contexts: list[SessionContext], max_batch_tokens: int | None = None
) -> list[SessionBatch]:
    """Group session contexts into batches for LLM calls.

    Args:
        session_contexts: Extracted session contexts.
        max_batch_tokens: Max tokens per batch for session content.
            When None, reads from Settings.max_batch_tokens.

    Returns:
        List of SessionBatch ready for concurrent LLM calls.
    """
    if not session_contexts:
        return []

    settings = get_settings()
    budget = max_batch_tokens or settings.max_batch_tokens

    chains = _build_chains(session_contexts)
    chains = _split_oversized_chains(chains, budget)
    batches = _pack_batches(chains, budget)

    if batches:
        logger.info(
            "Built %d batch(es) from %d chain(s), avg %d tokens/batch",
            len(batches),
            len(chains),
            sum(b.total_tokens for b in batches) // len(batches),
        )

    return batches


def _build_chains(contexts: list[SessionContext]) -> list[_Chain]:
    """Merge linked sessions into chains.

    Sessions linked via last_trajectory_ref/continued_trajectory_ref
    are merged into ordered chains. Unlinked sessions become
    single-item chains. Visiting earlier sessions first ensures
    chains are built from the chronological start.

    Args:
        contexts: All session contexts to process.

    Returns:
        List of _Chain objects with cached token counts.
    """
    by_id = {c.session_id: c for c in contexts}
    visited: set[str] = set()
    chains: list[_Chain] = []

    # Sort contexts by timestamp
    sorted_contexts = sorted(contexts, key=lambda c: c.timestamp or datetime.min)
    # Iterate in chronological order, building chains from unvisited sessions
    for ctx in sorted_contexts:
        if ctx.session_id in visited:
            continue
        chain_ctxs = _follow_chain(ctx, by_id, visited)
        tokens = sum(count_tokens(c.context_text) for c in chain_ctxs)
        project = chain_ctxs[0].project_path or NO_PROJECT
        earliest = min((c.timestamp for c in chain_ctxs if c.timestamp), default=None)
        chains.append(
            _Chain(contexts=chain_ctxs, tokens=tokens, project=project, timestamp=earliest)
        )
    return chains


def _split_oversized_chains(chains: list[_Chain], budget: int) -> list[_Chain]:
    """Split chains that exceed the token budget into smaller chains.

    For multi-session chains, each session becomes its own chain.
    For single-session chains whose context_text still exceeds budget,
    the text is split at step boundaries into multiple parts.

    Args:
        chains: Chains from _build_chains, possibly oversized.
        budget: Max tokens per batch.

    Returns:
        New list of chains where every chain fits within budget.
    """
    result: list[_Chain] = []

    for chain in chains:
        if chain.tokens <= budget:
            result.append(chain)
            continue

        # Multi-session chain: split into individual sessions
        if len(chain.contexts) > 1:
            for ctx in chain.contexts:
                tokens = count_tokens(ctx.context_text)
                sub_chain = _Chain(
                    contexts=[ctx],
                    tokens=tokens,
                    project=ctx.project_path or NO_PROJECT,
                    timestamp=ctx.timestamp,
                )
                if tokens > budget:
                    result.extend(_split_single_session(sub_chain, budget))
                else:
                    result.append(sub_chain)
        else:
            result.extend(_split_single_session(chain, budget))

    return result


def _split_single_session(chain: _Chain, budget: int) -> list[_Chain]:
    """Split a single oversized session's context at step boundaries.

    The context_text is divided into segments at step boundaries
    (double-newline before ``[step_id=...]``). Segments are grouped
    into parts that each fit within the token budget. Each part
    becomes a new SessionContext with a suffixed session_id.

    The session header (=== SESSION: ... ===) is prepended to every
    part so the LLM always knows which session it's reading.

    Args:
        chain: A single-session chain that exceeds budget.
        budget: Max tokens per batch.

    Returns:
        List of chains, one per part, each within budget.
    """
    ctx = chain.contexts[0]
    text = ctx.context_text

    # Split at step boundaries, preserving the header for each part
    segments = STEP_BOUNDARY_PATTERN.split(text)

    # First segment contains the header + possibly the first step.
    # Extract the header (lines before the first [step_id=] block)
    header = ""
    first_segment = segments[0]
    step_match = re.search(r"\[step_id=", first_segment)
    if step_match:
        header = first_segment[: step_match.start()].rstrip()
        segments[0] = first_segment[step_match.start() :]
    else:
        # Entire first segment is header (no steps yet)
        header = first_segment.rstrip()
        segments = segments[1:]

    if not segments:
        # No step boundaries found — cannot split further, keep as-is
        logger.warning(
            "Cannot split oversized session %s (%d tokens) — no step boundaries",
            ctx.session_id,
            chain.tokens,
        )
        return [chain]

    header_tokens = count_tokens(header) if header else 0
    # Reserve space for header + separator in each part
    part_budget = budget - header_tokens - 5  # 5 tokens for separator newlines

    if part_budget <= 0:
        # Header alone exceeds budget — nothing we can do
        logger.warning(
            "Session %s header alone exceeds budget (%d tokens)",
            ctx.session_id,
            header_tokens,
        )
        return [chain]

    # Greedily pack segments into parts
    parts: list[str] = []
    current_segments: list[str] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = count_tokens(segment)

        if current_tokens + seg_tokens > part_budget and current_segments:
            # Flush current part
            body = "\n\n".join(current_segments)
            parts.append(f"{header}\n\n{body}" if header else body)
            current_segments = []
            current_tokens = 0

        current_segments.append(segment)
        current_tokens += seg_tokens

    # Flush remaining
    if current_segments:
        body = "\n\n".join(current_segments)
        parts.append(f"{header}\n\n{body}" if header else body)

    # Create new chains from parts
    result: list[_Chain] = []
    for i, part_text in enumerate(parts, 1):
        part_tokens = count_tokens(part_text)
        part_ctx = SessionContext(
            session_id=f"{ctx.session_id}__part{i}",
            project_path=ctx.project_path,
            context_text=part_text,
            char_count=len(part_text),
            trajectory_group=ctx.trajectory_group,
            last_trajectory_ref_id=ctx.last_trajectory_ref_id,
            continued_trajectory_ref_id=ctx.continued_trajectory_ref_id,
            timestamp=ctx.timestamp,
            step_index_map=ctx.step_index_map,
        )
        result.append(
            _Chain(
                contexts=[part_ctx],
                tokens=part_tokens,
                project=chain.project,
                timestamp=chain.timestamp,
            )
        )

    logger.info(
        "Split oversized session %s (%d tokens) into %d parts",
        ctx.session_id,
        chain.tokens,
        len(parts),
    )
    return result


def _follow_chain(
    start: SessionContext, by_id: dict[str, SessionContext], visited: set[str]
) -> list[SessionContext]:
    """Follow linked sessions forward and backward to build a chain.

    Walks backward via last_trajectory_ref_id to find the chain head,
    then forward via continued_trajectory_ref_id to find the tail.
    All visited sessions are marked to prevent re-processing.

    Args:
        start: Starting session context.
        by_id: Lookup table of all session contexts by ID.
        visited: Set of already-processed session IDs (mutated).

    Returns:
        Ordered list of linked sessions from earliest to latest.
    """
    # Walk backward to find chain head
    backward: list[SessionContext] = []
    current = start
    while True:
        ref_id = current.last_trajectory_ref_id
        if not ref_id or ref_id not in by_id or ref_id in visited:
            break
        current = by_id[ref_id]
        backward.append(current)

    # Build chain: backward (reversed) + start + forward
    backward.reverse()
    chain = backward + [start]

    # Walk forward to find chain tail
    current = start
    while True:
        ref_id = current.continued_trajectory_ref_id
        if not ref_id or ref_id not in by_id or ref_id in visited:
            break
        current = by_id[ref_id]
        chain.append(current)

    for c in chain:
        visited.add(c.session_id)

    return chain


def _pack_batches(chains: list[_Chain], budget: int) -> list[SessionBatch]:
    """Pack chains into batches using affinity-based greedy packing.

    Algorithm:
    1. Sort all chains by (project, timestamp) for deterministic ordering
    2. Pop the first unplaced chain as the batch seed
    3. Rank remaining chains by affinity: same-project time-nearest
       first, then cross-project time-nearest
    4. Greedily add chains that fit within the token budget
    5. Repeat until all chains are placed

    Oversized chains (exceeding budget alone) get their own batch.

    Args:
        chains: All session chains from _build_chains.
        budget: Max tokens per batch.

    Returns:
        List of SessionBatch objects.
    """
    sorted_chains = sorted(chains, key=lambda c: (c.project, c.timestamp or datetime.min))
    remaining = list(range(len(sorted_chains)))
    batches: list[SessionBatch] = []

    while remaining:
        seed_idx = remaining.pop(0)
        seed = sorted_chains[seed_idx]

        batch_contexts = list(seed.contexts)
        batch_tokens = seed.tokens
        batch_projects = {seed.project}

        # Rank remaining by affinity, then greedily add what fits
        placed = _fill_batch(sorted_chains, remaining, seed, batch_tokens, budget)
        for idx in placed:
            chain = sorted_chains[idx]
            batch_contexts.extend(chain.contexts)
            batch_tokens += chain.tokens
            batch_projects.add(chain.project)
            remaining.remove(idx)

        batch_id = f"batch-{len(batches) + 1:03d}"
        batches.append(
            SessionBatch(
                batch_id=batch_id,
                session_contexts=batch_contexts,
                total_tokens=batch_tokens,
                project_paths=batch_projects,
            )
        )

    return batches


def _fill_batch(
    chains: list[_Chain], remaining: list[int], seed: _Chain, batch_tokens: int, budget: int
) -> list[int]:
    """Select chains to add to a batch, ranked by affinity.

    Affinity sort key: (is_cross_project, time_distance_seconds).
    Same-project chains rank higher; within each group, closer in
    time ranks higher. Chains that exceed remaining budget are skipped.

    Args:
        chains: All chains (indexed by position).
        remaining: Indices of unplaced chains.
        seed: The seed chain that started this batch.
        batch_tokens: Current token count in the batch.
        budget: Max tokens per batch.

    Returns:
        Indices of chains selected to add (caller removes from remaining).
    """
    seed_time = seed.timestamp or datetime.min

    def affinity_key(idx: int) -> tuple[int, float]:
        chain = chains[idx]
        is_cross_project = 0 if chain.project == seed.project else 1
        if chain.timestamp and seed_time != datetime.min:
            time_dist = abs((chain.timestamp - seed_time).total_seconds())
        else:
            time_dist = float("inf")
        return (is_cross_project, time_dist)

    ranked = sorted(remaining, key=affinity_key)

    placed: list[int] = []
    current_tokens = batch_tokens
    for idx in ranked:
        chain = chains[idx]
        if current_tokens + chain.tokens > budget:
            continue
        placed.append(idx)
        current_tokens += chain.tokens

    return placed
