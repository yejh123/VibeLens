"""Skill digest helpers for LLM skill analysis."""

from collections import Counter

from vibelens.models.analysis.friction import StepSignal
from vibelens.services.friction.digest import (
    DigestLimits,
    _format_step,
    _group_by_session,
    select_limits,
)
from vibelens.utils.text import extract_text, truncate

MAX_FREQUENCY_LINES = 15


def digest_step_signals_for_skills(
    signals: list[StepSignal], limits: DigestLimits | None = None
) -> str:
    """Serialize StepSignals into prompt text optimized for skill detection."""
    if not signals:
        return "[no steps]"

    if limits is None:
        limits = select_limits(len(signals))

    grouped = _group_by_session(signals)
    parts: list[str] = []
    for session_id, session_signals in grouped.items():
        parts.append(_format_skill_session(session_id, session_signals, limits))
    return "\n\n".join(parts)


def _format_skill_session(session_id: str, signals: list[StepSignal], limits: DigestLimits) -> str:
    first = signals[0]
    header_lines = [f"=== SESSION: {session_id} ==="]
    if first.project_path:
        header_lines.append(f"PROJECT: {first.project_path}")

    model_name = first.step.model_name
    if model_name:
        header_lines.append(f"MODEL: {model_name}")
    header_lines.append(f"STEPS: {len(signals)}")

    freq_lines = _build_tool_frequency(signals)
    if freq_lines:
        header_lines.append("")
        header_lines.append("TOOL FREQUENCY:")
        header_lines.extend(freq_lines)

    themes = _extract_prompt_themes(signals)
    if themes:
        header_lines.append("")
        header_lines.append(f"USER TOPICS: {themes}")

    header = "\n".join(header_lines)
    step_lines = [_format_step(signal, limits) for signal in signals]
    return header + "\n\n" + "\n\n".join(step_lines)


def _build_tool_frequency(signals: list[StepSignal]) -> list[str]:
    counter: Counter[str] = Counter()
    for signal in signals:
        for tc in signal.step.tool_calls:
            counter[tc.function_name] += 1

    if not counter:
        return []

    return [
        f"  {tool_name}: {count}" for tool_name, count in counter.most_common(MAX_FREQUENCY_LINES)
    ]


def _extract_prompt_themes(signals: list[StepSignal]) -> str:
    user_messages: list[str] = []
    for signal in signals:
        if signal.step.source.value == "user":
            text = extract_text(signal.step.message)
            if text.strip():
                user_messages.append(truncate(text.strip(), 60))

    if not user_messages:
        return ""

    return " | ".join(user_messages[:5])
