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

## User Roles

The platform serves three primary user personas:

- **Vendors** – Access the vendor portal to import timesheets and use vendor-specific
  features only.
- **District Staff** – Operate within the district module, including the district
  console (active vendors, approvals, analytics, settings, etc.).
- **Administrators** – Have full visibility across both vendor and district
  experiences.

## Getting Started

1. Copy `.env.example` to `.env` and supply environment values.
2. Install backend requirements (FastAPI, SQLAlchemy, etc.) and frontend dependencies
   (React, Vite, TailwindCSS).
3. Launch the FastAPI app with `uvicorn app.backend.src.main:app --reload` and the frontend
   with `npm run dev` inside `app/frontend`.
4. Run tests with `pytest` (backend) and `npm test` / `npm run test:e2e` (frontend) once the
   corresponding suites are implemented.

## Development seed data

- Run `python seed_dev_data.py` to create the demo vendor and user in your local database.
  The script prints the `X-User-Id` header value required when calling protected endpoints
  such as `/api/jobs` or `/api/invoices/generate`.
- If the API server is already running you can also call `POST /api/admin/seed` to seed the
  same records and receive the header value in the JSON response.

After seeding, include the returned `X-User-Id` header in your automation or API clients so the
requests are authenticated against the demo user.

## Next Steps

- Implement Auth0 JWT validation middleware.
- Flesh out the processing pipeline connecting uploads, Redis queues, S3 storage, and PDF
  generation.
- Add Alembic migrations and seed data commands.
- Build the React dashboards and integrate with the backend APIs.
