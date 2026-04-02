"""Amp CLI backend (experimental).

Invokes ``amp`` as a subprocess. Prompt is piped via stdin.
Does not support native JSON output — uses prompt-level schema augmentation.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class AmpCliBackend(CliBackend):
    """Run inference via the Amp CLI (experimental)."""

    @property
    def cli_executable(self) -> str:
        return "amp"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.AMP_CLI

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build amp CLI command.

        Args:
            request: Inference request (unused beyond base class).

        Returns:
            Command as a list of strings.
        """
        return [self._cli_path or self.cli_executable]
