"""
Application-wide constants and enumerations.

All magic strings and values are centralized here.
This makes the codebase grep-friendly and prevents typo bugs.
"""

from enum import StrEnum


class AnalysisStatus(StrEnum):
    """Status of an analysis pipeline run."""

    PENDING = "pending"
    CLONING = "cloning"
    SCANNING = "scanning"
    PARSING = "parsing"
    ANALYZING_AST = "analyzing_ast"
    BUILDING_GRAPHS = "building_graphs"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    RUNNING_STATIC_ANALYSIS = "running_static_analysis"
    LLM_REASONING = "llm_reasoning"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"


class SupportedLanguage(StrEnum):
    """Languages supported for analysis. Starting with Python only."""

    PYTHON = "python"


class RiskSeverity(StrEnum):
    """Severity levels for detected risks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(StrEnum):
    """Categories of detected risks/anti-patterns."""

    GOD_CLASS = "god_class"
    DEEP_INHERITANCE = "deep_inheritance"
    CYCLIC_DEPENDENCY = "cyclic_dependency"
    LARGE_FUNCTION = "large_function"
    HIGH_COMPLEXITY = "high_complexity"
    LOW_COHESION = "low_cohesion"
    DEAD_CODE = "dead_code"
    EXCEPTION_SWALLOWING = "exception_swallowing"
    SECURITY_SMELL = "security_smell"
    HIDDEN_COUPLING = "hidden_coupling"
    TIGHT_COUPLING = "tight_coupling"


class GraphType(StrEnum):
    """Types of graphs the system can produce."""

    DEPENDENCY = "dependency"
    CALL_GRAPH = "call_graph"
    MODULE = "module"
    ARCHITECTURE = "architecture"


# --- File Extension Mappings ---

PYTHON_EXTENSIONS: frozenset[str] = frozenset({".py", ".pyi"})

# Files/directories to always skip during scanning
IGNORED_DIRECTORIES: frozenset[str] = frozenset({
    ".git", ".svn", ".hg",
    "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "node_modules", ".tox", ".nox",
    "venv", ".venv", "env", ".env",
    ".eggs", "*.egg-info",
    "dist", "build",
    ".idea", ".vscode",
})

IGNORED_FILES: frozenset[str] = frozenset({
    ".DS_Store", "Thumbs.db",
    ".gitignore", ".gitattributes",
})

# --- Analysis Thresholds ---

# Functions with more lines than this are flagged as "large"
LARGE_FUNCTION_THRESHOLD: int = 50
# Cyclomatic complexity above this is "high"
HIGH_COMPLEXITY_THRESHOLD: int = 10
# Classes with more methods than this may be "god classes"
GOD_CLASS_METHOD_THRESHOLD: int = 20
# Inheritance depth above this is "deep"
DEEP_INHERITANCE_THRESHOLD: int = 4
# Max parameters before flagging
MAX_PARAMETERS_THRESHOLD: int = 7
