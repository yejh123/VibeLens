"""Evolution-mode LLM output models."""

from pydantic import BaseModel, Field

from vibelens.models.skill.patterns import WorkflowPattern


class SkillEdit(BaseModel):
    """A single edit to an existing skill definition.

    Uses old_string/new_string like the Edit tool:
    - Replace: old_string="original text", new_string="new text"
    - Delete: old_string="text to remove", new_string=""
    - Add/append: old_string="" (empty), new_string="text to add"
    """

    old_string: str = Field(description="Text to find in the skill. Empty string for append.")
    new_string: str = Field(description="Replacement text. Empty string for deletion.")
    replace_all: bool = Field(default=False, description="Replace all occurrences if True.")


class SkillSelectionOutput(BaseModel):
    """LLM output from step-1 skill selection for evolution."""

    relevant_skills: list[str] = Field(
        description="Names of installed skills relevant to the session patterns."
    )
    reasoning: str = Field(description="Brief reasoning for why these skills were selected.")


class SkillEvolutionSuggestion(BaseModel):
    """A suggested improvement to an existing installed skill."""

    skill_name: str = Field(description="Name of the existing skill to evolve.")
    edits: list[SkillEdit] = Field(description="Ordered list of granular edits to apply.")
    rationale: str = Field(
        description="Overall rationale for evolving this skill. 1-2 sentences, under 40 words."
    )


class SkillEvolutionOutput(BaseModel):
    """LLM output for evolution-mode skill analysis."""

    user_profile: str = Field(
        default="",
        description=(
            "2-3 sentence description of the user's working style,"
            " tools, and project focus. Under 50 words."
        ),
    )
    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list, description="Detected workflow patterns from trajectory analysis."
    )
    summary: str = Field(
        description=(
            "Concise analysis overview for readers of all expertise levels."
            " Under 100 words."
        )
    )
    evolution_suggestions: list[SkillEvolutionSuggestion] = Field(
        default_factory=list, description="Evolution suggestions for existing skills."
    )
