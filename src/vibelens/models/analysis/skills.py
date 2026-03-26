"""Skill personalization models for LLM-powered trajectory analysis.

Defines the model hierarchy from LLM output (SkillLLMOutput) through
enriched result (SkillAnalysisResult). Covers three modes: retrieval,
creation, and evolution. See docs/spec-skill-personalization.md v0.3.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from vibelens.models.analysis.step_ref import StepRef


class SkillMode(StrEnum):
    """Skill personalization analysis mode."""

    RETRIEVAL = "retrieval"
    CREATION = "creation"
    EVOLUTION = "evolution"


class WorkflowPattern(BaseModel):
    """A recurring workflow pattern detected from trajectory analysis.

    Every recommendation, creation, and evolution suggestion MUST link
    to at least one pattern, and every pattern MUST identify a pain point.
    """

    pattern_id: str = Field(
        description="Unique identifier for this pattern. Format: p-{sequential_number}.",
    )
    description: str = Field(
        description="Human-readable description of what this pattern does.",
    )
    tool_sequence: list[str] = Field(
        description="Ordered list of tools commonly used together in this pattern.",
    )
    frequency: int = Field(
        description="How many times this pattern appeared across analyzed sessions.",
    )
    pain_point: str = Field(
        description="Why this pattern is suboptimal or could be automated.",
    )
    example_refs: list[StepRef] = Field(
        default_factory=list,
        description="Step references where this pattern was observed.",
    )


class SkillRecommendation(BaseModel):
    """A skill recommended from marketplace or local catalog."""

    skill_name: str = Field(description="Name of the recommended skill.")
    source: str = Field(
        description="Where the skill comes from (e.g. 'skillhub', 'local', 'anthropic').",
    )
    match_reason: str = Field(
        description="Why this skill matches the user's workflow patterns.",
    )
    matched_patterns: list[str] = Field(
        description="Pattern IDs this skill addresses.",
    )
    url: str = Field(default="", description="URL to install or view the skill.")
    confidence: float = Field(
        default=0.0,
        description="Match confidence from 0.0 to 1.0.",
    )


class SkillCreation(BaseModel):
    """A new skill generated from detected workflow patterns."""

    name: str = Field(description="Proposed skill name in kebab-case.")
    description: str = Field(description="Trigger description for the skill.")
    skill_md_content: str = Field(
        description="Full SKILL.md content including YAML frontmatter.",
    )
    source_patterns: list[str] = Field(
        description="Pattern IDs that inspired this skill.",
    )
    rationale: str = Field(
        description="Why this skill would improve the user's workflow.",
    )


class SkillEditKind(StrEnum):
    """Type of granular edit to an existing skill."""

    ADD_INSTRUCTION = "add_instruction"
    REMOVE_INSTRUCTION = "remove_instruction"
    REPLACE_INSTRUCTION = "replace_instruction"
    UPDATE_DESCRIPTION = "update_description"
    ADD_TOOL = "add_tool"
    REMOVE_TOOL = "remove_tool"


class SkillEdit(BaseModel):
    """A single granular edit to an existing skill definition."""

    kind: SkillEditKind = Field(description="Type of edit operation.")
    target: str = Field(description="The instruction, tool, or section being modified.")
    replacement: str | None = Field(
        default=None,
        description="New content for replace operations. None for removals.",
    )
    rationale: str = Field(description="Why this edit improves the skill.")


class SkillEvolutionSuggestion(BaseModel):
    """A suggested improvement to an existing installed skill."""

    skill_name: str = Field(description="Name of the existing skill to evolve.")
    edits: list[SkillEdit] = Field(
        description="Ordered list of granular edits to apply.",
    )
    rationale: str = Field(
        description="Overall rationale for evolving this skill.",
    )
    source_patterns: list[str] = Field(
        description="Pattern IDs that motivate these changes.",
    )


class SkillLLMOutput(BaseModel):
    """Raw structured output from LLM skill analysis.

    The LLM populates workflow_patterns (always) plus the mode-specific
    list (recommendations, generated_skills, or evolution_suggestions).
    """

    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list,
        description="Detected workflow patterns from trajectory analysis.",
    )
    recommendations: list[SkillRecommendation] = Field(
        default_factory=list,
        description="Recommended skills for retrieval mode.",
    )
    generated_skills: list[SkillCreation] = Field(
        default_factory=list,
        description="Generated skills for creation mode.",
    )
    evolution_suggestions: list[SkillEvolutionSuggestion] = Field(
        default_factory=list,
        description="Evolution suggestions for existing skills.",
    )
    summary: str = Field(
        description="Overall analysis summary across all sessions.",
    )
    user_profile: str = Field(
        default="",
        description="Brief description of the detected user workflow style.",
    )


class SkillAnalysisResult(BaseModel):
    """Complete skill analysis result with service metadata.

    Flattens SkillLLMOutput fields and adds session tracking,
    backend info, and cost metadata from the service layer.
    """

    analysis_id: str | None = Field(
        default=None,
        description="Persistence ID. Set when saved to disk.",
    )
    mode: SkillMode = Field(description="Which analysis mode was used.")
    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list,
        description="Detected workflow patterns from trajectory analysis.",
    )
    recommendations: list[SkillRecommendation] = Field(
        default_factory=list,
        description="Recommended skills (retrieval mode).",
    )
    generated_skills: list[SkillCreation] = Field(
        default_factory=list,
        description="Generated skills (creation mode).",
    )
    evolution_suggestions: list[SkillEvolutionSuggestion] = Field(
        default_factory=list,
        description="Evolution suggestions (evolution mode).",
    )
    summary: str = Field(
        description="Overall analysis summary.",
    )
    user_profile: str = Field(
        default="",
        description="Detected user workflow style.",
    )
    session_ids: list[str] = Field(
        description="Session IDs that were successfully loaded and analyzed.",
    )
    sessions_skipped: list[str] = Field(
        default_factory=list,
        description="Session IDs that could not be loaded.",
    )
    backend_id: str = Field(description="Inference backend used.")
    model: str = Field(description="Model identifier.")
    cost_usd: float | None = Field(
        default=None,
        description="Inference cost in USD.",
    )
    computed_at: str = Field(description="ISO timestamp of analysis completion.")
