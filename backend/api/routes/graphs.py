"""
API routes for graph retrieval and analysis.

Endpoints:
- GET /api/repos/{id}/graphs/dependency  — Dependency graph data
- GET /api/repos/{id}/graphs/call        — Call graph data
- GET /api/repos/{id}/graphs/analysis    — Graph analysis report
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.api.dependencies.common import AppConfig, DbSession
from backend.core.logger import get_logger
from backend.models.database import Analysis
from backend.models.schemas import GraphData

logger = get_logger(__name__)

router = APIRouter(prefix="/api/repos/{repo_id}/graphs", tags=["graphs"])


def _load_artifact(artifacts_path: str | None, filename: str) -> dict:  # type: ignore[type-arg]
    """Load a JSON artifact from the analysis artifacts directory."""
    if not artifacts_path:
        raise HTTPException(status_code=404, detail="Analysis artifacts not found")

    artifact_file = Path(artifacts_path) / filename
    if not artifact_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{filename}' not found. Analysis may still be running.",
        )

    return json.loads(artifact_file.read_text(encoding="utf-8"))


def _get_analysis_for_repo(db: DbSession, repo_id: int) -> Analysis:
    """Get the latest analysis for a repository."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.repository_id == repo_id)
        .order_by(Analysis.id.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this repository")
    return analysis


@router.get("/dependency", response_model=GraphData)
def get_dependency_graph(repo_id: int, db: DbSession) -> GraphData:
    """
    Get the dependency graph for a repository.

    Returns nodes (modules) and edges (import relationships)
    suitable for visualization with React Flow.
    """
    analysis = _get_analysis_for_repo(db, repo_id)
    data = _load_artifact(analysis.artifacts_path, "dependency_graph.json")
    return GraphData(**data)


@router.get("/call", response_model=GraphData)
def get_call_graph(repo_id: int, db: DbSession) -> GraphData:
    """
    Get the call graph for a repository.

    Returns nodes (functions) and edges (call relationships).
    """
    analysis = _get_analysis_for_repo(db, repo_id)
    data = _load_artifact(analysis.artifacts_path, "call_graph.json")
    return GraphData(**data)


@router.get("/analysis")
def get_graph_analysis(repo_id: int, db: DbSession) -> dict:  # type: ignore[type-arg]
    """
    Get the full graph analysis report.

    Includes cycles, centrality, fan-in/out, orphans,
    coupling analysis, and dead code candidates.
    """
    analysis = _get_analysis_for_repo(db, repo_id)

    result: dict = {}  # type: ignore[type-arg]

    # Load dependency graph analysis
    try:
        dep_analysis = _load_artifact(analysis.artifacts_path, "dependency_analysis.json")
        result["dependency"] = dep_analysis
    except HTTPException:
        result["dependency"] = None

    # Load call graph analysis
    try:
        call_analysis = _load_artifact(analysis.artifacts_path, "call_graph_analysis.json")
        result["call_graph"] = call_analysis
    except HTTPException:
        result["call_graph"] = None

    return result
