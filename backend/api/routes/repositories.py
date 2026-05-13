"""
API routes for repository submission and analysis status.

Endpoints:
- POST /api/repos          — Submit a repository for analysis
- GET  /api/repos          — List all analyzed repositories
- GET  /api/repos/{id}     — Get repository details
- GET  /api/analysis/{id}  — Get analysis status and stage details
"""

import json
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.api.dependencies.common import AppConfig, DbSession
from backend.core.logger import get_logger
from backend.models.database import Analysis, AnalysisStage, Repository
from backend.models.schemas import (
    AnalysisStatusResponse,
    RepoSubmitRequest,
    RepoSubmitResponse,
    RepositoryInfo,
    StageStatus,
)
from backend.services.orchestration.pipeline import run_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["repositories"])


@router.post("/repos", response_model=RepoSubmitResponse)
def submit_repository(
    request: RepoSubmitRequest,
    db: DbSession,
    config: AppConfig,
) -> RepoSubmitResponse:
    """
    Submit a GitHub repository URL for analysis.

    Creates a repository record and analysis run, then kicks off
    the analysis pipeline in a background thread.

    Why background thread instead of Celery/task queue?
    - Simplicity: no external broker needed for Phase 1.
    - SQLite: doesn't need connection pooling complexity.
    - Can be upgraded to a proper task queue later.
    """
    url_str = str(request.url).rstrip("/")

    logger.info("repo_submitted", url=url_str)

    # Create repository record
    repo = Repository(
        url=url_str,
        owner="",  # Will be populated during clone
        name="",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Create analysis record
    analysis = Analysis(
        repository_id=repo.id,
        status="pending",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Run pipeline in background thread
    # NOTE: Creates a new DB session for the background thread because
    # SQLAlchemy sessions are not thread-safe.
    from backend.api.dependencies.common import _get_session_factory

    def _run_in_background() -> None:
        session_factory = _get_session_factory()
        bg_db = session_factory()
        try:
            run_pipeline(
                repo_url=url_str,
                analysis_id=analysis.id,
                repository_id=repo.id,
                db=bg_db,
                repos_dir=Path(config.repos_dir),
                artifacts_base_dir=Path(config.artifacts_dir),
                clone_timeout=config.clone_timeout_seconds,
            )
        except Exception as e:
            logger.error("pipeline_background_error", error=str(e))
        finally:
            bg_db.close()

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()

    return RepoSubmitResponse(
        analysis_id=analysis.id,
        repository_id=repo.id,
        status="pending",
        message=f"Analysis started for {url_str}",
    )


@router.get("/repos", response_model=list[RepositoryInfo])
def list_repositories(db: DbSession) -> list[RepositoryInfo]:
    """List all repositories that have been submitted for analysis."""
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    results: list[RepositoryInfo] = []
    for repo in repos:
        languages = []
        if repo.languages_detected:
            try:
                languages = json.loads(repo.languages_detected)
            except (json.JSONDecodeError, TypeError):
                pass

        results.append(RepositoryInfo(
            id=repo.id,
            url=repo.url,
            owner=repo.owner,
            name=repo.name,
            total_files=repo.total_files or 0,
            total_lines=repo.total_lines or 0,
            languages=languages,
            created_at=repo.created_at,
        ))
    return results


@router.get("/repos/{repo_id}", response_model=RepositoryInfo)
def get_repository(repo_id: int, db: DbSession) -> RepositoryInfo:
    """Get details about a specific repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    languages = []
    if repo.languages_detected:
        try:
            languages = json.loads(repo.languages_detected)
        except (json.JSONDecodeError, TypeError):
            pass

    return RepositoryInfo(
        id=repo.id,
        url=repo.url,
        owner=repo.owner,
        name=repo.name,
        total_files=repo.total_files or 0,
        total_lines=repo.total_lines or 0,
        languages=languages,
        created_at=repo.created_at,
    )


@router.get("/analysis/{analysis_id}", response_model=AnalysisStatusResponse)
def get_analysis_status(analysis_id: int, db: DbSession) -> AnalysisStatusResponse:
    """
    Get the current status of an analysis run.

    Returns overall status plus per-stage details for observability.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get all stages for this analysis
    stages = (
        db.query(AnalysisStage)
        .filter(AnalysisStage.analysis_id == analysis_id)
        .order_by(AnalysisStage.id)
        .all()
    )

    stage_statuses = [
        StageStatus(
            stage_name=s.stage_name,
            status=s.status,
            duration_seconds=s.duration_seconds,
            items_processed=s.items_processed or 0,
            summary=s.summary,
            error_message=s.error_message,
        )
        for s in stages
    ]

    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        repository_id=analysis.repository_id,
        status=analysis.status,
        current_stage=analysis.current_stage,
        progress_percent=analysis.progress_percent or 0.0,
        started_at=analysis.started_at,
        duration_seconds=analysis.duration_seconds,
        error_message=analysis.error_message,
        stages=stage_statuses,
    )


@router.get("/analysis/{analysis_id}/artifacts/{artifact_name}")
def get_analysis_artifact(analysis_id: int, artifact_name: str, db: DbSession) -> Any:
    """Get a specific artifact (JSON) from an analysis run."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not analysis.artifacts_path:
        raise HTTPException(status_code=404, detail="Artifacts path not set")

    # Add .json extension if not provided
    if not artifact_name.endswith(".json"):
        artifact_name += ".json"

    artifact_file = Path(analysis.artifacts_path) / artifact_name
    if not artifact_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{artifact_name}' not found",
        )

    try:
        return json.loads(artifact_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse artifact JSON")


@router.get("/analysis/{analysis_id}/report/download")
def download_pdf_report(analysis_id: int, db: DbSession) -> FileResponse:
    """Download the generated PDF autopsy report."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not analysis.artifacts_path:
        raise HTTPException(status_code=404, detail="Artifacts path not set")

    pdf_file = Path(analysis.artifacts_path) / "autopsy_report.pdf"
    if not pdf_file.exists():
        raise HTTPException(
            status_code=404,
            detail="PDF report not found. Analysis may still be running or PDF generation failed.",
        )

    # We need the repository name for a nice filename
    repo = db.query(Repository).filter(Repository.id == analysis.repository_id).first()
    filename = "codeautopsy_report.pdf"
    if repo and repo.name:
        filename = f"{repo.name}_autopsy.pdf"

    return FileResponse(
        path=pdf_file,
        filename=filename,
        media_type="application/pdf"
    )
