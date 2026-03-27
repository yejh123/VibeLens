"""Step signal builder — trajectory to StepSignal conversion.

Flattens trajectories into StepSignal objects for LLM friction analysis.
Filters out noise steps that carry no actionable friction signal:
sub-agent trajectories, copied-context steps, and empty system steps.
"""

from vibelens.models.analysis.friction import StepSignal
from vibelens.models.enums import StepSource
from vibelens.models.trajectories import Trajectory
from vibelens.utils.text import extract_text


def build_step_signals(trajectories: list[Trajectory]) -> list[StepSignal]:
    """Convert trajectories into a flat StepSignal list for LLM consumption.

    Filters out noise steps before building signals:
    - Sub-agent trajectories (parent_trajectory_ref is set)
    - Copied-context steps (is_copied_context is True)
    - Empty system steps (system source with no tools and blank message)

    Args:
        trajectories: Loaded ATIF trajectory objects.

    Returns:
        Ordered list of StepSignal (trajectory order, then step order).
    """
    signals: list[StepSignal] = []
    for trajectory in trajectories:
        if trajectory.parent_trajectory_ref is not None:
            continue

        for index, step in enumerate(trajectory.steps):
            if step.is_copied_context:
                continue
            if _is_empty_system_step(step):
                continue

            signals.append(
                StepSignal(
                    session_id=trajectory.session_id,
                    project_path=trajectory.project_path,
                    step_index=index,
                    step=step,
                )
            )
    return signals


def _is_empty_system_step(step) -> bool:
    """Check if a step is a system step with no tools and blank message."""
    if step.source != StepSource.SYSTEM:
        return False
    if step.tool_calls:
        return False
    message = extract_text(step.message)
    return not message.strip()
