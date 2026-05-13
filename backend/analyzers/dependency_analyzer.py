"""
Dependency analyzer — builds the import/dependency graph.

Takes parsed module data (imports, file paths) and constructs a directed graph
where nodes are modules and edges represent import relationships.

Design decisions:
- Pure function: parsed data in → GraphData out. No I/O, no side effects.
- Resolves relative imports to absolute module names.
- Distinguishes internal (within-repo) vs external (third-party/stdlib) imports.
- Each edge carries metadata: import type, line number, specific names imported.
- Does NOT use LLMs — this is entirely deterministic.
"""

from backend.core.logger import get_logger
from backend.models.schemas import (
    GraphData,
    GraphEdge,
    GraphNode,
    ImportInfo,
    ModuleInfo,
)

logger = get_logger(__name__)


def _resolve_relative_import(
    importing_module: str,
    import_info: ImportInfo,
) -> str:
    """
    Resolve a relative import to an absolute module name.

    Example:
        importing_module = "pkg.sub.module"
        import_info.module = "utils"  (from .utils import X)
        → "pkg.sub.utils"

    Args:
        importing_module: The dotted name of the module doing the import.
        import_info: The import statement to resolve.

    Returns:
        The resolved absolute module name.
    """
    if not import_info.is_relative:
        return import_info.module

    # Split the importing module's path to get the package
    parts = importing_module.split(".")
    if parts:
        # For relative imports, go up one level (parent package)
        parent = ".".join(parts[:-1])
        if import_info.module:
            return f"{parent}.{import_info.module}" if parent else import_info.module
        return parent
    return import_info.module


def _is_internal_module(
    module_name: str,
    known_modules: set[str],
    top_level_packages: set[str],
) -> bool:
    """
    Determine if a module is internal to the repository.

    A module is internal if:
    - It exactly matches a known module in the repo, OR
    - Its top-level package matches a known top-level package.

    Args:
        module_name: Dotted module name to check.
        known_modules: Set of all known module names in the repo.
        top_level_packages: Set of top-level package names in the repo.

    Returns:
        True if the module is internal to the repo.
    """
    if module_name in known_modules:
        return True

    # Check if the top-level package matches
    top_level = module_name.split(".")[0]
    return top_level in top_level_packages


def build_dependency_graph(
    modules: list[ModuleInfo],
) -> GraphData:
    """
    Build a module-level dependency graph from parsed import data.

    Each node represents a Python module (file).
    Each edge represents an import relationship: source → target.

    The graph distinguishes:
    - internal edges: imports within the repository
    - external edges: imports of third-party or stdlib modules

    Args:
        modules: List of parsed module data.

    Returns:
        GraphData with nodes and edges for the dependency graph.
    """
    logger.info("building_dependency_graph", module_count=len(modules))

    # Build lookup structures
    known_modules: set[str] = {m.module_name for m in modules if m.module_name}
    top_level_packages: set[str] = set()
    for m in modules:
        if m.module_name:
            top_level = m.module_name.split(".")[0]
            if top_level:
                top_level_packages.add(top_level)

    # Build nodes — one per module
    nodes: list[GraphNode] = []
    node_ids: set[str] = set()

    for module in modules:
        if not module.module_name:
            continue
        node_id = module.module_name
        if node_id in node_ids:
            continue
        node_ids.add(node_id)

        nodes.append(GraphNode(
            id=node_id,
            label=module.module_name.split(".")[-1],  # Short name for display
            type="module",
            metadata={
                "file_path": module.file_path,
                "functions": module.total_functions,
                "classes": module.total_classes,
                "lines": module.line_count,
                "complexity": round(module.complexity_score, 2),
            },
        ))

    # Build edges — one per import relationship
    edges: list[GraphEdge] = []
    edge_set: set[tuple[str, str]] = set()  # Deduplicate edges

    internal_count = 0
    external_count = 0

    for module in modules:
        if not module.module_name:
            continue

        source = module.module_name

        for imp in module.imports:
            # Resolve the target module name
            target = _resolve_relative_import(source, imp)
            if not target:
                continue

            is_internal = _is_internal_module(target, known_modules, top_level_packages)

            # For external modules, add as a node if not present
            if not is_internal:
                external_count += 1
                if target not in node_ids:
                    node_ids.add(target)
                    nodes.append(GraphNode(
                        id=target,
                        label=target.split(".")[-1],
                        type="external",
                        metadata={"external": 1},
                    ))
            else:
                internal_count += 1

            # Add edge (deduplicated)
            edge_key = (source, target)
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                relationship = "imports_internal" if is_internal else "imports_external"
                names_str = ", ".join(imp.names[:5])  # Cap display names

                edges.append(GraphEdge(
                    source=source,
                    target=target,
                    relationship=relationship,
                    weight=1.0,
                ))

    logger.info(
        "dependency_graph_built",
        nodes=len(nodes),
        edges=len(edges),
        internal_imports=internal_count,
        external_imports=external_count,
    )

    return GraphData(
        graph_type="dependency",
        nodes=nodes,
        edges=edges,
        metadata={
            "total_modules": len(modules),
            "internal_edges": internal_count,
            "external_edges": external_count,
        },
    )
