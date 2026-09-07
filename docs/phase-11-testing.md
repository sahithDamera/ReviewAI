# Phase 11 — Regression and browser testing

Phase 11 closes the highest-value verification gaps across Phases 1–10. Backend pytest coverage now includes AI output bounds, QR asset signatures, configuration, migrations, authentication, ownership, URL validation, health/error redaction, and safe request logging. The Playwright owner workflow covers desktop and mobile signup, onboarding, customer rating/topics, AI suggestions, clipboard handoff, editing, logout, and login.

Run the offline backend suite:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
```

Run browser tests with both local servers running:

```powershell
cd frontend
npx playwright test
```

The PostgreSQL integration suite remains opt-in and requires the disposable local test database described in `README.md`. Production deployment, real provider smoke tests, backup restore, accessibility tooling, and performance measurement remain external release gates.
