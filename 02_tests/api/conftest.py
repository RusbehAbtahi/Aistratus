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
