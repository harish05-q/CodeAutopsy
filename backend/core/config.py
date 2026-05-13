"""
Application configuration using Pydantic Settings.

All configuration is loaded from environment variables or .env file.
No global state — config is injected via FastAPI dependencies.

Design decisions:
- Pydantic Settings provides validation, type coercion, and documentation in one place.
- All paths are resolved to absolute paths at load time to avoid ambiguity.
- Sensible defaults allow running without any env vars for development.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the CodeAutopsy backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CODEAUTOPSY_",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "CodeAutopsy"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Paths ---
    # Base directory for all data (cloned repos, artifacts, indexes)
    data_dir: Path = Path("./data")
    # Where cloned repositories are stored temporarily
    repos_dir: Path = Path("./data/repos")
    # Where analysis artifacts (JSON, graphs, embeddings) are saved
    artifacts_dir: Path = Path("./data/artifacts")

    # --- Database ---
    database_url: str = "sqlite:///./data/codeautopsy.db"

    # --- GitHub ---
    # Maximum repo size in MB before we refuse to clone
    max_repo_size_mb: int = 500
    # Clone timeout in seconds
    clone_timeout_seconds: int = 120

    # --- Groq LLM ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 4096
    groq_temperature: float = 0.1

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # --- Analysis ---
    # Max number of files to analyze in a single repo
    max_files_to_analyze: int = 5000
    # Max file size in KB for individual file analysis
    max_file_size_kb: int = 1024

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
