# ASCS x SCUSD Invoice Agent

This repository hosts the multi-tenant invoice automation platform combining a FastAPI
backend with a React + Vite frontend. The current commit provides the project scaffolding,
core domain models, API routers, and placeholder services that match the system design
requirements. Future work will extend these stubs into the fully automated processing
pipeline powered by OpenAI AgentKit.

## Repository Layout

```
app/
  backend/
    src/
      api/                # FastAPI routers
      agents/             # OpenAI AgentKit integration points
      core/               # Config, database, logging, and storage utilities
      models/             # SQLAlchemy models for the domain
      schemas/            # Pydantic v2 schemas
      services/           # Data processing services
      main.py             # FastAPI application factory
    migrations/           # Alembic migrations (to be implemented)
    tests/
      unit/
      e2e/
  frontend/
    src/
      components/
      pages/
      lib/
      styles/
    index.html
render.yaml               # Render deployment definition
.env.example              # Environment variable template
README.md                 # Project overview
```

## Getting Started

1. Copy `.env.example` to `.env` and supply environment values.
2. Install backend requirements (FastAPI, SQLAlchemy, etc.) and frontend dependencies
   (React, Vite, TailwindCSS).
3. Launch the FastAPI app with `uvicorn app.backend.src.main:app --reload` and the frontend
   with `npm run dev` inside `app/frontend`.
4. Run tests with `pytest` (backend) and `npm test` / `npm run test:e2e` (frontend) once the
   corresponding suites are implemented.

## Next Steps

- Implement Auth0 JWT validation middleware.
- Flesh out the processing pipeline connecting uploads, Redis queues, S3 storage, and PDF
  generation.
- Add Alembic migrations and seed data commands.
- Build the React dashboards and integrate with the backend APIs.
