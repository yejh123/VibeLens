"""Context extraction — compress trajectory groups into LLM-ready text.

Extracts compressed context from a session's trajectory group (main + sub-agents).
Compaction-aware: detects compaction sub-agents (flagged via ``extra["is_compaction_agent"]``)
and uses their summaries alongside the full step chronology.

Reusable by friction analysis, skill analysis, and other LLM-powered modules.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from vibelens.models.enums import StepSource
from vibelens.models.trajectories import Trajectory
from vibelens.models.trajectories.step import Step
from vibelens.utils.log import get_logger
from vibelens.utils.text import extract_text, is_error_content, truncate

logger = get_logger(__name__)

BASH_COMMAND_MAX_CHARS = 80
ERROR_TRUNCATE_CHARS = 300
USER_PROMPT_MAX_CHARS = 2000
USER_PROMPT_HEAD_CHARS = 1500
USER_PROMPT_TAIL_CHARS = 500

# Tool-specific argument keys to extract for summarization
TOOL_ARG_KEYS: dict[str, list[str]] = {
    "Write": ["file_path"],
    "Edit": ["file_path"],
    "Read": ["file_path"],
    "Bash": ["command"],
    "Glob": ["pattern", "path"],
    "Grep": ["pattern", "path"],
    "WebFetch": ["url"],
    "WebSearch": ["query"],
}


@dataclass
class _IndexTracker:
    """Assigns sequential 0-based indices to steps during formatting."""

    _counter: int = 0
    index_to_real_id: dict[int, str] = field(default_factory=dict)

    def assign(self, real_id: str) -> int:
        """Assign the next sequential index to a real step ID."""
        idx = self._counter
        self.index_to_real_id[idx] = real_id
        self._counter += 1
        return idx


@dataclass
class IdMapping:
    """Maps 0-indexed synthetic IDs back to real UUIDs."""

    session_index_to_id: dict[int, str] = field(default_factory=dict)
    step_index_to_id: dict[int, dict[int, str]] = field(default_factory=dict)

    def resolve_session_id(self, synthetic: str) -> str | None:
        """Convert a synthetic session index string (e.g. "0") to real UUID."""
        try:
            idx = int(synthetic)
        except (ValueError, TypeError):
            return None
        return self.session_index_to_id.get(idx)

    def resolve_step_id(self, session_index: int, synthetic: str) -> str | None:
        """Convert a synthetic step index string (e.g. "5") to real UUID."""
        try:
            step_idx = int(synthetic)
        except (ValueError, TypeError):
            return None
        step_map = self.step_index_to_id.get(session_index)
        if step_map is None:
            return None
        return step_map.get(step_idx)


@dataclass
class SessionContext:
    """Compressed context for one session, ready for LLM consumption."""

    session_id: str
    project_path: str | None
    context_text: str
    char_count: int
    trajectory_group: list[Trajectory] = field(repr=False)
    last_trajectory_ref_id: str | None = None
    continued_trajectory_ref_id: str | None = None
    timestamp: datetime | None = None
    step_index_map: dict[int, str] = field(default_factory=dict)


def extract_session_context(trajectory_group: list[Trajectory]) -> SessionContext:
    """Extract compressed context from a session's trajectory group.

    Detects compaction sub-agents and adapts extraction strategy:
    - With compactions: compaction summaries interleaved with steps chronologically
    - Without compactions: all steps with user messages, tool calls, and errors

    Steps use 0-indexed IDs via _IndexTracker for compact LLM prompts.
    The mapping from index → real UUID is stored in step_index_map.

    Args:
        trajectory_group: All trajectories for one session (main + sub-agents).

    Returns:
        SessionContext with compressed text representation.
    """
    main = _find_main_trajectory(trajectory_group)
    compaction_agents = _find_compaction_agents(trajectory_group)
    tracker = _IndexTracker()

    # Extract context text with or without compaction-aware formatting
    if compaction_agents:
        context_text = _extract_with_compactions(main, compaction_agents, tracker)
    else:
        context_text = _extract_without_compactions(main, tracker)

    header = _build_header(main)
    full_text = f"{header}\n\n{context_text}"

    return SessionContext(
        session_id=main.session_id,
        project_path=main.project_path,
        context_text=full_text,
        char_count=len(full_text),
        trajectory_group=trajectory_group,
        last_trajectory_ref_id=(
            main.last_trajectory_ref.session_id if main.last_trajectory_ref else None
        ),
        continued_trajectory_ref_id=(
            main.continued_trajectory_ref.session_id if main.continued_trajectory_ref else None
        ),
        timestamp=main.timestamp,
        step_index_map=tracker.index_to_real_id,
    )


def _find_main_trajectory(trajectory_group: list[Trajectory]) -> Trajectory:
    """Find the main (non-sub-agent) trajectory in the group.

    The main trajectory is the one without a parent_trajectory_ref, meaning
    it was not spawned as a sub-agent. For single-trajectory groups (e.g.
    Dataclaw, Codex single-session), the first trajectory is returned as
    a safe fallback since it has no parent_ref by definition.
    """
    for t in trajectory_group:
        if t.parent_trajectory_ref is None:
            return t
    return trajectory_group[0]


def _find_compaction_agents(trajectory_group: list[Trajectory]) -> list[Trajectory]:
    """Find compaction sub-agents sorted by timestamp.

    Compaction agents are detected via the ``extra["is_compaction_agent"]`` flag
    set by parsers during ingestion. This decouples detection from any
    agent-specific session_id naming convention.

    Parser contract: parsers that encounter compaction sub-agents must set
    ``extra={"is_compaction_agent": True}`` on the Trajectory. Currently only
    the Claude Code parser produces compaction agents (``acompact-*`` files).
    """
    compaction = [t for t in trajectory_group if (t.extra or {}).get("is_compaction_agent")]
    compaction.sort(key=lambda t: t.timestamp or datetime.min)
    return compaction


def _build_header(main: Trajectory) -> str:
    """Build the session header block."""
    lines = [f"=== SESSION: {main.session_id} ==="]
    if main.project_path:
        lines.append(f"PROJECT: {main.project_path}")
    return "\n".join(lines)


def _extract_with_compactions(
    main: Trajectory, compaction_agents: list[Trajectory], tracker: _IndexTracker
) -> str:
    """Extract context for sessions WITH compaction sub-agents.

    Interleaves compaction summaries at their chronological position among steps.
    Each summary is inserted just before the first step whose timestamp exceeds
    the compaction boundary. Falls back to summaries-first if timestamps are unavailable.
    """
    boundaries = _build_compaction_boundaries(compaction_agents)
    parts: list[str] = []

    # Track which boundaries have been inserted
    boundary_idx = 0
    summary_counter = 0

    for step in main.steps:
        # Insert any compaction summaries whose timestamp precedes this step
        while boundary_idx < len(boundaries):
            boundary_ts, summary_text = boundaries[boundary_idx]
            step_ts = step.timestamp

            # If either timestamp is missing, defer to fallback (summaries first)
            if boundary_ts is None or step_ts is None:
                break

            if boundary_ts < step_ts:
                summary_counter += 1
                parts.append(f"--- COMPACTION SUMMARY {summary_counter} ---")
                parts.append(summary_text)
                boundary_idx += 1
            else:
                break

        formatted = _format_step(step, tracker)
        if formatted:
            parts.append(formatted)

    # Append any remaining summaries that follow all steps
    while boundary_idx < len(boundaries):
        _, summary_text = boundaries[boundary_idx]
        summary_counter += 1
        parts.append(f"--- COMPACTION SUMMARY {summary_counter} ---")
        parts.append(summary_text)
        boundary_idx += 1

    return "\n\n".join(parts)


def _extract_without_compactions(main: Trajectory, tracker: _IndexTracker) -> str:
    """Extract context for sessions WITHOUT compaction.

    Includes user messages (truncated if long), agent steps with tool calls
    (function name + key args only), and error observations in full.
    """
    parts: list[str] = []
    for step in main.steps:
        formatted = _format_step(step, tracker)
        if formatted:
            parts.append(formatted)
    return "\n\n".join(parts)


def _build_compaction_boundaries(
    compaction_agents: list[Trajectory],
) -> list[tuple[datetime | None, str]]:
    """Build timestamped compaction summaries sorted by timestamp.

    Each compaction agent typically has step[0] as system/user prompt and
    step[1] as the agent's summary response. The agent's trajectory timestamp
    marks when the compaction occurred.

    Returns:
        Sorted list of (timestamp, summary_text) pairs.
    """
    boundaries: list[tuple[datetime | None, str]] = []
    for agent in compaction_agents:
        for step in agent.steps:
            if step.source == StepSource.AGENT:
                summary = extract_text(step.message)
                if summary.strip():
                    boundaries.append((agent.timestamp, summary.strip()))
                break
    boundaries.sort(key=lambda b: b[0] or datetime.min)
    return boundaries


def _truncate_user_prompt(message: str) -> str:
    """Truncate long user prompts to save tokens.

    Keeps the first USER_PROMPT_HEAD_CHARS and last USER_PROMPT_TAIL_CHARS
    with a truncation marker in between.
    """
    if len(message) <= USER_PROMPT_MAX_CHARS:
        return message
    head = message[:USER_PROMPT_HEAD_CHARS]
    tail = message[-USER_PROMPT_TAIL_CHARS:]
    return f"{head}\n[...truncated...]\n{tail}"


def _format_step(step: Step, tracker: _IndexTracker) -> str:
    """Format a step with 0-indexed IDs, truncated user prompts, and tool info.

    Filtering logic:
    - USER steps: truncate long messages, assign 0-indexed step ID
    - AGENT steps: include only if they have tool calls or error observations.
      Agent-only text responses (no tools, no errors) are skipped to reduce noise.
    - SYSTEM steps: skipped entirely (internal prompts, not useful for analysis)

    Observations are scanned for error content (stderr, exception traces) which
    is included truncated. Non-error tool output is omitted to keep context compact.
    """
    lines: list[str] = []

    if step.source == StepSource.USER:
        message = extract_text(step.message)
        if message.strip():
            idx = tracker.assign(step.step_id)
            truncated = _truncate_user_prompt(message.strip())
            lines.append(f"[step_id={idx}] USER: {truncated}")

    elif step.source == StepSource.AGENT:
        idx = tracker.assign(step.step_id)
        agent_lines = [f"[step_id={idx}] AGENT:"]
        for tc in step.tool_calls:
            tool_summary = _summarize_tool_args(tc.function_name, tc.arguments)
            agent_lines.append(f"  TOOL: fn={tc.function_name} {tool_summary}")

        # Include error observations — Dataclaw trajectories may have no
        # observation at all, so the None check is required for compatibility
        if step.observation:
            for result in step.observation.results:
                content = extract_text(result.content)
                if is_error_content(content):
                    error_text = truncate(content, ERROR_TRUNCATE_CHARS)
                    agent_lines.append(f"  ERROR: {error_text}")

        # Only include agent step if it has tool calls or errors (len > 1
        # means something beyond the header line was added)
        if len(agent_lines) > 1:
            lines.extend(agent_lines)

    return "\n".join(lines)


def _summarize_tool_args(function_name: str, arguments) -> str:
    """Summarize tool call arguments based on tool-specific rules.

    For known tools (Edit, Read, Bash, etc.), extracts only the key arguments
    defined in TOOL_ARG_KEYS. For unknown tools, falls back to checking common
    argument names (file_path, path, pattern, query, url, command) and shows
    the first match found.

    Args:
        function_name: Name of the tool function.
        arguments: Tool call arguments (dict, str, or None).

    Returns:
        Compact argument summary string.
    """
    if arguments is None:
        return ""
    if not isinstance(arguments, dict):
        return truncate(str(arguments), BASH_COMMAND_MAX_CHARS)

    keys_to_show = TOOL_ARG_KEYS.get(function_name)
    if keys_to_show:
        parts = []
        for key in keys_to_show:
            value = arguments.get(key)
            if value is not None:
                val_str = str(value)
                if function_name == "Bash" and key == "command":
                    val_str = truncate(val_str, BASH_COMMAND_MAX_CHARS)
                parts.append(f"{key}={val_str}")
        return " ".join(parts) if parts else ""

    # Unknown tool: show first recognized key if any
    for key in ("file_path", "path", "pattern", "query", "url", "command"):
        if key in arguments:
            return f"{key}={truncate(str(arguments[key]), BASH_COMMAND_MAX_CHARS)}"
    return ""


def remap_session_ids(contexts: list[SessionContext]) -> IdMapping:
    """Assign 0-based session indices and replace session_id in context_text.

    Mutates each context's context_text, replacing the real session UUID
    in the header with a 0-based index. Returns the combined mapping for
    resolving synthetic IDs back to real UUIDs after LLM inference.

    Args:
        contexts: Session contexts to remap (mutated in place).

    Returns:
        IdMapping with session and step index→UUID mappings.
    """
    mapping = IdMapping()
    for idx, ctx in enumerate(contexts):
        mapping.session_index_to_id[idx] = ctx.session_id
        mapping.step_index_to_id[idx] = dict(ctx.step_index_map)

        # Replace the session UUID in the header line
        ctx.context_text = re.sub(
            rf"=== SESSION: {re.escape(ctx.session_id)} ===",
            f"=== SESSION: {idx} ===",
            ctx.context_text,
            count=1,
        )
        ctx.char_count = len(ctx.context_text)
    return mapping
