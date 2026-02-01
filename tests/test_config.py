"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from rasen.config import _transform_task_config, load_config


def test_load_default_config():
    """Test loading default config."""
    config = load_config()

    assert config.project.name is not None
    assert config.orchestrator.max_iterations > 0
    assert config.agent.model is not None


def test_config_from_yaml(tmp_path: Path):
    """Test loading config from YAML file."""
    config_file = tmp_path / "rasen.yml"
    config_data = {
        "project": {"name": "test-project", "root": str(tmp_path)},
        "orchestrator": {"max_iterations": 100},
    }
    config_file.write_text(yaml.dump(config_data))

    config = load_config(config_file)

    assert config.project.name == "test-project"
    assert config.orchestrator.max_iterations == 100


def test_config_defaults():
    """Test default configuration values."""
    config = load_config()

    assert config.orchestrator.session_delay_seconds == 3
    assert config.memory.enabled is True
    assert config.backpressure.require_tests is True
    assert config.review.enabled is True
    assert config.qa.enabled is True


def test_config_can_disable_review_and_qa():
    """Test config can disable review and QA."""
    config = load_config()
    config.review.enabled = False
    config.qa.enabled = False

    assert config.review.enabled is False
    assert config.qa.enabled is False


def test_transform_extracts_per_agent_models():
    """Test that _transform_task_config extracts models from agents section."""
    data = {
        "agents": {
            "initializer": {"model": "claude-opus-4-20250514", "prompt": "init.md"},
            "coder": {"model": "claude-opus-4-20250514", "prompt": "coder.md"},
            "reviewer": {"model": "claude-sonnet-4-20250514", "enabled": True},
            "qa": {"model": "claude-sonnet-4-20250514", "enabled": True},
        }
    }

    result = _transform_task_config(data)

    assert "models" in result
    assert result["models"]["initializer"] == "claude-opus-4-20250514"
    assert result["models"]["coder"] == "claude-opus-4-20250514"
    assert result["models"]["reviewer"] == "claude-sonnet-4-20250514"
    assert result["models"]["qa"] == "claude-sonnet-4-20250514"


def test_transform_extracts_review_and_qa_settings():
    """Test that _transform_task_config extracts review/qa settings."""
    data = {
        "agents": {
            "reviewer": {"enabled": True, "max_iterations": 5},
            "qa": {"enabled": False, "max_iterations": 10, "recurring_issue_threshold": 2},
        }
    }

    result = _transform_task_config(data)

    assert result["review"]["enabled"] is True
    assert result["review"]["max_loops"] == 5
    assert result["qa"]["enabled"] is False
    assert result["qa"]["max_iterations"] == 10
    assert result["qa"]["recurring_issue_threshold"] == 2


def test_config_get_model_returns_per_agent_model(tmp_path: Path):
    """Test that config.get_model returns correct per-agent model."""
    # Create .rasen directory and config
    rasen_dir = tmp_path / ".rasen"
    rasen_dir.mkdir()
    config_file = rasen_dir / "config.yaml"
    config_data = {
        "agents": {
            "initializer": {"model": "claude-opus-4-20250514"},
            "coder": {"model": "claude-opus-4-20250514"},
            "reviewer": {"model": "claude-sonnet-4-20250514"},
            "qa": {"model": "claude-sonnet-4-20250514"},
        }
    }
    config_file.write_text(yaml.dump(config_data))

    # Change to tmp_path so load_config finds .rasen/config.yaml
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        config = load_config()

        assert config.get_model("initializer") == "claude-opus-4-20250514"
        assert config.get_model("coder") == "claude-opus-4-20250514"
        assert config.get_model("reviewer") == "claude-sonnet-4-20250514"
        assert config.get_model("qa") == "claude-sonnet-4-20250514"
    finally:
        os.chdir(original_cwd)


def test_config_get_model_falls_back_to_default():
    """Test that get_model falls back to default when agent model not set."""
    config = load_config()

    # Default model should be returned for any agent without explicit config
    model = config.get_model("coder")
    assert model == config.models.default
