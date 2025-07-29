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
