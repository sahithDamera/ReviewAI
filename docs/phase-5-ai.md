# Phase 5 — AI review suggestions

Phase 5 provides a server-side generation contract and three-option suggestion flow. Anthropic is the configured hosted provider when `GENERATION_ENABLED=true` and `AI_API_KEY` is present. The backend sends supplied business facts plus recent review openings to reduce repetition. The local template provider automatically handles disabled generation, daily-ceiling exhaustion, timeouts, provider errors, and invalid output.

Changed files:

- `backend/app/schemas/ai.py` — generation request and strict three-option response contracts.
- `backend/app/services/ai_service.py` — bounded deterministic provider and output validation.
- `backend/app/services/generation.py` — token-scoped generation reservation, idempotency, persistence, and three-attempt cap.
- `backend/app/api/reviews.py` — `POST /api/public/generate-review`.
- `frontend/services/api.ts` — generation response types.
- `frontend/components/PublicReviewFlow.tsx` — suggestion cards, selection, editing, and manual fallback.

The existing `review_generations` table is used; no database migration is needed. A generation requires a saved rating and matching `input_version`, and callers must send an `Idempotency-Key`. Anthropic requests use a six-second timeout and one retry. API keys never appear in frontend code, responses, or logs. Failed or unavailable generation never removes the manual-writing path.

Verification passed:

- Ruff and backend offline tests: `29 passed`.
- Frontend lint, TypeScript, and production build: passed.
- Live smoke test for the configured business: a temporary session saved a rating and returned exactly three options.
