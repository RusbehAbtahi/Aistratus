"""
tinyllama.utils.auth
--------------------
Single, canonical place for **all** JWT helpers used by tests, API, and Lambda
so we never suffer the “unknown-kid / audience mismatch” bug again.

• make_token(...)     – test-only helper (uses local RSA key from jwt_tools.py)
• verify_jwt(token)   – runtime helper (verifies RS256 token, returns claims)
"""

from __future__ import annotations

import json, os, time
from pathlib import Path
from typing import Dict, Any

from jose import jwt, jwk, JWTError

from jose.utils import base64url_decode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# ─────────────────────────────────────────────────────────────────────────────
# 1)  Test-token generator  (imported — we DO NOT duplicate code)
# ─────────────────────────────────────────────────────────────────────────────
from .jwt_tools import make_token                    # already creates key & JWKS
#   → keep as-is; nothing else to do here.


# ─────────────────────────────────────────────────────────────────────────────
# 2)  Runtime verifier  (used by API FastAPI & Lambda router)
# ─────────────────────────────────────────────────────────────────────────────
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID", "dummy-aud")
# issuer defaults to Cognito user-pool URL; override in tests if needed
COGNITO_ISSUER        = os.getenv(
    "COGNITO_ISSUER",
    "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_AP5Xpw0cL",
)

# local JWKS file for pytest; in production the verifier downloads JWKS lazily
_LOCAL_JWKS_PATH = Path(os.getenv("LOCAL_JWKS_PATH", ""))
_cached_jwks: Dict[str, Dict[str, Any]] = {}          # kid → jwk entry


def _load_jwks() -> Dict[str, Dict[str, Any]]:
    """Load JWKS either from local file (tests) or from the Cognito URL."""
    if _LOCAL_JWKS_PATH.is_file():
        data = json.loads(_LOCAL_JWKS_PATH.read_text())
    else:
        import requests
        resp = requests.get(f"{COGNITO_ISSUER}/.well-known/jwks.json", timeout=5)
        resp.raise_for_status()
        data = resp.json()

    return {key["kid"]: key for key in data["keys"]}


def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Decode & validate an RS256 JWT.

    Returns
    -------
    claims : dict
        The token payload if signature, exp, aud, iss are all valid.

    Raises
    ------
    jose.JWTError (or subclass) if verification fails.
    """
    if not token:
        raise JWTError("Empty token")

    # Header → get kid
    header = jwt.get_unverified_header(token)
    kid    = header.get("kid")
    if not kid:
        raise JWTError("Missing kid")

    # Lazy-load or refresh JWKS
    global _cached_jwks
    if kid not in _cached_jwks:
        _cached_jwks = _load_jwks()                   # refresh whole set
    jwk_entry = _cached_jwks.get(kid)
    if jwk_entry is None:
        raise JWTError("Unknown kid")

    # Decode
    return jwt.decode(
        token,
        jwk.construct(jwk_entry),
        algorithms=["RS256"],
        audience=COGNITO_APP_CLIENT_ID,
        issuer=COGNITO_ISSUER,
    )


__all__ = ["make_token", "verify_jwt"]
