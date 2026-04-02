"""Cursor CLI backend (experimental).

Invokes ``cursor --cli`` as a subprocess. Prompt is piped via stdin.
Does not support native JSON output — uses prompt-level schema augmentation.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class CursorCliBackend(CliBackend):
    """Run inference via the Cursor CLI (experimental)."""

    @property
    def cli_executable(self) -> str:
        return "cursor"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.CURSOR_CLI

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build cursor CLI command.

        Args:
            request: Inference request (unused beyond base class).

        Returns:
            Command as a list of strings.
        """
        return [self._cli_path or self.cli_executable, "--cli"]
