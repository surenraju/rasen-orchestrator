"""Integration test: Build binary and generate Fibonacci program.

This test builds the RASEN binary and uses it to generate a Fibonacci program.
It tests the full workflow: build → init → run → verify.

NOTE: This requires Claude Code CLI configured with valid API key.
Set RASEN_INTEGRATION_TEST=1 to enable (otherwise skipped).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def binary_path(project_root: Path) -> Path:
    """Build binary and return path to it.

    This fixture runs once per test module and builds the binary.
    """
    dist_dir = project_root / "dist"
    binary = dist_dir / "rasen"

    # Build binary if it doesn't exist or is outdated
    build_script = project_root / "build.py"

    # Check if binary needs rebuilding
    needs_rebuild = True
    if binary.exists():
        # Check if source files are newer than binary
        binary_mtime = binary.stat().st_mtime
        src_dir = project_root / "src" / "rasen"

        newest_source = max((f.stat().st_mtime for f in src_dir.rglob("*.py")), default=0)

        if newest_source <= binary_mtime:
            needs_rebuild = False

    if needs_rebuild:
        print("\n🔨 Building binary...")
        result = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            pytest.fail(f"Binary build failed:\n{result.stderr}")

        print(result.stdout)
    else:
        print(f"\n✓ Using existing binary: {binary}")

    assert binary.exists(), "Binary was not created"
    return binary


@pytest.fixture
def test_project(tmp_path: Path, binary_path: Path) -> Path:
    """Create a test project directory with binary.

    Returns:
        Path to test project directory with rasen binary copied in.
    """
    # Create test project structure
    project_dir = tmp_path / "fibonacci-test"
    project_dir.mkdir()

    # Copy binary to test project
    test_binary = project_dir / "rasen"
    shutil.copy2(binary_path, test_binary)
    test_binary.chmod(0o755)

    # Create minimal rasen.yml config
    config = project_dir / "rasen.yml"
    config.write_text("""
project:
  name: "fibonacci-test"
  root: "."

orchestrator:
  max_iterations: 10
  session_delay_seconds: 3

agent:
  model: "claude-sonnet-4-20250514"
  max_thinking_tokens: 4096

review:
  enabled: false  # Disable for speed in tests

qa:
  enabled: false  # Disable for speed in tests

backpressure:
  require_tests: false  # Allow without tests for simple example
  require_lint: false

worktree:
  enabled: false  # Don't use worktrees in test
