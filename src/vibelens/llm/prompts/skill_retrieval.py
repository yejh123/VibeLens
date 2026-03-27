"""Prompt for skill retrieval analysis.

Detects workflow patterns from session transcripts and recommends
existing skills from a pre-built candidate list. Uses SkillLLMOutput
as the output model.
"""

from vibelens.models.prompts import AnalysisPrompt, load_template
from vibelens.models.skill.skills import SkillLLMOutput

SKILL_RETRIEVAL_PROMPT = AnalysisPrompt(
    task_id="skill_retrieval",
    system_template=load_template("skill_retrieval_system.j2"),
    user_template=load_template("skill_retrieval_user.j2"),
    output_model=SkillLLMOutput,
)
