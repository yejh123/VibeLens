"""Prompt for step-1 skill selection in the evolution pipeline.

Identifies which installed skills are relevant to observed session patterns
before loading full SKILL.md content for the evolution step.
"""

from vibelens.models.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillSelectionOutput

SKILL_EVOLUTION_SELECTION_PROMPT = AnalysisPrompt(
    task_id="skill_evolution_selection",
    system_template=load_template("skill/evolution_selection_system.j2"),
    user_template=load_template("skill/evolution_selection_user.j2"),
    output_model=SkillSelectionOutput,
)
