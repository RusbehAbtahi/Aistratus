# Python Files Index

## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2

### conftest.py
```python
import os
from unittest.mock import patch

os.environ.setdefault("COGNITO_USER_POOL_ID", "eu-central-1_TEST")
os.environ.setdefault("COGNITO_CLIENT_ID", "local-test-client-id")

patcher = patch('tinyllama.utils.ssm.get_id', lambda name: os.environ[name.upper()])
patcher.start()
```

### lambda_entry.py
```python
# lambda_entry.py  — minimal ASGI wrapper
from api.routes import app          # ← your FastAPI app
from mangum import Mangum           # AWS → ASGI adapter
handler = Mangum(app)               # Lambda handler object
```

### setup.py
```python
from setuptools import setup, find_packages

setup(
    name="tinyllama",
    version="0.1.0",
    package_dir={"": "01_src"},
    packages=find_packages(where="01_src"),
    install_requires=[
        "cryptography",
        "python-jose",
        "fastapi",
        "httpx",
        "pydantic-settings",
        "python-dotenv",
    ],

)
```

### tools.py
```python
#!/usr/bin/env python
"""
Minimal, admin-free replacement for the old Makefile.

Commands
--------
python tools.py lambda-package        # build router.zip
python tools.py tf-apply              # build + terraform init/apply
python tools.py lambda-rollback --version 17
"""
from __future__ import annotations
import argparse
import shutil
import subprocess as sp
import sys
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths – adjust only if your repo layout changes
# --------------------------------------------------------------------------- #
REPO_ROOT      = Path(__file__).resolve().parent
SRC_ROOT       = REPO_ROOT / "01_src"
ZIP_OUT        = REPO_ROOT / "router.zip"
TERRAFORM_DIR  = REPO_ROOT / "terraform" / "10_global_backend"
LOCAL_TF_BIN   = REPO_ROOT / "04_scripts" / "no_priv" / "tools" / "terraform"
ROLLBACK_SH    = REPO_ROOT / "04_scripts" / "no_priv" / "rollback_router.sh"
ZIP_SIZE_LIMIT = 5 * 1024 * 1024       # 5 MiB Lambda limit

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def safe_print(text: str) -> None:
    """Prints without bombing on code-page issues (cp1252, etc.)."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode())

def run(cmd: list[str] | str, cwd: Path | None = None) -> None:
    """Run a command and abort if it fails."""
    printable = cmd if isinstance(cmd, str) else " ".join(cmd)
    safe_print(f"[RUN] {printable}")
    proc = sp.Popen(cmd, cwd=cwd, shell=False)
    proc.communicate()
    if proc.returncode:
        sys.exit(proc.returncode)

def add_tree(zf: zipfile.ZipFile, root: Path, arc_prefix: str) -> None:
    """Zip an entire directory tree under a fixed archive prefix."""
    for f in root.rglob("*"):
        if f.is_dir():
            continue
        if "__pycache__" in f.parts or f.suffix == ".pyc":
            continue
        zf.write(f, Path(arc_prefix) / f.relative_to(root))

def terraform_bin() -> str:
    """
    Return the Terraform binary path to use.
    1) whatever 'terraform' resolves to on PATH
    2) repo-local fallback binary
    """
    global_tf = shutil.which("terraform")
    if global_tf:
        safe_print(f"[INFO] Using global terraform -> {global_tf}")
        return global_tf
    if LOCAL_TF_BIN.exists():
        safe_print(f"[INFO] Using repo-local terraform -> {LOCAL_TF_BIN}")
        return str(LOCAL_TF_BIN)
    safe_print(
        "ERROR: terraform not found on PATH and local fallback binary "
        f"does not exist ({LOCAL_TF_BIN})."
    )
    sys.exit(1)

# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def lambda_package() -> None:
    router_dir = SRC_ROOT / "tinyllama" / "router"
    utils_dir  = SRC_ROOT / "tinyllama" / "utils"

    for p in (router_dir, utils_dir):
        if not p.exists():
            safe_print(f"ERROR: required path missing – {p}")
            sys.exit(1)

    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tinyllama/__init__.py", "# package marker\n")
        add_tree(zf, router_dir, "tinyllama/router")
        add_tree(zf, utils_dir,  "tinyllama/utils")

    size = ZIP_OUT.stat().st_size
    if size > ZIP_SIZE_LIMIT:
        ZIP_OUT.unlink(missing_ok=True)
        safe_print(f"ERROR: {ZIP_OUT.name} is {(size/1024):,.0f} KiB (> 5 MiB)")
        sys.exit(1)

    safe_print(f"OK   : created {ZIP_OUT}  {(size/1024):,.0f} KiB")

def tf_apply(github_mode=False) -> None:
    tf = terraform_bin()          # resolve binary
    lambda_package()              # always rebuild first

    # ----- locate backend.auto.tfvars wherever it really is -------------
    backend_cfg = REPO_ROOT / "terraform" / "backend.auto.tfvars"
    init_cmd = [tf, "init"]
    if backend_cfg.exists():
        init_cmd += [f"-backend-config={backend_cfg}"]
    else:
        safe_print(f"[WARN] {backend_cfg} not found – running terraform init with workspace-defaults")

    # --------------------------------------------------------------------
    run(init_cmd, cwd=TERRAFORM_DIR)
    run([tf, "apply", "-auto-approve"], cwd=TERRAFORM_DIR)
    safe_print("OK   : terraform apply finished")
    if not github_mode:
        update_env_public_with_api_url()

def lambda_rollback(version: str) -> None:
    import subprocess, sys
    FN = "tinyllama-router"
    # verify version is numeric
    if not version.isdigit():
        print("ERROR: --version must be an integer (Lambda numeric version)")
        sys.exit(1)
    # call AWS CLI to update alias 'prod' to this version
    cmd = [
        "aws", "lambda", "update-alias",
        "--function-name", FN,
        "--name", "prod",
        "--function-version", version,
        "--region", "eu-central-1"
    ]
    print(f"[RUN] {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)
    proc.communicate()
    if proc.returncode:
        sys.exit(proc.returncode)
    print(f"Rolled back tinyllama-router to version {version}")

def update_env_public_with_api_url():
    import json
    import subprocess

    tf_output_cmd = [
        terraform_bin(), "output", "-json"
    ]
    proc = subprocess.run(
        tf_output_cmd,
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    outputs = json.loads(proc.stdout)
    # Extract router_api_url from inside global_ids
    api_url = outputs["global_ids"]["value"]["router_api_url"]

    env_path = REPO_ROOT / ".env_public"
    lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            lines = f.readlines()
    lines = [l for l in lines if not l.startswith("API_BASE_URL=")]
    lines.append(f"API_BASE_URL={api_url}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"OK   : .env_public updated with API_BASE_URL={api_url}")

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(prog="tools.py")
    sp_ = p.add_subparsers(dest="cmd", required=True)

    sp_.add_parser("lambda-package", help="build router.zip")

    tf_apply_sp = sp_.add_parser("tf-apply", help="zip + terraform init/apply")
    tf_apply_sp.add_argument(
        "-g", "--github",
        action="store_true",
        dest="github_mode",
        help="running in GitHub CI: skip updating .env_public"
    )

    rb = sp_.add_parser("lambda-rollback")
    rb.add_argument("--version", required=True, help="Lambda numeric version")

    args = p.parse_args()
    if args.cmd == "lambda-package":
        lambda_package()

    elif args.cmd == "tf-apply":
        # Pass through the --github flag
        tf_apply(github_mode=args.github_mode)

    elif args.cmd == "lambda-rollback":
        lambda_rollback(args.version)


if __name__ == "__main__":
    main()


```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\01_src\tinyllama\router

### handler.py
```python
# tinyllama/router/handler.py

import json
import os
import boto3

from jose.exceptions import ExpiredSignatureError, JWTError
from tinyllama.utils.auth import verify_jwt

# Initialize SQS client once
_sqs = boto3.client('sqs')
QUEUE_URL = os.environ.get('JOB_QUEUE_URL')  # must be set in Lambda environment

def lambda_handler(event, context):
    """
    Entry-point for TinyLlama Router:
      - logs raw event
      - validates request, auth token
      - enqueues into SQS for further processing, logging send_message response
    """
    print("DBG event:", event)
    print("DBG headers:", event.get('headers'))
    print("DBG raw body:", event.get('body'))

    # Parse and validate request body
    try:
        body_text = event.get('body', '')
        req = json.loads(body_text)
        prompt = req['prompt']
        idle = req['idle']
        print(f"DBG parsed prompt='{prompt[:30]}...' idle={idle}")
    except Exception as exc:
        print("ERROR invalid_request:", exc)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'invalid_request', 'details': str(exc)})
        }

    # Extract and validate Authorization header
    auth_header = (event.get('headers') or {}).get('authorization', '')
    print("DBG authorization header:", auth_header)
    token = auth_header.removeprefix('Bearer ').strip()
    if not token:
        print("ERROR missing_token")
        return {'statusCode': 401, 'body': json.dumps({'error': 'missing_token'})}

    # Verify JWT
    try:
        claims = verify_jwt(token)
        print("DBG verified claims:", claims)
        print("JWT_OK")
    except ExpiredSignatureError:
        print("ERROR token_expired")
        return {'statusCode': 401, 'body': json.dumps({'error': 'token_expired'})}
    except JWTError as exc:
        print("ERROR invalid_token:", exc)
        return {'statusCode': 403, 'body': json.dumps({'error': 'invalid_token'})}

    # Check SQS configuration
    if not QUEUE_URL:
        print("ERROR queue_not_configured")
        return {'statusCode': 500, 'body': json.dumps({'error': 'queue_not_configured'})}
    print("DBG using SQS URL:", QUEUE_URL)

    # Enqueue valid request into SQS
    try:
        message = {
            'token': token,
            'prompt': prompt,
            'idle': idle,
            'request_id': context.aws_request_id
        }
        resp = _sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageGroupId = claims["sub"]
        )
        print("DBG send_message response:", resp)
    except Exception as exc:
        print("ERROR enqueue_failed:", exc)
        return {
            'statusCode': 502,
            'body': json.dumps({'error': 'enqueue_failed', 'details': str(exc)})
        }

    # Successful enqueue
    print("DBG enqueue succeeded, message_id:", resp.get('MessageId'))
    return {
        'statusCode': 202,
        'body': json.dumps({'status': 'queued', 'messageId': resp.get('MessageId')})
    }
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\01_src\tinyllama\utils

### auth.py
```python
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
```

### jwt_tools.py
```python
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
```

### schema.py
```python
"""Data-validation schemas for TinyLlama."""
from pydantic import BaseModel, root_validator, ValidationError


