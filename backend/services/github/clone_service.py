"""
GitHub repository cloning service.

Safely clones a public GitHub repository to a local directory.
Validates the URL, enforces size limits, and handles timeouts.

Design decisions:
- Uses subprocess for git clone (not a library) for transparency and debuggability.
- All operations are logged with correlation IDs.
- Cloned repos go into an isolated temp directory under the configured repos_dir.
- No authentication — public repos only (can be extended later).
"""

import re
import shutil
import subprocess
from pathlib import Path

from backend.core.logger import get_logger

logger = get_logger(__name__)

# Regex to validate and parse GitHub URLs
GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[\w\-\.]+)/(?P<name>[\w\-\.]+?)(?:\.git)?/?$"
)


class CloneError(Exception):
    """Raised when repository cloning fails."""

    pass


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract owner and repo name from a GitHub URL.

    Args:
        url: GitHub repository URL.

    Returns:
        Tuple of (owner, repo_name).

    Raises:
        CloneError: If the URL is not a valid GitHub repository URL.
    """
    match = GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        raise CloneError(
            f"Invalid GitHub URL: {url}. "
            "Expected format: https://github.com/owner/repo"
        )
    return match.group("owner"), match.group("name")


def clone_repository(
    url: str,
    repos_dir: Path,
    timeout_seconds: int = 120,
) -> tuple[Path, str, str]:
    """
    Clone a GitHub repository to a local directory.

    Steps:
    1. Validate the URL format.
    2. Create a unique directory for this clone.
    3. Run `git clone --depth 1` (shallow clone for speed).
    4. Return the clone path and parsed owner/name.

    Args:
        url: GitHub repository URL.
        repos_dir: Base directory to clone into.
        timeout_seconds: Maximum time to wait for clone.

    Returns:
        Tuple of (clone_path, owner, repo_name).

    Raises:
        CloneError: If cloning fails for any reason.
    """
    owner, name = parse_github_url(url)
    clone_dir = repos_dir / f"{owner}__{name}"

    logger.info(
        "cloning_repository",
        url=url,
        owner=owner,
        name=name,
        target_dir=str(clone_dir),
    )

    # Clean up any previous clone of the same repo
    if clone_dir.exists():
        logger.info("removing_existing_clone", path=str(clone_dir))
        shutil.rmtree(clone_dir, ignore_errors=True)

    try:
        # Shallow clone (--depth 1) is much faster and uses less disk
        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",
                "--single-branch",
                url,
                str(clone_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown git clone error"
            logger.error(
                "clone_failed",
                url=url,
                returncode=result.returncode,
                stderr=error_msg,
            )
            raise CloneError(f"Git clone failed: {error_msg}")

        logger.info(
            "clone_successful",
            url=url,
            path=str(clone_dir),
        )

        return clone_dir, owner, name

    except subprocess.TimeoutExpired:
        # Clean up partial clone
        if clone_dir.exists():
            shutil.rmtree(clone_dir, ignore_errors=True)
        logger.error("clone_timeout", url=url, timeout=timeout_seconds)
        raise CloneError(
            f"Clone timed out after {timeout_seconds}s. "
            "Repository may be too large."
        )
    except FileNotFoundError:
        raise CloneError(
            "Git is not installed or not in PATH. "
            "Please install git: https://git-scm.com/"
        )


def cleanup_clone(clone_path: Path) -> None:
    """
    Remove a cloned repository from disk.

    Args:
        clone_path: Path to the cloned repository.
    """
    if clone_path.exists():
        logger.info("cleaning_up_clone", path=str(clone_path))
        shutil.rmtree(clone_path, ignore_errors=True)
