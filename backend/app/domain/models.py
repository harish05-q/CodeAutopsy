from datetime import datetime
import json
from typing import List, Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.infrastructure.db import Base

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(30), primary_key=True, index=True) # ULID
    github_url = Column(String(512), nullable=False, unique=True)
    owner = Column(String(256), nullable=False)
    name = Column(String(256), nullable=False)
    default_branch = Column(String(128), default="main")
    created_at = Column(DateTime, default=datetime.utcnow)

    runs = relationship("AnalysisRun", back_populates="repository", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="repository", cascade="all, delete-orphan")

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String(30), primary_key=True, index=True) # ULID
    repository_id = Column(String(30), ForeignKey("repositories.id"), nullable=False)
    commit_sha = Column(String(64), nullable=True)
    status = Column(String(32), default="queued") # queued, analyzing, completed, failed
    stage = Column(String(32), default="clone") # clone, ast, graph, embed, report, complete
    progress = Column(Integer, default=0) # 0 to 100
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)

    repository = relationship("Repository", back_populates="runs")
    symbols = relationship("Symbol", back_populates="run", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(String(30), primary_key=True, index=True) # ULID
    run_id = Column(String(30), ForeignKey("analysis_runs.id"), nullable=False)
    module_id = Column(String(256), nullable=True)
    kind = Column(String(64), nullable=False) # class, function, method
    qualified_name = Column(String(512), nullable=False)
    file_path = Column(String(512), nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    decorators_json = Column(Text, default="[]") # JSON list of strings
    complexity = Column(Integer, default=1)

    run = relationship("AnalysisRun", back_populates="symbols")

    @property
    def decorators(self) -> List[str]:
        try:
            return json.loads(self.decorators_json or "[]")
        except Exception:
            return []

    @decorators.setter
    def decorators(self, val: List[str]):
        self.decorators_json = json.dumps(val or [])

class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(30), primary_key=True, index=True) # ULID
    run_id = Column(String(30), ForeignKey("analysis_runs.id"), nullable=False)
    rule_id = Column(String(128), nullable=False)
    severity = Column(String(32), nullable=False) # low, medium, high
    title = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False)
    line = Column(Integer, nullable=True)
    evidence = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    run = relationship("AnalysisRun", back_populates="findings")

# Graph nodes and edges are stored in artifacts (dependency_graph.json/call_graph.json)
# to keep database queries lightweight. The Artifact model tracks metadata for these files.

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(30), primary_key=True, index=True) # ULID
    run_id = Column(String(30), ForeignKey("analysis_runs.id"), nullable=False)
    kind = Column(String(64), nullable=False) # manifest, ast, dependency_graph, call_graph, overview, architecture, onboarding, risks
    relative_path = Column(String(512), nullable=False)
    content_type = Column(String(128), nullable=False)
    schema_version = Column(Integer, default=1)
    checksum = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AnalysisRun", back_populates="artifacts")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(30), primary_key=True, index=True) # ULID
    repository_id = Column(String(30), ForeignKey("repositories.id"), nullable=False)
    conversation_id = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False) # user, assistant
    content = Column(Text, nullable=False)
    source_refs_json = Column(Text, default="[]") # JSON list of sources
    created_at = Column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="chat_messages")

    @property
    def source_refs(self) -> List[dict]:
        try:
            return json.loads(self.source_refs_json or "[]")
        except Exception:
            return []

    @source_refs.setter
    def source_refs(self, val: List[dict]):
        self.source_refs_json = json.dumps(val or [])
