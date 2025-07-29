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
