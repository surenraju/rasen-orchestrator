"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

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
    max_loops: int = 3


class QAConfig(BaseModel):
    """QA loop settings (Coder ↔ QA)."""

    enabled: bool = True
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


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from YAML file with environment overrides.

    Priority (highest to lowest):
    1. Environment variables (RASEN_AGENT_MODEL, etc.)
    2. Config file (rasen.yml)
    3. Defaults

    Args:
        config_path: Path to config file. If None, searches for rasen.yml.

    Returns:
        Validated Config object.

    Raises:
        ConfigurationError: If config file is invalid.
    """
    # Find config file
    if config_path is None:
        config_path = Path("rasen.yml")

    # Load from file if exists
    if config_path.exists():
        try:
            with config_path.open() as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {config_path}: {e}") from e
    else:
        data = {}

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
