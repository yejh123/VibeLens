"""FastAPI application factory."""

import asyncio
import contextlib
import json
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
    get_agent_skill_stores,
    get_central_skill_store,
    get_codex_skill_store,
    get_example_store,
    get_llm_config,
    get_skill_store,
    get_store,
    reconstruct_upload_registry,
)
from vibelens.models.enums import AppMode
from vibelens.services.dashboard.loader import warm_cache
from vibelens.services.job_tracker import cleanup_stale as cleanup_stale_jobs
from vibelens.services.session.demo import load_demo_examples
from vibelens.services.session.search import (
    build_full_search_index,
    build_search_index,
    refresh_search_index,
)
from vibelens.utils import get_logger

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

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
    settings = load_settings()

    # Initialize the trajectory store (local or disk)
    store = get_store()
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
    loop.run_in_executor(None, _lightweight_startup, settings)

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


def _lightweight_startup(settings) -> None:
    """Run lightweight startup tasks in a background thread.

    Skill import and example seeding are fast and don't involve heavy
    JSON parsing, so a thread is fine.
    """
    _load_agent_skills_into_central_store()
    _seed_example_analyses()


def _load_agent_skills_into_central_store() -> None:
    """Import skills from all agent interfaces into the central store on startup.

    Scans Claude Code, Codex, and all third-party agent skill directories,
    copying any skills not already present in the central repository (~/.vibelens/skills/).
    Existing central skills are never overwritten to preserve user edits.
    """
    central = get_central_skill_store()
    agent_stores = [
        ("claude_code", get_skill_store()),
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


def _seed_example_analyses() -> None:
    """Copy pre-built example analyses into the user's analysis stores.

    Looks for bundled example analyses adjacent to the configured example
    session paths (e.g. examples/recipe-book/friction_analyses/). Only
    copies when the target store is empty to avoid overwriting user data.
    """
    settings = load_settings()
    for example_path in settings.example_session_paths:
        if not example_path.is_dir():
            continue
        _copy_example_store(example_path / "friction_analyses", settings.friction_dir, "friction")
        _copy_example_store(example_path / "skill_analyses", settings.skill_analysis_dir, "skill")


def _copy_example_store(src_dir: Path, dst_dir: Path, label: str) -> None:
    """Copy example analysis files from a bundled directory into the user store.

    Appends example entries alongside any existing user analyses. Skips
    individual files that already exist in the destination to avoid
    overwriting user data or duplicating on repeated startups.

    Args:
        src_dir: Bundled example analyses directory.
        dst_dir: User's analysis store directory.
        label: Human-readable label for logging.
    """
    if not src_dir.is_dir():
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    src_index = src_dir / "index.jsonl"
    if not src_index.exists():
        return

    # Copy result JSON files, injecting is_example flag for frontend display
    copied = 0
    for src_file in src_dir.iterdir():
        if src_file.suffix == ".json" and not (dst_dir / src_file.name).exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                data = json.loads(src_file.read_text(encoding="utf-8"))
                data["is_example"] = True
                (dst_dir / src_file.name).write_text(json.dumps(data, indent=2), encoding="utf-8")
                copied += 1

    if copied == 0:
        return

    # Append new index entries (skip IDs already present)
    existing_ids: set[str] = set()
    dst_index = dst_dir / "index.jsonl"
    if dst_index.exists():
        for line in dst_index.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                existing_ids.add(json.loads(line).get("analysis_id", ""))

    new_lines = []
    for line in src_index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(json.JSONDecodeError, ValueError):
            entry = json.loads(line)
            if entry.get("analysis_id", "") not in existing_ids:
                entry["is_example"] = True
                new_lines.append(json.dumps(entry))

    if new_lines:
        with dst_index.open("a", encoding="utf-8") as f:
            for line in new_lines:
                f.write(line + "\n")

    logger.info("Seeded %d example %s analysis files", copied, label)


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
