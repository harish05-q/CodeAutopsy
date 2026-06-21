# Data models

Core identifiers are ULIDs. Timestamps are UTC ISO 8601 values. All stored artifacts have an explicit schema version.

```text
Repository
  id, github_url, owner, name, default_branch, created_at

AnalysisRun
  id, repository_id, commit_sha, status, stage, progress,
  started_at, completed_at, error_code

Symbol
  id, run_id, module_id, kind, qualified_name, file_path,
  start_line, end_line, decorators, complexity

GraphNode
  id, graph_id, symbol_id?, label, kind, metadata

GraphEdge
  id, graph_id, source_id, target_id, kind, confidence

Finding
  id, run_id, rule_id, severity, title, file_path,
  line?, evidence, recommendation

Artifact
  id, run_id, kind, relative_path, content_type,
  schema_version, checksum, created_at

ChatMessage
  id, repository_id, conversation_id, role, content,
  source_refs, created_at
```

The public API uses Pydantic DTOs distinct from persistence models. Graph metadata is a typed discriminated union rather than an unbounded JSON bag.
