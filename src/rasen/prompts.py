"""Prompt template rendering for agent sessions."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from rasen.claude_runner import get_agent_config
from rasen.exceptions import ConfigurationError


def get_template_path(template_name: str) -> Path:
    """Get path to a bundled prompt template.

    Args:
        template_name: Name of template file (e.g., "prompts/initializer.md")

    Returns:
        Path to template file

    Raises:
        ConfigurationError: If template doesn't exist
    """
    # Load from package resources
    # templates are in src/rasen/prompts/
    try:
        # Get the prompts package
        prompts_package = files("rasen").joinpath("prompts")

        # Extract just the filename (remove "prompts/" prefix if present)
        filename = template_name.split("/")[-1]

        # Get template file reference
        template_file = prompts_package.joinpath(filename)

        # For Python 3.9+, files() returns a Traversable
        # We need to convert to Path for reading
        if hasattr(template_file, "read_text"):
            # It's a Traversable, we'll handle it differently
            return template_file  # type: ignore[return-value]
        else:
            # Fallback to Path
            return Path(str(template_file))

    except (FileNotFoundError, KeyError) as e:
        raise ConfigurationError(
            f"Prompt template not found: {template_name}. "
            "Ensure prompts are bundled with the package."
        ) from e


def render_prompt(
    template_content: str,
    variables: dict[str, str],
) -> str:
    """Render prompt template with variable substitution.

    Args:
        template_content: Template string
        variables: Dictionary of {variable_name: value} for substitution

    Returns:
        Rendered prompt string
    """
    template = template_content

    # Simple {variable} substitution
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        template = template.replace(placeholder, str(value))

    return template


def create_agent_prompt(
    agent_type: str,
    **variables: str,
) -> str:
    """Create a prompt for a specific agent type.

    Args:
        agent_type: Type of agent (initializer, coder, reviewer, qa)
        **variables: Variables to substitute in template

    Returns:
        Rendered prompt string

    Raises:
        ConfigurationError: If agent type is invalid or template not found
    """
    config = get_agent_config(agent_type)
    template_name = config["prompt_template"]

    # Get template from package resources
    template_ref = get_template_path(template_name)

    # Read template content
    # Handle both Path and Traversable types
    if hasattr(template_ref, "read_text"):
        template_content = template_ref.read_text(encoding="utf-8")
    else:
        template_content = Path(template_ref).read_text(encoding="utf-8")

    return render_prompt(template_content, variables)
