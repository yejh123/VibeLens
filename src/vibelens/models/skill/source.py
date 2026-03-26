"""Source metadata for skills."""

from enum import StrEnum

from pydantic import BaseModel, Field

from vibelens.models.enums import AgentType


class SkillSourceType(StrEnum):
    """Unified source/store type for skills."""

    CLAUDE_CODE = AgentType.CLAUDE_CODE
    CODEX = AgentType.CODEX
    GEMINI = AgentType.GEMINI
    DATACLAW = AgentType.DATACLAW
    PARSED = AgentType.PARSED
    CENTRAL = "central"
    URL = "url"


class SkillSource(BaseModel):
    """One source from which a skill is available or was loaded."""

    source_type: SkillSourceType = Field(description="Source/store type for this skill.")
    source_path: str = Field(description="Local path or URL for the source.")
