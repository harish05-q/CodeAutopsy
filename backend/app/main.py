import json
import logging
import asyncio
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.config import settings
from backend.app.domain.models import Repository, AnalysisRun, Artifact, ChatMessage, Symbol, Finding
from backend.app.domain.utils import generate_ulid
from backend.app.infrastructure.db import engine, Base, get_db, AsyncSessionLocal
from backend.app.services.orchestrator import Orchestrator, sse_manager
from backend.app.agents.qa_agent import QaAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("codeautopsy")

app = FastAPI(
    title="CodeAutopsy API",
    description="AI-powered code repository dissection and onboarding documentation generation",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

@app.on_event("startup")
async def on_startup():
    """Create database tables on startup if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully.")

# DTO Schemas
class AnalyzeRequest(BaseModel):
    url: str
    ref: Optional[str] = "main"

class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None

# Helper to find latest run for repository
async def get_latest_run(session: AsyncSession, repo_id: str) -> Optional[AnalysisRun]:
    stmt = select(AnalysisRun).where(AnalysisRun.repository_id == repo_id).order_by(desc(AnalysisRun.started_at)).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

# ----------------------------------------------------
# ROUTES
# ----------------------------------------------------

@app.post("/api/v1/repositories/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_repository(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    x_groq_api_key: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    """
    Submits a GitHub repository for dissection. Clones, parses AST, structures graphs,
    and runs LLM document extraction in background.
    """
    url_str = str(request.url).rstrip("/")
    
    # 1. Deduplicate Repository or create new record
    stmt = select(Repository).where(Repository.github_url == url_str)
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()

    if not repo:
        # Extract owner/repo name
        try:
            parts = url_str.split("github.com/")[-1].split("/")
            owner, name = parts[0], parts[1]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL structure.")

        repo = Repository(
            id=generate_ulid(),
            github_url=url_str,
            owner=owner,
            name=name,
            default_branch=request.ref or "main"
        )
        db.add(repo)
        await db.commit()
        await db.refresh(repo)

    # 2. Spawn a new Analysis Run
    run = AnalysisRun(
        id=generate_ulid(),
        repository_id=repo.id,
        commit_sha=None,
        status="queued",
        stage="clone",
        progress=0
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 3. Schedule asynchronous background process
    background_tasks.add_task(
        orchestrator.run_analysis,
        AsyncSessionLocal, # Pass session factory for thread-safety in background task
        repo.id,
        run.id,
        x_groq_api_key
    )

    return {
        "repository_id": repo.id,
        "run_id": run.id,
        "status": "queued"
    }

@app.get("/api/v1/analysis/{run_id}")
async def get_analysis_status(run_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch status, stage, progress, and error code of a run."""
    stmt = select(AnalysisRun).where(AnalysisRun.id == run_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
        
    return {
        "run_id": run.id,
        "repository_id": run.repository_id,
        "status": run.status,
        "stage": run.stage,
        "progress": run.progress,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_code": run.error_code
    }

@app.get("/api/v1/analysis/{run_id}/events")
async def get_analysis_events(run_id: str):
    """Server-Sent Event (SSE) stream for tracking analysis progress in real-time."""
    async def event_generator():
        # Get subscriber queue
        queue = sse_manager.subscribe(run_id)
        try:
            while True:
                item = await queue.get()
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
        except Exception:
            pass
        finally:
            sse_manager.unsubscribe(run_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/v1/repositories/{repo_id}/overview")
async def get_repository_overview(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Returns overview statistics, framework, and maintainability details."""
    latest_run = await get_latest_run(db, repo_id)
    if not latest_run:
        raise HTTPException(status_code=404, detail="No completed analysis runs for repository.")

    repo_dir = settings.ANALYSIS_DIR / repo_id
    manifest_path = repo_dir / "repository_manifest.json"
    risk_path = repo_dir / "risk_report.json"
    arch_path = repo_dir / "architecture_report.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Repository manifest files not found.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    maintainability_score = 70
    avg_complexity = 1.0
    hotspots = []
    if risk_path.exists():
        with open(risk_path, "r", encoding="utf-8") as f:
            risk = json.load(f)
            maintainability_score = risk.get("maintainability_score", 70)
            avg_complexity = risk.get("avg_complexity", 1.0)
            hotspots = risk.get("hotspots", [])

    arch_pattern = "Layered Monolith"
    arch_confidence = 80
    arch_reasoning = ""
    if arch_path.exists():
        with open(arch_path, "r", encoding="utf-8") as f:
            arch = json.load(f)
            arch_pattern = arch.get("pattern", "Layered Monolith")
            arch_confidence = arch.get("confidence", 80)
            arch_reasoning = arch.get("reasoning", "")

    # Calculate count of elements
    stmt_classes = select(Symbol).where(Symbol.run_id == latest_run.id, Symbol.kind == "class")
    res_classes = await db.execute(stmt_classes)
    total_classes = len(res_classes.scalars().all())

    stmt_funcs = select(Symbol).where(Symbol.run_id == latest_run.id, Symbol.kind.in_(["function", "method"]))
    res_funcs = await db.execute(stmt_funcs)
    total_funcs = len(res_funcs.scalars().all())

    # Map details to overview display
    return {
        "repository_id": repo_id,
        "name": manifest.get("name"),
        "owner": manifest.get("owner"),
        "url": manifest.get("url"),
        "stats": [
            {"value": str(manifest.get("total_files")), "label": "Files", "note": f"{total_classes} classes"},
            {"value": str(len(manifest.get("file_list", []))), "label": "Modules", "note": "Python modules"},
            {"value": str(total_classes), "label": "Classes", "note": f"{total_funcs} functions"},
            {"value": str(total_funcs), "label": "Functions", "note": "Total declarations"}
        ],
        "frameworks": manifest.get("frameworks", ["Python"]),
        "architecture": {
            "pattern": arch_pattern,
            "confidence": arch_confidence,
            "reasoning": arch_reasoning
        },
        "maintainability_score": maintainability_score,
        "avg_complexity": avg_complexity,
        "hotspots": hotspots,
        "status": latest_run.status,
        "stage": latest_run.stage,
        "progress": latest_run.progress
    }

@app.get("/api/v1/repositories/{repo_id}/graphs/dependencies")
async def get_dependency_graph(repo_id: str):
    """Retrieve React Flow formatted module import dependency graph."""
    graph_path = settings.ANALYSIS_DIR / repo_id / "dependency_graph.json"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Dependency graph not generated.")
    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/v1/repositories/{repo_id}/graphs/calls")
async def get_call_graph(repo_id: str):
    """Retrieve React Flow formatted function execution call graph."""
    graph_path = settings.ANALYSIS_DIR / repo_id / "call_graph.json"
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Call graph not generated.")
    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/v1/repositories/{repo_id}/architecture")
async def get_architecture_report(repo_id: str):
    """Returns the inferred architectural pattern structure."""
    report_path = settings.ANALYSIS_DIR / repo_id / "architecture_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Architecture report not found.")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/v1/repositories/{repo_id}/onboarding")
async def get_onboarding_guide(repo_id: str):
    """Returns onboarding guide Markdown document."""
    onboarding_path = settings.ANALYSIS_DIR / repo_id / "onboarding_guide.md"
    if not onboarding_path.exists():
        raise HTTPException(status_code=404, detail="Onboarding guide not found.")
    with open(onboarding_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content}

@app.get("/api/v1/repositories/{repo_id}/risks")
async def get_risks_report(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Returns maintainability, list of findings, and hotspots."""
    latest_run = await get_latest_run(db, repo_id)
    if not latest_run:
        raise HTTPException(status_code=404, detail="No run found.")

    report_path = settings.ANALYSIS_DIR / repo_id / "risk_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Risk report not found.")
        
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    return report

@app.post("/api/v1/repositories/{repo_id}/chat")
async def ask_repository_question(
    repo_id: str,
    request: ChatRequest,
    x_groq_api_key: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    """
    RAG QA router. Matches question query against FAISS database
    and synthesizes source-grounded answers.
    """
    conv_id = request.conversation_id or generate_ulid()

    # 1. Record user message in DB
    user_msg = ChatMessage(
        id=generate_ulid(),
        repository_id=repo_id,
        conversation_id=conv_id,
        role="user",
        content=request.question,
        source_refs=[]
    )
    db.add(user_msg)
    await db.commit()

    # 2. Run QA RAG Pipeline
    api_key = x_groq_api_key or settings.GROQ_API_KEY
    qa_agent = QaAgent(api_key=api_key, model_name=settings.GROQ_MODEL)
    loop = asyncio.get_running_loop()
    # Execute synchronous FAISS search and Groq call in threadpool to avoid blocking event loop
    response = await loop.run_in_executor(None, qa_agent.run, repo_id, request.question)

    # 3. Record assistant message in DB
    assistant_msg = ChatMessage(
        id=generate_ulid(),
        repository_id=repo_id,
        conversation_id=conv_id,
        role="assistant",
        content=response.answer,
        source_refs=[s.model_dump() for s in response.sources]
    )
    db.add(assistant_msg)
    await db.commit()

    return {
        "conversation_id": conv_id,
        "answer": response.answer,
        "confidence": response.confidence,
        "sources": [s.model_dump() for s in response.sources]
    }
