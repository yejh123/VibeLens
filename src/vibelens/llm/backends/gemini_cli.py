"""Google Gemini CLI backend.

Invokes ``gemini --print`` as a subprocess. Prompt is piped via stdin.
Does not support native JSON output — uses prompt-level schema augmentation.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class GeminiCliBackend(CliBackend):
    """Run inference via the Gemini CLI."""

    @property
    def cli_executable(self) -> str:
        return "gemini"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.GEMINI_CLI

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build gemini CLI command.

        Args:
            request: Inference request for model settings.

        Returns:
            Command as a list of strings.
        """
        cmd = [self._cli_path or self.cli_executable, "--print"]
        if self._model:
            cmd.extend(["--model", self._model])
        return cmd
