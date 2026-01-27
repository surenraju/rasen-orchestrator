"""Tests for atomic file operations."""

from __future__ import annotations

from pathlib import Path

from rasen.stores._atomic import atomic_write, file_lock


def test_atomic_write(tmp_path: Path):
    """Test atomic text write."""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"

    atomic_write(test_file, content)

    assert test_file.exists()
    assert test_file.read_text() == content


def test_atomic_write_overwrites(tmp_path: Path):
    """Test atomic write overwrites existing file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Old content")

    atomic_write(test_file, "New content")

    assert test_file.read_text() == "New content"


def test_atomic_write_creates_parent_dirs(tmp_path: Path):
    """Test atomic write creates parent directories."""
    test_file = tmp_path / "subdir" / "deep" / "test.txt"

    atomic_write(test_file, "Content")

    assert test_file.exists()
    assert test_file.read_text() == "Content"


def test_atomic_write_with_json(tmp_path: Path):
    """Test atomic write with JSON content."""
    import json

    test_file = tmp_path / "test.json"
    data = {"key": "value", "number": 42, "list": [1, 2, 3]}
    content = json.dumps(data, indent=2)

    atomic_write(test_file, content)

    assert test_file.exists()
    loaded = json.loads(test_file.read_text())
    assert loaded == data


def test_file_lock_exclusive(tmp_path: Path):
    """Test exclusive file lock."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Initial content")

    with file_lock(test_file, shared=False):
        # File is locked for writing
        content = test_file.read_text()
        test_file.write_text(content + " Modified")

    assert test_file.read_text() == "Initial content Modified"


def test_file_lock_shared(tmp_path: Path):
    """Test shared file lock."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Content")

    with file_lock(test_file, shared=True):
        # File is locked for reading
        content = test_file.read_text()
        assert content == "Content"


def test_file_lock_creates_file_if_missing(tmp_path: Path):
    """Test file lock creates file if it doesn't exist."""
    test_file = tmp_path / "new.txt"

    with file_lock(test_file, shared=False):
        assert test_file.exists()


def test_atomic_write_preserves_encoding(tmp_path: Path):
    """Test atomic write preserves UTF-8 encoding."""
    test_file = tmp_path / "unicode.txt"
    content = "Hello 世界 🎉 Ümläuts"

    atomic_write(test_file, content)

    assert test_file.read_text() == content


def test_atomic_write_multiline(tmp_path: Path):
    """Test atomic write with multiline content."""
    test_file = tmp_path / "multiline.txt"
    content = """Line 1
Line 2
Line 3"""

    atomic_write(test_file, content)

    assert test_file.read_text() == content


def test_atomic_write_empty_content(tmp_path: Path):
    """Test atomic write with empty content."""
    test_file = tmp_path / "empty.txt"

    atomic_write(test_file, "")

    assert test_file.exists()
    assert test_file.read_text() == ""


def test_multiple_atomic_writes_sequential(tmp_path: Path):
    """Test multiple atomic writes work correctly."""
    test_file = tmp_path / "test.txt"

    for i in range(5):
        content = f"Iteration {i}"
        atomic_write(test_file, content)
        assert test_file.read_text() == content


def test_atomic_write_temp_file_cleanup_on_error(tmp_path: Path):
    """Test temp file is cleaned up on error."""
    # Create a file we can't write to by making directory read-only
    test_dir = tmp_path / "readonly"
    test_dir.mkdir()
    test_file = test_dir / "test.txt"

    # Make parent read-only (Unix only)
    import sys

    if sys.platform != "win32":
        import stat

        test_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            atomic_write(test_file, "content")
        except PermissionError:
            pass  # Expected

        # No .tmp files should be left behind
        temp_files = list(test_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Restore permissions for cleanup
        test_dir.chmod(stat.S_IRWXU)


def test_file_lock_releases_on_exception(tmp_path: Path):
    """Test file lock is released even when exception occurs."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Content")

    try:
        with file_lock(test_file, shared=False):
            raise ValueError("Test error")
    except ValueError:
        pass

    # Lock should be released - we should be able to lock again
    with file_lock(test_file, shared=False):
        assert test_file.read_text() == "Content"


def test_nested_directory_creation(tmp_path: Path):
    """Test atomic write creates deeply nested directories."""
    test_file = tmp_path / "a" / "b" / "c" / "d" / "test.txt"

    atomic_write(test_file, "Deep content")

    assert test_file.exists()
    assert test_file.read_text() == "Deep content"
