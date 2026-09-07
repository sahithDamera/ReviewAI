# Phase 7 — QR generation

Phase 7 adds owner-authenticated QR assets for the stable ReviewFlow customer URL. The backend generates high-contrast PNG and vector SVG files with a four-module quiet zone. The Google destination is never encoded in the QR; customers reach it after the review handoff.

Changed files:

- `backend/app/services/qr_service.py` — PNG/SVG QR rendering.
- `backend/app/api/businesses.py` — owner-scoped `/api/businesses/{id}/qr` endpoint.
- `backend/requirements.lock`, `backend/pyproject.toml` — pinned `qrcode` and `Pillow` dependencies.
- `frontend/app/dashboard/qr/page.tsx` — preview and PNG/SVG downloads.

No database migration is required. Verification passed with Ruff, frontend lint/type-check/build, and direct PNG/SVG generation smoke checks.
