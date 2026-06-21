import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from groq import Groq

logger = logging.getLogger(__name__)

class LayerDetail(BaseModel):
    name: str
    detail: str

class ArchitectureInference(BaseModel):
    pattern: str
    confidence: int
    reasoning: str
    layers: List[LayerDetail]
    evidence: List[str]
    alternative_pattern: str
    alternative_confidence: int
    alternative_reasoning: str
    mermaid_diagram: str

class ArchitectureAgent:
    def __init__(self, api_key: str = "", model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = Groq(api_key=api_key) if api_key else None

    def _get_rule_based_fallback(self, manifest: Dict[str, Any], python_files: List[str]) -> ArchitectureInference:
        """Rule-based architectural inference when Groq LLM is not available."""
        frameworks = manifest.get("frameworks", [])
        
        # Check folders in file list
        has_api = any("api/" in f or "routes/" in f or "views.py" in f for f in python_files)
        has_services = any("services/" in f or "logic/" in f for f in python_files)
        has_db = any("db/" in f or "models.py" in f or "schema.py" in f for f in python_files)
        has_agents = any("agents/" in f or "agent.py" in f for f in python_files)

        pattern = "Layered Monolith"
        confidence = 65
        reasoning = "Inferred through deterministic folder and module heuristics. Standard python project layout."
        layers = [
            LayerDetail(name="Interface", detail="Entrypoints and endpoints"),
            LayerDetail(name="Domain", detail="Core business logic and modules"),
            LayerDetail(name="Infrastructure", detail="Database models and storage configuration")
        ]
        evidence = ["Standard package imports", "Decoupled logic files"]
        
        if "FastAPI" in frameworks:
            pattern = "FastAPI Service"
            confidence = 80
            reasoning = "FastAPI architecture identified with clean routing interfaces and modular layout."
            layers = [
                LayerDetail(name="API Routing", detail="FastAPI APIRouter endpoint definitions"),
                LayerDetail(name="Domain Logic", detail="Service orchestration and handlers"),
                LayerDetail(name="Persistence", detail="Relational engines or file-system storages")
            ]
            evidence = ["FastAPI import statements found in source code files", "Modular file structure"]
            
        elif "Django" in frameworks:
            pattern = "Django MVC Monolith"
            confidence = 85
            reasoning = "Standard Django Model-View-Controller layout detected."
            layers = [
                LayerDetail(name="URL Router", detail="Django urls pattern matching"),
                LayerDetail(name="Views/Templates", detail="Rendering interfaces and serializers"),
                LayerDetail(name="Models", detail="Django ORM models mapping to DB tables")
            ]
            evidence = ["Django import statements", "Standard urls.py and models.py structure"]

        if has_agents:
            pattern = "Agentic Application Layer"
            confidence = 75
            reasoning = "Multi-agent structure layout inferred based on agents/ package directory."
            layers.insert(1, LayerDetail(name="Agentic Controllers", detail="Autonomous worker agents"))
            evidence.append("Folder directory containing agents/ packages present")

        mermaid = """graph TD
    API[API Interface / Endpoints] --> Services[Service Orchestration]
    Services --> DB[(Database / Persistence)]
    Services --> Agents[Agent Operations]
"""

        return ArchitectureInference(
            pattern=pattern,
            confidence=confidence,
            reasoning=reasoning,
            layers=layers,
            evidence=evidence,
            alternative_pattern="Clean Architecture",
            alternative_confidence=40,
            alternative_reasoning="Code shows attempts to isolate external resources but layers are coupled.",
            mermaid_diagram=mermaid
        )

    def run(self, manifest: Dict[str, Any], python_files: List[str], dependency_graph_nodes: List[Dict[str, Any]]) -> ArchitectureInference:
        """
        Runs the Architecture Agent using Groq or falling back to heuristics.
        """
        if not self.client:
            logger.warning("Groq API key not configured. Using rule-based fallback.")
            return self._get_rule_based_fallback(manifest, python_files)

        # Summarize repo structure for the LLM
        frameworks_str = ", ".join(manifest.get("frameworks", []))
        dependencies_str = ", ".join(manifest.get("dependencies", [])[:30])
        files_sample = "\n".join(python_files[:50])
        if len(python_files) > 50:
            files_sample += f"\n... and {len(python_files) - 50} more files"

        prompt = f"""You are a Staff-Level Software Architect. Analyze the structure and manifest details of a Python repository and infer its high-level architectural patterns.

Repository Manifest:
- Frameworks detected: {frameworks_str}
- Dependencies: {dependencies_str}
- Total files: {manifest.get("total_files")}
- Lines of code: {manifest.get("total_lines_of_code")}

Sample Python Files List:
{files_sample}

Identify:
1. The primary architecture pattern (e.g., MVC, Layered Monolith, Clean Architecture, Hexagonal, Monolith, Microservice).
2. Your confidence level (0 to 100).
3. The reasoning / diagnosis.
4. Discernible logical layers in the repository with details (up to 4 layers).
5. Bullet points of evidence supporting your diagnosis.
6. An alternative architectural pattern with confidence and reasoning.
7. A Mermaid flow diagram representing the folder dependency structure (graph TD format).

Respond ONLY as a valid JSON object matching this schema:
{{
  "pattern": "Layered Monolith",
  "confidence": 85,
  "reasoning": "Diagnosis explanation...",
  "layers": [
    {{ "name": "Layer Name", "detail": "Description of files/responsibilities..." }}
  ],
  "evidence": [
    "Evidence detail 1...",
    "Evidence detail 2..."
  ],
  "alternative_pattern": "MVC Monolith",
  "alternative_confidence": 45,
  "alternative_reasoning": "Reasoning...",
  "mermaid_diagram": "graph TD\\n  A[API] --> B[Service]\\n  B --> C[DB]"
}}
"""
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a professional software architecture inference bot. Return ONLY a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result_text = chat_completion.choices[0].message.content
            data = json.loads(result_text)
            return ArchitectureInference(**data)
            
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}. Falling back to heuristics.")
            return self._get_rule_based_fallback(manifest, python_files)
