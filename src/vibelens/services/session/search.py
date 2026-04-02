"""In-memory search index for full-text session search.

Pre-builds the index eagerly at startup via build_search_index() so the
first query is instant. Falls back to lazy build with 5-minute TTL
auto-invalidation if the eager call hasn't run yet.
"""

import time
from dataclasses import dataclass

from vibelens.models.enums import StepSource
from vibelens.models.trajectories import Trajectory
from vibelens.models.trajectories.content import ContentPart
from vibelens.services.session.store_resolver import list_all_metadata, load_from_stores
from vibelens.utils import get_logger

logger = get_logger(__name__)

INDEX_TTL_SECONDS = 300
ARG_VALUE_MAX_LENGTH = 500
OBSERVATION_MAX_LENGTH = 200


@dataclass
class _SearchEntry:
    """Pre-extracted, lowercased text for a single session."""

    session_id: str
    user_prompts: str
    agent_messages: str
    tool_calls: str


_search_index: dict[str, _SearchEntry] = {}
_index_built_at: float | None = None


def build_search_index(session_token: str | None = None) -> None:
    """Eagerly build the search index (call at startup to avoid first-search lag)."""
    _build_index(session_token)
    global _index_built_at
    _index_built_at = time.monotonic()


def search_sessions(query: str, sources: list[str], session_token: str | None = None) -> list[str]:
    """Search sessions by query across selected text sources.

    Args:
        query: Search string (case-insensitive substring match).
        sources: List of source names to search
            (user_prompts, agent_messages, tool_calls, session_id).
        session_token: Browser tab token for upload scoping.

    Returns:
        List of matching session IDs.
    """
    if not query:
        return []

    _ensure_index_fresh(session_token)

    query_lower = query.lower()
    matches: list[str] = []

    for entry in _search_index.values():
        if _entry_matches(entry, query_lower, sources):
            matches.append(entry.session_id)

    return matches


def invalidate_search_index() -> None:
    """Reset index timestamp to force rebuild on next search."""
    global _index_built_at
    _index_built_at = None
    _search_index.clear()


def _entry_matches(entry: _SearchEntry, query: str, sources: list[str]) -> bool:
    """Check if a search entry matches the query in any of the selected sources."""
    for source in sources:
        if source == "user_prompts" and query in entry.user_prompts:
            return True
        if source == "agent_messages" and query in entry.agent_messages:
            return True
        if source == "tool_calls" and query in entry.tool_calls:
            return True
        if source == "session_id" and query in entry.session_id.lower():
            return True
    return False


def _ensure_index_fresh(session_token: str | None) -> None:
    """Rebuild the index if it's stale or missing."""
    global _index_built_at

    now = time.monotonic()
    is_stale = _index_built_at is None or (now - _index_built_at) > INDEX_TTL_SECONDS

    if not is_stale:
        return

    _build_index(session_token)
    _index_built_at = now


def _build_index(session_token: str | None) -> None:
    """Iterate all sessions and extract searchable text into the index."""
    _search_index.clear()

    summaries = list_all_metadata(session_token)
    logger.info("Building search index for %d sessions", len(summaries))

    for summary in summaries:
        session_id = summary.get("session_id", "")
        if not session_id:
            continue

        trajectories = load_from_stores(session_id, session_token)
        if not trajectories:
            continue

        _search_index[session_id] = _SearchEntry(
            session_id=session_id,
            user_prompts=_extract_user_prompts(trajectories),
            agent_messages=_extract_agent_messages(trajectories),
            tool_calls=_extract_tool_calls(trajectories),
        )

    logger.info("Search index built with %d entries", len(_search_index))


def _extract_user_prompts(trajectories: list[Trajectory]) -> str:
    """Concatenate all user step messages, lowercased."""
    parts: list[str] = []
    for traj in trajectories:
        for step in traj.steps:
            if step.source != StepSource.USER:
                continue
            text = _extract_message_text(step.message)
            if text:
                parts.append(text)
    return " ".join(parts).lower()


def _extract_agent_messages(trajectories: list[Trajectory]) -> str:
    """Extract agent text messages (no tool data)."""
    parts: list[str] = []
    for traj in trajectories:
        for step in traj.steps:
            if step.source != StepSource.AGENT:
                continue
            text = _extract_message_text(step.message)
            if text:
                parts.append(text)
    return " ".join(parts).lower()


def _extract_tool_calls(trajectories: list[Trajectory]) -> str:
    """Extract tool names, arguments, and truncated observations."""
    parts: list[str] = []
    for traj in trajectories:
        for step in traj.steps:
            if step.source != StepSource.AGENT:
                continue

            for tc in step.tool_calls:
                parts.append(tc.function_name)
                arg_text = _extract_readable_args(tc.arguments)
                if arg_text:
                    parts.append(arg_text[:ARG_VALUE_MAX_LENGTH])

            if step.observation:
                for result in step.observation.results:
                    obs_text = _extract_message_text(result.content)
                    if obs_text:
                        parts.append(obs_text[:OBSERVATION_MAX_LENGTH])

    return " ".join(parts).lower()


def _extract_message_text(message: str | list[ContentPart] | None) -> str:
    """Extract plain text from a string or ContentPart list."""
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    # list[ContentPart]
    texts: list[str] = []
    for part in message:
        if part.text:
            texts.append(part.text)
    return " ".join(texts)


def _extract_readable_args(arguments: dict | str | None) -> str:
    """Extract string values from tool call arguments."""
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        return arguments
    # dict — extract string-valued entries
    parts: list[str] = []
    for value in arguments.values():
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)
