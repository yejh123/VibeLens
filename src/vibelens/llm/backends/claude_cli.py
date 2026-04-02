"""Claude Code CLI backend.

Invokes ``claude -p - --output-format json`` as a subprocess.
The ``--output-format json`` flag wraps the response in a JSON envelope
with ``result``, ``usage``, and ``modelUsage`` fields.

Note: ``--json-schema`` is NOT used because it hangs in ``-p`` (print)
mode as of Claude Code v2.x. Schema enforcement relies on the
prompt-level ``{{ output_schema }}`` template variable instead.
"""

from vibelens.llm.backends.cli_base import CliBackend
from vibelens.models.inference import BackendType, InferenceRequest


class ClaudeCliBackend(CliBackend):
    """Run inference via the Claude Code CLI."""

    @property
    def cli_executable(self) -> str:
        return "claude"

    @property
    def backend_id(self) -> BackendType:
        return BackendType.CLAUDE_CLI

    @property
    def supports_native_json(self) -> bool:
        return True

    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build claude CLI command.

        Uses ``--output-format json`` for structured JSON envelope output.

        Args:
            request: Inference request for model settings.

        Returns:
            Command as a list of strings.
        """
        cmd = [self._cli_path or self.cli_executable, "-p", "-", "--output-format", "json"]
        if self._model:
            cmd.extend(["--model", self._model])
        return cmd
