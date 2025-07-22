import json
import time
import pytest

from tinyllama.utils import jwt_tools as jt
from tinyllama.router.handler import lambda_handler
from tinyllama.utils import ssm as _ssm  # patched in tests

# --- PRINT KEY/JWKS n/e DEBUG ---
from cryptography.hazmat.primitives import serialization

with open("02_tests/api/data/rsa_test_key.pem", "rb") as f:
    priv = serialization.load_pem_private_key(f.read(), password=None)
    pub = priv.public_key().public_numbers()
    print("DEBUG SIGNER n:", pub.n)
    print("DEBUG SIGNER e:", pub.e)

with open("02_tests/api/data/mock_jwks.json") as f:
    jwks = json.load(f)
    jwk = jwks["keys"][0]
    import base64
    def url_b64decode(val):
        pad = '=' * (-len(val) % 4)
        return base64.urlsafe_b64decode(val + pad)
    print("DEBUG JWKS n:", int.from_bytes(url_b64decode(jwk['n']), "big"))
    print("DEBUG JWKS e:", int.from_bytes(url_b64decode(jwk['e']), "big"))

# --------------------------------------------------------------------------- #
# CONSTANTS FOR TEST CLAIMS
# --------------------------------------------------------------------------- #
AUD = "local-test-client-id"
ISS = "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"


# --------------------------------------------------------------------------- #
# HELPER-PATCH: fake SSM look-ups so handler does not hit AWS
# --------------------------------------------------------------------------- #
def _patch_ssm(monkeypatch):
    def _fake_get_id(name: str) -> str:          # type: ignore[override]
        if name == "COGNITO_USER_POOL_ID":
            return "test-pool"
        if name == "COGNITO_CLIENT_ID":
            return AUD
        raise KeyError(name)
    monkeypatch.setattr(_ssm, "get_id", _fake_get_id, raising=True)

def _event(token: str, body: dict) -> dict:
    return {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body),
    }

# --------------------------------------------------------------------------- #
# TESTS
# --------------------------------------------------------------------------- #
def test_happy_path(monkeypatch):
    _patch_ssm(monkeypatch)
    print("DEBUG TOKEN AUD:", AUD)
    print("DEBUG TOKEN ISS:", ISS)
    token = jt.make_token(
        iss=ISS,
        aud=AUD,
        exp_delta=3600,          # valid for 1 h
    )
    resp = lambda_handler(_event(token, {"prompt": "hi", "idle": 5}), None)
    assert resp["statusCode"] == 202

def test_schema_fail(monkeypatch):
    _patch_ssm(monkeypatch)

    token = jt.make_token(iss=ISS, aud=AUD)
    resp = lambda_handler(_event(token, {"prompt": "hi", "idle": 0}), None)
    assert resp["statusCode"] == 400
    assert "idle" in resp["body"]

def test_bad_token(monkeypatch):
    _patch_ssm(monkeypatch)

    resp = lambda_handler(_event("abc.def.ghi", {"prompt": "hi", "idle": 5}), None)
    assert resp["statusCode"] in (401, 403)

def test_expired_token(monkeypatch):
    _patch_ssm(monkeypatch)

    token = jt.make_token(
        iss=ISS,
        aud=AUD,
        exp_delta=-3600,         # expired 1 h ago
    )
    resp = lambda_handler(_event(token, {"prompt": "hi", "idle": 5}), None)
    assert resp["statusCode"] == 401
