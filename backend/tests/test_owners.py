from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.commands.seed import main as seed_main
from app.core.config import Settings
from app.core.runtime import event_loop_factory
from app.main import create_app

pytestmark = pytest.mark.integration
ORIGIN = "http://localhost:3000"
PASSWORD = "a long test-only passphrase"


@pytest.fixture
def browser(migrated, database_url):
    import asyncio

    asyncio.run(seed_main(), loop_factory=event_loop_factory)
    with migrated.begin() as connection:
        connection.execute(text("DELETE FROM reviewflow.auth_rate_limits"))
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_url=ORIGIN,
        database_url=database_url.render_as_string(hide_password=False),
        auth_secret="test-only-persistent-secret-with-32-characters",
    )
    with TestClient(
        create_app(settings), backend_options={"loop_factory": event_loop_factory}
    ) as client:
        yield client


def mutate(browser, method, path, **kwargs):
    csrf = browser.get("/api/auth/csrf").json()["csrf_token"]
    return browser.request(method, path, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}, **kwargs)


def register(browser, email=None):
    email = email or f"owner-{uuid4().hex}@example.com"
    response = mutate(
        browser,
        "POST",
        "/api/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "is_superuser": True,
            "is_verified": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["is_superuser"] is False
    assert response.json()["is_verified"] is False
    return email, response.json()["id"]


def login(browser, email):
    response = mutate(
        browser, "POST", "/api/auth/login", data={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 204, response.text
    return response


def payload(browser):
    categories = browser.get("/api/business-categories").json()
    return {
        "name": "Mario's Italian Kitchen",
        "category_id": categories[0]["id"],
        "google_review_url": "https://g.page/r/test-place/review",
        "description": "A neighborhood kitchen",
        "brand_tone": "friendly",
        "status": "active",
        "destination_confirmed": True,
    }


def test_registration_password_hash_and_logout_revocation(browser, migrated):
    email, user_id = register(browser, f"UPPER-{uuid4().hex}@EXAMPLE.COM")
    assert browser.get("/api/auth/me").status_code == 401
    response = login(browser, email)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert browser.get("/api/auth/me").json()["email"] == email.lower()
    assert PASSWORD not in browser.get("/api/auth/me").text
    with migrated.connect() as connection:
        hashed = connection.scalar(
            text("SELECT password_hash FROM reviewflow.users WHERE id=:id"), {"id": user_id}
        )
        assert hashed.startswith("$argon2")
        assert hashed != PASSWORD
    token = browser.cookies.get("reviewflow_owner")
    assert mutate(browser, "POST", "/api/auth/logout").status_code == 204
    browser.cookies.set("reviewflow_owner", token)
    assert browser.get("/api/auth/me").status_code == 401


def test_business_creation_editing_and_owner_isolation(browser, migrated):
    first_email, _ = register(browser)
    login(browser, first_email)
    body = payload(browser)
    created = mutate(browser, "POST", "/api/businesses", json=body)
    assert created.status_code == 201, created.text
    business = created.json()
    assert business["review_url"].startswith(ORIGIN + "/r/")
    assert len(business["public_identifier"]) >= 22
    assert mutate(browser, "POST", "/api/businesses", json=body).status_code == 409
    categories = browser.get("/api/business-categories").json()
    body.update(name="Mario's Cafe", category_id=categories[1]["id"])
    updated = mutate(browser, "PUT", f"/api/businesses/{business['id']}", json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["review_url"] == business["review_url"]
    with migrated.connect() as connection:
        attributes = (
            connection.execute(
                text(
                    "SELECT a.category_id FROM reviewflow.business_attributes ba "
                    "JOIN reviewflow.experience_attributes a ON a.id=ba.attribute_id "
                    "WHERE ba.business_id=:id"
                ),
                {"id": business["id"]},
            )
            .scalars()
            .all()
        )
        assert len(attributes) == 5
        assert all(str(category) == categories[1]["id"] for category in attributes)
    mutate(browser, "POST", "/api/auth/logout")
    second_email, _ = register(browser)
    login(browser, second_email)
    assert browser.get(f"/api/businesses/{business['id']}").status_code == 404
    assert mutate(browser, "PUT", f"/api/businesses/{business['id']}", json=body).status_code == 404
    assert browser.get("/api/businesses/me").status_code == 404


def test_csrf_origin_and_session_binding(browser):
    assert browser.post("/api/auth/register", json={}).status_code == 403
    csrf = browser.get("/api/auth/csrf").json()["csrf_token"]
    response = browser.post(
        "/api/auth/register",
        json={},
        headers={
            "Origin": "https://attacker.example",
            "X-CSRF-Token": csrf,
        },
    )
    assert response.status_code == 403
    email, _ = register(browser)
    # Pre-login CSRF token must not authorize an authenticated mutation.
    pre_login = browser.get("/api/auth/csrf").json()["csrf_token"]
    authenticated = browser.post(
        "/api/auth/login",
        data={"username": email, "password": PASSWORD},
        headers={"Origin": ORIGIN, "X-CSRF-Token": pre_login},
    )
    assert authenticated.status_code == 204
    response = browser.post(
        "/api/businesses",
        json=payload(browser),
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": pre_login,
        },
    )
    assert response.status_code == 403


def test_invalid_onboarding_rolls_back(browser):
    email, _ = register(browser)
    login(browser, email)
    body = payload(browser)
    body["destination_confirmed"] = False
    assert mutate(browser, "POST", "/api/businesses", json=body).status_code == 422
    body["destination_confirmed"] = True
    body["category_id"] = str(uuid4())
    assert mutate(browser, "POST", "/api/businesses", json=body).status_code == 422
    assert browser.get("/api/businesses/me").status_code == 404
    body = payload(browser)
    body["owner_id"] = str(uuid4())
    assert mutate(browser, "POST", "/api/businesses", json=body).status_code == 422


def test_duplicate_registration_and_expired_session(browser, migrated):
    email, user_id = register(browser)
    duplicate = mutate(
        browser, "POST", "/api/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert duplicate.status_code == 400
    login(browser, email)
    with migrated.begin() as connection:
        connection.execute(
            text(
                "UPDATE reviewflow.owner_sessions SET created_at=now()-interval '2 days' "
                "WHERE user_id=:id"
            ),
            {"id": user_id},
        )
    assert browser.get("/api/auth/me").status_code == 401


def test_login_rate_limit_is_shared_and_bounded(browser):
    for _ in range(10):
        response = mutate(
            browser,
            "POST",
            "/api/auth/login",
            data={
                "username": "missing@example.com",
                "password": PASSWORD,
            },
        )
        assert response.status_code == 400, response.text
    response = mutate(
        browser,
        "POST",
        "/api/auth/login",
        data={
            "username": "missing@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_invalid_password_is_not_echoed(browser):
    response = mutate(
        browser,
        "POST",
        "/api/auth/register",
        json={
            "email": "valid@example.com",
            "password": "shortpw",
        },
    )
    assert response.status_code == 422
    assert "shortpw" not in response.text