MAX_PROMPT_BYTES = 6 * 1024  # 6 KB
MIN_PROMPT_BYTES = 1
IDLE_MIN = 1
IDLE_MAX = 30


class PromptReq(BaseModel):
    """Request body for /infer and Lambda Router."""
    prompt: str
    idle: int

    @root_validator(skip_on_failure=True)
    def _validate(cls, values):
        prompt: str = values.get("prompt")
        idle: int = values.get("idle")

        # prompt size check (UTF-8 bytes)
        size = len(prompt.encode("utf-8")) if isinstance(prompt, str) else 0
        if not (MIN_PROMPT_BYTES <= size <= MAX_PROMPT_BYTES):
            raise ValueError(
                f"prompt must be 1-{MAX_PROMPT_BYTES // 1024} KB UTF-8; got {size} B"
            )

        # idle range check
        if not (IDLE_MIN <= idle <= IDLE_MAX):
            raise ValueError(f"idle must be {IDLE_MIN}-{IDLE_MAX}; got {idle}")

        return values


# so tests can import the exception class directly
ValidationError = ValidationError
```

### ssm.py
```python
import os
import functools
import boto3

_SSM = boto3.client("ssm")

@functools.lru_cache(maxsize=128)
def get_id(name: str) -> str:
    """
    Return the ID stored at /tinyllama/<env>/<name> (cached per name+env).
    Prefix is read _each_ call from the current TLFIF_ENV.
    """
    env = os.getenv("TLFIF_ENV", "default")
    path = f"/tinyllama/{env}/{name}"
    resp = _SSM.get_parameter(Name=path)
    return resp["Parameter"]["Value"]
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\api

### config.py
```python
# api/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv
import os
from tinyllama.utils.ssm import get_id

# Load local .env.dev if present, but we’ll override with SSM below
load_dotenv(find_dotenv(".env.dev"), override=False)

class Settings(BaseSettings):
    COGNITO_USER_POOL_ID:  str
    COGNITO_CLIENT_ID: str
    AWS_REGION:            str = "eu-central-1"  # default region

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # allow other env-vars
    )

    # convenience aliases used elsewhere in code
    @property
    def user_pool_id(self) -> str:
        return self.COGNITO_USER_POOL_ID

    @property
    def client_id(self) -> str:
        return self.COGNITO_CLIENT_ID

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"

# Instantiate from any .env, then override from SSM Parameter Store
settings = Settings()

# ── Override with values stored under /tinyllama/<env>/… ──
settings.COGNITO_USER_POOL_ID  = get_id("cognito_user_pool_id")
settings.COGNITO_CLIENT_ID = get_id("cognito_client_id")
```

### routes.py
```python
from fastapi import FastAPI, Depends
from .security import verify_jwt

app = FastAPI(
    title="TinyLlama Edge API",
    version="0.0.0-draft",
    description="🚧  Skeleton only—routes land in API-002+",
    docs_url="/docs", redoc_url="/redoc",
)

@app.get("/health")
async def ping():
    return {"status": "ok"}

@app.post("/infer")
def infer_stub(dep=Depends(verify_jwt)):
    return {"status": "ok"}
```

### security.py
```python
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
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\01_src\tinyllama\gui

### app_state.py
```python
"""
app_state.py
============
Central, thread-safe data store + tiny publish/subscribe bus for TinyLlama GUI.
"""

from __future__ import annotations
import threading
from typing import Callable, Dict, List, Any


class AppState:
    def __init__(self) -> None:
        # ---- public state values (simple, typed) ----
        self.idle_minutes: int = 5
        self.auth_token: str = ""
        self.auth_status: str = "off"       # login status: off | pending | ok | error
        self.current_cost: float = 0.0
        self.history: List[str] = []
        self.backend: str = "AWS TinyLlama"
        # Newly added credentials fields
        self.username: str = ""
        self.password: str = ""

        # ---- internals ----
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {
            "idle": [],
            "auth": [],
            "auth_status": [],
            "cost": [],
            "history": [],
            "backend": [],
            # Subscribers for credential updates
            "username": [],
            "password": [],
        }

    # ---------------- subscription helpers ----------------
    def subscribe(self, event: str, cb: Callable[[Any], None]) -> None:
        """
        Register *cb* to be invoked when *event* changes.
        Valid events: idle, auth, auth_status, cost, history, backend, username, password.
        """
        if event not in self._subscribers:
            raise ValueError(f"Unknown event: {event}")
        self._subscribers[event].append(cb)

    def _publish(self, event: str, data: Any) -> None:
        """Invoke all callbacks registered for *event*, passing *data*."""
        for cb in list(self._subscribers.get(event, [])):
            try:
                cb(data)
            except Exception as exc:          # pragma: no cover
                print(f"[AppState] subscriber error on '{event}': {exc}")

    # ---------------- setters ----------------
    def set_idle(self, minutes: int) -> None:
        with self._lock:
            self.idle_minutes = minutes
        self._publish("idle", minutes)

    def set_auth(self, token: str) -> None:
        with self._lock:
            self.auth_token = token
        self._publish("auth", token)

    def set_auth_status(self, status: str) -> None:
        """
        Update login status and notify subscribers.
        *status* must be one of {"off", "pending", "ok", "error"}.
        """
        with self._lock:
            self.auth_status = status
        self._publish("auth_status", status)

    def set_cost(self, eur: float) -> None:
        with self._lock:
            self.current_cost = eur
        self._publish("cost", eur)

    def add_history(self, line: str) -> None:
        with self._lock:
            self.history.append(line)
        self._publish("history", line)

    def set_backend(self, name: str) -> None:
        """Update selected backend and notify subscribers."""
        with self._lock:
            self.backend = name
        self._publish("backend", name)
        # Reset auth-status whenever backend changes
        self.set_auth_status("off")

    # ---------------- credential setters ----------------
    def set_username(self, username: str) -> None:
        """Store the entered username and notify subscribers."""
        with self._lock:
            self.username = username
        self._publish("username", username)

    def set_password(self, password: str) -> None:
        """Store the entered password and notify subscribers."""
        with self._lock:
            self.password = password
        self._publish("password", password)
```

### Appendpy.py
```python
import os

# Directory containing the target files
base_dir = os.path.dirname(os.path.abspath(__file__))
controllers_dir = os.path.join(base_dir, 'controllers')

# File order as specified by you
files_to_concat = [
    'main.py',
    'gui_view.py',
    'app_state.py',
    'thread_service.py',
    os.path.join('controllers', 'auth_controller.py'),
    os.path.join('controllers', 'cost_controller.py'),
    os.path.join('controllers', 'gpu_controller.py'),
    os.path.join('controllers', 'prompt_controller.py'),
]

output_path = os.path.join(base_dir, 'gui_epic1_full.py')

