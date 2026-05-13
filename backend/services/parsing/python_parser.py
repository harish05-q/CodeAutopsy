"""
Python AST parser using the stdlib ast module.

Extracts functions, classes, imports, decorators, docstrings, and call relationships
from Python source files using Python's built-in AST parser.

Design decisions:
- Uses stdlib ast (not tree-sitter) for Python because ast module produces
  a richer, more Pythonic AST for Python specifically.
- Tree-sitter is reserved for multi-language support in future phases.
- Pure functions: file in → structured data out. No side effects.
- Every extraction function is independently testable.
- Parse errors are caught and reported, never crash the pipeline.
"""

import ast
from pathlib import Path

from backend.core.logger import get_logger
from backend.models.schemas import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    ModuleInfo,
    ParseResult,
)

logger = get_logger(__name__)


def _get_docstring(node: ast.AST) -> str | None:
    """Extract docstring from an AST node (function, class, or module)."""
    try:
        return ast.get_docstring(node)
    except TypeError:
        return None


def _get_decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """Extract decorator names from a function or class definition."""
    decorators: list[str] = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(ast.unparse(dec))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(ast.unparse(dec.func))
    return decorators


def _get_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Extract return type annotation as a string."""
    if node.returns is not None:
        try:
            return ast.unparse(node.returns)
        except Exception:
            return None
    return None


def _get_parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract parameter names from a function definition."""
    params: list[str] = []
    for arg in node.args.args:
        params.append(arg.arg)
    for arg in node.args.kwonlyargs:
        params.append(arg.arg)
    if node.args.vararg:
        params.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        params.append(f"**{node.args.kwarg.arg}")
    return params


def _extract_calls(node: ast.AST) -> list[str]:
    """
    Extract all function/method calls within an AST node.

    Walks the subtree and collects call target names.
    """
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                try:
                    calls.append(ast.unparse(child.func))
                except Exception:
                    calls.append(child.func.attr)
    return calls


