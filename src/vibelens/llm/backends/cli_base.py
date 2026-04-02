"""Base class for CLI subprocess inference backends.

Shared infrastructure for all CLI-based backends: subprocess lifecycle
(spawn → stdin pipe → timeout → kill → parse), prompt augmentation
with JSON schema instructions, and temp schema file management.
"""

import asyncio
import contextlib
import json
import os
import shutil
import tempfile
import time
from abc import abstractmethod
from pathlib import Path

from vibelens.llm.backend import InferenceBackend, InferenceError, InferenceTimeoutError
from vibelens.models.inference import (
    BackendType,
    InferenceRequest,
    InferenceResult,
    TokenUsage,
)
from vibelens.utils.log import get_logger

logger = get_logger(__name__)

SIGTERM_GRACE_SECONDS = 5

SCHEMA_INSTRUCTION_TEMPLATE = (
    "\n\n---\nYou MUST respond with a single JSON object conforming to the following schema. "
    "Do NOT wrap the JSON in markdown code fences or add any text before/after it.\n\n"
    "```json\n{schema}\n```"
)


class CliBackend(InferenceBackend):
    """Abstract base for CLI subprocess backends.

    Subclasses provide CLI-specific command construction and metadata.
    This base handles the full subprocess lifecycle, optional JSON schema
    augmentation, and output parsing.
    """

    def __init__(self, model: str | None = None, timeout: int = 120):
        """Initialize CLI backend.

        Args:
            model: Optional model override passed to the CLI.
            timeout: Request timeout in seconds.
        """
        self._model = model
        self._timeout = timeout
        self._cli_path = shutil.which(self.cli_executable)
        self._schema_tempfile: Path | None = None

    @property
    @abstractmethod
    def cli_executable(self) -> str:
        """Binary name to invoke (e.g. 'claude', 'codex')."""

    @property
    @abstractmethod
    def backend_id(self) -> BackendType:
        """Unique BackendType enum value for this backend."""

    @property
    def supports_native_json(self) -> bool:
        """Whether the CLI natively supports JSON output mode."""
        return False

    @property
    def supports_schema_file(self) -> bool:
        """Whether the CLI accepts an --output-schema file argument."""
        return False

    @abstractmethod
    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Build the CLI command arguments.

        Args:
            request: Inference request (used for model/token settings).

        Returns:
            Command as a list of strings.
        """

    async def generate(self, request: InferenceRequest) -> InferenceResult:
        """Run inference via subprocess.

        Spawns the CLI process, pipes the prompt via stdin, enforces
        timeout with SIGTERM/SIGKILL, and parses stdout.

        Args:
            request: Inference request to process.

        Returns:
            InferenceResult from CLI output.

        Raises:
            InferenceError: If CLI is not available or exits with error.
            InferenceTimeoutError: If the subprocess exceeds the timeout.
        """
        if not self._cli_path:
            raise InferenceError(f"{self.cli_executable} CLI not found in PATH")

        # Write temp schema file if the CLI supports it
        if request.json_schema and self.supports_schema_file:
            self._write_schema_file(request.json_schema)

        try:
            cmd = self._build_command(request)
            prompt_text = self._build_prompt(request)
            prompt_bytes = prompt_text.encode("utf-8")
            env = self._build_env()

            start_ms = _now_ms()
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                timeout = request.timeout or self._timeout
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt_bytes), timeout=timeout
                )
            except TimeoutError as exc:
                await _kill_process(proc)
                raise InferenceTimeoutError(
                    f"{self.cli_executable} timed out after {timeout}s"
                ) from exc
            except OSError as exc:
                raise InferenceError(f"Failed to start {self.cli_executable}: {exc}") from exc

            duration_ms = _now_ms() - start_ms

            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace").strip()
                raise InferenceError(
                    f"{self.cli_executable} exited with code {proc.returncode}: {stderr_text}"
                )

            output = stdout.decode("utf-8", errors="replace").strip()
            return self._parse_output(output, duration_ms)
        finally:
            self._cleanup_schema_file()

    async def is_available(self) -> bool:
        """Check if the CLI executable exists in PATH."""
        return shutil.which(self.cli_executable) is not None

    def _build_env(self) -> dict[str, str]:
        """Build a clean environment for the subprocess.

        Strips variables that cause nesting-detection failures (e.g.
        CLAUDECODE prevents Claude Code from launching inside another
        Claude Code session).
        """
        env = os.environ.copy()
        for var in ("CLAUDECODE",):
            env.pop(var, None)
        return env

    def _build_prompt(self, request: InferenceRequest) -> str:
        """Combine system and user prompts, optionally augmenting with schema.

        Args:
            request: Inference request with system and user prompts.

        Returns:
            Combined prompt text.
        """
        prompt = f"{request.system}\n\n{request.user}"
        if request.json_schema and not self.supports_native_json:
            prompt = self._augment_prompt_with_schema(prompt, request.json_schema)
        return prompt

    def _augment_prompt_with_schema(self, prompt: str, json_schema: dict) -> str:
        """Append JSON schema instruction to the prompt.

        Used when the CLI lacks native JSON output support, so the LLM
        must be instructed via the prompt itself.

        Args:
            prompt: Original combined prompt text.
            json_schema: JSON schema dict for structured output.

        Returns:
            Prompt with appended schema instruction.
        """
        schema_str = json.dumps(json_schema, indent=2)
        return prompt + SCHEMA_INSTRUCTION_TEMPLATE.format(schema=schema_str)

    def _write_schema_file(self, json_schema: dict) -> None:
        """Write JSON schema to a temp file for CLIs that accept --output-schema.

        Args:
            json_schema: Schema dict to serialize.
        """
        fd, path = tempfile.mkstemp(suffix=".json", prefix="vibelens_schema_")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(json_schema, f, indent=2)
            self._schema_tempfile = Path(path)
        except OSError:
            logger.warning("Failed to write schema temp file at %s", path)
            self._schema_tempfile = None

    def _cleanup_schema_file(self) -> None:
        """Remove the temp schema file if it exists."""
        if self._schema_tempfile and self._schema_tempfile.exists():
            with contextlib.suppress(OSError):
                self._schema_tempfile.unlink()
            self._schema_tempfile = None

    def _parse_output(self, output: str, duration_ms: int) -> InferenceResult:
        """Parse CLI output into InferenceResult.

        Handles two JSON envelope formats:
        - Claude Code: ``{"type":"result","result":"...",
          "usage":{...},"modelUsage":{...},"total_cost_usd":...}``
        - Codex: ``{"result":"...","usage":{...},"model":"..."}``

        Falls back to treating the entire output as plain text if not JSON.

        Args:
            output: Raw stdout from the CLI process.
            duration_ms: Elapsed time in milliseconds.

        Returns:
            Parsed InferenceResult.
        """
        text = output
        usage = None
        cost_usd = None
        model = self._model or self.cli_executable

        try:
            data = json.loads(output)
            if isinstance(data, dict):
                text = data.get("result", data.get("content", data.get("text", output)))
                if "usage" in data:
                    usage_data = data["usage"]
                    usage = TokenUsage(
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                    )
                if "model" in data:
                    model = data["model"]
                # Claude Code envelope: extract model from modelUsage keys
                if "modelUsage" in data and not data.get("model"):
                    model_keys = list(data["modelUsage"].keys())
                    if model_keys:
                        model = model_keys[0].split("[")[0]
                if "total_cost_usd" in data:
                    cost_usd = data["total_cost_usd"]
        except (json.JSONDecodeError, TypeError):
            pass

        return InferenceResult(
            text=str(text), model=model, usage=usage, cost_usd=cost_usd, duration_ms=duration_ms
        )


async def _kill_process(proc: asyncio.subprocess.Process) -> None:
    """Terminate a subprocess with SIGTERM, then SIGKILL after grace period."""
    try:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=SIGTERM_GRACE_SECONDS)
        except TimeoutError:
            proc.kill()
            await proc.wait()
    except ProcessLookupError:
        pass


def _now_ms() -> int:
    """Return current time in milliseconds."""
    return int(time.monotonic() * 1000)
