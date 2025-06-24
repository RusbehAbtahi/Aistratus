from datetime import datetime, timedelta
from jose import jwt
import json, os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

RSA_KEY_PATH = "02_tests/api/data/rsa_test_key.pem"
JWKS_PATH    = "02_tests/api/data/mock_jwks.json"
KID          = "test-key"

def _ensure_keypair():
    if os.path.exists(RSA_KEY_PATH): return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with open(RSA_KEY_PATH, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    pub = key.public_key().public_numbers()
    jwk_obj = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": KID,
        "n": jwt.base64url_encode(pub.n.to_bytes(256, "big")).decode(),
        "e": jwt.base64url_encode(pub.e.to_bytes(3, "big")).decode(),
    }
    with open(JWKS_PATH, "w") as f:
        json.dump({"keys":[jwk_obj]}, f, indent=2)

_ensure_keypair()

from cryptography.hazmat.primitives import serialization
from jose import jwk

with open(RSA_KEY_PATH, "rb") as f:
    _PRIVATE = serialization.load_pem_private_key(f.read(), password=None)

def make_token(exp_delta=300, aud="dummy"):
    now = datetime.utcnow()
    payload = {
        "sub": "test-user",
        "email": "tester@example.com",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta)).timestamp()),
        "iss": "https://example.com/dev",   # ignored by dev verifier
        "aud": aud,
    }
    return jwt.encode(payload, _PRIVATE, algorithm="RS256", headers={"kid": KID})