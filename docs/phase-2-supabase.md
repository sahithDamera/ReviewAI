# Phase 2 — Supabase backend foundation

User-directed change: Supabase is the database service. It hosts PostgreSQL, so UUIDs, JSONB, foreign keys, SQLAlchemy, and the relational design remain applicable. We use server-side SQL connections, not a browser SDK or service-role REST calls. Supabase Auth is not implicitly enabled by this database change; the owner-authentication choice is revisited in Phase 3 before auth code is added.

## Implemented

- FastAPI app factory, liveness/readiness endpoints, request IDs, redacted readiness errors, and startup configuration validation.
- Verified TLS for remote SQL connections, bounded async pooling, query/connect timeouts, separate optional migration credentials, and a Windows-compatible async loop.
- Alembic migration with 11 private-schema tables: users, categories, experience attributes, businesses, business attributes, Google destinations, review sessions, generations, selections, raw analytics, daily aggregates.
- Foreign-key ownership safeguards, rating/length/status constraints, one pending generation per session, unique request/event keys, and session deletion that retains the event's business association.
- Repeatable transactional seeds for all 11 categories and 55 default attributes, typed category models, pinned runtime/test dependencies, a backend Dockerfile, and disposable SQL integration-test configuration.

`owner_sessions` is deferred to Phase 3 so its shape follows the selected authentication library. Empty business/review tables reserve the agreed V1 schema; no business or review endpoints are implemented here. Redis is deferred until rate-limited endpoints exist. No hosted Supabase project is created or changed without a configured development connection.

## Supabase access boundary

The new `reviewflow` schema revokes PUBLIC access and remains outside the exposed API schemas. Application requests go through FastAPI. SQL roles govern this private path; there are no permissive browser RLS policies. If direct browser access is added later, it requires a separately reviewed RLS and API design.

Use the Supabase owner credential for migrations during setup. Before deploying, create a dedicated login through Supabase's SQL administration tools and configure its password outside versioned SQL. Then, as the schema owner, grant the runtime role only what it needs (example role name `reviewflow_api`):

```sql
GRANT USAGE ON SCHEMA reviewflow TO reviewflow_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA reviewflow TO reviewflow_api;
REVOKE INSERT, UPDATE, DELETE ON reviewflow.alembic_version FROM reviewflow_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA reviewflow
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO reviewflow_api;
```

Execute default-privilege changes as the same role that runs migrations. Set the restricted login in `DATABASE_URL` and keep the owner login in `MIGRATION_DATABASE_URL`. Schema ownership, role creation, passwords, and project-level settings are operator provisioning tasks, not automatic app startup changes. No special grants to `anon`, `authenticated`, or `service_role` are needed. Supabase connection usernames and session-pooler hostnames must be copied from that project's Connect panel.

## Verification scope

Automated tests cover settings rejection/redaction, health success/failure, offline SQL generation, migrations on an empty real SQL database, repeated upgrades, reversible migrations, idempotent seeds preserving edits, selected-rating bounds, cross-session selection rejection, concurrent-pending protection, schema privileges, and cleanup foreign-key behavior. The local database validates PostgreSQL SQL semantics, not hosted Supabase TLS, credentials, pooler routing, or dashboard settings; those require the separate hosted connection smoke check.

Next phase: owner authentication and onboarding. No customer AI, QR, frontend, billing, or POS implementation belongs to this phase.

## Verification result (2026-09-07)

All 17 automated tests passed against the disposable PostgreSQL 17 engine. A separate live smoke check successfully ran `alembic upgrade head`, seeded 11 categories/55 attributes, started Uvicorn with the Windows-compatible loop, returned `ok` from liveness and `ready` from database readiness, and exposed the two expected health routes in OpenAPI. Dependency consistency checks passed. Two upstream test-client deprecation warnings remain; they do not affect the application or test results.

After the user configured their project, the hosted Supabase connection and TLS certificate were verified, migration `0001_foundation` was applied, and the hosted counts were confirmed as 11 categories and 55 attributes. Phase 2's hosted setup is complete.
