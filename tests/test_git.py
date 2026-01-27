"""Tests for git operations."""

from __future__ import annotations

import subprocess

from rasen.exceptions import GitError
from rasen.git import (
    count_new_commits,
    get_current_commit,
    get_git_diff,
    get_last_commit_message,
    has_uncommitted_changes,
    is_git_repo,
)


def test_is_git_repo_true(git_repo):
    """Test detecting git repository."""
    assert is_git_repo(git_repo) is True


def test_is_git_repo_false(tmp_path):
    """Test detecting non-git directory."""
    assert is_git_repo(tmp_path) is False


def test_get_current_commit(git_repo):
    """Test getting current commit hash."""
    commit = get_current_commit(git_repo)

    assert commit is not None
    assert len(commit) == 40  # SHA-1 hash length
    assert all(c in "0123456789abcdef" for c in commit)


def test_get_last_commit_message(git_repo):
    """Test getting last commit message."""
    message = get_last_commit_message(git_repo)

    assert message == "Initial commit"


def test_count_new_commits_none(git_repo):
    """Test counting commits when none added."""
    commit = get_current_commit(git_repo)

    count = count_new_commits(git_repo, commit)

    assert count == 0


def test_count_new_commits_one(git_repo):
    """Test counting one new commit."""
    before = get_current_commit(git_repo)

    # Make a commit
    test_file = git_repo / "newfile.txt"
    test_file.write_text("New content")
    subprocess.run(["git", "add", "newfile.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add newfile"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    count = count_new_commits(git_repo, before)

    assert count == 1


def test_count_new_commits_multiple(git_repo):
    """Test counting multiple new commits."""
    before = get_current_commit(git_repo)

    # Make three commits
    for i in range(3):
        test_file = git_repo / f"file{i}.txt"
        test_file.write_text(f"Content {i}")
        subprocess.run(
            ["git", "add", f"file{i}.txt"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add file {i}"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

    count = count_new_commits(git_repo, before)

    assert count == 3


def test_get_git_diff_no_changes(git_repo):
    """Test getting diff with no changes."""
    commit = get_current_commit(git_repo)

    diff = get_git_diff(git_repo, commit)

    assert diff == ""


def test_get_git_diff_with_changes(git_repo):
    """Test getting diff with changes."""
    before = get_current_commit(git_repo)

    # Make a change
    test_file = git_repo / "changed.txt"
    test_file.write_text("Changed content")
    subprocess.run(["git", "add", "changed.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Change file"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    diff = get_git_diff(git_repo, before)

    assert "changed.txt" in diff
    assert "Changed content" in diff


def test_has_uncommitted_changes_false(git_repo):
    """Test detecting no uncommitted changes."""
    assert has_uncommitted_changes(git_repo) is False


def test_has_uncommitted_changes_true(git_repo):
    """Test detecting uncommitted changes."""
    # Create an untracked file
    test_file = git_repo / "untracked.txt"
    test_file.write_text("Untracked")

    assert has_uncommitted_changes(git_repo) is True


def test_has_uncommitted_changes_staged(git_repo):
    """Test detecting staged but uncommitted changes."""
    test_file = git_repo / "staged.txt"
    test_file.write_text("Staged content")
    subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, check=True, capture_output=True)

    assert has_uncommitted_changes(git_repo) is True


def test_get_current_commit_no_git(tmp_path):
    """Test get_current_commit raises on non-git directory."""
    import pytest

    with pytest.raises(GitError):
        get_current_commit(tmp_path)


def test_git_diff_between_commits(git_repo):
    """Test getting diff between two commits."""
    # Create first commit
    file1 = git_repo / "file1.txt"
    file1.write_text("First")
    subprocess.run(["git", "add", "file1.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "First"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    commit1 = get_current_commit(git_repo)

    # Create second commit
    file2 = git_repo / "file2.txt"
    file2.write_text("Second")
    subprocess.run(["git", "add", "file2.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Second"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    diff = get_git_diff(git_repo, commit1)

    assert "file2.txt" in diff
    assert "Second" in diff
    assert "file1.txt" not in diff  # file1 was in commit1
