"""Analysis prompt template model for LLM-powered session analysis."""

import copy
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel, ConfigDict, Field

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts" / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    keep_trailing_newline=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def load_template(name: str) -> Template:
    """Load a Jinja2 template from the prompts/templates directory.

    Args:
        name: Template filename (e.g. 'highlights_system.j2').

    Returns:
        Compiled Jinja2 Template.
    """
    return _jinja_env.get_template(name)


class AnalysisPrompt(BaseModel):
    """Template for a specific LLM analysis task.

    Decouples prompt content from inference transport. Adding a new
    analysis type requires only a new AnalysisPrompt instance, a pair
    of .j2 template files, and a Pydantic output model.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    task_id: str = Field(description="Unique identifier for this analysis type.")
    system_template: Template = Field(description="Jinja2 template for the system prompt.")
    user_template: Template = Field(description="Jinja2 template for the user prompt.")
    output_model: type[BaseModel] = Field(
        description="Pydantic model class for parsing structured LLM output."
    )
    exclude_fields: frozenset[str] = Field(
        default_factory=frozenset,
        description="Field names to strip from the JSON schema sent to the LLM.",
    )

    def render_system(self, **kwargs: object) -> str:
        """Render the system prompt template with the given variables.

        Args:
            **kwargs: Template variables.

        Returns:
            Rendered system prompt string.
        """
        return self.system_template.render(**kwargs)

    def render_user(self, **kwargs: object) -> str:
        """Render the user prompt template with the given variables.

        Args:
            **kwargs: Template variables.

        Returns:
            Rendered user prompt string.
        """
        return self.user_template.render(**kwargs)

    def output_json_schema(self) -> dict:
        """Return JSON schema for output_model, stripping exclude_fields.

        Strips excluded fields from both top-level properties and any
        nested model definitions under $defs.

        Returns:
            JSON schema dict with excluded fields removed.
        """
        schema = copy.deepcopy(self.output_model.model_json_schema())
        if not self.exclude_fields:
            return schema
        _strip_fields(schema, self.exclude_fields)
        for def_schema in schema.get("$defs", {}).values():
            _strip_fields(def_schema, self.exclude_fields)
        return schema


def _strip_fields(schema: dict, fields: frozenset[str]) -> None:
    """Remove field names from a JSON schema's properties and required list.

    Args:
        schema: A JSON schema dict with properties/required keys.
        fields: Field names to remove.
    """
    props = schema.get("properties", {})
    for field_name in fields:
        props.pop(field_name, None)
    required = schema.get("required")
    if required is not None:
        schema["required"] = [r for r in required if r not in fields]
