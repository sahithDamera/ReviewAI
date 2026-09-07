# ReviewFlow AI — 12-phase implementation review

This document is the review checklist for the work completed from Phase 1 through Phase 12. It describes the behavior currently implemented in this repository, where to find it, what has been verified, and which decisions remain before a public launch.

## Product delivered

ReviewFlow gives a business owner a private dashboard and a stable public review link. A customer opens that link, chooses a rating and optional experience topics, receives three server-generated review suggestions, edits or writes a review, copies the exact text, and then chooses whether to open the business’s configured Google destination. The application records operational events for owner analytics without exposing private customer text in the dashboard.

The stack is Next.js and React in `frontend/`, FastAPI and SQLAlchemy in `backend/`, and Supabase-managed PostgreSQL. Supabase is used as PostgreSQL; the application talks to it through the FastAPI server and the private `reviewflow` schema.

## Phase-by-phase record

### Phase 1 — Architecture and product definition

- Defined owner and customer journeys, data boundaries, privacy expectations, and MVP acceptance criteria.
- Chose Next.js, FastAPI, PostgreSQL/Supabase, Alembic, Playwright, and server-side AI generation.
- Recorded the design in [reviewflow-ai-architecture.md](reviewflow-ai-architecture.md).

### Phase 2 — Supabase database foundation

- Added the private `reviewflow` schema and explicit Alembic migrations.
- Added repeatable category and experience-attribute seeding.
- Added TLS-verified Supabase connection settings, migration credentials, statement timeouts, and connection pooling.
- Added database and migration tests.

### Phase 3 — Owner accounts and onboarding

- Added email/password registration, login, logout, current-user lookup, CSRF bootstrap, secure owner cookies, password hashing, and session expiry.
- Added category selection, business creation/update, Google destination URL validation and confirmation, public identifiers, and ownership checks.
- Added SQL-backed authentication rate limits and cleanup.
- Main code: `backend/app/api/auth.py`, `backend/app/api/businesses.py`, `backend/app/services/business.py`, `frontend/app/signup`, `frontend/app/login`, `frontend/app/onboarding`.

### Phase 4 — Public customer review flow

- Added public business lookup by identifier and the `/r/[business_identifier]` route.
- Added short-lived, hashed customer review sessions.
- Added five-star rating, optional topic polarity, optional comment, validation, expiry, and revision/version handling.
- Added manual-writing fallback and low-rating handoff support.
- Main code: `backend/app/api/reviews.py`, `backend/app/services/reviews.py`, `frontend/components/PublicReviewFlow.tsx`.

### Phase 5 — Review suggestions

- Added a server-side deterministic provider that creates exactly three distinct bounded suggestions from rating, topics, business category, tone, and comment.
- Added generation persistence, idempotency keys, attempt limits, stale-input checks, and failure/manual fallback behavior.
- No external AI key is required for the current provider. A future provider key must remain backend-only.
- Main code: `backend/app/services/ai_service.py`, `backend/app/services/generation.py`, `backend/app/schemas/ai.py`.

### Phase 6 — Selection and Google handoff

- Added selection persistence, editing, exact final-text response, clipboard copy, clipboard failure handling, and user-initiated Google navigation.
- Added copy and Google-open analytics events. The app never submits a Google review.
- Main code: `backend/app/services/handoff.py`, `backend/app/schemas/handoff.py`, `frontend/services/api.ts`, `frontend/components/PublicReviewFlow.tsx`.

### Phase 7 — QR assets

- Added owner-protected PNG and SVG QR downloads pointing to the public review URL.
- Added `/dashboard/qr` and QR download controls.
- Added signature tests for PNG/SVG output.
- Main code: `backend/app/services/qr_service.py`, `backend/app/api/businesses.py`, `frontend/app/dashboard/qr`.

### Phase 8 — Owner dashboard

- Added dashboard overview and activity endpoints/pages.
- Added totals, rating average, generation and handoff counts, recent activity, loading/error/empty states, and owner-only access.
- Customer review text is intentionally excluded from the dashboard.
- Main code: `backend/app/schemas/dashboard.py`, `backend/app/api/businesses.py`, `frontend/app/dashboard`, `frontend/app/dashboard/activity`.

### Phase 9 — Analytics and retention

- Added analytics summary and daily trend endpoint/page.
- Added event recording for session start, rating, generation, selection, copy, and Google-open actions.
- Added daily aggregate generation and cleanup command for expired sessions, raw events, old aggregates, and expired rate-limit rows.
- Main code: `backend/app/schemas/analytics.py`, `backend/app/commands/cleanup_reviews.py`, `frontend/app/dashboard/analytics`.

### Phase 10 — Security hardening

