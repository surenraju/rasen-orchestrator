"""Pytest fixtures for RASEN tests."""

import pytest


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory for testing."""
    return tmp_path / "test_project"
