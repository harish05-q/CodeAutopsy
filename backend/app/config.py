import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./codeautopsy.db"

    # Path where generated analysis artifacts are stored
    ANALYSIS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "analysis"

    # LLM and API configuration
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Constraints
    MAX_REPO_SIZE_MB: int = 100
    MAX_FILE_COUNT: int = 2000


# Create singleton settings object
settings = Settings()

# Debug (remove after verifying)
print("GROQ KEY LOADED:", bool(settings.GROQ_API_KEY))

# Ensure analysis folder exists
settings.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)