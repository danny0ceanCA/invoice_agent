``# ASCS x SCUSD Invoice Agent

This repository hosts the multi-tenant invoice automation platform combining a FastAPI
backend with a React + Vite frontend. The current commit provides the project scaffolding,
core domain models, API routers, and placeholder services that match the system design
requirements. Future work will extend these stubs into the fully automated processing
pipeline powered by OpenAI AgentKit.

## Repository Layout

```
app/uvicorn app.backend.main:app --reload

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

## Analytics run_sql tool

The district analytics agent exposes a `run_sql` tool that executes read-only analytics
queries against the warehouse. The tool validates that every query starts with `SELECT`
or `WITH`, strips trailing semicolons, and binds any provided `district_key` or
`district_id` into the statement so results stay tenant-scoped. When the context only
includes `district_id`, it looks up the corresponding key before executing the SQL via
SQLAlchemy and logs the request and row count for observability. Hard-coded
`district_key` predicates in the model-generated SQL are removed, and broad `SELECT * FROM
invoices` queries can be wrapped with a `WHERE sub.district_key = :district_key` guard to
keep results constrained. Error conditions are logged and re-raised so callers can handle
failures. 【F:app/backend/src/agents/district_analytics_agent.py†L1703-L1864】

For simpler utility usage outside the full agent workflow, `app/backend/src/api/analytics_agent.py`
provides a helper `run_sql(query)` that enforces the same read-only restriction and runs the
statement with SQLAlchemy, returning rows as dictionaries. 【F:app/backend/src/api/analytics_agent.py†L86-L102】

## District analytics agent model stack

Natural Language Variability (NLV) – Normalizes raw user queries into a structured intent
JSON, enforcing strict JSON-only output, synonym handling (e.g., provider→clinician),
school-year/time normalization rules anchored to TODAY, and ambiguity flags that drive
later clarification.

Entity Resolution – Refines the NLV intent against known students, vendors, and
clinicians, fuzzily matching names, converting any “provider” references to clinicians,
and flagging ambiguous or missing entities that require clarification.

SQL Planner – Produces a semantic query plan (not SQL) describing entity focus, time
window, metrics, grouping, and trend needs; normalizes school-year/YTD phrasing, maps
natural-language report types to plan kinds, and enforces clinician/provider normalization
for downstream SQL builders.

SQL Router – Converts the semantic plan plus multi-turn context into a high-level
RouterDecision (e.g., student_monthly, provider_breakdown, top_invoices), inferring
mode/filters, preserving active topics, and detecting when invoice detail or provider
breakdowns are needed.

Validator – Safety check for the logic-layer AnalyticsIR, whitelisting simple list/table
responses, blocking HTML/SQL keywords, enforcing schema constraints on rows/entities/time
windows, and sanitizing problematic content while returning a validity report.

Insight Generator – Transforms a validated AnalyticsIR into up to four plain-English
insights, avoiding SQL/HTML leakage, and defaulting to empty insights when the result set
is empty or in a clarification state.

Together, these models form the multi-stage workflow: NLV structures the intent → Entity
Resolution grounds it to district data → SQL Planner drafts a semantic plan → SQL Router
chooses the execution mode → Validator sanity-checks logic output → Insight Generator
summarizes results for the end user.

app/backend/src/agents/logic_model.py — Defines the analytics agent’s logic-model prompt
and helper functions for building the system prompt used when generating SQL/IR logic. It
includes detailed schema hints and SQL patterns for invoices, vendors, and line items,
along with strict tenant-scoping guidance.

multi_turn_model.py (repo root) — Implements the multi-turn conversation manager,
including the ConversationState dataclass for tracking slots, history, topics, and period
context, plus Redis-backed state persistence and user-message processing with reset
handling.

app/backend/src/agents/rendering_model.py — Provides the rendering-stage system prompt and
run_rendering_model function that converts the analytics IR and optional insights into
user-facing text/HTML via an OpenAI chat completion, with safeguards for entity ambiguity
and list-intent handling.
