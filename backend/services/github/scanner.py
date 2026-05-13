"""
Repository file scanner.

Indexes all files in a cloned repository: paths, sizes, languages, line counts.
Produces a RepoScanResult that downstream stages consume.

Design decisions:
- Pure function: takes a path, returns structured data. No side effects.
- Respects IGNORED_DIRECTORIES and IGNORED_FILES from constants.
- Only counts files within size limits to prevent OOM on huge binaries.
- Language detection is extension-based (simple, deterministic, fast).
"""

from pathlib import Path

from backend.core.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_FILES,
    PYTHON_EXTENSIONS,
)
from backend.core.logger import get_logger
from backend.models.schemas import FileInfo, RepoScanResult

logger = get_logger(__name__)


def _detect_language(extension: str) -> str:
    """Map file extension to language name."""
    extension_map: dict[str, str] = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
        ".txt": "text",
        ".toml": "toml",
        ".cfg": "config",
        ".ini": "config",
    }
    return extension_map.get(extension.lower(), "unknown")


def _count_lines(file_path: Path, max_size_kb: int = 1024) -> int:
    """
    Count lines in a text file safely.

    Skips files larger than max_size_kb to avoid reading huge binaries.
    Returns 0 on any read error (binary files, encoding issues).
    """
    if file_path.stat().st_size > max_size_kb * 1024:
        return 0
    try:
        return sum(1 for _ in file_path.open("r", encoding="utf-8", errors="ignore"))
    except (OSError, UnicodeDecodeError):
        return 0


def _should_skip_directory(dir_name: str) -> bool:
    """Check if a directory should be skipped during scanning."""
    return dir_name in IGNORED_DIRECTORIES or dir_name.startswith(".")


def scan_repository(
    repo_path: Path,
    max_files: int = 5000,
    max_file_size_kb: int = 1024,
) -> RepoScanResult:
    """
    Scan a cloned repository and index all files.

    Walks the directory tree, collects file metadata, and identifies Python files
    for downstream analysis.

    Args:
        repo_path: Path to the cloned repository root.
        max_files: Maximum number of files to index (safety limit).
        max_file_size_kb: Maximum size per file in KB for line counting.

    Returns:
        RepoScanResult with complete file listing and metadata.
    """
    logger.info("scanning_repository", path=str(repo_path))

    all_files: list[FileInfo] = []
    python_files: list[FileInfo] = []
    languages_seen: set[str] = set()
    total_lines = 0
    directory_tree: dict[str, list[str]] = {}
    total_dirs = 0

    for item in sorted(repo_path.rglob("*")):
        # Skip ignored directories
        if any(_should_skip_directory(part) for part in item.parts):
            continue

        if item.is_dir():
            total_dirs += 1
            rel_dir = str(item.relative_to(repo_path))
            directory_tree[rel_dir] = [
                f.name for f in item.iterdir()
                if f.is_file() and f.name not in IGNORED_FILES
            ]
            continue

        if not item.is_file():
            continue

        # Safety limit
        if len(all_files) >= max_files:
            logger.warning(
                "max_files_reached",
                max_files=max_files,
                path=str(repo_path),
            )
            break

        # Skip ignored files
        if item.name in IGNORED_FILES:
            continue

        rel_path = str(item.relative_to(repo_path))
        extension = item.suffix
        language = _detect_language(extension)
        size_bytes = item.stat().st_size
        line_count = _count_lines(item, max_file_size_kb)
        total_lines += line_count

        file_info = FileInfo(
            path=rel_path,
            absolute_path=str(item),
            language=language,
            size_bytes=size_bytes,
            line_count=line_count,
            extension=extension,
        )

        all_files.append(file_info)

        if language != "unknown":
            languages_seen.add(language)

        if extension in PYTHON_EXTENSIONS:
            python_files.append(file_info)

    result = RepoScanResult(
        total_files=len(all_files),
        total_directories=total_dirs,
        python_files=python_files,
        all_files=all_files,
        languages_detected=sorted(languages_seen),
        total_lines=total_lines,
        directory_tree=directory_tree,
    )

    logger.info(
        "scan_complete",
        total_files=result.total_files,
        python_files=len(python_files),
        languages=result.languages_detected,
        total_lines=total_lines,
    )

    return result
