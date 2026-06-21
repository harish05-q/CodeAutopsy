import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse
from pydantic import BaseModel

class RepositoryManifest(BaseModel):
    repository_id: str
    owner: str
    name: str
    url: str
    ref: str
    frameworks: List[str]
    dependencies: List[str]
    total_files: int
    total_lines_of_code: int
    file_extensions: Dict[str, int]
    file_list: List[str] # relative paths of python files

class RepoAgent:
    def __init__(self, max_size_mb: int = 100, max_files: int = 2000):
        self.max_size_mb = max_size_mb
        self.max_files = max_files

    def parse_github_url(self, url: str) -> Tuple[str, str]:
        """Extract owner and repo name from github URL."""
        parsed = urlparse(url)
        if parsed.netloc != "github.com":
            raise ValueError("Only github.com URLs are supported.")
        path = parsed.path.strip("/")
        parts = path.split("/")
        if len(parts) < 2:
            raise ValueError("Invalid GitHub repository URL.")
        owner = parts[0]
        # Remove .git suffix if present
        repo = parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo

    async def run(self, repository_id: str, url: str, ref: str = "main") -> Tuple[Path, RepositoryManifest]:
        """
        Clones the repo to a temporary directory, analyzes its structure,
        and generates a manifest.
        """
        owner, repo_name = self.parse_github_url(url)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"repo_{repository_id}_"))

        try:
            # 1. Clone the repo shallowly
            # Use subprocess to run git clone
            cmd = ["git", "clone", "--depth", "1", "--branch", ref, url, str(temp_dir)]
            # If ref is a commit SHA, depth 1 branch clone won't work directly, but for public github URLs,
            # this works for branches/tags.
            process = await asyncio_subprocess(cmd)
            if process.returncode != 0:
                # Fallback: clone without branch, then checkout ref if it failed
                cmd_fallback = ["git", "clone", "--depth", "1", url, str(temp_dir)]
                process_fallback = await asyncio_subprocess(cmd_fallback)
                if process_fallback.returncode != 0:
                    raise RuntimeError(f"Failed to clone repository: {url}")
                
                # Try checking out the specific ref
                checkout_cmd = ["git", "-C", str(temp_dir), "checkout", ref]
                await asyncio_subprocess(checkout_cmd)

            # 2. Check limits (files and sizes)
            total_size = sum(f.stat().st_size for f in temp_dir.glob("**/*") if f.is_file())
            total_size_mb = total_size / (1024 * 1024)
            if total_size_mb > self.max_size_mb:
                raise ValueError(f"Repository size ({total_size_mb:.1f}MB) exceeds limit of {self.max_size_mb}MB")

            # 3. Scan filesystem and compute metrics
            all_files = []
            python_files = []
            extensions = {}
            total_loc = 0

            # Exclude dotfiles, venv, node_modules
            exclude_dirs = {".git", ".github", "node_modules", "venv", ".venv", "env", "__pycache__", ".next", "dist", "build"}

            for root, dirs, files in os.walk(temp_dir):
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(temp_dir)
                    all_files.append(rel_path.as_posix())
                    
                    ext = full_path.suffix.lower()
                    if ext:
                        extensions[ext] = extensions.get(ext, 0) + 1
                    
                    if ext == ".py":
                        python_files.append(rel_path.as_posix())
                        try:
                            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                                total_loc += sum(1 for _ in f)
                        except Exception:
                            pass

            if len(all_files) > self.max_files:
                raise ValueError(f"Repository has too many files ({len(all_files)}), limit is {self.max_files}")

            # 4. Framework and dependency detection
            frameworks = []
            dependencies = set()
            
            # Simple inspection of files
            for rel_path in python_files:
                full_path = temp_dir / rel_path
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "import fastapi" in content or "from fastapi" in content:
                            frameworks.append("FastAPI")
                        if "import django" in content or "from django" in content:
                            frameworks.append("Django")
                        if "import flask" in content or "from flask" in content:
                            frameworks.append("Flask")
                except Exception:
                    pass
            
            # Read requirements/dependency declarations
            requirements_txt = temp_dir / "requirements.txt"
            pyproject_toml = temp_dir / "pyproject.toml"
            setup_py = temp_dir / "setup.py"

            if requirements_txt.exists():
                try:
                    with open(requirements_txt, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Extract dependency name
                                match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                                if match:
                                    dependencies.add(match.group(1).lower())
                except Exception:
                    pass

            if pyproject_toml.exists():
                try:
                    with open(pyproject_toml, "r", encoding="utf-8", errors="ignore") as f:
                        toml_content = f.read()
                        # Simple regex parsing for dependencies to avoid external toml parser in repo_agent
                        deps = re.findall(r"\"([a-zA-Z0-9_\-]+)[>=<]*.*\"", toml_content)
                        for d in deps:
                            dependencies.add(d.lower())
                except Exception:
                    pass

            frameworks = list(set(frameworks))
            if not frameworks:
                # Default to Python if no web frameworks detected
                frameworks.append("Python CLI / Core")

            manifest = RepositoryManifest(
                repository_id=repository_id,
                owner=owner,
                name=repo_name,
                url=url,
                ref=ref,
                frameworks=frameworks,
                dependencies=list(dependencies),
                total_files=len(all_files),
                total_lines_of_code=total_loc,
                file_extensions=extensions,
                file_list=python_files
            )

            return temp_dir, manifest

        except Exception as e:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise e

async def asyncio_subprocess(cmd: List[str]) -> subprocess.CompletedProcess:
    """Helper to run a subprocess asynchronously."""
    loop = asyncio_get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    )

# Helper to support asyncio methods in simple files
def asyncio_get_event_loop():
    import asyncio
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()
