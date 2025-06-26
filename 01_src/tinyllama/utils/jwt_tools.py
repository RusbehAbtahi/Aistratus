
import time
from pathlib import Path
import json, os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt
from jose.utils import base64url_encode

# ─── Paths & Constants ────────────────────────────────────────────────────────
# point at the canonical test-data folder, one level up
ROOT_DIR     = Path(__file__).resolve().parents[3]
DATA_DIR     = ROOT_DIR / "02_tests" / "api" / "data"

RSA_KEY_PATH = DATA_DIR / "rsa_test_key.pem"
JWKS_PATH    = DATA_DIR / "mock_jwks.json"
KID          = "test-key"

# ─── Ensure test-data directory exists ───────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── ❶ Generate RSA key + JWKS once ───────────────────────────────────────────
def _ensure_keypair() -> None:
    if RSA_KEY_PATH.exists() and JWKS_PATH.exists():
        return

    # generate new 2048-bit RSA key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # write private PEM
    RSA_KEY_PATH.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    # build JWKS entry
    pub = key.public_key().public_numbers()
    jwk_obj = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": KID,
        "n": base64url_encode(pub.n.to_bytes(256, "big")).decode(),
        "e": base64url_encode(pub.e.to_bytes(3,   "big")).decode(),
    }
    JWKS_PATH.write_text(json.dumps({"keys": [jwk_obj]}, indent=2))

_ensure_keypair()

# ─── ❷ Tell api/security where to load JWKS from ────────────────────────────
os.environ.setdefault("LOCAL_JWKS_PATH", str(JWKS_PATH))

# ─── ❸ Read the *bytes* of the private key for signing ───────────────────────
_KEY_BYTES = RSA_KEY_PATH.read_bytes()

# ─── ❹ Helper to issue tokens for tests ───────────────────────────────────────
def make_token(*, exp_delta: int = 300, aud: str = "dummy") -> str:
    """
    Return a freshly-signed RS256 JWT with the given audience.
    """
    iat = int(time.time())            # true epoch seconds
    payload = {
        "sub":   "test-user",
        "email": "tester@example.com",
        "iat":   iat,
        "exp":   iat + exp_delta,
        "iss":   "https://example.com/dev",
        "aud":   aud,
    }
    return jwt.encode(
        payload,
        _KEY_BYTES,
        algorithm="RS256",
        headers={"kid": KID},
    )
