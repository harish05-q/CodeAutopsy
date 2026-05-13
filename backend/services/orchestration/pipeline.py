"""
Analysis pipeline orchestrator.

Manages the full analysis pipeline from repo submission to completion.
Each stage: logs inputs/outputs, saves artifacts as JSON, tracks timing.

Design decisions:
- Each stage is a separate function for independent testing.
- PipelineContext is the shared data bus — fully inspectable.
- Artifacts are saved to disk after each stage for debugging.
- Failures are caught per-stage; pipeline continues where possible.
- All timing is tracked for observability.
"""

import asyncio
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from stat import S_IWRITE
from typing import Any

from sqlalchemy.orm import Session

from backend.analyzers.ast_analyzer import run_ast_analysis
from backend.analyzers.call_graph_builder import build_call_graph
from backend.services.analysis.static_analyzer import run_static_analysis
from backend.analyzers.dependency_analyzer import build_dependency_graph
from backend.core.constants import AnalysisStatus
from backend.core.logger import correlation_id_var, generate_id, get_logger
from backend.models.database import Analysis, AnalysisStage, Repository
from backend.models.schemas import PipelineContext
from backend.services.embeddings.embedding_service import generate_embeddings
from backend.services.github.clone_service import clone_repository
from backend.services.github.scanner import scan_repository
from backend.services.graph.graph_service import analyze_graph, graph_risks_to_findings
from backend.services.llm.reasoning_service import generate_architectural_autopsy
from backend.services.parsing.python_parser import parse_all_python_files
from backend.services.reporting.pdf_generator import generate_pdf_report

logger = get_logger(__name__)


def _remove_readonly(func: Any, path: str, excinfo: Any) -> None:
    """Helper to remove read-only files (like .git objects on Windows)."""
    Path(path).chmod(S_IWRITE)
    func(path)


def _save_artifact(artifacts_dir: Path, stage_name: str, data: dict) -> Path:  # type: ignore[type-arg]
    """
    Save stage output as a JSON artifact for debugging and inspection.

    Args:
        artifacts_dir: Base directory for this analysis run's artifacts.
        stage_name: Name of the pipeline stage (used as filename).
        data: Serializable data to save.

    Returns:
        Path to the saved artifact file.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{stage_name}.json"
    artifact_path.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("artifact_saved", stage=stage_name, path=str(artifact_path))
    return artifact_path


def _update_analysis_status(
    db: Session,
    analysis_id: int,
    status: str,
    stage: str | None = None,
    progress: float = 0.0,
    error: str | None = None,
) -> None:
    """Update the analysis record in the database."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if analysis:
        analysis.status = status
        analysis.current_stage = stage
        analysis.progress_percent = progress
        if error:
            analysis.error_message = error
            analysis.error_stage = stage
        db.commit()


