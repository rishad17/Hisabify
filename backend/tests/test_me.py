"""Profile onboarding and per-user data isolation (needs PostgreSQL)."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models import Category, Profile, Wallet
from app.services.onboarding import DEFAULT_CATEGORIES, ensure_profile
from tests.conftest import auth_header

pytestmark = pytest.mark.db


def test_first_login_sets_up_account(db_client, make_token):
    user_id = uuid.uuid4()
    r = db_client.get("/api/v1/me", headers=auth_header(make_token(user_id)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_new_user"] is True
    assert body["profile"]["id"] == str(user_id)
    assert body["profile"]["preferred_language"] == "en"
    assert body["profile"]["timezone"] == "Asia/Dhaka"
    assert body["profile"]["store_ai_text"] is False
    assert body["default_wallet_name"] == "Cash"
    assert body["category_count"] == len(DEFAULT_CATEGORIES)


def test_second_login_does_not_duplicate_defaults(db_client, db_session, make_token):
    user_id = uuid.uuid4()
    headers = auth_header(make_token(user_id))
    db_client.get("/api/v1/me", headers=headers)
    r = db_client.get("/api/v1/me", headers=headers)
    assert r.json()["is_new_user"] is False

    wallets = db_session.scalar(select(func.count()).where(Wallet.user_id == user_id))
    categories = db_session.scalar(select(func.count()).where(Category.user_id == user_id))
    assert wallets == 1
    assert categories == len(DEFAULT_CATEGORIES)


def test_ensure_profile_is_idempotent(db_session):
    user_id = uuid.uuid4()
    _, created_first = ensure_profile(db_session, user_id)
    _, created_again = ensure_profile(db_session, user_id)
    assert (created_first, created_again) == (True, False)
    assert db_session.scalar(select(func.count()).where(Profile.id == user_id)) == 1


def test_users_only_see_their_own_categories(db_client, make_token):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    a = auth_header(make_token(alice))
    b = auth_header(make_token(bob))
    db_client.get("/api/v1/me", headers=a)
    db_client.get("/api/v1/me", headers=b)

    alice_ids = {c["id"] for c in db_client.get("/api/v1/categories", headers=a).json()}
    bob_ids = {c["id"] for c in db_client.get("/api/v1/categories", headers=b).json()}
    assert len(alice_ids) == len(DEFAULT_CATEGORIES)
    assert alice_ids.isdisjoint(bob_ids)


def test_categories_filter_and_bangla_names(db_client, make_token):
    h = auth_header(make_token())
    db_client.get("/api/v1/me", headers=h)
    income = db_client.get("/api/v1/categories?kind=income", headers=h).json()
    assert income and all(c["kind"] == "income" for c in income)
    names = {c["name"]: c["name_bn"] for c in db_client.get("/api/v1/categories", headers=h).json()}
    assert names["Transport"] == "যাতায়াত"


def test_update_profile(db_client, make_token):
    h = auth_header(make_token())
    r = db_client.patch(
        "/api/v1/me",
        headers=h,
        json={"display_name": "  Rafi   Ahmed ", "preferred_language": "bn"},
    )
    assert r.status_code == 200, r.text
    profile = r.json()["profile"]
    assert profile["display_name"] == "Rafi Ahmed"
    assert profile["preferred_language"] == "bn"


@pytest.mark.parametrize(
    "body",
    [
        {"preferred_language": "fr"},
        {"preferred_language": None},
        {"display_name": "x" * 61},
        {"unknown_field": 1},
    ],
)
def test_update_profile_validation(db_client, make_token, body):
    r = db_client.patch("/api/v1/me", headers=auth_header(make_token()), json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_health_db(db_client):
    assert db_client.get("/health/db").json() == {"status": "ok", "database": "reachable"}
