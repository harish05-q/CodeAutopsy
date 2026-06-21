import asyncio
from datetime import datetime
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Set, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.config import settings
from backend.app.domain.models import Repository, AnalysisRun, Symbol, Finding, Artifact
from backend.app.domain.utils import generate_ulid

from backend.app.agents.repo_agent import RepoAgent
from backend.app.agents.ast_agent import AstAgent
from backend.app.agents.graph_agent import GraphAgent
from backend.app.agents.embedding_agent import EmbeddingAgent
from backend.app.agents.architecture_agent import ArchitectureAgent
from backend.app.agents.documentation_agent import DocumentationAgent
from backend.app.services.risk_service import RiskService

logger = logging.getLogger(__name__)

class SSEManager:
    def __init__(self):
        self.listeners: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        if run_id not in self.listeners:
            self.listeners[run_id] = set()
        queue = asyncio.Queue()
        self.listeners[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue):
        if run_id in self.listeners:
            self.listeners[run_id].discard(queue)
            if not self.listeners[run_id]:
                del self.listeners[run_id]

    async def broadcast(self, run_id: str, event_type: str, data: dict):
        if run_id in self.listeners:
            payload = {"event": event_type, "data": data}
            for q in self.listeners[run_id]:
                await q.put(payload)

sse_manager = SSEManager()

