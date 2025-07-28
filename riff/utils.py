import json
import pprint
from enum import Enum
from pathlib import Path

import git
import typer
from git.repo import Repo
from unidiff import PatchedFile, PatchSet

from riff.logger import logger
from riff.violation import Violation


class DiffMode(Enum):
    """Modes for git diff operations."""

    BRANCH = "branch"  # Compare against base branch (default)
    UNSTAGED = "unstaged"  # Uncommitted, unstaged changes
    STAGED = "staged"  # Staged changes
    REF = "ref"  # Arbitrary ref comparison


def parse_ruff_output(ruff_stdout: str) -> tuple[Violation, ...]:
    """
    This method assumes stderr was empty
    """
    logger.debug(f"{ruff_stdout=}")

    if not ruff_stdout:
        logger.debug("No ruff output, assuming no violations")
        return ()

    try:
        raw_violations = json.loads(ruff_stdout)
    except json.JSONDecodeError:
        logger.error("Could not parse Ruff output as JSON")
        raise

    violations = tuple(map(Violation.parse, raw_violations))
    logger.debug(f"parsed {len(violations)} ruff violations")
    return violations


def parse_git_modified_lines(
    mode: DiffMode = DiffMode.BRANCH,
    base_branch: str | None = None,
    diff_ref: str | None = None,
) -> dict[Path, set[int]]:
    """
    Parse and return a dictionary mapping modified files to their changed line indices.

    This function analyzes modifications based on the specified diff mode:
    - BRANCH: Compare current HEAD against a base branch
    - UNSTAGED: Show uncommitted, unstaged changes
    - STAGED: Show staged changes
    - REF: Compare against an arbitrary git reference

    Args:
        mode: The diff mode to use
        base_branch: The base branch for BRANCH mode (required for BRANCH mode)
        diff_ref: The git reference for REF mode (required for REF mode)

    Returns:
        Dict[Path, Set[int]]: A dictionary mapping modified files to sets of line indices that were added.
    """

    def parse_modified_lines(patched_file: PatchedFile) -> set[int]:
        """
        Parse and return the line indices of added non-empty lines in a modified file.

        Args:
            patched_file (PatchedFile): A 'PatchedFile' object representing a modified file.

        Returns:
            set[int]: A set of line indices that have been added with non-empty content.
        """
        return {
            line.target_line_no
            for hunk in patched_file
            for line in hunk
            if line.is_added and line.value.strip() and line.target_line_no is not None
        }

    repo = Repo(search_parent_directories=True)
    repo_root = Path(repo.git_dir).parent

    # Prepare git diff arguments based on mode
    diff_args = []
    if mode == DiffMode.BRANCH:
        if not base_branch:
            msg = "base_branch is required for BRANCH mode"
            raise ValueError(msg)
        diff_args = [base_branch]
    elif mode == DiffMode.UNSTAGED:
        # No arguments for unstaged changes
        diff_args = []
    elif mode == DiffMode.STAGED:
        diff_args = ["--cached"]
    elif mode == DiffMode.REF:
        if not diff_ref:
            msg = "diff_ref is required for REF mode"
            raise ValueError(msg)
        diff_args = [diff_ref]

    # Get the diff
    diff_output = repo.git.diff(
        *diff_args,
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )

    result = {
        (repo_root / patched_file.path): parse_modified_lines(patched_file)
        for patched_file in PatchSet(diff_output)
    }

    if result:
        logger.debug(
            "modified lines:\n"
            + pprint.pformat(
                {
                    str(file): sorted(changed_lines)
                    for file, changed_lines in result.items()
                },
                compact=True,
            )
        )
    else:
        logger.warning(
            f"could not find any git-modified lines in {repo_root}: "
            f"Mode={mode.value}, no changes detected"
        )
    return result


def validate_repo_path() -> Path:
    """
    Validate and retrieve the repository path.

    This function attempts to identify the parent directory of the current Git repository.
    It does so by searching upwards from the current working directory for the nearest Git repository.
    If a valid Git repository is found, the function returns the resolved path of its parent directory.
    If no Git repository is found, an error message is logged, and the application exits with a non-zero status.

    Returns:
        Path: The resolved path of the parent directory of the detected Git repository.

    Raises:
        typer.Exit: Raised with a status code of 1 if a Git repository is not found in the directory hierarchy.
    """
    try:
        return Path(git.Repo(search_parent_directories=True).git_dir).parent.resolve()
    except git.exc.InvalidGitRepositoryError:
        logger.error(f"Cannot detect repository in {Path.cwd()}")
        raise typer.Exit(1) from None  # no need for whole stack trace
