# ReviewFlow AI

Phase 12: production release readiness for the public customer review flow, with deterministic server-side AI suggestions, Google handoff, owner QR exports, activity dashboard, analytics, retention cleanup, security hardening, regression/browser testing, production Docker images, and CI using **Next.js + FastAPI + Supabase-managed PostgreSQL**.

See the [Phase 12 release runbook](docs/phase-12-release.md) for image builds, Supabase migrations, deployment, rollback, backups, and staging gates.
See the [QA and release checklist](docs/qa-release-checklist.md) for implemented functionality and testing steps.
See the [team setup and Git handoff guide](docs/team-setup-and-git.md) for onboarding and secret handling.
See [PRODUCT_POLICY.md](PRODUCT_POLICY.md) for the consumer-review policy.

See the [Phase 11 setup and verification](docs/phase-11-testing.md), [Phase 10 setup and verification](docs/phase-10-hardening.md), [Phase 9 setup and verification](docs/phase-9-analytics.md), [Phase 8 setup and verification](docs/phase-8-dashboard.md), [Phase 7 setup and verification](docs/phase-7-qr.md), [Phase 6 setup and verification](docs/phase-6-handoff.md), [Phase 5 setup and verification](docs/phase-5-ai.md), [Phase 4 setup and verification](docs/phase-4-customer.md), [Phase 3 setup and verification](docs/phase-3-owners.md), [architecture specification](docs/reviewflow-ai-architecture.md), and [Phase 2 notes](docs/phase-2-supabase.md).

## Start the owner app

With `backend/.env` configured, run these in two terminals from the repository root.

Backend:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.lock
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --loop app.core.runtime:event_loop_factory --no-proxy-headers --reload
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://localhost:3000/signup**. Backend `APP_URL` must match that origin exactly. Keep `AUTH_SECRET` stable in `backend/.env`; it was generated during Phase 3 setup. Accounts appear in `reviewflow.users` in Supabase's Table Editor, not its Authentication section. Do not overwrite the existing `.env` when following first-time setup instructions below.

After creating a business, open its public review URL from the owner dashboard or scan the link. It has the form `http://localhost:3000/r/<public_identifier>` during local development.

## Supabase connection

1. Create or select a development project in Supabase. In **Connect**, copy the **Session pooler** connection string (port 5432), or use a Direct connection if your network supports it. This backend intentionally rejects the transaction-pooler port 6543.
2. Create `backend/.env` from `backend/.env.example`. Set `DATABASE_URL`, replacing the placeholders, and URL-encode the password. Use the `postgresql+psycopg://` scheme and `?sslmode=verify-full`. If required, download the project's database CA certificate and set `DATABASE_SSL_ROOT_CERT` to its local path. Do not disable TLS verification to work around certificate errors.
3. Use `MIGRATION_DATABASE_URL` for the schema-owner credential when the runtime uses a restricted SQL role. Neither connection string belongs in the frontend or source control.
4. Keep `reviewflow` out of Supabase's exposed Data API schemas. This app accesses SQL through FastAPI. You may disable the Data API if no other part of your project uses it. No Supabase API/service-role key is required for Phase 2.

Supabase supplies PostgreSQL rather than a different database engine. Its documentation recommends direct/session connections for persistent backends and explains how to disable unused Data API access: [connection options](https://supabase.com/docs/guides/database/connecting-to-postgres), [API access controls](https://supabase.com/docs/guides/api/securing-your-api).

## Install and run (PowerShell)

From the repository root, using Python 3.12:

```powershell
cd backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.lock
Copy-Item .env.example .env
# Edit .env with your Supabase development project's SQL connection string.
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.commands.seed
& .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --loop app.core.runtime:event_loop_factory --reload
```

Do not overwrite an existing `.env`. The virtual environment may already exist. On macOS/Linux, use `python3.12 -m venv .venv` and `.venv/bin/python` in place of the Windows executable.

- `http://localhost:8000/api/health/live`: process health, independent of the database.
- `http://localhost:8000/api/health/ready`: database connectivity and expected migration revision; 503 when missing/unavailable.
- `http://localhost:8000/api/docs`: development OpenAPI interface; disabled in production.

The explicit event-loop factory supports Psycopg async connections on Windows. Startup validates settings but does not migrate, seed, or require a live database. Health failures do not expose database exceptions or connection strings.

## Migrations and seeds

Alembic is the only schema migration authority. Do not also apply these tables through Supabase CLI migrations. The initial SQL migration creates 11 application tables in the private `reviewflow` schema, plus Alembic history. It does not change Supabase `auth`, `storage`, or `public` objects.

```powershell
cd backend
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.commands.seed
```

The seed command is transactional and repeatable: it adds 11 category defaults and 55 experience attributes while preserving existing labels. It does not create an owner, demo password, or fake Google destination. The demo business is deferred until owner onboarding is implemented.

SQL migrations define the complete foundation; only the category models needed by Phase 2 exist in Python. Add feature models as their phases are implemented. Autogeneration is deliberately disabled so partial Python metadata cannot drop future tables. Timestamps default at insertion; later write services must explicitly update `updated_at`.

Preview SQL using `python -m alembic upgrade head --sql`. Rollback with `python -m alembic downgrade base` is destructive to application data and is intended only for disposable development databases. It drops the named application tables without cascading into unrelated Supabase objects. Never use it on a live project without a reviewed recovery plan.

## Tests

Unit/configuration/offline migration checks need no database:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
& .\.venv\Scripts\python.exe -m ruff check app migrations tests
```

Full tests use a disposable local PostgreSQL engine matching Supabase's database semantics. This test container is not the application's hosted database and does not emulate Supabase Auth, PostgREST, or pooler infrastructure.

From the repository root with Docker Desktop running:

```powershell
docker compose -f compose.test.yaml -p reviewflow-phase2-test up -d --wait
cd backend
$env:TEST_DATABASE_URL='postgresql+psycopg://reviewflow_test:local-test-only@127.0.0.1:55432/reviewflow_test'
& .\.venv\Scripts\python.exe -m pytest -q
cd ..
docker compose -f compose.test.yaml -p reviewflow-phase2-test down
```

Tests refuse non-loopback hosts and any database not named `reviewflow_test`; they exercise a destructive migration round-trip only in that isolated database. Data is temporary. Without `TEST_DATABASE_URL`, integration tests are explicitly skipped. Do not use a hosted project URL for the test suite.

For a local API smoke test, use the test database URL as `DATABASE_URL`, migrate, seed, and run the server above. For hosted Supabase validation, run the non-destructive upgrade/seed/health steps against a separate development project after configuring credentials.

## Production boundary

Phase 3 includes owner authentication, authorization, CSRF checks, and shared owner-auth throttles. Customer endpoints, AI limits, password recovery/email delivery, and the remaining production hardening are still scheduled. Before deployment, give FastAPI a SQL login with only `USAGE` on `reviewflow` and needed table DML; reserve schema ownership/DDL for the migration credential. Do not grant browser roles (`anon`, `authenticated`) access to this private schema. See [Phase 2 setup](docs/phase-2-supabase.md) for role setup details and [Phase 3](docs/phase-3-owners.md) for proxy/limit configuration.
