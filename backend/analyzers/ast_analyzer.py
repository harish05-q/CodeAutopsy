"""
AST Analyzer — extracts quality metrics from parsed code structures.

Operates on the output of the parser (ModuleInfo, FunctionInfo, ClassInfo).
Detects code quality issues using deterministic rules — no LLM involvement.

Detected issues:
- Large functions (too many lines)
- High cyclomatic complexity
- Too many parameters
- God classes (too many methods)
- Deep inheritance
- Missing docstrings
- Exception swallowing (bare except)

Design decisions:
- Pure functions: takes parsed data, returns findings. No I/O.
- Thresholds are configurable via constants.py.
- Each detector is a separate function for independent testing.
"""

import ast
from pathlib import Path

from backend.core.constants import (
    DEEP_INHERITANCE_THRESHOLD,
    GOD_CLASS_METHOD_THRESHOLD,
    HIGH_COMPLEXITY_THRESHOLD,
    LARGE_FUNCTION_THRESHOLD,
    MAX_PARAMETERS_THRESHOLD,
    RiskCategory,
    RiskSeverity,
)
from backend.core.logger import get_logger
from backend.models.schemas import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    RiskFinding,
)

logger = get_logger(__name__)


def detect_large_functions(functions: list[FunctionInfo]) -> list[RiskFinding]:
    """Flag functions exceeding the line count threshold."""
    findings: list[RiskFinding] = []
    for func in functions:
        if func.line_count > LARGE_FUNCTION_THRESHOLD:
            severity = (
                RiskSeverity.HIGH if func.line_count > LARGE_FUNCTION_THRESHOLD * 2
                else RiskSeverity.MEDIUM
            )
            findings.append(RiskFinding(
                category=RiskCategory.LARGE_FUNCTION,
                severity=severity,
                title=f"Large function: {func.name}",
                description=(
                    f"Function '{func.name}' has {func.line_count} lines "
                    f"(threshold: {LARGE_FUNCTION_THRESHOLD}). "
                    "Large functions are harder to test and maintain."
                ),
                file_path=func.file_path,
                line_number=func.start_line,
                suggestion="Consider breaking this function into smaller, focused functions.",
                evidence={"line_count": func.line_count, "threshold": LARGE_FUNCTION_THRESHOLD},
            ))
    return findings


def detect_high_complexity(functions: list[FunctionInfo]) -> list[RiskFinding]:
    """Flag functions with high cyclomatic complexity."""
    findings: list[RiskFinding] = []
    for func in functions:
        if func.complexity > HIGH_COMPLEXITY_THRESHOLD:
            severity = (
                RiskSeverity.HIGH if func.complexity > HIGH_COMPLEXITY_THRESHOLD * 2
                else RiskSeverity.MEDIUM
            )
            findings.append(RiskFinding(
                category=RiskCategory.HIGH_COMPLEXITY,
                severity=severity,
                title=f"High complexity: {func.name}",
                description=(
                    f"Function '{func.name}' has cyclomatic complexity of {func.complexity} "
                    f"(threshold: {HIGH_COMPLEXITY_THRESHOLD}). "
                    "High complexity makes code error-prone and hard to test."
                ),
                file_path=func.file_path,
                line_number=func.start_line,
                suggestion="Simplify by extracting conditions into helper functions or using early returns.",
                evidence={"complexity": func.complexity, "threshold": HIGH_COMPLEXITY_THRESHOLD},
            ))
    return findings


def detect_too_many_parameters(functions: list[FunctionInfo]) -> list[RiskFinding]:
    """Flag functions with too many parameters."""
    findings: list[RiskFinding] = []
    for func in functions:
        # Exclude 'self' and 'cls' from count for methods
        params = [p for p in func.parameters if p not in ("self", "cls")]
        if len(params) > MAX_PARAMETERS_THRESHOLD:
            findings.append(RiskFinding(
                category=RiskCategory.LOW_COHESION,
                severity=RiskSeverity.MEDIUM,
                title=f"Too many parameters: {func.name}",
                description=(
                    f"Function '{func.name}' has {len(params)} parameters "
                    f"(threshold: {MAX_PARAMETERS_THRESHOLD}). "
                    "This often indicates the function is doing too many things."
                ),
                file_path=func.file_path,
                line_number=func.start_line,
                suggestion="Consider grouping related parameters into a dataclass or config object.",
                evidence={"param_count": len(params), "threshold": MAX_PARAMETERS_THRESHOLD},
            ))
    return findings


def detect_god_classes(classes: list[ClassInfo]) -> list[RiskFinding]:
    """Flag classes with too many methods (god class anti-pattern)."""
    findings: list[RiskFinding] = []
    for cls in classes:
        if cls.method_count > GOD_CLASS_METHOD_THRESHOLD:
            findings.append(RiskFinding(
                category=RiskCategory.GOD_CLASS,
                severity=RiskSeverity.HIGH,
                title=f"God class: {cls.name}",
                description=(
                    f"Class '{cls.name}' has {cls.method_count} methods "
                    f"(threshold: {GOD_CLASS_METHOD_THRESHOLD}). "
                    "God classes violate the Single Responsibility Principle."
                ),
                file_path=cls.file_path,
                line_number=cls.start_line,
                suggestion="Split into smaller, focused classes with clear responsibilities.",
                evidence={"method_count": cls.method_count, "threshold": GOD_CLASS_METHOD_THRESHOLD},
            ))
    return findings


