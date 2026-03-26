"""Central managed skill repository (~/.vibelens/skills/).

Acts as the authoritative skill store for VibeLens. Skills imported from
agent-native stores (Claude Code, Codex) are copied here with source
metadata injected into the SKILL.md frontmatter so the UI can display
where each skill originated and which interfaces it can be synced to.
"""

from pathlib import Path

import yaml

from vibelens.models.skill import VALID_SKILL_NAME, SkillInfo, SkillSource, SkillSourceType
from vibelens.storage.skill.base import SkillStore
from vibelens.storage.skill.claude_code import (
    FRONTMATTER_DELIMITER,
    SKILL_FILENAME,
    _detect_subdirs,
    _parse_allowed_tools,
    _parse_frontmatter,
)
from vibelens.utils.log import get_logger

logger = get_logger(__name__)


class CentralSkillStore(SkillStore):
    """Central repository for VibeLens-managed skills."""

    def __init__(self, root_dir: Path) -> None:
        super().__init__()
        self._root_dir = root_dir.expanduser().resolve()
        self._root_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_type(self) -> SkillSourceType:
        """Unified source/store type for the central managed store."""
        return SkillSourceType.CENTRAL

    @property
    def skills_dir(self) -> Path:
        """Return the managed skill root directory."""
        return self._root_dir

    def list_skills(self) -> list[SkillInfo]:
        """List all managed skills."""
        skills: list[SkillInfo] = []
        for entry in sorted(self._root_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill = self.get_skill(entry.name)
            if skill:
                skills.append(skill)
        return skills

    def get_skill(self, name: str) -> SkillInfo | None:
        """Read managed metadata from a skill directory."""
        skill_dir = self._root_dir / name
        skill_file = skill_dir / SKILL_FILENAME
        if not skill_file.is_file():
            return None
        if not VALID_SKILL_NAME.match(name):
            return None
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", skill_file, exc)
            return None

        frontmatter = _parse_frontmatter(text)
        description = str(frontmatter.pop("description", ""))
        allowed_tools = _parse_allowed_tools(frontmatter.pop("allowed-tools", None))
        tags = frontmatter.pop("tags", [])
        sources = _parse_sources(frontmatter.pop("sources", None))
        skill_targets = _parse_skill_targets(frontmatter.pop("skill_targets", None))
        if not isinstance(tags, list):
            tags = []
        return SkillInfo(
            name=name,
            description=description,
            sources=sources,
            central_path=skill_dir,
            content_hash=SkillInfo.hash_content(text),
            metadata={
                **frontmatter,
                "allowed_tools": allowed_tools,
                "subdirs": _detect_subdirs(skill_dir),
                "tags": [str(tag) for tag in tags if str(tag).strip()],
                "line_count": text.count("\n") + 1,
            },
            skill_targets=skill_targets,
        )

    def import_skill_from(
        self, source_store: "SkillStore", name: str, overwrite: bool = False
    ) -> SkillInfo | None:
        """Import a skill from another store, injecting source metadata.

        After copying, updates the SKILL.md frontmatter with a ``sources``
        entry recording where the skill came from (source_type + path).
        """
        result = super().import_skill_from(source_store, name, overwrite=overwrite)
        if result is None:
            return None

        # Inject source metadata into frontmatter so the UI shows provenance
        self._inject_source_metadata(name, source_store)
        self.invalidate_cache()
        return self.get_skill(name)

    def _inject_source_metadata(self, name: str, source_store: "SkillStore") -> None:
        """Add source_type and source_path to SKILL.md frontmatter."""
        skill_file = self._root_dir / name / SKILL_FILENAME
        if not skill_file.is_file():
            return

        text = skill_file.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)

        # Build the new source entry from the importing store
        new_source = {
            "source_type": str(source_store.source_type),
            "source_path": str(source_store.skill_path(name)),
        }

        # Merge with existing sources, avoiding duplicates by source_type
        existing_sources = frontmatter.get("sources", [])
        if not isinstance(existing_sources, list):
            existing_sources = []
        existing_types = {s.get("source_type") for s in existing_sources if isinstance(s, dict)}
        if new_source["source_type"] not in existing_types:
            existing_sources.append(new_source)
        frontmatter["sources"] = existing_sources

        # Rebuild SKILL.md with updated frontmatter
        body = _extract_body(text)
        yaml_block = yaml.dump(
            frontmatter, default_flow_style=False, allow_unicode=True
        ).rstrip()
        new_text = (
            f"{FRONTMATTER_DELIMITER}\n{yaml_block}\n"
            f"{FRONTMATTER_DELIMITER}\n{body}"
        )
        skill_file.write_text(new_text, encoding="utf-8")

    def read_content(self, name: str) -> str | None:
        """Read SKILL.md for a managed skill."""
        skill_file = self._root_dir / name / SKILL_FILENAME
        if not skill_file.is_file():
            return None
        return skill_file.read_text(encoding="utf-8")

    def write_skill(self, name: str, content: str) -> Path:
        """Write a managed skill to the central repo."""
        if not VALID_SKILL_NAME.match(name):
            raise ValueError(f"Skill name must be kebab-case: {name!r}")
        skill_dir = self._root_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / SKILL_FILENAME
        skill_file.write_text(content, encoding="utf-8")
        self.invalidate_cache()
        return skill_file

    def delete_skill(self, name: str) -> bool:
        """Delete a managed skill directory."""
        skill_dir = self._root_dir / name
        if not skill_dir.is_dir():
            return False
        for child in sorted(skill_dir.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        skill_dir.rmdir()
        self.invalidate_cache()
        return True


def _extract_body(text: str) -> str:
    """Extract the markdown body after the YAML frontmatter."""
    if not text.startswith(FRONTMATTER_DELIMITER):
        return text
    end_idx = text.find(FRONTMATTER_DELIMITER, len(FRONTMATTER_DELIMITER))
    if end_idx < 0:
        return text
    return text[end_idx + len(FRONTMATTER_DELIMITER) :]


def _parse_sources(raw: object) -> list[SkillSource]:
    """Normalize persisted source metadata into SkillSource objects."""
    if not isinstance(raw, list):
        return []
    sources: list[SkillSource] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source_value = item.get("source_type")
        try:
            sources.append(
                SkillSource(
                    source_type=SkillSourceType(source_value),
                    source_path=str(item.get("source_path", "")),
                )
            )
        except Exception:
            continue
    return sources


def _parse_skill_targets(raw: object) -> list[SkillSourceType]:
    """Normalize persisted target metadata into SkillSourceType values."""
    if not isinstance(raw, list):
        return []
    targets: list[SkillSourceType] = []
    for item in raw:
        try:
            targets.append(SkillSourceType(item))
        except Exception:
            continue
    return targets
