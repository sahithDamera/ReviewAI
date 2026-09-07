# Phase 12 — Production release readiness

Phase 12 packages the application for deployment and defines release controls around Supabase. The repository contains production Docker images, a CI workflow, and rollout, rollback, backup, and smoke-test steps.

## Build and run images

```powershell
docker build -t reviewflow-api:local ./backend
docker build -t reviewflow-web:local ./frontend
docker run --rm --env-file backend/.env.production -p 8000:8000 reviewflow-api:local
```

The API image does not run migrations automatically. Run the migration job once with the migration credential, then start API workers:

```powershell
docker run --rm --env-file backend/.env.production reviewflow-api:local python -m alembic upgrade head
```

The frontend image is a standalone Next.js build. Set `API_INTERNAL_URL` in the frontend build environment to the backend’s private HTTPS URL, and expose port 3000.

## Supabase release sequence

1. Use separate Supabase projects for staging and production. Never point CI or integration tests at production.
2. Store `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `DATABASE_SSL_ROOT_CERT`, `AUTH_SECRET`, and `APP_URL` as backend secrets. Use the session pooler on port 5432 or a direct connection, with `sslmode=verify-full` and the CA certificate mounted in the container.
3. Run `alembic upgrade head` once, then verify `/api/health/live` and `/api/health/ready` return 200 before routing frontend traffic.
4. Set backend `APP_URL` to the public frontend origin exactly, with no trailing slash. Deploy the frontend with `API_INTERNAL_URL` targeting the backend.
5. Complete a staging owner/customer smoke test, including QR resolution and Google handoff. The application navigates to Google but never submits a review.

## Rollback and recovery

Deployments are image-versioned. Roll back application code by routing traffic to the previous API and frontend image tags. Do not downgrade Alembic on a live database; forward-fix incompatible migrations, or restore a Supabase backup into a new project and switch the connection secret after verification.

Before production, enable Supabase point-in-time recovery and verify a backup restore into a disposable project. Record the restore timestamp, migration revision, and readiness result. Schedule `python -m app.commands.cleanup_reviews` daily and alert on a non-zero exit status.

## Provider and operations controls

The default deterministic provider is safe for local and staging use and requires no API key. If a real provider adapter is added, its key belongs only in backend secrets, never `NEXT_PUBLIC_*`. Set provider timeout, budget, and daily generation limits before enabling it, then run a disposable-business staging smoke test.

Use HTTPS at the edge, preserve `X-Request-ID` in logs, and redact request bodies, cookies, bearer tokens, customer comments, and database URLs. Monitor API 5xx responses, readiness failures, generation latency, generation-limit responses, and cleanup failures. Keep the private `reviewflow` schema out of Supabase Data API exposure.

## CI and release gates

`.github/workflows/ci.yml` runs backend Ruff and offline pytest plus frontend lint, typecheck, and production build on every push and pull request. Staging must additionally pass PostgreSQL integration tests, desktop/mobile Playwright journeys, backup restore and cleanup verification, accessibility/performance checks, and a real-provider smoke test when a provider is enabled.