def _calculate_complexity(node: ast.AST) -> int:
    """
    Calculate cyclomatic complexity of a function.

    Counts decision points: if, elif, for, while, except, with,
    boolean operators (and, or), assert, comprehensions.

    Starts at 1 (the function itself is one path).
    """
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            complexity += 1
        elif isinstance(child, (ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, (ast.While,)):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, (ast.With, ast.AsyncWith)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # Each 'and'/'or' adds a branch
            complexity += len(child.values) - 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            complexity += 1
    return complexity


def extract_functions(
    tree: ast.Module,
    file_path: str,
    module_name: str = "",
) -> list[FunctionInfo]:
    """
    Extract all top-level and nested function definitions.

    Args:
        tree: Parsed AST module.
        file_path: Source file path (for context in output).
        module_name: Dotted module name.

    Returns:
        List of FunctionInfo with full metadata.
    """
    functions: list[FunctionInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Determine if this is a method (defined inside a class)
        is_method = False
        class_name = ""
        # Check parent context by walking tree structure
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in ast.iter_child_nodes(parent):
                    if child is node:
                        is_method = True
                        class_name = parent.name
                        break

        qualified = f"{module_name}.{class_name}.{node.name}" if class_name else f"{module_name}.{node.name}"

        func_info = FunctionInfo(
            name=node.name,
            qualified_name=qualified.strip("."),
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            line_count=(node.end_lineno or node.lineno) - node.lineno + 1,
            parameters=_get_parameter_names(node),
            return_type=_get_return_type(node),
            decorators=_get_decorator_names(node),
            docstring=_get_docstring(node),
            is_method=is_method,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            calls=_extract_calls(node),
            complexity=_calculate_complexity(node),
        )
        functions.append(func_info)

    return functions


def extract_classes(
    tree: ast.Module,
    file_path: str,
    module_name: str = "",
) -> list[ClassInfo]:
    """
    Extract all class definitions with their metadata.

    Args:
        tree: Parsed AST module.
        file_path: Source file path.
        module_name: Dotted module name.

    Returns:
        List of ClassInfo with bases, methods, attributes.
    """
    classes: list[ClassInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Extract base class names
        bases: list[str] = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("?")

        # Extract method names
        methods = [
            n.name for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Extract class-level attribute assignments
        attributes: list[str] = []
        for n in node.body:
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                attributes.append(n.target.id)
            elif isinstance(n, ast.Assign):
                for target in n.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        qualified = f"{module_name}.{node.name}".strip(".")

        class_info = ClassInfo(
            name=node.name,
            qualified_name=qualified,
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            line_count=(node.end_lineno or node.lineno) - node.lineno + 1,
            bases=bases,
            decorators=_get_decorator_names(node),
            docstring=_get_docstring(node),
            methods=methods,
            attributes=attributes,
            method_count=len(methods),
        )
        classes.append(class_info)

    return classes


def extract_imports(tree: ast.Module, file_path: str) -> list[ImportInfo]:
    """
    Extract all import statements from a module.

    Handles both `import X` and `from X import Y` forms.
    """
    imports: list[ImportInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    module=alias.name,
                    names=[],
                    alias=alias.asname,
                    is_relative=False,
                    file_path=file_path,
                    line_number=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            names = [alias.name for alias in node.names]
            imports.append(ImportInfo(
                module=module_name,
                names=names,
                alias=None,
                is_relative=node.level > 0,
                file_path=file_path,
                line_number=node.lineno,
            ))

    return imports


def parse_python_file(file_info: FileInfo, repo_root: Path) -> ModuleInfo | None:
    """
    Parse a single Python file and extract all code structure.

    Args:
        file_info: Metadata about the file to parse.
        repo_root: Root of the repository (for computing module names).

    Returns:
        ModuleInfo with all extracted data, or None if parsing fails.
    """
    file_path = Path(file_info.absolute_path)

    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning("file_read_error", path=str(file_path), error=str(e))
        return None

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        logger.warning(
            "parse_syntax_error",
            path=file_info.path,
            line=e.lineno,
            msg=str(e.msg),
        )
        return None

    # Compute dotted module name from file path
    rel_path = Path(file_info.path)
    parts = list(rel_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    module_name = ".".join(parts)

    functions = extract_functions(tree, file_info.path, module_name)
    classes = extract_classes(tree, file_info.path, module_name)
    imports = extract_imports(tree, file_info.path)

    total_complexity = sum(f.complexity for f in functions) if functions else 0
    avg_complexity = total_complexity / len(functions) if functions else 0.0

    return ModuleInfo(
        file_path=file_info.path,
        module_name=module_name,
        functions=functions,
        classes=classes,
        imports=imports,
        docstring=_get_docstring(tree),
        line_count=file_info.line_count,
        total_functions=len(functions),
        total_classes=len(classes),
        complexity_score=avg_complexity,
    )


def parse_all_python_files(
    python_files: list[FileInfo],
    repo_root: Path,
) -> ParseResult:
    """
    Parse all Python files in the repository.

    Args:
        python_files: List of Python files to parse.
        repo_root: Root of the cloned repository.

    Returns:
        ParseResult with all modules and aggregate stats.
    """
    import time

    start = time.monotonic()
    modules: list[ModuleInfo] = []
    parse_errors: list[str] = []
    total_functions = 0
    total_classes = 0
    total_imports = 0

    logger.info("parsing_python_files", file_count=len(python_files))

    for file_info in python_files:
        module = parse_python_file(file_info, repo_root)
        if module is None:
            parse_errors.append(f"Failed to parse: {file_info.path}")
            continue

        modules.append(module)
        total_functions += module.total_functions
        total_classes += module.total_classes
        total_imports += len(module.imports)

    duration = time.monotonic() - start

    logger.info(
        "parsing_complete",
        modules=len(modules),
        functions=total_functions,
        classes=total_classes,
        imports=total_imports,
        errors=len(parse_errors),
        duration_seconds=round(duration, 3),
    )

    return ParseResult(
        modules=modules,
        total_functions=total_functions,
        total_classes=total_classes,
        total_imports=total_imports,
        parse_errors=parse_errors,
        duration_seconds=round(duration, 3),
    )
