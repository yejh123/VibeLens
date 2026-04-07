"""Tests for friction cost computation.

Tests _compute_span_cost and _compute_type_cost with various scenarios:
- Steps with metrics and timestamps
- Steps without metrics (None tokens)
- Steps without timestamps (None time)
- Missing trajectory (zero cost)
- Point ref (single step)
- Multiple refs (aggregate cost)
"""

from datetime import UTC, datetime

from vibelens.models.analysis.step_ref import StepRef
from vibelens.models.trajectories.step import Metrics, Step
from vibelens.models.trajectories.trajectory import Trajectory
from vibelens.services.friction.analysis import _compute_span_cost, _compute_type_cost


def _make_step(
    step_id: str,
    source: str = "agent",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    timestamp: datetime | None = None,
    has_metrics: bool = True,
) -> Step:
    """Build a Step with optional metrics and timestamp."""
    metrics = None
    if has_metrics:
        metrics = Metrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=0,
            cache_creation_tokens=0,
        )
    return Step(
        step_id=step_id,
        source=source,
        message="test",
        tool_calls=[],
        metrics=metrics,
        timestamp=timestamp,
    )


def _make_ref(session_id: str, start: str, end: str | None = None) -> StepRef:
    """Build a StepRef for testing."""
    return StepRef(session_id=session_id, start_step_id=start, end_step_id=end)


def _make_trajectory(session_id: str, steps: list[Step]) -> Trajectory:
    """Build a minimal Trajectory for testing."""
    return Trajectory(session_id=session_id, agent={"name": "claude_code"}, steps=steps)


def test_span_cost_with_metrics_and_timestamps():
    """Span cost computation with full metrics and timestamps."""
    ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    ts2 = datetime(2024, 1, 1, 12, 0, 30, tzinfo=UTC)
    ts3 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC)

    steps = [
        _make_step("s1", prompt_tokens=100, completion_tokens=50, timestamp=ts1),
        _make_step("s2", prompt_tokens=200, completion_tokens=100, timestamp=ts2),
        _make_step("s3", prompt_tokens=300, completion_tokens=150, timestamp=ts3),
    ]
    traj = _make_trajectory("session-1", steps)
    ref = _make_ref("session-1", "s1", "s3")

    cost = _compute_span_cost(ref, [traj])

    assert cost.affected_steps == 3
    assert cost.affected_tokens == 900  # (100+50) + (200+100) + (300+150)
    assert cost.affected_time_seconds == 60  # 1 minute
    print(
        f"Full cost: steps={cost.affected_steps}, "
        f"tokens={cost.affected_tokens}, "
        f"time={cost.affected_time_seconds}s"
    )


def test_span_cost_without_metrics():
    """Span cost computation when steps lack metrics -- tokens should be None."""
    steps = [
        _make_step("s1", has_metrics=False),
        _make_step("s2", has_metrics=False),
    ]
    traj = _make_trajectory("session-1", steps)
    ref = _make_ref("session-1", "s1", "s2")

    cost = _compute_span_cost(ref, [traj])

    assert cost.affected_steps == 2
    assert cost.affected_tokens is None
    assert cost.affected_time_seconds is None
    print(f"No-metrics cost: steps={cost.affected_steps}, tokens={cost.affected_tokens}")


def test_span_cost_without_timestamps():
    """Span cost computation when steps lack timestamps -- time should be None."""
    steps = [
        _make_step("s1", prompt_tokens=100, completion_tokens=50),
        _make_step("s2", prompt_tokens=200, completion_tokens=100),
    ]
    traj = _make_trajectory("session-1", steps)
    ref = _make_ref("session-1", "s1", "s2")

    cost = _compute_span_cost(ref, [traj])

    assert cost.affected_steps == 2
    assert cost.affected_tokens == 450
    assert cost.affected_time_seconds is None
    print(f"No-timestamp cost: tokens={cost.affected_tokens}, time={cost.affected_time_seconds}")


def test_span_cost_missing_trajectory():
    """Span cost computation when trajectory is not found -- zero cost."""
    ref = _make_ref("nonexistent-session", "s1", "s2")
    cost = _compute_span_cost(ref, [])

    assert cost.affected_steps == 0
    assert cost.affected_tokens is None
    assert cost.affected_time_seconds is None
    print("Missing trajectory: zero cost")


def test_span_cost_point_ref():
    """Span cost computation for a point reference (single step)."""
    ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    steps = [
        _make_step("s1", prompt_tokens=500, completion_tokens=250, timestamp=ts),
        _make_step("s2", prompt_tokens=100, completion_tokens=50),
    ]
    traj = _make_trajectory("session-1", steps)
    ref = _make_ref("session-1", "s1")

    cost = _compute_span_cost(ref, [traj])

    assert cost.affected_steps == 1
    assert cost.affected_tokens == 750
    assert cost.affected_time_seconds is None  # Single step = no time delta
    print(f"Point ref cost: steps={cost.affected_steps}, tokens={cost.affected_tokens}")


def test_span_cost_invalid_step_ids():
    """Span cost computation when start_step_id is invalid -- zero cost."""
    steps = [_make_step("s1"), _make_step("s2")]
    traj = _make_trajectory("session-1", steps)
    ref = _make_ref("session-1", "nonexistent")

    cost = _compute_span_cost(ref, [traj])

    assert cost.affected_steps == 0
    print("Invalid step_id: zero cost")


def test_type_cost_aggregates_multiple_refs():
    """Type cost aggregates steps, tokens, and time across multiple refs."""
    ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    ts2 = datetime(2024, 1, 1, 12, 0, 30, tzinfo=UTC)
    ts3 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC)
    ts4 = datetime(2024, 1, 1, 12, 1, 30, tzinfo=UTC)

    steps_a = [
        _make_step("a1", prompt_tokens=100, completion_tokens=50, timestamp=ts1),
        _make_step("a2", prompt_tokens=200, completion_tokens=100, timestamp=ts2),
    ]
    steps_b = [
        _make_step("b1", prompt_tokens=300, completion_tokens=150, timestamp=ts3),
        _make_step("b2", prompt_tokens=400, completion_tokens=200, timestamp=ts4),
    ]

    trajs = [
        _make_trajectory("sess-a", steps_a),
        _make_trajectory("sess-b", steps_b),
    ]

    refs = [
        _make_ref("sess-a", "a1", "a2"),
        _make_ref("sess-b", "b1", "b2"),
    ]

    cost = _compute_type_cost(refs, trajs)

    assert cost.affected_steps == 4  # 2 + 2
    assert cost.affected_tokens == 1500  # (100+50+200+100) + (300+150+400+200)
    assert cost.affected_time_seconds == 60  # 30s + 30s
    print(
        f"Aggregate cost: steps={cost.affected_steps}, "
        f"tokens={cost.affected_tokens}, "
        f"time={cost.affected_time_seconds}s"
    )


def test_type_cost_single_ref():
    """Type cost with a single ref behaves like span cost."""
    steps = [
        _make_step("s1", prompt_tokens=100, completion_tokens=50),
        _make_step("s2", prompt_tokens=200, completion_tokens=100),
    ]
    traj = _make_trajectory("session-1", steps)
    refs = [_make_ref("session-1", "s1", "s2")]

    cost = _compute_type_cost(refs, [traj])

    assert cost.affected_steps == 2
    assert cost.affected_tokens == 450
    print(f"Single-ref type cost: steps={cost.affected_steps}, tokens={cost.affected_tokens}")