def detect_deep_inheritance(classes: list[ClassInfo]) -> list[RiskFinding]:
    """Flag classes with deep inheritance chains."""
    findings: list[RiskFinding] = []
    for cls in classes:
        if len(cls.bases) > DEEP_INHERITANCE_THRESHOLD:
            findings.append(RiskFinding(
                category=RiskCategory.DEEP_INHERITANCE,
                severity=RiskSeverity.MEDIUM,
                title=f"Deep inheritance: {cls.name}",
                description=(
                    f"Class '{cls.name}' inherits from {len(cls.bases)} bases. "
                    "Deep or wide inheritance makes code fragile and hard to understand."
                ),
                file_path=cls.file_path,
                line_number=cls.start_line,
                suggestion="Prefer composition over inheritance.",
                evidence={"base_count": len(cls.bases), "bases": cls.bases},
            ))
    return findings


def detect_missing_docstrings(modules: list[ModuleInfo]) -> list[RiskFinding]:
    """Flag public functions and classes without docstrings."""
    findings: list[RiskFinding] = []
    for module in modules:
        for func in module.functions:
            if not func.name.startswith("_") and not func.docstring:
                findings.append(RiskFinding(
                    category=RiskCategory.LOW_COHESION,
                    severity=RiskSeverity.LOW,
                    title=f"Missing docstring: {func.name}",
                    description=f"Public function '{func.name}' lacks a docstring.",
                    file_path=func.file_path,
                    line_number=func.start_line,
                    suggestion="Add a docstring describing the function's purpose, args, and return value.",
                ))
        for cls in module.classes:
            if not cls.name.startswith("_") and not cls.docstring:
                findings.append(RiskFinding(
                    category=RiskCategory.LOW_COHESION,
                    severity=RiskSeverity.LOW,
                    title=f"Missing docstring: {cls.name}",
                    description=f"Public class '{cls.name}' lacks a docstring.",
                    file_path=cls.file_path,
                    line_number=cls.start_line,
                    suggestion="Add a docstring describing the class's purpose and usage.",
                ))
    return findings


def detect_exception_swallowing(python_files_paths: list[str], repo_root: Path) -> list[RiskFinding]:
    """
    Detect bare 'except' or 'except Exception' blocks that silently swallow errors.

    This requires re-reading source files since the parser doesn't capture
    try/except structure in detail.
    """
    findings: list[RiskFinding] = []

    for file_path in python_files_paths:
        full_path = repo_root / file_path
        try:
            source = full_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            # Bare except: or except Exception:
            is_bare = node.type is None
            is_broad = (
                isinstance(node.type, ast.Name)
                and node.type.id in ("Exception", "BaseException")
            )

            if is_bare or is_broad:
                # Check if the handler body is just 'pass' or empty
                body_is_pass = (
                    len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)
                )
                if body_is_pass:
                    findings.append(RiskFinding(
                        category=RiskCategory.EXCEPTION_SWALLOWING,
                        severity=RiskSeverity.HIGH,
                        title="Exception swallowing",
                        description=(
                            "A bare 'except' or 'except Exception' block silently "
                            "swallows all errors with 'pass'. This hides bugs."
                        ),
                        file_path=file_path,
                        line_number=node.lineno,
                        suggestion="Log the exception or handle it explicitly. Never silently swallow errors.",
                    ))

    return findings


def run_ast_analysis(
    modules: list[ModuleInfo],
    python_file_paths: list[str],
    repo_root: Path,
) -> list[RiskFinding]:
    """
    Run all AST-based analysis checks on parsed modules.

    This is the main entry point for the AST analyzer.
    Aggregates findings from all individual detectors.

    Args:
        modules: Parsed module data from the parser.
        python_file_paths: Relative paths to Python files.
        repo_root: Repository root path.

    Returns:
        List of all risk findings.
    """
    logger.info("running_ast_analysis", module_count=len(modules))

    all_functions: list[FunctionInfo] = []
    all_classes: list[ClassInfo] = []
    for module in modules:
        all_functions.extend(module.functions)
        all_classes.extend(module.classes)

    findings: list[RiskFinding] = []
    findings.extend(detect_large_functions(all_functions))
    findings.extend(detect_high_complexity(all_functions))
    findings.extend(detect_too_many_parameters(all_functions))
    findings.extend(detect_god_classes(all_classes))
    findings.extend(detect_deep_inheritance(all_classes))
    findings.extend(detect_missing_docstrings(modules))
    findings.extend(detect_exception_swallowing(python_file_paths, repo_root))

    logger.info(
        "ast_analysis_complete",
        total_findings=len(findings),
        high_severity=sum(1 for f in findings if f.severity == RiskSeverity.HIGH),
        medium_severity=sum(1 for f in findings if f.severity == RiskSeverity.MEDIUM),
    )

    return findings
