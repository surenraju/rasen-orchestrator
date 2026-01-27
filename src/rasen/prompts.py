"""Prompt template rendering for agent sessions."""

from __future__ import annotations

from pathlib import Path

from rasen.claude_runner import get_agent_config
from rasen.exceptions import ConfigurationError


def render_prompt(
    template_path: Path,
    variables: dict[str, str],
) -> str:
    """Render prompt template with variable substitution.

    Args:
        template_path: Path to prompt markdown template
        variables: Dictionary of {variable_name: value} for substitution

    Returns:
        Rendered prompt string

    Raises:
        ConfigurationError: If template file doesn't exist
    """
    if not template_path.exists():
        raise ConfigurationError(f"Prompt template not found: {template_path}")

    template = template_path.read_text()

    # Simple {variable} substitution
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        template = template.replace(placeholder, str(value))

    return template


def create_agent_prompt(
    agent_type: str,
    prompts_dir: Path,
    **variables: str,
) -> str:
    """Create a prompt for a specific agent type.

    Args:
        agent_type: Type of agent (initializer, coder, reviewer, qa)
        prompts_dir: Directory containing prompt templates
        **variables: Variables to substitute in template

    Returns:
        Rendered prompt string

    Raises:
        ConfigurationError: If agent type is invalid or template not found
    """
    config = get_agent_config(agent_type)
    template_path = prompts_dir / config["prompt_template"]

    return render_prompt(template_path, variables)
