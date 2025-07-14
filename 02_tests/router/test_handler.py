import importlib
import json
from tinyllama.utils.jwt_tools import make_token      # test helper
from tinyllama.router import handler as router_mod


def make_event(token: str, body: dict):
    return {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body),
    }


def test_happy_path(monkeypatch):
    token = make_token()               # valid, non-expired

    event = make_event(token, {"prompt": "hi", "idle": 5})

    resp = router_mod.lambda_handler(event, None)
    assert resp["statusCode"] == 202


def test_schema_fail():
    token = make_token()
    # idle out of range
    event = make_event(token, {"prompt": "hi", "idle": 0})

    resp = router_mod.lambda_handler(event, None)
    assert resp["statusCode"] == 400
    assert "idle" in resp["body"]


def test_bad_token():
    bad_token = "abc.def.ghi"
    event = make_event(bad_token, {"prompt": "hi", "idle": 5})

    resp = router_mod.lambda_handler(event, None)
    # verify_jwt raises → 401 or 403, depending on failure path
    assert resp["statusCode"] in (401, 403)


def test_expired_token(monkeypatch):
    old_token = make_token(expired=True)
    event = make_event(old_token, {"prompt": "hi", "idle": 5})

    resp = router_mod.lambda_handler(event, None)
    assert resp["statusCode"] == 401
