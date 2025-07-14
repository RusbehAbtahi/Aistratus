import json
import os
from pydantic import ValidationError
from tinyllama.utils.auth import verify_jwt
from tinyllama.utils.schema import PromptReq

def lambda_handler(evt, ctx):
    # ----- auth ------------------------------------------------------------
    hdr = evt.get("headers", {}).get("authorization", "")
    token = hdr.removeprefix("Bearer ").strip()
    try:
        verify_jwt(
            token,
            os.environ["COGNITO_ISSUER"],
            os.environ["COGNITO_AUD"],
        )
    except Exception as exc:  # precise exception types already raised in auth.py
        status = 401 if "token" in str(exc) else 403
        return {
            "statusCode": status,
            "body": json.dumps({"error": str(exc)}),
        }

    # ----- body validation -------------------------------------------------
    try:
        body = PromptReq.model_validate_json(evt.get("body", ""))
    except (ValidationError, json.JSONDecodeError) as exc:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(exc)}),
        }

    # ----- happy path ------------------------------------------------------
    # LAM-001 ends here – LAM-002 will enqueue
    _ = body  # placeholder to avoid linter warning
    return {
        "statusCode": 202,
        "body": json.dumps({"status": "queued"}),
    }
