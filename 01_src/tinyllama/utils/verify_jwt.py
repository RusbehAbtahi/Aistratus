"""
tinyllama.utils.verify_jwt
Single place for JWT helpers shared by API and Lambda.
"""

import os
import json
import time
import requests
from pathlib import Path

from jose import jwt, jwk
from jose.exceptions import JWTError

from tinyllama.utils.ssm import get_id

# ─────────────────────────────────────────────────────────────────────────────
# Configuration via SSM
# ─────────────────────────────────────────────────────────────────────────────
LOCAL_JWKS_PATH = os.getenv("LOCAL_JWKS_PATH")      # tests only
COGNITO_POOL_ID = get_id("cognito_user_pool_id")    # from SSM
APP_CLIENT_ID   = get_id("cognito_client_id")       # from SSM

# ─────────────────────────────────────────────────────────────────────────────
def _load_jwks() -> dict:
    """
    Return {kid: jwk} mapping, from local file (tests) or Cognito URL (prod).
    """
    if LOCAL_JWKS_PATH and Path(LOCAL_JWKS_PATH).exists():
        data = json.loads(Path(LOCAL_JWKS_PATH).read_text())
    else:
        region = COGNITO_POOL_ID.split("_", 1)[0]
        url = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{COGNITO_POOL_ID}/.well-known/jwks.json"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

    return {k["kid"]: k for k in data["keys"]}

_JWKS = _load_jwks()        # cache at import

# ─────────────────────────────────────────────────────────────────────────────
def verify_jwt(token: str) -> dict:
    """
    Raises JWTError if token invalid, else returns decoded payload.
    """
    header = jwt.get_unverified_header(token)

    # refresh JWKS once if kid missing
    key = _JWKS.get(header["kid"])
    if not key:
        _JWKS.update(_load_jwks())
        key = _JWKS.get(header["kid"])
        if not key:
            raise JWTError("kid not found in JWKS")

    region = COGNITO_POOL_ID.split("_", 1)[0]
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{COGNITO_POOL_ID}"

    return jwt.decode(
        token,
        jwk.construct(key),
        algorithms=["RS256"],
        audience=APP_CLIENT_ID,
        issuer=issuer,
    )

# re-export for tests
from .jwt_tools import make_token
__all__ = ["verify_jwt", "make_token"]
