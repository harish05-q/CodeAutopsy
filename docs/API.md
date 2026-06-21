# API specification

Base path: `/api/v1`

## Analysis

### `POST /repositories/analyze`

Request:

```json
{ "url": "https://github.com/owner/repository", "ref": "main" }
```

Response `202`:

```json
{ "repository_id": "repo_01J...", "run_id": "run_01J...", "status": "queued" }
```

### `GET /analysis/{run_id}`

Returns run status, progress from 0–100, current stage, timing and failure details.

### `GET /analysis/{run_id}/events`

Server-sent event stream. Events: `stage.started`, `stage.progress`, `artifact.ready`, `run.completed`, `run.failed`.

## Repository intelligence

- `GET /repositories/{id}/overview`
- `GET /repositories/{id}/graphs/dependencies`
- `GET /repositories/{id}/graphs/calls`
- `GET /repositories/{id}/architecture`
- `GET /repositories/{id}/onboarding`
- `GET /repositories/{id}/risks`
- `GET /repositories/{id}/artifacts`

Graph responses contain `nodes` and `edges` with stable IDs. Markdown resources return `{ content, generated_at, model, sources }`.

## Repository QA

### `POST /repositories/{id}/chat`

Request: `{ "question": "How does authentication work?", "conversation_id": null }`

Response includes `answer`, `confidence`, and `sources[]`; each source contains file path, line interval, symbol and relevance score.

## Errors

All errors follow RFC 9457 problem details with `type`, `title`, `status`, `detail`, `instance` and a stable application `code`.
