from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from jose import jwt, jwk, JWSError
import requests, json, time
from .config import settings

def _load_jwks():
    resp = requests.get(settings.jwks_url, timeout=5)
    resp.raise_for_status()
    return {k["kid"]: k for k in resp.json()["keys"]}

_JWKS = _load_jwks()

def verify_jwt(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        token = authorization.split()[1]
        header = jwt.get_unverified_header(token)
        key = _JWKS[header["kid"]]
        jwt.decode(
            token,
            jwk.construct(key),
            algorithms=["RS256"],
            audience=settings.client_id,
            issuer=settings.issuer,
        )
    except (KeyError, JWSError):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid or expired token")