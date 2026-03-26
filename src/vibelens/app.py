"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vibelens import __version__
from vibelens.api import build_router
from vibelens.config import load_settings
from vibelens.deps import (
    get_central_skill_store,
    get_codex_skill_store,
    get_skill_analysis_store,
    get_skill_store,
    get_store,
)
from vibelens.models.enums import AppMode
from vibelens.services.dashboard_service import warm_cache
from vibelens.services.demo_loader import load_demo_examples
from vibelens.storage.conversation.disk import DiskStore
from vibelens.utils import get_logger

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize store and start background tasks on startup.

    Only essential setup (store init, demo loading) runs synchronously.
    All other work (skill import, mock seeding, cache warming) is
    deferred to a background thread so the server accepts requests
    immediately — the session list is available on first API call.
    """
    settings = load_settings()

    # Initialize the trajectory store (local or disk)
    store = get_store()
    store.initialize()

    if settings.app_mode == AppMode.DEMO:
        assert isinstance(store, DiskStore), "Demo mode requires DiskStore"
        loaded = load_demo_examples(settings, store)
        if loaded:
            logger.info("Loaded %d trajectory groups for demo mode", loaded)

    # Run remaining startup work in background so the server is ready immediately
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _background_startup, settings)

    yield


def _background_startup(settings) -> None:
    """Run non-critical startup tasks in a background thread.

    Skill import, mock seeding, and cache warming don't need to
    complete before the server starts serving requests.
    """
    _load_agent_skills_into_central_store()
    if settings.app_mode in (AppMode.TEST, AppMode.DEMO):
        _seed_mock_skill_history()
    warm_cache()


def _load_agent_skills_into_central_store() -> None:
    """Import skills from all agent interfaces into the central store on startup.

    Scans Claude Code (~/.claude/skills/) and Codex (~/.codex/skills/) stores,
    copying any skills not already present in the central repository (~/.vibelens/skills/).
    Existing central skills are never overwritten to preserve user edits.
    """
    central = get_central_skill_store()
    agent_stores = [("claude_code", get_skill_store()), ("codex", get_codex_skill_store())]
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


def _seed_mock_skill_history() -> None:
    """Pre-populate skill analysis history with one record per mode.

    Picks the first 3 available session IDs from the trajectory store
    and generates mock analysis results for retrieval, creation, and
    evolution modes so the History sidebar has sample entries.
    """
    from vibelens.models.analysis.skills import SkillMode
    from vibelens.services.mock import build_mock_skill_result

    analysis_store = get_skill_analysis_store()

    # Skip seeding if history already has records
    if analysis_store.list_analyses():
        return

    store = get_store()
    metadata = store.list_metadata()
    session_ids = [m["session_id"] for m in metadata if "session_id" in m][:3]
    if not session_ids:
        logger.info("No sessions available to seed skill analysis history")
        return

    for mode in (SkillMode.RETRIEVAL, SkillMode.CREATION, SkillMode.EVOLUTION):
        try:
            result = build_mock_skill_result(session_ids, mode)
            analysis_store.save(result)
            logger.info("Seeded mock skill analysis history: mode=%s", mode)
        except Exception:
            logger.warning("Failed to seed mock skill analysis for mode=%s", mode, exc_info=True)


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(title="VibeLens", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router(), prefix="/api")

    if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app