class Orchestrator:
    def __init__(self):
        self.repo_agent = RepoAgent(
            max_size_mb=settings.MAX_REPO_SIZE_MB,
            max_files=settings.MAX_FILE_COUNT
        )
        self.ast_agent = AstAgent()
        self.graph_agent = GraphAgent()
        self.risk_service = RiskService()
        self.embedding_agent = EmbeddingAgent(model_name=settings.EMBEDDING_MODEL)
        self.architecture_agent = ArchitectureAgent(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.GROQ_MODEL
        )
        self.documentation_agent = DocumentationAgent(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.GROQ_MODEL
        )

    async def run_analysis(self, db_session_factory, repository_id: str, run_id: str, groq_api_key: Optional[str] = None):
        """
        Runs the full analysis pipeline.
        Saves output files, updates SQLite schemas, and emits SSE events.
        """
        # Override agents API keys if dynamic key is supplied
        api_key = groq_api_key or settings.GROQ_API_KEY
        if api_key:
            self.architecture_agent = ArchitectureAgent(api_key=api_key, model_name=settings.GROQ_MODEL)
            self.documentation_agent = DocumentationAgent(api_key=api_key, model_name=settings.GROQ_MODEL)

        # Create output directory for this repository case
        output_dir = settings.ANALYSIS_DIR / repository_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        checkout_path = None
        
        try:
            # Helper to update run status in database
            async def update_status(stage: str, progress: int, status: str = "analyzing", error_code: str = None):
                async with db_session_factory() as session:
                    stmt = select(AnalysisRun).where(AnalysisRun.id == run_id)
                    result = await session.execute(stmt)
                    run = result.scalar_one_or_none()
                    if run:
                        run.stage = stage
                        run.progress = progress
                        run.status = status
                        if error_code:
                            run.error_code = error_code
                        if status in ("completed", "failed"):
                            run.completed_at = datetime.utcnow()
                        await session.commit()
                
                await sse_manager.broadcast(run_id, "stage.progress", {
                    "run_id": run_id,
                    "stage": stage,
                    "progress": progress,
                    "status": status,
                    "error_code": error_code
                })

            async with db_session_factory() as session:
                stmt = select(Repository).where(Repository.id == repository_id)
                result = await session.execute(stmt)
                repo = result.scalar_one_or_none()
                repo_url = repo.github_url
                repo_ref = repo.default_branch

            # ----------------------------------------------------
            # 1. Clone & Scan Manifest
            # ----------------------------------------------------
            await update_status("clone", 10)
            logger.info(f"[{run_id}] Cloning repository: {repo_url} ref={repo_ref}")
            checkout_path, manifest = await self.repo_agent.run(repository_id, repo_url, repo_ref)
            
            # Save manifest file
            manifest_path = output_dir / "repository_manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest.model_dump(), f, indent=2)
            
            await update_status("ast", 25)

            # ----------------------------------------------------
            # 2. Extract AST Symbols
            # ----------------------------------------------------
            logger.info(f"[{run_id}] Extracting AST symbols...")
            ast_data = self.ast_agent.run(checkout_path, manifest.file_list)
            
            ast_path = output_dir / "ast_data.json"
            with open(ast_path, "w", encoding="utf-8") as f:
                json.dump(ast_data, f, indent=2)
                
            # Write Symbols to SQL db
            async with db_session_factory() as session:
                for sym in ast_data.get("symbols", []):
                    db_sym = Symbol(
                        id=generate_ulid(),
                        run_id=run_id,
                        module_id=sym.get("file_path"),
                        kind=sym.get("kind"),
                        qualified_name=sym.get("qualified_name"),
                        file_path=sym.get("file_path"),
                        start_line=sym.get("start_line"),
                        end_line=sym.get("end_line"),
                        decorators=sym.get("decorators", []),
                        complexity=sym.get("complexity", 1)
                    )
                    session.add(db_sym)
                await session.commit()

            await update_status("graph", 45)

            # ----------------------------------------------------
            # 3. Build Dependency & Call Graphs
            # ----------------------------------------------------
            logger.info(f"[{run_id}] Constructing graphs...")
            dep_graph, call_graph = self.graph_agent.run(ast_data, checkout_path, manifest.file_list)
            
            dep_graph_path = output_dir / "dependency_graph.json"
            with open(dep_graph_path, "w", encoding="utf-8") as f:
                json.dump(dep_graph, f, indent=2)
                
            call_graph_path = output_dir / "call_graph.json"
            with open(call_graph_path, "w", encoding="utf-8") as f:
                json.dump(call_graph, f, indent=2)

            await update_status("embed", 60)

            # ----------------------------------------------------
            # 4. Generate FAISS Embeddings and Analyze Risks
            # ----------------------------------------------------
            logger.info(f"[{run_id}] Embedding source code chunks...")
            embedded_chunks = self.embedding_agent.run(
                checkout_path=checkout_path,
                python_files=manifest.file_list,
                symbols=ast_data.get("symbols", []),
                output_dir=output_dir
            )

            # Compute code quality findings & hotspots
            logger.info(f"[{run_id}] Performing static risk analysis...")
            risk_report = self.risk_service.analyze(run_id, ast_data, dep_graph)
            
            risk_path = output_dir / "risk_report.json"
            with open(risk_path, "w", encoding="utf-8") as f:
                json.dump(risk_report.model_dump(), f, indent=2)

            # Write Findings to SQL DB
            async with db_session_factory() as session:
                for find in risk_report.findings:
                    db_find = Finding(
                        id=generate_ulid(),
                        run_id=run_id,
                        rule_id=find.type,
                        severity=find.risk,
                        title=find.location,
                        file_path=find.file_path,
                        line=find.line,
                        evidence=find.advice,
                        recommendation=find.advice
                    )
                    session.add(db_find)
                await session.commit()

            await update_status("report", 80)

            # ----------------------------------------------------
            # 5. Architecture Inference & Documentation Authored via Groq
            # ----------------------------------------------------
            logger.info(f"[{run_id}] Running architecture pattern inference...")
            arch_report = self.architecture_agent.run(
                manifest=manifest.model_dump(),
                python_files=manifest.file_list,
                dependency_graph_nodes=dep_graph.get("nodes", [])
            )
            
            arch_path = output_dir / "architecture_report.md"
            # Write report as markdown
            with open(arch_path, "w", encoding="utf-8") as f:
                f.write(f"# Architecture Pattern: {arch_report.pattern}\n\n")
                f.write(f"Confidence: {arch_report.confidence}%\n\n")
                f.write(f"## Reasoning\n{arch_report.reasoning}\n\n")
                f.write("## Key Evidence\n")
                for ev in arch_report.evidence:
                    f.write(f"- {ev}\n")
                f.write("\n## Mermaid Diagram\n```mermaid\n" + arch_report.mermaid_diagram + "\n```\n")

            # Also save raw json report for easy API retrieval
            arch_json_path = output_dir / "architecture_report.json"
            with open(arch_json_path, "w", encoding="utf-8") as f:
                json.dump(arch_report.model_dump(), f, indent=2)

            logger.info(f"[{run_id}] Generating module summaries and onboarding guides...")
            summaries, readme, onboarding = self.documentation_agent.run(
                manifest=manifest.model_dump(),
                ast_data=ast_data
            )
            
            with open(output_dir / "module_summaries.json", "w", encoding="utf-8") as f:
                json.dump(summaries, f, indent=2)
                
            with open(output_dir / "readme_generated.md", "w", encoding="utf-8") as f:
                f.write(readme)
                
            with open(output_dir / "onboarding_guide.md", "w", encoding="utf-8") as f:
                f.write(onboarding)

            # ----------------------------------------------------
            # 6. Save Artifact Rows & Complete
            # ----------------------------------------------------
            async with db_session_factory() as session:
                artifact_files = [
                    ("manifest", "repository_manifest.json", "application/json"),
                    ("ast", "ast_data.json", "application/json"),
                    ("dependency_graph", "dependency_graph.json", "application/json"),
                    ("call_graph", "call_graph.json", "application/json"),
                    ("risks", "risk_report.json", "application/json"),
                    ("architecture", "architecture_report.json", "application/json"),
                    ("onboarding", "onboarding_guide.md", "text/markdown"),
                    ("readme", "readme_generated.md", "text/markdown")
                ]
                for kind, filename, content_type in artifact_files:
                    session.add(Artifact(
                        id=generate_ulid(),
                        run_id=run_id,
                        kind=kind,
                        relative_path=filename,
                        content_type=content_type
                    ))
                await session.commit()

            await update_status("complete", 100, "completed")
            logger.info(f"[{run_id}] Analysis run completed successfully.")

        except Exception as e:
            logger.exception(f"[{run_id}] Analysis failed.")
            await update_status("failed", 100, "failed", error_code=str(e))
        
        finally:
            # Cleanup cloned repository path to free up space
            if checkout_path and checkout_path.exists():
                logger.info(f"[{run_id}] Cleaning up checkout directory: {checkout_path}")
                shutil.rmtree(checkout_path, ignore_errors=True)
