"""
Graph analysis service — NetworkX-powered graph intelligence.

Takes GraphData (from dependency/call graph builders) and performs
structural analysis: cycle detection, centrality, coupling, orphans, etc.

This is the analytical backbone of CodeAutopsy's architecture inference.
All operations are deterministic — no LLM involvement.

Design decisions:
- Converts GraphData ↔ NetworkX DiGraph for analysis.
- Each analysis function is independent and testable.
- Results are returned as structured data (Pydantic models / dicts).
- Caches nothing — pure functions, call as needed.
"""

import networkx as nx

from backend.core.constants import RiskCategory, RiskSeverity
from backend.core.logger import get_logger
from backend.models.schemas import GraphData, RiskFinding

logger = get_logger(__name__)


def to_networkx(graph_data: GraphData) -> nx.DiGraph:
    """
    Convert a GraphData model to a NetworkX directed graph.

    Preserves all node/edge metadata as graph attributes.
    """
    G = nx.DiGraph()

    for node in graph_data.nodes:
        G.add_node(
            node.id,
            label=node.label,
            type=node.type,
            **node.metadata,
        )

    for edge in graph_data.edges:
        G.add_edge(
            edge.source,
            edge.target,
            relationship=edge.relationship,
            weight=edge.weight,
        )

    return G


def from_networkx(G: nx.DiGraph, graph_type: str) -> GraphData:
    """Convert a NetworkX graph back to GraphData for serialization."""
    from backend.models.schemas import GraphEdge, GraphNode

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        label = attrs.pop("label", str(node_id))
        node_type = attrs.pop("type", "unknown")
        nodes.append(GraphNode(
            id=str(node_id),
            label=label,
            type=node_type,
            metadata={k: v for k, v in attrs.items() if isinstance(v, (str, int, float))},
        ))

    edges = []
    for src, tgt, attrs in G.edges(data=True):
        edges.append(GraphEdge(
            source=str(src),
            target=str(tgt),
            relationship=attrs.get("relationship", "unknown"),
            weight=attrs.get("weight", 1.0),
        ))

    return GraphData(graph_type=graph_type, nodes=nodes, edges=edges)


# ── Cycle Detection ──────────────────────────────────────────


def find_cycles(graph_data: GraphData) -> list[list[str]]:
    """
    Find all simple cycles in the graph.

    Cycles in dependency graphs indicate circular dependencies.
    Cycles in call graphs may indicate recursion (which can be intentional).

    Returns:
        List of cycles, where each cycle is a list of node IDs.
    """
    G = to_networkx(graph_data)
    cycles = list(nx.simple_cycles(G))

    logger.info(
        "cycles_detected",
        graph_type=graph_data.graph_type,
        cycle_count=len(cycles),
    )

    return cycles


# ── Centrality Analysis ──────────────────────────────────────


def compute_centrality(graph_data: GraphData) -> dict[str, dict[str, float]]:
    """
    Compute multiple centrality metrics for all nodes.

    Metrics:
    - in_degree: How many nodes depend on this node (importance).
    - out_degree: How many nodes this node depends on (coupling).
    - betweenness: How often this node sits on shortest paths (bottleneck risk).
    - pagerank: Recursive importance score.

    Returns:
        Dict mapping node_id → {metric_name: score}.
    """
    G = to_networkx(graph_data)

    if G.number_of_nodes() == 0:
        return {}

    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())

    # Betweenness can be expensive on large graphs, cap at 500 nodes
    if G.number_of_nodes() <= 500:
        betweenness = nx.betweenness_centrality(G)
    else:
        betweenness = {n: 0.0 for n in G.nodes()}
        logger.info("skipping_betweenness", reason="graph_too_large", nodes=G.number_of_nodes())

    try:
        pagerank = nx.pagerank(G, max_iter=100)
    except nx.PowerIterationFailedConvergence:
        pagerank = {n: 0.0 for n in G.nodes()}

    result: dict[str, dict[str, float]] = {}
    for node in G.nodes():
        result[node] = {
            "in_degree": float(in_deg.get(node, 0)),
            "out_degree": float(out_deg.get(node, 0)),
            "betweenness": round(betweenness.get(node, 0.0), 4),
            "pagerank": round(pagerank.get(node, 0.0), 6),
        }

    return result


