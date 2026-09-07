# Phase 9 — Analytics and retention

Phase 9 adds owner-scoped date-range reports with separate AI and manual funnel counts, UTC daily buckets, rating averages, and a scheduled cleanup command. Cleanup upserts historical activity into `reviewflow.analytics_daily` before removing expired session detail, raw events older than 30 days, and daily aggregates older than 12 months.

Changed files:

- `backend/app/schemas/analytics.py` — report, summary, and daily contracts.
- `backend/app/api/businesses.py` — authenticated `/api/businesses/{id}/analytics` endpoint.
- `backend/app/commands/cleanup_reviews.py` — aggregate-and-purge command for daily scheduling.
- Earlier session/generation/selection services now emit funnel events transactionally.

No migration is required. Reports enforce a maximum 366-day inclusive range and owner scoping. Customer text is never returned.

Verification passed: Ruff, 29 backend offline tests, frontend lint, and TypeScript checks.
