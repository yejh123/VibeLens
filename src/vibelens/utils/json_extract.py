"""Shared JSON extraction utilities for LLM output parsing.

LLMs often wrap JSON responses in markdown code fences, sometimes with
preamble text before the fence. These helpers robustly extract the JSON
content regardless of formatting.
"""

import re

# Greedy match: finds opening ```json fence and extends to the LAST closing ```.
# Greedy (.*) is required because the JSON value itself may contain embedded
# triple backticks (e.g. markdown code blocks inside a skill_md_content string).
_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(.*)\n```",
    re.DOTALL,
)


def extract_json(text: str) -> str:
    """Extract JSON from LLM output, handling markdown code blocks.

    Handles three cases:
    1. Plain JSON (no fences) — returned as-is after stripping.
    2. JSON wrapped in ``` fences at the start of output.
    3. Text preamble before a fenced JSON block
       (e.g. "Here is the output:\\n```json\\n{...}\\n```").

    Args:
        text: Raw LLM output text.

    Returns:
        Extracted JSON string.
    """
    stripped = text.strip()
    if not stripped:
        return stripped

    # Search for a code-fenced block anywhere in the text
    match = _CODE_FENCE_RE.search(stripped)
    if match:
        return match.group(1).strip()

    return stripped


def repair_truncated_json(text: str) -> str:
    """Attempt to repair JSON truncated by max_tokens.

    Strategy: strip trailing incomplete tokens, fix unbalanced quotes,
    then count unclosed braces/brackets and append closing characters.

    Args:
        text: Truncated JSON string.

    Returns:
        Best-effort repaired JSON string.
    """
    trimmed = text.rstrip()

    # Strip trailing JSON noise (dangling commas, colons, whitespace)
    while trimmed and trimmed[-1] in (",", ":", " ", "\n", "\r", "\t"):
        trimmed = trimmed[:-1]

    # Fix unbalanced quotes by truncating to last complete string
    if trimmed.count('"') % 2 != 0:
        last_quote = trimmed.rfind('"')
        if last_quote > 0:
            trimmed = trimmed[: last_quote + 1]

    # Count unclosed braces/brackets (respecting string boundaries)
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False

    for char in trimmed:
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            open_braces += 1
        elif char == "}":
            open_braces -= 1
        elif char == "[":
            open_brackets += 1
        elif char == "]":
            open_brackets -= 1

    # Append closing characters (brackets before braces for valid nesting)
    suffix = "]" * max(open_brackets, 0) + "}" * max(open_braces, 0)
    return trimmed + suffix
