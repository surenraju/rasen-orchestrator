"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from rasen.exceptions import ConfigurationError


class ProjectConfig(BaseModel):
    """Project identification."""

    name: str = "unnamed-project"
    root: Path = Field(default_factory=Path.cwd)


class OrchestratorConfig(BaseModel):
    """Orchestration loop settings."""

    max_iterations: int = 50
    max_runtime_seconds: int = 14400  # 4 hours
    session_delay_seconds: int = 3
    session_timeout_seconds: int = 1800  # 30 min
    idle_timeout_seconds: int = 300  # 5 min


class AgentConfig(BaseModel):
    """Claude agent settings."""

    model: str = "claude-sonnet-4-20250514"
    max_thinking_tokens: int | None = 4096


class WorktreeConfig(BaseModel):
    """Git worktree settings."""

    enabled: bool = True
    base_path: str = ".worktrees"


class MemoryConfig(BaseModel):
    """Cross-session memory settings."""

    enabled: bool = True
    path: str = ".rasen/memories.md"
    max_tokens: int = 2000


class BackpressureConfig(BaseModel):
    """Quality gate settings."""

    require_tests: bool = True
    require_lint: bool = True


class BackgroundConfig(BaseModel):
    """Background daemon settings."""

    enabled: bool = False
    pid_file: str = ".rasen/rasen.pid"
    log_file: str = ".rasen/rasen.log"
    status_file: str = ".rasen/status.json"


class StallDetectionConfig(BaseModel):
    """Stall detection thresholds."""

    max_no_commit_sessions: int = 3
    max_consecutive_failures: int = 5
    circular_fix_threshold: float = 0.3


class ReviewConfig(BaseModel):
    """Review loop settings (Coder ↔ Reviewer)."""

    enabled: bool = True
    per_subtask: bool = False  # False = review after all subtasks (like Auto-Claude)
    max_loops: int = 3


class QAConfig(BaseModel):
    """QA loop settings (Coder ↔ QA)."""

    enabled: bool = True
    per_subtask: bool = False  # False = QA after all subtasks (like Auto-Claude)
    max_iterations: int = 50
    recurring_issue_threshold: int = 3


class Config(BaseModel):
    """Root configuration model."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    backpressure: BackpressureConfig = Field(default_factory=BackpressureConfig)
    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    stall_detection: StallDetectionConfig = Field(default_factory=StallDetectionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    qa: QAConfig = Field(default_factory=QAConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)

    Returns:
        Merged dictionary with override values taking precedence
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = _deep_merge(result[key], value)
        else:
            # Override value
            result[key] = value
    return result


def _transform_task_config(data: dict[str, Any]) -> dict[str, Any]:
    """Transform .rasen/config.yaml structure to match Config model.

    Transforms nested agents.reviewer/agents.qa settings into separate
    review and qa top-level sections for compatibility with existing Config model.

    Args:
        data: Raw YAML data from .rasen/config.yaml

    Returns:
        Transformed data matching Config model structure
    """
    if "agents" not in data:
        return data

    result = data.copy()
    agents = result.get("agents", {})

    # Extract reviewer settings -> review section
    if "reviewer" in agents and isinstance(agents["reviewer"], dict):
        reviewer_config = agents["reviewer"]
        if "enabled" in reviewer_config or "max_iterations" in reviewer_config:
            if "review" not in result:
                result["review"] = {}
            if "enabled" in reviewer_config:
                result["review"]["enabled"] = reviewer_config["enabled"]
            if "max_iterations" in reviewer_config:
                result["review"]["max_loops"] = reviewer_config["max_iterations"]

    # Extract qa settings -> qa section
    if "qa" in agents and isinstance(agents["qa"], dict):
        qa_config = agents["qa"]
        if any(k in qa_config for k in ["enabled", "max_iterations", "recurring_issue_threshold"]):
            if "qa" not in result:
                result["qa"] = {}
            if "enabled" in qa_config:
                result["qa"]["enabled"] = qa_config["enabled"]
            if "max_iterations" in qa_config:
                result["qa"]["max_iterations"] = qa_config["max_iterations"]
            if "recurring_issue_threshold" in qa_config:
                result["qa"]["recurring_issue_threshold"] = qa_config["recurring_issue_threshold"]

    return result


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from YAML file with environment overrides.

    Priority (highest to lowest):
    1. Environment variables (RASEN_AGENT_MODEL, etc.)
    2. .rasen/config.yaml (task-specific config, if exists)
    3. rasen.yml (project-level config)
    4. Defaults

    Args:
        config_path: Path to config file. If None, auto-detects config files.

    Returns:
        Validated Config object.

    Raises:
        ConfigurationError: If config file is invalid.
    """
    data: dict[str, Any] = {}

    # 1. Load project-level config (rasen.yml)
    project_config = Path("rasen.yml") if config_path is None else config_path

    if project_config.exists():
        try:
            with project_config.open() as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {project_config}: {e}") from e

    # 2. Load task-specific config (.rasen/config.yaml) and merge
    task_config = Path(".rasen/config.yaml")
    if task_config.exists():
        try:
            with task_config.open() as f:
                task_data = yaml.safe_load(f) or {}
                # Transform new structure (agents.reviewer.enabled -> review.enabled)
                task_data = _transform_task_config(task_data)
                # Deep merge: task config overrides project config
                data = _deep_merge(data, task_data)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {task_config}: {e}") from e

    # Apply environment overrides
    data = _apply_env_overrides(data)

    # Validate and return
    try:
        return Config.model_validate(data)
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {e}") from e


def _apply_env_overrides(data: dict) -> dict:  # type: ignore[type-arg]
    """Apply RASEN_* environment variables as overrides."""
    env_mappings = {
        "RASEN_AGENT_MODEL": ("agent", "model"),
        "RASEN_MAX_ITERATIONS": ("orchestrator", "max_iterations"),
        "RASEN_SESSION_TIMEOUT": ("orchestrator", "session_timeout_seconds"),
    }

    for env_var, (section, key) in env_mappings.items():
        if value := os.environ.get(env_var):
            if section not in data:
                data[section] = {}
            # Convert to int if needed
            if key.endswith(("_seconds", "_iterations", "_tokens")):
                value = int(value)  # type: ignore[assignment]
            data[section][key] = value

    return data
