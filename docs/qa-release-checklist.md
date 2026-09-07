# ReviewFlow AI — QA and release checklist

Use this document to understand what is implemented and to verify it before launch. The application has been built in 12 phases. Local automated checks cover the code; the sections marked **staging** require a real Supabase project, deployed services, or a physical device.

## What currently works

### Owner workflow

1. Open `/signup`.
2. Register with an email and a password of 12–128 characters.
3. Log in and open onboarding.
4. Choose a business category, name, tone, and Google review URL.
5. Confirm the URL and create the business.
6. View the business review URL and dashboard.
7. Edit business settings, download PNG/SVG QR codes, view activity, and view analytics.
8. Log out; protected dashboard and QR routes require logging in again.

Implemented controls include password hashing, secure owner cookies, CSRF protection, ownership checks, origin validation, authentication throttling, verification/reset routes, and production verification enforcement.

### Customer workflow

1. Open `/r/<public_identifier>` or scan the QR code.
2. Choose one to five stars; there is no preselected rating.
3. Optionally select topics and positive/negative polarity.
4. Optionally enter a comment.
5. Continue to the writing step.
6. Receive three distinct suggestions when Anthropic is enabled, or template suggestions when disabled/unavailable.
7. Select and edit a suggestion, or write manually.
8. Copy the exact final text.
9. Continue through the preconfigured Google link.

The app never submits a Google review. All ratings use the same destination, including one- and two-star ratings.

### Reliability and privacy behavior

- Review sessions last two hours by default and are hashed in the database.
- Draft rating, topics, comment, and step are stored only in tab-scoped `sessionStorage` for expiry recovery.
- Expired sessions are recreated and drafts replayed automatically when possible.
- AI requests are backend-only; API keys never belong in frontend variables.
- AI failures fall back to templates and then manual writing.
- Request IDs, redacted errors, security headers, request-size limits, and public/auth throttles are enabled.
- Customer review text is not shown in owner dashboard responses.
- Cleanup removes expired sessions, raw events, old aggregates, and expired throttles.

## Automated checks

Run backend checks:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m ruff check app migrations tests
& .\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
```

Run frontend checks:

```powershell
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

Run browser journeys with backend and frontend running:

```powershell
cd frontend
npx playwright test
```

The browser suite covers owner signup/onboarding/login/logout, customer rating/topics, suggestions, editing, clipboard handoff, and desktop/mobile layouts.

## Supabase staging checks

Use a separate staging Supabase project. Never use production for integration tests.

```powershell
cd backend
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.commands.seed
```

Verify:

- Supabase contains the private `reviewflow` schema and migration revision `0003_funnel_columns`.
- `reviewflow` is not exposed through browser Data API roles.
- Database TLS uses `sslmode=verify-full` and the CA certificate.
- `/api/health/live` returns 200.
- `/api/health/ready` returns 200 after migrations.
- A staging owner can complete onboarding and cannot access another owner’s business.
- A staging customer can complete both high- and low-rating flows.
- QR PNG and SVG files decode to the correct public URL.
- Analytics counts change after session, generation, selection, copy, and handoff events.
- Cleanup runs successfully and removes only expired/private data.

## Anthropic checks

Set these only in the backend environment:

```env
GENERATION_ENABLED=true
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-haiku-latest
AI_API_KEY=your_key
```

Verify in staging that:

- Three options are returned.
- Options are distinct and within length limits.
- The customer’s rating and supplied facts are preserved.
- Unsupported details are not invented.
- Recent review openings are avoided.
- Timeout, malformed output, provider outage, and missing credentials fall back safely.
- The daily business ceiling and three-attempt session ceiling work.
- No API key appears in responses, frontend bundles, or logs.

## Manual device and accessibility checks

On a physical iPhone using Safari:

- Open a public review link.
- Complete the flow without leaving the page unexpectedly.
- Confirm clipboard permission behavior and manual-copy fallback.
- Confirm the Google link opens correctly after the selection is saved.
- Repeat with a one-star rating.

On keyboard and screen-reader testing:

- Every control is reachable in a logical order.
- Rating buttons expose their selected state.
- Topic controls and errors have accessible labels.
- Focus remains understandable after validation and generation errors.
- Text can be selected and copied manually.

## Release gates still requiring evidence

- Full PostgreSQL integration suite in GitHub Actions.
- Supabase staging migration and restore from backup.
- Production HTTPS, domain, secure cookies, and readiness routing.
- Real email delivery for verification and password reset.
- Physical iPhone Safari handoff test.
- Accessibility review on target devices.
- p75 initial interaction and p95 AI latency measurements.
- Cleanup scheduler and alert verification.
- Anthropic budget and usage monitoring.

Record the date, environment, commit/image version, tester, and result for each staging gate. Do not mark production ready based only on local unit tests.

## Where to find implementation details

- Full phase map: [implementation-review-12-phases.md](implementation-review-12-phases.md)
- Deployment and rollback: [phase-12-release.md](phase-12-release.md)
- Automated testing: [phase-11-testing.md](phase-11-testing.md)
- Consumer-review policy: [../PRODUCT_POLICY.md](../PRODUCT_POLICY.md)
