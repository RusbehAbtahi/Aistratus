from pathlib import Path
import base64, json
from cryptography.hazmat.primitives import serialization
import pytest, os
from jose import jwt
from tinyllama.utils.jwt_tools import make_token

DATA_DIR = Path(__file__).parent / "data"
RSA_PEM  = DATA_DIR / "rsa_test_key.pem"
JWKS     = DATA_DIR / "mock_jwks.json"
AUD      = os.getenv("COGNITO_CLIENT_ID", "dummy-aud")

def _mod_exp_from_pem():
    priv = serialization.load_pem_private_key(RSA_PEM.read_bytes(), None)
    pubn = priv.public_key().public_numbers()
    n = base64.urlsafe_b64encode(pubn.n.to_bytes((pubn.n.bit_length()+7)//8, "big")).rstrip(b"=")
    e = base64.urlsafe_b64encode(pubn.e.to_bytes((pubn.e.bit_length()+7)//8, "big")).rstrip(b"=")
    return n.decode(), e.decode()

def test_keypair_matches_jwks():
    n, e = _mod_exp_from_pem()
    kid = "test-key"
    jwks = json.loads(JWKS.read_text())["keys"][0]
    assert (jwks["kid"], jwks["n"], jwks["e"]) == (kid, n, e)

def test_direct_jwt_roundtrip():
    from tinyllama.utils.jwt_tools import make_token
    token = make_token(aud=AUD)
    with open(JWKS) as f:
        jwks = json.load(f)
    payload = jwt.decode(token, jwks, algorithms=["RS256"], audience=AUD)
    assert payload["email"] == "tester@example.com"
