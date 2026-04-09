"""Import skills from agent CLIs into the central managed repository."""

from vibelens.deps import (
    get_agent_skill_stores,
    get_central_skill_store,
    get_claude_skill_store,
    get_codex_skill_store,
)
from vibelens.utils import get_logger

logger = get_logger(__name__)


def import_agent_skills() -> int:
    """Import skills from all agent interfaces into the central store.

    Scans Claude Code, Codex, and all third-party agent skill directories,
    copying any skills not already present in the central repository
    (~/.vibelens/skills/). Existing central skills are never overwritten
    to preserve user edits.

    Returns:
        Total number of skills imported.
    """
    central = get_central_skill_store()
    agent_stores = [
        ("claude_code", get_claude_skill_store()),
        ("codex", get_codex_skill_store()),
        *((s.source_type.value, s) for s in get_agent_skill_stores()),
    ]
    total_imported = 0
    for label, store in agent_stores:
        try:
            imported = central.import_all_from(store, overwrite=False)
            if imported:
                logger.info("Imported %d skills from %s into central store", len(imported), label)
                total_imported += len(imported)
        except Exception:
            logger.warning("Failed to import skills from %s", label, exc_info=True)

    if total_imported:
        logger.info("Total skills imported into central store: %d", total_imported)
    return total_imported
