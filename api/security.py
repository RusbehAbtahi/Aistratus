# api/security.py
from typing import Optional
from fastapi import Header, HTTPException, status
from jose import jwt, JWTError, ExpiredSignatureError
import json, os, pathlib, requests
from .config import settings

# ─── Load JWKS ────────────────────────────────────────────────────────────────
def _load_jwks() -> dict[str, dict]:
    local = os.getenv("LOCAL_JWKS_PATH")
    if local and pathlib.Path(local).exists():
        with open(local, "r", encoding="utf-8") as f:
            return {k["kid"]: k for k in json.load(f)["keys"]}

    resp = requests.get(settings.jwks_url, timeout=5)
    resp.raise_for_status()
    return {k["kid"]: k for k in resp.json()["keys"]}

_JWKS: dict[str, dict] = _load_jwks()

# ─── Decode helper (auto-reload once) ────────────────────────────────────────
def _decode_with_auto_reload(token: str, header: dict[str, str]):
    kid = header["kid"]
    key = _JWKS.get(kid)
    if key is None:                 # refresh cache exactly once
        _JWKS.update(_load_jwks())
        key = _JWKS.get(kid)
    if key is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Unknown kid")

    return jwt.decode(
        token,
        key,                         # pass raw JWK dict, not jwk.construct()
        algorithms=["RS256"],
        audience=settings.client_id,
        options={"verify_iss": False},
    )

# ─── FastAPI dependency ──────────────────────────────────────────────────────
def verify_jwt(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        scheme, token = authorization.split(maxsplit=1)
        if scheme.lower() != "bearer":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Wrong auth scheme")

        header = jwt.get_unverified_header(token)
        _decode_with_auto_reload(token, header)

    except ExpiredSignatureError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Token expired")
    except JWTError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid or expired token")
