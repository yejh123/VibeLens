"""Skill analysis result persistence."""

import json
import secrets
from pathlib import Path

from vibelens.models.analysis.skills import SkillAnalysisResult
from vibelens.schemas.skills import SkillAnalysisMeta
from vibelens.utils.log import get_logger

logger = get_logger(__name__)

TOKEN_BYTES = 12
SUMMARY_PREVIEW_LENGTH = 120


class SkillAnalysisStore:
    """Manages persisted skill analysis results on disk."""

    def __init__(self, store_dir: Path):
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _data_path(self, analysis_id: str) -> Path:
        return self._dir / f"{analysis_id}.json"

    def _meta_path(self, analysis_id: str) -> Path:
        return self._dir / f"{analysis_id}.meta.json"

    def save(self, result: SkillAnalysisResult) -> SkillAnalysisMeta:
        analysis_id = secrets.token_urlsafe(TOKEN_BYTES)
        result.analysis_id = analysis_id

        self._data_path(analysis_id).write_text(result.model_dump_json(indent=2), encoding="utf-8")

        meta = _build_meta(analysis_id, result)
        self._meta_path(analysis_id).write_text(meta.model_dump_json(indent=2), encoding="utf-8")

        logger.info(
            "Saved skill analysis %s (mode=%s, %d patterns)",
            analysis_id,
            result.mode,
            len(result.workflow_patterns),
        )
        return meta

    def load(self, analysis_id: str) -> SkillAnalysisResult | None:
        path = self._data_path(analysis_id)
        if not path.exists():
            return None
        return SkillAnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))

    def list_analyses(self) -> list[SkillAnalysisMeta]:
        analyses: list[SkillAnalysisMeta] = []
        for meta_path in self._dir.glob("*.meta.json"):
            try:
                meta = SkillAnalysisMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
                analyses.append(meta)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Skipping corrupt skill analysis metadata: %s", meta_path)
        analyses.sort(key=lambda m: m.computed_at, reverse=True)
        return analyses

    def delete(self, analysis_id: str) -> bool:
        data_path = self._data_path(analysis_id)
        meta_path = self._meta_path(analysis_id)
        if not data_path.exists() and not meta_path.exists():
            return False
        data_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        logger.info("Deleted skill analysis %s", analysis_id)
        return True


def _build_meta(analysis_id: str, result: SkillAnalysisResult) -> SkillAnalysisMeta:
    preview = result.summary[:SUMMARY_PREVIEW_LENGTH]
    if len(result.summary) > SUMMARY_PREVIEW_LENGTH:
        preview += "..."

    return SkillAnalysisMeta(
        analysis_id=analysis_id,
        mode=result.mode,
        session_ids=result.session_ids,
        pattern_count=len(result.workflow_patterns),
        summary_preview=preview,
        computed_at=result.computed_at,
        model=result.model,
        cost_usd=result.cost_usd,
    )
