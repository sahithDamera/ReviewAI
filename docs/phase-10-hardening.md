# Phase 10 — Security hardening

Public session and generation throttles now use a bounded in-process counter. Owner authentication throttles remain SQL-backed and shared. The public limiter is approximate across multiple backend instances; move it to a shared store such as Redis when scaling horizontally.

Phase 10 adds shared SQL-backed throttles for public session creation and AI generation, production transport/security headers, and rate-limit cleanup. The counters are shared across API workers through Supabase PostgreSQL and fail closed if the database is unavailable. CSP, Permissions-Policy, Referrer-Policy, HSTS (production), and existing CSRF/origin checks are now applied at the application boundary.

Redis remains an optional deployment optimization; this Supabase-only setup does not require another service. Password recovery/email verification still require selecting an email provider before unattended launch. A real AI provider also remains an explicit configuration choice; the local provider does not need a key.

Changed files: `backend/app/core/security.py`, `backend/app/main.py`, `backend/app/commands/cleanup_reviews.py`, `frontend/next.config.ts`.

Verification passed: Ruff, 29 backend offline tests, frontend lint, TypeScript, production build, and live security-header checks.
