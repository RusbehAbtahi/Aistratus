import os, json, uuid
from http import HTTPStatus
from tinyllama.utils.auth import verify_jwt   # shared helper

_DISABLED = os.getenv("TL_DISABLE_LAM_ROUTER", "1") == "1"

def _resp(code, body):
    return {"statusCode": code.value, "body": json.dumps(body)}

def handler(event, _ctx):
    if _DISABLED:
        return _resp(HTTPStatus.SERVICE_UNAVAILABLE,
                     {"error": "Router disabled (LAM-001 phase)"})

    # JWT --------------------------------------------------------------
    auth = event.get("headers", {}).get("Authorization", "")
    try:
        scheme, token = auth.split()
        assert scheme.lower() == "bearer"
        verify_jwt(token)
    except Exception:
        return _resp(HTTPStatus.UNAUTHORIZED, {"error": "JWT missing/invalid"})

    # Body -------------------------------------------------------------
    try:
        body = json.loads(event.get("body") or "{}")
        prompt = body["prompt"]
    except (KeyError, json.JSONDecodeError):
        return _resp(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON or prompt"})
    if not isinstance(prompt, str) or len(prompt) > 6_000:
        return _resp(HTTPStatus.BAD_REQUEST, {"error": "Prompt too large"})

    # Placeholder until Redis / EC2 logic (LAM-003/004)
    return _resp(HTTPStatus.ACCEPTED,
                 {"status": "queued", "id": str(uuid.uuid4())})