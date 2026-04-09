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
from vibelens.deps import (
    get_example_store,
    get_llm_config,
    get_settings,
    get_trajectory_store,
    reconstruct_upload_registry,
)
from vibelens.models.enums import AppMode
from vibelens.services.dashboard.loader import warm_cache
from vibelens.services.job_tracker import cleanup_stale as cleanup_stale_jobs
from vibelens.services.session.demo import load_demo_examples, seed_example_analyses
from vibelens.services.session.search import (
    build_full_search_index,
    build_search_index,
    refresh_search_index,
)
from vibelens.services.skill.importer import import_agent_skills
from vibelens.utils import get_logger

logger = get_logger(__name__)

# Directory containing the built React frontend assets
STATIC_DIR = Path(__file__).parent / "static"
# How often to evict finished jobs from the in-memory tracker
JOB_CLEANUP_INTERVAL_SECONDS = 600


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize store and start background tasks on startup.

    Only essential setup (store init, demo loading) runs synchronously.
    Skill import and mock seeding run in a thread (lightweight).
    Dashboard cache warming runs as an async task that processes
    sessions in batches, yielding the event loop between batches
    so other endpoints (friction history, LLM status) can respond
    without waiting for all sessions to finish loading.
    """
    settings = get_settings()

    # Initialize the trajectory store (local or disk)
    store = get_trajectory_store()
    store.initialize()
    _log_startup_summary(settings, store)

    # Load example sessions (demo: required, self: for example analyses)
    if settings.example_session_paths:
        example_store = get_example_store()
        example_store.initialize()
        loaded = load_demo_examples(settings, example_store)
        if loaded:
            logger.info("Loaded %d example trajectory groups", loaded)

    if settings.app_mode == AppMode.DEMO:
        reconstruct_upload_registry()

    # Lightweight startup tasks in a thread (no heavy I/O)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_background_startup)

    # Tier 1: instant metadata-based search index (no disk I/O, <100ms)
    build_search_index()

    # Tier 2: full-text search index built in background thread
    asyncio.create_task(_async_build_full_search_index())

    # Dashboard cache warming as an async background task so it yields
    # the event loop between session batches instead of holding the GIL
    asyncio.create_task(_async_warm_cache())

    # Periodic incremental search index refresh (diff-based, <1s typical)
    search_refresh_task = asyncio.create_task(_periodic_search_refresh())

    # Periodic cleanup of finished job tracker entries to prevent memory leak
    cleanup_task = asyncio.create_task(_periodic_job_cleanup())

    yield

    search_refresh_task.cancel()
    cleanup_task.cancel()


async def _periodic_job_cleanup() -> None:
    """Evict finished jobs from the in-memory tracker every 10 minutes."""
    while True:
        await asyncio.sleep(JOB_CLEANUP_INTERVAL_SECONDS)
        try:
            cleanup_stale_jobs()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Job cleanup failed", exc_info=True)


async def _async_build_full_search_index() -> None:
    """Build the full-text (Tier 2) search index in a background thread."""
    try:
        await asyncio.to_thread(build_full_search_index)
    except Exception:
        logger.warning("Full search index build failed", exc_info=True)


# How often to diff-refresh the search index for new sessions
SEARCH_REFRESH_INTERVAL_SECONDS = 300


async def _periodic_search_refresh() -> None:
    """Incrementally refresh the search index every 5 minutes.

    Uses diff-based refresh that only loads new sessions and removes
    stale ones, completing in <1s for typical workloads.
    """
    while True:
        await asyncio.sleep(SEARCH_REFRESH_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(refresh_search_index)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Search index refresh failed", exc_info=True)


async def _async_warm_cache() -> None:
    """Run dashboard cache warming in the background, yielding periodically.

    Wraps the synchronous warm_cache() in asyncio.to_thread so it runs
    in the default thread pool. Unlike run_in_executor fire-and-forget,
    this is a proper task that can be awaited and doesn't silently swallow
    exceptions.
    """
    try:
        await asyncio.to_thread(warm_cache)
    except Exception:
        logger.warning("Dashboard cache warming failed", exc_info=True)


def _run_background_startup() -> None:
    """Run lightweight startup tasks in a background thread.

    Skill import and example seeding are fast and don't involve heavy
    JSON parsing, so a thread is fine.
    """
    import_agent_skills()
    seed_example_analyses()


def _log_startup_summary(settings, store) -> None:
    """Log a single-line startup summary with key configuration details."""
    llm_config = get_llm_config()
    store_type = type(store).__name__
    logger.info(
        "VibeLens v%s started: mode=%s store=%s llm_backend=%s host=%s:%d",
        __version__,
        settings.app_mode.value,
        store_type,
        llm_config.backend.value,
        settings.host,
        settings.port,
    )


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
