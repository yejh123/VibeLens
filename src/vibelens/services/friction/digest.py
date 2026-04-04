"""Friction digest — format batched session contexts for LLM prompts.

Thin layer that concatenates pre-extracted session contexts from
context_extraction.py into a single digest string for one LLM batch.
"""

from vibelens.services.session_batcher import SessionBatch


def format_batch_digest(batch: SessionBatch) -> str:
    """Concatenate pre-extracted session contexts for one LLM prompt.

    Args:
        batch: SessionBatch containing pre-extracted session contexts.

    Returns:
        Formatted digest text with all session contexts.
    """
    if not batch.session_contexts:
        return "[no sessions]"

    parts = [ctx.context_text for ctx in batch.session_contexts]
    return "\n\n".join(parts)
