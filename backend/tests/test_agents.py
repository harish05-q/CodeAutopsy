import tempfile
from pathlib import Path
import pytest
from backend.app.agents.repo_agent import RepoAgent
from backend.app.agents.ast_agent import AstAgent
from backend.app.agents.graph_agent import GraphAgent
from backend.app.services.risk_service import RiskService
from backend.app.agents.embedding_agent import EmbeddingAgent

# 1. Test Repository Agent URL Parsing
def test_repo_agent_url_parsing():
    agent = RepoAgent()
    owner, repo = agent.parse_github_url("https://github.com/acme/atlas-api.git")
    assert owner == "acme"
    assert repo == "atlas-api"

    owner, repo = agent.parse_github_url("https://github.com/fastapi/fastapi")
    assert owner == "fastapi"
    assert repo == "fastapi"

    with pytest.raises(ValueError):
        agent.parse_github_url("https://gitlab.com/invalid/repo")

# 2. Test AST Agent Parsing and Complexity Heuristics
def test_ast_agent_extraction(tmp_path):
    # Create a mock python file
    code = """
\"\"\"
Mock module docstring
\"\"\"
import os
from collections import defaultdict
import fastapi

@decorator1
@decorator2
class MockService(BaseService):
    def __init__(self, x: int):
        self.x = x

    def calculate(self, y: int) -> int:
        # Decision points: 1 (if), 1 (for) -> complexity = 3
        if y > 10:
            total = 0
            for i in range(y):
                total += i
            return total
        return y

def top_level_func(a, b):
    return a + b
"""
    file_path = tmp_path / "mock_module.py"
    file_path.write_text(code, encoding="utf-8")

    agent = AstAgent()
    module_data = agent.parse_file(file_path, "mock_module.py")

    assert module_data.docstring == "Mock module docstring"
    assert len(module_data.imports) == 3
    assert module_data.imports[0].names == ["os"]
    assert module_data.imports[1].module == "collections"

    # Verify Classes
    assert len(module_data.classes) == 1
    cls = module_data.classes[0]
    assert cls.name == "MockService"
    assert cls.bases == ["BaseService"]
    assert "decorator1" in cls.decorators

    # Verify Methods
    assert len(cls.methods) == 2
    init_method = next(m for m in cls.methods if m.name == "__init__")
    calc_method = next(m for m in cls.methods if m.name == "calculate")
    
    assert init_method.complexity == 1
    assert calc_method.complexity == 3 # Base 1 + 1 (if) + 1 (for)

    # Verify Functions
    assert len(module_data.functions) == 1
    assert module_data.functions[0].name == "top_level_func"

# 3. Test Graph Agent and NetworkX layouts
def test_graph_agent_construction():
    ast_mock = {
        "modules": {
            "app/main.py": {
                "imports": [
                    {"module": "app.services.auth", "names": [], "raw": "import app.services.auth"}
                ]
            },
            "app/services/auth.py": {
                "imports": []
            }
        },
        "symbols": [
            {
                "kind": "function",
                "name": "login",
                "qualified_name": "app.main.login",
                "file_path": "app/main.py",
                "start_line": 5,
                "end_line": 10,
                "decorators": [],
                "complexity": 1
            },
            {
                "kind": "function",
                "name": "verify_token",
                "qualified_name": "app.services.auth.verify_token",
                "file_path": "app/services/auth.py",
                "start_line": 3,
                "end_line": 8,
                "decorators": [],
                "complexity": 1
            }
        ]
    }
    
    agent = GraphAgent()
    # Mock checkout path
    python_files = ["app/main.py", "app/services/auth.py"]
    
    dep_graph = agent.build_dependency_graph(ast_mock, python_files)
    
    assert len(dep_graph["nodes"]) == 2
    assert len(dep_graph["edges"]) == 1
    assert dep_graph["edges"][0]["source"] == "app/main.py"
    assert dep_graph["edges"][0]["target"] == "app/services/auth.py"

# 4. Test Risk Service and Cycle Detections
def test_risk_service_smells():
    # Build a cycle: main -> service -> auth -> main
    dep_graph_mock = {
        "nodes": [{"id": "main.py"}, {"id": "service.py"}, {"id": "auth.py"}],
        "edges": [
            {"source": "main.py", "target": "service.py"},
            {"source": "service.py", "target": "auth.py"},
            {"source": "auth.py", "target": "main.py"}
        ]
    }
    
    # Mock AST containing a God class with 25 methods
    ast_mock = {
        "modules": {
            "main.py": {
                "loc": 120,
                "classes": [
                    {
                        "name": "GodClass",
                        "start_line": 10,
                        "end_line": 100,
                        "complexity": 40,
                        "methods": [{"name": f"method_{i}", "complexity": 1} for i in range(22)]
                    }
                ],
                "functions": []
            }
        }
    }

    service = RiskService()
    report = service.analyze("run_01", ast_mock, dep_graph_mock)

    # Check Circular Dependency findings
    cycle_findings = [f for f in report.findings if f.type == "Circular dependency"]
    assert len(cycle_findings) > 0
    
    # Check God Class findings
    god_class_findings = [f for f in report.findings if f.type == "God class"]
    assert len(god_class_findings) == 1

    # Score should be significantly deducted
    assert report.maintainability_score <= 80
