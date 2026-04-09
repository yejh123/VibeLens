"""Prompts for skill creation: proposals, synthesis, and generation.

Two-step pipeline:
1. Proposals: detect patterns and generate lightweight skill proposals
2. Generation: generate full SKILL.md for each approved proposal
"""

from vibelens.models.llm.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillCreation, SkillCreationProposalOutput

# Per-batch proposal: detects patterns and proposes new skills
SKILL_CREATION_PROPOSAL_PROMPT = AnalysisPrompt(
    task_id="skill_creation_proposal",
    system_template=load_template("skill/creation_proposal_system.j2"),
    user_template=load_template("skill/creation_proposal_user.j2"),
    output_model=SkillCreationProposalOutput,
)
# Post-batch synthesis: merges and deduplicates proposals across batches
SKILL_CREATION_PROPOSAL_SYNTHESIS_PROMPT = AnalysisPrompt(
    task_id="skill_creation_proposal_synthesis",
    system_template=load_template("skill/creation_proposal_synthesis_system.j2"),
    user_template=load_template("skill/creation_proposal_synthesis_user.j2"),
    output_model=SkillCreationProposalOutput,
)
# Generation step: produces full SKILL.md for each approved proposal
SKILL_CREATION_GENERATE_PROMPT = AnalysisPrompt(
    task_id="skill_creation_generate",
    system_template=load_template("skill/creation_system.j2"),
    user_template=load_template("skill/creation_user.j2"),
    output_model=SkillCreation,
    exclude_fields={"SkillCreation": frozenset({"addressed_patterns"})},
)
