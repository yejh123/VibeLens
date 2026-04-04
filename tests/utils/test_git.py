"""Tests for vibelens.utils.git — repo resolution, bundling, hashing."""

import re
import shutil
import tempfile
from pathlib import Path

import pytest

from vibelens.utils.git import compute_repo_hash, create_git_bundle, resolve_git_root

# VibeLens repo root (this test file lives inside it)
REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_NO_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="git not in PATH")


@SKIP_NO_GIT
def test_resolve_git_root_in_repo():
    """resolve_git_root returns the repo root when called inside a git repo."""
    result = resolve_git_root(REPO_ROOT / "src")
    print(f"resolve_git_root(src/) = {result}")
    assert result is not None
    assert result == REPO_ROOT
    assert (result / ".git").exists()


@SKIP_NO_GIT
def test_resolve_git_root_at_root():
    """resolve_git_root works when given the repo root directly."""
    result = resolve_git_root(REPO_ROOT)
    print(f"resolve_git_root(repo_root) = {result}")
    assert result == REPO_ROOT


@SKIP_NO_GIT
def test_resolve_git_root_nonexistent(tmp_path: Path):
    """resolve_git_root returns None for a non-existent path."""
    nonexistent = tmp_path / "does" / "not" / "exist"
    result = resolve_git_root(nonexistent)
    print(f"resolve_git_root(nonexistent) = {result}")
    assert result is None


@SKIP_NO_GIT
def test_resolve_git_root_not_git():
    """resolve_git_root returns None for a directory that is not a git repo."""
    with tempfile.TemporaryDirectory() as tmp:
        result = resolve_git_root(Path(tmp))
        print(f"resolve_git_root(tmp_dir) = {result}")
        assert result is None


def test_compute_repo_hash_deterministic():
    """Same path always produces the same hash."""
    hash_a = compute_repo_hash(REPO_ROOT)
    hash_b = compute_repo_hash(REPO_ROOT)
    print(f"hash_a={hash_a}, hash_b={hash_b}")
    assert hash_a == hash_b


def test_compute_repo_hash_length():
    """Hash is exactly 8 hex characters."""
    result = compute_repo_hash(REPO_ROOT)
    print(f"compute_repo_hash = {result}")
    assert len(result) == 8
    assert re.fullmatch(r"[0-9a-f]{8}", result)


def test_compute_repo_hash_differs_for_different_paths(tmp_path: Path):
    """Different paths produce different hashes."""
    hash_a = compute_repo_hash(tmp_path / "path_a")
    hash_b = compute_repo_hash(tmp_path / "path_b")
    print(f"hash_a={hash_a}, hash_b={hash_b}")
    assert hash_a != hash_b


@SKIP_NO_GIT
def test_create_git_bundle():
    """create_git_bundle creates a non-empty bundle file from the VibeLens repo."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "test.bundle"
        result = create_git_bundle(REPO_ROOT, output)
        print(f"create_git_bundle success={result}, path={output}")
        assert result is True
        assert output.exists()
        size = output.stat().st_size
        print(f"bundle size = {size} bytes")
        assert size > 0


@SKIP_NO_GIT
def test_create_git_bundle_invalid_repo():
    """create_git_bundle returns False for a non-git directory."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "test.bundle"
        result = create_git_bundle(Path(tmp), output)
        print(f"create_git_bundle(non-repo) = {result}")
        assert result is False
        assert not output.exists()
