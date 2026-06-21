from pathlib import Path
from typing import Any, Dict, List, Tuple
import networkx as nx
from pydantic import BaseModel
from backend.app.domain.utils import generate_ulid

class RiskFinding(BaseModel):
    type: str
    location: str
    advice: str
    risk: str # High, Medium, Low
    file_path: str
    line: int = None

class Hotspot(BaseModel):
    file: str
    risk: str
    score: int
    color: str

class RiskReport(BaseModel):
    maintainability_score: int
    avg_complexity: float
    findings: List[RiskFinding]
    hotspots: List[Hotspot]

class RiskService:
    def __init__(self, coupling_threshold: int = 8):
        self.coupling_threshold = coupling_threshold

    def analyze(self, run_id: str, ast_data: Dict[str, Any], dep_graph_data: Dict[str, Any]) -> RiskReport:
        """
        Analyzes code quality metrics, detects smells, builds hotspots, 
        and calculates maintainability score.
        """
        findings = []
        hotspots = []
        
        # 1. God Classes and Large Files check from AST
        total_complexity = 0
        total_functions = 0
        
        # Keep track of file risk scores to rank hotspots
        file_risk_scores: Dict[str, float] = {}

        for file_path, module in ast_data.get("modules", {}).items():
            # Calculate total complexity and LOC for file
            file_loc = module.get("loc", 0)
            
            # Count LOC manually if not present
            if file_loc == 0:
                # Approximate LOC based on symbols and max ranges
                all_ranges = []
                for cls in module.get("classes", []):
                    all_ranges.append(cls.get("end_line", 0))
                for f in module.get("functions", []):
                    all_ranges.append(f.get("end_line", 0))
                file_loc = max(all_ranges) if all_ranges else 10

            file_risk_score = 0.0

            # Large file check
            if file_loc > 500:
                advice = f"Split this module into smaller logical files or classes. Current size is {file_loc} lines."
                findings.append(RiskFinding(
                    type="Large file",
                    location=f"{file_path} · {file_loc} LOC",
                    advice=advice,
                    risk="Medium",
                    file_path=file_path
                ))
                file_risk_score += 30.0

            # God class check
            for cls in module.get("classes", []):
                methods = cls.get("methods", [])
                method_count = len(methods)
                
                # Update complexity counters
                for m in methods:
                    total_complexity += m.get("complexity", 1)
                    total_functions += 1
                
                cls_complexity = cls.get("complexity", 1)
                
                if method_count > 20:
                    advice = f"Extract methods into separate helper classes or utility modules. Found {method_count} methods."
                    findings.append(RiskFinding(
                        type="God class",
                        location=f"{cls.get('name')} in {file_path} · {method_count} methods",
                        advice=advice,
                        risk="High",
                        file_path=file_path,
                        line=cls.get("start_line")
                    ))
                    file_risk_score += 50.0

            for f in module.get("functions", []):
                total_complexity += f.get("complexity", 1)
                total_functions += 1

            # Accumulate a base score for file LOC
            file_risk_score += min(40.0, (file_loc / 100.0) * 8)
            file_risk_scores[file_path] = file_risk_score

        # 2. Circular dependency check
        # We can build a NetworkX graph from the dependency nodes and edges
        G = nx.DiGraph()
        for node in dep_graph_data.get("nodes", []):
            G.add_node(node["id"])
        for edge in dep_graph_data.get("edges", []):
            G.add_edge(edge["source"], edge["target"])

        # Detect cycles
        cycles = list(nx.simple_cycles(G))
        for cycle in cycles:
            if len(cycle) >= 2:
                cycle_str = " ↔ ".join(cycle[:3])
                if len(cycle) > 3:
                    cycle_str += "..."
                findings.append(RiskFinding(
                    type="Circular dependency",
                    location=cycle_str,
                    advice="Break the cycle by extracting shared types, helper functions, or constants to a separate leaf module.",
                    risk="High",
                    file_path=cycle[0]
                ))
                # Add risk penalty to all files in the cycle
                for f in cycle:
                    if f in file_risk_scores:
                        file_risk_scores[f] = file_risk_scores.get(f, 0.0) + 40.0

        # 3. High Coupling Check
        for node in G.nodes:
            in_deg = G.in_degree(node)
            out_deg = G.out_degree(node)
            total_coupling = in_deg + out_deg
            if total_coupling > self.coupling_threshold:
                advice = f"Simplify dependencies. This module interacts with {total_coupling} other modules."
                findings.append(RiskFinding(
                    type="High coupling",
                    location=f"{node} · {total_coupling} links",
                    advice=advice,
                    risk="Medium",
                    file_path=node
                ))
                file_risk_scores[node] = file_risk_scores.get(node, 0.0) + 20.0

        # Calculate Average Complexity
        avg_complexity = float(total_complexity / max(1, total_functions))

        # Rank and compile hotspots
        # Filter out files that have very low scores, sort by risk score desc
        ranked_files = sorted(file_risk_scores.items(), key=lambda x: x[1], reverse=True)
        for file_path, score in ranked_files[:5]:
            norm_score = min(99, int(score + 10))
            if norm_score > 30:
                risk_lvl = "High" if norm_score > 70 else "Medium"
                color = "#e85d3f" if risk_lvl == "High" else "#ed9d58" if norm_score > 50 else "#d8bc4c"
                hotspots.append(Hotspot(
                    file=file_path,
                    risk=risk_lvl,
                    score=norm_score,
                    color=color
                ))

        # 4. Calculate Maintainability Score
        # Start at 100
        maintainability = 100
        # Deduct based on findings
        for f in findings:
            if f.risk == "High":
                maintainability -= 10
            elif f.risk == "Medium":
                maintainability -= 5
            else:
                maintainability -= 2
        
        # Bound score between 10 and 100
        maintainability = max(10, min(100, maintainability))

        return RiskReport(
            maintainability_score=maintainability,
            avg_complexity=round(avg_complexity, 1),
            findings=findings,
            hotspots=hotspots
        )
