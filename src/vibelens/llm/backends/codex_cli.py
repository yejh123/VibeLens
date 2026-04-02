"""OpenAI Codex CLI backend.

Invokes ``codex exec --json --sandbox read-only`` as a subprocess.
Supports native JSON output, schema file via ``--output-schema``,
and model override.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class CodexCliBackend(CliBackend):
    """Run inference via the OpenAI Codex CLI."""

    @property
    def cli_executable(self) -> str:
        return "codex"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.CODEX_CLI

    @property
    def supports_native_json(self) -> bool:
        return True

    @property
    def supports_schema_file(self) -> bool:
        return True

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build codex CLI command.

        Args:
            request: Inference request for model settings.

        Returns:
            Command as a list of strings.
        """
        cmd = [self._cli_path or self.cli_executable, "exec", "--json", "--sandbox", "read-only"]
        if self._model:
            cmd.extend(["--model", self._model])
        if self._schema_tempfile:
            cmd.extend(["--output-schema", str(self._schema_tempfile)])
        return cmd
