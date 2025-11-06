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

1. Create environment files for each app:
   - `app/backend/.env` for server-side variables such as `AUTH0_DOMAIN`,
     `AUTH0_AUDIENCE`, `DATABASE_URL`, Redis, and storage credentials.
   - `app/frontend/.env` for browser-safe variables prefixed with `VITE_`
     like `VITE_API_BASE_URL`, `VITE_AUTH0_DOMAIN`, and `VITE_AUTH0_CLIENT_ID`.
2. Install backend requirements (FastAPI, SQLAlchemy, etc.) and frontend dependencies
   (React, Vite, TailwindCSS).
3. Launch the FastAPI app with `uvicorn app.backend.src.main:app --reload` and the frontend
   with `npm run dev` inside `app/frontend`.
4. Run tests with `pytest` (backend) and `npm test` / `npm run test:e2e` (frontend) once the
   corresponding suites are implemented.

## Development seed data

- Run `python seed_dev_data.py` to create the demo vendor and user in your local database.
 Optionally set `AUTH0_DEMO_SUB` to link the seeded user to an Auth0 identity.
- If the API server is already running you can also call `POST /api/admin/seed` to seed the
  same records; the response now includes the linked Auth0 subject when present.

After seeding, use Auth0-issued access tokens when calling protected endpoints such as
`/api/jobs` or `/api/invoices/generate`.

## Next Steps

- Configure automated jobs to update Auth0-linked profiles with additional vendor metadata.
- Flesh out the processing pipeline connecting uploads, Redis queues, S3 storage, and PDF
  generation.
- Add Alembic migrations and seed data commands.
- Build the React dashboards and integrate with the backend APIs.
