# 🔬 CodeAutopsy

**AI-powered static analysis and architecture reverse-engineering platform.**

Analyze GitHub repositories to generate architecture documentation, dependency maps, call graphs, risk analysis, and PDF autopsy reports.

## ✨ Features

- **Architecture Inference** — Detects patterns, module relationships, and design decisions
- **Dependency Graphs** — Interactive import and module dependency visualization
- **Call Graphs** — Function call relationship mapping
- **Risk Analysis** — Detects god classes, cyclic deps, high complexity, dead code, and more
- **AI Insights** — LLM-powered semantic summaries via Groq API
- **Semantic Search** — Find related code by meaning using embeddings + FAISS
- **PDF Reports** — Downloadable comprehensive autopsy reports
- **Full Observability** — Request IDs, pipeline timing, intermediate artifacts, structured logging

## 🏗️ Architecture

```
Frontend (Next.js + TypeScript + Tailwind)
    ↕ REST API
Backend (FastAPI + Python 3.12)
    ├── Orchestrator (pipeline stages)
    ├── GitHub Service (clone + scan)
    ├── Parser (AST extraction)
    ├── Graph Service (networkx)
    ├── Embeddings (sentence-transformers + FAISS)
    ├── LLM Service (Groq API)
    ├── Static Analyzers (radon, bandit, ruff)
    └── Report Generator (ReportLab PDF)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Git

### Backend

```bash
cd backend
py -3 -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Create a `.env` file from the template:
```bash
copy ..\.env.example .env
# Edit .env and add your GROQ_API_KEY
```

Start the backend:
```bash
cd ..  # Project root
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### API Documentation

Once the backend is running: http://localhost:8000/docs

## 📁 Project Structure

```
CodeAutopsy/
├── backend/
│   ├── api/              # FastAPI routes & dependencies
│   ├── core/             # Config, logging, constants
│   ├── models/           # SQLAlchemy + Pydantic models
│   ├── services/         # Business logic services
│   │   ├── github/       # Clone + scan
│   │   ├── parsing/      # AST extraction
│   │   └── orchestration/# Pipeline management
│   ├── analyzers/        # Analysis modules
│   └── main.py           # FastAPI app entry
├── frontend/
│   └── src/
│       ├── app/          # Next.js pages
│       └── lib/          # API client
├── docker-compose.yml
└── .github/workflows/    # CI/CD
```

## 🧪 Testing

```bash
cd backend
python -m pytest tests/ -v
```

## 🐳 Docker

```bash
docker-compose up
```

## 📜 License

MIT
