"""Shared fixtures and helpers for live integration tests.

These tests require example data and/or external backends (Claude CLI, LiteLLM).
They are excluded from CI via --ignore=tests/live.
"""

import json
from pathlib import Path

from vibelens.models.trajectories import Trajectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples" / "claude-codex-example" / "parsed"
LOGS_DIR = PROJECT_ROOT / "logs"


def load_trajectory_groups(
    examples_dir: Path = EXAMPLES_DIR,
) -> dict[str, list[Trajectory]]:
    """Load all parsed trajectories grouped by session_id.

    Args:
        examples_dir: Directory containing parsed JSON trajectory files.

    Returns:
        Mapping of session_id to list of trajectories.
    """
    json_files = sorted(examples_dir.glob("*.json"))
    session_files = [f for f in json_files if not f.name.endswith(".meta.json")]

    groups: dict[str, list[Trajectory]] = {}
    for filepath in session_files:
        data = json.loads(filepath.read_text())
        trajectories = []
        if isinstance(data, list):
            for item in data:
                trajectories.append(Trajectory.model_validate(item))
        else:
            trajectories.append(Trajectory.model_validate(data))
        for t in trajectories:
            groups.setdefault(t.session_id, []).append(t)
    return groups


def save_log(log_dir: Path, filename: str, content: str) -> None:
    """Save content to a log file, creating directories as needed.

    Args:
        log_dir: Directory for the log file.
        filename: Name of the log file.
        content: Text content to write.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / filename).write_text(content, encoding="utf-8")
