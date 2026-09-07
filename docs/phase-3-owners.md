# Phase 3 — Owner authentication and onboarding

Implemented scope: owner signup, login, logout, business creation/retrieval/editing, category defaults, a stable public review URL, owner UI, and authorization checks. Supabase remains the database service; FastAPI Users manages accounts in `reviewflow.users`, not Supabase Auth's `auth.users`.

## Architecture decisions

- Use the planned FastAPI Users 14 library and SQLAlchemy adapter. Argon2 password hashes map to the existing `password_hash` column. Registration normalizes email, requires 12–128 character passwords, and cannot grant privileged flags.
- Use the library's database-backed random session tokens in HttpOnly, SameSite=Lax cookies. Production adds Secure and the `__Host-` prefix. Tokens expire after 12 hours by default; logout revokes the current database session. Browser JavaScript never reads the owner token.
- `AUTH_SECRET` signs CSRF tokens and hashes rate-limit keys. Bootstrap tokens bind a random cookie nonce and timestamp to the current owner cookie. Mutation routes require both the token/header and an exact `Origin` match with `APP_URL`. No wildcard CORS is enabled; Next.js proxies `/api` to FastAPI under one browser origin.
- Authentication throttles use atomic PostgreSQL counters shared by backend workers. This avoids adding Redis solely for low-volume owner authentication. Login is limited by IP and normalized-email digest (10/15 minutes); registration by IP (5/hour). Only keyed digests are persisted. Counters are checked before password verification. Redis remains planned for the public customer/AI endpoints.
- Run the supplied Uvicorn command with `--no-proxy-headers`. The current limiter uses the connection peer IP; behind the Next.js proxy this is intentionally coarse. Before a broader deployment, configure a trusted edge that overwrites forwarded IP headers and review proxy trust and limit tuning together. Never accept arbitrary client-supplied forwarded headers.
- Business creation is one transaction for the profile, validated Google destination, and category attributes. A unique owner constraint enforces one business per owner. Edits lock and scope the business by owner; changing category replaces enabled defaults. The public identifier remains stable.
- Per the user's follow-up request, destinations accept any valid HTTPS URL, including Google Search/Maps links with query parameters and fragments. Embedded credentials, invalid URLs, and executable schemes are rejected. URLs are preserved without removing review fragments. No server-side URL fetch takes place. Activating a business requires the owner's explicit confirmation that the link opens the correct business; this is not platform-verified ownership.

## Migration

`0002_owners` adds `users.is_superuser`, `owner_sessions`, and `auth_rate_limits` in the existing private schema. It changes neither existing business data nor Supabase's own schemas. Readiness now expects `0002_owners`. Alembic remains the sole migration authority.

## API and pages

| Route | Behavior |
| --- | --- |
| `GET /api/auth/csrf` | Obtain a short-lived CSRF token and nonce cookie |
| `POST /api/auth/register` | JSON email/password; safe owner profile, 201 |
| `POST /api/auth/login` | Form username/password; sets cookie, 204 |
| `POST /api/auth/logout` | Revoke current session, clear cookie, 204 |
| `GET /api/auth/me` | Current active owner or 401 |
| `GET /api/business-categories` | Authenticated category/attribute list |
| `POST /api/businesses` | Create owned business/destination/defaults, 201 |
| `GET /api/businesses/me` | Current owner's profile or 404 |
| `GET /api/businesses/{id}` | Owned profile; returns 404 for another owner's record |
| `PUT /api/businesses/{id}` | Update only the authenticated owner's business |

Frontend routes: `/`, `/signup`, `/login`, `/onboarding`, `/dashboard`, `/dashboard/settings`. The dashboard in this phase is a business profile and URL page, not analytics. It explicitly describes the URL as reserved until Phase 4. All private data comes from authenticated APIs; the statically rendered page shells contain no account data. Logo upload, customer pages, QR exports, and AI are not introduced here.

## Running locally

Keep your existing Supabase connection/certificate in `backend/.env`. Add a stable random 32+ character `AUTH_SECRET` if not already configured. `APP_URL` must be exactly `http://localhost:3000`, with no trailing slash. The setup work generated a secret locally without displaying it or altering the database credential. Different deployments need their own secret.

Backend terminal (from the repository root):

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.lock
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.commands.seed
& .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --loop app.core.runtime:event_loop_factory --no-proxy-headers --reload
```

Frontend terminal (from the repository root):

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://localhost:3000/signup**. Use `localhost` consistently: the browser Origin must match backend `APP_URL`. The frontend defaults to proxying to `http://127.0.0.1:8000`; override `API_INTERNAL_URL` in `frontend/.env.local` only if using another backend address. Restart the frontend after changing that setting. No database secrets belong in frontend environment files.

For deployment, schedule `python -m app.commands.cleanup_auth` daily. Expiry is enforced on every authenticated request even if cleanup is delayed. No reset/verification email routes are exposed yet; email delivery and account recovery remain a required public-launch task in the original hardening roadmap.

## Verification

- 38 backend tests cover Phase 2 regression plus signup, normalized emails, Argon2 storage, safe privilege flags, cookie persistence, logout revocation, expired sessions, missing/wrong/session-bound CSRF, duplicate accounts/businesses, owned CRUD, category replacement, stable URLs, URL allowlists, invalid input, and shared auth throttling.
- Desktop Chromium and a Chromium mobile viewport both exercised real API signup → onboarding → edit → refresh → logout → private-route rejection → login against a disposable local database. These are not mocked backend responses. No browser tests create users in hosted Supabase or submit Google reviews.
- Frontend production build/TypeScript and lint are checked. The mobile dashboard capture was visually reviewed. Browser testing does not claim native iOS Safari coverage.

To reproduce browser tests, start the disposable SQL container, migrate/seed it using a local `DATABASE_URL` override, run the backend and frontend against it, then run `npm run test:e2e` from `frontend`. Use a dedicated test `AUTH_SECRET` and keep `APP_URL` matched to the browser. Do not point E2E at a live business database. The Playwright base URL defaults to localhost:3000 and can be overridden with `E2E_BASE_URL`.

Next phase: the anonymous customer rating, attributes, optional comment, and manual review flow.

Hosted verification: migration `0002_owners` was applied to the configured Supabase project. Both new tables exist and all 11 categories remain. The built frontend returned HTTP 200 for `/signup`, and `/api/health/ready` through the frontend proxy returned `ready` against hosted Supabase. The disposable test database was removed after verification; no test owners were created in Supabase.
