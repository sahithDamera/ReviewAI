# Phase 8 — Owner dashboard activity

Phase 8 adds an owner-scoped overview endpoint and activity page. It reports directional counts from stored events and customer-selected ratings while keeping comments, generated text, tokens, and private identifiers out of the owner view.

Changed files:

- `backend/app/schemas/dashboard.py` — summary and activity response contracts.
- `backend/app/api/businesses.py` — authenticated `/api/businesses/{id}/overview` endpoint.
- `frontend/services/dashboard.ts` — overview client type and loader.
- `frontend/app/dashboard/activity/page.tsx` — summary cards and recent activity timeline.

No migration is required. Detailed date-range funnels, daily aggregates, and cleanup remain Phase 9.

Verification passed: Ruff, 29 backend offline tests, frontend lint, TypeScript, and production build.
