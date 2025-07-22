import json
import os

# PyJWT exception types
from jose.exceptions import ExpiredSignatureError, JWTError


# Project helpers
from tinyllama.utils.auth   import verify_jwt
from tinyllama.utils.schema import PromptReq


def lambda_handler(event, context):
    """AWS Lambda entry-point for TinyLlama Router v2 (LAM-001 scope)."""

    # ------------------------------------------------------------------ body
    try:
        body = PromptReq.model_validate_json(event.get("body", ""))
    except Exception as exc:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "invalid_request", "details": str(exc)}),
        }

    # -------------------------------------------------------------- auth hdr
    auth_header = event.get("headers", {}).get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "missing_token"}),
        }

    # ------------------------------------------------------------ jwt check
    try:
        verify_jwt(token)
    except ExpiredSignatureError as exc:
        print("DEBUG CAUGHT: ExpiredSignatureError:", exc)
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "token_expired"}),
        }
    except JWTError as exc:
        print("DEBUG CAUGHT: JWTError:", exc)
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "invalid_token"}),
        }
    except Exception as exc:
        print("DEBUG CAUGHT: General Exception:", type(exc), exc)
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "invalid_token"}),
        }

    # ----------------------------------------------------------- happy path
    # (LAM-001 ends here – later epics will enqueue, etc.)
    return {
        "statusCode": 202,
        "body": json.dumps({"status": "queued"}),
    }
