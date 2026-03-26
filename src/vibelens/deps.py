"""Dependency injection singletons for VibeLens."""

from pathlib import Path

from vibelens.config import LLMConfig, Settings, load_llm_config, load_settings, save_llm_config
from vibelens.config.llm_config import DEFAULT_LLM_CONFIG_PATH, discover_llm_config_path
from vibelens.llm.backend import InferenceBackend
from vibelens.models.enums import AppMode
from vibelens.storage.conversation.base import TrajectoryStore
from vibelens.storage.conversation.disk import DiskStore
from vibelens.storage.conversation.local import LocalStore

_settings: Settings | None = None
_llm_config: LLMConfig | None = None
_store: TrajectoryStore | None = None
_share_service = None
_friction_store = None
_skill_store = None
_central_skill_store = None
_codex_skill_store = None
_skill_analysis_store = None
_inference_backend: InferenceBackend | None = None
_inference_checked = False

DATASETS_ROOT = Path("datasets")


def get_settings() -> Settings:
    """Return cached application settings."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def is_demo_mode() -> bool:
    """Check whether the application is running in demo mode."""
    return get_settings().app_mode == AppMode.DEMO


def is_test_mode() -> bool:
    """Check whether the application is running in test mode."""
    return get_settings().app_mode == AppMode.TEST


def get_share_service():
    """Return cached ShareService singleton."""
    from vibelens.services.share_service import ShareService

    global _share_service
    if _share_service is None:
        _share_service = ShareService(get_settings().share_dir)
    return _share_service


def get_friction_store():
    """Return cached FrictionStore singleton."""
    from vibelens.services.friction.store import FrictionStore

    global _friction_store
    if _friction_store is None:
        _friction_store = FrictionStore(get_settings().friction_dir)
    return _friction_store


def get_skill_store():
    """Return cached ClaudeCodeSkillStore singleton."""
    from vibelens.storage.skill.claude_code import ClaudeCodeSkillStore

    global _skill_store
    if _skill_store is None:
        _skill_store = ClaudeCodeSkillStore(get_settings().skills_dir)
    return _skill_store


def get_codex_skill_store():
    """Return cached CodexSkillStore singleton."""
    from vibelens.storage.skill.codex import CodexSkillStore

    global _codex_skill_store
    if _codex_skill_store is None:
        _codex_skill_store = CodexSkillStore(get_settings().codex_dir / "skills")
    return _codex_skill_store


def get_central_skill_store():
    """Return cached central managed skill repository."""
    from vibelens.storage.skill.central import CentralSkillStore

    global _central_skill_store
    if _central_skill_store is None:
        _central_skill_store = CentralSkillStore(get_settings().managed_skills_dir)
    return _central_skill_store


def get_skill_analysis_store():
    """Return cached SkillAnalysisStore singleton."""
    from vibelens.services.skill.analysis_store import SkillAnalysisStore

    global _skill_analysis_store
    if _skill_analysis_store is None:
        _skill_analysis_store = SkillAnalysisStore(get_settings().skill_analysis_dir)
    return _skill_analysis_store


def get_llm_config() -> LLMConfig:
    """Return cached LLM configuration, lazy-loading from YAML/env."""
    global _llm_config
    if _llm_config is None:
        _llm_config = load_llm_config()
    return _llm_config


def set_llm_config(config: LLMConfig) -> None:
    """Update LLM config singleton, persist to YAML, and recreate backend."""
    global _llm_config
    _llm_config = config

    config_path = discover_llm_config_path() or DEFAULT_LLM_CONFIG_PATH
    save_llm_config(config, config_path)

    from vibelens.llm.backends import create_backend_from_llm_config

    backend = create_backend_from_llm_config(config)
    set_inference_backend(backend)


def get_inference_backend() -> InferenceBackend | None:
    """Return cached InferenceBackend, or None if disabled."""
    global _inference_backend, _inference_checked
    if _inference_checked:
        return _inference_backend
    _inference_checked = True

    from vibelens.llm.backends import create_backend_from_llm_config

    _inference_backend = create_backend_from_llm_config(get_llm_config())
    return _inference_backend


def set_inference_backend(backend: InferenceBackend | None) -> None:
    """Replace the inference backend singleton at runtime."""
    global _inference_backend, _inference_checked
    _inference_backend = backend
    _inference_checked = True


def get_store() -> TrajectoryStore:
    """Return cached TrajectoryStore singleton.

    In demo mode returns DiskStore; in self mode returns LocalStore.
    """
    global _store
    if _store is None:
        _store = DiskStore(DATASETS_ROOT) if is_demo_mode() else LocalStore(settings=get_settings())
    return _store