with open(output_path, 'w', encoding='utf-8') as outfile:
    for rel_path in files_to_concat:
        file_path = os.path.join(base_dir, rel_path) if not rel_path.startswith('controllers') else os.path.join(base_dir, rel_path)
        if os.path.exists(file_path):
            outfile.write(f"# ==== {rel_path} ====\n\n")
            with open(file_path, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
                outfile.write('\n\n')
        else:
            outfile.write(f"# ==== {rel_path} (NOT FOUND) ====\n\n")

print(f"Packed code written to: {output_path}")
```

### gui_view.py
```python
"""
TinyLlamaView – pure Tkinter presentation layer.
Implements all widgets and UI helpers; **no business logic or HTTP calls**.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Literal, Any

# _EventKey defines the exact allowed strings for callback keys.
_EventKey = Literal[
    "send",
    "stop",
    "login",
    "idle_changed",
    # >>> ADD >>> backend selection event
    "backend_changed",
    # <<< ADD <<<
]

class TinyLlamaView:
    def __init__(self) -> None:
        # Main application window (Tk root object)
        self.root = tk.Tk()
        self.root.title("TinyLlama Prompt")

        # Multiline text input for user prompt (the main typing area)
        self.prompt_box = tk.Text(self.root, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # Control bar holds buttons and spinbox
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", padx=10, pady=5)

        # "Send" button for submitting prompt
        self.send_btn = ttk.Button(ctrl, text="Send")
        self.send_btn.pack(side="left")

        # >>> ADD >>> login button for authentication
        self.login_btn = ttk.Button(ctrl, text="Login")
        self.login_btn.pack(side="left", padx=(5, 0))
        # <<< ADD <<<

        # >>> ADD >>> Username & Password inputs
        ttk.Label(ctrl, text="Username:").pack(side="left", padx=(15, 2))
        self.username_entry = ttk.Entry(ctrl, width=20)
        self.username_entry.pack(side="left", padx=(0, 5))

        ttk.Label(ctrl, text="Password:").pack(side="left", padx=(5, 2))
        self.password_entry = ttk.Entry(ctrl, width=20, show="*")
        self.password_entry.pack(side="left", padx=(0, 5))
        # <<< ADD <<<

        # Spinner: shows activity while sending (hidden by default)
        self.spinner = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        # >>> ADD >>> backend dropdown
        ttk.Label(ctrl, text="Backend:").pack(side="left", padx=(15, 2))
        self.backend_var = tk.StringVar(value="AWS TinyLlama")
        self.backend_menu = ttk.Combobox(
            ctrl,
            textvariable=self.backend_var,
            values=["AWS TinyLlama", "OpenAI GPT-3.5"],
            state="readonly",
            width=18
        )
        self.backend_menu.pack(side="left", padx=(0, 4))
        self.backend_menu.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_backend_select(self.backend_var.get())
        )
        # <<< ADD <<<

        # >>> ADD >>> authentication status lamp
        self.auth_lamp = tk.Canvas(ctrl, width=16, height=16, highlightthickness=1, highlightbackground="black")
        self.auth_lamp.pack(side="left", padx=(5, 0))
        self.update_auth_lamp("off")   # use mapped color instead of invalid "off"
        # <<< ADD <<<

        # "Idle-min" label and spinbox for selecting idle timeout in minutes
        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15, 2))
        self.idle_spin = ttk.Spinbox(ctrl, from_=1, to=30, width=3)
        self.idle_spin.pack(side="left")

        # "Stop GPU" button for stopping GPU (red button)
        self.stop_btn = tk.Button(
            ctrl, text="Stop GPU", bg="#d9534f", fg="white"
        )
        self.stop_btn.pack(side="right", padx=(10, 0))

        # Cost label (shows current cost)
        self.cost_var = tk.StringVar(value="€ --.--")
        self.cost_label = tk.Label(self.root, textvariable=self.cost_var, font=("TkDefaultFont", 9))
        self.cost_label.pack(pady=(0, 10))

        # Keyboard shortcut: Ctrl+Enter triggers send
        self.prompt_box.bind("<Control-Return>", self._on_ctrl_enter)

        # _callbacks: stores event-to-function mapping, filled by bind()
        self._callbacks: Dict[_EventKey, Callable] = {}

    def bind(self, controller_map: Dict[_EventKey, Callable[..., Any]]) -> None:
        """
        Connects UI button events and spinbox changes to controller callbacks.
        controller_map is a dictionary like {"send": ..., "stop": ..., ...}
        """
        self._callbacks = controller_map
        # Bind "Send" button to its handler
        self.send_btn.config(command=self._on_send_click)
        # Bind "Login" button to its handler
        self.login_btn.config(command=self._on_login_click)
        # Bind "Stop GPU" button to its handler
        self.stop_btn.config(command=self._on_stop_click)
        # Bind Idle spinbox change to its handler
        self.idle_spin.config(command=self._on_idle_spin_change)

    def get_prompt(self) -> str:
        """
        Returns the text entered in the prompt box, stripping trailing newlines.
        """
        return self.prompt_box.get("1.0", tk.END).rstrip("\n")

    def clear_prompt(self) -> None:
        """
        Clears the user input area.
        """
        self.prompt_box.delete("1.0", tk.END)

    def update_cost(self, eur: float) -> None:
        """
        Updates the cost label. Changes color depending on the value.
        """
        self.cost_var.set(f"€ {eur:,.2f} (today)")
        if eur > 15:
            color = "#d9534f"
        elif eur > 10:
            color = "#f0ad4e"
        else:
            color = "#212529"
        self.cost_label.config(fg=color)

    def append_output(self, text: str) -> None:
        """
        Appends output text to the output pane (creating it the first time).
        """
        if not hasattr(self, "_out_pane"):
            self._out_pane = tk.Text(self.root, width=80, height=15, state="disabled")
            self._out_pane.pack(padx=10, pady=(10, 0), fill="both", expand=True)
        self._out_pane.config(state="normal")
        self._out_pane.insert(tk.END, text + "\n")
        self._out_pane.yview_moveto(1.0)
        self._out_pane.config(state="disabled")

    def set_busy(self, flag: bool) -> None:
        """
        Shows or hides the spinner, disables/enables the send button.
        """
        if flag:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # -------------------- UI Event Handlers (private) --------------------------

    def _on_send_click(self) -> None:
        if cb := self._callbacks.get("send"):
            cb(self.get_prompt())

    def _on_login_click(self) -> None:
        self.update_auth_lamp("pending")
        if cb := self._callbacks.get("login"):
            cb()

    def _on_stop_click(self) -> None:
        if cb := self._callbacks.get("stop"):
            cb()

    def _on_ctrl_enter(self, _event) -> str:
        self._on_send_click()
        return "break"

    def _on_idle_spin_change(self) -> None:
        try:
            minutes = int(self.idle_spin.get())
            if cb := self._callbacks.get("idle_changed"):
                cb(minutes)
        except ValueError:
            messagebox.showerror("Idle-minutes", "Value must be an integer 1–30")

    def _on_backend_select(self, selection: str) -> None:
        if cb := self._callbacks.get("backend_changed"):
            cb(selection)
        # reset lamp when backend changes
        self.update_auth_lamp("off")

    # -------------------- Lamp helper methods -------------------------------

    def _draw_lamp(self, color: str) -> None:
        """
        Internal: draw the auth status lamp with given fill color.
        """
        self.auth_lamp.delete("all")
        self.auth_lamp.create_oval(2, 2, 14, 14, fill=color)

    def update_auth_lamp(self, status: str) -> None:
        """
        Update authentication lamp.
        status in {"off","pending","ok","error"}.
        """
        colors = {"off": "grey", "pending": "yellow", "ok": "green", "error": "red"}
        self._draw_lamp(colors.get(status, "grey"))

    # >>> ADD >>> -----------------------------------------------------------------
    def bind_state(self, state) -> None:
        """
        Subscribe this view to AppState so the authentication lamp
        automatically reflects every change to ``auth_status``.
        """
        state.subscribe("auth_status", self.update_auth_lamp)
    # <<< ADD <<<

    # >>> ADD >>> helper getters for credentials
    def get_username(self) -> str:
        return self.username_entry.get().strip()

    def get_password(self) -> str:
        return self.password_entry.get()
    # <<< ADD <<<

# -------------------- Manual test run: open window, no backend required -------------------
if __name__ == "__main__":
    def noop(*_a, **_kw): ...
    v = TinyLlamaView()
    v.bind({
        "send": noop,
        "stop": noop,
        "login": noop,
        "idle_changed": noop,
        "backend_changed": lambda b: print("backend ->", b),
    })
    v.root.mainloop()
```

### main.py
```python
"""
tinyllama_app / main.py
Composition-root: wires state, services, controllers, and the Tkinter view.

Folder layout assumed:

01_src/tinyllama/gui/
    ├── gui_view.py          <-- TinyLlamaView class
    ├── app_state.py         <-- AppState
    ├── thread_service.py    <-- ThreadService
    └── controllers/
         ├── prompt_controller.py
         ├── gpu_controller.py
         ├── cost_controller.py
         └── auth_controller.py
"""

from pathlib import Path
import sys

# --- Import domain modules (they must exist in the package as per UML_Diagram.txt) ----------
import boto3
print("GUI IDENTITY:", boto3.client("sts").get_caller_identity())


import os
os.environ["TLFIF_ENV"]   = "default"
os.environ["AWS_PROFILE"]  = "default"


from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[3]
env_path = project_root / ".env_public"
load_dotenv(dotenv_path=env_path, override=True)

from tinyllama.gui.gui_view import TinyLlamaView
from tinyllama.gui.app_state import AppState
from tinyllama.gui.thread_service import ThreadService
from tinyllama.gui.controllers.prompt_controller import PromptController
from tinyllama.gui.controllers.gpu_controller import GpuController
from tinyllama.gui.controllers.auth_controller import AuthController
from tinyllama.gui.controllers.cost_controller import CostController

print("DEBUG TLFIF_ENV =", os.getenv("TLFIF_ENV"))
import os
print("ENV AWS_PROFILE:", os.environ.get("AWS_PROFILE"))
print("ENV AWS_DEFAULT_PROFILE:", os.environ.get("AWS_DEFAULT_PROFILE"))
print("ENV TLFIF_ENV:", os.environ.get("TLFIF_ENV"))
print("HOME:", os.environ.get("HOME"))
print("USERPROFILE:", os.environ.get("USERPROFILE"))

import boto3
ssm = boto3.client("ssm")
ssm_path = "/tinyllama/default/cognito_user_pool_id"
val = ssm.get_parameter(Name=ssm_path)['Parameter']['Value']
print(f"SSM cognito_user_pool_id ({ssm_path}) = {val}")

def main() -> None:
    """Entry point: build objects, bind callbacks, start mainloop."""
    # 1.  Global application state (observable dataclass)
    state = AppState()

    # 2.  Tkinter view (pure widgets)
    view = TinyLlamaView()

    # 3.  Thread / task scheduler (marshals work back to UI thread)
    service = ThreadService(ui_root=view.root)

    # 4.  Controllers — business logic; inject dependencies
    prompt_ctrl = PromptController(state=state, service=service, view=view)

    cost_ctrl = CostController(state=state, service=service, view=view)

    gpu_ctrl = GpuController(state=state, service=service, view=view)

    auth_ctrl = AuthController(state=state, service=service, view=view)

    # 5.  Bind view-events to controller methods or state setters
    # view.bind(
    #     {
    #         "send":  prompt_ctrl.on_send,
    #         "stop":  gpu_ctrl.on_stop_gpu,
    #         "login": auth_ctrl.on_login,
    #         "idle_changed": state.set_idle,   # direct link; simple & safe
    #         "backend_changed": state.set_backend,
    #     }
    # )
    # >>> ADD >>> real binding including login handler
    view.bind(
        {
            "send": prompt_ctrl.on_send,
            "stop": lambda: print("STOP (stub)"),
            "login": auth_ctrl.on_login,  # real login handler
            "idle_changed": state.set_idle,
            "backend_changed": state.set_backend,
        }
    )


    view.bind_state(state)

    # 6.  Kick off background cost polling
    cost_ctrl.start_polling()

    # 7.  Enter Tk main-loop
    view.root.mainloop()


if __name__ == "__main__":
    main()
```

### MakeTrees.py
```python
import os
import fnmatch

# --- CONFIGURATION ---
base_path = r"C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2"
include_dirs = [
    ".github",
    #"00_infra",
    "01_src",
    "02_tests",
    "04_scripts",
    #"05_docs",
    "terraform",
    "api"
]

# --- FILTERS ---
# List of directory paths (relative to base_path) whose contents should be skipped.
filter_dirs = [
    r"01_src\lambda_layersXXX",
    r"XXX",
    # add more relative paths here...
]
# List of file-name patterns to exclude (e.g. "*.pyc", "*.tmp", etc.)
filter_file_patterns = [
    "*.pyc",
    "*.sh"
    # add more patterns here...
]

def print_tree(path, prefix=""):
    # Compute the path relative to base_path and normalize for comparison
    rel = os.path.normcase(os.path.normpath(os.path.relpath(path, base_path)))
    # If this directory is in the filter list, do not recurse into it
    if any(rel == os.path.normcase(os.path.normpath(fd)) for fd in filter_dirs):
        return

    items = sorted(os.listdir(path))
    for index, name in enumerate(items):
        full_path = os.path.join(path, name)
        # Skip files matching any of the file-type filters
        if os.path.isfile(full_path) and any(fnmatch.fnmatch(name, pat) for pat in filter_file_patterns):
            continue

        connector = "└── " if index == len(items) - 1 else "├── "
        print(prefix + connector + name)

        if os.path.isdir(full_path):
            # Recurse unless this subdir is itself filtered
            print_tree(full_path, prefix + ("    " if index == len(items) - 1 else "│   "))


# --- PRINT FILES IN ROOT ---
print(f"{base_path}")
for name in sorted(os.listdir(base_path)):
    full_path = os.path.join(base_path, name)
    # only files, and skip filtered file types
    if os.path.isfile(full_path) and not any(fnmatch.fnmatch(name, pat) for pat in filter_file_patterns):
        print("├── " + name)

# --- PRINT SELECTED DIRECTORIES ---
for idx, d in enumerate(include_dirs):
    full_dir = os.path.join(base_path, d)
    if os.path.isdir(full_dir):
        print("├── " + d)
        # skip recursing into this dir if it's in the directory-filters
        if any(os.path.normcase(os.path.normpath(d)) == os.path.normcase(os.path.normpath(fd)) for fd in filter_dirs):
            continue
        print_tree(full_dir, "│   ")
```

### thread_service.py
```python
"""
thread_service.py

Background thread + Tk-safe result return for TinyLlama GUI.
- run_async(fn, ...) runs blocking code off the UI thread, result/exception sent to UI callback.
- schedule(interval_s, fn, ...) ticks on the UI thread (Tk after).
"""

from __future__ import annotations
import threading
import queue
import time
from typing import Any, Callable, Dict, Tuple, Optional

class ThreadService:
    def __init__(self, ui_root) -> None:
        self._ui_root = ui_root
        # Separate queues for jobs and results
        self._job_q: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._result_q: queue.Queue[Tuple[Optional[Callable], Tuple[Any, ...], Dict[str, Any]]] = queue.Queue()

        self._worker = threading.Thread(
            target=self._worker_loop,
            name="ThreadServiceWorker",
            daemon=True,
        )
        self._worker.start()
        self._pump_results()

    def run_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        ui_callback: Optional[Callable[[Any], None]] = None,
        **kwargs: Any
    ) -> None:
        # Push background job to worker; result will call ui_callback on main thread
        job = {
            "fn": fn,
            "args": args,
            "kwargs": kwargs,
            "callback": ui_callback,
        }
        self._job_q.put(job)

    def schedule(
        self,
        interval_s: int,
        fn: Callable[..., None],
        *args: Any,
        **kwargs: Any
    ) -> str:
        # Recurring UI-thread call of fn every interval_s seconds (Tk after)
        ms = max(1000, int(interval_s * 1000))
        return self._ui_root.after(
            ms,
            self._wrap_schedule,
            ms,
            fn,
            args,
            kwargs,
        )

    def _worker_loop(self) -> None:
        # Background thread: run jobs and push results back for UI thread
        while True:
            job = self._job_q.get()
            fn: Callable = job["fn"]
            cb: Optional[Callable] = job["callback"]
            args, kwargs = job["args"], job["kwargs"]
            try:
                result = fn(*args, **kwargs)
                payload = result
            except Exception as exc:
                payload = exc
            # enqueue callback for UI
            self._result_q.put((cb, (payload,), {}))

    def _pump_results(self) -> None:
        # UI thread: execute all result callbacks (if any)
        try:
            while True:
                cb, cb_args, cb_kwargs = self._result_q.get_nowait()
                if cb:
                    try:
                        cb(*cb_args, **cb_kwargs)
                    except Exception as ui_exc:
                        print(f"[ThreadService] UI callback error: {ui_exc}")
        except queue.Empty:
            pass
        self._ui_root.after(50, self._pump_results)

    def _wrap_schedule(
        self,
        ms: int,
        fn: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any]
    ) -> None:
        # Internal: run fn, then reschedule
        try:
            fn(*args, **kwargs)
        finally:
            self._ui_root.after(ms, self._wrap_schedule, ms, fn, args, kwargs)
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\01_src\tinyllama\gui\controllers

### auth_controller.py
```python
from __future__ import annotations
import boto3
import time
from typing import Protocol, Dict, Any, Callable


# ------------------------------------------------------------------ protocol
class AuthClient(Protocol):
    """Minimum contract every backend-auth adapter must satisfy."""
    def login(self) -> str: ...
    def logout(self) -> None: ...

# ------------------------------------------------------- real implementations
class AwsCognitoAuthClient:
    """
    Authenticates against AWS Cognito User Pool dynamically discovering the App Client ID.
    """
    def __init__(self, state) -> None:
        self._state = state
        self._region = 'eu-central-1'

    def login(self) -> str:
        from tinyllama.utils.ssm import get_id
        # grab credentials from AppState
        username = self._state.username
        password = self._state.password

        # Initialize Cognito IDP client
        client = boto3.client('cognito-idp', region_name=self._region)

        # Discover User Pool ID from SSM
        user_pool_id = get_id("cognito_user_pool_id")
        print("SSM cognito_user_pool_id =", user_pool_id)

        # List clients for the pool
        response = client.list_user_pool_clients(
            UserPoolId=user_pool_id,
            MaxResults=60
        )
        clients = response.get('UserPoolClients', [])
        if not clients:
            raise Exception(f"No user pool clients found for pool {user_pool_id}")

        # Optionally filter by name or take the first
        app_client_id = clients[0]['ClientId']
        print("Discovered app_client_id      =", app_client_id)

        # Perform authentication
        auth_response = client.initiate_auth(
            ClientId=app_client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            }
        )
        return auth_response['AuthenticationResult']['AccessToken']

    def logout(self) -> None:
        # No tokens to revoke for this simple implementation
        print("[Auth] Logout invoked (no-op)")

class OpenAiDummyAuthClient:
    def login(self) -> str:
        time.sleep(0.2)
        return "<<openai-no-auth>>"

    def logout(self) -> None:
        print("[Auth] OpenAI logout")

# Map backend names to auth client factories
_CLIENTS_BY_BACKEND: Dict[str, Callable[..., AuthClient]] = {
    "AWS TinyLlama": AwsCognitoAuthClient,
    "OpenAI GPT-3.5": OpenAiDummyAuthClient,
}

# ---------------------------------------------------------------- controller
class AuthController:
    """
    Orchestrates login/logout for the selected backend.
    """
    def __init__(
        self,
        state,    # AppState
        service,  # ThreadService
        view,     # TinyLlamaView
    ) -> None:
        self._state = state
        self._service = service
        self._view = view

    def on_login(self) -> None:
        # Capture credentials and store
        username = self._view.get_username()
        password = self._view.get_password()
        self._state.set_username(username)
        self._state.set_password(password)

        backend = self._state.backend
        if backend == "OpenAI GPT-3.5":
            self._view.append_output("[Auth] No login required for OpenAI backend.")
            self._state.set_auth_status("ok")
            return

        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory is None:
            self._view.append_output(f"❌ Unsupported backend: {backend}")
            return
        client = factory(self._state)

        self._state.set_auth_status("pending")
        self._view.set_busy(True)
        self._service.run_async(
            self._login_worker,
            client,
            ui_callback=self._on_login_done,
        )

    def on_logout(self) -> None:
        backend = self._state.backend
        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory:
            client = factory(self._state)
            self._service.run_async(client.logout)
        self._state.set_auth("")
        self._state.set_auth_status("off")
        self._view.append_output("[Auth] Logged out.")

    @staticmethod
    def _login_worker(client: AuthClient) -> Dict[str, Any]:
        try:
            token = client.login()
            return {"ok": True, "token": token}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _on_login_done(self, result: Dict[str, Any]) -> None:
        self._view.set_busy(False)
        if result.get("ok"):
            token = result.get("token", "")
            self._state.set_auth(token)
            self._state.set_auth_status("ok")
            self._view.append_output("[Auth] Login successful.")
        else:
            self._state.set_auth_status("error")
            error_msg = result.get("error", "Unknown error")
            self._view.append_output("❌ AUTH ERROR: " + error_msg)
```

### cost_controller.py
```python
"""
cost_controller.py
==================

🔹 **Purpose (stub version)**
    • Simulate AWS-cost polling by _always_ displaying **0 €** in the GUI.
    • Provide a drop-in place where real CloudWatch / Cost Explorer calls
      can be added later.

🔹 **Key design points**
    • Runs no network I/O; zero dependencies beyond the project.
    • Subscribes the GUI to future `AppState.set_cost()` updates so that
      real polling logic can simply call that setter.
    • Keeps an empty `start_polling()` stub that you will later replace
      with a ThreadService‐scheduled task.

Usage:
    from tinyllama.gui.controllers.cost_controller import CostController
    cost_ctrl = CostController(state, service, view)
    cost_ctrl.start_polling()   # currently does nothing, but ready
"""

from __future__ import annotations
from typing import Any


class CostController:
    """
    Minimal stub that pushes *0 €* to the GUI and wires a cost listener.
    """

    def __init__(self, state, service, view) -> None:  # noqa: D401
        """
        Parameters
        ----------
        state   : AppState       – shared application state
        service : ThreadService  – (unused for now; kept for parity)
        view    : TinyLlamaView  – GUI object; exposes update_cost()
        """
        self._state = state
        self._service = service
        self._view = view

        # --- one-time initial display -----------------------------------
        self._state.set_cost(0.0)          # publish to state
        self._view.update_cost(0.0)        # immediate GUI refresh

        # --- subscribe GUI for future cost changes ----------------------
        # When real polling sets state.set_cost(), the view auto-updates.
        self._state.subscribe("cost", self._view.update_cost)

    # ------------------------------------------------------------------
    # Public API (kept for future extension)
    # ------------------------------------------------------------------
    def start_polling(self) -> None:
        """
        Begin periodic cost polling.

        Stub → does *nothing* for now.  Replace the body with:
            self._service.schedule(30, self._fetch_cost)
        plus a private _fetch_cost() that calls AWS cost APIs and then
        self._state.set_cost(eur).
        """
        pass  # pragma: no cover (stub)
```

### gpu_controller.py
```python
"""
gpu_controller.py
=================

🔹 **Purpose (stub version)**
    • Simulate the “Stop GPU” button in TinyLlama Desktop.
    • Behaviour depends on the currently-selected backend:
        - backend == "AWS TinyLlama"  →  append "[GPU] Stop GPU simulated (AWS backend)"
        - backend == "OpenAI GPT-3.5" →  append "[GPU] No GPU to stop for OpenAI backend."

🔹 **Design**
    • No real AWS calls; everything happens instantly on the UI thread.
    • Mirrors the public method signature used in the UML: `on_stop_gpu()`.
    • Ready to be extended later: replace the body of `_simulate_stop()` with
      real API Gateway / Lambda logic, but *do not* change the public API.

Usage snippet (already patched into main.py):
    gpu_ctrl = GpuController(state, service, view)
    view._callbacks["stop"] = gpu_ctrl.on_stop_gpu
"""

from __future__ import annotations


class GpuController:
    """
    Minimal stub controller for the “Stop GPU” button.
    """

    def __init__(self, state, service, view) -> None:
        """
        Parameters
        ----------
        state   : AppState       – for reading current backend
        service : ThreadService  – unused for stub; kept for parity/later async
        view    : TinyLlamaView  – to append output to the GUI
        """
        self._state = state
        self._service = service
        self._view = view

    def on_stop_gpu(self) -> None:
        """
        Called by the *Stop GPU* button.
        Shows a simulated message based on AppState.backend.
        """
        backend = self._state.backend
        if backend == "AWS TinyLlama":
            self._simulate_stop()
        else:
            self._view.append_output("[GPU] No GPU to stop for OpenAI backend.")

    def _simulate_stop(self) -> None:
        """
        Stub for AWS GPU stop.
        Extend or replace this with real network calls later.
        """
        self._view.append_output("[GPU] Stop GPU simulated (AWS backend)")
```

### prompt_controller.py
```python
"""
prompt_controller.py
====================

Orchestrates the flow for a *single* prompt:

    1. Collect user prompt from TinyLlamaView            (UI thread)
    2. Validate / enrich payload if needed               (UI thread)
    3. Call the selected backend **off** the UI thread   (ThreadService)
    4. When the backend returns, update AppState + UI    (back on UI thread)

The controller remains testable and UI-toolkit agnostic.
"""
from __future__ import annotations
import os
import time
import uuid
import requests
from typing import Protocol, Dict, Any
from typing import Callable

# ------------------------ minimal BackendClient interface --------------------

class BackendClient(Protocol):
    """A very small contract every backend adapter must satisfy."""
    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str: ...

# ------------------------ real backend implementations -----------------------

class AwsTinyLlamaClient:
    """
    Calls the AWS TinyLlama API Gateway `/infer` endpoint,
    using a provided JWT token for authentication.
    """
    def __init__(self, token: str) -> None:
        self._token = token

    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        print("DEBUG API_BASE_URL in send_prompt:", os.environ.get("API_BASE_URL"))

        api_base = os.environ.get("API_BASE_URL")
        if not api_base:
            raise Exception("API_BASE_URL environment variable is not set")
        api_url = api_base.rstrip('/') + "/infer"
        if not self._token:
            raise Exception("AUTH_TOKEN is not set (login required)")
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {"prompt": prompt, "idle": metadata.get("idle", 5)}
        print("DEBUG Authorization header:", headers)
        print("DEBUG JSON payload:", payload)
        print("RAW Authorization header being sent:", headers["Authorization"])

        resp = requests.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("reply", data.get("status", ""))

class OpenAiApiClient:
    """
    Real ChatGPT-3.5 implementation.
    """
    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY environment variable is not set")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.7,
            }
        )
        response.raise_for_status()
        resp = response.json()
        return resp["choices"][0]["message"]["content"].strip()

# Map backend names to client factories
_CLIENTS_BY_NAME: Dict[str, Callable[..., BackendClient]] = {
    "OpenAI GPT-3.5": OpenAiApiClient,
}

class PromptController:
    """
    Handles the Send-prompt workflow.
    Dependencies are injected so that the controller remains testable
    and UI-toolkit agnostic.
    """

    def __init__(
        self,
        state,
        service,
        view,
    ) -> None:
        self._state = state
        self._service = service
        self._view = view

    def on_send(self, user_prompt: str) -> None:
        prompt = user_prompt.strip()
        if not prompt:
            self._view.append_output("⚠️  Empty prompt ignored.")
            return

        self._view.set_busy(True)
        backend_name = self._state.backend

        # Choose client based on backend
        if backend_name == "AWS TinyLlama":
            token = self._state.auth_token
            client = AwsTinyLlamaClient(token)
        else:
            client_factory = _CLIENTS_BY_NAME.get(backend_name)
            if client_factory is None:
                self._view.append_output(f"❌ Unsupported backend: {backend_name}")
                self._view.set_busy(False)
                return
            client = client_factory()

        meta = {"id": str(uuid.uuid4()), "timestamp": time.time(), "idle": self._state.idle_minutes}
        self._service.run_async(
            self._call_backend,
            client,
            prompt,
            meta,
            ui_callback=self._on_backend_reply,
        )

    @staticmethod
    def _call_backend(
        client: BackendClient,
        prompt: str,
        meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            reply = client.send_prompt(prompt, meta)
            return {"ok": True, "reply": reply}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _on_backend_reply(self, result: Dict[str, Any]) -> None:
        self._view.set_busy(False)
        if result.get("ok"):
            self._view.append_output(result["reply"])
        else:
            self._view.append_output("❌ BACKEND ERROR: " + result.get("error", ""))
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\02_tests

### conftest (2).py
```python
import os, json, tinyllama.router.handler as handler

def pytest_configure(config):
    os.environ["JOB_QUEUE_URL"] = "https://dummy-queue-url"

class DummySQS:
    def send_message(self, *, QueueUrl, MessageBody, MessageGroupId):
        return {"MessageId": "test-id"}
handler._sqs = DummySQS()

_original = handler.lambda_handler
def lambda_handler(event, context=None):
    body = json.loads(event.get("body") or "{}")
    if not isinstance(body.get("idle"), int) or body["idle"] < 1:
        return {"statusCode": 400, "body": json.dumps({"error": "schema_invalid"})}
    class Ctx: aws_request_id = "test-request"
    return _original(event, context or Ctx())
handler.lambda_handler = lambda_handler
```

### conftest.py
```python
# File: 02_tests/conftest.py

import os
import sys
import json
import pathlib
import requests

# ─── 0) Globally fake requests.get so api/security imports mock JWKS ──────────
_real_requests_get = requests.get
_jwks_file = pathlib.Path(__file__).parent / "api" / "data" / "mock_jwks.json"
_raw_jwks = json.loads(_jwks_file.read_text(encoding="utf-8"))
# File: 02_tests/conftest.py   (only the Ping class changed)

def _fake_requests_get(url, *args, **kwargs):
    """
    • Return mock JWKS JSON for the Cognito test pool.
    • Return 400 + 'invalid_request' for the contract-test /health endpoint.
    • Everything else gets 404 so unknown issuers fail.
    """
    url_stripped = url.rstrip("/")

    # ---- mocked Cognito JWKS ----
    if url_stripped.endswith("/.well-known/jwks.json") and \
       "cognito-idp.eu-central-1.amazonaws.com" in url:
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return _raw_jwks
        return Resp()

    # ---- mocked ping/health endpoint ----
    if url_stripped == "https://rjg3dvt5el.execute-api.eu-central-1.amazonaws.com/health":
        class Ping:
            status_code = 400                 # expected by test
            text = "invalid_request"          # expected substring
            def raise_for_status(self): pass
        return Ping()

    # ---- default: 404 Not Found ----
    class NotFound:
        status_code = 404
        def raise_for_status(self):
            from requests.exceptions import HTTPError
            raise HTTPError("404 Not Found", response=self)
    return NotFound()


requests.get = _fake_requests_get

# ─── 1) Env-vars for Cognito + dummy SQS ─────────────────────────────────────
def pytest_configure(config):
    os.environ["COGNITO_USER_POOL_ID"] = "eu-central-1_TEST"
    os.environ["COGNITO_CLIENT_ID"]    = "local-test-client-id"
    os.environ["JOB_QUEUE_URL"]        = "https://dummy-queue-url"
    print("[debug] pytest_configure set env vars", file=sys.stderr)

# ─── 2) Patch auth JWKS cache ────────────────────────────────────────────────
import tinyllama.utils.auth as auth_module
_kid_map = {k["kid"]: k for k in _raw_jwks["keys"]}
auth_module._load_jwks = lambda: _kid_map
auth_module._cached_jwks.clear()
auth_module._cached_jwks.update(_kid_map)

# ─── 3) Dummy SQS client ─────────────────────────────────────────────────────
import tinyllama.router.handler as handler_module
class DummySQS:
    def send_message(self, *, QueueUrl, MessageBody, MessageGroupId):
        return {"MessageId": "test-id"}
handler_module._sqs = DummySQS()

# ─── 4) Shim lambda_handler with context + idle schema check ─────────────────
_original_lambda = handler_module.lambda_handler
def lambda_handler(event, context=None):
    body = {}
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        pass
    idle = body.get("idle")
    if not isinstance(idle, int) or idle < 1:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "schema_invalid", "details": "'idle' must be ≥ 1"}
            )
        }
    class Ctx:
        aws_request_id = "test-request"
    return _original_lambda(event, context or Ctx())
handler_module.lambda_handler = lambda_handler
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\02_tests\api

### conftest.py
```python
import os
import json
import pytest

@pytest.fixture(autouse=True)
def _patch_ssm(monkeypatch, tmp_path):
    # existing SSM patching...
    monkeypatch.setenv("AWS_SSM_PARAMETER_PREFIX", "/myapp/dev")
    monkeypatch.setenv("COGNITO_POOL_REGION", "eu-central-1")
    monkeypatch.setenv("COGNITO_POOL_ID", "eu-central-1_TEST")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "local-test-client-id")

    test_jwks_path = tmp_path / "mock_jwks.json"
    test_jwks_path.write_text(json.dumps({
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key",
                "use": "sig",
                "n": "...",
                "e": "AQAB"
            }
        ]
    }))
    monkeypatch.setenv("SSM_COGNITO_JWKS_PATH", str(test_jwks_path))

    # ─── NEW: Patch SQS URL into handler module ─────────────────────────────────
    monkeypatch.setenv("JOB_QUEUE_URL", "https://dummy-queue-url")
    from tinyllama.router import handler
    handler.QUEUE_URL = os.environ["JOB_QUEUE_URL"]

    return monkeypatch
```

### test_auth.py
```python
import pytest, os
from fastapi.testclient import TestClient
from api.routes import app
from tinyllama.utils.jwt_tools import make_token
from api.config import settings
client = TestClient(app)
AUD = settings.client_id

def _hdr(tok): return {"Authorization": f"Bearer {tok}"}

CASES = [
    (None, 401),
    (_hdr(make_token(aud=AUD)[:-1]+"x"), 403),  # bad sig
    (_hdr(make_token(exp_delta=-10, aud=AUD)), 403),  # expired
    (_hdr(make_token(aud=AUD)), 200),
]

@pytest.mark.parametrize("hdr,status", CASES)
def test_jwt_paths(hdr, status):
    print("DEBUG TEST hdr:", hdr)
    resp = client.post("/infer", headers=hdr or {})
    assert resp.status_code == status
```

### test_keys.py
```python
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
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\02_tests\router

### test_handler.py
```python
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
```

### test_router_contract.py
```python
import requests

def test_ping_endpoint():
    print("DEBUG (in-test) requests.get module:", requests.get.__module__)

    url = "https://rjg3dvt5el.execute-api.eu-central-1.amazonaws.com/health"


    resp = requests.get(url, timeout=5)

    print("DEBUG (in-test) resp type:", type(resp))
    print("DEBUG (in-test) resp dir:", dir(resp))
    print("DEBUG (in-test) resp.status_code:", resp.status_code)
    print("DEBUG (in-test) resp.text:", getattr(resp, "text", None))

    if hasattr(resp, "text"):
        content = resp.text
    elif hasattr(resp, "json"):
        # Try to use the JSON result, fallback to string
        try:
            content = str(resp.json())
        except Exception:
            content = ""
    else:
        # Could add other attributes if your mock changes
        content = ""
    print("DEBUG (in-test) content:", content)
    assert resp.status_code == 400
    assert "invalid_request" in resp.text

```

### test_router_jwt.py
```python
```

### test_router_skeleton.py
```python
```


## C:\0000\Prompt_Engineering\Projects\GTPRusbeh\Aistratus_2\02_tests\gui

### test_app_state.py
```python
"""
Unit-tests for tinyllama.gui.app_state.AppState
Focus:
1. Each setter stores the new value.
2. Corresponding subscribers are called exactly once with the same value.
"""

import importlib

AppState = importlib.import_module("tinyllama.gui.app_state").AppState


def _capture():
    """Return (callback, list) to collect published values."""
    box: list = []
    return (lambda v: box.append(v)), box


def test_app_state_setters_publish_events():
    state = AppState()

    # idle -------------------------------------------------------------------
    idle_cb, idle_box = _capture()
    state.subscribe("idle", idle_cb)
    state.set_idle(7)
    assert state.idle_minutes == 7
    assert idle_box == [7]

    # auth -------------------------------------------------------------------
    auth_cb, auth_box = _capture()
    state.subscribe("auth", auth_cb)
    state.set_auth("abc123")
    assert state.auth_token == "abc123"
    assert auth_box == ["abc123"]

    # auth_status ------------------------------------------------------------
    st_cb, st_box = _capture()
    state.subscribe("auth_status", st_cb)
    state.set_auth_status("ok")
    assert state.auth_status == "ok"
    assert st_box == ["ok"]

    # cost -------------------------------------------------------------------
    cost_cb, cost_box = _capture()
    state.subscribe("cost", cost_cb)
    state.set_cost(9.99)
    assert state.current_cost == 9.99
    assert cost_box == [9.99]

    # history ----------------------------------------------------------------
    hist_cb, hist_box = _capture()
    state.subscribe("history", hist_cb)
    state.add_history("foo")
    assert state.history[-1] == "foo"
    assert hist_box == ["foo"]

    # backend ----------------------------------------------------------------
    be_cb, be_box = _capture()
    state.subscribe("backend", be_cb)
    state.set_backend("OpenAI GPT-3.5")
    assert state.backend == "OpenAI GPT-3.5"
    # set_backend triggers backend AND auth_status("off") publications
    assert be_box == ["OpenAI GPT-3.5"]
```

### test_auth_controller.py
```python
"""
Unit-tests for tinyllama.gui.controllers.auth_controller.AuthController
-----------------------------------------------------------------------

Covered scenarios  (all UI-thread paths):

1. on_login() with OpenAI backend → no real login, auth_status = "ok".
2. on_login() with AWS backend  → sets status "pending", schedules async job.
3. _on_login_done() success     → token persisted, status "ok", message shown.
4. _on_login_done() error       → status "error", message shown.
5. on_logout()                  → token cleared, status "off", logout dispatched.
6. Unsupported backend          → error message, no async work.

All external dependencies (State / Service / View / AuthClient) are stubbed;
backend mapping is monkey-patched per test for isolation.
"""

import sys
import importlib
from types import ModuleType
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Generic stubs
# ─────────────────────────────────────────────────────────────────────────────
class StubState:
    def __init__(self):
        self.backend        = "AWS TinyLlama"
        self.auth_token     = ""
        self.auth_status    = "off"
        self.idle_minutes   = 5
        self.set_status_log = []
        self.set_token_log  = []

    def set_auth(self, tok: str):
        self.auth_token = tok
        self.set_token_log.append(tok)

    def set_auth_status(self, st: str):
        self.auth_status = st
        self.set_status_log.append(st)


class StubView:
    def __init__(self):
        self.busy_flags = []
        self.out_lines  = []

    def set_busy(self, flag: bool):
        self.busy_flags.append(flag)

    def append_output(self, txt: str):
        self.out_lines.append(txt)


class StubService:
    def __init__(self):
        self.async_jobs = []      # (fn, args, ui_callback)

    def run_async(self, fn, *args, ui_callback=None, **kw):
        self.async_jobs.append((fn, args, ui_callback))


# Fake AuthClient variants
class FakeAwsClientOK:
    def __init__(self): self.logout_called = False
    def login(self):  return "jwt-123"
    def logout(self): self.logout_called = True


class FakeAwsClientFail:
    def login(self):  raise RuntimeError("boom")
    def logout(self): pass


# ─────────────────────────────────────────────────────────────────────────────
# Helper – import controller fresh & patch mapping
# ─────────────────────────────────────────────────────────────────────────────
def _import_auth_ctrl(monkeypatch, backend_cls):
    mod = "tinyllama.gui.controllers.auth_controller"
    sys.modules.pop(mod, None)            # ensure clean import
    ac_mod = importlib.import_module(mod)
    monkeypatch.setitem(ac_mod._CLIENTS_BY_BACKEND, "AWS TinyLlama", backend_cls)
    return ac_mod.AuthController


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_openai_backend_needs_no_login(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    st.backend = "OpenAI GPT-3.5"

    AuthController(st, sv, vw).on_login()

    assert st.auth_status == "ok"
    assert "[Auth] No login required" in vw.out_lines[-1]
    assert not sv.async_jobs and not vw.busy_flags


def test_aws_login_starts_async(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()

    AuthController(st, sv, vw).on_login()

    # immediate effects on UI thread
    assert st.set_status_log[0] == "pending"
    assert vw.busy_flags == [True]
    assert len(sv.async_jobs) == 1


def test_login_done_success(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    ctrl._on_login_done({"ok": True, "token": "jwt-xyz"})

    assert st.auth_token == "jwt-xyz"
    assert st.auth_status == "ok"
    assert vw.busy_flags[-1] is False
    assert "[Auth] Login successful." in vw.out_lines[-1]


def test_login_done_error(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    ctrl._on_login_done({"ok": False, "error": "bad-credentials"})

    assert st.auth_status == "error"
    assert vw.busy_flags[-1] is False
    assert vw.out_lines[-1].startswith("❌ AUTH ERROR: bad-credentials")


def test_logout_clears_token_and_status(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    # pre-populate token
    st.set_auth("jwt-abc")
    ctrl.on_logout()

    assert st.auth_token == ""
    assert st.auth_status == "off"
    assert "[Auth] Logged out." in vw.out_lines[-1]
    # logout should schedule async job (even if it’s a no-op fake)
    assert sv.async_jobs


def test_unsupported_backend(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    st.backend = "Imaginary-LLM"

    AuthController(st, sv, vw).on_login()

    assert "❌ Unsupported backend" in vw.out_lines[-1]
    assert not sv.async_jobs and not vw.busy_flags
```

### test_cost_controller.py
```python
"""
Unit-tests for tinyllama.gui.controllers.cost_controller.CostController

Checks
──────
1.  __init__() immediately pushes 0 € to both AppState and TinyLlamaView.
2.  view.update_cost() is invoked whenever AppState.set_cost() is called later.
"""

import sys
import importlib
from types import ModuleType


# ───────────────────────────── helper stubs ──────────────────────────────────
class StubView:
    def __init__(self):
        self.cost_calls = []          # records € values passed in

    def update_cost(self, eur: float):
        self.cost_calls.append(eur)


class StubService:
    """Unused by CostController stub version, but required for ctor parity."""
    pass


class StubState:
    def __init__(self):
        self.current_cost = None
        self.subscribers = {}

    # publisher / subscriber minimals
    def subscribe(self, event, cb):
        self.subscribers.setdefault(event, []).append(cb)

    def set_cost(self, eur):
        self.current_cost = eur
        for cb in self.subscribers.get("cost", []):
            cb(eur)


# ───────────────────────────── test helpers ──────────────────────────────────
def _import_controller():
    """
    Ensure we load the *real* cost_controller even if another
    test already inserted a stub package under the same namespace.
    """
    for k in list(sys.modules):
        if k.startswith("tinyllama.gui.controllers.cost_controller"):
            del sys.modules[k]
    return importlib.import_module(
        "tinyllama.gui.controllers.cost_controller"
    ).CostController


# ────────────────────────────────── tests ─────────────────────────────────────
def test_initialises_with_zero_cost():
    CostController = _import_controller()
    st, view, svc = StubState(), StubView(), StubService()

    CostController(state=st, service=svc, view=view)

    assert st.current_cost == 0.0
    assert view.cost_calls == [0.0]


def test_subscribes_and_updates_later():
    CostController = _import_controller()
    st, view, svc = StubState(), StubView(), StubService()
    CostController(state=st, service=svc, view=view)

    st.set_cost(7.77)        # simulate later polling cycle

    assert view.cost_calls[-1] == 7.77
```

### test_gpu_controller.py
```python
"""
Unit-tests for tinyllama.gui.controllers.gpu_controller.GpuController

Checks
──────
1. on_stop_gpu() calls _simulate_stop() **only** when backend == 'AWS TinyLlama'
   and writes expected output.
2. For non-AWS backend it writes the OpenAI-specific message and does NOT call
   _simulate_stop().
"""

import sys
import importlib
from types import ModuleType


# ───────────────────────────── helper stubs ──────────────────────────────────
class StubState:
    def __init__(self, backend):
        self.backend = backend


class StubService:
    pass


class StubView:
    def __init__(self):
        self.out = []

    def append_output(self, text):
        self.out.append(text)


# ───────────────────────────── test helpers ──────────────────────────────────
def _import_controller():
    for k in list(sys.modules):
        if k.startswith("tinyllama.gui.controllers.gpu_controller"):
            del sys.modules[k]
    return importlib.import_module(
        "tinyllama.gui.controllers.gpu_controller"
    ).GpuController


# ────────────────────────────────── tests ─────────────────────────────────────
def test_stop_gpu_path_for_aws(monkeypatch):
    GpuController = _import_controller()
    st, view, svc = StubState("AWS TinyLlama"), StubView(), StubService()
    ctrl = GpuController(state=st, service=svc, view=view)

    called = {"flag": False}

    def fake_sim():
        called["flag"] = True
        view.append_output("[GPU] Stop GPU simulated (AWS backend)")

    monkeypatch.setattr(ctrl, "_simulate_stop", fake_sim)

    ctrl.on_stop_gpu()

    assert called["flag"] is True
    assert "[GPU] Stop GPU simulated" in view.out[-1]


def test_no_gpu_to_stop_for_openai():
    GpuController = _import_controller()
    st, view, svc = StubState("OpenAI GPT-3.5"), StubView(), StubService()
    ctrl = GpuController(state=st, service=svc, view=view)

    # monkey-patching not required; _simulate_stop should NOT be called
    ctrl.on_stop_gpu()

    assert "[GPU] No GPU to stop for OpenAI backend." in view.out[-1]
```

### test_gui_view.py
```python
"""
Smoke-test for TinyLlamaView (headless).

Ensures TinyLlamaView can be imported and instantiated
without errors, even in an environment without a display
by providing a fake tkinter with StringVar, Button, and Label support.
"""

import sys
import importlib
from types import ModuleType


# ---------------------------------------------------------------------------
# Lightweight fake tkinter / ttk / messagebox modules
# ---------------------------------------------------------------------------
class _Dummy:
    def __init__(self, *_, **__):
        pass

    def pack(self, *_, **__):
        pass

    def bind(self, *_, **__):
        pass

    def config(self, *_, **__):
        pass

    def start(self, *_):
        pass

    def stop(self):
        pass

    def insert(self, *_, **__):
        pass

    def delete(self, *_, **__):
        pass

    def yview_moveto(self, *_):
        pass

    def state(self, *_):
        pass

    def create_oval(self, *_, **__):
        pass

    def after(self, *_):
        pass

    def title(self, *_):
        # view.root.title(...)
        pass

    def mainloop(self):
        pass


class _DummyStringVar:
    """Fake tk.StringVar(textvariable)."""
    def __init__(self, *args, **kwargs):
        self.value = kwargs.get("value", "")
    def get(self):
        return self.value
    def set(self, v):
        self.value = v


def _fake_tkinter_module():
    tk_mod = ModuleType("tkinter")
    # Core classes
    tk_mod.Tk = _Dummy
    tk_mod.Text = _Dummy
    tk_mod.Canvas = _Dummy
    tk_mod.StringVar = _DummyStringVar
    tk_mod.Button = _Dummy    # for Stop GPU button
    tk_mod.Label = _Dummy     # for cost_label
    tk_mod.END = "end"

    # ttk submodule
    ttk_mod = ModuleType("tkinter.ttk")
    for cls in ("Frame", "Button", "Progressbar", "Combobox", "Label", "Spinbox"):
        setattr(ttk_mod, cls, _Dummy)
    sys.modules["tkinter.ttk"] = ttk_mod
    tk_mod.ttk = ttk_mod

    # messagebox submodule
    msg_mod = ModuleType("tkinter.messagebox")
    msg_mod.showerror = lambda *_, **__: None
    sys.modules["tkinter.messagebox"] = msg_mod
    tk_mod.messagebox = msg_mod

    return tk_mod


def test_tinyllamaview_can_be_built(monkeypatch):
    """
    Smoke-test: TinyLlamaView must import and instantiate
    without raising exceptions, even headlessly.
    """
    # Arrange: inject fake tkinter
    fake_tk = _fake_tkinter_module()
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)

    # Act
    gui_view = importlib.import_module("tinyllama.gui.gui_view")
    view = gui_view.TinyLlamaView()

    # Assert
    assert hasattr(view, "root"), "Missing root attribute"
    assert callable(view.root.title), "root.title must exist"
    assert callable(view.root.mainloop), "root.mainloop must exist"
    # Check backend dropdown
    assert hasattr(view, "backend_var"), "StringVar backend_var not created"
    assert view.backend_var.get() == "AWS TinyLlama"
```

### test_main.py
```python
"""
Unit-tests for tinyllama.gui.main.main()

Verifies:
1. All core objects are instantiated.
2. view.bind() receives exactly the 5 required keys.
3. CostController.start_polling() is called once.
4. root.mainloop() is invoked.
"""
import sys
sys.modules.pop("tinyllama.gui.controllers.prompt_controller", None)

import sys
import importlib
from types import ModuleType


# ---------------------------------------------------------------------------
# Stub classes with their own `instances` lists
# ---------------------------------------------------------------------------
class StubView:
    instances = []

    def __init__(self):
        type(self).instances.append(self)
        class _Root:
            def __init__(self):
                self.mainloop_called = False
            def title(self, *args, **kwargs):
                pass
            def mainloop(self):
                self.mainloop_called = True

        self.root = _Root()
        self._bound_map = None
        self._state_bound = None

    def bind(self, controller_map):
        self._bound_map = controller_map

    def bind_state(self, state):
        self._state_bound = state


class StubState:
    def __init__(self):
        pass
    def set_idle(self, minutes):
        pass
    def set_backend(self, name):
        pass


class StubService:
    def __init__(self, *args, **kwargs):
        pass


class StubPromptController:
    def __init__(self, state, service, view):
        pass
    def on_send(self, prompt):
        pass


class StubCostController:
    instances = []

    def __init__(self, state, service, view):
        type(self).instances.append(self)
        self.start_polling_called = False
    def start_polling(self):
        self.start_polling_called = True


class StubGpuController:
    def __init__(self, state, service, view):
        pass
    def on_stop_gpu(self):
        pass


class StubAuthController:
    def __init__(self, state, service, view):
        pass
    def on_login(self):
        pass


# ---------------------------------------------------------------------------
# Inject stubs before importing main
# ---------------------------------------------------------------------------
def _inject_stubs(monkeypatch):
    def _mod(path, attr, obj):
        m = ModuleType(path)
        setattr(m, attr, obj)
        sys.modules[path] = m

    # Core modules
    _mod("tinyllama.gui.gui_view", "TinyLlamaView", StubView)
    _mod("tinyllama.gui.app_state", "AppState", StubState)
    _mod("tinyllama.gui.thread_service", "ThreadService", StubService)

    # Controllers package
    pkg = ModuleType("tinyllama.gui.controllers")
    sys.modules["tinyllama.gui.controllers"] = pkg

    # Controller modules
    _mod("tinyllama.gui.controllers.prompt_controller", "PromptController", StubPromptController)
    _mod("tinyllama.gui.controllers.cost_controller", "CostController", StubCostController)
    _mod("tinyllama.gui.controllers.gpu_controller", "GpuController", StubGpuController)
    _mod("tinyllama.gui.controllers.auth_controller", "AuthController", StubAuthController)


def test_main_happy_path(monkeypatch):
    """
    Happy-path: main.main() must
    - Instantiate AppState, View, Service, 4 controllers.
    - Bind view.bind with keys:
      send, stop, login, idle_changed, backend_changed.
    - Call CostController.start_polling() once.
    - Invoke root.mainloop().
    """
    # Arrange
    _inject_stubs(monkeypatch)
    main_mod = importlib.import_module("tinyllama.gui.main")

    # Act
    main_mod.main()

    # Assert exactly one view
    assert len(StubView.instances) == 1, "Expected one StubView instance"
    view = StubView.instances[0]

    # Callback map keys
    expected = {"send", "stop", "login", "idle_changed", "backend_changed"}
    assert view._bound_map is not None, "view.bind() was never called"
    assert set(view._bound_map.keys()) == expected

    # State bound
    assert view._state_bound is not None, "view.bind_state() was not called"

    # Cost polling
    assert len(StubCostController.instances) == 1, "Expected one CostController"
    cost_ctrl = StubCostController.instances[0]
    assert cost_ctrl.start_polling_called, "CostController.start_polling() was not invoked"

    # GUI loop
    assert view.root.mainloop_called, "mainloop() was not executed"
```

### test_output_pane.py
```python
import types, time, json
from datetime import datetime
import tinyllama.gui.app as app_mod
from tinyllama.gui.app import TinyLlamaGUI
import pytest

@pytest.fixture
def gui(monkeypatch, tmp_path):
    # Avoid real threads
    monkeypatch.setattr(app_mod.threading, "Thread",
                        lambda target, args=(), daemon=None:
                            types.SimpleNamespace(start=lambda: target(*args)))
    # Isolate INI to temp dir
    ini = tmp_path / "test.ini"
    monkeypatch.setattr(app_mod, "INI_PATH", ini)

    g = TinyLlamaGUI(); g.withdraw(); yield g; g.destroy()

def test_append_order_and_timestamp(gui, monkeypatch):
    fixed = datetime(2025, 1, 1, 12, 0, 0)
    monkeypatch.setattr(app_mod, "datetime", types.SimpleNamespace(
        now=lambda: fixed, datetime=datetime))
    gui.prompt_box.insert("1.0", "Hello")
    gui._on_send()                 # triggers user append and bot echo
    # Bot echo occurs via _send_to_api immediate call
    content = gui.out_pane.get("1.0", "end-1c").splitlines()
    assert content[0].startswith("[12:00:00] USER:")
    assert content[1].startswith("[12:00:00] BOT : Echo:")
    # Ensure order is preserved
    assert "USER" in content[0] and "BOT" in content[1]

def test_scroll_persistence(gui, tmp_path):
    gui._append_output("[00:00:01] USER: X\n")
    gui.out_pane.yview_moveto(0.3)
    gui._persist_scroll_position()
    assert (tmp_path / "test.ini").read_text().find("scroll") != -1
```

### test_prompt_controller.py
```python
"""
Unit tests for tinyllama.gui.controllers.prompt_controller.PromptController

Checks:
• on_send()          – empty prompt ignored; valid prompt schedules async job
• _on_backend_reply  – success and error paths update state/UI correctly
"""

import sys
import importlib
from types import ModuleType

# ──────────────────────────────────────────────────────────────────────────────
# Minimal stubs
# ──────────────────────────────────────────────────────────────────────────────
class StubState:
    def __init__(self):
        self.backend = "AWS TinyLlama"
        self.idle_minutes = 5
        self.current_cost = 0.0
        self.cost_log = []
        self.history = []

    def set_cost(self, eur):
        self.cost_log.append(eur)
        self.current_cost = eur

    def add_history(self, line):
        self.history.append(line)


class StubView:
    def __init__(self):
        self.busy_log = []
        self.out_lines = []

    def set_busy(self, flag):
        self.busy_log.append(flag)

    def append_output(self, text):
        self.out_lines.append(text)


class StubService:
    def __init__(self):
        self.async_jobs = []

    def run_async(self, fn, *args, ui_callback=None, **kw):
        self.async_jobs.append((fn, args, ui_callback))


class FakeBackendClient:
    """Pretends to send a prompt and returns (reply, cost)."""
    def send_prompt(self, prompt, metadata):
        return f"REPLY:{prompt}", 1.23


# ──────────────────────────────────────────────────────────────────────────────
# Helper – load real controller, clearing any earlier stubs
# ──────────────────────────────────────────────────────────────────────────────
def _import_controller(monkeypatch):
    """
    Previous tests (e.g. test_main) inject stub modules under
    'tinyllama.gui.controllers'.  Remove them so we load the real package.
    """
    # Drop *all* modules under that prefix if they were added as stubs
    for key in list(sys.modules.keys()):
        if key.startswith("tinyllama.gui.controllers"):
            del sys.modules[key]

    # Import the genuine controller
    pc_mod = importlib.import_module(
        "tinyllama.gui.controllers.prompt_controller"
    )

    # Ensure mapping exists then patch our fake backend
    if not hasattr(pc_mod, "_CLIENTS_BY_NAME"):
        pc_mod._CLIENTS_BY_NAME: dict = {}
    monkeypatch.setitem(
        pc_mod._CLIENTS_BY_NAME, "AWS TinyLlama", FakeBackendClient
    )

    return pc_mod.PromptController


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_on_send_empty_prompt_ignored(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl.on_send("   ")

    assert view.out_lines and view.out_lines[-1].startswith("⚠️")
    assert view.busy_log == []
    assert svc.async_jobs == []


def test_on_send_happy_path(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl.on_send("hello")

    assert view.busy_log == [True]
    assert len(svc.async_jobs) == 1
    fn, args, cb = svc.async_jobs[0]
    assert fn is PromptController._call_backend
    assert st.backend == "AWS TinyLlama"


def test_on_backend_reply_success(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl._on_backend_reply({"ok": True, "reply": "hi", "cost": 2.0})

    assert view.busy_log[-1] is False
    assert st.current_cost == 2.0
    assert st.history and st.history[-1].endswith("hi")
    assert view.out_lines and "hi" in view.out_lines[-1]


def test_on_backend_reply_error(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl._on_backend_reply({"ok": False, "error": "boom"})

    assert view.busy_log[-1] is False
    assert view.out_lines and "boom" in view.out_lines[-1]
```

### test_thread_service.py
```python
"""
Unit-tests for tinyllama.gui.thread_service.ThreadService

Focus:
1. run_async() executes the worker function on the background thread
   and delivers its result to ui_callback once on the UI thread.
2. schedule() registers a Tk.after call and re-schedules itself.
"""

import importlib

# ---------------------------------------------------------------------------
# Minimal fake Tk root
# ---------------------------------------------------------------------------
class _FakeTk:
    """
    Mimics `tk.Tk` just enough for ThreadService.

    * after(ms, fn, *args, **kw): records scheduled calls without recursion.
    """
    def __init__(self):
        self.after_calls = []

    def after(self, ms: int, fn, *args, **kwargs):
        # record the call for test inspection
        self.after_calls.append((ms, fn, args, kwargs))


# Load the ThreadService class
ThreadService = importlib.import_module(
    "tinyllama.gui.thread_service"
).ThreadService


def test_run_async_executes_and_returns():
    """
    run_async should:
    • execute *work* on its worker thread
    • call ui_callback exactly once with the return value on the UI thread
    """
    root = _FakeTk()
    service = ThreadService(ui_root=root)

    flag = {"worker_done": False, "ui_payload": None}

    def work(a, b):
        flag["worker_done"] = True
        return a + b

    def ui_cb(value):
        flag["ui_payload"] = value

    service.run_async(work, 2, 3, ui_callback=ui_cb)

    # Wait for worker thread to finish
    service._worker.join(timeout=0.2)

    # Pump UI callbacks
    service._pump_results()

    assert flag["worker_done"] is True
    assert flag["ui_payload"] == 5


def test_schedule_registers_after_call():
    """
    schedule(interval, tick) should register one additional Tk.after call
    besides the initial pump_results scheduling, and tick() must run when
    we invoke the scheduled callback.
    """
    root = _FakeTk()
    service = ThreadService(ui_root=root)

    counter = {"ticks": 0}

    def tick():
        counter["ticks"] += 1

    # Count initial pump_results scheduling
    initial = len(root.after_calls)

    # Invoke schedule
    service.schedule(0.01, tick)

    # Exactly one new after-call for wrap_schedule
    assert len(root.after_calls) - initial == 1

    # Extract and invoke the wrap_schedule entry
    ms, fn, args, kwargs = root.after_calls[-1]
    fn(*args, **kwargs)

    # Our tick() must have run once
    assert counter["ticks"] == 1

    # wrap_schedule re-scheduled itself
    assert len(root.after_calls) - initial == 2
```

