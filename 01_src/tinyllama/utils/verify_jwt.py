"""
tinyllama.utils.auth
Single place for JWT helpers shared by API and Lambda.
"""
import os, json, time, requests
from pathlib import Path
from jose import jwt, jwk
from jose.exceptions import JWTError

LOCAL_JWKS_PATH = os.getenv("LOCAL_JWKS_PATH")            # tests
COGNITO_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")       # prod
APP_CLIENT_ID   = os.getenv("COGNITO_APP_CLIENT_ID")      # aud claim

# ----------------------------------------------------------------------
def _load_jwks() -> dict:
    """
    Return {kid: jwk} mapping, from local file (tests) or Cognito URL (prod).
    """
    if LOCAL_JWKS_PATH and Path(LOCAL_JWKS_PATH).exists():
        data = json.loads(Path(LOCAL_JWKS_PATH).read_text())
    else:
        url = f"https://cognito-idp.{COGNITO_POOL_ID.split('_')[0]}.amazonaws.com/{COGNITO_POOL_ID}/.well-known/jwks.json"
        data = requests.get(url, timeout=5).json()
    return {k["kid"]: k for k in data["keys"]}

_JWKS = _load_jwks()        # cache at import

# ----------------------------------------------------------------------
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

    return jwt.decode(
        token,
        jwk.construct(key),
        algorithms=["RS256"],
        audience=APP_CLIENT_ID,
        issuer=f"https://cognito-idp.{COGNITO_POOL_ID.split('_')[0]}.amazonaws.com/{COGNITO_POOL_ID}",
    )

# re-export for tests
from .jwt_tools import make_token
__all__ = ["verify_jwt", "make_token"]
