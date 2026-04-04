"""Prompt for deep skill creation from an approved proposal.

Generates production-ready SKILL.md content for a single proposal,
using session evidence and installed skills as context.
"""

from vibelens.models.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillDeepCreationOutput

SKILL_DEEP_CREATION_PROMPT = AnalysisPrompt(
    task_id="skill_deep_creation",
    system_template=load_template("skill/deep_creation_system.j2"),
    user_template=load_template("skill/deep_creation_user.j2"),
    output_model=SkillDeepCreationOutput,
)
