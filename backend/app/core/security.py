import asyncio
import hashlib
import hmac
import secrets
import time
from collections import OrderedDict

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session


def owner_cookie(request: Request) -> str:
    return (
        "__Host-reviewflow_owner"
        if request.app.state.settings.app_env == "production"
        else "reviewflow_owner"
    )


def csrf_cookie(request: Request) -> str:
    return (
        "__Host-reviewflow_csrf"
        if request.app.state.settings.app_env == "production"
        else "reviewflow_csrf"
    )


def signature(request: Request, payload: str) -> str:
    session = request.cookies.get(owner_cookie(request), "")
    return hmac.new(
        request.app.state.auth_secret.encode(), f"{payload}:{session}".encode(), hashlib.sha256
    ).hexdigest()


def make_csrf(request: Request) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(32)
    payload = f"{nonce}.{int(time.time())}"
    return nonce, f"{payload}.{signature(request, payload)}"


async def require_csrf(request: Request):
    if request.headers.get("origin") != request.app.state.settings.app_url:
        raise HTTPException(403, "ORIGIN_REJECTED")
    token = request.headers.get("x-csrf-token", "")
    try:
        nonce, timestamp, mac = token.split(".")
        age = time.time() - int(timestamp)
        valid = (
            0 <= age <= 3600
            and hmac.compare_digest(nonce, request.cookies.get(csrf_cookie(request), ""))
            and hmac.compare_digest(mac, signature(request, f"{nonce}.{timestamp}"))
        )
        if not valid:
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(403, "CSRF_INVALID") from None


async def auth_limits(request: Request, session: AsyncSession = Depends(get_session)):
    """Shared SQL counters for low-volume owner auth; never trust client X-Forwarded-For."""
    route = request.url.path.rsplit("/", 1)[-1]
    if route not in {"login", "register"}:
        return
    ip = request.client.host if request.client else "unknown"
    keys = [f"{route}:ip:{ip}"]
    if route == "login":
        form = await request.form()
        keys.append(f"login:email:{str(form.get('username', '')).strip().lower()}")
    limit = 10 if route == "login" else 5
    window = 900 if route == "login" else 3600
    exceeded = False
    for key in keys:
        digest = hmac.new(
            request.app.state.auth_secret.encode(), key.encode(), hashlib.sha256
        ).hexdigest()
        hits = await session.scalar(
            text("""
            INSERT INTO reviewflow.auth_rate_limits(key,hits,expires_at)
            VALUES (:key,1,now()+make_interval(secs => :window))
            ON CONFLICT (key) DO UPDATE SET
              hits = CASE WHEN reviewflow.auth_rate_limits.expires_at <= now()
                     THEN 1 ELSE reviewflow.auth_rate_limits.hits+1 END,
              expires_at = CASE WHEN reviewflow.auth_rate_limits.expires_at <= now()
                           THEN EXCLUDED.expires_at ELSE reviewflow.auth_rate_limits.expires_at END
            RETURNING hits
        """),
            {"key": digest, "window": window},
        )
        exceeded |= hits > limit
    await session.execute(text("DELETE FROM reviewflow.auth_rate_limits WHERE expires_at < now()"))
    await session.commit()
    if exceeded:
        raise HTTPException(429, "AUTH_RATE_LIMITED", headers={"Retry-After": str(window)})


async def public_limits(request: Request, session: AsyncSession = Depends(get_session)):
    """Shared SQL throttles for public session and generation endpoints."""
    if request.method != "POST":
        return
    path = request.url.path
    if path.endswith("/review-session"):
        bucket, limit, window = "session", 120, 3600
    elif path.endswith("/generate-review"):
        bucket, limit, window = "generation", 60, 3600
    else:
        return
    ip = request.client.host if request.client else "unknown"
    digest = hmac.new(
        request.app.state.auth_secret.encode(), f"public:{bucket}:{ip}".encode(), hashlib.sha256
    ).hexdigest()
    hits = await session.scalar(
        text("""
            INSERT INTO reviewflow.auth_rate_limits(key,hits,expires_at)
            VALUES (:key,1,now()+make_interval(secs => :window))
            ON CONFLICT (key) DO UPDATE SET
              hits = CASE WHEN reviewflow.auth_rate_limits.expires_at <= now()
                     THEN 1 ELSE reviewflow.auth_rate_limits.hits+1 END,
              expires_at = CASE WHEN reviewflow.auth_rate_limits.expires_at <= now()
                           THEN EXCLUDED.expires_at ELSE reviewflow.auth_rate_limits.expires_at END
            RETURNING hits
        """), {"key": digest, "window": window},
    )
    await session.commit()
    if hits > limit:
        raise HTTPException(429, "PUBLIC_RATE_LIMITED", headers={"Retry-After": str(window)})


_public_local: OrderedDict[str, tuple[float, int]] = OrderedDict()
_public_local_lock = asyncio.Lock()


async def public_local_limits(request: Request):
    """Bounded per-instance public throttle; owner auth limits remain SQL-backed."""
    if request.method != "POST":
        return
    path = request.url.path
    if path.endswith("/review-session"):
        bucket, limit, window = "session", 120, 3600
    elif path.endswith("/generate-review"):
        bucket, limit, window = "generation", 60, 3600
    else:
        return
    ip = request.client.host if request.client else "unknown"
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    async with _public_local_lock:
        previous = _public_local.get(key)
        active = previous is not None and previous[0] > now
        hits = previous[1] + 1 if active else 1
        expiry = previous[0] if active else now + window
        _public_local[key] = (expiry, hits)
        _public_local.move_to_end(key)
        while len(_public_local) > 10000:
            _public_local.popitem(last=False)
    if hits > limit:
        raise HTTPException(429, "PUBLIC_RATE_LIMITED", headers={"Retry-After": str(window)})
