# Team setup and Git handoff

This guide recreates the ReviewFlow development environment without sharing secrets.

## What belongs in Git

Commit source code, migrations, tests, Dockerfiles, lockfiles, documentation, `.env.example` files, and CI configuration. Do not commit `.env`, `.env.production`, Supabase database URLs, Anthropic keys, `AUTH_SECRET`, database certificates, `.venv`, `node_modules`, `.next`, test reports, or generated build files. The repository `.gitignore` excludes these files.

Before the first push:

```powershell
git status --short
git add .
git diff --cached --name-only
git diff --cached -- .env backend/.env frontend/.env
```

The final command must show no staged environment files. If a secret was ever staged or pushed, rotate it; deleting the file is not enough.

## Prerequisites

- Python 3.12
- Node.js 22 LTS and npm
- Docker Desktop for integration tests
- A Supabase development project

## First-time setup

```powershell
cd backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.lock
Copy-Item .env.example .env
# Edit .env with development Supabase values.
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.commands.seed

cd ..\frontend
npm ci
```

Run backend and frontend in separate terminals using the root README commands. Keep `APP_URL=http://localhost:3000` locally and use `API_INTERNAL_URL=http://127.0.0.1:8000` for the frontend proxy.

## Local settings

Use `backend/.env.example` as the complete template. For Anthropic testing, set `GENERATION_ENABLED=true`, `AI_PROVIDER=anthropic`, `AI_MODEL`, and `AI_API_KEY`. To avoid external calls, set `GENERATION_ENABLED=false`; the template provider still exercises the full review flow.

## Pull-request checks

```powershell
cd backend
& .\.venv\Scripts\python.exe -m ruff check app migrations tests
& .\.venv\Scripts\python.exe -m pytest -m 'not integration' -q

cd ..\frontend
npm run lint
npm run typecheck
npm run build
```

GitHub Actions also runs the full PostgreSQL integration suite. Never use a production Supabase URL as `TEST_DATABASE_URL`.

## Secret rotation

Your current local `.env` contains live Supabase credentials, `AUTH_SECRET`, and an Anthropic key. Rotate the Supabase database password and Anthropic key immediately, update `.env`, and restart the backend. Rotate `AUTH_SECRET` only with a planned logout because it invalidates existing owner sessions.
