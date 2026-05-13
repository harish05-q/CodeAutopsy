"""
API routes for semantic search over code elements.

Endpoints:
- GET /api/repos/{id}/search  — Semantic search across functions, classes, and modules
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.dependencies.common import DbSession
from backend.core.constants import AnalysisStatus
from backend.core.logger import get_logger
from backend.models.database import Analysis
from backend.services.embeddings.embedding_service import semantic_search
from backend.services.embeddings.faiss_store import FaissStore

logger = get_logger(__name__)

router = APIRouter(prefix="/api/repos/{repo_id}/search", tags=["search"])


class SearchResult(BaseModel):
    """Semantic search result item."""
    id: str
    type: str
    name: str
    file_path: str
    text_preview: str
    score: float


class SearchResponse(BaseModel):
    """Response model for semantic search."""
    results: list[SearchResult]
    total: int


def _get_analysis_for_repo(db: DbSession, repo_id: int) -> Analysis:
    """Get the latest completed analysis for a repository."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.repository_id == repo_id)
        .filter(Analysis.status == AnalysisStatus.COMPLETED)
        .order_by(Analysis.id.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="No completed analysis found for this repository")
    return analysis


@router.get("", response_model=SearchResponse)
def search_code(
    repo_id: int,
    db: DbSession,
    q: str = Query(..., description="Semantic search query", min_length=2),
    k: int = Query(10, description="Number of results to return", ge=1, le=50),
    min_score: float = Query(0.1, description="Minimum cosine similarity score"),
    type: str | None = Query(None, description="Filter by type: function, class, module"),
) -> SearchResponse:
    """
    Perform semantic search over the codebase.
    
    Uses sentence-transformers to encode the query and FAISS to find
    the most semantically similar code elements (functions, classes, modules).
    """
    analysis = _get_analysis_for_repo(db, repo_id)
    
    if not analysis.artifacts_path:
        raise HTTPException(status_code=404, detail="Analysis artifacts not found")
        
    artifacts_dir = Path(analysis.artifacts_path)
    store = FaissStore()
    
    if not store.load(artifacts_dir):
        raise HTTPException(
            status_code=404, 
            detail="FAISS index not found for this repository. It may have failed to generate."
        )

    logger.info("executing_semantic_search", query=q, repo_id=repo_id, k=k)
    
    raw_results = semantic_search(
        query=q,
        store=store,
        k=k,
        min_score=min_score,
        type_filter=type,
    )
    
    results = [SearchResult(**r) for r in raw_results]  # type: ignore[arg-type]
    
    return SearchResponse(results=results, total=len(results))
