"""Integration tests for config and prompt initialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def test_init_creates_config_file(tmp_path: Path) -> None:
    """Test that rasen init creates rasen-config.yml."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--task", "Test task"])

        assert result.exit_code == 0, f"Failed: {result.output}"

        config_file = Path(".rasen/rasen-config.yml")
        assert config_file.exists(), "rasen-config.yml was not created"

        # Verify config structure
        config_data = yaml.safe_load(config_file.read_text())
        assert "agents" in config_data
        assert "initializer" in config_data["agents"]
        assert "coder" in config_data["agents"]
        assert "reviewer" in config_data["agents"]
        assert "qa" in config_data["agents"]
        assert "session" in config_data
        assert "review" in config_data
        assert "qa" in config_data
        assert "stall" in config_data


def test_init_copies_agent_prompts(tmp_path: Path) -> None:
    """Test that rasen init copies all agent prompts to .rasen/prompts/."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--task", "Test task"])

        assert result.exit_code == 0, f"Failed: {result.output}"

        prompts_dir = Path(".rasen/prompts")
        assert prompts_dir.exists(), "prompts directory was not created"

        # Verify all 4 agent prompts were copied
        required_prompts = ["initializer.md", "coder.md", "reviewer.md", "qa.md"]
        for prompt_name in required_prompts:
            prompt_file = prompts_dir / prompt_name
            assert prompt_file.exists(), f"{prompt_name} was not created"
            assert prompt_file.read_text().strip(), f"{prompt_name} is empty"


def test_init_doesnt_overwrite_custom_prompts(tmp_path: Path) -> None:
    """Test that rasen init doesn't overwrite existing custom prompts."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # First init
        result = runner.invoke(main, ["init", "--task", "Test task"])
        assert result.exit_code == 0

        # Modify a prompt
        custom_prompt = Path(".rasen/prompts/coder.md")
        custom_content = "# CUSTOM CODER PROMPT\nThis is my customization!"
        custom_prompt.write_text(custom_content)

        # Second init (should not overwrite)
        result = runner.invoke(main, ["init", "--task", "Test task 2"])
        assert result.exit_code == 0

        # Verify customization is preserved
        assert custom_prompt.read_text() == custom_content


def test_create_agent_prompt_uses_local_prompts(tmp_path: Path) -> None:
    """Test that create_agent_prompt uses local customized prompts."""
    from rasen.prompts import create_agent_prompt

    # Create .rasen/prompts/ with custom prompt
    prompts_dir = tmp_path / ".rasen" / "prompts"
    prompts_dir.mkdir(parents=True)

    custom_coder = prompts_dir / "coder.md"
    custom_coder.write_text("CUSTOM CODER: Task {subtask_description}")

    # Create prompt with project_dir
    result = create_agent_prompt(
        "coder",
        project_dir=tmp_path,
        subtask_id="test-1",
        subtask_description="Build feature",
        attempt_number="1",
        memory_context="",
        failed_approaches_section="",
    )

    # Should use custom prompt
    assert "CUSTOM CODER: Task Build feature" in result


def test_create_agent_prompt_falls_back_to_bundled(tmp_path: Path) -> None:
    """Test that create_agent_prompt falls back to bundled prompts if no local."""
    from rasen.prompts import create_agent_prompt

    # Don't create local prompts

    # Create prompt without local prompts
    result = create_agent_prompt(
        "coder",
        project_dir=tmp_path,
        subtask_id="test-1",
        subtask_description="Build feature",
        attempt_number="1",
        memory_context="",
        failed_approaches_section="",
    )

    # Should use bundled prompt (contains standard text)
    assert "Coding Session" in result or "subtask" in result.lower()


def test_init_output_shows_customization_instructions(tmp_path: Path) -> None:
    """Test that rasen init output guides users to customize."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--task", "Test task"])

        assert result.exit_code == 0

        # Verify helpful output
        assert "Config:" in result.output
        assert "Prompts:" in result.output
        assert "Customize agent prompts" in result.output
        assert "rasen-config.yml" in result.output


def test_config_file_has_correct_defaults(tmp_path: Path) -> None:
    """Test that rasen-config.yml has sensible defaults."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--task", "Test task"])
        assert result.exit_code == 0

        config_file = Path(".rasen/rasen-config.yml")
        config = yaml.safe_load(config_file.read_text())

        # Verify defaults
        assert config["session"]["timeout_seconds"] == 1800  # 30 minutes
        assert config["session"]["max_iterations"] == 100
        assert config["review"]["enabled"] is True
        assert config["review"]["max_iterations"] == 3
        assert config["qa"]["enabled"] is True
        assert config["qa"]["max_iterations"] == 50
        assert config["stall"]["max_no_commit_sessions"] == 3
        assert config["stall"]["max_consecutive_failures"] == 5

        # Verify read-only agents
        assert config["agents"]["reviewer"]["read_only"] is True
        assert config["agents"]["qa"]["read_only"] is True
        assert config["agents"]["coder"]["read_only"] is False
        assert config["agents"]["initializer"]["read_only"] is False


def test_prompt_paths_in_config(tmp_path: Path) -> None:
    """Test that config references correct prompt paths."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "--task", "Test task"])
        assert result.exit_code == 0

        config_file = Path(".rasen/rasen-config.yml")
        config = yaml.safe_load(config_file.read_text())

        # Verify prompt paths
        assert config["agents"]["initializer"]["prompt"] == "prompts/initializer.md"
        assert config["agents"]["coder"]["prompt"] == "prompts/coder.md"
        assert config["agents"]["reviewer"]["prompt"] == "prompts/reviewer.md"
        assert config["agents"]["qa"]["prompt"] == "prompts/qa.md"


def test_multiple_inits_preserve_state(tmp_path: Path) -> None:
    """Test that multiple rasen init calls preserve existing state."""
    from rasen.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # First init
        result = runner.invoke(main, ["init", "--task", "Task 1"])
        assert result.exit_code == 0

        # Create some state
        status_file = Path(".rasen/status.json")
        original_status = json.loads(status_file.read_text())

        # Modify config
        config_file = Path(".rasen/rasen-config.yml")
        config = yaml.safe_load(config_file.read_text())
        config["session"]["timeout_seconds"] = 3600  # Change to 1 hour
        config_file.write_text(yaml.dump(config))

        # Second init with different task
        result = runner.invoke(main, ["init", "--task", "Task 2"])
        assert result.exit_code == 0

        # Verify config was NOT overwritten (because it exists)
        config_after = yaml.safe_load(config_file.read_text())
        assert config_after["session"]["timeout_seconds"] == 3600, (
            "Config was overwritten when it shouldn't be"
        )

        # Task file should be updated
        task_file = Path(".rasen/task.txt")
        assert task_file.read_text().strip() == "Task 2"
