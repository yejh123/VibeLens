"""Service-layer result models with metadata for skill analysis."""

from pydantic import BaseModel, Field

from vibelens.models.inference import BackendType
from vibelens.models.skill.create import SkillCreation
from vibelens.models.skill.evolve import SkillEvolutionSuggestion
from vibelens.models.skill.patterns import SkillMode, WorkflowPattern
from vibelens.models.skill.retrieve import SkillRecommendation


class SkillAnalysisResult(BaseModel):
    """Complete skill analysis result with service metadata.

    Flattens mode-specific LLM output fields and adds session tracking,
    backend info, and cost metadata from the service layer.
    """

    analysis_id: str | None = Field(
        default=None, description="Persistence ID. Set when saved to disk."
    )
    mode: SkillMode = Field(description="Which analysis mode was used.")
    session_ids: list[str] = Field(
        description="Session IDs that were successfully loaded and analyzed."
    )
    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list, description="Detected workflow patterns from trajectory analysis."
    )
    recommendations: list[SkillRecommendation] = Field(
        default_factory=list, description="Recommended skills (retrieval mode)."
    )
    generated_skills: list[SkillCreation] = Field(
        default_factory=list, description="Generated skills (creation mode)."
    )
    evolution_suggestions: list[SkillEvolutionSuggestion] = Field(
        default_factory=list, description="Evolution suggestions (evolution mode)."
    )
    summary: str = Field(description="Overall analysis summary.")
    user_profile: str = Field(default="", description="Detected user workflow style.")
    sessions_skipped: list[str] = Field(
        default_factory=list, description="Session IDs that could not be loaded."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal issues encountered during analysis."
    )
    backend_id: BackendType = Field(description="Inference backend used.")
    model: str = Field(description="Model identifier.")
    cost_usd: float | None = Field(default=None, description="Inference cost in USD.")
    batch_count: int = Field(default=1, description="Number of LLM batches used.")
    created_at: str = Field(description="ISO timestamp of analysis completion.")
