"""Retrieval-mode LLM output models."""

from pydantic import BaseModel, Field

from vibelens.models.skill.patterns import WorkflowPattern


class SkillRecommendation(BaseModel):
    """A skill recommended from the catalog, matched to detected patterns."""

    skill_name: str = Field(description="Name of the recommended skill.")
    description: str = Field(
        default="",
        description="Short description of what this skill does. Set by the service layer.",
    )
    rationale: str = Field(
        description=(
            "One-sentence conclusion on why this fits, followed by "
            "1-2 bullet points starting with '- '. Max 50 words."
        )
    )
    addressed_patterns: list[str] = Field(
        default_factory=list,
        description="Titles of workflow patterns this recommendation addresses.",
    )
    confidence: float = Field(default=0.0, description="Match confidence from 0.0 to 1.0.")


class SkillRetrievalOutput(BaseModel):
    """LLM output for retrieval-mode skill analysis."""

    title: str = Field(
        default="",
        description="Clear, reader-friendly title capturing the main finding. Max 8 words.",
    )
    user_profile: str = Field(
        default="",
        description=(
            "One-sentence role summary followed by 1-2 bullet points "
            "starting with '- '. Max 50 words."
        ),
    )
    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list, description="Detected workflow patterns from trajectory analysis."
    )
    summary: str = Field(
        description=(
            "One-sentence conclusion followed by 2-4 bullet points starting with '- '. "
            "Accessible to all expertise levels. Max 100 words."
        )
    )
    recommendations: list[SkillRecommendation] = Field(
        default_factory=list, description="Recommended skills from the featured catalog."
    )