# ── Fan-In / Fan-Out Analysis ────────────────────────────────


def compute_fan_in_fan_out(graph_data: GraphData) -> dict[str, dict[str, int]]:
    """
    Compute fan-in (incoming edges) and fan-out (outgoing edges) for each node.

    High fan-in = many dependents (important, risky to change).
    High fan-out = depends on many things (fragile, high coupling).

    Returns:
        Dict mapping node_id → {"fan_in": N, "fan_out": M}.
    """
    G = to_networkx(graph_data)
    result: dict[str, dict[str, int]] = {}

    for node in G.nodes():
        result[node] = {
            "fan_in": G.in_degree(node),
            "fan_out": G.out_degree(node),
        }

    return result


# ── Orphan Detection ─────────────────────────────────────────


def find_orphan_modules(graph_data: GraphData) -> list[str]:
    """
    Find orphan nodes — modules with no incoming or outgoing edges.

    Orphans may indicate:
    - Dead code
    - Entry points (intended)
    - Misconfigured imports

    Returns:
        List of orphan node IDs.
    """
    G = to_networkx(graph_data)
    orphans = [
        node for node in G.nodes()
        if G.in_degree(node) == 0 and G.out_degree(node) == 0
    ]

    logger.info("orphans_detected", count=len(orphans))
    return orphans


# ── Coupling Analysis ────────────────────────────────────────


def find_tightly_coupled_modules(
    graph_data: GraphData,
    threshold: int = 3,
) -> list[dict[str, str | int]]:
    """
    Find pairs of modules with bidirectional high coupling.

    Two modules are tightly coupled if they both import each other
    or have many mutual dependencies.

    Args:
        graph_data: The dependency or call graph.
        threshold: Minimum combined edge weight to flag.

    Returns:
        List of coupling entries: {module_a, module_b, mutual_edges}.
    """
    G = to_networkx(graph_data)
    coupled_pairs: list[dict[str, str | int]] = []
    seen: set[frozenset[str]] = set()

    for u, v in G.edges():
        if G.has_edge(v, u):
            pair = frozenset({u, v})
            if pair not in seen:
                seen.add(pair)
                coupled_pairs.append({
                    "module_a": u,
                    "module_b": v,
                    "mutual_edges": 2,
                })

    logger.info("tight_coupling_detected", pairs=len(coupled_pairs))
    return coupled_pairs


# ── Connected Components ─────────────────────────────────────


def find_components(graph_data: GraphData) -> list[list[str]]:
    """
    Find weakly connected components in the graph.

    Multiple components suggest independent subsystems or disconnected code.

    Returns:
        List of components, each a list of node IDs, sorted by size (largest first).
    """
    G = to_networkx(graph_data)
    components = sorted(
        nx.weakly_connected_components(G),
        key=len,
        reverse=True,
    )
    return [list(c) for c in components]


# ── Dead Code Candidates ─────────────────────────────────────


def find_dead_code_candidates(graph_data: GraphData) -> list[str]:
    """
    Find potential dead code — internal nodes with zero fan-in.

    In a call graph: functions never called by anything.
    In a dependency graph: modules never imported by anything.

    Excludes:
    - External nodes
    - Nodes that look like entry points (main, test_, etc.)

    Returns:
        List of node IDs that may be dead code.
    """
    G = to_networkx(graph_data)

    entry_point_prefixes = ("main", "test_", "conftest", "__main__", "setup", "app")

    candidates: list[str] = []
    for node in G.nodes():
        attrs = G.nodes[node]
        node_type = attrs.get("type", "")

        # Skip external nodes
        if node_type == "external":
            continue

        # Skip if has incoming edges
        if G.in_degree(node) > 0:
            continue

        # Skip likely entry points
        short_name = node.split(".")[-1]
        if any(short_name.startswith(p) for p in entry_point_prefixes):
            continue

        candidates.append(node)

    logger.info("dead_code_candidates", count=len(candidates))
    return candidates


# ── Full Graph Analysis ──────────────────────────────────────


