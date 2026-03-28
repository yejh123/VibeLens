"""Codex CLI skill storage backend (~/.codex/skills/).

Extends DiskSkillStore to also scan the .system/ subdirectory
for built-in skills, with user skills taking precedence.

Directory layout:
    ~/.codex/skills/
    ├── my-skill/SKILL.md          (user-installed)
    └── .system/
        └── built-in-skill/SKILL.md (shipped with Codex)
"""

from pathlib import Path

from vibelens.models.skill import VALID_SKILL_NAME, SkillInfo, SkillSourceType
from vibelens.storage.skill.disk import SKILL_FILENAME, DiskSkillStore


class CodexSkillStore(DiskSkillStore):
    """Skill storage for Codex CLI with user + .system/ scopes."""

    SYSTEM_DIRNAME = ".system"

    def __init__(self, skills_dir: Path) -> None:
        super().__init__(skills_dir, SkillSourceType.CODEX)

    def list_skills(self) -> list[SkillInfo]:
        """Scan both user and built-in Codex skill locations."""
        skills: list[SkillInfo] = []
        seen: set[str] = set()

        for skill_dir in self._iter_skill_dirs():
            name = skill_dir.name
            if name in seen or not VALID_SKILL_NAME.match(name):
                continue
            skill_file = skill_dir / SKILL_FILENAME
            if not skill_file.is_file():
                continue
            info = self._build_skill_info(name, skill_dir, skill_file)
            if info:
                skills.append(info)
                seen.add(name)
        return skills

    def get_skill(self, name: str) -> SkillInfo | None:
        """Look up a single Codex skill, preferring user scope over .system."""
        if not VALID_SKILL_NAME.match(name):
            return None

        candidates = [self._skills_dir / name, self._skills_dir / self.SYSTEM_DIRNAME / name]
        for skill_dir in candidates:
            skill_file = skill_dir / SKILL_FILENAME
            if skill_file.is_file():
                return self._build_skill_info(name, skill_dir, skill_file)
        return None

    def _iter_skill_dirs(self) -> list[Path]:
        """Return both user-scoped and built-in system skill directories.

        User skills are listed first so they take precedence via the
        dedup set in list_skills().
        """
        dirs: list[Path] = []
        if self._skills_dir.is_dir():
            for entry in sorted(self._skills_dir.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    dirs.append(entry)

        system_dir = self._skills_dir / self.SYSTEM_DIRNAME
        if system_dir.is_dir():
            for entry in sorted(system_dir.iterdir()):
                if entry.is_dir():
                    dirs.append(entry)
        return dirs