def _record_stage(
    db: Session,
    analysis_id: int,
    stage_name: str,
    status: str,
    duration: float,
    items: int = 0,
    summary: str = "",
    artifact_path: str = "",
    error: str | None = None,
) -> None:
    """Record a pipeline stage execution in the database."""
    stage = AnalysisStage(
        analysis_id=analysis_id,
        stage_name=stage_name,
        status=status,
        duration_seconds=round(duration, 3),
        items_processed=items,
        summary=summary,
        artifact_path=artifact_path,
        error_message=error,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(stage)
    db.commit()


def run_pipeline(
    repo_url: str,
    analysis_id: int,
    repository_id: int,
    db: Session,
    repos_dir: Path,
    artifacts_base_dir: Path,
    clone_timeout: int = 120,
) -> PipelineContext:
    """
    Run the full analysis pipeline for a repository.

    Stages:
    1. Clone repository
    2. Scan file structure
    3. Parse Python files
    4. Run AST analysis
    5. Build dependency graph
    6. Build call graph
    7. Generate semantic embeddings
    8. Run static analysis tools (Bandit, Radon, Semgrep)
    9. Generate LLM Architectural Autopsy
    10. Generate PDF Report

    Each stage saves artifacts and updates the database.
    Failures are caught per-stage and recorded.

    Args:
        repo_url: GitHub repository URL.
        analysis_id: Database ID of the analysis run.
        repository_id: Database ID of the repository.
        db: Database session.
        repos_dir: Directory to clone repos into.
        artifacts_base_dir: Base directory for analysis artifacts.
        clone_timeout: Git clone timeout in seconds.

    Returns:
        PipelineContext with all results.
    """
    # Set correlation ID for this pipeline run
    corr_id = generate_id()
    correlation_id_var.set(corr_id)

    artifacts_dir = artifacts_base_dir / str(analysis_id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    ctx = PipelineContext(
        analysis_id=analysis_id,
        repository_id=repository_id,
        repo_url=repo_url,
        artifacts_dir=artifacts_dir,
    )

    logger.info(
        "pipeline_started",
        analysis_id=analysis_id,
        repo_url=repo_url,
    )

    # Update analysis start time
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if analysis:
        analysis.started_at = datetime.now(timezone.utc)
        analysis.artifacts_path = str(artifacts_dir)
        db.commit()

    # ── Stage 1: Clone ──────────────────────────────────────────
    stage = "cloning"
    _update_analysis_status(db, analysis_id, AnalysisStatus.CLONING, stage, 10.0)
    start = time.monotonic()

    try:
        # Clear existing clone if it exists before cloning
        # Assumes repo directory naming convention based on repo URL
        repo_path = repos_dir / str(repository_id)
        if repo_path.exists():
            shutil.rmtree(repo_path, onerror=_remove_readonly)
        
        clone_path, owner, name = clone_repository(repo_url, repos_dir, clone_timeout)
        ctx.clone_path = clone_path
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Update repository metadata
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if repo:
            repo.owner = owner
            repo.name = name
            repo.clone_path = str(clone_path)
            db.commit()

        _record_stage(db, analysis_id, stage, "completed", duration, summary=f"Cloned {owner}/{name}")
        logger.info("stage_complete", stage=stage, duration=round(duration, 3))

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        _update_analysis_status(db, analysis_id, AnalysisStatus.FAILED, stage, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))
        return ctx

    # ── Stage 2: Scan ───────────────────────────────────────────
    stage = "scanning"
    _update_analysis_status(db, analysis_id, AnalysisStatus.SCANNING, stage, 25.0)
    start = time.monotonic()

    try:
        scan_result = scan_repository(clone_path)
        ctx.scan_result = scan_result
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Save scan artifact
        _save_artifact(artifacts_dir, "scan_result", scan_result.model_dump())

        # Update repository metadata
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if repo:
            repo.total_files = scan_result.total_files
            repo.total_lines = scan_result.total_lines
            repo.languages_detected = json.dumps(scan_result.languages_detected)
            db.commit()

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=scan_result.total_files,
            summary=f"Found {scan_result.total_files} files, {len(scan_result.python_files)} Python files",
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        _update_analysis_status(db, analysis_id, AnalysisStatus.FAILED, stage, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))
        return ctx

    # ── Stage 3: Parse ──────────────────────────────────────────
    stage = "parsing"
    _update_analysis_status(db, analysis_id, AnalysisStatus.PARSING, stage, 40.0)
    start = time.monotonic()

    try:
        parse_result = parse_all_python_files(scan_result.python_files, clone_path)
        ctx.parse_result = parse_result
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Save parse artifact
        _save_artifact(artifacts_dir, "parse_result", parse_result.model_dump())

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=len(parse_result.modules),
            summary=(
                f"Parsed {len(parse_result.modules)} modules: "
                f"{parse_result.total_functions} functions, "
                f"{parse_result.total_classes} classes"
            ),
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        _update_analysis_status(db, analysis_id, AnalysisStatus.FAILED, stage, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))
        return ctx

    # ── Stage 4: AST Analysis ───────────────────────────────────
    stage = "analyzing_ast"
    _update_analysis_status(db, analysis_id, AnalysisStatus.ANALYZING_AST, stage, 55.0)
    start = time.monotonic()

    try:
        python_paths = [f.path for f in scan_result.python_files]
        findings = run_ast_analysis(parse_result.modules, python_paths, clone_path)
        ctx.risks = findings
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Save findings artifact
        _save_artifact(
            artifacts_dir, "ast_findings",
            [f.model_dump() for f in findings],
        )

        # Update analysis stats
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.total_functions = parse_result.total_functions
            analysis.total_classes = parse_result.total_classes
            analysis.total_modules = len(parse_result.modules)
            analysis.risk_count = len(findings)
            db.commit()

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=len(findings),
            summary=f"Found {len(findings)} risk findings",
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Stage 5: Build Dependency Graph ──────────────────────────
    stage = "building_dependency_graph"
    _update_analysis_status(db, analysis_id, AnalysisStatus.BUILDING_GRAPHS, stage, 65.0)
    start = time.monotonic()

    try:
        dep_graph = build_dependency_graph(parse_result.modules)
        ctx.graph_data["dependency"] = dep_graph
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Save graph artifact
        _save_artifact(artifacts_dir, "dependency_graph", dep_graph.model_dump())

        # Run graph analysis
        dep_analysis = analyze_graph(dep_graph)
        _save_artifact(artifacts_dir, "dependency_analysis", dep_analysis)

        # Convert graph issues to risk findings
        graph_findings = graph_risks_to_findings(dep_analysis, "dependency")
        ctx.risks.extend(graph_findings)

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=len(dep_graph.nodes),
            summary=(
                f"{len(dep_graph.nodes)} nodes, {len(dep_graph.edges)} edges, "
                f"{dep_analysis['summary']['cycle_count']} cycles"
            ),
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Stage 6: Build Call Graph ────────────────────────────────
    stage = "building_call_graph"
    _update_analysis_status(db, analysis_id, AnalysisStatus.BUILDING_GRAPHS, stage, 78.0)
    start = time.monotonic()

    try:
        call_graph = build_call_graph(parse_result.modules)
        ctx.graph_data["call_graph"] = call_graph
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        # Save graph artifact
        _save_artifact(artifacts_dir, "call_graph", call_graph.model_dump())

        # Run graph analysis
        call_analysis = analyze_graph(call_graph)
        _save_artifact(artifacts_dir, "call_graph_analysis", call_analysis)

        # Convert graph issues to risk findings
        call_findings = graph_risks_to_findings(call_analysis, "call_graph")
        ctx.risks.extend(call_findings)

        # Update total risk count
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.risk_count = len(ctx.risks)
            db.commit()

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=len(call_graph.nodes),
            summary=(
                f"{len(call_graph.nodes)} nodes, {len(call_graph.edges)} edges, "
                f"{call_analysis['summary']['cycle_count']} cycles"
            ),
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Stage 7: Generate Semantic Embeddings ────────────────────
    stage = "generate_embeddings"
    _update_analysis_status(db, analysis_id, AnalysisStatus.BUILDING_GRAPHS, stage, 88.0)
    start = time.monotonic()

    try:
        store, stats = generate_embeddings(parse_result.modules)
        store.save(artifacts_dir)
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=stats["total"],
            summary=f"Embedded {stats['total']} items ({stats['functions']} funcs, {stats['classes']} classes, {stats['modules']} modules)",
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Stage 8: Run Static Analysis Tools ────────────────────────
    stage = "static_analysis"
    _update_analysis_status(db, analysis_id, AnalysisStatus.RUNNING_STATIC_ANALYSIS, stage, 95.0)
    start = time.monotonic()

    try:
        if ctx.clone_path is None:
            raise ValueError("Repository was not cloned successfully")
        static_risks = run_static_analysis(ctx.clone_path)
        ctx.risks.extend(static_risks)
        
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            items=len(static_risks),
            summary=f"Found {len(static_risks)} static analysis findings",
        )
        
        _save_artifact(
            artifacts_dir, "static_analysis",
            [f.model_dump() for f in static_risks],
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Stage 9: Generate LLM Architectural Autopsy ────────────────
    stage = "llm_reasoning"
    _update_analysis_status(db, analysis_id, AnalysisStatus.LLM_REASONING, stage, 98.0)
    start = time.monotonic()

    try:
        if not ctx.scan_result or not ctx.parse_result or "dependency" not in ctx.graph_data:
            raise ValueError("Missing prior stage statistics for LLM reasoning")

        scan_stats = {
            "total_files": ctx.scan_result.total_files,
            "python_files": len(ctx.scan_result.python_files),
        }
        parse_stats = {
            "modules": len(ctx.parse_result.modules),
            "functions": ctx.parse_result.total_functions,
            "classes": ctx.parse_result.total_classes,
        }
        dep_graph = ctx.graph_data["dependency"]
        dependency_stats = {
            "nodes": len(dep_graph.nodes),
            "edges": len(dep_graph.edges),
            "cycles": dep_graph.metadata.get("cycles", 0),
            "orphans": dep_graph.metadata.get("orphans", 0),
            "tight_coupling": 0,
        }

        autopsy_report = asyncio.run(
            generate_architectural_autopsy(
                repo_name=f"{owner}/{name}",
                scan_stats=scan_stats,
                parse_stats=parse_stats,
                dependency_stats=dependency_stats,
                risks=ctx.risks,
            )
        )
        
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            summary=f"Generated autopsy: {autopsy_report.get('architecture_pattern', 'Unknown')}",
        )
        
        # Only save artifact if we got a report (graceful degradation)
        if autopsy_report:
            _save_artifact(
                artifacts_dir, "autopsy_report",
                autopsy_report,
            )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # Save all risk findings (combined AST + graph + static)
    _save_artifact(
        artifacts_dir, "all_findings",
        [f.model_dump() for f in ctx.risks],
    )

    # ── Stage 10: Generate PDF Report ──────────────────────────────
    stage = "generate_pdf_report"
    _update_analysis_status(db, analysis_id, "generating_report", stage, 99.0)
    start = time.monotonic()

    try:
        # Build stats from context securely
        scan_stats = {}
        if ctx.scan_result:
            scan_stats = {
                "total_files": ctx.scan_result.total_files,
                "python_files": len(ctx.scan_result.python_files),
            }
            
        parse_stats = {}
        if ctx.parse_result:
            parse_stats = {
                "modules": len(ctx.parse_result.modules),
                "functions": ctx.parse_result.total_functions,
                "classes": ctx.parse_result.total_classes,
            }
            
        dependency_stats = {}
        dep_graph = ctx.graph_data.get("dependency")
        if dep_graph:
            dependency_stats = {
                "nodes": len(dep_graph.nodes),
                "edges": len(dep_graph.edges),
                "cycles": dep_graph.metadata.get("cycles", 0),
                "tight_coupling": dep_graph.metadata.get("tight_coupling", 0),
            }

        call_graph = ctx.graph_data.get("call_graph")
        call_stats = {}
        if call_graph:
            call_stats = {
                "nodes": len(call_graph.nodes),
                "edges": len(call_graph.edges),
                "orphans": call_graph.metadata.get("orphans", 0),
            }

        pdf_bytes = generate_pdf_report(
            repo_name=f"{owner}/{name}",
            scan_stats=scan_stats,
            parse_stats=parse_stats,
            dependency_stats=dependency_stats,
            call_stats=call_stats,
            risks=ctx.risks,
            llm_autopsy=autopsy_report if 'autopsy_report' in locals() else None,
        )
        
        pdf_path = artifacts_dir / "autopsy_report.pdf"
        pdf_path.write_bytes(pdf_bytes)
        
        duration = time.monotonic() - start
        ctx.stage_timings[stage] = duration

        _record_stage(
            db, analysis_id, stage, "completed", duration,
            summary="PDF report generated successfully",
        )

    except Exception as e:
        duration = time.monotonic() - start
        _record_stage(db, analysis_id, stage, "failed", duration, error=str(e))
        logger.error("stage_failed", stage=stage, error=str(e))

    # ── Mark pipeline as completed ───────────────────────────────
    _update_analysis_status(db, analysis_id, AnalysisStatus.COMPLETED, None, 100.0)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if analysis:
        now = datetime.now(timezone.utc)
        analysis.completed_at = now
        if analysis.started_at:
            # Convert started_at to aware if naive (SQLite stores naive datetimes)
            started = analysis.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            analysis.duration_seconds = (now - started).total_seconds()
        db.commit()

    logger.info(
        "pipeline_complete",
        analysis_id=analysis_id,
        timings=ctx.stage_timings,
    )

    return ctx
