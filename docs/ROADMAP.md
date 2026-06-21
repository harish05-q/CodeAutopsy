# Development roadmap

## Phase 0 — product shell (complete)

- Architecture, data model and API boundary
- Responsive, interactive dashboard
- React Flow dependency and call graph experiences
- Upload/progress, reports, onboarding, risks and grounded-chat states

## Phase 1 — deterministic vertical slice

1. FastAPI application, SQLite migrations and repository records
2. Safe shallow Git clone and repository manifest
3. Python Tree-sitter symbol/import extraction
4. NetworkX dependency and approximate call graphs
5. Risk heuristics with fixture-based tests
6. Connect the dashboard to a single real analysis run

## Phase 2 — semantic intelligence

1. Syntax-aware source chunking
2. all-MiniLM-L6-v2 embedding adapter
3. Per-run FAISS index and retrieval evaluation set
4. Groq answer generation with source references
5. Resilient LLM timeouts, quotas and deterministic fallback

## Phase 3 — authored artifacts and deployment

1. Architecture inference evidence model
2. Module summaries and onboarding document generation
3. Mermaid diagram validation and rendering
4. Render backend deployment and Vercel frontend deployment
5. Observability, rate limits, retention and artifact cleanup

## Acceptance target

A first-time user can submit a medium Python repository, see live progress, inspect real dependency and call graphs, identify the top risks, follow a source-linked onboarding path and receive grounded answers within five minutes.