""")

    # Initialize git repo (required by orchestrator)
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = project_dir / "README.md"
    readme.write_text("# Fibonacci Test Project\n")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    return project_dir


def test_binary_exists(binary_path: Path) -> None:
    """Test that binary was built successfully."""
    assert binary_path.exists(), "Binary does not exist"
    assert binary_path.stat().st_size > 1_000_000, "Binary seems too small"


def test_binary_version(binary_path: Path) -> None:
    """Test that binary reports correct version."""
    result = subprocess.run(
        [str(binary_path), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, "Binary --version failed"
    assert "rasen" in result.stdout.lower(), "Version output doesn't mention rasen"


def test_binary_help(binary_path: Path) -> None:
    """Test that binary shows help."""
    result = subprocess.run(
        [str(binary_path), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, "Binary --help failed"
    assert "RASEN" in result.stdout, "Help doesn't mention RASEN"
    assert "init" in result.stdout, "Help doesn't mention init command"
    assert "run" in result.stdout, "Help doesn't mention run command"


def test_init_command(test_project: Path) -> None:
    """Test that init command creates expected files."""
    binary = test_project / "rasen"

    # Run init command
    result = subprocess.run(
        [str(binary), "init", "--task", "create fibonacci program in python"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Init command failed:\n{result.stderr}"

    # Verify output
    assert "Initializing task" in result.stdout
    assert "fibonacci" in result.stdout.lower()
    assert "✅ Task initialized" in result.stdout

    # Verify files created
    rasen_dir = test_project / ".rasen"
    assert rasen_dir.exists(), ".rasen directory not created"
    assert rasen_dir.is_dir(), ".rasen is not a directory"

    # Verify task.txt
    task_file = rasen_dir / "task.txt"
    assert task_file.exists(), "task.txt not created"
    task_content = task_file.read_text()
    assert "fibonacci" in task_content.lower(), "Task description not saved correctly"
    assert "python" in task_content.lower(), "Python not mentioned in task"

    # Verify status.json
    status_file = rasen_dir / "status.json"
    assert status_file.exists(), "status.json not created"
    status = json.loads(status_file.read_text())
    assert status["status"] == "initialized", "Status not set to initialized"
    assert status["iteration"] == 0, "Iteration not set to 0"


def test_status_before_run(test_project: Path) -> None:
    """Test status command after init but before run."""
    binary = test_project / "rasen"

    # Init first
    subprocess.run(
        [str(binary), "init", "--task", "create fibonacci program"],
        cwd=test_project,
        check=True,
        capture_output=True,
    )

    # Check status
    result = subprocess.run(
        [str(binary), "status"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Status command failed:\n{result.stderr}"
    assert "Status: INITIALIZED" in result.stdout or "Status: Not running" in result.stdout


@pytest.mark.skipif(
    os.environ.get("RASEN_INTEGRATION_TEST") != "1",
    reason=(
        "Full integration test requires Claude Code CLI and API key. "
        "Set RASEN_INTEGRATION_TEST=1 to enable."
    ),
)
def test_run_fibonacci_full(test_project: Path) -> None:
    """Full integration test: Generate Fibonacci program.

    This test actually runs the orchestrator and calls Claude Code CLI.
    It requires:
    - Claude Code CLI installed (npm install -g @anthropic-ai/claude-code)
    - API key configured (claude setup-token)
    - RASEN_INTEGRATION_TEST=1 environment variable

    This test is expensive and slow (~5-10 minutes).
    Only run manually or in dedicated integration test CI job.
    """
    binary = test_project / "rasen"

    # Init task
    result = subprocess.run(
        [str(binary), "init", "--task", "create fibonacci program in python"],
        cwd=test_project,
        check=True,
        capture_output=True,
        text=True,
    )
    print(result.stdout)

    # Run orchestrator (this will take several minutes)
    print("\n🚀 Running orchestrator (this may take 5-10 minutes)...")
    result = subprocess.run(
        [str(binary), "run"],
        cwd=test_project,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout
        check=False,
    )

    print("\n=== ORCHESTRATOR OUTPUT ===")
    print(result.stdout)
    if result.stderr:
        print("\n=== STDERR ===")
        print(result.stderr)
    print("=== END OUTPUT ===\n")

    # Check exit code
    assert result.returncode == 0, f"Orchestrator run failed with code {result.returncode}"

    # Verify plan was created
    plan_file = test_project / ".rasen" / "implementation_plan.json"
    assert plan_file.exists(), "Implementation plan not created"

    plan = json.loads(plan_file.read_text())
    assert "task_name" in plan
    assert "fibonacci" in plan["task_name"].lower()
    assert "subtasks" in plan
    assert len(plan["subtasks"]) > 0, "No subtasks in plan"

    # Verify some Python file was created
    python_files = list(test_project.glob("*.py"))
    assert len(python_files) > 0, "No Python files created"

    # Check for fibonacci-related content
    found_fibonacci = False
    for py_file in python_files:
        content = py_file.read_text()
        if "fibonacci" in content.lower() or "fib" in content.lower():
            found_fibonacci = True
            print(f"\n✓ Found Fibonacci implementation in {py_file.name}")
            print("  First 20 lines:\n")
            print("\n".join(content.split("\n")[:20]))
            break

    assert found_fibonacci, "No Fibonacci implementation found in generated files"

    # Verify git commits were made
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=False,
    )
    commits = result.stdout.strip().split("\n")
    # Should have initial commit + at least one implementation commit
    assert len(commits) >= 2, f"Expected at least 2 commits, got {len(commits)}"

    # Check status
    result = subprocess.run(
        [str(binary), "status"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"\nFinal status:\n{result.stdout}")


def test_run_without_init_fails(test_project: Path) -> None:
    """Test that run command fails gracefully without init."""
    binary = test_project / "rasen"

    # Try to run without init
    result = subprocess.run(
        [str(binary), "run"],
        cwd=test_project,
        capture_output=True,
        text=True,
        check=False,
    )

    # Should fail with clear error
    assert result.returncode != 0, "Run should fail without init"
    assert "Error" in result.stderr or "No task found" in result.stderr, (
        "Should show clear error message"
    )


def test_init_twice_overwrites(test_project: Path) -> None:
    """Test that running init twice updates the task."""
    binary = test_project / "rasen"

    # First init
    subprocess.run(
        [str(binary), "init", "--task", "first task"],
        cwd=test_project,
        check=True,
        capture_output=True,
    )

    task_file = test_project / ".rasen" / "task.txt"
    first_task = task_file.read_text()
    assert "first task" in first_task

    # Second init
    subprocess.run(
        [str(binary), "init", "--task", "second task"],
        cwd=test_project,
        check=True,
        capture_output=True,
    )

    second_task = task_file.read_text()
    assert "second task" in second_task
    assert "first task" not in second_task, "Old task should be overwritten"


if __name__ == "__main__":
    # Allow running this test file directly for development
    pytest.main([__file__, "-v", "-s"])
