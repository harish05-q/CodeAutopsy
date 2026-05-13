"""
Call graph builder — builds function-level call relationships.

Takes parsed function data (each function knows which functions it calls)
and constructs a directed graph where nodes are functions/methods and
edges represent call relationships.

Design decisions:
- Pure function: parsed data in → GraphData out. No I/O.
- Resolves call targets to qualified function names where possible.
- Handles method calls (self.method), module-level calls, and built-in calls.
- Distinguishes internal calls (within repo) from external calls.
- Does NOT use LLMs — entirely deterministic.
"""

from backend.core.logger import get_logger
from backend.models.schemas import (
    FunctionInfo,
    GraphData,
    GraphEdge,
    GraphNode,
    ModuleInfo,
)

logger = get_logger(__name__)


def _build_function_lookup(
    modules: list[ModuleInfo],
) -> dict[str, FunctionInfo]:
    """
    Build a lookup table from function name → FunctionInfo.

    Creates entries for:
    - qualified_name (module.class.func)
    - short name (func) — used as fallback for unresolved calls

    Returns:
        Dict mapping various name forms to FunctionInfo.
    """
    lookup: dict[str, FunctionInfo] = {}
    for module in modules:
        for func in module.functions:
            if func.qualified_name:
                lookup[func.qualified_name] = func
            # Also index by short name for fallback resolution
            # (may collide, but that's okay — best-effort)
            if func.name not in lookup:
                lookup[func.name] = func
    return lookup


def _resolve_call_target(
    call_name: str,
    caller_module: str,
    function_lookup: dict[str, FunctionInfo],
    known_functions: set[str],
) -> str | None:
    """
    Attempt to resolve a call target to a qualified function name.

    Resolution order:
    1. Try the call name as-is (already qualified)
    2. Try qualifying with the caller's module
    3. Try the short name against known functions
    4. Return None if unresolvable (external or built-in call)

    Args:
        call_name: The raw call target from AST (e.g., "foo", "self.bar", "os.path.join")
        caller_module: The module where the call occurs.
        function_lookup: Name → FunctionInfo mapping.
        known_functions: Set of all known qualified function names.

    Returns:
        Resolved qualified name, or None if external/built-in.
    """
    # Skip self/cls method calls — try to resolve the method name
    if call_name.startswith("self.") or call_name.startswith("cls."):
        method_name = call_name.split(".", 1)[1]
        # Try to find this method in the caller's module
        qualified = f"{caller_module}.{method_name}"
        # Check if any known function ends with this pattern
        for known in known_functions:
            if known.endswith(f".{method_name}"):
                return known
        return None

    # 1. Try as-is
    if call_name in known_functions:
        return call_name

    # 2. Try qualifying with caller module
    qualified = f"{caller_module}.{call_name}"
    if qualified in known_functions:
        return qualified

    # 3. Try short name lookup
    if call_name in function_lookup and function_lookup[call_name].qualified_name in known_functions:
        return function_lookup[call_name].qualified_name

    # 4. Unresolvable — likely external or built-in
    return None


def build_call_graph(
    modules: list[ModuleInfo],
    include_external: bool = False,
) -> GraphData:
    """
    Build a function-level call graph from parsed module data.

    Each node is a function or method.
    Each directed edge represents a function call: caller → callee.

    Args:
        modules: List of parsed module data with function call information.
        include_external: If True, include nodes for external/unresolved calls.

    Returns:
        GraphData with nodes and edges for the call graph.
    """
    logger.info("building_call_graph", module_count=len(modules))

    # Build lookup structures
    function_lookup = _build_function_lookup(modules)
    known_functions: set[str] = set()
    for module in modules:
        for func in module.functions:
            if func.qualified_name:
                known_functions.add(func.qualified_name)

    # Build nodes — one per function
    nodes: list[GraphNode] = []
    node_ids: set[str] = set()

    for module in modules:
        for func in module.functions:
            if not func.qualified_name or func.qualified_name in node_ids:
                continue
            node_ids.add(func.qualified_name)

            node_type = "method" if func.is_method else "function"
            if func.is_async:
                node_type = f"async_{node_type}"

            nodes.append(GraphNode(
                id=func.qualified_name,
                label=func.name,
                type=node_type,
                metadata={
                    "file_path": func.file_path,
                    "start_line": func.start_line,
                    "line_count": func.line_count,
                    "complexity": func.complexity,
                    "parameters": len(func.parameters),
                },
            ))

    # Build edges — one per call relationship
    edges: list[GraphEdge] = []
    edge_set: set[tuple[str, str]] = set()
    resolved_count = 0
    unresolved_count = 0

    for module in modules:
        for func in module.functions:
            if not func.qualified_name:
                continue

            caller = func.qualified_name

            for call_name in func.calls:
                target = _resolve_call_target(
                    call_name,
                    module.module_name,
                    function_lookup,
                    known_functions,
                )

                if target is None:
                    unresolved_count += 1
                    if include_external:
                        # Add external node
                        ext_id = f"external::{call_name}"
                        if ext_id not in node_ids:
                            node_ids.add(ext_id)
                            nodes.append(GraphNode(
                                id=ext_id,
                                label=call_name,
                                type="external",
                                metadata={},
                            ))
                        edge_key = (caller, ext_id)
                        if edge_key not in edge_set:
                            edge_set.add(edge_key)
                            edges.append(GraphEdge(
                                source=caller,
                                target=ext_id,
                                relationship="calls_external",
                                weight=0.5,
                            ))
                    continue

                resolved_count += 1

                # Skip self-calls
                if target == caller:
                    continue

                edge_key = (caller, target)
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append(GraphEdge(
                        source=caller,
                        target=target,
                        relationship="calls",
                        weight=1.0,
                    ))

    logger.info(
        "call_graph_built",
        nodes=len(nodes),
        edges=len(edges),
        resolved_calls=resolved_count,
        unresolved_calls=unresolved_count,
    )

    return GraphData(
        graph_type="call_graph",
        nodes=nodes,
        edges=edges,
        metadata={
            "total_functions": len(known_functions),
            "resolved_calls": resolved_count,
            "unresolved_calls": unresolved_count,
        },
    )
