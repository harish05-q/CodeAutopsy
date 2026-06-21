import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import networkx as nx
from pydantic import BaseModel

class GraphNodeDto(BaseModel):
    id: str
    type: str = "module"
    position: Dict[str, float]
    data: Dict[str, Any]

class GraphEdgeDto(BaseModel):
    id: str
    source: str
    target: str
    animated: bool = False
    style: Dict[str, Any]
    markerEnd: Dict[str, Any]

class GraphDataDto(BaseModel):
    nodes: List[GraphNodeDto]
    edges: List[GraphEdgeDto]

class GraphAgent:
    def __init__(self):
        # Color palette: warm paper theme
        # Ember: #e85d3f, Mint: #8bd3bd, Acid: #d9ee68, Peach: #f4b183, Sand: #e6c5a8
        self.colors = ["#f4b183", "#d9ee68", "#8bd3bd", "#e6c5a8", "#e85d3f"]

    def _get_color(self, index: int) -> str:
        return self.colors[index % len(self.colors)]

    def _layout_nodes_networkx(self, G: nx.DiGraph) -> Dict[str, Tuple[float, float]]:
        """Compute 2D positions for React Flow using NetworkX spring layout."""
        if not G.nodes:
            return {}
        
        # Calculate spring layout
        pos = nx.spring_layout(G, k=1.5 / math.sqrt(len(G.nodes)) if len(G.nodes) > 0 else 1.0, seed=42)
        
        # Scale to pixel coordinate space centered at (400, 300)
        scaled_pos = {}
        for node_id, coords in pos.items():
            x = float(coords[0] * 320 + 400)
            y = float(coords[1] * 220 + 260)
            scaled_pos[node_id] = (x, y)
        return scaled_pos

    def _resolve_import_to_module(self, import_module: str, current_file: str, all_files: List[str]) -> str:
        """
        Tries to resolve an imported module (e.g. app.services.auth)
        to a concrete file path in the workspace (e.g. app/services/auth.py).
        """
        if not import_module:
            return ""
        
        # Convert dotted notation to path slash notation
        import_path = import_module.replace(".", "/")
        
        candidates = [
            f"{import_path}.py",
            f"{import_path}/__init__.py"
        ]
        
        # Check direct candidates
        for cand in candidates:
            if cand in all_files:
                return cand
            
        # Check relative candidate from current_file directory
        current_dir = Path(current_file).parent.as_posix()
        for cand in candidates:
            rel_cand = f"{current_dir}/{cand}".replace("//", "/")
            if rel_cand in all_files:
                return rel_cand
                
        # Look for partial matches in all files
        for f in all_files:
            if f.endswith(f"/{import_path}.py") or f == f"{import_path}.py":
                return f
                
        return ""

    def build_dependency_graph(self, ast_data: Dict[str, Any], python_files: List[str]) -> Dict[str, Any]:
        """
        Builds a module-level import dependency graph.
        Returns React Flow compatible format.
        """
        G = nx.DiGraph()
        
        # Add all modules as nodes
        for idx, file_path in enumerate(python_files):
            # Classify kind based on directory
            kind = "core"
            parts = file_path.split("/")
            if len(parts) > 1:
                kind = parts[0]
            if file_path.endswith("__init__.py"):
                kind = "package"
            
            G.add_node(file_path, label=file_path, kind=kind, color=self._get_color(idx))

        # Add edges from imports
        for file_path, module_info in ast_data.get("modules", {}).items():
            for imp in module_info.get("imports", []):
                target_module = imp.get("module")
                resolved = self._resolve_import_to_module(target_module, file_path, python_files)
                if resolved and resolved != file_path:
                    G.add_edge(file_path, resolved)
                
                # Also check direct names (for from-imports or alias imports)
                for name in imp.get("names", []):
                    resolved_name = self._resolve_import_to_module(name, file_path, python_files)
                    if resolved_name and resolved_name != file_path:
                        G.add_edge(file_path, resolved_name)

        # Layout
        positions = self._layout_nodes_networkx(G)
        
        # Structure into React Flow
        nodes = []
        for node_id in G.nodes:
            data = G.nodes[node_id]
            x, y = positions.get(node_id, (400, 300))
            nodes.append(GraphNodeDto(
                id=node_id,
                type="module",
                position={"x": x, "y": y},
                data={
                    "label": data["label"],
                    "kind": data["kind"],
                    "files": 1, # relative size metric
                    "tone": data["color"]
                }
            ))

        edges = []
        for i, (u, v) in enumerate(G.edges):
            # First few connections can look highlighted/animated in UI
            animated = i < 5
            edges.append(GraphEdgeDto(
                id=f"e_dep_{i}",
                source=u,
                target=v,
                animated=animated,
                style={"stroke": "#e85d3f" if animated else "#5f685e", "strokeWidth": 2 if animated else 1.4},
                markerEnd={"type": "arrowclosed", "color": "#e85d3f" if animated else "#5f685e"}
            ))

        return {"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]}

    def build_call_graph(self, ast_data: Dict[str, Any], checkout_path: Path) -> Dict[str, Any]:
        """
        Builds an approximate function/method call graph.
        Returns React Flow compatible format.
        """
        G = nx.DiGraph()
        
        # 1. Compile list of all defined functions/methods
        # mapped by their simple name to list of full qualified names
        name_to_qnames: Dict[str, List[str]] = {}
        qname_to_info: Dict[str, Dict[str, Any]] = {}
        
        # We also want to map class names to their methods
        class_to_methods: Dict[str, List[str]] = {}

        for symbol in ast_data.get("symbols", []):
            kind = symbol["kind"]
            name = symbol["name"]
            qname = symbol["qualified_name"]
            
            qname_to_info[qname] = symbol
            
            if name not in name_to_qnames:
                name_to_qnames[name] = []
            name_to_qnames[name].append(qname)
            
            if kind == "method":
                # Find class parent from qualified_name: e.g. module.Class.method -> Class
                parts = qname.split(".")
                if len(parts) >= 3:
                    class_name = parts[-2]
                    if class_name not in class_to_methods:
                        class_to_methods[class_name] = []
                    class_to_methods[class_name].append(qname)

        # Add all defined function/method symbols as nodes in the call graph
        for idx, (qname, info) in enumerate(qname_to_info.items()):
            if info["kind"] in ("function", "method"):
                # We classify color/kind
                G.add_node(qname, label=info["name"] + "()", kind=info["kind"], color=self._get_color(idx))

        # 2. Extract call references inside each function/method body
        # We read the file content and do a simple string/regex analysis on the lines of the function.
        # This is fast, robust, and handles cases tree-sitter might miss in complex code.
        for qname, info in list(qname_to_info.items()):
            if info["kind"] not in ("function", "method"):
                continue
                
            file_path = checkout_path / info["file_path"]
            if not file_path.exists():
                continue
                
            try:
                # Read the lines of this function/method
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    
                # line index is 0-based, start_line/end_line are 1-based
                start = max(0, info["start_line"] - 1)
                end = min(len(lines), info["end_line"])
                func_body = "".join(lines[start:end])
                
                # Simple approximation: find names followed by '('
                # e.g. verify_token(args)
                calls = re.findall(r"([a-zA-Z0-9_]+)\s*\(", func_body)
                
                for call_name in calls:
                    # Ignore python builtins
                    if call_name in ("str", "int", "dict", "list", "set", "super", "print", "len", "sum", "range", "min", "max", "enumerate", "isinstance", "getattr", "setattr"):
                        continue
                        
                    # Find candidate symbols matching call_name
                    candidates = name_to_qnames.get(call_name, [])
                    for cand in candidates:
                        # Add a call edge if it maps to a function/method
                        if qname_to_info[cand]["kind"] in ("function", "method") and cand != qname:
                            # Heuristic validation:
                            # 1. If it's a method on a class: did we use "self." or instantiate the class?
                            # 2. If it's in the same file: highly likely.
                            # 3. If it is imported in the file: highly likely.
                            # Since it's an approximate call graph, we link it.
                            G.add_edge(qname, cand)
            except Exception as e:
                print(f"Error building calls for {qname}: {e}")

        # Layout
        positions = self._layout_nodes_networkx(G)
        
        # Structure into React Flow format
        nodes = []
        for node_id in G.nodes:
            data = G.nodes[node_id]
            x, y = positions.get(node_id, (400, 300))
            nodes.append(GraphNodeDto(
                id=node_id,
                type="module", # Use 'module' node type to share styling
                position={"x": x, "y": y},
                data={
                    "label": data["label"],
                    "kind": data["kind"],
                    "files": 1,
                    "tone": data["color"]
                }
            ))

        edges = []
        for i, (u, v) in enumerate(G.edges):
            animated = i < 4
            edges.append(GraphEdgeDto(
                id=f"e_call_{i}",
                source=u,
                target=v,
                animated=animated,
                style={"stroke": "#e85d3f" if animated else "#5f685e", "strokeWidth": 2 if animated else 1.4},
                markerEnd={"type": "arrowclosed", "color": "#e85d3f" if animated else "#5f685e"}
            ))

        return {"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]}

    def run(self, ast_data: Dict[str, Any], checkout_path: Path, python_files: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Runs the Graph Agent and yields dependency and call graphs."""
        dep_graph = self.build_dependency_graph(ast_data, python_files)
        call_graph = self.build_call_graph(ast_data, checkout_path)
        return dep_graph, call_graph

