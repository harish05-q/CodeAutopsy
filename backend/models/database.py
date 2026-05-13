"""
SQLAlchemy database models and session management.

Uses SQLite for simplicity. Stores only metadata — not code content.
Analysis artifacts (JSON, graphs, embeddings) are stored on disk.

Design decisions:
- SQLAlchemy with synchronous engine (SQLite doesn't benefit from async).
- Session factory via dependency injection, not global.
- Tables track repositories and their analysis runs with per-stage timing.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Repository(Base):
    """
    A GitHub repository submitted for analysis.

    Tracks the repo URL, clone status, and basic metadata.
    One repository can have multiple analysis runs.
    """

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False, index=True)
    owner = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    default_branch = Column(String(100), default="main")
    clone_path = Column(String(1000), nullable=True)
    total_files = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    languages_detected = Column(Text, default="[]")  # JSON array
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Analysis(Base):
    """
    A single analysis pipeline run for a repository.

    Tracks overall status, timing, and error information.
    Each stage's detailed output is saved as JSON artifacts on disk.
    """

    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    current_stage = Column(String(50), nullable=True)
    progress_percent = Column(Float, default=0.0)
    # Artifact directory for this analysis run
    artifacts_path = Column(String(1000), nullable=True)
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_stage = Column(String(50), nullable=True)
    # Summary stats (populated after completion)
    total_functions = Column(Integer, default=0)
    total_classes = Column(Integer, default=0)
    total_modules = Column(Integer, default=0)
    risk_count = Column(Integer, default=0)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AnalysisStage(Base):
    """
    Tracks individual pipeline stage execution.

    Every stage logs: what happened, how long it took, and what it produced.
    This is the core of the observability system.
    """

    __tablename__ = "analysis_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(Integer, nullable=False, index=True)
    stage_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    # Path to the artifact JSON file produced by this stage
    artifact_path = Column(String(1000), nullable=True)
    # Human-readable summary of what this stage did
    summary = Column(Text, nullable=True)
    # Number of items processed (files parsed, functions found, etc.)
    items_processed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


def create_db_engine(database_url: str) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy engine and session factory.

    Args:
        database_url: SQLite connection string.

    Returns:
        A sessionmaker bound to the engine. Use it to create sessions.
    """
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # Required for SQLite
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)
