"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from rasen.config import load_config


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