- Added shared SQL-backed public generation/session throttles.
- Added request size limits, CSRF and origin checks, secure cookie behavior, security headers, strict production HTTPS checks, and redacted errors.
- Added request IDs and structured completion/failure logging without request bodies, tokens, comments, or database URLs.
- Main code: `backend/app/core/security.py`, `backend/app/core/config.py`, `backend/app/main.py`, `frontend/next.config.ts`.

### Phase 11 — Testing and SDLC verification

- Added offline backend tests for configuration, authentication, ownership, validation, AI output bounds, QR signatures, health behavior, and logging.
- Added Playwright owner/customer journeys for desktop and mobile, including rating/topics, suggestions, clipboard handoff, editing, logout, and login.
- Added Ruff, frontend lint, TypeScript, and production build checks.
- Details: [phase-11-testing.md](phase-11-testing.md).

### Phase 12 — Production release readiness

- Added standalone Next.js production Docker image and backend Docker healthcheck.
- Added GitHub Actions CI for backend and frontend static checks/builds.
- Added deployment, migration, backup/restore, rollback, cleanup scheduling, provider-secret, and staging smoke-test instructions.
- Details: [phase-12-release.md](phase-12-release.md).

## Database schema

All application tables live under `reviewflow` and are managed by Alembic. The migrations currently create:

| Table | Purpose |
| --- | --- |
| `users` | Owner accounts and password hashes |
| `owner_sessions` | Hashed owner login sessions |
| `auth_rate_limits` | Shared authentication/public throttle counters |
| `business_categories` | Seeded business categories |
| `experience_attributes` | Seeded selectable topics per category |
| `businesses` | Owner business profile and public identifier |
| `business_attributes` | Topics enabled for a business |
| `business_google_destinations` | Confirmed Google destination URL |
| `review_sessions` | Short-lived customer inputs and rating |
| `review_generations` | Generated suggestion sets and idempotency state |
| `review_selections` | Selected/edited final review text |
| `analytics_events` | Operational funnel events |
| `analytics_daily` | Retained daily aggregates |

Supabase `auth`, `storage`, and browser Data API objects are not used by this implementation. SQL credentials and CA certificates belong in backend environment secrets only.

## Routes and screens

Backend health: `/api/health/live`, `/api/health/ready`; development OpenAPI: `/api/docs`.

Owner API areas include auth, categories, business profile, QR, overview, activity, and analytics. Public API areas include business lookup, review-session create/read/update, generation, selection, copy-event, and Google-open-event.

Frontend screens are `/`, `/signup`, `/login`, `/onboarding`, `/dashboard`, `/dashboard/activity`, `/dashboard/analytics`, `/dashboard/qr`, `/dashboard/settings`, and `/r/[business_identifier]`.

## Environment and secrets

Backend production requires `APP_ENV=production`, an HTTPS exact-origin `APP_URL`, a stable 32+ character `AUTH_SECRET`, a verified-TLS Supabase `DATABASE_URL`, and the CA certificate path when required. `MIGRATION_DATABASE_URL` should use a separate schema-owner credential. Frontend uses only `API_INTERNAL_URL`; no Supabase password, service-role key, or AI key belongs in frontend variables.

## Verification status

The current local verification is:

- Backend Ruff: passed.
- Backend offline pytest: 32 passed, 11 integration tests deselected without `TEST_DATABASE_URL`.
- Frontend lint: passed.
- Frontend TypeScript check: passed.
- Frontend production build: passed.
- Playwright desktop and mobile journeys: passed in separate runs.

Hosted integration tests, provider smoke tests, backup restore, accessibility audit, and mobile performance measurement remain staging release gates.

## Review decisions before launch

### Task 1 and Task 3 updates

- Anthropic is now the hosted generation provider when enabled through backend-only settings. The deterministic implementation remains the automatic template fallback for provider errors, invalid output, timeouts, disabled generation, and the daily ceiling.
- Review prompts include recent final-text openings to reduce repeated phrasing. The API key is never exposed to the frontend or logs.
- Review sessions retain a two-hour default TTL and customer drafts are stored in tab-scoped `sessionStorage` so expired sessions can be recreated and replayed.
- FastAPI Users verification and password-reset routes are enabled. Production business creation and updates require a verified owner; local development remains usable while an email sender is configured.
- Added verification and password-reset screens at `/verify` and `/reset-password`, plus a local console email sender. A real production mail transport still must be connected before launch.
- Public review throttling now uses a bounded per-instance limiter, while owner authentication throttling remains SQL-backed. Horizontal deployments need a shared limiter later.

1. Choose backend/frontend hosting and configure a production domain.
2. Create separate staging and production Supabase projects and credentials.
3. Decide whether to keep the deterministic provider for launch or add a real AI provider and budget controls.
4. Confirm owner email verification/password recovery delivery requirements.
5. Confirm the cleanup scheduler, backup retention, alerting destination, and incident owner.
6. Run the remaining staging gates listed above.

This document is intended to be edited as decisions change. The phase-specific documents remain the detailed operating instructions for each area.
