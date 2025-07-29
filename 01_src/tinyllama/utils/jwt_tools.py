import time
from pathlib import Path
import json
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt
from jose.utils import base64url_encode

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[3]

# 1) Prefer explicit env var for testing, CI, or special runs
env_data_dir = os.getenv("TINYLLAMA_DATA_DIR")

if env_data_dir:
    DATA_DIR = Path(env_data_dir)
elif os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    DATA_DIR = Path("/tmp/02_tests/api/data")
else:
    DATA_DIR = ROOT_DIR / "02_tests" / "api" / "data"

# 2) Paths that depend on DATA_DIR
RSA_KEY_PATH = DATA_DIR / "rsa_test_key.pem"
JWKS_PATH    = DATA_DIR / "mock_jwks.json"
KID          = "test-key"

# Ensure test-data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Generate RSA key + JWKS once
# ---------------------------------------------------------------------------
def _ensure_keypair() -> None:
    if RSA_KEY_PATH.exists() and JWKS_PATH.exists():
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Write private key (PEM)
    RSA_KEY_PATH.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    # Build JWKS entry
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

# ---------------------------------------------------------------------------
# Read private key bytes for signing
# ---------------------------------------------------------------------------
_KEY_BYTES = RSA_KEY_PATH.read_bytes()

# ---------------------------------------------------------------------------
# Helper: issue tokens for tests
# ---------------------------------------------------------------------------
def make_token(
    *,
    exp_delta: int = 300,
    aud: str = "dummy",
    iss: str = "https://example.com/dev",
) -> str:
    """
    Return a freshly-signed RS256 JWT for unit tests.

    Parameters
    ----------
    exp_delta : seconds until expiration (positive) or since expiration (negative)
    aud       : audience claim expected by the verifier
    iss       : issuer claim expected by the verifier
    """
    iat = int(time.time())
    payload = {
        "sub":   "test-user",
        "email": "tester@example.com",
        "iat":   iat,
        "exp":   iat + exp_delta,
        "iss":   iss,
        "aud":   aud,
    }
    return jwt.encode(
        payload,
        _KEY_BYTES,
        algorithm="RS256",
        headers={"kid": KID},
    )