def analyze_graph(graph_data: GraphData) -> dict:  # type: ignore[type-arg]
    """
    Run all graph analyses and return a comprehensive report.

    This is the main entry point — runs every analysis function
    and aggregates results into a single dict for artifact saving.

    Args:
        graph_data: The graph to analyze.

    Returns:
        Dict with all analysis results.
    """
    logger.info(
        "analyzing_graph",
        graph_type=graph_data.graph_type,
        nodes=len(graph_data.nodes),
        edges=len(graph_data.edges),
    )

    cycles = find_cycles(graph_data)
    centrality = compute_centrality(graph_data)
    fan_in_out = compute_fan_in_fan_out(graph_data)
    orphans = find_orphan_modules(graph_data)
    coupled = find_tightly_coupled_modules(graph_data)
    components = find_components(graph_data)
    dead_code = find_dead_code_candidates(graph_data)

    # Find the most "important" nodes (highest pagerank)
    top_nodes = sorted(
        centrality.items(),
        key=lambda x: x[1].get("pagerank", 0),
        reverse=True,
    )[:10]

    # Find highest fan-out (most coupled)
    high_fan_out = sorted(
        fan_in_out.items(),
        key=lambda x: x[1]["fan_out"],
        reverse=True,
    )[:10]

    report = {
        "graph_type": graph_data.graph_type,
        "summary": {
            "total_nodes": len(graph_data.nodes),
            "total_edges": len(graph_data.edges),
            "cycle_count": len(cycles),
            "orphan_count": len(orphans),
            "component_count": len(components),
            "dead_code_candidates": len(dead_code),
            "coupled_pairs": len(coupled),
        },
        "cycles": [cycle[:10] for cycle in cycles[:20]],  # Cap output
        "top_nodes_by_importance": [
            {"node": n, **metrics} for n, metrics in top_nodes
        ],
        "highest_fan_out": [
            {"node": n, **metrics} for n, metrics in high_fan_out
        ],
        "orphans": orphans[:50],
        "tightly_coupled": coupled[:20],
        "dead_code_candidates": dead_code[:50],
        "components": [c[:20] for c in components[:10]],
    }

    logger.info(
        "graph_analysis_complete",
        graph_type=graph_data.graph_type,
        cycles=len(cycles),
        orphans=len(orphans),
        dead_code=len(dead_code),
    )

    return report


def graph_risks_to_findings(
    analysis_report: dict,  # type: ignore[type-arg]
    graph_type: str,
) -> list[RiskFinding]:
    """
    Convert graph analysis results into RiskFinding objects.

    Translates structural issues (cycles, tight coupling, dead code)
    into the standard risk finding format used by the rest of the system.

    Args:
        analysis_report: Output from analyze_graph().
        graph_type: "dependency" or "call_graph".

    Returns:
        List of RiskFinding objects.
    """
    findings: list[RiskFinding] = []

    # Cyclic dependencies
    for cycle in analysis_report.get("cycles", []):
        findings.append(RiskFinding(
            category=RiskCategory.CYCLIC_DEPENDENCY,
            severity=RiskSeverity.HIGH,
            title=f"Cyclic dependency detected ({graph_type})",
            description=(
                f"A circular dependency was found involving {len(cycle)} modules: "
                f"{' → '.join(cycle[:5])}{'...' if len(cycle) > 5 else ''}"
            ),
            suggestion="Break the cycle by extracting shared logic into a separate module.",
            evidence={"cycle_length": len(cycle), "modules": ", ".join(cycle[:5])},
        ))

    # Tightly coupled pairs
    for pair in analysis_report.get("tightly_coupled", []):
        findings.append(RiskFinding(
            category=RiskCategory.TIGHT_COUPLING,
            severity=RiskSeverity.MEDIUM,
            title=f"Tight coupling: {pair['module_a']} ↔ {pair['module_b']}",
            description=(
                f"Modules '{pair['module_a']}' and '{pair['module_b']}' "
                "have bidirectional dependencies. Changes to one may break the other."
            ),
            suggestion="Consider introducing an interface or shared abstraction.",
        ))

    # Dead code
    for candidate in analysis_report.get("dead_code_candidates", [])[:10]:
        findings.append(RiskFinding(
            category=RiskCategory.DEAD_CODE,
            severity=RiskSeverity.LOW,
            title=f"Potential dead code: {candidate}",
            description=(
                f"'{candidate}' has no incoming references in the {graph_type}. "
                "It may be unused dead code."
            ),
            suggestion="Verify if this code is needed. If not, remove it to reduce maintenance burden.",
        ))

    return findings
