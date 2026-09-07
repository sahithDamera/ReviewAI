# Phase 6 — Review selection and Google handoff

Phase 6 saves the customer’s selected AI option or manual text, copies the exact final text, records copy and handoff events, and navigates to the owner-confirmed HTTPS destination after a user action. Clipboard denial keeps the editor visible and offers manual copying. Event requests are best-effort and do not delay navigation.

Changed files:

- `backend/app/schemas/handoff.py` — selection and event contracts.
- `backend/app/services/handoff.py` — session-scoped selection validation and deduplicated event persistence.
- `backend/app/api/reviews.py` — selection, copy-event, and google-open-event routes.
- `frontend/services/api.ts` — selection response type.
- `frontend/components/PublicReviewFlow.tsx` — exact clipboard copy, persistence, fallback, and Google navigation.

The existing `review_selections` and `analytics_events` tables are used; no migration is required. The application never submits a review to Google; it only opens the configured destination.

Verification passed:

- Ruff and backend offline tests: `29 passed`.
- Frontend lint, TypeScript, and production build: passed.
