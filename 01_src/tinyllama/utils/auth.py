# tinyllama/utils/auth.py
# ---------------------------------------------------------------------------
# Re-written to remove the third-party “requests” dependency.
# Uses urllib.request instead, so no extra packages are required
# inside the Lambda zip or layer.
# ---------------------------------------------------------------------------

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any
import urllib.request
import urllib.error

from jose import jwt, jwk, JWTError

# ---------------------------------------------------------------------------
#  Test helper (kept unchanged)
# ---------------------------------------------------------------------------
from .jwt_tools import make_token                      # noqa: F401

# ---------------------------------------------------------------------------
#  Runtime configuration (resolved via SSM)
# ---------------------------------------------------------------------------
from tinyllama.utils.ssm import get_id

AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
COGNITO_CLIENT_ID = get_id("cognito_client_id")
COGNITO_ISSUER = (
    f"https://cognito-idp.{AWS_REGION}.amazonaws.com/"
    f"{get_id('cognito_user_pool_id')}"
)

# Optional local JWKS override for unit tests
_LOCAL_JWKS_PATH = Path(os.getenv("LOCAL_JWKS_PATH", ""))
_cached_jwks: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
def _load_jwks() -> Dict[str, Dict[str, Any]]:
    """
    Return a dict mapping kid -> JWK entry.
    – Uses LOCAL_JWKS_PATH during tests.
    – Falls back to Cognito’s JWKS endpoint in Lambda.
    """
    print("DBG jwks-path:", _LOCAL_JWKS_PATH if _LOCAL_JWKS_PATH else ".")
    if _LOCAL_JWKS_PATH.is_file():
        data = json.loads(_LOCAL_JWKS_PATH.read_text())
    else:
        url = f"{COGNITO_ISSUER}/.well-known/jwks.json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    print("DBG jwks kids:", [k["kid"] for k in data["keys"]])
    return {k["kid"]: k for k in data["keys"]}

# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------
def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Validate an RS256 Cognito JWT.

    Raises jose.JWTError on any failure.
    Returns decoded claims dict when valid.
    """
    print("DBG raw-token-len:", len(token))
    segs = token.count(".") + 1
    print("DBG segments:", segs)
    if segs != 3:
        raise JWTError("token is not header.payload.signature")

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        print("DBG header-decode-error:", exc)
        raise

    kid = header.get("kid")
    if not kid:
        raise JWTError("missing kid")

    global _cached_jwks
    if kid not in _cached_jwks:
        _cached_jwks = _load_jwks()
    jwk_entry = _cached_jwks.get(kid)
    if jwk_entry is None:
        raise JWTError("unknown kid")

    return jwt.decode(
        token,
        jwk.construct(jwk_entry),
        algorithms=["RS256"],
        options={"verify_aud": False},
        issuer=COGNITO_ISSUER,
    )

__all__ = ["make_token", "verify_jwt"]
