"""Creation-mode LLM output and service result models."""

from pydantic import BaseModel, Field

from vibelens.models.inference import BackendType
from vibelens.models.skill.patterns import WorkflowPattern


class SkillCreation(BaseModel):
    """A new skill generated from detected workflow patterns."""

    name: str = Field(description="Proposed skill name in kebab-case.")
    description: str = Field(
        description="One-line trigger description for the YAML frontmatter. Under 20 words."
    )
    skill_md_content: str = Field(description="Full SKILL.md content including YAML frontmatter.")
    rationale: str = Field(
        description="Why this skill would improve the workflow. 1-2 sentences, under 40 words."
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence that this skill addresses a real recurring need. 0.0-1.0.",
    )


class SkillProposal(BaseModel):
    """A lightweight skill proposal from the proposal pipeline."""

    name: str = Field(description="Proposed skill name in kebab-case.")
    description: str = Field(
        description="One-line trigger description for the YAML frontmatter. Under 20 words."
    )
    rationale: str = Field(
        description="Why this skill would improve the workflow. 1-2 sentences, under 40 words."
    )
    addressed_patterns: list[str] = Field(
        default_factory=list,
        description="Titles of workflow patterns this proposal addresses.",
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence that this skill addresses a real recurring need. 0.0-1.0.",
    )


class SkillProposalOutput(BaseModel):
    """LLM output from the proposal generation step.

    Contains lightweight proposals (name + description + rationale) without
    full SKILL.md content. Deep creation produces the full content per proposal.
    """

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
    proposals: list[SkillProposal] = Field(default_factory=list, description="Proposed skills.")


class SkillDeepCreationOutput(BaseModel):
    """LLM output from deep creation of a single skill.

    Generates production-ready SKILL.md content for one approved proposal.
    """

    name: str = Field(description="Skill name in kebab-case.")
    description: str = Field(description="Trigger description for the YAML frontmatter.")
    skill_md_content: str = Field(description="Full SKILL.md content including YAML frontmatter.")
    rationale: str = Field(description="Why this skill improves the user's workflow.")
    tools_used: list[str] = Field(
        default_factory=list,
        description="Tool names referenced in the skill (e.g. Read, Edit, Bash).",
    )


class SkillProposalResult(BaseModel):
    """Service result wrapping proposals with metadata."""

    proposal_id: str | None = Field(
        default=None, description="Persistence ID. Set when saved to disk."
    )
    session_ids: list[str] = Field(
        description="Session IDs that were successfully loaded and analyzed."
    )
    workflow_patterns: list[WorkflowPattern] = Field(
        default_factory=list, description="Detected workflow patterns."
    )
    proposals: list[SkillProposal] = Field(default_factory=list, description="Proposed skills.")
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
