import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from riff.utils import DiffMode, parse_git_modified_lines, parse_ruff_output
from riff.violation import Violation


def test_parse_ruff_output_valid_one() -> None:
    code = "E0001"
    file = "file.py"
    start_row = 1
    start_column = 2
    end_row = 3
    end_column = 4
    error_message = "Error message"
    fix_suggestion = "Fix suggestion"

    mocked_ruff_output = json.dumps(
        [
            {
                "code": code,
                "filename": file,
                "location": {"row": start_row, "column": start_column},
                "end_location": {"row": end_row, "column": end_column},
                "message": error_message,
                "fix": {"message": fix_suggestion},
            }
        ]
    )
    violation = Violation(
        error_code=code,
        path=Path(file),
        line_start=start_row,
        message=error_message,
        linter_name="Ruff",
        is_autofixable=True,
        fix_suggestion=fix_suggestion,
        line_end=end_row,
        column_start=start_column,
        column_end=end_column,
    )
    assert parse_ruff_output(mocked_ruff_output) == (violation,)


@patch("riff.utils.Repo")
@patch("riff.utils.PatchSet")
def test_parse_git_modified_lines_unstaged(mock_patchset: MagicMock, mock_repo: MagicMock) -> None:
    """Test parsing unstaged changes."""
    # Mock repository
    mock_repo_instance = Mock()
    mock_repo_instance.git_dir = "/test/repo/.git"
    mock_repo_instance.git.diff.return_value = "mock diff output"
    mock_repo.return_value = mock_repo_instance
    
    # Mock PatchSet
    mock_patchset.return_value = []
    
    # Call function with UNSTAGED mode
    result = parse_git_modified_lines(mode=DiffMode.UNSTAGED)
    
    # Verify git.diff was called with no arguments for unstaged changes
    mock_repo_instance.git.diff.assert_called_once_with(
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )
    assert result == {}


@patch("riff.utils.Repo")
@patch("riff.utils.PatchSet")
def test_parse_git_modified_lines_staged(mock_patchset: MagicMock, mock_repo: MagicMock) -> None:
    """Test parsing staged changes."""
    # Mock repository
    mock_repo_instance = Mock()
    mock_repo_instance.git_dir = "/test/repo/.git"
    mock_repo_instance.git.diff.return_value = "mock diff output"
    mock_repo.return_value = mock_repo_instance
    
    # Mock PatchSet
    mock_patchset.return_value = []
    
    # Call function with STAGED mode
    result = parse_git_modified_lines(mode=DiffMode.STAGED)
    
    # Verify git.diff was called with --cached for staged changes
    mock_repo_instance.git.diff.assert_called_once_with(
        "--cached",
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )
    assert result == {}


@patch("riff.utils.Repo")
@patch("riff.utils.PatchSet")
def test_parse_git_modified_lines_ref(mock_patchset: MagicMock, mock_repo: MagicMock) -> None:
    """Test parsing changes against arbitrary ref."""
    # Mock repository
    mock_repo_instance = Mock()
    mock_repo_instance.git_dir = "/test/repo/.git"
    mock_repo_instance.git.diff.return_value = "mock diff output"
    mock_repo.return_value = mock_repo_instance
    
    # Mock PatchSet
    mock_patchset.return_value = []
    
    # Call function with REF mode
    result = parse_git_modified_lines(mode=DiffMode.REF, diff_ref="HEAD~1")
    
    # Verify git.diff was called with the ref
    mock_repo_instance.git.diff.assert_called_once_with(
        "HEAD~1",
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )
    assert result == {}


@patch("riff.utils.Repo")
@patch("riff.utils.PatchSet")
def test_parse_git_modified_lines_branch(mock_patchset: MagicMock, mock_repo: MagicMock) -> None:
    """Test parsing changes against base branch (default behavior)."""
    # Mock repository
    mock_repo_instance = Mock()
    mock_repo_instance.git_dir = "/test/repo/.git"
    mock_repo_instance.git.diff.return_value = "mock diff output"
    mock_repo.return_value = mock_repo_instance
    
    # Mock PatchSet
    mock_patchset.return_value = []
    
    # Call function with BRANCH mode (default)
    result = parse_git_modified_lines(mode=DiffMode.BRANCH, base_branch="origin/main")
    
    # Verify git.diff was called with base branch
    mock_repo_instance.git.diff.assert_called_once_with(
        "origin/main",
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )
    assert result == {}


def test_parse_git_modified_lines_invalid_mode() -> None:
    """Test that appropriate errors are raised for invalid mode configurations."""
    # Test REF mode without diff_ref
    with pytest.raises(ValueError, match="diff_ref is required for REF mode"):
        parse_git_modified_lines(mode=DiffMode.REF)
    
    # Test BRANCH mode without base_branch
    with pytest.raises(ValueError, match="base_branch is required for BRANCH mode"):
        parse_git_modified_lines(mode=DiffMode.BRANCH)
