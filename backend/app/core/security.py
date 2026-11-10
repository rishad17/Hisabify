"""Authentication: verify the Supabase access token sent by the frontend.

Flow:
  1. The user logs in through Supabase Auth in the browser (supabase-js).
  2. Supabase issues a signed JWT access token.
  3. The frontend sends it on every API call:  Authorization: Bearer <token>
  4. This module checks the signature, expiry, audience and issuer, then takes the
     user's id from the `sub` claim. Every database query is scoped to that id.

Signing keys:
  * New Supabase projects sign tokens with an asymmetric key (ES256/RS256) and publish
    the public keys at  {SUPABASE_URL}/auth/v1/.well-known/jwks.json  — we fetch and
    cache them. No secret needs to be stored on our server.
  * Older projects may still use a shared secret (HS256). That is supported only if
    SUPABASE_JWT_SECRET is configured.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError

ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
AUDIENCE = "authenticated"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None


class SigningKeySource(Protocol):
    """Anything that can return the public key for a token (PyJWKClient, or a test fake)."""

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK: ...


def _unauthorized(message: str = "Invalid or expired session. Please sign in again.") -> AppError:
    return AppError("unauthorized", message, status_code=401)


class TokenVerifier:
    def __init__(
        self,
        supabase_url: str,
        jwt_secret: str | None = None,
        key_source: SigningKeySource | None = None,
    ) -> None:
        self.issuer = f"{supabase_url}/auth/v1"
        self.jwt_secret = jwt_secret
        self.key_source = key_source or jwt.PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=600,  # re-fetch keys at most every 10 min (handles key rotation)
            timeout=5,
        )

    def verify(self, token: str) -> CurrentUser:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise _unauthorized() from exc

        # Pick the key based on the algorithm, and only ever accept that algorithm.
        # This blocks "alg confusion" tricks such as alg=none or HS256-signed-with-public-key.
        alg = header.get("alg")
        key: Any
        if alg in ASYMMETRIC_ALGORITHMS:
            try:
                key = self.key_source.get_signing_key_from_jwt(token).key
            except jwt.PyJWKClientError as exc:
                raise _unauthorized() from exc
        elif alg == "HS256" and self.jwt_secret:
            key = self.jwt_secret
        else:
            raise _unauthorized()

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience=AUDIENCE,
                issuer=self.issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
                leeway=10,  # tolerate small clock differences
            )
        except jwt.ExpiredSignatureError as exc:
            raise _unauthorized("Your session has expired. Please sign in again.") from exc
        except jwt.PyJWTError as exc:
            raise _unauthorized() from exc

        # The public anon key is also a JWT — make sure this is a real signed-in user.
        if claims.get("role") != "authenticated":
            raise _unauthorized()
        try:
            user_id = uuid.UUID(claims["sub"])
        except (ValueError, TypeError) as exc:
            raise _unauthorized() from exc

        return CurrentUser(id=user_id, email=claims.get("email"))


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency: add `user: CurrentUser = Depends(get_current_user)` to a route."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Sign in required.")
    verifier: TokenVerifier | None = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        raise AppError("auth_not_configured", "SUPABASE_URL is not set.", status_code=503)
    return verifier.verify(credentials.credentials)
