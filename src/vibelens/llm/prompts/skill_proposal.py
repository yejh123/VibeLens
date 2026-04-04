"""Prompts for skill proposal generation and cross-batch synthesis.

The proposal pipeline produces lightweight skill proposals (name + description +
rationale) without full SKILL.md content. Deep creation handles the full content.
"""

from vibelens.models.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillProposalOutput

SKILL_PROPOSAL_PROMPT = AnalysisPrompt(
    task_id="skill_proposal",
    system_template=load_template("skill/proposal_system.j2"),
    user_template=load_template("skill/proposal_user.j2"),
    output_model=SkillProposalOutput,
)

SKILL_PROPOSAL_SYNTHESIS_PROMPT = AnalysisPrompt(
    task_id="skill_proposal_synthesis",
    system_template=load_template("skill/proposal_synthesis_system.j2"),
    user_template=load_template("skill/proposal_synthesis_user.j2"),
    output_model=SkillProposalOutput,
)
