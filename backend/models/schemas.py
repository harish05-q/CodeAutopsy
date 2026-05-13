"""
Pydantic models for API request/response types and internal data structures.

Every piece of structured data flowing through the system has a Pydantic model.
This provides:
- Runtime validation
- Auto-generated API docs
- Type safety
- Serialization to/from JSON

Design decisions:
- Separate models for API (request/response) vs internal (analysis data).
- Internal models are used for intermediate artifacts saved to disk.
- All models are immutable (frozen) where possible to prevent accidental mutation.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


# ============================================================
# API Request / Response Models
# ============================================================


class RepoSubmitRequest(BaseModel):
    """Request body for submitting a repository for analysis."""

    url: HttpUrl = Field(
        ..., description="GitHub repository URL to analyze"
    )


class RepoSubmitResponse(BaseModel):
    """Response after submitting a repository."""

    analysis_id: int
    repository_id: int
    status: str
    message: str


class AnalysisStatusResponse(BaseModel):
    """Current status of an analysis pipeline run."""

    analysis_id: int
    repository_id: int
    status: str
    current_stage: str | None = None
    progress_percent: float = 0.0
    started_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    stages: list["StageStatus"] = []


class StageStatus(BaseModel):
    """Status of a single pipeline stage."""

    stage_name: str
    status: str
    duration_seconds: float | None = None
    items_processed: int = 0
    summary: str | None = None
    error_message: str | None = None


class RepositoryInfo(BaseModel):
    """Summary information about an analyzed repository."""

    id: int
    url: str
    owner: str
    name: str
    total_files: int = 0
    total_lines: int = 0
    languages: list[str] = []
    created_at: datetime


# ============================================================
# Internal Data Models — Used for analysis artifacts
# ============================================================


class FileInfo(BaseModel):
    """Metadata about a single file in the repository."""

    path: str = Field(..., description="Relative path within the repo")
    absolute_path: str = ""
    language: str = "unknown"
    size_bytes: int = 0
    line_count: int = 0
    extension: str = ""


class FunctionInfo(BaseModel):
    """Extracted information about a function/method."""

    name: str
    qualified_name: str = ""  # module.class.function
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    line_count: int = 0
    parameters: list[str] = []
    return_type: str | None = None
    decorators: list[str] = []
    docstring: str | None = None
    is_method: bool = False
    is_async: bool = False
    calls: list[str] = []  # Functions this function calls
    complexity: int = 1  # Cyclomatic complexity


class ClassInfo(BaseModel):
    """Extracted information about a class."""

    name: str
    qualified_name: str = ""  # module.class
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    line_count: int = 0
    bases: list[str] = []  # Parent classes
    decorators: list[str] = []
    docstring: str | None = None
    methods: list[str] = []  # Method names
    attributes: list[str] = []
    method_count: int = 0


class ImportInfo(BaseModel):
    """An import statement extracted from source code."""

    module: str  # The module being imported
    names: list[str] = []  # Specific names imported (from X import a, b)
    alias: str | None = None
    is_relative: bool = False
    file_path: str = ""
    line_number: int = 0


class ModuleInfo(BaseModel):
    """Analysis results for a single Python module (file)."""

    file_path: str
    module_name: str = ""  # Dotted module name
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    imports: list[ImportInfo] = []
    global_variables: list[str] = []
    docstring: str | None = None
    line_count: int = 0
    # Metrics
    total_functions: int = 0
    total_classes: int = 0
    complexity_score: float = 0.0


class RepoScanResult(BaseModel):
    """Result of scanning the repository file structure."""

    total_files: int = 0
    total_directories: int = 0
    python_files: list[FileInfo] = []
    all_files: list[FileInfo] = []
    languages_detected: list[str] = []
    total_lines: int = 0
    directory_tree: dict[str, list[str]] = {}  # dir -> list of files


class ParseResult(BaseModel):
    """Result of parsing all source files in the repository."""

    modules: list[ModuleInfo] = []
    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0
    parse_errors: list[str] = []
    duration_seconds: float = 0.0


# ============================================================
# Graph Data Models
# ============================================================


class GraphNode(BaseModel):
    """A node in a dependency/call/module graph."""

    id: str
    label: str
    type: str = "module"  # module, function, class
    metadata: dict[str, str | int | float] = {}


class GraphEdge(BaseModel):
    """An edge in a dependency/call/module graph."""

    source: str
    target: str
    relationship: str = "depends_on"  # depends_on, calls, inherits
    weight: float = 1.0


class GraphData(BaseModel):
    """Serializable graph representation for API responses and artifacts."""

    graph_type: str
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    metadata: dict[str, str | int | float] = {}


# ============================================================
# Risk & Analysis Models
# ============================================================


class RiskFinding(BaseModel):
    """A single risk or anti-pattern detected in the codebase."""

    category: str
    severity: str  # low, medium, high, critical
    title: str
    description: str
    file_path: str = ""
    line_number: int | None = None
    suggestion: str = ""
    evidence: dict[str, str | int | float] = {}


class AnalysisArtifact(BaseModel):
    """Metadata about a saved analysis artifact."""

    stage: str
    artifact_type: str  # json, graph, embedding, report
    file_path: str
    created_at: datetime
    size_bytes: int = 0
    description: str = ""


class PipelineContext(BaseModel):
    """
    Shared context passed through the analysis pipeline.

    Each stage reads from and writes to this context.
    This is the "data bus" of the pipeline — fully inspectable.
    """

    analysis_id: int
    repository_id: int
    repo_url: str = ""
    clone_path: Path | None = None
    artifacts_dir: Path | None = None
    # Populated by each stage
    scan_result: RepoScanResult | None = None
    parse_result: ParseResult | None = None
    graph_data: dict[str, GraphData] = {}
    risks: list[RiskFinding] = []
    # Timing for each stage
    stage_timings: dict[str, float] = {}

    class Config:
        arbitrary_types_allowed = True
