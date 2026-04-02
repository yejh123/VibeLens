"""Kimi CLI backend.

Invokes ``kimi --print`` as a subprocess. Prompt is piped via stdin.
Does not support native JSON output — uses prompt-level schema augmentation.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class KimiCliBackend(CliBackend):
    """Run inference via the Kimi CLI."""

    @property
    def cli_executable(self) -> str:
        return "kimi"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.KIMI_CLI

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build kimi CLI command.

        Args:
            request: Inference request (unused beyond base class).

        Returns:
            Command as a list of strings.
        """
        return [self._cli_path or self.cli_executable, "--print"]
