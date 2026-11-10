"""Authentication tests — no database needed.

/api/v1/categories requires auth; with a valid token the request gets past auth and then
fails with 503 (no DB configured in this client). So:
    401 → rejected by auth      503 → auth passed
"""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from tests.conftest import ISSUER, KEY_ID, auth_header

URL = "/api/v1/categories"


def test_missing_token_is_rejected(client):
    r = client.get(URL)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_valid_token_passes_auth(client, make_token):
    r = client.get(URL, headers=auth_header(make_token()))
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "database_not_configured"


def test_expired_token(client, make_token):
    token = make_token(exp=int(time.time()) - 3600)
    r = client.get(URL, headers=auth_header(token))
    assert r.status_code == 401
    assert "expired" in r.json()["error"]["message"]


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "anon"},  # wrong audience
        {"iss": "https://other-project.supabase.co/auth/v1"},  # another Supabase project
        {"role": "anon"},  # the public anon key, not a signed-in user
        {"role": "service_role"},
        {"sub": "not-a-uuid"},
        {"sub": None},  # missing subject
        {"exp": None},  # never-expiring token
    ],
)
def test_bad_claims_are_rejected(client, make_token, claims):
    r = client.get(URL, headers=auth_header(make_token(**claims)))
    assert r.status_code == 401


def test_token_signed_by_unknown_key(client):
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "exp": int(time.time()) + 600,
        },
        attacker_key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )
    assert client.get(URL, headers=auth_header(token)).status_code == 401


def test_hs256_rejected_when_no_secret_configured(client):
    """Without SUPABASE_JWT_SECRET, symmetric tokens must never be accepted."""
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "exp": int(time.time()) + 600,
        },
        "guessable-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    assert client.get(URL, headers=auth_header(token)).status_code == 401


def test_unsigned_alg_none_token_rejected(client):
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": ISSUER, "role": "authenticated"},
        key=None,
        algorithm="none",
    )
    assert client.get(URL, headers=auth_header(token)).status_code == 401


def test_garbage_token(client):
    assert client.get(URL, headers=auth_header("not.a.jwt")).status_code == 401
    assert client.get(URL, headers={"Authorization": "Basic abc"}).status_code == 401
