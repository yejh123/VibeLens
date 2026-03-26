"""Prompt for multi-session friction analysis.

Uses user-centric friction detection with batched output.
Variables: session_count, batch_digest, output_schema.
"""

from vibelens.models.analysis.friction import FrictionLLMBatchOutput
from vibelens.models.analysis.prompts import AnalysisPrompt, load_template

FRICTION_ANALYSIS_PROMPT = AnalysisPrompt(
    task_id="friction_analysis",
    system_template=load_template("friction_analysis_system.j2"),
    user_template=load_template("friction_analysis_user.j2"),
    output_model=FrictionLLMBatchOutput,
)
