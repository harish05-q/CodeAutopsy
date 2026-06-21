import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
from groq import Groq

logger = logging.getLogger(__name__)

class DocumentationAgent:
    def __init__(self, api_key: str = "", model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = Groq(api_key=api_key) if api_key else None

    def _generate_fallback_docs(self, manifest: Dict[str, Any], ast_data: Dict[str, Any]) -> Tuple[Dict[str, str], str, str]:
        """Generate static documentation fallback when Groq LLM is not configured."""
        repo_name = manifest.get("name", "Unknown Repository")
        owner = manifest.get("owner", "Unknown Owner")
        frameworks = ", ".join(manifest.get("frameworks", []))
        total_files = manifest.get("total_files", 0)
        total_loc = manifest.get("total_lines_of_code", 0)
        python_files = manifest.get("file_list", [])

        # 1. Module summaries
        summaries = {}
        for f in python_files:
            # Check AST module docstring
            module_ast = ast_data.get("modules", {}).get(f, {})
            doc = module_ast.get("docstring")
            if doc:
                summaries[f] = doc
            else:
                # Basic guess
                name = Path(f).stem
                summaries[f] = f"Module containing {name} logic, including classes and functions."

        # 2. Generated README
        readme = f"""# {repo_name} (AI-Generated Overview)

This repository is owned by **{owner}** and built using **{frameworks}**.
It contains **{total_files} files** comprising **{total_loc} lines of Python code**.

## Frameworks & Packages
- Core technologies: {frameworks}
- Dependencies: {", ".join(manifest.get("dependencies", [])[:15])}

## Quick Start
Analyze the folder structure below to locate the main entry point, typically `main.py` or similar execution scripts.
"""

        # 3. Onboarding Guide
        # Make a folder tree string representation
        folder_tree = {}
        for f in python_files:
            parts = f.split("/")
            curr = folder_tree
            for p in parts[:-1]:
                if p not in curr:
                    curr[p] = {}
                curr = curr[p]
            curr[parts[-1]] = "file"

        def format_tree(tree, indent=""):
            lines = []
            for k, v in tree.items():
                if v == "file":
                    lines.append(f"{indent}├── {k}")
                else:
                    lines.append(f"{indent}├── {k}/")
                    lines.extend(format_tree(v, indent + "│   "))
            return lines

        tree_lines = "\n".join(format_tree(folder_tree)[:40])
        if len(python_files) > 40:
            tree_lines += "\n..."

        # Find important files
        important_files = []
        for file in python_files:
            file_lower = file.lower()
            if "main.py" in file_lower or "app.py" in file_lower or "wsgi.py" in file_lower or "asgi.py" in file_lower:
                important_files.append((file, "Application Entry Point", "Start execution tracking here."))
            elif "config.py" in file_lower or "settings.py" in file_lower:
                important_files.append((file, "Configuration Settings", "Defines environment setup and parameter values."))
            elif "routes.py" in file_lower or "api/" in file_lower:
                important_files.append((file, "API Layer / Routing", "Lists REST endpoint URLs and request schemes."))

        if not important_files:
            # Fallback
            for file in python_files[:3]:
                important_files.append((file, "Source Module", "Core logical components."))

        important_files_md = "\n".join(f"- **[{Path(f).name}](file:///{f})** ({role}): {desc}" for f, role, desc in important_files)

        onboarding = f"""# Onboarding Guide - {repo_name}

## Project Purpose
To provide structured operations leveraging {frameworks}. Designed for modular utility and logic execution.

## Folder Structure
```text
{tree_lines}
```

## Core Components
- **HTTP Surface**: Routes and validation interfaces mapping HTTP inputs.
- **Business Domains**: Decoupled service packages executing specific functions.
- **Persistence Store**: Local SQLite database or file repository interfaces.

## Important Files
{important_files_md}

## Learning Path
1. Begin at the main entry point to understand system loading.
2. Read the configuration setup to view dependencies and API keys.
3. Walk the API endpoints to trace how Web/CLI inputs are channeled.
4. Explore the underlying database model/schema.

## Estimated Time to Understand
**2 hours** (Small codebase, modular structure).
"""

        return summaries, readme, onboarding

    def run(self, manifest: Dict[str, Any], ast_data: Dict[str, Any]) -> Tuple[Dict[str, str], str, str]:
        """
        Runs the Documentation Agent using Groq or falls back to template structures.
        Returns:
            - Module summaries mapping (dict)
            - Generated README (string)
            - Onboarding guide (string)
        """
        if not self.client:
            logger.warning("Groq API key not configured. Using fallback documentation generator.")
            return self._generate_fallback_docs(manifest, ast_data)

        repo_name = manifest.get("name", "Unknown Repository")
        frameworks_str = ", ".join(manifest.get("frameworks", []))
        
        # Compile class and function summaries for the LLM
        symbols_summary = []
        for file_path, module in ast_data.get("modules", {}).items():
            classes = [c.get("name") for c in module.get("classes", [])]
            funcs = [f.get("name") for f in module.get("functions", [])]
            symbols_summary.append(
                f"- File: {file_path}\n  Classes: {', '.join(classes) if classes else 'None'}\n  Functions: {', '.join(funcs) if funcs else 'None'}"
            )
        symbols_str = "\n".join(symbols_summary[:40]) # limit to avoid token context overflow

        # 1. Module summaries prompt
        modules_prompt = f"""You are a technical documenter. Review these modules and symbols in a repository named {repo_name}. Generate a 1-sentence description summarizing the responsibilities of each Python file.

Modules list:
{symbols_str}

Return ONLY a JSON dictionary where the keys are file paths and values are their 1-sentence summaries. Example:
{{
  "api/v1/endpoints.py": "Defines the REST endpoints for repository management."
}}
"""
        
        # 2. README and Onboarding prompts
        doc_prompt = f"""You are a Senior Technical Writer. Analyze the structure and modules of the {repo_name} repository (Frameworks: {frameworks_str}).

File structure details:
{symbols_str}

Please generate two outputs:
1. A generated overview README (in Markdown) that explains what the codebase does, how it is structured, and how to get started.
2. A comprehensive Onboarding Field Guide (in Markdown) structured exactly with the following sections:
   - **Project Purpose**
   - **Folder Structure** (using standard ASCII text directory tree layout)
   - **Core Components**
   - **Execution Flow**
   - **Important Files** (list with descriptions)
   - **Learning Path** (a step-by-step guide on what to read first, second, etc.)
   - **Estimated Time to Understand** (e.g. '1 hour', '4 hours')

Return ONLY a JSON object matching this schema:
{{
  "readme": "# README content in markdown...",
  "onboarding_guide": "# Onboarding Guide content in markdown..."
}}
"""
        
        try:
            # Call for modules
            chat_completion_modules = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a professional code doc generator. Return ONLY JSON."},
                    {"role": "user", "content": modules_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            summaries = json.loads(chat_completion_modules.choices[0].message.content)

            # Call for onboarding and readme
            chat_completion_docs = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a senior technical writer. Return ONLY JSON."},
                    {"role": "user", "content": doc_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            docs_data = json.loads(chat_completion_docs.choices[0].message.content)

            readme = docs_data.get("readme", "")
            onboarding = docs_data.get("onboarding_guide", "")
            return summaries, readme, onboarding

        except Exception as e:
            logger.error(f"Error calling Groq SDK for documentation: {e}. Using fallback.")
            return self._generate_fallback_docs(manifest, ast_data)
