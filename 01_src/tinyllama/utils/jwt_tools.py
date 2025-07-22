import time
from pathlib import Path
import json, os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt
from jose.utils import base64url_encode
import tempfile

# ─── Paths & Constants ────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[3]

# 1. Prefer explicit env var for testing, CI, or special runs
env_data_dir = os.getenv("TINYLLAMA_DATA_DIR")

if env_data_dir:
    DATA_DIR = Path(env_data_dir)
elif os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    DATA_DIR = Path("/tmp/02_tests/api/data")
else:
    DATA_DIR = ROOT_DIR / "02_tests" / "api" / "data"

# 2. Paths that depend on DATA_DIR
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
def make_token(
    *,
    exp_delta: int = 300,
    aud: str = "dummy",
    iss: str = "https://example.com/dev",
) -> str:
    """
    Helper for tests only: return a freshly-signed RS256 JWT.

    Parameters
    ----------
    exp_delta : int
        Seconds from 'now' until expiration (+ve) or since expiration (-ve).
    aud : str
        Audience claim the handler expects (COGNITO_CLIENT_ID in tests).
    iss : str
        Issuer claim the handler expects
        (e.g. 'https://cognito-idp.eu-central-1.amazonaws.com/test-pool').

    Returns
    -------
    str
        Compact JWS (header.payload.signature) as required by handler.verify_jwt.
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
        _KEY_BYTES,             # existing private key bytes from your module
        algorithm="RS256",
        headers={"kid": KID},    # existing constant in your module
    )
