"""
Static Analysis Service.

Wraps external static analysis tools (Radon, Bandit, Semgrep) to find
security, complexity, and quality issues.
"""

import json
import subprocess
from pathlib import Path

from backend.core.logger import get_logger
from backend.models.schemas import RiskFinding

logger = get_logger(__name__)


def _run_bandit(repo_dir: Path) -> list[RiskFinding]:
    """Run Bandit security scanner on the repository."""
    logger.info("running_bandit", repo_dir=str(repo_dir))
    findings: list[RiskFinding] = []
    
    try:
        # Run bandit: -r recursive, -f json format, -ll low severity or higher
        # We use -q (quiet) to avoid unstructured output in stdout
        result = subprocess.run(
            ["bandit", "-r", str(repo_dir), "-f", "json", "-q"],
            capture_output=True,
            text=True,
            check=False,  # Bandit exits with 1 if issues are found
        )
        
        if not result.stdout.strip():
            return []
            
        data = json.loads(result.stdout)
        
        for issue in data.get("results", []):
            severity = issue.get("issue_severity", "LOW").lower()
            if severity not in ["high", "medium", "low"]:
                severity = "medium"
                
            # Convert absolute path to relative path
            file_path = issue.get("filename", "")
            try:
                rel_path = str(Path(file_path).relative_to(repo_dir))
            except ValueError:
                rel_path = file_path
                
            findings.append(RiskFinding(
                category="security",
                severity=severity,
                title=f"Bandit: {issue.get('issue_text')}",
                description=f"Issue: {issue.get('test_id')} - {issue.get('issue_text')}",
                file_path=rel_path,
                line_number=issue.get("line_number"),
                suggestion="Review the flagged code for security vulnerabilities. See Bandit docs for details.",
                evidence={
                    "tool": "bandit",
                    "confidence": issue.get("issue_confidence"),
                    "code": issue.get("code", "").strip(),
                }
            ))
            
    except Exception as e:
        logger.error("bandit_failed", error=str(e))
        
    return findings


def _run_radon_mi(repo_dir: Path) -> list[RiskFinding]:
    """Run Radon Maintainability Index scanner on the repository."""
    logger.info("running_radon", repo_dir=str(repo_dir))
    findings: list[RiskFinding] = []
    
    try:
        # Run radon mi: -j for json output
        result = subprocess.run(
            ["radon", "mi", "-j", str(repo_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        
        if not result.stdout.strip():
            return []
            
        data = json.loads(result.stdout)
        
        for file_path, info in data.items():
            if "error" in info:
                continue
                
            mi_score = info.get("mi", 100.0)
            rank = info.get("rank", "A")
            
            # MI ranges from 0 to 100. Rank A is > 20, B is 10-20, C is < 10.
            # Wait, Radon MI ranges from 0-100 (higher is better). 
            # A (20-100), B (10-19), C (0-9). Let's flag C as high, B as medium.
            if rank in ["C", "F"]:
                severity = "high"
            elif rank == "B":
                severity = "medium"
            else:
                continue  # Skip A
                
            try:
                rel_path = str(Path(file_path).relative_to(repo_dir))
            except ValueError:
                rel_path = file_path
                
            findings.append(RiskFinding(
                category="complexity",
                severity=severity,
                title=f"Low Maintainability Index ({rank})",
                description=f"The module has a very low Maintainability Index of {mi_score:.1f} (Rank {rank}).",
                file_path=rel_path,
                line_number=None,
                suggestion="Consider breaking this module into smaller, more focused modules to improve maintainability.",
                evidence={
                    "tool": "radon",
                    "mi_score": round(mi_score, 2),
                    "rank": rank,
                }
            ))
            
    except Exception as e:
        logger.error("radon_failed", error=str(e))
        
    return findings


def _run_semgrep(repo_dir: Path) -> list[RiskFinding]:
    """Run Semgrep scanner with python security rules."""
    logger.info("running_semgrep", repo_dir=str(repo_dir))
    findings: list[RiskFinding] = []
    
    try:
        # Run semgrep with python rules. --quiet and --json
        # NOTE: Semgrep might take longer than Bandit/Radon.
        result = subprocess.run(
            ["semgrep", "scan", "--config", "p/python", "--json", "--quiet", str(repo_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        
        if not result.stdout.strip():
            return []
            
        data = json.loads(result.stdout)
        
        for issue in data.get("results", []):
            extra = issue.get("extra", {})
            severity_raw = extra.get("severity", "WARNING").lower()
            
            # Map semgrep severity (ERROR, WARNING, INFO) to ours
            if severity_raw == "error":
                severity = "high"
            elif severity_raw == "warning":
                severity = "medium"
            else:
                severity = "low"
                
            file_path = issue.get("path", "")
            try:
                rel_path = str(Path(file_path).relative_to(repo_dir))
            except ValueError:
                rel_path = file_path
                
            findings.append(RiskFinding(
                category="quality",
                severity=severity,
                title=f"Semgrep: {extra.get('message', 'Issue found')[:50]}...",
                description=extra.get('message', 'Issue found'),
                file_path=rel_path,
                line_number=issue.get("start", {}).get("line"),
                suggestion="Review the flagged code and apply standard best practices.",
                evidence={
                    "tool": "semgrep",
                    "rule_id": issue.get("check_id"),
                    "lines": f"{issue.get('start', {}).get('line')}-{issue.get('end', {}).get('line')}",
                }
            ))
            
    except Exception as e:
        logger.error("semgrep_failed", error=str(e))
        
    return findings


def run_static_analysis(repo_dir: Path) -> list[RiskFinding]:
    """
    Run all static analysis tools on the repository.
    
    Args:
        repo_dir: Path to the cloned repository.
        
    Returns:
        List of RiskFinding objects combined from all tools.
    """
    all_findings: list[RiskFinding] = []
    
    # Run Bandit for security
    bandit_findings = _run_bandit(repo_dir)
    all_findings.extend(bandit_findings)
    
    # Run Radon for complexity/maintainability
    radon_findings = _run_radon_mi(repo_dir)
    all_findings.extend(radon_findings)
    
    # Semgrep can be slow, but let's include it for thoroughness
    semgrep_findings = _run_semgrep(repo_dir)
    all_findings.extend(semgrep_findings)
    
    logger.info(
        "static_analysis_complete",
        total_findings=len(all_findings),
        bandit=len(bandit_findings),
        radon=len(radon_findings),
        semgrep=len(semgrep_findings),
    )
    
    return all_findings
