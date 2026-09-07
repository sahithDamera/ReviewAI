# Phase 4 — Public customer review flow

Phase 4 implements the first anonymous customer experience. A public business identifier resolves to an active, owner-confirmed business without exposing owner data. The API creates a configurable two-hour bearer session by default, stores only its SHA-256 token hash, validates ratings and enabled category attributes, and supports restoring or updating the session. If a session expires, the browser can create a replacement and replay its tab-scoped draft. Expired, invalid, paused, and unknown businesses return safe errors.

Changed files:

- `backend/app/api/reviews.py` — public business and review-session routes.
- `backend/app/schemas/review.py` — public profile, session, rating, and attribute contracts.
- `backend/app/services/reviews.py` — business resolution, token hashing, session lifecycle, and attribute ownership checks.
- `backend/app/main.py` — registers public review routes.
- `frontend/app/r/[business_identifier]/page.tsx` — dynamic customer page.
- `frontend/components/PublicReviewFlow.tsx` — rating, topics, comment, and manual-writing interaction.
- `frontend/services/api.ts` — public review types.

Architectural decisions:

- Existing `reviewflow.review_sessions` storage is sufficient; no migration is required.
- Customer tokens stay in tab-scoped `sessionStorage` and are sent in an `Authorization: Bearer` header, never in the URL.
- Draft rating, selected topics, comment, and step are stored in `sessionStorage` for expiry recovery. Owner credentials, email addresses, and account identifiers are not stored in the draft record. Draft storage is cleared after successful copy handoff.
- Public business profiles use a five-minute in-process cache and are invalidated after owner updates. The cache is per backend instance; a shared cache can be introduced when horizontal scaling requires it.
- Public lookup returns only display fields, enabled attribute IDs/labels, availability, and the configured HTTPS destination needed by later handoff work.
- Phase 4 saves customer input but does not call an AI provider or submit anything to Google. AI begins in Phase 5; selection, clipboard, and handoff begin in Phase 6.

Verification:

- Backend Ruff and offline tests: passed (`29 passed`, integration tests skipped without the disposable test database).
- Frontend lint, TypeScript, and production build: passed.
- Public route returns a page for an unknown identifier and safely shows the unavailable state; the API returns `404 BUSINESS_UNAVAILABLE`.
