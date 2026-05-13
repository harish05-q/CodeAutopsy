"""
LLM Reasoning Service.

Aggregates pipeline artifacts and asks the LLM to synthesize an
architectural autopsy report.
"""

from pathlib import Path
from typing import Any

from backend.core.logger import get_logger
from backend.models.schemas import RiskFinding
from backend.services.llm.groq_client import generate_json_response
from backend.services.llm.prompts import (
    SYSTEM_PROMPT_ARCHITECTURE,
    build_architecture_user_prompt,
)

logger = get_logger(__name__)


async def generate_architectural_autopsy(
    repo_name: str,
    scan_stats: dict[str, Any],
    parse_stats: dict[str, Any],
    dependency_stats: dict[str, Any],
    risks: list[RiskFinding],
) -> dict[str, Any]:
    """
    Generate an architectural autopsy report using the LLM.
    
    Args:
        repo_name: The name of the repository (owner/name).
        scan_stats: Statistics from the scanning stage.
        parse_stats: Statistics from the parsing stage.
        dependency_stats: Statistics from the dependency graph stage.
        risks: List of detected risk findings.
        
    Returns:
        A dictionary containing the parsed LLM response.
    """
    logger.info("generating_architectural_autopsy", repo_name=repo_name)
    
    # Combine stats
    stats = {
        "total_files": scan_stats.get("total_files", 0),
        "python_files": scan_stats.get("python_files", 0),
        "modules": parse_stats.get("modules", 0),
        "functions": parse_stats.get("functions", 0),
        "classes": parse_stats.get("classes", 0),
    }
    
    # Format dependency summary
    dep_summary = (
        f"Nodes (Files/Modules): {dependency_stats.get('nodes', 0)}\n"
        f"Edges (Imports): {dependency_stats.get('edges', 0)}\n"
        f"Cycles Detected: {dependency_stats.get('cycles', 0)}\n"
        f"Orphaned Modules: {dependency_stats.get('orphans', 0)}\n"
        f"Tight Coupling Pairs: {dependency_stats.get('tight_coupling', 0)}\n"
    )
    
    # Sort risks by severity (high -> medium -> low)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.severity, 4))
    
    # Convert RiskFinding models to dicts for the prompt builder
    risk_dicts = [
        {
            "severity": r.severity,
            "category": r.category,
            "title": r.title,
            "file_path": r.file_path,
        }
        for r in sorted_risks
    ]
    
    user_prompt = build_architecture_user_prompt(
        repo_name=repo_name,
        stats=stats,
        top_risks=risk_dicts,
        dependency_summary=dep_summary,
    )
    
    response = await generate_json_response(
        system_prompt=SYSTEM_PROMPT_ARCHITECTURE,
        user_prompt=user_prompt,
    )
    
    logger.info("architectural_autopsy_generated", repo_name=repo_name)
    return response
