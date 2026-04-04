"""Prompts for skill evolution analysis and cross-batch synthesis.

Detects workflow patterns and suggests granular edits to existing
installed skills. Synthesis merges batch-level results when multiple
batches are used.
"""

from vibelens.models.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillEvolutionOutput

SKILL_EVOLUTION_PROMPT = AnalysisPrompt(
    task_id="skill_evolution",
    system_template=load_template("skill/evolution_system.j2"),
    user_template=load_template("skill/evolution_user.j2"),
    output_model=SkillEvolutionOutput,
)

SKILL_EVOLUTION_SYNTHESIS_PROMPT = AnalysisPrompt(
    task_id="skill_evolution_synthesis",
    system_template=load_template("skill/evolution_synthesis_system.j2"),
    user_template=load_template("skill/evolution_synthesis_user.j2"),
    output_model=SkillEvolutionOutput,
)
