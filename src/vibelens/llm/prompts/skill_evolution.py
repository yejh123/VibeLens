"""Prompts for skill evolution: proposals, synthesis, and editing.

Two-step pipeline:
1. Proposals: detect patterns and propose improvements to existing skills
2. Editing: generate granular edits for each approved proposal
"""

from vibelens.models.llm.prompts import AnalysisPrompt, load_template
from vibelens.models.skill import SkillEvolution, SkillEvolutionProposalOutput

# Per-batch proposal: detects patterns and proposes improvements to existing skills
SKILL_EVOLUTION_PROPOSAL_PROMPT = AnalysisPrompt(
    task_id="skill_evolution_proposal",
    system_template=load_template("skill/evolution_proposal_system.j2"),
    user_template=load_template("skill/evolution_proposal_user.j2"),
    output_model=SkillEvolutionProposalOutput,
)
# Post-batch synthesis: merges and deduplicates evolution proposals across batches
SKILL_EVOLUTION_PROPOSAL_SYNTHESIS_PROMPT = AnalysisPrompt(
    task_id="skill_evolution_proposal_synthesis",
    system_template=load_template("skill/evolution_proposal_synthesis_system.j2"),
    user_template=load_template("skill/evolution_proposal_synthesis_user.j2"),
    output_model=SkillEvolutionProposalOutput,
)
# Edit step: generates granular old_string/new_string edits for each proposal
SKILL_EVOLUTION_EDIT_PROMPT = AnalysisPrompt(
    task_id="skill_evolution_edit",
    system_template=load_template("skill/evolution_system.j2"),
    user_template=load_template("skill/evolution_user.j2"),
    output_model=SkillEvolution,
    exclude_fields={"SkillEvolution": frozenset({"description", "addressed_patterns"})},
)
